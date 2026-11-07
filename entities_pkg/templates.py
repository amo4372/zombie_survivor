# -*- coding: utf-8 -*-
"""僵尸 / Boss 模板与统一行为层（v2.9.13）

设计目标
--------
1. 模板：每个 EnemyType 一份数据表（内置默认 + SQLite enemies 表覆盖），
   用 EnemyTemplate 包装成对象，不再把一大坨字典硬编码在 Enemy._setup_enemy 里。
2. 统一行为：BehaviorProfile 把「移动模式 / 目标选择 / 攻击偏好 /
   群体分工 / Boss 阶段」抽出来，所有僵尸共用同一套行为接口。
3. 数据库权威：resolve() 优先读 game_data.db，缺表/缺行/读失败回退内置，
   且按内置值的类型强制转换（沿用 gamedata 的 coerce_like）。
4. 向后兼容：resolve_config() 返回老代码期待的普通 dict，
   Enemy._setup_enemy 的 setattr 循环不用改。

策划改数据：SQLite 打开 game_data.db → enemies 表 → 改 hp/speed/damage/extra。
extra(JSON) 里可放 melee_* / behavior_* 等任意模板字段。
"""
import json
from config import *   # 颜色常量（DARK_GREEN / PURPLE / ...）

# 内置模板（从旧 _setup_enemy 的 base_configs 原样抽取）
BUILTIN_TEMPLATES = {
    "ZOMBIE_NORMAL": {
        "hp": 35, "speed": 1.8, "damage": 12, "size": 15,
        "color": DARK_GREEN, "exp": 10, "score": 10
    },
    "ZOMBIE_FAST": {
        "hp": 20, "speed": 3.5, "damage": 10, "size": 12,
        "color": POISON_GREEN, "exp": 15, "score": 15
    },
    "ZOMBIE_TANK": {
        "hp": 120, "speed": 1.0, "damage": 25, "size": 22,
        "color": GRAY, "exp": 30, "score": 30
    },
    "ZOMBIE_RANGED": {
        "hp": 30, "speed": 1.5, "damage": 18, "size": 14,
        "color": PURPLE, "exp": 20, "score": 20,
        "attack_range": 300, "attack_cooldown": 2.0,
        "can_throw": True, "throw_type": "rock",
    },
    # === 新机制僵尸 ===
    "ZOMBIE_EXPLODER": {
        "hp": 40, "speed": 2.5, "damage": 8, "size": 16,
        "color": RUST, "exp": 25, "score": 25,
        "is_exploder": True, "explode_radius": 100, "explode_damage": 100
    },
    "ZOMBIE_CRAWLER": {
        "hp": 15, "speed": 4.0, "damage": 8, "size": 8,
        "color": SLATE, "exp": 12, "score": 12,
        "is_crawler": True, "dodge_chance": 0.3
    },
    "ZOMBIE_SPLITTER": {
        "hp": 80, "speed": 1.3, "damage": 15, "size": 18,
        "color": BLOOD_RED, "exp": 35, "score": 35,
        "is_splitter": True, "split_into": 2
    },
    "ZOMBIE_SHIELD": {
        "hp": 60, "speed": 1.2, "damage": 15, "size": 17,
        "color": CHARCOAL, "exp": 22, "score": 22,
        "is_shield": True, "front_reduction": 0.6
    },
    "ZOMBIE_HEALER": {
        "hp": 35, "speed": 1.0, "damage": 10, "size": 14,
        "color": GREEN, "exp": 30, "score": 30,
        "is_healer": True, "heal_amount": 5, "heal_interval": 2.0
    },
    "ZOMBIE_PHANTOM": {
        "hp": 45, "speed": 2.0, "damage": 20, "size": 15,
        "color": PURPLE, "exp": 28, "score": 28,
        "is_phantom": True, "invisible_duration": 2.0, "visible_duration": 3.0
    },
    "BOSS_LONG": {
        "hp": 6000, "speed": 1.5, "damage": 75, "size": 35,
        "color": BLOOD_RED, "exp": 500, "score": 1000,
        "is_boss": True, "name": "龙某"
    },
    "BOSS_XIANG": {
        "hp": 5000, "speed": 1.8, "damage": 55, "size": 32,
        "color": RUST, "exp": 500, "score": 1000,
        "is_boss": True, "name": "向某"
    },
    # === 新Boss ===
    "BOSS_MUTANT": {
        "hp": 8000, "speed": 2.2, "damage": 70, "size": 38,
        "color": BLOOD_RED, "exp": 800, "score": 1500,
        "is_boss": True, "name": "变异体-深渊",
        "has_combo": True, "combo_damage_mult": 3.0,
    },
    "BOSS_QUEEN": {
        "hp": 7000, "speed": 1.3, "damage": 45, "size": 40,
        "color": PURPLE, "exp": 800, "score": 1500,
        "is_boss": True, "name": "尸潮女王",
        "summons_minions": True, "summon_interval": 8.0,
    },
    "BOSS_TITAN": {
        "hp": 12000, "speed": 0.9, "damage": 110, "size": 50,
        "color": CHARCOAL, "exp": 1000, "score": 2000,
        "is_boss": True, "name": "泰坦",
        "is_titan": True, "stomp_damage": 200, "stomp_radius": 150,
    },
    "BOSS_WANG": {
        "hp": 10000, "speed": 1.6, "damage": 70, "size": 36,
        "color": (70, 70, 80), "exp": 1200, "score": 2500,
        "is_boss": True, "name": "王某",
        "has_gunfire": True, "has_scythe": True,
        "scythe_damage_mult": 3.6,
    },
    # === 精英怪 ===
    "ELITE_BRUTE": {
        "hp": 300, "speed": 1.4, "damage": 35, "size": 24,
        "color": DARK_RED, "exp": 80, "score": 80,
        "is_elite": True, "name": "精英蛮兵",
        "heavy_attack_chance": 0.3, "heavy_damage_mult": 2.5,
    },
    "ELITE_ASSASSIN": {
        "hp": 150, "speed": 4.5, "damage": 40, "size": 14,
        "color": CYAN, "exp": 80, "score": 80,
        "is_elite": True, "name": "精英刺客",
        "dash_chance": 0.25, "dash_damage_mult": 3.0,
    },
    "ELITE_SORCERER": {
        "hp": 180, "speed": 1.2, "damage": 25, "size": 16,
        "color": PURPLE, "exp": 90, "score": 90,
        "is_elite": True, "name": "精英术士",
        "is_ranged": True, "projectile_damage": 30, "attack_range": 350,
        "applies_curse": True,
        "can_throw": True, "throw_type": "fire",
    },
    "ELITE_GUARDIAN": {
        "hp": 400, "speed": 1.0, "damage": 20, "size": 22,
        "color": GOLD, "exp": 100, "score": 100,
        "is_elite": True, "name": "精英守卫",
        "aura_heal": True, "aura_radius": 120, "aura_heal_amount": 3,
        "shield_reduction": 0.5,
    },
    # === 新普通僵尸 ===
    "ZOMBIE_SPITTER": {
        "hp": 30, "speed": 1.5, "damage": 10, "size": 14,
        "color": LIME, "exp": 18, "score": 18,
        "is_ranged": True, "projectile_damage": 12, "attack_range": 250,
        "applies_corrosion": True,
        "can_throw": True, "throw_type": "acid",
    },
    "ZOMBIE_LEAPER": {
        "hp": 25, "speed": 2.0, "damage": 18, "size": 13,
        "color": ORANGE, "exp": 20, "score": 20,
        "leap_chance": 0.15, "leap_range": 200, "leap_damage_mult": 2.0,
    },
    "ZOMBIE_CORPSE_EATER": {
        "hp": 50, "speed": 1.3, "damage": 15, "size": 17,
        "color": BROWN, "exp": 25, "score": 25,
        "eats_corpses": True, "grow_per_corpse": 1.2,
    },
    "ZOMBIE_WRAITH": {
        "hp": 35, "speed": 2.5, "damage": 15, "size": 15,
        "color": PURPLE, "exp": 30, "score": 30,
        "is_wraith": True, "phase_through": True,
        "applies_fear": True, "fear_chance": 0.2,
    },
    # === 新增僵尸类型 ===
    "ZOMBIE_BOMBER": {
        "hp": 40, "speed": 2.0, "damage": 20, "size": 16,
        "color": ORANGE, "exp": 28, "score": 28,
        "can_throw": True, "throw_type": "bomb",
        "is_bomber": True,
    },
    "ZOMBIE_FROST": {
        "hp": 45, "speed": 1.5, "damage": 12, "size": 16,
        "color": CYAN, "exp": 25, "score": 25,
        "is_frost": True, "applies_slow": True,
        "slow_duration": 2.0, "slow_amount": 0.5,
    },
    "ZOMBIE_VENOM": {
        "hp": 30, "speed": 2.2, "damage": 8, "size": 14,
        "color": POISON_GREEN, "exp": 26, "score": 26,
        "is_venom": True, "applies_poison": True,
        "poison_damage": 5, "poison_duration": 4.0,
    },
    "ZOMBIE_BERSERKER": {
        "hp": 80, "speed": 1.8, "damage": 18, "size": 18,
        "color": CRIMSON, "exp": 35, "score": 35,
        "is_berserker": True, "enrage_below_hp": 0.4,
        "enrage_speed_mult": 2.0, "enrage_damage_mult": 1.5,
    },
    "ZOMBIE_GHOUL": {
        "hp": 50, "speed": 2.0, "damage": 10, "size": 15,
        "color": BLOOD_RED, "exp": 28, "score": 28,
        "is_ghoul": True, "bleed_chance": 0.4,
        "bleed_damage": 3, "bleed_duration": 3.0,
    },
    "ZOMBIE_SHAMAN": {
        "hp": 35, "speed": 1.2, "damage": 8, "size": 15,
        "color": MAGENTA, "exp": 32, "score": 32,
        "is_shaman": True, "buff_radius": 120,
        "buff_damage_mult": 1.3, "buff_speed_mult": 1.2,
    },
    "ZOMBIE_HUNTER": {
        "hp": 35, "speed": 1.8, "damage": 25, "size": 14,
        "color": DARK_BLUE, "exp": 30, "score": 30,
        "is_hunter": True, "attack_range": 350,
        "attack_cooldown": 3.0, "is_ranged": True,
    },
    "ZOMBIE_JUGGERNAUT": {
        "hp": 200, "speed": 0.8, "damage": 30, "size": 25,
        "color": DARK_GRAY, "exp": 50, "score": 50,
        "is_juggernaut": True, "armor": 0.5,
        "knockback_resist": 0.8,
    },
}

