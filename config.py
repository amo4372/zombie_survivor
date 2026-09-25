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

MAGENTA = (255, 0, 255)

# ========== 游戏难度完整配置 ==========
DIFFICULTY_CONFIG = {
    "简单": {
        "enemy_hp_mult": 0.7,
        "enemy_damage_mult": 0.7,
        "enemy_speed_mult": 0.9,
        "enemy_spawn_mult": 0.7,
        "player_hp_mult": 1.3,
        "player_damage_mult": 1.2,
        "drop_rate_mult": 1.5,
        "exp_mult": 1.3,
        "start_weapons": 1,  # 初始武器数量
        "description": "敌人较弱，资源丰富，适合新手",
    },
    "普通": {
        "enemy_hp_mult": 1.0,
        "enemy_damage_mult": 1.0,
        "enemy_speed_mult": 1.0,
        "enemy_spawn_mult": 1.0,
        "player_hp_mult": 1.0,
        "player_damage_mult": 1.0,
        "drop_rate_mult": 1.0,
        "exp_mult": 1.0,
        "start_weapons": 1,
        "description": "标准体验，平衡的挑战",
    },
    "困难": {
        "enemy_hp_mult": 1.5,
        "enemy_damage_mult": 1.4,
        "enemy_speed_mult": 1.1,
        "enemy_spawn_mult": 1.3,
        "player_hp_mult": 0.9,
        "player_damage_mult": 0.95,
        "drop_rate_mult": 0.8,
        "exp_mult": 1.2,
        "start_weapons": 1,
        "description": "敌人更强，资源稀缺，考验技巧",
    },
    "地狱": {
        "enemy_hp_mult": 2.2,
        "enemy_damage_mult": 1.8,
        "enemy_speed_mult": 1.2,
        "enemy_spawn_mult": 1.6,
        "player_hp_mult": 0.75,
        "player_damage_mult": 0.9,
        "drop_rate_mult": 0.6,
        "exp_mult": 1.5,
        "start_weapons": 1,
        "description": "极致挑战，敌人凶猛，步步惊心",
    },
}

DIFFICULTY_LIST = ["简单", "普通", "困难", "地狱"]
DIFFICULTY_WEIGHT = {"简单": 0.5, "普通": 1.0, "困难": 1.8, "地狱": 3.0}

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
    WEAPON_BOX = auto()   # 武器箱：随机一把武器
    TREASURE_CHEST = auto()  # 宝箱：多重奖励
    SKILL_SLOT = auto()   # 技能槽扩展：升级时多一个技能选项
    BUFF_CHARM = auto()   # 护符：随机获得一个正面buff
    INCENDIARY = auto()   # 燃烧弹：大范围持续燃烧区域
    SMOKE_GRENADE = auto()  # 烟雾弹：大范围烟雾减速致盲
    CLUSTER_BOMB = auto()  # 集束炸弹：爆炸后分裂多枚小炸弹
    EMP_GRENADE = auto()   # EMP脉冲：范围眩晕+破盾
    RUNE = auto()         # 符文：局内永久buff，从宝箱开出
    GOLDEN_CHEST = auto() # 黄金宝箱：必出符文+大量资源
    MYSTERY_BOX = auto()  # 神秘盒：随机效果（可能好可能坏）

class RuneType(Enum):
    FLAME = "flame"           # 火焰符文：攻击附带燃烧
    FROST = "frost"           # 冰霜符文：攻击附带减速
    POISON = "poison"         # 毒素符文：攻击附带中毒
    POWER = "power"           # 力量符文：伤害+15%
    VITALITY = "vitality"     # 生命符文：最大生命+30
    SWIFTNESS = "swiftness"   # 迅捷符文：移速+10%
    CRITICAL = "critical"     # 暴击符文：暴击率+10%
    VAMPIRE = "vampire"       # 吸血符文：生命偷取+5%
    GUARDIAN = "guardian"     # 守护符文：护甲+10
    FRENZY = "frenzy"         # 狂怒符文：攻速+15%
    THUNDER = "thunder"       # 雷电符文：攻击有几率连锁闪电
    REGEN = "regen"           # 再生符文：每秒回复2点生命
    LUCK = "luck"             # 幸运符文：掉落率+20%
    SHADOW = "shadow"         # 暗影符文：暴击伤害+50%
    TITAN = "titan"           # 泰坦符文：体型增大，近战范围+20%

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
    MODE_SELECT = auto()  # 新增：模式选择（故事/无尽）
    DIFFICULTY_SELECT = auto()  # 新增：难度选择页面
    STORY_ARCHIVE = auto()
    CODEX = auto()  # 新增：剧情资料库
    SKILL_TREE = auto()  # 新增：技能树界面
    MAP_TRANSITION = auto()  # 新增：地图切换过场
    TEXT_VIEWER = auto()  # 新增：可拾取文本查看界面
    MOD_MANAGER = auto()  # 新增：Mod管理页面
    UPDATE = auto()  # 新增：自动更新页面
    UPDATE_NOTES = auto()  # 新增：更新说明/版本详情页面


class ControlMode(Enum):
    KEYBOARD = auto()
    TOUCH = auto()

class GameMode(Enum):
    TIMED = auto()
    ENDLESS = auto()
    STORY = auto()  # 新增：故事模式

