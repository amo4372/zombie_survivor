#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置和常量模块 - 黑暗色调版"""

import pygame
from enum import Enum, auto

BASE_WIDTH = 1280
BASE_HEIGHT = 720

# 黑暗色调配色方案
WHITE = (220, 220, 220)
BLACK = (10, 10, 12)
RED = (200, 50, 50)
GREEN = (50, 180, 80)
BLUE = (60, 120, 200)
YELLOW = (220, 200, 60)
ORANGE = (220, 140, 40)
PURPLE = (160, 60, 180)
GRAY = (80, 80, 85)
DARK_GRAY = (35, 35, 40)
LIGHT_GRAY = (160, 160, 165)
BROWN = (100, 60, 35)
DARK_GREEN = (20, 80, 30)
CYAN = (40, 200, 200)
DARK_RED = (120, 20, 20)

# 新增/调整配色 - 黑暗主题
GOLD = (220, 180, 40)
DARK_BLUE = (30, 40, 80)
PINK = (220, 80, 140)
LIME = (80, 200, 60)
TEAL = (30, 140, 140)
CRIMSON = (180, 30, 50)
AMBER = (220, 160, 30)
DARK_PURPLE = (60, 20, 80)
BLOOD_RED = (160, 20, 20)
SLATE = (45, 50, 60)
CHARCOAL = (25, 25, 28)
RUST = (180, 80, 30)
POISON_GREEN = (100, 220, 60)
VOID_BLACK = (5, 5, 8)
MUTED_GOLD = (180, 150, 60)

SMOKE_GRAY = (60, 60, 65)
FIRE_ORANGE = (255, 100, 20)
FIRE_YELLOW = (255, 200, 50)
SHOCKWAVE_WHITE = (255, 255, 255, 100)
BLOOD_SPLATTER = (180, 20, 20)
LASER_RED = (255, 50, 50)
PLASMA_BLUE = (50, 150, 255)
MUZZLE_FLASH = (255, 220, 100)
LASER_CORE = (200, 255, 255)
LASER_GLOW = (100, 200, 255, 80)
PLASMA_GLOW = (50, 255, 255, 60)
FLAME_CORE = (255, 180, 50)
FLAME_GLOW = (255, 100, 20, 70)
TRACER_YELLOW = (255, 220, 80)
TRACER_RED = (255, 80, 30)
SPARK_WHITE = (255, 255, 220)
SCREEN_BLOOD = (180, 10, 10, 120)
SHOCK_RING = (255, 255, 255, 150)


class ItemType(Enum):
    VACCINE = auto()
    HEALTH_PACK = auto()
    AMMO_BOX = auto()
    SPEED_BOOST = auto()
    DAMAGE_BOOST = auto()
    SHIELD_REPAIR = auto()

class GameState(Enum):
    MENU = auto()
    SETTINGS = auto()
    TUTORIAL = auto()
    PLAYING = auto()
    PAUSED = auto()
    SKILL_SELECT = auto()  # 替换 SKILL_TREE
    GAME_OVER = auto()
    VICTORY = auto()
    DIALOGUE = auto()
    ENDING = auto()
    RECORDS = auto()  # 新增：记录查看
    ACHIEVEMENTS = auto() #新增:成就页面状态

class ControlMode(Enum):
    KEYBOARD = auto()
    TOUCH = auto()

class GameMode(Enum):
    TIMED = auto()
    ENDLESS = auto()

class EnemyType(Enum):
    ZOMBIE_NORMAL = auto()
    ZOMBIE_FAST = auto()
    ZOMBIE_TANK = auto()
    ZOMBIE_RANGED = auto()
    ZOMBIE_EXPLODER = auto()   # 爆炸僵尸 - 靠近玩家后自爆
    ZOMBIE_CRAWLER = auto()    # 爬行者 - 体型小，速度快，难以命中
    ZOMBIE_SPLITTER = auto()   # 分裂者 - 死后分裂成2个小僵尸
    ZOMBIE_SHIELD = auto()     # 盾兵僵尸 - 正面减伤
    ZOMBIE_HEALER = auto()     # 治疗僵尸 - 给周围僵尸回血
    ZOMBIE_PHANTOM = auto()    # 幻影僵尸 - 偶尔隐身
    BOSS_LONG = auto()
    BOSS_XIANG = auto()

class WeaponType(Enum):
    PISTOL = auto()
    RIFLE = auto()
    SHOTGUN = auto()
    SNIPER = auto()
    MACHINE_GUN = auto()
    ROCKET_LAUNCHER = auto()
    FLAMETHROWER = auto()
    CROSSBOW = auto()          # 十字弩 - 高穿透，可回收
    GRENADE_LAUNCHER = auto()  # 榴弹发射器 - 抛物线AOE
    PLASMA_RIFLE = auto()      # 等离子步枪 - 持续伤害
    RAILGUN = auto()           # 轨道炮 - 超高伤害，穿透一切
    MINIGUN = auto()           # 加特林 - 极高射速，移动减速
    DOUBLE_BARREL = auto()     # 双管霰弹 - 近距离毁灭

class SkillType(Enum):
    # 被动技能
    HEALTH_UP = auto()
    SPEED_UP = auto()
    DAMAGE_UP = auto()
    FIRE_RATE_UP = auto()
    CRIT_CHANCE = auto()
    CRIT_DAMAGE = auto()
    LIFE_STEAL = auto()
    PICKUP_RANGE = auto()
    EXP_BOOST = auto()
    COOLDOWN_REDUCTION = auto()
    ARMOR_UP = auto()          # 新增：护甲提升
    REGENERATION = auto()      # 新增：生命恢复
    DODGE_CHANCE = auto()      # 新增：闪避几率
    VAMPIRE_AURA = auto()      # 新增：吸血光环
    FORTRESS = auto()          # 新增：堡垒 - 静止时减伤

    # 主动技能
    DASH = auto()
    GRENADE = auto()
    TURRET = auto()
    AIRSTRIKE = auto()
    SHIELD_BASH = auto()
    GRAPPLE_PULL = auto()
    TIME_SLOW = auto()
    OVERLOAD = auto()
    RIOT_GEAR = auto()
    STEEL_WILL = auto()
    BLINK = auto()             # 新增：闪烁 - 瞬移到鼠标位置
    BLACK_HOLE = auto()        # 新增：黑洞 - 吸引并伤害敌人
    ICE_NOVA = auto()          # 新增：冰霜新星 - 冻结周围敌人
    CHAIN_LIGHTNING = auto()   # 新增：连锁闪电
    BERSERK = auto()           # 新增：狂暴 - 攻速翻倍，受到伤害增加
    PHANTOM_STRIKE = auto()    # 新增：幻影打击 - 分身攻击
    MEDIC_POD = auto()         # 新增：医疗舱 - 持续回血区域
    SHOCKWAVE = auto()         # 新增：冲击波 - 推开周围敌人
