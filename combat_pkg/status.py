# -*- coding: utf-8 -*-
"""实体状态数据管理（v2.9.12 / v2.9.20 / v2.9.22）

统一维护 流血 / 燃烧 / 冰冻 / 中毒 / 眩晕 / 感电 等状态的
层数、剩余时间、每跳伤害与易伤，供：
- 伤害计算（damage.py 读 `vulnerability()`）
- 渲染层（HUD 图标、实体光环、粒子颜色）
- 死亡详情 / 回放（状态快照）

不推翻原有 BuffManager：apply 时可选桥接进去，保证冻结移速、燃烧加深
等旧机制继续生效，本项目只是把它变成**结构化数据**并补齐渲染。

v2.9.22 **免疫机制重做**（按需求重新定义）：
  1. 每次吃到 debuff → 叠加层数；
  2. 层数到达该状态上限后，后续施加改为「覆盖」：刷新持续时间/强度，
     **不清除已有 debuff**、不重置层数；
  3. 满层后反复覆盖达到 `IMMUNITY_THRESHOLD` 次 → 获得 `immune_<kind>`
     buff，一段时间内不再接受该 debuff 的新覆盖（免疫窗口）；
  4. 免疫**不清除当前已有的 debuff**，它按自己的剩余时间自然走完；
  5. 免疫结束（或 debuff 自然结束）后计数归零，可以重新被施加。

旧版是「累计 3 次施加直接给 6s 免疫并拒绝刷新」，在冰冻区域里每帧 apply
会瞬间吃满阈值 → 冻一下马上解冻、之后很久不再冻。现在覆盖按真实时间
节流推进，区域内能稳定冻结一段时间才进入免疫。
"""
from typing import Dict, List, Optional

KINDS = ("bleed", "burn", "freeze", "poison", "stun", "shock")
DEBUFF_KINDS = ("bleed", "burn", "freeze", "poison", "stun", "shock")
IMMUNITY_THRESHOLD = 3       # 满层后的**覆盖次数**上限（达到即进入免疫）
IMMUNITY_DURATION = 6.0      # 免疫持续 6 秒
IMMUNE_PREFIX = "immune_"

# 默认状态定义（也是 status_defs 表的播种数据；数据库权威）
STATUS_DEFS: Dict[str, dict] = {
    "bleed":  {"name": "流血", "color": (200, 40, 55), "icon": "血",
               "dps": 6.0, "duration": 5.0, "max_stacks": 3,
               "vulnerability": {"physical": 0.10}, "fx": "drip"},
    "burn":   {"name": "燃烧", "color": (255, 130, 30), "icon": "燃",
               "dps": 9.0, "duration": 4.0, "max_stacks": 3,
               "vulnerability": {"fire": 0.20, "physical": 0.08}, "fx": "flame"},
    "freeze": {"name": "冰冻", "color": (110, 200, 255), "icon": "冰",
               "dps": 0.0, "duration": 3.0, "max_stacks": 1,
               "vulnerability": {"ice": 0.15}, "fx": "crystal"},
    "poison": {"name": "中毒", "color": (120, 220, 80), "icon": "毒",
               "dps": 5.0, "duration": 6.0, "max_stacks": 5,
               "vulnerability": {"poison": 0.12}, "fx": "bubble"},
    "stun":   {"name": "眩晕", "color": (255, 225, 90), "icon": "晕",
               "dps": 0.0, "duration": 1.0, "max_stacks": 1,
               "vulnerability": {}, "fx": "stars"},
    "shock":  {"name": "感电", "color": (160, 190, 255), "icon": "电",
               "dps": 4.0, "duration": 2.5, "max_stacks": 2,
               "vulnerability": {"lightning": 0.15}, "fx": "spark"},
    # 免疫 buff：无 DOT、无易伤，纯粹是一个可见的增益状态
    "immune": {"name": "免疫", "color": (185, 150, 255), "icon": "免",
               "dps": 0.0, "duration": IMMUNITY_DURATION, "max_stacks": 1,
               "vulnerability": {}, "fx": "shield"},
}

# 状态 → damage.py 的通道（DOT 走什么抗性）
KIND_CHANNEL = {
    "bleed": "physical", "burn": "fire", "freeze": "ice",
    "poison": "poison", "stun": "true", "shock": "lightning",
}

# 状态 → 旧 BuffType 名（桥接用，取不到就跳过）
KIND_BUFF = {
    "bleed": "BLEED", "burn": "BURN", "freeze": "FREEZE",
    "poison": "POISON", "stun": "STUN",
}