class MapType(Enum):
    SCHOOL = auto()        # 学校（第一章）
    STREET = auto()        # 街区（第二章）
    DOWNTOWN = auto()      # 城市中心区（第三章）
    SUBURB = auto()        # 郊区（第四章）
    NUCLEAR_PLANT = auto() # 核电站（第五章）

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
    # === 新Boss ===
    BOSS_MUTANT = auto()      # 变异体Boss - 高伤害连招
    BOSS_QUEEN = auto()       # 尸潮女王 - 召唤+控制
    BOSS_TITAN = auto()       # 泰坦 - 巨型坦克Boss
    # === 精英怪 ===
    ELITE_BRUTE = auto()      # 精英蛮兵 - 高血量重击
    ELITE_ASSASSIN = auto()   # 精英刺客 - 高速高爆
    ELITE_SORCERER = auto()   # 精英术士 - 远程法术
    ELITE_GUARDIAN = auto()   # 精英守卫 - 护盾+治疗
    # === 新普通僵尸 ===
    ZOMBIE_SPITTER = auto()   # 吐酸僵尸 - 远程酸液
    ZOMBIE_LEAPER = auto()    # 跳跃僵尸 - 远距离扑击
    ZOMBIE_CORPSE_EATER = auto() # 食尸者 - 吞噬尸体变强
    ZOMBIE_WRAITH = auto()    # 怨灵 - 穿墙+恐惧
    # === 新增僵尸类型 ===
    ZOMBIE_BOMBER = auto()       # 爆破手 - 投掷炸弹
    ZOMBIE_FROST = auto()        # 冰霜僵尸 - 减速攻击
    ZOMBIE_VENOM = auto()        # 剧毒僵尸 - 中毒DOT
    ZOMBIE_BERSERKER = auto()    # 狂暴僵尸 - 低血量加速
    ZOMBIE_GHOUL = auto()        # 食尸鬼 - 啃咬持续伤害
    ZOMBIE_SHAMAN = auto()       # 萨满僵尸 - 增益周围僵尸
    ZOMBIE_HUNTER = auto()       # 猎人僵尸 - 远程精准射击
    ZOMBIE_JUGGERNAUT = auto()   # 重甲僵尸 - 高护甲高血量

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
    SEMI_AUTO_SNIPER = auto()  # 连狙 - 半自动狙击，高射速高精度
    # 近战武器
    FISTS = auto()             # 拳头 - 基础近战，无限耐久
    KNIFE = auto()             # 匕首 - 快速近战，高暴击
    BAT = auto()               # 棒球棍 - 中速近战，击退效果
    CHAINSAW = auto()          # 电锯 - 持续伤害，高DPS
    # 手枪扩展
    REVOLVER = auto()          # 左轮手枪 - 高伤害，低射速
    DESERT_EAGLE = auto()      # 沙漠之鹰 - 超高伤害，低射速
    # 冲锋枪扩展
    SMG = auto()               # 冲锋枪 - 基础冲锋枪
    UMP45 = auto()             # UMP45 - 高伤害冲锋枪
    P90 = auto()               # P90 - 高射速大容量
    # 步枪扩展
    AK47 = auto()              # AK47 - 高伤害，后坐力大
    M4A1 = auto()              # M4A1 - 均衡步枪
    SCAR = auto()              # SCAR - 高精度步枪
    # 狙击枪扩展
    AWP = auto()               # AWP - 超高伤害狙击
    # 霰弹枪扩展
    AA12 = auto()              # AA12 - 全自动霰弹枪
    # 重武器扩展
    LMG = auto()               # 轻机枪 - 大容量，中等射速
    # 投掷物
    GRENADE = auto()           # 手雷 - 范围爆炸伤害
    MOLOTOV = auto()           # 燃烧瓶 - 持续燃烧区域
    SMOKE_GRENADE = auto()     # 烟雾弹 - 减速视野内敌人


