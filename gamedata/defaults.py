# -*- coding: utf-8 -*-
"""代码内置默认值（数据库缺失/损坏时的兜底，也是首次建库的种子来源）

这些数值**同步自现有代码**，因此即使数据库整个丢掉，游戏行为也完全一致。
策划改数据库后以数据库为准；数据库缺行时仍以此处为准。
"""

# ---------------- 全局调参（tuning）----------------
TUNING_DEFAULTS = {
    "player_base_hp":       (100.0, "玩家基础最大生命"),
    "player_base_speed":    (3.2, "玩家基础移动速度"),
    "player_base_damage":   (1.0, "玩家基础伤害倍率"),
    "player_crit_chance":   (0.05, "玩家基础暴击率"),
    "player_crit_mult":     (2.0, "玩家基础暴击倍率"),
    "player_pickup_radius": (60.0, "经验球拾取半径"),
    "horde_base_interval":  (45.0, "尸潮基础间隔（秒）"),
    "horde_min_interval":   (18.0, "尸潮最小间隔（秒）"),
    "horde_size_base":      (12.0, "尸潮基础规模"),
    "horde_size_per_wave":  (2.5, "每波尸潮规模增量"),
    "exp_base":             (10.0, "击杀基础经验"),
    "exp_per_wave":         (1.5, "每波经验增量"),
    "drop_rate_base":       (0.12, "基础掉落率"),
    "boss_hp_mult":         (12.0, "Boss 血量倍率"),
    "boss_damage_mult":     (2.0, "Boss 伤害倍率"),
    "revive_hp_ratio":      (0.5, "救援复活后血量比例"),
    "downed_death_time":    (20.0, "倒地未获救的死亡时限（秒）"),
    "rescue_cooldown":      (15.0, "再次可被救援的冷却（秒）"),
}

# ---------------- 难度（difficulty）----------------
DIFFICULTY_DEFAULTS = {
    "简单": dict(enemy_hp_mult=0.7, enemy_damage_mult=0.7, enemy_speed_mult=0.9,
                 enemy_spawn_mult=0.7, player_hp_mult=1.3, player_damage_mult=1.2,
                 drop_rate_mult=1.5, exp_mult=1.3, start_weapons=1,
                 description="敌人较弱，资源丰富，适合新手"),
    "普通": dict(enemy_hp_mult=1.0, enemy_damage_mult=1.0, enemy_speed_mult=1.0,
                 enemy_spawn_mult=1.0, player_hp_mult=1.0, player_damage_mult=1.0,
                 drop_rate_mult=1.0, exp_mult=1.0, start_weapons=1,
                 description="标准体验，平衡的挑战"),
    "困难": dict(enemy_hp_mult=1.5, enemy_damage_mult=1.4, enemy_speed_mult=1.1,
                 enemy_spawn_mult=1.3, player_hp_mult=0.9, player_damage_mult=0.95,
                 drop_rate_mult=0.8, exp_mult=1.2, start_weapons=1,
                 description="敌人更强，资源稀缺，考验技巧"),
    "地狱": dict(enemy_hp_mult=2.2, enemy_damage_mult=1.8, enemy_speed_mult=1.2,
                 enemy_spawn_mult=1.6, player_hp_mult=0.75, player_damage_mult=0.9,
                 drop_rate_mult=0.6, exp_mult=1.5, start_weapons=1,
                 description="极致挑战，敌人凶猛，步步惊心"),
}


