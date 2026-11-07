# -*- coding: utf-8 -*-
"""统一伤害计算与抗性系统（v2.9.12）

设计目标
--------
1. **所有实体共用一份计算**：玩家、僵尸、Boss、载具都走 `resolve_damage()`，
   不再各写各的 `*= (1 - ...)`。
2. **伤害 = 基础伤害 × 伤害倍率**：`DamagePacket(base=, mult=)`，
   倍率来自技能等级 / 暴击 / 狂暴 / 符文，基础值来自数据库。
3. **抗性按通道**：物理 / 燃烧 / 冰冻 / 中毒 / 雷电 / 爆炸 / 魔法 / 真实，
   每个实体一份 `ResistanceSet`，数值由数据库 `resistances` 表权威提供。
4. **可追溯**：`DamageResult` 保留每一步，死亡详情 / 命中反馈 / 调试面板
   都能拿到"原始多少、被抗性吃掉多少、最终多少"。

兼容性
------
旧代码大量调用 `take_damage(30, damage_type="fire")`，所以 `DamagePacket`
支持从裸数字构造；`coerce_packet()` 统一转换，调用方零改动即可享受抗性。
"""
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

# ---------------------------------------------------------------- 通道定义
CHANNELS = (
    "physical", "fire", "ice", "poison", "lightning",
    "explosion", "magic", "true",
)

# 旧代码里的 damage_type → 抗性通道。
# 未列出的类型一律归到 physical（保守，不会因为拼错而绕过抗性）。
TYPE_TO_CHANNEL = {
    "melee": "physical", "ranged": "physical", "normal": "physical",
    "physical": "physical", "bullet": "physical", "ram": "physical",
    "fire": "fire", "burn": "fire", "flame": "fire",
    "ice": "ice", "freeze": "ice", "frost": "ice", "cold": "ice",
    "poison": "poison", "toxic": "poison", "dot": "poison",
    "lightning": "lightning", "electric": "lightning", "chain": "lightning",
    "explosion": "explosion", "explosive": "explosion",
    "magic": "magic", "aoe": "magic", "void": "magic", "laser": "magic",
    "true": "true", "execute": "true",
}

# ---------------------------------------------------------------- 默认抗性
# 数据库不可用时的兜底，同时也是播种数据来源（单一来源，不会分叉）。
# 数值含义：0.0 = 无抗性，0.5 = 减半，1.0 = 免疫；负数 = 易伤。
DEFAULT_PROFILES: Dict[str, Dict[str, float]] = {
    "PLAYER": {c: 0.0 for c in CHANNELS},
    "ZOMBIE": {c: 0.0 for c in CHANNELS},
    "RUNNER": {"physical": 0.0, "fire": -0.15, "ice": 0.10, "poison": 0.0,
               "lightning": 0.0, "explosion": 0.0, "magic": 0.0, "true": 0.0},
    "FAT": {"physical": 0.20, "fire": 0.0, "ice": 0.0, "poison": 0.10,
            "lightning": 0.0, "explosion": -0.10, "magic": 0.0, "true": 0.0},
    "SHIELD": {"physical": 0.45, "fire": -0.20, "ice": 0.0, "poison": 0.0,
               "lightning": 0.0, "explosion": 0.0, "magic": 0.0, "true": 0.0},
    "ARMORED": {"physical": 0.35, "fire": 0.10, "ice": 0.10, "poison": 0.20,
                "lightning": -0.10, "explosion": 0.10, "magic": 0.0, "true": 0.0},
    "GHOST": {"physical": 0.30, "fire": 0.0, "ice": 0.0, "poison": 0.0,
              "lightning": 0.0, "explosion": 0.0, "magic": -0.25, "true": 0.0},
    "FIRE": {"physical": 0.0, "fire": 0.80, "ice": -0.35, "poison": 0.0,
             "lightning": 0.0, "explosion": 0.0, "magic": 0.0, "true": 0.0},
    "TOXIC": {"physical": 0.0, "fire": -0.20, "ice": 0.0, "poison": 0.85,
              "lightning": 0.0, "explosion": 0.0, "magic": 0.0, "true": 0.0},
    "ELECTRIC": {"physical": 0.0, "fire": 0.0, "ice": 0.0, "poison": 0.0,
                 "lightning": 0.80, "explosion": 0.0, "magic": 0.0, "true": 0.0},
    "BOSS": {"physical": 0.15, "fire": 0.10, "ice": 0.10, "poison": 0.15,
             "lightning": 0.10, "explosion": 0.10, "magic": 0.10, "true": 0.0},
    "ELITE": {"physical": 0.10, "fire": 0.05, "ice": 0.05, "poison": 0.10,
              "lightning": 0.05, "explosion": 0.05, "magic": 0.05, "true": 0.0},
    "VEHICLE": {"physical": 0.30, "fire": 0.0, "ice": 0.0, "poison": 0.50,
                "lightning": 0.0, "explosion": 0.20, "magic": 0.0, "true": 0.0},
}