# ========== 故事模式地图配置 ==========
MAP_CONFIGS = {
    MapType.SCHOOL: {
        "name": "沦陷的校园",
        "chapter": "第一章",
        "description": "病毒最初爆发的地方。曾经的书声琅琅，如今只剩丧尸的嘶吼。",
        "time_limit": 1200,  # 20分钟（秒）
        "bg_color": (25, 25, 30),
        "obstacle_types": ["desk", "chair", "podium", "blackboard", "bookshelf", "locker",
                           "basketball_hoop", "pingpong_table", "water_dispenser", "trash_bin",
                           "flower_bed", "school_bus", "fence", "wall", "barricade", "pillar", "debris_pile"],
        "enemy_weights": {
            EnemyType.ZOMBIE_NORMAL: 50, EnemyType.ZOMBIE_FAST: 20, EnemyType.ZOMBIE_RANGED: 10,
            EnemyType.ZOMBIE_TANK: 5, EnemyType.ZOMBIE_CRAWLER: 8, EnemyType.ZOMBIE_EXPLODER: 4,
            EnemyType.ZOMBIE_SPLITTER: 3,
            EnemyType.ZOMBIE_SPITTER: 5, EnemyType.ZOMBIE_LEAPER: 4, EnemyType.ZOMBIE_WRAITH: 2,
        },
        "weapon_pool": [WeaponType.PISTOL, WeaponType.RIFLE, WeaponType.SHOTGUN, WeaponType.CROSSBOW],
        "boss_type": EnemyType.BOSS_LONG,
        "boss_spawn_minute": 15,
        "special_event": "school_evacuation",  # 14分钟后从室内转场室外
        "difficulty_mult": 1.0,
    },
    MapType.STREET: {
        "name": "死寂的街区",
        "chapter": "第二章",
        "description": "逃离校园后，你来到了熟悉的街区。每一扇窗户后都可能藏着危险。",
        "time_limit": 1200,
        "bg_color": (20, 22, 28),
        "obstacle_types": ["car", "bus_stop", "streetlight", "mailbox", "fire_hydrant", "bench",
                           "trash_bin", "fence", "wall", "barricade", "pillar", "debris_pile",
                           "shopping_cart", "vending_machine", "dumpster"],
        "enemy_weights": {
            EnemyType.ZOMBIE_NORMAL: 40, EnemyType.ZOMBIE_FAST: 22, EnemyType.ZOMBIE_RANGED: 15,
            EnemyType.ZOMBIE_TANK: 8, EnemyType.ZOMBIE_CRAWLER: 5, EnemyType.ZOMBIE_EXPLODER: 5,
            EnemyType.ZOMBIE_SPLITTER: 3, EnemyType.ZOMBIE_SHIELD: 2,
            EnemyType.ZOMBIE_SPITTER: 4, EnemyType.ZOMBIE_LEAPER: 3, EnemyType.ZOMBIE_CORPSE_EATER: 2,
            EnemyType.ELITE_BRUTE: 1, EnemyType.ELITE_ASSASSIN: 1,
        },
        "weapon_pool": [WeaponType.RIFLE, WeaponType.SHOTGUN, WeaponType.MACHINE_GUN, WeaponType.GRENADE_LAUNCHER, WeaponType.CROSSBOW, WeaponType.SEMI_AUTO_SNIPER],
        "boss_type": EnemyType.BOSS_XIANG,
        "boss_spawn_minute": 15,
        "special_event": "street_blackout",  # 12分钟后停电，视野缩小
        "difficulty_mult": 1.2,
    },
    MapType.DOWNTOWN: {
        "name": "燃烧的市中心",
        "chapter": "第三章",
        "description": "城市中心已经完全沦陷。军方的抵抗化为废墟，火光映红了整片天空。",
        "time_limit": 1200,
        "bg_color": (38, 18, 14),  # 市中心 - 火光橙红
        "obstacle_types": ["car", "bus", "truck", "barricade", "wall", "pillar", "debris_pile",
                           "checkpoint", "sandbag", "wrecked_tank", "burning_car", "billboard",
                           "bus_stop", "streetlight", "bench"],
        "enemy_weights": {
            EnemyType.ZOMBIE_NORMAL: 25, EnemyType.ZOMBIE_FAST: 18, EnemyType.ZOMBIE_RANGED: 15,
            EnemyType.ZOMBIE_TANK: 8, EnemyType.ZOMBIE_EXPLODER: 7, EnemyType.ZOMBIE_SPLITTER: 5,
            EnemyType.ZOMBIE_SHIELD: 4, EnemyType.ZOMBIE_HEALER: 2, EnemyType.ZOMBIE_PHANTOM: 2,
            EnemyType.ZOMBIE_SPITTER: 4, EnemyType.ZOMBIE_LEAPER: 3, EnemyType.ZOMBIE_WRAITH: 3,
            EnemyType.ELITE_BRUTE: 2, EnemyType.ELITE_SORCERER: 2,
        },
        "weapon_pool": [WeaponType.MACHINE_GUN, WeaponType.ROCKET_LAUNCHER, WeaponType.FLAMETHROWER,
                        WeaponType.GRENADE_LAUNCHER, WeaponType.SHOTGUN, WeaponType.DOUBLE_BARREL,
                        WeaponType.SEMI_AUTO_SNIPER],
        "boss_type": EnemyType.BOSS_MUTANT,
        "boss_spawn_minute": 14,
        "special_event": "downtown_airstrike",  # 10分钟后军方空袭，随机爆炸
        "difficulty_mult": 1.4,
    },
    MapType.SUBURB: {
        "name": "荒芜的郊区",
        "chapter": "第四章",
        "description": "远离城市的郊区本应是避难所，但变异的生物让这里比城市更加凶险。",
        "time_limit": 1200,
        "bg_color": (18, 30, 18),  # 郊区 - 幽暗墨绿
        "obstacle_types": ["house", "shed", "fence", "tree", "bush", "well", "haystack",
                           "tractor", "water_tower", "barricade", "wall", "debris_pile", "pillar",
                           "trash_bin", "bench"],
        "enemy_weights": {
            EnemyType.ZOMBIE_NORMAL: 20, EnemyType.ZOMBIE_FAST: 15, EnemyType.ZOMBIE_RANGED: 10,
            EnemyType.ZOMBIE_TANK: 10, EnemyType.ZOMBIE_CRAWLER: 8, EnemyType.ZOMBIE_EXPLODER: 7,
            EnemyType.ZOMBIE_SPLITTER: 5, EnemyType.ZOMBIE_SHIELD: 4, EnemyType.ZOMBIE_HEALER: 3,
            EnemyType.ZOMBIE_PHANTOM: 2, EnemyType.ZOMBIE_CORPSE_EATER: 5, EnemyType.ZOMBIE_WRAITH: 4,
            EnemyType.ELITE_ASSASSIN: 2, EnemyType.ELITE_GUARDIAN: 2,
        },
        "weapon_pool": [WeaponType.SNIPER, WeaponType.RIFLE, WeaponType.SHOTGUN, WeaponType.FLAMETHROWER,
                        WeaponType.CROSSBOW, WeaponType.MINIGUN, WeaponType.SEMI_AUTO_SNIPER],
        "boss_type": EnemyType.BOSS_QUEEN,
        "boss_spawn_minute": 14,
        "special_event": "suburb_mutation",  # 8分钟后变异体大量出现
        "difficulty_mult": 1.6,
    },
    MapType.NUCLEAR_PLANT: {
        "name": "深渊核电站",
        "chapter": "第五章 - 终章",
        "description": "病毒的源头就在这座核电站的深处。最后的真相，与最后的战斗，都在这里。",
        "time_limit": 1200,
        "bg_color": (12, 14, 35),  # 核电站 - 深紫辐射
        "obstacle_types": ["reactor", "pipe", "control_panel", "barrel", "crate", "barricade",
                           "wall", "pillar", "debris_pile", "generator", "cooling_tower",
                           "radiation_barrier", "terminal", "server_rack"],
        "enemy_weights": {
            EnemyType.ZOMBIE_NORMAL: 15, EnemyType.ZOMBIE_FAST: 12, EnemyType.ZOMBIE_RANGED: 12,
            EnemyType.ZOMBIE_TANK: 10, EnemyType.ZOMBIE_EXPLODER: 8, EnemyType.ZOMBIE_SPLITTER: 7,
            EnemyType.ZOMBIE_SHIELD: 5, EnemyType.ZOMBIE_HEALER: 4, EnemyType.ZOMBIE_PHANTOM: 5,
            EnemyType.ZOMBIE_CRAWLER: 4, EnemyType.ZOMBIE_SPITTER: 5, EnemyType.ZOMBIE_WRAITH: 5,
            EnemyType.ELITE_BRUTE: 3, EnemyType.ELITE_ASSASSIN: 2, EnemyType.ELITE_SORCERER: 2, EnemyType.ELITE_GUARDIAN: 1,
        },
        "weapon_pool": [WeaponType.PLASMA_RIFLE, WeaponType.RAILGUN, WeaponType.ROCKET_LAUNCHER,
                        WeaponType.MINIGUN, WeaponType.FLAMETHROWER, WeaponType.GRENADE_LAUNCHER],
        "boss_type": EnemyType.BOSS_TITAN,  # 最终Boss：泰坦"
        "boss_spawn_minute": 12,
        "special_event": "nuclear_meltdown",  # 6分钟后堆芯熔毁，辐射区扩散
        "difficulty_mult": 2.0,
    },
}

# 故事模式地图顺序
STORY_MAP_ORDER = [MapType.SCHOOL, MapType.STREET, MapType.DOWNTOWN, MapType.SUBURB, MapType.NUCLEAR_PLANT]

