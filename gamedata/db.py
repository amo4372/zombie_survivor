# -*- coding: utf-8 -*-
"""SQLite 数据访问层

特性：
- 首次运行自动用代码默认值建库（game_data.db）
- 全表内存缓存 + mtime 热重载（策划改库后无需重启，重新开局即生效）
- 缺表 / 缺行 / 读失败 → 一律回退代码内置默认值，绝不抛异常打断游戏
"""

import json
import os
import sqlite3
import threading
import time

from .schema import create_all
from . import defaults as D

_ENSURE_LOCK = threading.Lock()


def _color_to_hex(v):
    """颜色（元组/字符串）→ #RRGGBB"""
    if isinstance(v, str):
        return v if v.startswith("#") else "#" + v
    if isinstance(v, (tuple, list)) and len(v) >= 3:
        return "#%02X%02X%02X" % (int(v[0]) & 255, int(v[1]) & 255, int(v[2]) & 255)
    return "#FFFFFF"


def _hex_to_color(s):
    """#RRGGBB → (r,g,b)；非法返回 None"""
    if not isinstance(s, str):
        return None
    _s = s.strip().lstrip("#")
    if len(_s) != 6:
        return None
    try:
        return (int(_s[0:2], 16), int(_s[2:4], 16), int(_s[4:6], 16))
    except Exception:
        return None


def connect(path, timeout=10):
    """打开数据库并应用兼容参数

    使用 `journal_mode=MEMORY`：某些文件系统（Android 外置存储 / 部分网络盘 /
    容器挂载目录）不支持 SQLite 的日志文件，会直接报 "disk I/O error"。
    本数据库以读为主、写入只在建库与同步时发生，用 MEMORY 日志完全够用。
    """
    # 某些文件系统首次打开会瞬时返回 "disk I/O error"，重试即可成功
    _last = None
    for _i in range(4):
        try:
            _c = sqlite3.connect(path, timeout=timeout)
            try:
                _c.execute("PRAGMA journal_mode=MEMORY")
                _c.execute("PRAGMA temp_store=MEMORY")
            except Exception:
                pass
            return _c
        except Exception as _e:
            _last = _e
            try:
                time.sleep(0.15 * (_i + 1))
            except Exception:
                pass
    raise _last



# ======================================================================
# v2.8.4 类型转换层
# ----------------------------------------------------------------------
# SQLite 只有 TEXT/REAL/INTEGER 三种类型，而游戏代码里的配置值是
# int / float / str / tuple(颜色) / dict / bool 混用的。直接把数据库里的值
# 塞回代码会产生两类崩溃：
#   1) 颜色元组被存成 "#RRGGBB" 字符串 → 渲染时 c * 0.5 触发
#      "can't multiply sequence by non-int of type 'float'"
#   2) 数值被存成字符串（如 ammo "3"）→ 比较时触发
#      "'<=' not supported between instances of 'str' and 'int'"
#
# 解决办法：以**代码内置默认值的类型**为准，把数据库读出的值强制转换回去。
# 策划改的是数值大小，不是数值类型，所以这样做既安全又符合直觉。
# ======================================================================

def _num(v):
    """字符串 → int/float（无法解析返回 None）"""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        _t = v.strip()
        try:
            return int(_t)
        except Exception:
            pass
        try:
            return float(_t)
        except Exception:
            return None
    return None


def _coerce_color(v):
    """任意形式 → (r,g,b) 或 None"""
    if isinstance(v, str):
        _c = _hex_to_color(v)
        if _c:
            return _c
        # "(220, 200, 60)" 这种写法也兼容
        try:
            import ast as _ast
            _p = _ast.literal_eval(v)
            if isinstance(_p, (tuple, list)) and len(_p) >= 3:
                return (int(_p[0]) & 255, int(_p[1]) & 255, int(_p[2]) & 255)
        except Exception:
            pass
        return None
    if isinstance(v, (tuple, list)) and len(v) >= 3:
        try:
            return (int(v[0]) & 255, int(v[1]) & 255, int(v[2]) & 255)
        except Exception:
            return None
    return None