# 实体 profile 推断（不依赖具体枚举，纯字符串匹配，新增僵尸类型零改动）
def profile_for(enemy_key: str = "", is_boss: bool = False,
                is_elite: bool = False) -> str:
    k = str(enemy_key or "").upper()
    if is_boss:
        return "BOSS"
    for token, prof in (("FIRE", "FIRE"), ("BURN", "FIRE"), ("FLAME", "FIRE"),
                        ("TOXIC", "TOXIC"), ("POISON", "TOXIC"), ("GAS", "TOXIC"),
                        ("ELECTRIC", "ELECTRIC"), ("SHOCK", "ELECTRIC"),
                        ("SHIELD", "SHIELD"), ("ARMOR", "ARMORED"),
                        ("GHOST", "GHOST"), ("PHANTOM", "GHOST"),
                        ("FAT", "FAT"), ("TANK", "FAT"),
                        ("RUNNER", "RUNNER"), ("CRAWLER", "RUNNER")):
        if token in k:
            return prof
    if is_elite:
        return "ELITE"
    return "ZOMBIE"


# ---------------------------------------------------------------- 数据库读取
_PROFILE_CACHE: Dict[str, "ResistanceSet"] = {}
_DB_LOADED = False


def _load_db_profiles():
    """从 gamedata 数据库读 resistances 表（只跑一次，失败用默认值）"""
    global _DB_LOADED
    _DB_LOADED = True
    try:
        from gamedata import db as _gdb
        rows = _gdb.table("resistances")
        if not rows:
            return
        for r in rows:
            key = str(r.get("key", ""))
            if not key:
                continue
            vals = {}
            for c in CHANNELS:
                try:
                    vals[c] = float(r.get(c, 0.0) or 0.0)
                except (TypeError, ValueError):
                    vals[c] = 0.0
            extra = r.get("extra")
            if extra:
                try:
                    import json
                    _e = json.loads(extra) if isinstance(extra, str) else extra
                    if isinstance(_e, dict):
                        for c in CHANNELS:
                            if c in _e:
                                vals[c] = float(_e[c])
                except Exception:
                    pass
            _PROFILE_CACHE[key] = ResistanceSet(vals)
    except Exception:
        pass


def reload_profiles():
    """策划在编辑模式改完库后可调，清缓存重新读"""
    global _DB_LOADED
    _PROFILE_CACHE.clear()
    _DB_LOADED = False
    _load_db_profiles()


# ---------------------------------------------------------------- 数据结构
class ResistanceSet:
    """一组抗性。取值 -1.0(双倍受伤) ~ 1.0(完全免疫)。"""

    __slots__ = ("_v",)

    def __init__(self, values: Optional[Dict[str, float]] = None):
        self._v = {c: 0.0 for c in CHANNELS}
        if values:
            for c, v in values.items():
                if c in self._v:
                    try:
                        self._v[c] = max(-1.0, min(1.0, float(v)))
                    except (TypeError, ValueError):
                        pass

    def get(self, channel: str) -> float:
        return self._v.get(channel, 0.0)

    def set(self, channel: str, value: float):
        if channel in self._v:
            self._v[channel] = max(-1.0, min(1.0, float(value)))

    def add(self, channel: str, delta: float):
        self.set(channel, self.get(channel) + delta)

    def as_dict(self) -> Dict[str, float]:
        return dict(self._v)

    def multiplier(self, channel: str) -> float:
        """抗性 → 实际伤害倍率。真实伤害永远不吃抗性。"""
        if channel == "true":
            return 1.0
        return max(0.0, 1.0 - self._v.get(channel, 0.0))


def get_resistance_set(profile: str) -> ResistanceSet:
    if not _DB_LOADED:
        _load_db_profiles()
    hit = _PROFILE_CACHE.get(profile)
    if hit is not None:
        return hit
    base = DEFAULT_PROFILES.get(profile, DEFAULT_PROFILES["ZOMBIE"])
    rs = ResistanceSet(base)
    _PROFILE_CACHE[profile] = rs
    return rs


