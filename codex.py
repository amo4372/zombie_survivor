import os
import json
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图鉴系统模块 - 怪物图鉴和武器图鉴"""

# ============================================================
# 怪物图鉴数据
# ============================================================
MONSTER_CODEX = {
    # === 基础僵尸 ===
    "ZOMBIE_NORMAL": {
        "name": "普通僵尸",
        "category": "基础",
        "description": "最常见的感染者，行动缓慢但数量众多。它们是病毒初期感染的产物，保留了基本的移动能力。",
        "stats": {"hp": "50", "speed": "慢", "damage": "10", "exp": "10"},
        "threat": "低",
        "weakness": "头部",
        "lore": "病毒爆发后第一批被感染的人类。他们的身体机能严重退化，但仍保留着对活物的本能渴望。",
    },
    "ZOMBIE_FAST": {
        "name": "疾速僵尸",
        "category": "基础",
        "description": "变异后肌肉纤维异常发达的感染者，移动速度极快，擅长突袭。",
        "stats": {"hp": "35", "speed": "极快", "damage": "12", "exp": "15"},
        "threat": "中",
        "weakness": "体力不支",
        "lore": "感染了变异毒株的跑者，他们的肾上腺素分泌异常，能够在短时间内爆发出惊人的速度。",
    },
    "ZOMBIE_TANK": {
        "name": "坦克僵尸",
        "category": "基础",
        "description": "体型巨大的感染者，皮肤角质化，拥有极高的生命值和防御力。",
        "stats": {"hp": "200", "speed": "极慢", "damage": "25", "exp": "30"},
        "threat": "高",
        "weakness": "行动迟缓",
        "lore": "病毒与巨人症结合的产物，他们的骨骼和肌肉异常增生，成为移动的肉墙。",
    },
    # === 远程僵尸 ===
    "ZOMBIE_RANGED": {
        "name": "远程僵尸",
        "category": "远程",
        "description": "能够投掷物体的感染者，保留了一定的智力和投掷能力。",
        "stats": {"hp": "40", "speed": "中", "damage": "15", "exp": "20"},
        "threat": "中",
        "weakness": "近战脆弱",
        "lore": "感染前可能是运动员或士兵，他们保留了投掷技能，会用周围的杂物攻击幸存者。",
    },
    "ZOMBIE_SPITTER": {
        "name": "吐酸僵尸",
        "category": "远程",
        "description": "体内产生强腐蚀性酸液的感染者，能够远程喷射酸液攻击。",
        "stats": {"hp": "30", "speed": "中", "damage": "18", "exp": "22"},
        "threat": "中",
        "weakness": "酸液储备有限",
        "lore": "胃部变异产生强酸的怪物，他们的唾液能够腐蚀金属，是幸存者的噩梦。",
    },
    "ZOMBIE_HUNTER": {
        "name": "猎人僵尸",
        "category": "远程",
        "description": "精准的远程射手，能够使用简易武器进行远距离攻击。",
        "stats": {"hp": "35", "speed": "中", "damage": "25", "exp": "30"},
        "threat": "高",
        "weakness": "换弹间隙",
        "lore": "感染前的猎人或士兵，他们保留了射击技能，是最危险的远程感染者之一。",
    },
    # === 特殊僵尸 ===
    "ZOMBIE_EXPLODER": {
        "name": "爆炸僵尸",
        "category": "特殊",
        "description": "体内积聚可燃气体的感染者，靠近目标后会自爆造成范围伤害。",
        "stats": {"hp": "30", "speed": "中", "damage": "50", "exp": "25"},
        "threat": "高",
        "weakness": "远程击杀",
        "lore": "体内甲烷气体异常积聚的怪物，他们的身体就是一颗定时炸弹。",
    },
    "ZOMBIE_CRAWLER": {
        "name": "爬行者",
        "category": "特殊",
        "description": "下半身退化的感染者，只能爬行移动，体型小难以命中。",
        "stats": {"hp": "20", "speed": "快", "damage": "8", "exp": "12"},
        "threat": "中",
        "weakness": "血量低",
        "lore": "下半身腐烂脱落的感染者，他们用双手爬行，经常从意想不到的角度发起攻击。",
    },
    "ZOMBIE_SPLITTER": {
        "name": "分裂者",
        "category": "特殊",
        "description": "死亡后会分裂成两个小僵尸的感染者，难以彻底消灭。",
        "stats": {"hp": "60", "speed": "中", "damage": "15", "exp": "28"},
        "threat": "高",
        "weakness": "分裂体脆弱",
        "lore": "细胞具有极强再生能力的怪物，即使被击杀也会分裂出更多的小感染者。",
    },
    "ZOMBIE_SHIELD": {
        "name": "盾兵僵尸",
        "category": "特殊",
        "description": "手持 improvised 盾牌的感染者，正面攻击伤害大幅降低。",
        "stats": {"hp": "80", "speed": "慢", "damage": "18", "exp": "25"},
        "threat": "中",
        "weakness": "侧翼和背后",
        "lore": "感染前的防暴警察，他们手持盾牌，正面几乎无敌。",
    },
    "ZOMBIE_HEALER": {
        "name": "治疗僵尸",
        "category": "特殊",
        "description": "能够释放治疗波的感染者，会为周围的僵尸恢复生命值。",
        "stats": {"hp": "45", "speed": "慢", "damage": "8", "exp": "35"},
        "threat": "高",
        "weakness": "优先击杀",
        "lore": "病毒与某种未知生物能量结合的产物，他们能够释放治疗波，是僵尸群中的核心支援。",
    },
    "ZOMBIE_PHANTOM": {
        "name": "幻影僵尸",
        "category": "特殊",
        "description": "能够短暂隐身的感染者，擅长偷袭和伏击。",
        "stats": {"hp": "40", "speed": "快", "damage": "20", "exp": "30"},
        "threat": "高",
        "weakness": "隐身时仍有轮廓",
        "lore": "皮肤能够折射光线的变异体，他们可以短暂隐身，是最难以防范的感染者之一。",
    },
    "ZOMBIE_WRAITH": {
        "name": "怨灵",
        "category": "特殊",
        "description": "能够穿墙的灵体感染者，还能释放恐惧光环影响玩家。",
        "stats": {"hp": "35", "speed": "快", "damage": "15", "exp": "30"},
        "threat": "极高",
        "weakness": "恐惧效果可抵抗",
        "lore": "病毒与某种超自然力量结合的产物，他们能够穿透墙壁，散发的气息会让幸存者感到恐惧。",
    },
    "ZOMBIE_LEAPER": {
        "name": "跳跃僵尸",
        "category": "特殊",
        "description": "腿部肌肉异常发达的感染者，能够远距离扑击目标。",
        "stats": {"hp": "45", "speed": "中", "damage": "22", "exp": "25"},
        "threat": "高",
        "weakness": "扑击后硬直",
        "lore": "腿部变异的感染者，他们能够跳跃数米远，从天而降发起攻击。",
    },
    "ZOMBIE_CORPSE_EATER": {
        "name": "食尸者",
        "category": "特殊",
        "description": "以尸体为食的感染者，吞噬尸体后会变得更加强大。",
        "stats": {"hp": "55", "speed": "中", "damage": "16", "exp": "28"},
        "threat": "中",
        "weakness": "进食时脆弱",
        "lore": "嗜食同类的怪物，他们通过吞噬其他感染者的尸体来增强自己的力量。",
    },
    # === 新增僵尸 ===
    "ZOMBIE_BOMBER": {
        "name": "爆破手",
        "category": "新增",
        "description": "能够投掷炸弹的感染者，擅长范围攻击和区域封锁。",
        "stats": {"hp": "40", "speed": "中", "damage": "20", "exp": "28"},
        "threat": "高",
        "weakness": "炸弹有引信延迟",
        "lore": "感染前的爆破专家，他们保留了制作和投掷炸弹的技能，能够制造大范围爆炸。",
    },
    "ZOMBIE_FROST": {
        "name": "冰霜僵尸",
        "category": "新增",
        "description": "体内温度极低的感染者，攻击会附带减速效果。",
        "stats": {"hp": "45", "speed": "慢", "damage": "12", "exp": "25"},
        "threat": "中",
        "weakness": "火焰伤害",
        "lore": "病毒与某种低温变异结合的产物，他们的身体温度低于冰点，触碰会造成冻伤。",
    },
    "ZOMBIE_VENOM": {
        "name": "剧毒僵尸",
        "category": "新增",
        "description": "携带剧毒的感染者，攻击会造成持续中毒伤害。",
        "stats": {"hp": "30", "speed": "快", "damage": "8", "exp": "26"},
        "threat": "高",
        "weakness": "解毒剂",
        "lore": "体内产生剧毒的变异体，他们的每一次攻击都会注入毒素，让受害者慢慢死去。",
    },
    "ZOMBIE_BERSERKER": {
        "name": "狂暴僵尸",
        "category": "新增",
        "description": "血量越低越狂暴的感染者，低血量时速度和伤害大幅提升。",
        "stats": {"hp": "80", "speed": "中", "damage": "18", "exp": "35"},
        "threat": "极高",
        "weakness": "快速击杀",
        "lore": "肾上腺素异常分泌的怪物，他们在受伤后会进入狂暴状态，越战越勇。",
    },
    "ZOMBIE_GHOUL": {
        "name": "食尸鬼",
        "category": "新增",
        "description": "嗜血的感染者，攻击有概率造成流血效果。",
        "stats": {"hp": "50", "speed": "中", "damage": "10", "exp": "28"},
        "threat": "中",
        "weakness": "止血带",
        "lore": "嗜食血肉的怪物，他们的牙齿和爪子锋利无比，能够造成持续流血的伤口。",
    },
    "ZOMBIE_SHAMAN": {
        "name": "萨满僵尸",
        "category": "新增",
        "description": "能够为周围僵尸提供增益的感染者，是僵尸群中的核心支援。",
        "stats": {"hp": "35", "speed": "慢", "damage": "8", "exp": "32"},
        "threat": "高",
        "weakness": "优先击杀",
        "lore": "感染前的部落萨满，他们保留了某种神秘的仪式能力，能够增强周围僵尸的力量。",
    },
    "ZOMBIE_JUGGERNAUT": {
        "name": "重甲僵尸",
        "category": "新增",
        "description": "身披重甲的感染者，拥有极高的护甲和生命值。",
        "stats": {"hp": "200", "speed": "极慢", "damage": "30", "exp": "50"},
        "threat": "极高",
        "weakness": "破甲武器",
        "lore": "感染前的重装士兵，他们身披重甲，普通攻击几乎无法造成伤害。",
    },
    # === 精英怪 ===
    "ELITE_BRUTE": {
        "name": "精英蛮兵",
        "category": "精英",
        "description": "经过二次变异的强力感染者，拥有极高的血量和重击能力。",
        "stats": {"hp": "300", "speed": "慢", "damage": "35", "exp": "80"},
        "threat": "极高",
        "weakness": "重击前摇",
        "lore": "病毒深度变异的产物，他们是僵尸群中的精锐战士，每一击都能造成毁灭性伤害。",
    },
    "ELITE_ASSASSIN": {
        "name": "精英刺客",
        "category": "精英",
        "description": "高速高爆发的精英感染者，擅长瞬间秒杀目标。",
        "stats": {"hp": "120", "speed": "极快", "damage": "45", "exp": "75"},
        "threat": "极高",
        "weakness": "血量较低",
        "lore": "感染前的杀手，他们保留了暗杀技能，能够在瞬间发起致命攻击。",
    },
    "ELITE_SORCERER": {
        "name": "精英术士",
        "category": "精英",
        "description": "掌握远程法术的精英感染者，能够释放多种元素攻击。",
        "stats": {"hp": "150", "speed": "中", "damage": "40", "exp": "85"},
        "threat": "极高",
        "weakness": "施法前摇",
        "lore": "病毒与某种未知能量结合的产物，他们能够释放元素法术，是最危险的远程精英。",
    },
    "ELITE_GUARDIAN": {
        "name": "精英守卫",
        "category": "精英",
        "description": "拥有护盾和治疗能力的精英感染者，是僵尸群中的坚固防线。",
        "stats": {"hp": "250", "speed": "慢", "damage": "25", "exp": "90"},
        "threat": "极高",
        "weakness": "护盾可破",
        "lore": "感染前的精英守卫，他们拥有能量护盾和治疗能力，是最难攻克的精英之一。",
    },
    # === Boss ===
    "BOSS_LONG": {
        "name": "龙哥",
        "category": "Boss",
        "description": "校园中的第一个Boss，拥有强大的近战能力和召唤技能。",
        "stats": {"hp": "1000", "speed": "中", "damage": "40", "exp": "200"},
        "threat": "Boss",
        "weakness": "阶段转换时脆弱",
        "lore": "病毒爆发前的校园恶霸，感染后成为了校园区域的统治者。他的力量惊人，是幸存者遇到的第一个重大威胁。",
    },
    "BOSS_XIANG": {
        "name": "向雨晨",
        "category": "Boss",
        "description": "神秘的女性Boss，拥有多种元素攻击和瞬移能力。",
        "stats": {"hp": "1500", "speed": "快", "damage": "50", "exp": "300"},
        "threat": "Boss",
        "weakness": "瞬移后硬直",
        "lore": "身份不明的神秘女性，她似乎与病毒的起源有关。她掌握着超自然的力量，是最难以捉摸的Boss之一。",
    },
    "BOSS_MUTANT": {
        "name": "变异体",
        "category": "Boss",
        "description": "经过多次变异的终极感染者，拥有高伤害连招和多种形态。",
        "stats": {"hp": "2000", "speed": "中", "damage": "60", "exp": "400"},
        "threat": "Boss",
        "weakness": "连招间隙",
        "lore": "病毒深度变异的终极产物，他的身体不断变异，每一次战斗都会展现出新的能力。",
    },
    "BOSS_QUEEN": {
        "name": "尸潮女王",
        "category": "Boss",
        "description": "能够召唤和控制僵尸群的Boss，是尸潮的源头。",
        "stats": {"hp": "1800", "speed": "慢", "damage": "45", "exp": "500"},
        "threat": "Boss",
        "weakness": "召唤时脆弱",
        "lore": "僵尸群的母体，她能够召唤和控制无数的感染者。只要她还活着，尸潮就不会停止。",
    },
    "BOSS_TITAN": {
        "name": "泰坦",
        "category": "Boss",
        "description": "巨型坦克Boss，拥有极高的生命值和毁灭性的范围攻击。",
        "stats": {"hp": "3000", "speed": "极慢", "damage": "80", "exp": "600"},
        "threat": "Boss",
        "weakness": "行动迟缓",
        "lore": "病毒与巨人症深度结合的终极产物，他的体型堪比一座小山，每一步都能震动大地。",
    },
}

# ============================================================
# 武器图鉴数据
# ============================================================
WEAPON_CODEX = {
    # === 近战武器 ===
    "FISTS": {
        "name": "拳头",
        "category": "近战",
        "description": "最基础的武器，不需要弹药，但伤害较低。",
        "stats": {"damage": "5", "fire_rate": "快", "range": "极短", "ammo": "无限"},
        "rarity": "普通",
        "lore": "在末日中，有时候你的拳头就是你最后的武器。",
    },
    "KNIFE": {
        "name": "匕首",
        "category": "近战",
        "description": "锋利的近战武器，攻击速度快，适合近身搏斗。",
        "stats": {"damage": "15", "fire_rate": "极快", "range": "短", "ammo": "无限"},
        "rarity": "普通",
        "lore": "幸存者最常用的近战武器，轻便且致命。",
    },
    "BAT": {
        "name": "棒球棍",
        "category": "近战",
        "description": "沉重的钝器，伤害较高但攻击速度较慢。",
        "stats": {"damage": "25", "fire_rate": "中", "range": "中", "ammo": "无限"},
        "rarity": "普通",
        "lore": "末日中最容易找到的武器之一，一棍下去就能让僵尸脑袋开花。",
    },
    "CHAINSAW": {
        "name": "电锯",
        "category": "近战",
        "description": "高伤害的近战武器，能够持续造成伤害。",
        "stats": {"damage": "40", "fire_rate": "持续", "range": "短", "ammo": "燃料"},
        "rarity": "稀有",
        "lore": "电锯惊魂的末日版本，没有什么比电锯更能让僵尸感到恐惧了。",
    },
    # === 手枪 ===
    "PISTOL": {
        "name": "手枪",
        "category": "手枪",
        "description": "基础的远程武器，平衡了伤害和射速。",
        "stats": {"damage": "20", "fire_rate": "中", "range": "中", "ammo": "12"},
        "rarity": "普通",
        "lore": "最常见的枪械，每个幸存者都应该学会使用。",
    },
    "REVOLVER": {
        "name": "左轮手枪",
        "category": "手枪",
        "description": "高伤害的手枪，但射速较慢，弹容量小。",
        "stats": {"damage": "45", "fire_rate": "慢", "range": "中", "ammo": "6"},
        "rarity": "稀有",
        "lore": "经典的左轮手枪，每一发子弹都充满了力量。",
    },
    "DESERT_EAGLE": {
        "name": "沙漠之鹰",
        "category": "手枪",
        "description": "极高伤害的手枪，后坐力巨大。",
        "stats": {"damage": "70", "fire_rate": "慢", "range": "中", "ammo": "7"},
        "rarity": "史诗",
        "lore": "手枪中的王者，只有最强壮的人才能驾驭它的后坐力。",
    },
    # === 冲锋枪 ===
    "SMG": {
        "name": "冲锋枪",
        "category": "冲锋枪",
        "description": "高射速的武器，适合近距离战斗。",
        "stats": {"damage": "12", "fire_rate": "极快", "range": "短", "ammo": "30"},
        "rarity": "普通",
        "lore": "近距离战斗的利器，子弹倾泻如雨。",
    },
    "UMP45": {
        "name": "UMP45",
        "category": "冲锋枪",
        "description": "平衡的冲锋枪，伤害和射速都不错。",
        "stats": {"damage": "18", "fire_rate": "快", "range": "中", "ammo": "25"},
        "rarity": "稀有",
        "lore": "特种部队常用的冲锋枪，性能可靠。",
    },
    "P90": {
        "name": "P90",
        "category": "冲锋枪",
        "description": "大容量弹匣的冲锋枪，持续火力强。",
        "stats": {"damage": "15", "fire_rate": "极快", "range": "中", "ammo": "50"},
        "rarity": "史诗",
        "lore": "独特的外形设计，50发弹匣让你不用担心弹药耗尽。",
    },
    # === 步枪 ===
    "RIFLE": {
        "name": "突击步枪",
        "category": "步枪",
        "description": "全能的步枪，适合各种距离的战斗。",
        "stats": {"damage": "25", "fire_rate": "快", "range": "远", "ammo": "30"},
        "rarity": "普通",
        "lore": "最经典的突击步枪，是幸存者的主力武器。",
    },
    "AK47": {
        "name": "AK-47",
        "category": "步枪",
        "description": "高伤害的步枪，后坐力较大。",
        "stats": {"damage": "35", "fire_rate": "中", "range": "远", "ammo": "30"},
        "rarity": "稀有",
        "lore": "世界上最著名的步枪，简单可靠，威力巨大。",
    },
    "M4A1": {
        "name": "M4A1",
        "category": "步枪",
        "description": "精准的步枪，后坐力小，射速快。",
        "stats": {"damage": "28", "fire_rate": "快", "range": "远", "ammo": "30"},
        "rarity": "稀有",
        "lore": "美军制式步枪，精准度极高。",
    },
    "SCAR": {
        "name": "SCAR",
        "category": "步枪",
        "description": "高级步枪，平衡了伤害、射速和精准度。",
        "stats": {"damage": "40", "fire_rate": "快", "range": "极远", "ammo": "25"},
        "rarity": "史诗",
        "lore": "特种部队的专用步枪，性能卓越。",
    },
    # === 狙击枪 ===
    "SNIPER": {
        "name": "狙击步枪",
        "category": "狙击枪",
        "description": "极高伤害的远程武器，适合远距离精确打击。",
        "stats": {"damage": "100", "fire_rate": "极慢", "range": "极远", "ammo": "5"},
        "rarity": "稀有",
        "lore": "一枪爆头的快感，只有狙击手才能体会。",
    },
    "AWP": {
        "name": "AWP",
        "category": "狙击枪",
        "description": "传奇狙击枪，伤害极高，能够一枪毙命。",
        "stats": {"damage": "150", "fire_rate": "极慢", "range": "极远", "ammo": "5"},
        "rarity": "史诗",
        "lore": "狙击枪中的王者，每一发子弹都是一次审判。",
    },
    # === 霰弹枪 ===
    "SHOTGUN": {
        "name": "霰弹枪",
        "category": "霰弹枪",
        "description": "近距离伤害极高的武器，一发多弹。",
        "stats": {"damage": "60", "fire_rate": "慢", "range": "短", "ammo": "6"},
        "rarity": "普通",
        "lore": "近距离战斗的王者，没有什么能扛住一发霰弹。",
    },
    "DOUBLE_BARREL": {
        "name": "双管猎枪",
        "category": "霰弹枪",
        "description": "双管霰弹枪，能够同时发射两发霰弹。",
        "stats": {"damage": "100", "fire_rate": "极慢", "range": "短", "ammo": "2"},
        "rarity": "稀有",
        "lore": "经典的双管猎枪，两发下去，神仙难救。",
    },
    "AA12": {
        "name": "AA-12",
        "category": "霰弹枪",
        "description": "全自动霰弹枪，近距离火力压制利器。",
        "stats": {"damage": "50", "fire_rate": "极快", "range": "短", "ammo": "20"},
        "rarity": "史诗",
        "lore": "全自动霰弹枪，近距离就是一场屠杀。",
    },
    # === 重武器 ===
    "LMG": {
        "name": "轻机枪",
        "category": "重武器",
        "description": "大容量弹匣的机枪，持续火力压制。",
        "stats": {"damage": "30", "fire_rate": "极快", "range": "远", "ammo": "100"},
        "rarity": "稀有",
        "lore": "火力压制的首选，100发子弹让你尽情扫射。",
    },
    "ROCKET_LAUNCHER": {
        "name": "火箭筒",
        "category": "重武器",
        "description": "范围伤害武器，能够摧毁成群的僵尸。",
        "stats": {"damage": "200", "fire_rate": "极慢", "range": "远", "ammo": "3"},
        "rarity": "史诗",
        "lore": "范围伤害的终极武器，一发火箭弹，一片清净。",
    },
    "MINIGUN": {
        "name": "加特林",
        "category": "重武器",
        "description": "极高射速的重机枪，需要预热。",
        "stats": {"damage": "20", "fire_rate": "极快", "range": "远", "ammo": "200"},
        "rarity": "传说",
        "lore": "旋转的枪管，倾泻的子弹，这就是加特林的浪漫。",
    },
    # === 特殊武器 ===
    "FLAMETHROWER": {
        "name": "火焰喷射器",
        "category": "特殊",
        "description": "持续喷射火焰的武器，造成范围持续伤害。",
        "stats": {"damage": "15", "fire_rate": "持续", "range": "中", "ammo": "燃料"},
        "rarity": "稀有",
        "lore": "用火净化一切，僵尸也怕火。",
    },
    "CROSSBOW": {
        "name": "弩",
        "category": "特殊",
        "description": "静音的远程武器，箭矢可以回收。",
        "stats": {"damage": "80", "fire_rate": "慢", "range": "远", "ammo": "10"},
        "rarity": "稀有",
        "lore": "无声的杀手，弩箭可以回收，是资源匮乏时的最佳选择。",
    },
    "RAILGUN": {
        "name": "电磁轨道炮",
        "category": "特殊",
        "description": "高科技武器，能够发射高速弹丸穿透多个目标。",
        "stats": {"damage": "120", "fire_rate": "慢", "range": "极远", "ammo": "8"},
        "rarity": "传说",
        "lore": "未来科技的结晶，电磁加速的弹丸能够穿透一切。",
    },
    # === 投掷物 ===
    "GRENADE": {
        "name": "手雷",
        "category": "投掷物",
        "description": "投掷后爆炸的武器，造成范围伤害。",
        "stats": {"damage": "100", "fire_rate": "慢", "range": "中", "ammo": "5"},
        "rarity": "普通",
        "lore": "最经典的投掷武器，拉环，投掷，然后听响。",
    },
    "MOLOTOV": {
        "name": "燃烧瓶",
        "category": "投掷物",
        "description": "投掷后产生燃烧区域，持续造成伤害。",
        "stats": {"damage": "50", "fire_rate": "慢", "range": "中", "ammo": "5"},
        "rarity": "普通",
        "lore": "简易的燃烧武器，玻璃瓶加汽油，就是这么简单。",
    },
    "SMOKE_GRENADE": {
        "name": "烟雾弹",
        "category": "投掷物",
        "description": "产生烟雾区域，遮挡视线。",
        "stats": {"damage": "0", "fire_rate": "慢", "range": "中", "ammo": "3"},
        "rarity": "稀有",
        "lore": "战术撤退的好帮手，烟雾中僵尸会失去目标。",
    },
}

# ============================================================
# 图鉴分类
# ============================================================
MONSTER_CATEGORIES = ["全部", "基础", "远程", "特殊", "新增", "精英", "Boss"]
WEAPON_CATEGORIES = ["全部", "近战", "手枪", "冲锋枪", "步枪", "狙击枪", "霰弹枪", "重武器", "特殊", "投掷物"]

# 稀有度颜色
RARITY_COLORS = {
    "普通": (200, 200, 200),
    "稀有": (100, 150, 255),
    "史诗": (180, 100, 255),
    "传说": (255, 200, 50),
}

# 威胁等级颜色
THREAT_COLORS = {
    "低": (100, 255, 100),
    "中": (255, 255, 100),
    "高": (255, 150, 50),
    "极高": (255, 80, 80),
    "Boss": (200, 50, 255),
}


def get_monster_by_category(category):
    """根据分类获取怪物列表"""
    if category == "全部":
        return list(MONSTER_CODEX.keys())
    return [k for k, v in MONSTER_CODEX.items() if v["category"] == category]


def get_weapon_by_category(category):
    """根据分类获取武器列表"""
    if category == "全部":
        return list(WEAPON_CODEX.keys())
    return [k for k, v in WEAPON_CODEX.items() if v["category"] == category]


# ========== 图鉴解锁状态管理 ==========


# ============================================================
# 世界观背景故事
# ============================================================
WORLD_LORE = {
    "origin": {
        "title": "病毒起源",
        "content": """2027年，一场突如其来的病毒风暴席卷全球。这种被命名为"X-7"的逆转录病毒最初被认为是一种新型流感，但很快人们发现它的可怕之处——它能够重组人类的DNA，将感染者变成嗜血的怪物。