# ========== 剧情文本资料（游戏中可收集） ==========
# 每条：id, 地图, 刷新时间(分钟), 标题, 内容
STORY_FRAGMENTS = {
    MapType.SCHOOL: [
        {"id": "school_1", "spawn_minute": 2, "title": "学生日记 - 9月3日",
         "content": "今天学校突然封校了，说是有传染病。医务室那边传来奇怪的声音，\n老师不让我们靠近。同桌说他看到有人在走廊里咬人......我觉得他在开玩笑。"},
        {"id": "school_2", "spawn_minute": 6, "title": "广播稿残片",
         "content": "......全体师生注意，请立即前往体育馆集合。不要靠近一楼实验室......\n（杂音）......它们进来了！快跑！不要----"},
        {"id": "school_3", "spawn_minute": 10, "title": "实验室记录",
         "content": "项目代号：'夜枭'。实验体对新型病毒表现出异常的耐受性，\n但脑功能出现不可逆退化。上级要求加快实验进度，安全规范被搁置了。\n我有一种不好的预感......"},
        {"id": "school_4", "spawn_minute": 16, "title": "幸存者字条",
         "content": "如果你看到这个，说明你还活着。体育馆已经失守了，\n我看到校长......他变了。往南门跑，街区那边可能还有军队的人。\n祝你好运，陌生人。"},
        {"id": "school_5", "spawn_minute": 3, "title": "化学老师的备课笔记",
         "content": "第三节课的实验取消了。实验室被校方封锁，说是设备检修。\n但我路过时闻到了一股甜腻的气味，像是腐烂的水果？\n校长亲自带人守在门口，这不正常。"},
        {"id": "school_6", "spawn_minute": 5, "title": "校医室处方单",
         "content": "患者：高三(2)班李某。症状：高热40度、瞳孔扩散、肌肉痉挛。\n处方：转上级医院。备注：患者咬伤了两名护士，已报警。\n时间：爆发前12小时。"},
        {"id": "school_7", "spawn_minute": 8, "title": "食堂采购清单",
         "content": "本周采购：大米500kg、面粉200kg、肉类150kg、蔬菜300kg。\n备注：肉类供应商延迟交货，理由是屠宰场出事了。\n爆发后第3天，食堂成为临时避难所，后被攻破。"},
        {"id": "school_8", "spawn_minute": 12, "title": "保安巡逻记录",
         "content": "22:00 一切正常。23:30 教学楼B区有异响，前往查看。\n00:15 发现生物老师张某在啃食......（字迹潦草）\n00:45 对讲机呼叫增援，无人回应。这是最后一条记录。"},
        {"id": "school_9", "spawn_minute": 15, "title": "学生手机备忘录",
         "content": "妈妈，学校出事了。大家都在跑，有人在咬人。\n我躲在图书馆的储物间里，手机快没电了。\n如果我没回来，不要来找我。我爱你。"},
        {"id": "school_10", "spawn_minute": 18, "title": "校长办公室文件",
         "content": "关于夜枭计划合作协议：本校提供实验室场地，\n方舟生物科技提供研究资金。协议要求校方对实验内容保密。\n签字：校长王某。日期：爆发前6个月。"},
        {"id": "school_11", "spawn_minute": 20, "title": "体育馆避难须知",
         "content": "1.保持安静，感染者对声音敏感。2.门窗已用课桌封堵。\n3.食物和水按人头分配，每日两次。4.如有人员受伤，立即隔离。\n（底部红笔：第3条已失效。）"},
        {"id": "school_12", "spawn_minute": 22, "title": "图书馆借阅卡",
         "content": "持卡人：图书管理员周某。最后借阅：《病毒学导论》。\n卡背面：第7章第3节，逆转录病毒的基因整合机制。\n如果它们的DNA能整合到人类基因组，那疫苗就不可能了。"},
        {"id": "school_13", "spawn_minute": 25, "title": "美术教室画作",
         "content": "一幅未完成的油画，画的是校园全景。\n但天空被涂成暗红色，教学楼窗户里伸出无数只手。\n画框背面：我看到了未来。它们会来的。"},
        {"id": "school_14", "spawn_minute": 28, "title": "电脑教室U盘文件",
         "content": "文件名：紧急疏散方案v3.docx。\n鉴于校内出现不明暴力事件，启动三级响应。\n所有师生前往体育馆集合。（文件从未被打开过。）"},
        {"id": "school_15", "spawn_minute": 30, "title": "天台门锁钥匙",
         "content": "一串生锈的钥匙，铭牌：天台-仅限紧急情况。\n纸条：从这里可以看到整个城市。\n那天晚上，我看到远处的火光连成了一片。"},
        {"id": "school_16", "spawn_minute": 33, "title": "音乐教室乐谱",
         "content": "贝多芬《月光奏鸣曲》第三乐章。\n谱子上用红笔标注了大量表情记号，最后一页：\n在地狱里也要演奏。音乐是最后的文明。"},
        {"id": "school_17", "spawn_minute": 36, "title": "物理实验室报告",
         "content": "实验：声波对感染体行为的影响。\n结论：25-30Hz次声波可使感染体狂暴，15kHz以上超声波可短暂驱散。\n建议：开发声波武器。（报告被血渍覆盖一半）"},
        {"id": "school_18", "spawn_minute": 40, "title": "宿舍楼层长日志",
         "content": "第1天：3楼有人发烧，已上报。\n第2天：3楼的人开始攻击室友，楼层长被咬伤。\n第3天：整栋宿舍楼沦陷，我是唯一逃出来的。第4天：我开始发烧了。"},
        {"id": "school_19", "spawn_minute": 45, "title": "方舟计划招募海报",
         "content": "加入方舟计划，成为人类文明的火种。\n我们需要：科学家、医生、工程师、农业专家。\n待遇：地下避难所永久居住权。（海报被撕毁，背面写着：骗局）"},
        {"id": "school_20", "spawn_minute": 50, "title": "校史馆旧照片",
         "content": "一张建校50周年合影，照片背面写着所有教职工的名字。\n其中一个名字被红圈标注：陈某，生物教师，1998年入职。\n旁边小字：他就是后来的Dr.陈。"},
    ],
    MapType.STREET: [
        {"id": "street_1", "spawn_minute": 2, "title": "便利店收银条",
         "content": "购买时间：爆发后第6小时。商品：矿泉水x12、罐头x8、打火机x3。\n收银员已经不在了，我自己拿的。如果店主还活着，对不起。"},
        {"id": "street_2", "spawn_minute": 7, "title": "警方通讯记录",
         "content": "各单位注意，市区出现大规模暴力事件，嫌疑人表现出......非人特征。\n允许使用致命武器。请求军方支援......（通讯中断）"},
        {"id": "street_3", "spawn_minute": 12, "title": "孩子的画",
         "content": "画纸上用蜡笔画着一家三口，旁边歪歪扭扭写着：\n'爸爸妈妈睡着了，叫不醒。我在等他们醒来。'\n画的角落有暗红色的手印。"},
        {"id": "street_4", "spawn_minute": 17, "title": "医生的便签",
         "content": "病毒通过体液传播，感染后10-30分钟内发病。\n初期症状：发热、攻击性增强、瞳孔扩散。目前无治愈手段。\n唯一的建议：跑得比它们快。"},
        {"id": "street_5", "spawn_minute": 3, "title": "快递员的最后一单",
         "content": "收件地址：幸福小区3栋2单元501。包裹：医用口罩x200。\n客户说不管多少钱都要送到。\n我到的时候门开着，屋里没人，电视还在放新闻。"},
        {"id": "street_6", "spawn_minute": 5, "title": "加油站价目表",
         "content": "92号汽油：8.52→15→50→缺货。95号：9.23→20→缺货。\n柴油：8.12→30→缺货。\n（最后一行：现金也没用了，要换水和食物。）"},
        {"id": "street_7", "spawn_minute": 8, "title": "药店销售记录",
         "content": "爆发前24小时：退烧药300盒、抗生素150盒、消毒液80瓶。\n口罩全部售罄。\n爆发后：药店被洗劫一空。"},
        {"id": "street_8", "spawn_minute": 11, "title": "出租车司机电台录音",
         "content": "总台，我在中山路，这里全是......人？不，不是人。\n它们在追一个老太太，我开车冲过去了。\n它们的骨头碎了，但还在爬。我要离开这座城市。"},
        {"id": "street_9", "spawn_minute": 14, "title": "银行ATM凭条",
         "content": "交易时间：爆发后第5小时。取款：20000元（限额）。\n余额：156789.32元。\n（背面：钱有什么用？连一瓶水都买不到。）"},
        {"id": "street_10", "spawn_minute": 17, "title": "理发店会员卡",
         "content": "店名：潮流造型。会员：李某。余额：580元。\n背面：老板第一个变的，他咬了正在烫头的顾客。\n烫发器还开着，整个店都是焦糊味。"},
        {"id": "street_11", "spawn_minute": 20, "title": "社区公告栏通知",
         "content": "即日起封闭式管理，每户每两天可派一人外出采购。\n请配合志愿者工作，不信谣不传谣。\n（通知被撕一半，下面：志愿者都跑了。）"},
        {"id": "street_12", "spawn_minute": 23, "title": "外卖骑手保温箱",
         "content": "保温箱里还有一份没送出的黄焖鸡米饭。\n便签：第47单，送达超时。客户电话无人接听。\n我在楼下喊了半天，只有一个东西探出头来。"},
        {"id": "street_13", "spawn_minute": 26, "title": "修车铺工具清单",
         "content": "扳手x12、螺丝刀x8、千斤顶x2、电焊机x1、\n防刺手套x3、消防斧x1、弩箭x20（自制）。\n（老板说：这些工具现在比车值钱。）"},
        {"id": "street_14", "spawn_minute": 29, "title": "宠物店寄养协议",
         "content": "寄养宠物：金毛犬旺财。主人：张某。\n寄养时间：爆发前1天，预计3天。主人至今未取回。\n（背面：旺财很乖，它好像知道主人不会回来了。）"},
        {"id": "street_15", "spawn_minute": 32, "title": "报刊亭杂志",
         "content": "封面：城市突发公共卫生事件，专家：可防可控。\n出版日期：爆发当天。\n杂志垫在一个死去的感染者头下，他手里还攥着《末日生存手册》。"},
        {"id": "street_16", "spawn_minute": 35, "title": "公交司机行车日志",
         "content": "6:00首班车正常。8:30堵车，有人拍门。\n9:15一个乘客突然咬了旁边的人。\n9:20我打开车门让所有人下车，9:25锁门再也没打开过。"},
        {"id": "street_17", "spawn_minute": 38, "title": "洗衣店取衣凭证",
         "content": "客户：王女士。衣物：羽绒服x1、西装x1。\n取衣日期：爆发后第3天。\n（背面：我来取衣服时，洗衣机还在转，里面的衣服已被血染红。）"},
        {"id": "street_18", "spawn_minute": 42, "title": "废品收购站账本",
         "content": "爆发后：矿泉水瓶0.1→5元/个（装满水的），\n废铁0.8→50元/kg（可做武器的），旧书不收。\n（老板注：世道变了，垃圾也能救命。）"},
        {"id": "street_19", "spawn_minute": 46, "title": "血商名片",
         "content": "专业收购：未感染者血液、疫苗样本、抗病毒药物。\n价格公道，童叟无欺。联系人：血手。\n（名片背面：我们不生产希望，我们只是希望的搬运工。）"},
        {"id": "street_20", "spawn_minute": 50, "title": "观察者涂鸦",
         "content": "墙上用喷漆画着一只眼睛，下面写着：\n我们看着你。你不是一个人在战斗。\n但我们不会帮你。你的挣扎，就是我们的记录。"},
    ],
    MapType.DOWNTOWN: [
        {"id": "downtown_1", "spawn_minute": 2, "title": "军方作战命令",
         "content": "代号：'净化'。目标：清除市中心区域感染体。\n授权使用重武器。注意：平民已全部撤离（？）。\n指挥官签字处被血迹覆盖。"},
        {"id": "downtown_2", "spawn_minute": 6, "title": "新闻主播手稿",
         "content": "各位观众，现在是紧急插播。本市爆发的不明疫情已被证实为......\n（停顿）......政府建议市民留在家中，不要外出。\n重复，不要外出。它们对声音很敏感。"},
        {"id": "downtown_3", "spawn_minute": 11, "title": "黑客解密文件",
         "content": "我黑进了市政府的服务器。病毒不是意外，是从'那个地方'泄露出来的。\n城北的核电站一直在进行非法生物实验。\n如果你还活着，去那里。也许能找到答案，或者......解药。"},
        {"id": "downtown_4", "spawn_minute": 16, "title": "士兵的家书",
         "content": "妈，我在市中心。情况比新闻里说的严重得多。\n我们的子弹快用完了，增援一直没来。\n如果我没回去，告诉爸，我尽力了。\n另外，别相信官方说的'已控制'。"},
            {"id": "downtown_5", "spawn_minute": 3, "title": "市政府新闻通稿",
         "content": "我市出现的聚集性疫情已得到有效控制。\n请市民保持冷静，配合防疫工作。物资供应充足。\n（签发时间：爆发后第6小时。此时市中心已陷入混乱。）"},
        {"id": "downtown_6", "spawn_minute": 5, "title": "商场楼层导览图",
         "content": "B1超市（已洗劫）、1F化妆品（玻璃全碎）、\n2F女装（衣架散落）、3F男装（试衣间有感染者）、\n4F餐饮（后厨有罐头）、5F电影院（12人避难，食物撑5天）。"},
        {"id": "downtown_7", "spawn_minute": 8, "title": "医院急诊记录",
         "content": "00:00-06:00接诊127例。06:00-12:00接诊342例，医护开始感染。\n12:00-18:00医院失守，人员撤至顶楼。\n18:00最后一架直升机起飞。（记录者未登机。）"},
        {"id": "downtown_8", "spawn_minute": 11, "title": "银行金库门禁卡",
         "content": "持卡人：金库管理员。权限：B级。\n背面：金库里有三千万现金和两百公斤黄金。\n但最值钱的是隔壁储藏室的两百箱矿泉水。钱，就是纸。"},
        {"id": "downtown_9", "spawn_minute": 14, "title": "写字楼公司铭牌",
         "content": "方舟生物科技有限公司 28F。\n铭牌被斧头劈了好几下，沾着干涸血迹。\n墙上喷漆：是他们造的病毒！血债血偿！"},
        {"id": "downtown_10", "spawn_minute": 17, "title": "酒店房卡",
         "content": "房间：1808行政套房。\n便签：1808保险柜密码0818，里面有一把手枪和五十发子弹。\n用它们保护自己。——酒店保安队长"},
        {"id": "downtown_11", "spawn_minute": 20, "title": "地铁站台广播稿",
         "content": "各位乘客，由于系统故障，本次列车不停靠本站。\n请不要靠近站台边缘。\n（广播重复三天直到电力中断。站台上堆满感染者尸体。）"},
        {"id": "downtown_12", "spawn_minute": 23, "title": "律师事务所合同",
         "content": "甲方：方舟生物科技。乙方：某律师事务所。\n内容：处理意外事故法律事务，保密费500万。\n（合同从未执行——爆发后双方都死了。）"},
        {"id": "downtown_13", "spawn_minute": 26, "title": "保险公司理赔申请",
         "content": "申请人：李某。类型：意外伤害险。\n事故：被不明人员咬伤，正在医院治疗。\n（申请日期：爆发后第1天。保险公司第3天宣布破产。）"},
        {"id": "downtown_14", "spawn_minute": 29, "title": "电视台演播室脚本",
         "content": "主持人：连线前方记者。记者：我在市中心......\n（尖叫声）它们冲过来了！——（信号中断）\n（本市最后一次电视直播。）"},
        {"id": "downtown_15", "spawn_minute": 32, "title": "停车场缴费单",
         "content": "入场时间：爆发前2小时。停车费：0元（系统瘫痪）。\n背面：我的车还在B2层，但我不可能回去取了。\nB2层全是它们。"},
        {"id": "downtown_16", "spawn_minute": 35, "title": "咖啡馆菜单",
         "content": "美式28、拿铁32、摩卡35。\n末日特供：罐装咖啡100元/罐，最后3罐。\n不还价，不找零，只收矿泉水和子弹。"},
        {"id": "downtown_17", "spawn_minute": 38, "title": "图书馆借阅记录",
         "content": "《传染病学》借出12本，《野外生存指南》借出8本，\n《枪械组装与维护》借出5本，《刑法》借出0本。\n（爆发后第7天，图书馆被改造成堡垒。）"},
        {"id": "downtown_18", "spawn_minute": 42, "title": "快递分拣中心标签",
         "content": "目的地：全市各网点。状态：滞留。\n包裹：口罩、消毒液、药品、食品。\n（这些包裹足够救一万人，但分拣中心第2天沦陷。）"},
        {"id": "downtown_19", "spawn_minute": 46, "title": "神秘组织传单",
         "content": "观察者组织：我们不参与，只记录。\n我们知道病毒的起源、传播、变异。\n真相会让幸存者失去希望，所以我们选择沉默。"},
        {"id": "downtown_20", "spawn_minute": 50, "title": "疫苗研究中心门牌",
         "content": "市疾控中心病毒研究所。\n门牌被砸烂，地上散落着研究文件。\n一份文件残片：实验3号疫苗对A型病毒有效率67%，但对变异型无效。"},
],
    MapType.SUBURB: [
        {"id": "suburb_1", "spawn_minute": 2, "title": "农场主日志",
         "content": "城里的人往乡下跑，带来了那个病。\n我的牛开始发疯，撞坏了栅栏。我不得不开枪打死它们。\n这不是普通的病毒，连动物都被感染了。"},
        {"id": "suburb_2", "spawn_minute": 6, "title": "变异研究笔记",
         "content": "郊区的感染体出现了变异！有的体型变大，有的能隐身，\n还有的会喷出腐蚀性液体。病毒在适应环境，进化速度惊人。\n按照这个趋势，人类的时间不多了。"},
        {"id": "suburb_3", "spawn_minute": 11, "title": "避难所告示",
         "content": "本避难所已关闭。原因：内部出现感染。\n幸存者最后一次通讯是三天前。\n请勿靠近，请勿靠近，请勿靠近。"},
        {"id": "suburb_4", "spawn_minute": 16, "title": "神秘录音文字稿",
         "content": "......核电站......0号实验体......是一切的源头......\n它还活着，在反应堆深处。只有摧毁它，才能结束这一切。\n......我是项目的首席科学家，我罪孽深重......"},
        {"id": "suburb_5", "spawn_minute": 3, "title": "农家乐菜单",
         "content": "土鸡炖蘑菇68、烤全羊680、农家野菜28、自酿米酒30/斤。\n背面：爆发后农家乐成了避难所。\n老板说：院子有围墙，厨房有刀，地窖有粮。"},
        {"id": "suburb_6", "spawn_minute": 6, "title": "养殖场防疫记录",
         "content": "第1天：猪群异常躁动。第2天：3头猪死亡，死状怪异。\n第3天：死猪复活，攻击其他猪。第4天：全场扑杀焚烧。\n（记录者：兽医，扑杀过程中被咬伤。）"},
        {"id": "suburb_7", "spawn_minute": 9, "title": "果园主日记",
         "content": "城里的人逃到乡下，带来了病。\n我的果园被抢了，苹果被摘光，果树被砍了当柴烧。\n我藏在地窖里。有时候，活人比感染者更可怕。"},
        {"id": "suburb_8", "spawn_minute": 12, "title": "小学教师教案",
         "content": "课题：如何在灾难中保护自己。\n目标：1.基本生存技能。2.辨别危险。3.求救信号。\n（爆发前一周的教案。老师在爆发后第一天感染了。）"},
        {"id": "suburb_9", "spawn_minute": 15, "title": "村民联防队名单",
         "content": "队长：老周（退伍军人）。队员：12人。\n装备：猎枪x2、砍刀x5、农具若干。防线：村口路障+瞭望塔。\n（第7天防线被突破。12人，活下来2个。）"},
        {"id": "suburb_10", "spawn_minute": 18, "title": "养蜂人笔记",
         "content": "我的蜜蜂不对劲，不再采蜜，聚集在蜂箱门口防御。\n感染者从不靠近我的蜂场。\n也许蜂毒里有什么能抑制病毒？我被蜇了几十次，但还活着。"},
        {"id": "suburb_11", "spawn_minute": 21, "title": "渔民用渔网",
         "content": "破旧渔网，网眼里卡着感染者碎布。\n杆上刻字：这张网救过我的命。感染者掉进水里就不动了。\n但水里的东西......更可怕。"},
        {"id": "suburb_12", "spawn_minute": 24, "title": "气象站观测记录",
         "content": "第10天：气温异常升高3度。第20天：红色雾霾，能见度50米。\n第30天：酸雨，PH3.2。\n（环境在恶化，也许不只是病毒的问题。）"},
        {"id": "suburb_13", "spawn_minute": 27, "title": "教堂礼拜单",
         "content": "主题：末日审判。经文：启示录第6章。\n牧师在讲道时被感染的教友袭击。\n他临死前说：上帝不会救我们，我们只能自救。"},
        {"id": "suburb_14", "spawn_minute": 30, "title": "狩猎许可证",
         "content": "猎人：赵某。许可：野猪、野兔。有效期：2027全年。\n背面：现在猎什么都合法了。\n我猎过野猪、鹿，也猎过感染者。它们比野猪危险，但肉不能吃。"},
        {"id": "suburb_15", "spawn_minute": 33, "title": "水库管理日志",
         "content": "第1天：水质正常。第5天：检测到异常蛋白质。\n第10天：停止供水。第15天：水库周围出现大量感染者在喝水。\n（它们喝水，说明还有生理需求。它们还活着，只是变了。）"},
        {"id": "suburb_16", "spawn_minute": 36, "title": "废品站老板藏宝图",
         "content": "手绘地图：★加油站（柴油）★卫生院（药品）\n★超市仓库（罐头）★派出所（枪）★养鸡场（活鸡）。\n（这些地方我都去过了，能不能活着回来看你本事。）"},
        {"id": "suburb_17", "spawn_minute": 40, "title": "变异体观察报告",
         "content": "郊区发现新型变异体：体型较普通感染者小，\n但四肢修长，能在墙壁上爬行。夜间活动，对光敏感。\n暂命名为爬行者。危险等级：高。"},
        {"id": "suburb_18", "spawn_minute": 44, "title": "生存指南手抄本",
         "content": "六大生存技能：1.水源净化（煮沸+过滤）。2.食物保存（腌制/烟熏）。\n3.基础医疗（止血/包扎/抗生素使用）。4.自卫格斗。\n5.信号通讯。6.心理调节。（抄本作者：未知，已死亡。）"},
        {"id": "suburb_19", "spawn_minute": 48, "title": "农夫的遗书",
         "content": "我种了一辈子地，没想到最后种的是自己的坟。\n地窖里还有五十斤大米和二十斤腌肉。\n如果你看到这个，拿去用吧。别浪费。——老王"},
        {"id": "suburb_20", "spawn_minute": 52, "title": "神秘石碑拓片",
         "content": "石碑上刻着奇怪的符号，像是某种古老文字。\n拓片旁的笔记：这些符号与0号实验体身上的纹身一模一样。\n病毒不是人造的？它来自更古老的地方？"},
    ],
    MapType.NUCLEAR_PLANT: [
        {"id": "nuclear_1", "spawn_minute": 2, "title": "门禁记录",
         "content": "B7层实验室 - 最后出入记录：\nDr.陈 进入 03:17（未离开）\n安保队 进入 04:52（未离开）\n紧急封锁 05:01\n此后再无记录。"},
        {"id": "nuclear_2", "spawn_minute": 6, "title": "实验日志 - 最终篇",
         "content": "0号实验体挣脱了束缚。它比我们预想的强大得多。\n它能控制其他感染体，有一定的智能。\n我们创造了一个......神。或者说，一个魔鬼。\n反应堆的自毁密码是：7749。如果一切都失控了，就用它。"},
        {"id": "nuclear_3", "spawn_minute": 11, "title": "Dr.陈的遗书",
         "content": "我是这场灾难的罪魁祸首。\n'夜枭计划'的初衷是制造超级士兵，但病毒失控了。\n0号实验体就在反应堆核心室。它是母体，消灭它，病毒就会失去活性。\n我已经没有勇气面对它了。剩下的，交给你。"},
        {"id": "nuclear_4", "spawn_minute": 16, "title": "最终真相",
         "content": "你终于来到了这里。\n0号实验体曾经是一个人----我的儿子。\n我想用病毒治好他的绝症，但我失败了。\n现在，结束这一切吧。摧毁核心，连同他一起。\n这是我最后的请求。\n----Dr.陈"},
        {"id": "nuclear_5", "spawn_minute": 3, "title": "员工胸牌",
         "content": "姓名：Dr.陈。职位：首席科学家。部门：B7层特殊研究室。\n背面：我创造了它，也必须由我来毁灭它。\n7749，这是我儿子的生日。也是一切的终结。"},
        {"id": "nuclear_6", "spawn_minute": 5, "title": "辐射检测报告",
         "content": "B7层辐射值：0.12mSv/h（正常）。\n但检测到异常生物电信号，强度远超人类。\n0号实验体即使在休眠状态下，脑波也相当于清醒的人类。"},
        {"id": "nuclear_7", "spawn_minute": 8, "title": "安保队装备清单",
         "content": "手枪x4、霰弹枪x2、防弹衣x6、催泪弹x10、闪光弹x5。\n这些装备对付普通感染者足够，\n但对付0号实验体......子弹打光了，它还在走。"},
        {"id": "nuclear_8", "spawn_minute": 11, "title": "实验体观察日志",
         "content": "0号实验体X-001。第1天：注射后4小时心跳停止。\n第2天：死亡12小时后复活，极具攻击性。\n第7天：开始学习，能模仿研究员动作。第30天：学会说话，第一个词是妈妈。"},
        {"id": "nuclear_9", "spawn_minute": 14, "title": "反应堆操作手册",
         "content": "紧急停机：1.插入控制棒。2.启动冷却。3.关闭主阀。\n自毁程序：输入密码7749，10分钟倒计时。\n（红笔：不要轻易启动。方圆5公里将化为废墟。）"},
        {"id": "nuclear_10", "spawn_minute": 17, "title": "研究员辞职信",
         "content": "我申请辞职。我无法继续参与夜枭计划。\n0号实验体曾经是一个人，一个孩子。\n我们对它做的事情，比病毒更可怕。（辞职者在B7层被意外感染。）"},
        {"id": "nuclear_11", "spawn_minute": 20, "title": "通风系统图纸",
         "content": "B1-B7层通风管道分布图。\n红笔标注：从B7层通风管道可爬到地面，但管道狭窄。\nDr.陈的助手就是从这里逃出去的。"},
        {"id": "nuclear_12", "spawn_minute": 23, "title": "冷冻室库存清单",
         "content": "病毒样本：A型x20、B型x15、变异型x5。\n疫苗样本：实验1号x3（失败）、实验2号x3（失败）、实验3号x2（部分有效）。\n解毒剂原型：x1（未完成）。备用电源还能维持72小时。"},
        {"id": "nuclear_13", "spawn_minute": 26, "title": "通讯记录-最后通话",
         "content": "Dr.陈：它突破了最后一道防线。\n指挥中心：请求支援！Dr.陈：来不及了。\n它能控制其他感染体，在召唤它们。（低语）儿子，爸爸来陪你了。（通讯中断）"},
        {"id": "nuclear_14", "spawn_minute": 29, "title": "方舟计划内部文件",
         "content": "项目代号：方舟。目标：保存人类火种。\n挑选1000名精英进入地下避难所，等待地表恢复。\n预算：500亿。（边缘手写：方舟不是拯救人类，是让富人活下去。）"},
        {"id": "nuclear_15", "spawn_minute": 32, "title": "观察者组织传单",
         "content": "我们是观察者。我们不参与，只记录。\n我们记录了病毒的起源、传播、变异。\n真相会让幸存者失去希望。如果你看到这个，说明你被我们观察了。"},
        {"id": "nuclear_16", "spawn_minute": 35, "title": "血商交易记录",
         "content": "客户：匿名。商品：未感染者血液500ml。\n价格：100发子弹+3天食物。\n备注：未感染者血液能延缓感染——胡说八道。但有人愿意信，我们就卖。"},
        {"id": "nuclear_17", "spawn_minute": 38, "title": "疫苗研究进度报告",
         "content": "实验1号（灭活）：失败。实验2号（减毒）：失败，接种者变异。\n实验3号（mRNA）：部分有效，3人中1人产生抗体。\n疫苗研发需要6个月，但我们只有6天。——Dr.陈"},
        {"id": "nuclear_18", "spawn_minute": 42, "title": "变异体分类手册",
         "content": "7大类：1.行尸型（常见缓慢）2.迅捷型（极速）3.重装型（巨大）\n4.远程型（投掷/射击）5.特异型（爆炸/隐身/穿墙）\n6.变异型（二次变异）7.领袖型（0号衍生体，可指挥）。遇到第7类，跑。"},
        {"id": "nuclear_19", "spawn_minute": 46, "title": "0号实验体档案",
         "content": "姓名：陈小某。年龄：8岁。原身份：Dr.陈之子。\n病史：晚期脑癌，预计存活3个月。\n实验目的：使用改造病毒修复受损脑组织。结果：失控。\n（档案被Dr.陈亲手撕毁，这是残片。）"},
        {"id": "nuclear_20", "spawn_minute": 50, "title": "自毁控制室日志",
         "content": "最后进入者：未知。时间：爆发后第？天。\n自毁密码已被输入：7749。倒计时：10分钟。\n（日志最后一行：别了，世界。别了，我的儿子。——Dr.陈）"},
    ],
}