_ARCHETYPE_RULES = [
    ("BOSS",     lambda c: bool(c.get("is_boss"))),
    ("ELITE",    lambda c: bool(c.get("is_elite"))),
    ("RANGED",   lambda c: bool(c.get("is_ranged") or c.get("can_throw") or c.get("attack_range"))),
    ("EXPLODER", lambda c: bool(c.get("is_exploder") or c.get("is_bomber"))),
    ("HEALER",   lambda c: bool(c.get("is_healer") or c.get("aura_heal"))),
    ("SHIELD",   lambda c: bool(c.get("is_shield") or c.get("is_juggernaut"))),
    ("PHANTOM",  lambda c: bool(c.get("is_phantom") or c.get("is_wraith"))),
    ("FAST",     lambda c: float(c.get("speed") or 1.8) >= 3.0),
    ("TANK",     lambda c: float(c.get("hp") or 40) >= 100),
    ("MELEE",    lambda c: True),
]

BEHAVIOR_PRESETS = {
    "BOSS":     dict(move="phase_adaptive", target="threat",       aggression=0.95, spacing=140, flank=0.15, dodge=0.25, phase_hp=[0.65, 0.30]),
    "ELITE":    dict(move="flank",          target="weakest",      aggression=0.80, spacing=90,  flank=0.55, dodge=0.35, phase_hp=[]),
    "RANGED":   dict(move="kite",           target="nearest",      aggression=0.55, spacing=260, flank=0.30, dodge=0.55, phase_hp=[]),
    "EXPLODER": dict(move="rush",           target="nearest",      aggression=1.00, spacing=0,   flank=0.00, dodge=0.00, phase_hp=[]),
    "HEALER":   dict(move="stay_behind",    target="ally_cluster", aggression=0.20, spacing=180, flank=0.20, dodge=0.45, phase_hp=[]),
    "SHIELD":   dict(move="frontal",        target="nearest",      aggression=0.60, spacing=35,  flank=0.05, dodge=0.05, phase_hp=[]),
    "PHANTOM":  dict(move="flank",          target="weakest",      aggression=0.75, spacing=70,  flank=0.85, dodge=0.70, phase_hp=[]),
    "FAST":     dict(move="flank",          target="weakest",      aggression=0.85, spacing=45,  flank=0.70, dodge=0.45, phase_hp=[]),
    "TANK":     dict(move="frontal",        target="nearest",      aggression=0.55, spacing=30,  flank=0.05, dodge=0.05, phase_hp=[]),
    "MELEE":    dict(move="surround",       target="nearest",      aggression=0.70, spacing=40,  flank=0.45, dodge=0.20, phase_hp=[]),
}