病毒的起源至今成谜。有人说是某国秘密实验室的泄漏，有人说是来自深空的陨石携带，还有人认为这是大自然对人类的惩罚。无论真相如何，世界在短短三个月内彻底崩塌。

政府的隔离措施失败了，军队的防线崩溃了，城市变成了感染者的乐园。少数对病毒具有天然免疫力的人，成为了人类最后的希望。"""
    },
    "infection_stages": {
        "title": "感染阶段",
        "content": """X-7病毒的感染分为四个阶段：

第一阶段（0-6小时）：感染者出现高烧、咳嗽、肌肉酸痛等类似流感的症状。此时病毒正在快速复制，但尚未攻击神经系统。

第二阶段（6-24小时）：感染者开始出现意识模糊、攻击性增强的症状。病毒开始侵入大脑，破坏前额叶皮层，导致理智丧失。

第三阶段（24-72小时）：感染者完全丧失人性，成为只会追逐活物的"僵尸"。身体机能发生变异，肌肉纤维增强，痛觉消失。

第四阶段（72小时后）：部分感染者发生进一步变异，出现特殊能力。这一阶段的变异方向不可预测，产生了各种危险的变异体。

值得注意的是，约0.3%的人类具有天然免疫力，他们的免疫系统能够识别并消灭X-7病毒。这些幸存者成为了重建文明的火种。"""
    },
    "safe_zones": {
        "title": "幸存者据点",
        "content": """在末日中，幸存者们建立了各种类型的据点：

