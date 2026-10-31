# -*- coding: utf-8 -*-
"""v2.8.8 数据模型层（OOP）—— 取代散落各处的硬编码字典

设计原则
--------
1. **数据库权威**：所有数值以 SQLite 为准，代码里的字典只是"缺行时的补种源"
2. **一个类一个概念**：WeaponData / EnemyData / RuneData / BuffData / SkillData /
   CharacterData / MapData，各自带校验、派生属性与格式化方法
3. **类型安全**：构造时统一走 `coerce_like`，杜绝 "str vs int" 之类的比较崩溃
4. **注册表**：同一概念的全部实例集中管理，支持按 key 取、按条件筛选、批量迭代

用法：
    from gamedata.models import Weapons
    w = Weapons.get("AWP")
    print(w.damage, w.dps, w.describe())
"""

from .db import coerce_like

try:
    from config import CHARACTERS
except Exception:                                    # pragma: no cover
    CHARACTERS = {}


# ======================================================================
# 基类
# ======================================================================
class GameData:
    """所有数据模型的基类

    子类只需声明 `FIELDS = [(字段名, 默认值), ...]` 与 `TABLE`（可选）。
    """

    TABLE = None
    FIELDS = []

    def __init__(self, key, **kwargs):
        #: 唯一标识（与数据库 key 列一致）
        self.key = str(key)
        for _f, _default in self.FIELDS:
            _v = kwargs.get(_f, _default)
            # 以**代码声明的默认值类型**为准做转换，杜绝类型不一致
            setattr(self, _f, coerce_like(_v, _default))

    # ---------------- 序列化 ----------------
    def to_dict(self):
        _out = {"key": self.key}
        for _f, _ in self.FIELDS:
            _out[_f] = getattr(self, _f, None)
        return _out

    @classmethod
    def from_row(cls, row):
        """从数据库行（dict 或 sqlite3.Row）构造"""
        if row is None:
            return None
        try:
            _d = dict(row)
        except Exception:
            _d = dict(row) if hasattr(row, "keys") else {}
        _key = _d.pop("key", None)
        if _key is None:
            return None
        return cls(_key, **_d)

    def __repr__(self):
        return f"<{type(self).__name__} {self.key}>"


class Registry:
    """同类数据对象的注册表：集中存取、批量迭代"""

    MODEL = GameData
    TABLE = None

    def __init__(self):
        self._items = {}

    # ---------------- 存取 ----------------
    def add(self, obj):
        if obj is None:
            return None
        self._items[obj.key] = obj
        return obj

    def add_many(self, objs):
        return [self.add(_o) for _o in objs or []]

    def get(self, key, default=None):
        return self._items.get(str(key), default)

    def all(self):
        return list(self._items.values())

    def keys(self):
        return list(self._items.keys())

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items.values())

    def __contains__(self, key):
        return str(key) in self._items

    # ---------------- 查询 ----------------
    def filter(self, **cond):
        """按字段筛选（相等匹配）"""
        _out = []
        for _o in self._items.values():
            _ok = True
            for _k, _v in cond.items():
                if getattr(_o, _k, None) != _v:
                    _ok = False
                    break
            if _ok:
                _out.append(_o)
        return _out

    def sorted_by(self, field, reverse=False):
        try:
            return sorted(self._items.values(),
                          key=lambda o: getattr(o, field, 0),
                          reverse=reverse)
        except Exception:
            return self.all()

    # ---------------- 从数据库装载 ----------------
    def load(self, conn):
        """从 SQLite 装载本表（数据库权威）"""
        if not self.TABLE:
            return self
        try:
            _c = conn.cursor()
            _c.row_factory = None
            _rows = _c.execute(f"SELECT * FROM {self.TABLE}").fetchall()
            _cols = [_r[1] for _r in
                     _c.execute(f"PRAGMA table_info({self.TABLE})").fetchall()]
            for _r in _rows:
                _d = dict(zip(_cols, _r))
                self.add(self.MODEL.from_row(_d))
        except Exception:
            pass
        return self