def attach_resistances(target, profile: str = ""):
    """给实体挂上抗性集（构造时调用一次）。返回 ResistanceSet"""
    rs = get_resistance_set(profile or getattr(target, "resistance_profile", "ZOMBIE"))
    # 每个实体拿**副本**，改某个实体的抗性不会污染同 profile 的其他实体
    own = ResistanceSet(rs.as_dict())
    target.resistances = own
    target.resistance_profile = profile or getattr(target, "resistance_profile", "ZOMBIE")
    return own


@dataclass
class DamagePacket:
    """一次伤害的描述。base=基础伤害，mult=伤害倍率（技能/暴击/符文等）。"""
    base: float = 0.0
    mult: float = 1.0
    damage_type: str = "physical"
    channel: str = ""            # 为空则按 damage_type 推断
    source: str = "zombie"       # zombie / player / world
    attacker: object = None
    tags: tuple = ()             # "crit" / "skill" / "dot" / "melee" ...
    attack_x: Optional[float] = None
    attack_y: Optional[float] = None

    @property
    def raw(self) -> float:
        return max(0.0, float(self.base) * float(self.mult))

    def resolve_channel(self) -> str:
        return self.channel or TYPE_TO_CHANNEL.get(
            str(self.damage_type).lower(), "physical")


@dataclass
class DamageResult:
    raw: float = 0.0
    final: float = 0.0
    channel: str = "physical"
    resistance: float = 0.0
    absorbed: float = 0.0
    vulnerability: float = 0.0
    tags: tuple = ()

    @property
    def resisted(self) -> bool:
        return self.absorbed > 0.01

    @property
    def immune(self) -> bool:
        return self.raw > 0 and self.final <= 0.001


def coerce_packet(damage, damage_type="physical", mult=1.0, **kw) -> DamagePacket:
    """把旧式 `take_damage(30, "fire")` 与新式 DamagePacket 统一成 packet"""
    if isinstance(damage, DamagePacket):
        if damage_type and damage_type != "physical" and not damage.channel:
            damage.damage_type = damage_type
        return damage
    try:
        base = float(damage)
    except (TypeError, ValueError):
        base = 0.0
    return DamagePacket(base=base, mult=float(mult), damage_type=damage_type, **kw)


def resolve_damage(packet: DamagePacket, target) -> DamageResult:
    """唯一的伤害计算入口。

    顺序：raw = base × mult → 状态易伤 → 抗性 → 下限为 0。
    护甲 / buff 受伤倍率 / 防爆套装仍在各自 take_damage 里继续处理，
    避免重复计算（那些是"机制减免"，这里是"属性抗性"）。
    """
    ch = packet.resolve_channel()
    raw = packet.raw
    rs = getattr(target, "resistances", None)
    if rs is None:
        rs = attach_resistances(
            target, getattr(target, "resistance_profile", "ZOMBIE"))
    res = rs.get(ch) if ch != "true" else 0.0
    # 状态易伤：燃烧加深、中毒破防等，由 EntityStatus 提供
    vuln = 0.0
    st = getattr(target, "status", None)
    if st is not None and hasattr(st, "vulnerability"):
        try:
            vuln = float(st.vulnerability(ch) or 0.0)
        except Exception:
            vuln = 0.0
    mult = rs.multiplier(ch) * (1.0 + max(0.0, vuln))
    final = max(0.0, raw * mult)
    return DamageResult(raw=raw, final=final, channel=ch, resistance=res,
                        absorbed=max(0.0, raw - raw * rs.multiplier(ch)),
                        vulnerability=vuln, tags=packet.tags)


def channel_of(damage_type: str) -> str:
    return TYPE_TO_CHANNEL.get(str(damage_type).lower(), "physical")


def describe(result: DamageResult) -> str:
    if result.immune:
        return "免疫"
    if result.resisted:
        return f"-{int(result.resistance * 100)}%"
    if result.vulnerability > 0:
        return f"易伤+{int(result.vulnerability * 100)}%"
    return ""


__all__ = [
    "CHANNELS", "TYPE_TO_CHANNEL", "DEFAULT_PROFILES", "profile_for",
    "ResistanceSet", "get_resistance_set", "attach_resistances",
    "reload_profiles", "DamagePacket", "DamageResult", "coerce_packet",
    "resolve_damage", "channel_of", "describe",
]
