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
    WEAPON_BOX = auto()   # 武器箱：随机一把武器
    TREASURE_CHEST = auto()  # 宝箱：多重奖励
    SKILL_SLOT = auto()   # 技能槽扩展：升级时多一个技能选项
    BUFF_CHARM = auto()   # 护符：随机获得一个正面buff
    INCENDIARY = auto()   # 燃烧弹：大范围持续燃烧区域
    SMOKE_GRENADE = auto()  # 烟雾弹：大范围烟雾减速致盲
    CLUSTER_BOMB = auto()  # 集束炸弹：爆炸后分裂多枚小炸弹
    EMP_GRENADE = auto()   # EMP脉冲：范围眩晕+破盾

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
    STORY_ARCHIVE = auto()  # 新增：剧情资料库
    MAP_TRANSITION = auto()  # 新增：地图切换过场

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