【沦陷的校园】：病毒爆发时，这所中学正在进行期末考试。师生们被困在校园内，利用学校的物资和围墙建立了临时防线。但随着感染人数增加，校园最终沦陷，成为了僵尸的巢穴。

【废弃医院】：城市中心的三甲医院，病毒爆发初期被指定为定点收治医院。大量感染者涌入后，医院迅速崩溃。现在，这里是各种变异体的聚集地，因为医院的化学药品和辐射设备加速了病毒的变异。

【核电站废墟】：城郊的核电站在混乱中发生了泄漏，高辐射区域杀死了大部分感染者，但也催生了一些抗辐射的变异体。这里是最危险的区域之一，但也藏有大量未被搜刮的物资。

【地下避难所】：政府在城市各处修建的地下避难所，部分避难所仍然有幸存者居住。这些避难所拥有独立的空气过滤系统和食物储备，是相对安全的地方。"""
    },
    "factions": {
        "title": "幸存者势力",
        "content": """在末日中，幸存者们形成了不同的势力：

【新秩序军】：由前军人和警察组成的军事化组织，主张建立严格的等级制度。他们控制着城市的部分区域，拥有精良的武器装备。新秩序军相信，只有铁腕统治才能让人类延续。

【自由民】：松散的幸存者联盟，强调个人自由和互助。他们擅长 scavenging（搜刮），在城市的废墟中寻找物资。自由民之间没有严格的等级，靠信任和契约维持合作。