# ======================================================================
# 武器
# ======================================================================
class WeaponData(GameData):
    TABLE = "weapons"
    FIELDS = [
        ("name", "未命名"),
        ("damage", 0.0),
        ("damage_vs_player", 0.0),
        ("damage_per_frame", False),
        ("fire_rate", 1.0),
        ("range", 0.0),
        ("speed", 0.0),
        ("spread", 0.0),
        ("pierce", 1),
        ("ammo", "∞"),
        ("reload", 0.0),
        ("pellets", 1),
        ("color", (255, 255, 255)),
        ("projectile_size", 3),
        ("shake", 0),
        ("desc", ""),
        ("hold_charge", False),
        ("charge_full_time", 1.2),
        ("charge_spread_max", 0.06),
        ("charge_spread_min", 0.0),
        ("charge_zoom_min", 0.62),
        ("story", ""),
    ]

    @property
    def dps(self):
        """每秒伤害（弹丸类按 射速倒数 × 伤害 × 弹丸数 估算）"""
        try:
            _fr = float(self.fire_rate) or 1.0
            return round(float(self.damage) * float(self.pellets or 1) / _fr, 1)
        except Exception:
            return 0.0

    @property
    def damage_to_player(self):
        """对玩家伤害（未单独配置时与对僵尸一致）"""
        try:
            _v = float(self.damage_vs_player or 0)
            return _v if _v > 0 else float(self.damage)
        except Exception:
            return float(self.damage)

    @property
    def is_sniper(self):
        """是否为蓄力预瞄类武器"""
        return bool(self.hold_charge)

    def describe(self):
        _kind = "蓄力预瞄" if self.is_sniper else "常规"
        _extra = ""
        if self.damage_per_frame:
            _extra = "（帧伤武器）"
        return (f"{self.name}｜{_kind}{_extra}｜伤害 {self.damage:g}"
                f"｜对玩家 {self.damage_to_player:g}｜射速 {self.fire_rate:g}"
                f"｜射程 {self.range:g}｜DPS≈{self.dps}")


class Weapons(Registry):
    MODEL = WeaponData
    TABLE = "weapons"


# ======================================================================
# 敌人
# ======================================================================
class EnemyData(GameData):
    TABLE = "enemies"
    FIELDS = [
        ("name", "未命名"),
        ("hp", 100.0),
        ("speed", 60.0),
        ("damage", 10.0),
        ("attack_range", 40.0),
        ("attack_cooldown", 1.0),
        ("exp", 5.0),
        ("coins", 1.0),
        ("color", (255, 255, 255)),
        ("size", 20.0),
        ("is_boss", False),
        ("can_be_grappled", True),
        ("desc", ""),
        ("story", ""),
    ]

    @property
    def boss(self):
        """Boss 判定：优先用 is_boss 字段，缺失时按 key/名称推断

        数据库 enemies 表当前没有 is_boss 列，所以以 key 前缀 BOSS_ 为准。
        """
        # 先看 key（数据库暂无 is_boss 列时唯一可靠依据），再看字段
        if str(self.key).upper().startswith("BOSS_"):
            return True
        try:
            return bool(getattr(self, "is_boss", False))
        except Exception:
            return False

    def describe(self):
        _tag = "BOSS" if self.boss else "普通"
        return (f"{self.name}｜{_tag}｜HP {self.hp:g}｜速度 {self.speed:g}"
                f"｜伤害 {self.damage:g}｜经验 {self.exp:g}")


class Enemies(Registry):
    MODEL = EnemyData
    TABLE = "enemies"

    def bosses(self):
        return [e for e in self.all() if e.boss]


# ======================================================================
# 符文 / Buff / 技能 / 角色 / 地图
# ======================================================================
class RuneData(GameData):
    TABLE = "runes"
    FIELDS = [("name", "未命名"), ("desc", ""), ("buff_type", ""),
              ("value", 0.0), ("color", (255, 255, 255)), ("story", "")]

    def describe(self):
        return f"{self.name}｜{self.buff_type} +{self.value:g}｜{self.desc}"


class Runes(Registry):
    MODEL = RuneData
    TABLE = "runes"


