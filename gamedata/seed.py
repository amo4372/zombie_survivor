# -*- coding: utf-8 -*-
"""用代码默认值播种数据库（只在数据库文件不存在时全量执行）

策略：`INSERT OR IGNORE` —— 已有行不动，只补缺失行。
这样升级版本新增的内容会补进来，策划改过的数值不会被覆盖。
"""

import json
import os

from . import defaults as D


def _color(v):
    if isinstance(v, (tuple, list)) and len(v) >= 3:
        return "#%02X%02X%02X" % (int(v[0]) & 255, int(v[1]) & 255, int(v[2]) & 255)
    if isinstance(v, str):
        return v if v.startswith("#") else "#" + v
    return "#FFFFFF"


def _j(d):
    try:
        return json.dumps(d, ensure_ascii=False)
    except Exception:
        return "{}"


# 武器表里"标准列"之外的字段，塞进 extra
_WEAPON_COLS = {"name", "damage", "fire_rate", "range", "speed", "spread", "pierce",
                "projectile_size", "shake", "color", "desc", "ammo", "reload"}

_ENEMY_COLS = {"name", "hp", "speed", "damage", "size", "color", "desc"}

_BUFF_COLS = {"name", "icon", "color", "is_debuff", "desc"}

_SKILL_COLS = {"name", "desc", "max_level", "effect_key", "effect_per_level", "icon_color"}


_RUNE_COLS = {"name", "color", "rarity", "description", "max_stacks"}


def seed_tuning(conn):
    _c = conn.cursor()
    for _k, (_v, _d) in D.TUNING_DEFAULTS.items():
        _c.execute("INSERT OR IGNORE INTO tuning(key,value,description) VALUES(?,?,?)",
                   (_k, _v, _d))
    conn.commit()


def seed_difficulty(conn):
    _c = conn.cursor()
    for _k, _v in D.DIFFICULTY_DEFAULTS.items():
        _c.execute(
            "INSERT OR IGNORE INTO difficulty(key,enemy_hp_mult,enemy_damage_mult,"
            "enemy_speed_mult,enemy_spawn_mult,player_hp_mult,player_damage_mult,"
            "drop_rate_mult,exp_mult,start_weapons,description) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (_k, _v["enemy_hp_mult"], _v["enemy_damage_mult"], _v["enemy_speed_mult"],
             _v["enemy_spawn_mult"], _v["player_hp_mult"], _v["player_damage_mult"],
             _v["drop_rate_mult"], _v["exp_mult"], _v["start_weapons"], _v["description"]))
    conn.commit()


def seed_weapons(conn):
    _c = conn.cursor()
    _n = 0
    for _k, _v in (D.extract_weapons() or {}).items():
        if not isinstance(_v, dict):
            continue
        _extra = {_kk: _vv for _kk, _vv in _v.items() if _kk not in _WEAPON_COLS}
        _c.execute(
            "INSERT OR IGNORE INTO weapons(key,name,damage,fire_rate,range,speed,spread,"
            "pierce,projectile_size,shake,color,desc,ammo,reload,extra) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_k, _v.get("name"), _v.get("damage"), _v.get("fire_rate"), _v.get("range"),
             _v.get("speed"), _v.get("spread"), _v.get("pierce"), _v.get("projectile_size"),
             _v.get("shake"), _color(_v.get("color")) if _v.get("color") is not None else None,
             _v.get("desc"), str(_v.get("ammo")) if _v.get("ammo") is not None else None,
             _v.get("reload"), _j(_extra)))
        _n += 1
    conn.commit()
    return _n


def seed_enemies(conn):
    _c = conn.cursor()
    _n = 0
    for _k, _v in (D.extract_enemies() or {}).items():
        if not isinstance(_v, dict):
            continue
        _extra = {_kk: _vv for _kk, _vv in _v.items() if _kk not in _ENEMY_COLS}
        _c.execute(
            "INSERT OR IGNORE INTO enemies(key,name,hp,speed,damage,size,color,desc,extra) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (_k, _v.get("name"), _v.get("hp"), _v.get("speed"), _v.get("damage"),
             _v.get("size"), _color(_v.get("color")) if _v.get("color") is not None else None,
             _v.get("desc"), _j(_extra)))
        _n += 1
    conn.commit()
    return _n