class StatusState:
    __slots__ = ("kind", "stacks", "time", "tick", "intensity")

    def __init__(self, kind, stacks=1, time=0.0, intensity=1.0):
        self.kind = kind
        self.stacks = max(1, int(stacks))
        self.time = max(0.0, float(time))
        self.tick = 0.0
        self.intensity = float(intensity)

    @property
    def progress(self) -> float:
        d = STATUS_DEFS.get(self.kind, {}).get("duration", 1.0)
        return max(0.0, min(1.0, self.time / d)) if d > 0 else 0.0


class EntityStatus:
    """挂在 player / enemy 上的 `status` 组件。"""

    def __init__(self, owner=None, defs: Optional[Dict[str, dict]] = None):
        self.owner = owner
        self.defs = defs or STATUS_DEFS
        self.states: Dict[str, StatusState] = {}
        self._flash = 0.0                    # 新状态命中的闪光，渲染层读
        self.debuff_hits: Dict[str, int] = {}   # 满层后的「覆盖」次数
        self.immunities: Dict[str, float] = {}  # 免疫剩余秒数
        self.last_immune_kind: Optional[str] = None

    # ------------------------------------------------------------ 写入
    def apply(self, kind: str, stacks: int = 1, duration: Optional[float] = None,
              intensity: float = 1.0, bridge: bool = True, count_hit: bool = True):
        """施加 / 叠层 / 覆盖一个状态。

        返回现有或新建的 StatusState；免疫窗口内返回**当前已有的那个 debuff**
        （不刷新、不清除），若当前没有则返回 None。
        `count_hit=False` 用于「纯维持」类的调用，不计入覆盖次数。
        """
        kind = str(kind).lower()
        d = self.defs.get(kind)
        if not d:
            return None
        # 免疫窗口：不再叠加、不再覆盖，但**保留现有 debuff**让它自然走完
        if kind in DEBUFF_KINDS and self.is_immune(kind):
            self.last_immune_kind = kind
            return self.states.get(kind)

        dur = float(duration if duration is not None else d.get("duration", 3.0))
        cap = int(d.get("max_stacks", 3))
        st = self.states.get(kind)
        covered = False
        if st is None:
            # 首次施加：stacks 参数直接就是层数（而非"再叠加 stacks 次"）
            st = StatusState(kind, stacks=max(1, int(stacks)),
                             time=dur, intensity=intensity)
            self.states[kind] = st
        elif st.stacks < cap:
            # 未达上限：叠层（同时把持续时间补到本次的时长）
            st.stacks = min(cap, st.stacks + max(1, int(stacks)))
            st.time = max(st.time, dur)
            st.intensity = max(st.intensity, float(intensity))
        else:
            # 已达上限：**覆盖**——刷新持续时间与强度，不清除、不重置层数
            st.time = max(st.time, dur)
            st.intensity = max(st.intensity, float(intensity))
            covered = True

        self._flash = 0.25
        if kind in DEBUFF_KINDS and covered and count_hit:
            self._register_debuff_hit(kind)
        if bridge:
            self._bridge(kind, st.time)
        return st

    # ------------------------------------------------------------ 免疫
    def is_immune(self, kind: str) -> bool:
        return float(self.immunities.get(str(kind).lower(), 0.0) or 0.0) > 0.0

    def immune_remaining(self, kind: str) -> float:
        return float(self.immunities.get(str(kind).lower(), 0.0) or 0.0)

    def refresh_count(self, kind: str) -> int:
        """该 debuff 满层后已发生的覆盖次数（调试 / 测试用）。"""
        return int(self.debuff_hits.get(str(kind).lower(), 0) or 0)

    def immune_buffs(self) -> List[StatusState]:
        """免疫本身作为 buff 暴露给 HUD / 渲染 / 快照。"""
        return [st for k, st in self.states.items()
                if k.startswith(IMMUNE_PREFIX) and st.time > 0]

    def _register_debuff_hit(self, kind: str):
        n = int(self.debuff_hits.get(kind, 0) or 0) + 1
        if n >= IMMUNITY_THRESHOLD:
            self.debuff_hits[kind] = 0
            self.immunities[kind] = IMMUNITY_DURATION
            bk = IMMUNE_PREFIX + kind
            # 只挂免疫 buff，**绝不动 self.states[kind]**：
            # 现有的 debuff 保留并按剩余时间自然结束。
            self.states[bk] = StatusState(bk, stacks=1, time=IMMUNITY_DURATION)
            self.last_immune_kind = kind
            self._flash = 0.4
        else:
            self.debuff_hits[kind] = n

    def clear(self, kind: str = None):
        if kind is None:
            self.states.clear()
            self.debuff_hits.clear()
            self.immunities.clear()
        else:
            k = str(kind).lower()
            self.states.pop(k, None)
            self.states.pop(IMMUNE_PREFIX + k, None)
            self.debuff_hits.pop(k, None)
            self.immunities.pop(k, None)

    # ------------------------------------------------------------ 查询
    def has(self, kind: str) -> bool:
        return str(kind).lower() in self.states

    def get(self, kind: str) -> Optional[StatusState]:
        return self.states.get(str(kind).lower())

    def active_states(self) -> List[StatusState]:
        return [s for s in self.states.values() if s.time > 0]

    def vulnerability(self, channel: str) -> float:
        """该通道的额外易伤（燃烧提高火伤、流血提高物伤…）"""
        total = 0.0
        for s in self.states.values():
            if s.time <= 0:
                continue
            d = self.defs.get(s.kind, {})
            v = (d.get("vulnerability") or {}).get(channel, 0.0)
            if v:
                total += float(v) * s.stacks * s.intensity
        return min(1.5, total)

    def movement_mult(self) -> float:
        """冰冻/眩晕对移速的影响（渲染与逻辑都可读）"""
        m = 1.0
        if self.has("freeze"):
            m *= 0.25
        if self.has("stun"):
            m *= 0.0
        return m

    # ------------------------------------------------------------ 每帧
    def update(self, dt: float):
        """推进计时，返回本帧应结算的 DOT 列表 [(amount, damage_type), ...]"""
        out = []
        self._flash = max(0.0, self._flash - dt)
        # 免疫窗口倒计时；结束后删免疫 buff 并清零覆盖计数，
        # 但不碰原本的 debuff（它若还在就继续走完）。
        for k in list(self.immunities.keys()):
            t = float(self.immunities[k] or 0.0) - dt
            if t <= 0:
                self.immunities.pop(k, None)
                self.states.pop(IMMUNE_PREFIX + k, None)
                self.debuff_hits[k] = 0
            else:
                self.immunities[k] = t
                bk = IMMUNE_PREFIX + k
                if bk in self.states:
                    self.states[bk].time = t
        for kind, st in list(self.states.items()):
            if st.time <= 0:
                del self.states[kind]
                continue
            st.time -= dt
            d = self.defs.get(kind, {})
            dps = float(d.get("dps", 0.0) or 0.0)
            if dps > 0:
                st.tick += dt
                # 每 0.5s 一跳，层数线性叠加
                while st.tick >= 0.5:
                    st.tick -= 0.5
                    out.append((dps * 0.5 * st.stacks * st.intensity,
                                KIND_CHANNEL.get(kind, "physical")))
            if st.time <= 0:
                del self.states[kind]
                # debuff 自然结束时清零覆盖计数，下次从「首次施加」重新计
                if kind in DEBUFF_KINDS:
                    self.debuff_hits[kind] = 0
        return out

    def flash(self) -> float:
        return self._flash

    # ------------------------------------------------------------ 桥接旧系统
    def _bridge(self, kind: str, duration: float):
        try:
            buff_name = KIND_BUFF.get(kind)
            if not buff_name or self.owner is None:
                return
            bm = getattr(self.owner, "buff_manager", None)
            if bm is None:
                return
            from buff import BuffType
            bt = getattr(BuffType, buff_name, None)
            if bt is None:
                return
            if hasattr(bm, "add_buff"):
                bm.add_buff(bt, duration=duration)
        except Exception:
            pass

    # ------------------------------------------------------------ 快照
    def snapshot(self) -> dict:
        d = {k: {"stacks": s.stacks, "time": round(s.time, 2),
                 "intensity": s.intensity,
                 "immune": k.startswith(IMMUNE_PREFIX)}
             for k, s in self.states.items() if s.time > 0}
        d["_immunities"] = {k: round(v, 2)
                            for k, v in self.immunities.items() if v > 0}
        d["_refresh_counts"] = {k: int(v) for k, v in self.debuff_hits.items()}
        return d


def attach_status(owner, defs=None) -> EntityStatus:
    st = EntityStatus(owner, defs)
    owner.status = st
    return st


def status_meta(kind: str) -> dict:
    k = str(kind).lower()
    if k.startswith(IMMUNE_PREFIX):
        raw = k[len(IMMUNE_PREFIX):]
        base = dict(STATUS_DEFS.get("immune", {}))
        base["name"] = "免疫·" + str(STATUS_DEFS.get(raw, {}).get("name", raw))
        return base
    return STATUS_DEFS.get(k, {"name": k, "color": (200, 200, 200),
                               "icon": "?", "fx": "none"})


__all__ = ["KINDS", "STATUS_DEFS", "KIND_CHANNEL", "EntityStatus",
           "DEBUFF_KINDS", "IMMUNITY_THRESHOLD", "IMMUNITY_DURATION",
           "IMMUNE_PREFIX", "StatusState", "attach_status", "status_meta"]
