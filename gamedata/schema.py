# -*- coding: utf-8 -*-
"""数据库表结构定义（SQLite DDL）

改表结构请同步改 defaults.py 的种子数据与 db.py 的读取约定。
策划只需关心表内**行数据**，结构由代码维护。
"""

# 表 → (列名 → 列类型)
SCHEMA = {
    "meta": """
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        )""",

    # 武器：key 为 WeaponType 枚举名（PISTOL / RIFLE / ...）
    "weapons": """
        CREATE TABLE IF NOT EXISTS weapons (
            key             TEXT PRIMARY KEY,
            name            TEXT,
            damage          REAL,
            fire_rate       REAL,
            range           REAL,
            speed           REAL,
            spread          REAL,
            pierce          INTEGER,
            projectile_size REAL,
            shake           REAL,
            color           TEXT,
            desc            TEXT,
            ammo            TEXT,
            reload          REAL,
            extra           TEXT
        )""",

    # 敌人：key 为 EnemyType 枚举名；extra 存特殊机制（JSON）
    "enemies": """
        CREATE TABLE IF NOT EXISTS enemies (
            key   TEXT PRIMARY KEY,
            name  TEXT,
            hp    REAL,
            speed REAL,
            damage REAL,
            size  REAL,
            color TEXT,
            desc  TEXT,
            extra TEXT
        )""",

    # 符文
    "runes": """
        CREATE TABLE IF NOT EXISTS runes (
            key         TEXT PRIMARY KEY,
            name        TEXT,
            color       TEXT,
            rarity      TEXT,
            description TEXT,
            max_stacks  INTEGER,
            extra       TEXT
        )""",

    # 难度：key 为中文难度名
    "difficulty": """
        CREATE TABLE IF NOT EXISTS difficulty (
            key                TEXT PRIMARY KEY,
            enemy_hp_mult      REAL,
            enemy_damage_mult  REAL,
            enemy_speed_mult   REAL,
            enemy_spawn_mult   REAL,
            player_hp_mult     REAL,
            player_damage_mult REAL,
            drop_rate_mult     REAL,
            exp_mult           REAL,
            start_weapons      INTEGER,
            description        TEXT
        )""",

    # Buff 参数：key 为 BuffType 枚举名；extra 存各类倍率（JSON）
    "buffs": (
        "CREATE TABLE IF NOT EXISTS buffs ("
        "key TEXT PRIMARY KEY, name TEXT, icon TEXT, color TEXT,"
        " is_debuff INTEGER, desc TEXT, extra TEXT)"
    ),

    # 技能卡数值：key 为 SkillType 枚举名
    "skills": (
        "CREATE TABLE IF NOT EXISTS skills ("
        "key TEXT PRIMARY KEY, name TEXT, desc TEXT, max_level INTEGER,"
        " effect_key TEXT, effect_per_level REAL, icon_color TEXT, extra TEXT)"
    ),

    # 全局调参：key-value（尸潮间隔、掉落率、玩家基础属性等标量）
    "tuning": """
        CREATE TABLE IF NOT EXISTS tuning (
            key          TEXT PRIMARY KEY,
            value        REAL,
            value_text   TEXT,
            description  TEXT
        )""",
}

TABLES = list(SCHEMA.keys())


def create_all(conn):
    """建表（已存在则跳过）"""
    _c = conn.cursor()
    for _t in TABLES:
        _c.execute(SCHEMA[_t])
    conn.commit()