class BuffData(GameData):
    TABLE = "buffs"
    FIELDS = [("name", "未命名"), ("desc", ""), ("duration", 5.0),
              ("stackable", True), ("is_debuff", False),
              ("color", (255, 255, 255)), ("value", 0.0)]

    @property
    def debuff(self):
        return bool(self.is_debuff)

    def describe(self):
        _t = "负面" if self.debuff else "正面"
        return f"{self.name}｜{_t}｜持续 {self.duration:g}s｜{self.desc}"


class Buffs(Registry):
    MODEL = BuffData
    TABLE = "buffs"

    def debuffs(self):
        return [b for b in self.all() if b.debuff]


class SkillData(GameData):
    TABLE = "skills"
    FIELDS = [("name", "未命名"), ("desc", ""), ("max_level", 5),
              ("is_active", False), ("cooldown", 5.0),
              ("unlock_after", ""), ("color", (255, 255, 255)),
              ("level_descriptions", {})]

    @property
    def active(self):
        """主动技能判定：优先 is_active 字段，缺失时按 effect_key 推断"""
        # 数据库暂无 is_active 列 → 以 effect_key 是否存在来区分主动/被动
        _ek = str(getattr(self, "effect_key", "") or "")
        if _ek:
            return True
        try:
            return bool(getattr(self, "is_active", False))
        except Exception:
            return False

    def level_desc(self, level):
        try:
            _d = self.level_descriptions or {}
            return _d.get(int(level), _d.get(str(level), self.desc))
        except Exception:
            return self.desc

    def describe(self):
        _t = "主动" if self.active else "被动"
        return f"{self.name}｜{_t}｜最高 {self.max_level} 级｜CD {self.cooldown:g}s"


class Skills(Registry):
    MODEL = SkillData
    TABLE = "skills"

    def actives(self):
        return [s for s in self.all() if s.active]


class CharacterData(GameData):
    """局外角色：词条全部以数据驱动（不再是散落的 if/elif）"""

    FIELDS = [("name", "未命名"), ("price", 0), ("desc", ""),
              ("hp_bonus", 0), ("speed_bonus", 0.0), ("damage_bonus", 0.0),
              ("crit_bonus", 0.0), ("dmg_reduce", 0.0), ("regen", 0.0),
              ("ability", ""), ("requires_scythe", False), ("story", "")]

    def perks(self):
        """角色词条列表（供角色选择页展示）"""
        _out = []
        if self.hp_bonus:
            _out.append({"name": "生命强化", "desc": f"生命上限 +{self.hp_bonus:g}"})
        if self.speed_bonus:
            _out.append({"name": "疾行", "desc": f"移速 +{self.speed_bonus:g}"})
        if self.damage_bonus:
            _out.append({"name": "火力", "desc": f"伤害 +{float(self.damage_bonus) * 100:g}%"})
        if self.crit_bonus:
            _out.append({"name": "精准", "desc": f"暴击 +{float(self.crit_bonus) * 100:g}%"})
        if self.dmg_reduce:
            _out.append({"name": "减伤", "desc": f"受到伤害 -{float(self.dmg_reduce) * 100:g}%"})
        if self.regen:
            _out.append({"name": "再生", "desc": f"每 2 秒回复 {float(self.regen) * 2:g} 点生命"})
        return _out

    def apply_to(self, player, level=1):
        """把角色加成**应用**到玩家实例（替代原先散落的 if/elif）

        此前角色效果分散在多处、且 P2/P3/P4 有漏实现，
        现在统一由数据驱动，任何玩家对象都能吃到完整效果。
        """
        _s = 1.0 + (max(1, int(level)) - 1) * 0.2
        try:
            _hb = int(float(self.hp_bonus) * _s)
            if _hb:
                player.max_hp += _hb
                player.hp = min(getattr(player, "hp", 0) + _hb, player.max_hp)
            player.base_speed += float(self.speed_bonus) * _s
            player.speed = player.base_speed
            player.damage_multiplier *= (1 + float(self.damage_bonus))
            _cb = float(self.crit_bonus)
            player.crit_bonus_add = getattr(player, "crit_bonus_add", 0.0) + _cb
            player.crit_chance = getattr(player, "crit_chance", 0.0) + _cb
            player.health_regen = getattr(player, "health_regen", 0.0) + float(self.regen) * _s
            player.dmg_reduce = getattr(player, "dmg_reduce", 0.0) + float(self.dmg_reduce)
            player._character_applied = self.key
        except Exception:
            pass
        return player

    def describe(self):
        return f"{self.name}｜{self.price:g} 金币｜{self.ability or self.desc}"