【教会】：在末日中兴起的宗教组织，他们相信病毒是神的审判，只有虔诚的信徒才能获得救赎。教会在地下避难所中建立了据点，为幸存者提供精神慰藉和物质帮助。

【拾荒者】：独来独往的幸存者，他们不加入任何势力，靠在废墟中搜刮物资为生。拾荒者通常身手敏捷，熟悉城市的每一条小巷。

【科学家】：少数幸存的科研人员，他们致力于研究X-7病毒的解药和变异规律。科学家们隐藏在大学和研究所中，进行着危险的实验。"""
    },
    "mutations": {
        "title": "变异研究",
        "content": """X-7病毒的变异机制至今未被完全理解，但科学家们已经观察到一些规律：

【环境诱导变异】：辐射、化学物质、极端温度等环境因素能够加速病毒的变异。这就是为什么核电站、化工厂等区域的变异体特别多且特别危险。

【宿主特性影响】：感染者的体质、年龄、性别、健康状况都会影响变异方向。例如，运动员更容易变异成疾速僵尸，而肥胖者更容易变异成坦克僵尸。

【病毒重组】：当多个感染者聚集在一起时，病毒会在不同宿主之间传播和重组，产生新的变异株。这就是尸潮中经常出现新型变异体的原因。

【Boss级变异】：极少数感染者会发生"超级变异"，成为拥有强大能力的Boss级怪物。这些怪物通常具有独特的攻击方式和极高的生命值，是幸存者的最大威胁。