def coerce_like(v, ref):
    """把数据库值 v 转换成与代码默认值 ref **相同类型**的值

    ref 为 None（代码里没有这个字段，策划新增的）时按内容推断。
    任何转换失败都返回 ref（保证类型永远正确，绝不把错类型漏给游戏）。
    """
    if v is None:
        return ref
    # 颜色：ref 是三元组，或 v 看起来像颜色
    if isinstance(ref, (tuple, list)) and len(ref) >= 3 and             all(isinstance(_x, int) for _x in ref[:3]):
        _c = _coerce_color(v)
        return _c if _c is not None else ref
    if isinstance(ref, bool):
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)
    if isinstance(ref, int):
        _n = _num(v)
        return int(_n) if _n is not None else ref
    if isinstance(ref, float):
        _n = _num(v)
        return float(_n) if _n is not None else ref
    if isinstance(ref, str):
        return v if isinstance(v, str) else str(v)
    if isinstance(ref, dict):
        if isinstance(v, dict):
            # JSON 会把 int 键变成字符串键（如技能的 level_descriptions），
            # 这里按 ref 的键类型还原，否则 level_descriptions[1] 会 KeyError
            if ref and all(isinstance(_k, int) for _k in ref.keys()):
                try:
                    return {int(_k): _vv for _k, _vv in v.items()}
                except Exception:
                    return v
            if ref and all(isinstance(_k, str) for _k in ref.keys()):
                return {str(_k): _vv for _k, _vv in v.items()}
            return v
        if isinstance(v, str):
            try:
                _d = json.loads(v)
                if not isinstance(_d, dict):
                    return ref
                return coerce_like(_d, ref)
            except Exception:
                return ref
        return ref
    if isinstance(ref, (list, tuple)):
        if isinstance(v, (list, tuple)):
            return type(ref)(v)
        if isinstance(v, str):
            try:
                import ast as _ast
                _p = _ast.literal_eval(v)
                if isinstance(_p, (list, tuple)):
                    return type(ref)(_p)
            except Exception:
                pass
        return ref
    # ref 为 None：按内容推断
    if isinstance(v, str):
        if v.startswith("#") or (len(v) == 6 and all(_c in "0123456789ABCDEFabcdef" for _c in v)):
            _c = _coerce_color(v)
            if _c:
                return _c
        _n = _num(v)
        if _n is not None:
            return _n
    return v


def merge_row(row, fallback, skip=("key", "extra")):
    """把数据库行合并进代码默认值，并逐字段做类型转换

    - row 里为 NULL 的字段用 fallback 的值
    - 每个字段按 fallback 的类型强制转换
    - 跳过 key / extra 这两个元数据列（extra 已单独解析合并）
    """
    _out = dict(fallback or {})
    for _k, _v in (row or {}).items():
        if _k in skip:
            continue
        _ref = _out.get(_k) if fallback else None
        if isinstance(_ref, bool):
            pass
        elif _v is None and _ref is not None:
            continue
        _out[_k] = coerce_like(_v, _ref)
    return _out