class DifficultyData(GameData):
    """难度配置（把散落的难度字典收敛为类）"""

    FIELDS = [("name", "未命名"), ("enemy_hp_mult", 1.0),
              ("enemy_damage_mult", 1.0), ("player_hp_mult", 1.0),
              ("spawn_rate_mult", 1.0), ("coin_mult", 1.0),
              ("achievement_coef", 1.0), ("desc", "")]

    def describe(self):
        return (f"{self.name}｜敌人 HP ×{self.enemy_hp_mult:g}"
                f"｜敌人伤害 ×{self.enemy_damage_mult:g}"
                f"｜玩家 HP ×{self.player_hp_mult:g}")


class Difficulties(Registry):
    MODEL = DifficultyData

    def load_builtin(self):
        """从 config.DIFFICULTY_CONFIGS 装载（未入库时的数据源）"""
        try:
            from config import DIFFICULTY_CONFIGS as _DC
        except Exception:
            _DC = None
        for _k, _v in (_DC or {}).items():
            _d = dict(_v) if isinstance(_v, dict) else {}
            _d.setdefault("name", str(_k))
            self.add(DifficultyData(_k, **_d))
        return self


class Characters(Registry):
    MODEL = CharacterData

    def load_builtin(self):
        """从 config.CHARACTERS 装载（角色表暂未入库时的数据源）"""
        for _k, _v in (CHARACTERS or {}).items():
            _d = dict(_v)
            _d.setdefault("name", _k)
            self.add(CharacterData(_k, **_d))
        return self


class MapData(GameData):
    FIELDS = [("name", "未命名"), ("chapter", ""), ("description", ""),
              ("difficulty_scale", 1.0), ("recommend", 1),
              ("features", []), ("story", "")]

    def describe(self):
        return (f"{self.name}｜{self.chapter or '—'}｜难度系数 "
                f"{self.difficulty_scale:g}｜推荐等级 {self.recommend}")


class Maps(Registry):
    MODEL = MapData

    def load_builtin(self):
        """从 config.MAP_CONFIGS 装载（地图表暂未入库时的数据源）"""
        try:
            from config import MAP_CONFIGS as _MC
        except Exception:
            _MC = None
        try:
            from config import MapType as _MT
        except Exception:
            _MT = None
        _src = _MC or {}
        for _k, _v in _src.items():
            _key = getattr(_k, "name", str(_k)) if _MT else str(_k)
            _d = dict(_v) if isinstance(_v, dict) else {}
            _d.setdefault("name", _d.get("name", _key))
            self.add(MapData(_key, **_d))
        return self


# ======================================================================
# 统一入口
# ======================================================================
class GameDataHub:
    """全部数据的集中入口 —— 一次装载，处处可用"""

    def __init__(self, conn=None):
        self.weapons = Weapons()
        self.enemies = Enemies()
        self.runes = Runes()
        self.buffs = Buffs()
        self.skills = Skills()
        self.characters = Characters()
        self.maps = Maps()
        self.difficulties = Difficulties()
        if conn is not None:
            self.load(conn)

    def load(self, conn):
        """从数据库装载全部表（数据库权威）"""
        for _r in (self.weapons, self.enemies, self.runes,
                   self.buffs, self.skills):
            try:
                _r.load(conn)
            except Exception:
                pass
        # 角色/地图/难度暂以代码为数据源（后续可入库）
        self.characters.load_builtin()
        self.maps.load_builtin()
        self.difficulties.load_builtin()
        return self