科学家们相信，如果能够破解变异的规律，就有可能找到阻止变异的方法，甚至逆转感染过程。"""
    },
    "weapon_tech": {
        "title": "武器技术",
        "content": """在末日中，幸存者们发展出了独特的武器技术：

【 improvised weapons（即兴武器）】：最常见的武器类型，由日常用品改造而成。棒球棍、菜刀、消防斧等都是有效的近战武器。这些武器虽然简陋，但在近距离战斗中非常实用。

【改装枪械】：幸存者们收集了各种枪械，并进行了改装。由于弹药稀缺，每一发子弹都必须精打细算。一些高手能够用手枪在百米外命中僵尸的头部。

【能量武器】：少数科学家和工程师开发出了基于电能的武器，如电击棒、激光枪等。这些武器不需要弹药，但需要充电，在末日中电力是稀缺资源。

【生物武器】：基于X-7病毒研究开发的武器，能够对感染者造成特殊伤害。但这些武器非常危险，使用不当可能会导致新的变异。

【符文系统】：神秘的符文技术，据说来自古老的传承。符文能够为武器和装备附加特殊效果，如火焰伤害、冰冻效果等。符文的来源和原理至今是个谜。"""
    },
    "horde_behavior": {
        "title": "尸潮行为学",
        "content": """尸潮是末日中最可怕的现象之一。研究表明，尸潮的形成和行为有以下规律：