# ======================================================================
# 从现有代码里抽取数值（保证种子与当前行为一致）
# ======================================================================
def _extract_dict_from_source(path, func_name=None, var_name="configs"):
    """用 AST 从源文件里抽取一个大字典字面量，并解析其中的枚举/颜色常量。

    返回 {key字符串: 原始值dict}，解析失败返回 {}
    """
    import ast
    try:
        with open(path, "r", encoding="utf-8") as _f:
            _src = _f.read()
        _tree = ast.parse(_src)
    except Exception:
        return {}

    _ns = _build_namespace(path)

    def _resolve(node):
        """解析一个 AST 节点为 Python 值"""
        try:
            return ast.literal_eval(node)
        except Exception:
            pass
        if isinstance(node, ast.Name):
            return _ns.get(node.id)
        if isinstance(node, ast.Attribute):
            _base = _resolve(node.value)
            return getattr(_base, node.attr, None) if _base is not None else None
        if isinstance(node, ast.Dict):
            _out = {}
            for _k, _v in zip(node.keys, node.values):
                _kk = _resolve(_k)
                if _kk is None:
                    continue
                _out[_key_str(_kk)] = _resolve(_v)
            return _out
        if isinstance(node, (ast.List, ast.Tuple)):
            return [_resolve(_e) for _e in node.elts]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            _v = _resolve(node.operand)
            return -_v if isinstance(_v, (int, float)) else None
        return None

    # 遍历：找 `var_name = {...}` 赋值（可限定在某个函数内）
    _target = None
    for _n in ast.walk(_tree):
        if isinstance(_n, (ast.FunctionDef,)):
            if func_name and _n.name != func_name:
                continue
            for _st in ast.walk(_n):
                if isinstance(_st, ast.Assign):
                    for _t in _st.targets:
                        if isinstance(_t, ast.Name) and _t.id == var_name:
                            _target = _st.value
            if _target is not None:
                break
    if _target is None:
        # 模块级赋值
        for _st in _tree.body:
            if isinstance(_st, ast.Assign):
                for _t in _st.targets:
                    if isinstance(_t, ast.Name) and _t.id == var_name:
                        _target = _st.value
    if _target is None or not isinstance(_target, ast.Dict):
        return {}
    _res = _resolve(_target)
    return _res if isinstance(_res, dict) else {}


def _key_str(v):
    """枚举 → 枚举名字符串"""
    _n = getattr(v, "name", None)
    if _n:
        return str(_n)
    return str(v)


class _EnumKey:
    """枚举成员的轻量替身（避免 import 重型模块）"""
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<{self.name}>"

    def __eq__(self, o):
        return getattr(o, "name", None) == self.name

    def __hash__(self):
        return hash(self.name)


class _EnumProxy:
    """枚举类替身：WeaponType.PISTOL → _EnumKey('PISTOL')"""

    def __init__(self, members):
        self._m = {_x: _EnumKey(_x) for _x in members}

    def __getattr__(self, n):
        if n.startswith("_"):
            raise AttributeError(n)
        return self._m.get(n)


def _enum_members_from_source(path, class_name):
    """纯 AST：从源文件里读枚举类名下的成员名列表"""
    import ast
    try:
        with open(path, "r", encoding="utf-8") as _f:
            _tree = ast.parse(_f.read())
    except Exception:
        return []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.ClassDef) and _n.name == class_name:
            _out = []
            for _st in _n.body:
                if isinstance(_st, ast.Assign):
                    for _t in _st.targets:
                        if isinstance(_t, ast.Name):
                            _out.append(_t.id)
            return _out
    return []


def _colors_from_config(root):
    """纯 AST：从 config.py 读 NAME = (r,g,b) 颜色常量"""
    import ast
    _out = {}
    try:
        with open(root and __import__("os").path.join(root, "config.py") or "config.py",
                  "r", encoding="utf-8") as _f:
            _tree = ast.parse(_f.read())
    except Exception:
        return _out
    for _st in _tree.body:
        if isinstance(_st, ast.Assign):
            for _t in _st.targets:
                if not isinstance(_t, ast.Name):
                    continue
                try:
                    _v = ast.literal_eval(_st.value)
                except Exception:
                    continue
                if isinstance(_v, (tuple, list)) and len(_v) == 3 and \
                        all(isinstance(_x, int) for _x in _v):
                    _out[_t.id] = tuple(_v)
    return _out