# 故事模式开场对话（按地图）
STORY_INTRO_DIALOGUE = {
    MapType.SCHOOL: [
        {"speaker": "???", "text": "头好痛......我在哪里？"},
        {"speaker": "你", "text": "（环顾四周）这是......学校？为什么这么安静？"},
        {"speaker": "???", "text": "走廊里有声音......有人在吗？"},
        {"speaker": "你", "text": "那不是人......快跑！"},
    ],
    MapType.STREET: [
        {"speaker": "你", "text": "终于从学校逃出来了......街区怎么也变成这样了？"},
        {"speaker": "广播", "text": "......全市进入紧急状态......请市民留在家中......"},
        {"speaker": "你", "text": "手机没信号了。得找到其他幸存者。"},
    ],
    MapType.DOWNTOWN: [
        {"speaker": "你", "text": "市中心......军队在这里交过火，但他们失败了。"},
        {"speaker": "你", "text": "这份解密文件说......病毒是从核电站泄露的？"},
        {"speaker": "你", "text": "不管真假，我得去看看。先穿过这片废墟。"},
    ],
    MapType.SUBURB: [
        {"speaker": "你", "text": "郊区的变异体更可怕了......病毒在进化。"},
        {"speaker": "你", "text": "那盘录音说核电站里有'0号实验体'，是一切的源头。"},
        {"speaker": "你", "text": "快到了。核电站就在前方。"},
    ],
    MapType.NUCLEAR_PLANT: [
        {"speaker": "你", "text": "这里就是......深渊。"},
        {"speaker": "广播", "text": "警告：反应堆异常。所有人员请立即撤离。"},
        {"speaker": "你", "text": "0号实验体就在下面。这一切，该结束了。"},
    ],
}