【形成机制】：当感染者数量达到一定密度时，它们会释放一种信息素，吸引更多的感染者聚集。这种信息素具有传染性，能够在短时间内召集大量僵尸。

【规模分级】：尸潮根据规模分为四个等级：小型（50只以下）、中型（50-200只）、大型（200-500只）、巨型（500只以上）。规模越大的尸潮，包含的变异体和Boss越多。

【行为模式】：尸潮中的僵尸会表现出一定的集体智慧，它们会包围猎物、攻击防线、甚至使用简单的战术。Boss级怪物通常是尸潮的指挥者。

【消退规律】：尸潮通常会持续一段时间后自然消退，可能是因为信息素浓度下降。尸潮消退后，会留下大量的尸体和物资，这是幸存者搜刮的好时机，但也要小心残留的感染者。

【应对策略】：面对尸潮，最好的策略是躲避。如果无法躲避，就必须建立坚固的防线，集中火力攻击Boss和变异体。一旦Boss被击杀，尸潮通常会迅速崩溃。"""
    }
}

class CodexUnlockManager:
    """图鉴解锁管理器 - 跟踪已解锁的怪物和武器
    
    特性：
    - 使用绝对路径保存，确保无论从哪个目录运行都能正确读写
    - 每次解锁立即保存，非正常退出也不会丢失
    - 原子写入（先写临时文件再重命名），防止写入中断导致文件损坏
    """

    def __init__(self):
        self.unlocked_monsters = set()
        self.unlocked_weapons = set()
        self._save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codex_unlocks.json")
        self._load_unlocks()

    def _load_unlocks(self):
        """从存档加载解锁状态"""
        try:
            if os.path.exists(self._save_path):
                with open(self._save_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.unlocked_monsters = set(data.get('monsters', []))
                    self.unlocked_weapons = set(data.get('weapons', []))
        except Exception:
            pass

    def save_unlocks(self):
        """保存解锁状态到文件（原子写入，防止损坏）"""
        try:
            data = {
                'monsters': sorted(list(self.unlocked_monsters)),
                'weapons': sorted(list(self.unlocked_weapons))
            }
            # 先写临时文件，再原子重命名
            tmp_path = self._save_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._save_path)
        except Exception:
            pass

    def unlock_monster(self, monster_id):
        """解锁怪物图鉴（立即保存）"""
        if monster_id and monster_id not in self.unlocked_monsters:
            self.unlocked_monsters.add(monster_id)
            self.save_unlocks()
            return True
        return False

    def unlock_weapon(self, weapon_id):
        """解锁武器图鉴（立即保存）"""
        if weapon_id and weapon_id not in self.unlocked_weapons:
            self.unlocked_weapons.add(weapon_id)
            self.save_unlocks()
            return True
        return False

    def is_monster_unlocked(self, monster_id):
        """检查怪物是否已解锁"""
        return monster_id in self.unlocked_monsters

    def is_weapon_unlocked(self, weapon_id):
        """检查武器是否已解锁"""
        return weapon_id in self.unlocked_weapons

    def get_unlocked_monsters(self):
        """获取所有已解锁的怪物ID"""
        return list(self.unlocked_monsters)

    def get_unlocked_weapons(self):
        """获取所有已解锁的武器ID"""
        return list(self.unlocked_weapons)

# 全局图鉴解锁管理器
codex_unlock_manager = CodexUnlockManager()