def seed_runes(conn):
    _c = conn.cursor()
    _n = 0
    for _k, _v in (D.extract_runes() or {}).items():
        if not isinstance(_v, dict):
            continue
        _extra = {_kk: _vv for _kk, _vv in _v.items() if _kk not in _RUNE_COLS}
        _c.execute(
            "INSERT OR IGNORE INTO runes(key,name,color,rarity,description,max_stacks,extra) "
            "VALUES(?,?,?,?,?,?,?)",
            (_k, _v.get("name"), _color(_v.get("color")) if _v.get("color") is not None else None,
             _v.get("rarity"), _v.get("description"), _v.get("max_stacks"), _j(_extra)))
        _n += 1
    conn.commit()
    return _n


def seed_buffs(conn):
    _c = conn.cursor()
    _n = 0
    for _k, _v in (D.extract_buffs() or {}).items():
        if not isinstance(_v, dict):
            continue
        _extra = {_kk: _vv for _kk, _vv in _v.items() if _kk not in _BUFF_COLS}
        _c.execute(
            "INSERT OR IGNORE INTO buffs(key,name,icon,color,is_debuff,desc,extra) "
            "VALUES(?,?,?,?,?,?,?)",
            (_k, _v.get("name"), _v.get("icon"),
             _color(_v.get("color")) if _v.get("color") is not None else None,
             1 if _v.get("is_debuff") else 0, _v.get("desc"), _j(_extra)))
        _n += 1
    conn.commit()
    return _n


def seed_skills(conn):
    _c = conn.cursor()
    _n = 0
    for _k, _v in (D.extract_skills() or {}).items():
        if not isinstance(_v, dict):
            continue
        _extra = {_kk: _vv for _kk, _vv in _v.items() if _kk not in _SKILL_COLS}
        _c.execute(
            "INSERT OR IGNORE INTO skills(key,name,desc,max_level,effect_key,"
            "effect_per_level,icon_color,extra) VALUES(?,?,?,?,?,?,?,?)",
            (_k, _v.get("name"), _v.get("desc"), _v.get("max_level"),
             _v.get("effect_key"), _v.get("effect_per_level"),
             _color(_v.get("icon_color")) if _v.get("icon_color") is not None else None,
             _j(_extra)))
        _n += 1
    conn.commit()
    return _n


# ======================================================================
# v2.8.8 数据版本（dataver）—— 解决"数据库权威"与"更新要生效"的冲突
# ======================================================================
# 每行带一个 dataver（数据版本号）。发布时种子数据的 dataver = 当前 DATA_VERSION。
# 升级比对规则：
#   发布包 dataver > 本地行 dataver  → 覆盖（策划这一版改过，必须生效）
#   发布包 dataver <= 本地行 dataver → 保留（玩家/策划手工调过，不覆盖）
#   本地缺行                          → 插入
# 这样既"游戏一律读数据库"，又保证"发布的新数值能推到玩家端"。
DATA_VERSION = 1


def ensure_dataver_columns(conn):
    """为各数据表补上 dataver 列"""
    for _t in ("weapons", "enemies", "runes", "buffs", "skills"):
        try:
            _cols = [_r[1] for _r in
                     conn.execute(f"PRAGMA table_info({_t})").fetchall()]
            if "dataver" not in _cols:
                conn.execute(f"ALTER TABLE {_t} ADD COLUMN dataver INTEGER DEFAULT 0")
        except Exception:
            pass
    try:
        conn.commit()
    except Exception:
        pass