# 故事模式通关对话
STORY_ENDING_DIALOGUE = [
    {"speaker": "你", "text": "（按下自毁按钮）7749......结束了。"},
    {"speaker": "系统", "text": "反应堆自毁程序已启动。倒计时：10分钟。"},
    {"speaker": "你", "text": "（看着远处的火光） Dr.陈，你的儿子......安息吧。"},
    {"speaker": "旁白", "text": "核电站在巨大的爆炸中化为废墟。0号实验体被摧毁，病毒逐渐失去活性。"},
    {"speaker": "旁白", "text": "你从废墟中走出，阳光洒在脸上。这是灾难爆发以来，你第一次看到晴天。"},
    {"speaker": "旁白", "text": "世界已经满目疮痍，但希望，从未熄灭。"},
    {"speaker": "旁白", "text": "---- 丧尸幸存者 - 完 ----"},
]

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
    RELOAD_SPEED = auto()      # 新增：换弹速度 - 加快武器换弹
    ARMOR_UP = auto()          # 新增：护甲提升
    REGENERATION = auto()      # 新增：生命恢复
    DODGE_CHANCE = auto()      # 新增：闪避几率
    VAMPIRE_AURA = auto()      # 新增：吸血光环
    FORTRESS = auto()          # 新增：堡垒 - 静止时减伤
    # 近战专属技能
    MELEE_DAMAGE = auto()      # 近战伤害提升
    MELEE_RANGE = auto()       # 近战范围提升
    MELEE_SPEED = auto()       # 近战攻速提升
    MELEE_LIFESTEAL = auto()   # 近战吸血
    BERSERKER = auto()         # 狂暴 - 低血量增伤
    COMBO_MASTER = auto()      # 连击大师 - 连续攻击增伤

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
    # Buff相关技能
    FLAME_ENCHANT = auto()     # 火焰附魔 - 攻击几率施加燃烧
    FROST_ENCHANT = auto()     # 冰霜附魔 - 攻击几率施加减速
    POISON_ENCHANT = auto()    # 剧毒附魔 - 攻击几率施加中毒
    BLOODLUST = auto()         # 嗜血 - 击杀后获得加速buff
    WAR_CRY = auto()           # 战吼 - 主动获得多重正面buff
    PURIFY = auto()            # 净化 - 清除debuff并短暂无敌
    ELEMENTAL_MASTERY = auto() # 元素精通 - 增强debuff效果
    ADRENALINE = auto()        # 肾上腺素 - 装备防爆套装时体力上限和回复提升