class GameDatabase:
    def __init__(self, path):
        self.path = path
        self._cache = {}          # table -> [dict]
        self._by_key = {}         # table -> {key: dict}
        self._mtime = 0.0
        self._loaded = False
        self._lock = threading.RLock()
        self.available = False
        self.last_error = None
        try:
            self._ensure_db()
            self.reload(force=True)
        except Exception as _e:
            self.last_error = str(_e)
            self.available = False

    # ------------------------------------------------------------------
    # 建库 / 播种
    # ------------------------------------------------------------------
    def _ensure_db(self):
        with _ENSURE_LOCK:
            _need_seed = not os.path.exists(self.path)
            try:
                _conn = connect(self.path, timeout=10)
            except Exception as _e:
                self.last_error = f"数据库无法打开: {_e}"
                self.available = False
                return
            try:
                create_all(_conn)
                if _need_seed:
                    self._seed(_conn)
            finally:
                _conn.close()

    def _seed(self, conn):
        """用代码默认值播种"""
        try:
            from .seed import seed_all, seed_tuning, seed_difficulty
            seed_tuning(conn)
            seed_difficulty(conn)
            seed_all(conn)
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
                         ("seeded_at", time.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        except Exception as _e:
            self.last_error = f"播种失败: {_e}"

    # ------------------------------------------------------------------
    # 加载 / 热重载
    # ------------------------------------------------------------------
    def reload(self, force=False):
        with self._lock:
            try:
                _mt = os.path.getmtime(self.path) if os.path.exists(self.path) else -1
            except Exception:
                _mt = -1
            if not force and self._loaded and abs(_mt - self._mtime) < 1e-6:
                return True
            try:
                _conn = connect(self.path, timeout=10)
                _conn.row_factory = sqlite3.Row
                _cur = _conn.cursor()
                _cache, _by = {}, {}
                for _t in ("weapons", "enemies", "runes", "buffs", "skills", "difficulty", "tuning", "meta"):
                    try:
                        _cur.execute(f"SELECT * FROM {_t}")
                        _rows = [dict(_r) for _r in _cur.fetchall()]
                    except Exception:
                        _rows = []
                    _cache[_t] = _rows
                    _by[_t] = {_r.get("key"): _r for _r in _rows if _r.get("key") is not None}
                _conn.close()
                self._cache, self._by_key = _cache, _by
                self._mtime, self._loaded = _mt, True
                self.available = True
                return True
            except Exception as _e:
                self.last_error = str(_e)
                self.available = False
                return False

    def _check(self):
        """每次访问前检查文件是否变更（热重载）"""
        if not self._loaded:
            self.reload(force=True)
            return
        try:
            _mt = os.path.getmtime(self.path)
        except Exception:
            return
        if abs(_mt - self._mtime) > 1e-6:
            self.reload(force=True)

    # ------------------------------------------------------------------
    # 通用读取
    # ------------------------------------------------------------------
    def table(self, name):
        """整表 → [dict]"""
        try:
            self._check()
            return list(self._cache.get(name, []))
        except Exception:
            return []

    def row(self, table, key):
        """单行 → dict 或 None"""
        try:
            self._check()
            return self._by_key.get(table, {}).get(str(key))
        except Exception:
            return None

    def tuning(self, key, default=None):
        """调参标量"""
        try:
            self._check()
            _r = self._by_key.get("tuning", {}).get(str(key))
            if _r is None:
                return D.TUNING_DEFAULTS.get(str(key), (default, ""))[0] if str(key) in D.TUNING_DEFAULTS else default
            _v = _r.get("value")
            return _v if _v is not None else default
        except Exception:
            return default

    def meta(self, key, default=None):
        try:
            self._check()
            _r = self._by_key.get("meta", {}).get(str(key))
            return _r.get("value") if _r else default
        except Exception:
            return default

    # ------------------------------------------------------------------
    # 领域读取（带内置兜底）
    # ------------------------------------------------------------------
    def weapon(self, weapon_type, fallback=None):
        """武器配置 → dict。数据库没这一行时返回 fallback（代码原值）"""
        _k = getattr(weapon_type, "name", str(weapon_type))
        _r = self.row("weapons", _k)
        if not _r:
            return fallback if fallback is not None else {}
        # v2.8.4：以内置默认值的类型为准做强制转换（颜色/数值/字符串）
        _out = merge_row(_r, fallback)
        # extra（JSON）里的扩展字段同样按类型合并
        _ex = self._extra(_r)
        for _ek, _ev in _ex.items():
            _out[_ek] = coerce_like(_ev, _out.get(_ek))
        return _out

    def enemy(self, enemy_type, fallback=None):
        """敌人配置 → dict"""
        _k = getattr(enemy_type, "name", str(enemy_type))
        _r = self.row("enemies", _k)
        if not _r:
            return fallback if fallback is not None else {}
        # v2.8.4：之前这里**完全没有做颜色转换**——敌人的 color 从数据库
        # 读出来是 "#14501E" 字符串，渲染粒子时 c * 0.5 直接抛
        # "can't multiply sequence by non-int of type 'float'"。
        # 现在统一走类型转换层。
        _out = merge_row(_r, fallback)
        _ex = self._extra(_r)
        for _ek, _ev in _ex.items():
            _out[_ek] = coerce_like(_ev, _out.get(_ek))
        return _out

    def rune(self, rune_type, fallback=None):
        _k = getattr(rune_type, "name", str(rune_type))
        _r = self.row("runes", _k)
        if not _r:
            return fallback if fallback is not None else {}
        _out = merge_row(_r, fallback)
        _ex = self._extra(_r)
        for _ek, _ev in _ex.items():
            _out[_ek] = coerce_like(_ev, _out.get(_ek))
        return _out

    def buff(self, buff_type, fallback=None):
        """Buff 配置 → dict（extra 里的倍率会展开到顶层）"""
        _k = getattr(buff_type, "name", str(buff_type))
        _r = self.row("buffs", _k)
        if not _r:
            return fallback if fallback is not None else {}
        _out = merge_row(_r, fallback)
        _out["is_debuff"] = bool(_r.get("is_debuff"))
        _ex = self._extra(_r)
        for _ek, _ev in _ex.items():
            _out[_ek] = coerce_like(_ev, _out.get(_ek))
        return _out

    def skill(self, skill_type, fallback=None):
        """技能卡数值 → dict"""
        _k = getattr(skill_type, "name", str(skill_type))
        _r = self.row("skills", _k)
        if not _r:
            return fallback if fallback is not None else {}
        _out = merge_row(_r, fallback)
        _ex = self._extra(_r)
        for _ek, _ev in _ex.items():
            _out[_ek] = coerce_like(_ev, _out.get(_ek))
        return _out

    def difficulty(self, name, fallback=None):
        """难度配置 → dict"""
        _r = self.row("difficulty", str(name))
        if not _r:
            return fallback if fallback is not None else dict(
                D.DIFFICULTY_DEFAULTS.get(str(name), {}))
        _base = dict(D.DIFFICULTY_DEFAULTS.get(str(name), {}))
        return merge_row(_r, _base)

    def difficulty_table(self):
        """难度 → {中文名: dict}（缺失的用内置值补齐）"""
        _out = {}
        for _n in D.DIFFICULTY_DEFAULTS:
            _out[_n] = self.difficulty(_n)
        # 数据库里有额外自定义难度也带上
        for _r in self.table("difficulty"):
            _k = _r.get("key")
            if _k and _k not in _out:
                _out[_k] = merge_row(_r, {})
        return _out

    # ------------------------------------------------------------------
    @staticmethod
    def _extra(row):
        """解析 extra JSON 列"""
        _e = row.get("extra")
        if not _e:
            return {}
        try:
            _d = json.loads(_e)
            return _d if isinstance(_d, dict) else {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    def status(self):
        """用于「数据」页面展示的状态"""
        return {
            "path": self.path,
            "exists": os.path.exists(self.path),
            "available": self.available,
            "error": self.last_error,
            "tables": {_t: len(self._cache.get(_t, [])) for _t in
                       ("weapons", "enemies", "runes", "buffs", "skills",
                        "difficulty", "tuning")},
        }
