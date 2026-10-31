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


def seed_all(conn):
    """补种所有表（已有行不覆盖）"""
    _r = {
        "weapons": seed_weapons(conn),
        "enemies": seed_enemies(conn),
        "runes": seed_runes(conn),
    }
    return _r


def rebuild(conn):
    """强制重建：清空后用默认值重灌（策划改的数据会丢失，仅用于修复损坏）"""
    _c = conn.cursor()
    for _t in ("weapons", "enemies", "runes", "difficulty", "tuning"):
        try:
            _c.execute(f"DELETE FROM {_t}")
        except Exception:
            pass
    conn.commit()
    seed_tuning(conn)
    seed_difficulty(conn)
    return seed_all(conn)