MELEE_DEFAULTS = dict(melee_attack_cooldown=1.2, melee_attack_reach=10.0,
                      melee_windup=0.35, melee_recover=0.25)
BOSS_MELEE_DEFAULTS = dict(melee_attack_cooldown=1.6, melee_attack_reach=18.0,
                           melee_windup=0.55, melee_recover=0.40)
ELITE_MELEE_DEFAULTS = dict(melee_attack_cooldown=1.0, melee_attack_reach=14.0,
                            melee_windup=0.30, melee_recover=0.22)


def archetype_of(config):
    for name, fn in _ARCHETYPE_RULES:
        try:
            if fn(config):
                return name
        except Exception:
            continue
    return "MELEE"


class BehaviorProfile:
    """统一行为描述：所有僵尸共用一套字段，AI 层只消费这个对象"""
    FIELDS = ("move", "target", "aggression", "spacing", "flank", "dodge", "phase_hp")

    def __init__(self, archetype="MELEE", **overrides):
        self.archetype = archetype
        preset = dict(BEHAVIOR_PRESETS.get(archetype, BEHAVIOR_PRESETS["MELEE"]))
        preset.update({k: v for k, v in overrides.items() if k in self.FIELDS})
        for k, v in preset.items():
            setattr(self, k, v)

    def phase(self, hp_ratio):
        ph = list(getattr(self, "phase_hp", []) or [])
        if not ph:
            return 0
        if hp_ratio <= ph[-1]:
            return 2
        if hp_ratio <= ph[0]:
            return 1
        return 0

    def as_dict(self):
        d = {k: getattr(self, k, None) for k in self.FIELDS}
        d["archetype"] = self.archetype
        return d

    def __repr__(self):
        return "<Behavior %s %s>" % (self.archetype, self.move)