def _build_namespace(path):
    """构造用于解析常量的命名空间（枚举 + 颜色）

    全部走 **纯 AST**，不 import 任何游戏模块 ——
    这样在缺少 pygame 的环境里（打包机/CI/命令行工具）也能建库。
    """
    import os as _os
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _ns = {}
    _ns.update(_colors_from_config(_root))
    # 枚举全部定义在 config.py（v2.8.3 文件结构整理后集中于此）
    for _rel, _cls in (("config.py", "WeaponType"),
                       ("config.py", "EnemyType"),
                       ("config.py", "RuneType"),
                       ("buff.py", "BuffType"),
                       ("skills.py", "SkillType")):
        _members = _enum_members_from_source(_os.path.join(_root, _rel), _cls)
        if not _members:
            continue
        _proxy = _EnumProxy(_members)
        _ns[_cls] = _proxy
        for _m in _members:
            _ns[_m] = _proxy._m[_m]
            _ns[f"{_cls}.{_m}"] = _proxy._m[_m]
    return _ns


def extract_weapons():
    """从 weapons.py 抽取武器配置"""
    import os
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return _extract_dict_from_source(os.path.join(_root, "weapons.py"),
                                     func_name="_setup_weapon", var_name="configs")


def extract_enemies():
    """从 entities_pkg/enemy.py 抽取敌人基础配置"""
    import os
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return _extract_dict_from_source(os.path.join(_root, "entities_pkg", "enemy.py"),
                                     func_name=None, var_name="base_configs")


def extract_buffs():
    """从 buff.py 抽取 BUFF_CONFIGS"""
    import os
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return _extract_dict_from_source(os.path.join(_root, "buff.py"),
                                     func_name=None, var_name="BUFF_CONFIGS")


def extract_skills():
    """从 skills.py 抽取技能卡数值

    技能不是字典字面量，而是 `Skill(SkillType.XXX, 名称, 描述, 上限, ...)`
    的调用列表，所以用 AST 解析 Call 的关键字参数。
    """
    import ast
    import os as _os
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _src_path = _os.path.join(_root, "skills.py")
    try:
        with open(_src_path, "r", encoding="utf-8") as _f:
            _tree = ast.parse(_f.read())
    except Exception:
        return {}
    _ns = _build_namespace(_src_path)
    _out = {}
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.Call):
            continue
        _fn = _n.func
        _fname = getattr(_fn, "id", None) or getattr(_fn, "attr", None)
        if _fname != "Skill":
            continue
        if not _n.args or not isinstance(_n.args[0], ast.Attribute):
            continue
        _key = _n.args[0].attr

        def _lit(node):
            try:
                return ast.literal_eval(node)
            except Exception:
                if isinstance(node, ast.Name):
                    return _ns.get(node.id)
                if isinstance(node, ast.Attribute):
                    _b = _ns.get(getattr(node.value, "id", ""))
                    return getattr(_b, node.attr, None) if _b is not None else None
                return None

        _row = {"key": _key}
        if len(_n.args) >= 2:
            _row["name"] = _lit(_n.args[1]) or _key
        if len(_n.args) >= 3:
            _row["desc"] = _lit(_n.args[2]) or ""
        if len(_n.args) >= 4:
            try:
                _row["max_level"] = int(_lit(_n.args[3]))
            except Exception:
                pass
        for _kw in _n.keywords:
            if _kw.arg in ("effect_key", "effect_per_level"):
                _row[_kw.arg] = _lit(_kw.value)
            elif _kw.arg == "icon_color":
                _row["icon_color"] = _lit(_kw.value)
            elif _kw.arg == "is_active":
                _row["is_active"] = 1 if _lit(_kw.value) else 0
            elif _kw.arg == "level_descriptions":
                _row["level_descriptions"] = _lit(_kw.value)
        _out[_key] = _row
    return _out


def extract_runes():
    """从 runes.py 抽取符文配置"""
    import os
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _d = _extract_dict_from_source(os.path.join(_root, "runes.py"),
                                   func_name=None, var_name="RUNE_CONFIG")
    if not _d:
        _d = _extract_dict_from_source(os.path.join(_root, "runes.py"),
                                       func_name=None, var_name="RUNE_INFO")
    return _d
