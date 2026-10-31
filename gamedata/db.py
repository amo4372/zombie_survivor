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
                for _t in ("weapons", "enemies", "runes", "difficulty", "tuning", "meta"):
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
        _out = dict(_r)
        # 颜色：DB 存 #RRGGBB，代码要元组；转换失败保留原值
        _c = _hex_to_color(_r.get("color"))
        if _c is not None:
            _out["color"] = _c
        elif fallback is not None:
            _out["color"] = fallback.get("color")
        # extra（JSON）合并
        _out.update(self._extra(_r))
        # 补齐缺失字段（用代码默认值兜底）
        if fallback:
            for _fk, _fv in fallback.items():
                if _out.get(_fk) is None:
                    _out[_fk] = _fv
        return _out

    def enemy(self, enemy_type, fallback=None):
        """敌人配置 → dict"""
        _k = getattr(enemy_type, "name", str(enemy_type))
        _r = self.row("enemies", _k)
        if not _r:
            return fallback if fallback is not None else {}
        _out = {_kk: _vv for _kk, _vv in _r.items()
                if _kk not in ("key", "extra") and _vv is not None}
        _out.update(self._extra(_r))
        if fallback:
            for _fk, _fv in fallback.items():
                if _out.get(_fk) is None:
                    _out[_fk] = _fv
        return _out

    def rune(self, rune_type, fallback=None):
        _k = getattr(rune_type, "name", str(rune_type))
        _r = self.row("runes", _k)
        if not _r:
            return fallback if fallback is not None else {}
        _out = dict(_r)
        _c = _hex_to_color(_r.get("color"))
        if _c is not None:
            _out["color"] = _c
        elif fallback is not None:
            _out["color"] = fallback.get("color")
        _out.update(self._extra(_r))
        if fallback:
            for _fk, _fv in fallback.items():
                if _out.get(_fk) is None:
                    _out[_fk] = _fv
        return _out

    def difficulty(self, name, fallback=None):
        """难度配置 → dict"""
        _r = self.row("difficulty", str(name))
        if not _r:
            return fallback if fallback is not None else dict(
                D.DIFFICULTY_DEFAULTS.get(str(name), {}))
        _out = {_kk: _vv for _kk, _vv in _r.items() if _kk != "key" and _vv is not None}
        _base = D.DIFFICULTY_DEFAULTS.get(str(name), {})
        for _fk, _fv in _base.items():
            if _out.get(_fk) is None:
                _out[_fk] = _fv
        return _out

    def difficulty_table(self):
        """难度 → {中文名: dict}（缺失的用内置值补齐）"""
        _out = {}
        for _n in D.DIFFICULTY_DEFAULTS:
            _out[_n] = self.difficulty(_n)
        # 数据库里有额外自定义难度也带上
        for _r in self.table("difficulty"):
            _k = _r.get("key")
            if _k and _k not in _out:
                _out[_k] = {_kk: _vv for _kk, _vv in _r.items()
                            if _kk != "key" and _vv is not None}
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
                       ("weapons", "enemies", "runes", "difficulty", "tuning")},
        }