def sync_rows_from_code(conn, data_version=None, force=False):
    """按 dataver 把代码默认值同步进数据库（行级）

    返回 (新增行数, 更新行数, 保留行数)
    """
    ensure_dataver_columns(conn)
    _dv = int(data_version if data_version is not None else DATA_VERSION)
    _added = _updated = _kept = 0
    for _table, _rows in (("weapons", D.extract_weapons()),
                          ("enemies", D.extract_enemies()),
                          ("runes", D.extract_runes()),
                          ("buffs", D.extract_buffs()),
                          ("skills", D.extract_skills())):
        try:
            _cols = [_r[1] for _r in
                     conn.execute(f"PRAGMA table_info({_table})").fetchall()]
        except Exception:
            continue
        for _k, _v in _rows.items():
            if not isinstance(_v, dict):
                continue
            _sets, _vals = [], []
            for _f, _fv in _v.items():
                if _f not in _cols or _f == "key":
                    continue
                if isinstance(_fv, (tuple, list)) and len(_fv) >= 3:
                    _sets.append(f"{_f}=?"); _vals.append(_color(_fv))
                elif isinstance(_fv, bool):
                    _sets.append(f"{_f}=?"); _vals.append(1 if _fv else 0)
                elif isinstance(_fv, (int, float)):
                    _sets.append(f"{_f}=?"); _vals.append(_fv)
                elif isinstance(_fv, str):
                    _sets.append(f"{_f}=?"); _vals.append(_fv)
            if not _sets:
                continue
            try:
                _row = conn.execute(
                    f"SELECT dataver FROM {_table} WHERE key=?", (_k,)).fetchone()
            except Exception:
                _row = None
            if _row is None:
                _cs = ["key"] + [x.split("=")[0] for x in _sets] + ["dataver"]
                _vs = [_k] + _vals + [_dv]
                try:
                    conn.execute(
                        f"INSERT INTO {_table} ({','.join(_cs)}) "
                        f"VALUES ({','.join(['?'] * len(_cs))})", _vs)
                    _added += 1
                except Exception:
                    pass
                continue
            _local = _row[0] or 0
            if force or int(_local) < _dv:
                _vals.append(_k)
                try:
                    conn.execute(
                        f"UPDATE {_table} SET {', '.join(_sets)}, dataver=? WHERE key=?",
                        _vals + [_dv])
                    _updated += 1
                except Exception:
                    pass
            else:
                _kept += 1
    try:
        conn.commit()
    except Exception:
        pass
    return _added, _updated, _kept


def overwrite_from_code(conn):
    """v2.8.8：以代码内置默认值为准，**覆盖**数据库里的数值

    为什么需要：数据库是"只补不覆盖"，玩家端 DB 里存的是旧数值。
    策划在代码里把 AWM 从 420 改成 200 后，玩家更新了代码却仍读到 420 ——
    **数值改了但游戏里没变**。

    版本升级意味着"策划改了数值"，此时**代码是权威源**，
    所以对已有行用代码值覆盖（仍不删除用户自建行）。
    返回被覆盖的行数。
    """
    _c = conn.cursor()
    _n = 0
    for _table, _rows in (("weapons", D.extract_weapons()),
                          ("enemies", D.extract_enemies()),
                          ("runes", D.extract_runes()),
                          ("buffs", D.extract_buffs()),
                          ("skills", D.extract_skills())):
        for _k, _v in _rows.items():
            if not isinstance(_v, dict):
                continue
            try:
                _cols = [_r[1] for _r in
                         _c.execute(f"PRAGMA table_info({_table})").fetchall()]
            except Exception:
                continue
            _sets, _vals = [], []
            for _f, _fv in _v.items():
                if _f not in _cols or _f == "key":
                    continue
                if isinstance(_fv, (tuple, list)) and len(_fv) >= 3:
                    _sets.append(f"{_f}=?")
                    _vals.append(_color(_fv))
                elif isinstance(_fv, bool):
                    _sets.append(f"{_f}=?")
                    _vals.append(1 if _fv else 0)
                elif isinstance(_fv, (int, float)):
                    _sets.append(f"{_f}=?")
                    _vals.append(_fv)
                elif isinstance(_fv, str):
                    _sets.append(f"{_f}=?")
                    _vals.append(_fv)
            if not _sets:
                continue
            _vals.append(_k)
            try:
                _n += _c.execute(
                    f"UPDATE {_table} SET {', '.join(_sets)} WHERE key=?",
                    _vals).rowcount
            except Exception:
                continue
    conn.commit()
    return _n


def seed_all(conn):
    """补种所有表（已有行不覆盖）"""
    _r = {
        "weapons": seed_weapons(conn),
        "enemies": seed_enemies(conn),
        "runes": seed_runes(conn),
        "buffs": seed_buffs(conn),
        "skills": seed_skills(conn),
    }
    return _r


def rebuild(conn):
    """强制重建：清空后用默认值重灌（策划改的数据会丢失，仅用于修复损坏）"""
    _c = conn.cursor()
    for _t in ("weapons", "enemies", "runes", "buffs", "skills", "difficulty", "tuning"):
        try:
            _c.execute(f"DELETE FROM {_t}")
        except Exception:
            pass
    conn.commit()
    seed_tuning(conn)
    seed_difficulty(conn)
    return seed_all(conn)