class EnemyTemplate:
    """一份僵尸模板：数值 + 行为 + 数据库覆盖"""
    def __init__(self, key, data=None, behavior=None):
        self.key = str(key)
        self.data = dict(data or BUILTIN_TEMPLATES.get(self.key, {}))
        self.archetype = archetype_of(self.data)
        self.behavior = behavior or BehaviorProfile(self.archetype)

    def resolve(self, use_db=True):
        cfg = dict(self.data)
        if use_db:
            try:
                from gamedata import db as _gdb
                from gamedata.db import coerce_like
                row = _gdb.row("enemies", self.key)
                if row:
                    for k, v in row.items():
                        if k in ("key", "extra", "desc", "name"):
                            continue
                        cfg[k] = coerce_like(v, cfg.get(k, v))
                    ex = row.get("extra")
                    if isinstance(ex, str):
                        ex = json.loads(ex)
                    if isinstance(ex, dict):
                        for k, v in ex.items():
                            cfg[k] = coerce_like(v, cfg.get(k, v))
            except Exception:
                pass
        arch = archetype_of(cfg)
        md = (BOSS_MELEE_DEFAULTS if arch == "BOSS" else
              ELITE_MELEE_DEFAULTS if arch == "ELITE" else MELEE_DEFAULTS)
        for k, v in md.items():
            cfg.setdefault(k, v)
        ov = {}
        for k in list(cfg):
            if k.startswith("behavior_"):
                ov[k[len("behavior_"):]] = cfg[k]
        behavior = BehaviorProfile(arch, **ov)
        return cfg, behavior

    def __repr__(self):
        return "<Template %s [%s] hp=%s>" % (self.key, self.archetype, self.data.get("hp"))


_REGISTRY = {}


def template_for(enemy_type):
    key = getattr(enemy_type, "name", str(enemy_type))
    if key not in _REGISTRY:
        _REGISTRY[key] = EnemyTemplate(key)
    return _REGISTRY[key]


def resolve_config(enemy_type, fallback=None):
    """Enemy._setup_enemy 使用的唯一入口。返回 (config, behavior)"""
    tpl = template_for(enemy_type)
    cfg, beh = tpl.resolve()
    if fallback:
        for k, v in fallback.items():
            cfg.setdefault(k, v)
    return cfg, beh


def all_templates():
    return {k: EnemyTemplate(k, v) for k, v in BUILTIN_TEMPLATES.items()}


def summary():
    out = {}
    for k, v in BUILTIN_TEMPLATES.items():
        a = archetype_of(v)
        out[a] = out.get(a, 0) + 1
    return out


__all__ = ["BUILTIN_TEMPLATES", "BEHAVIOR_PRESETS", "BehaviorProfile",
           "EnemyTemplate", "template_for", "resolve_config", "all_templates",
           "archetype_of", "summary"]
