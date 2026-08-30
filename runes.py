#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""符文系统 - 局内永久buff，从宝箱/黄金宝箱开出
符文在一局游戏内永久生效，多枚同类型符文效果叠加（有上限）
"""
import random
from config import RuneType, RED, BLUE, GREEN, ORANGE, CYAN, PURPLE, YELLOW, GOLD, WHITE, DARK_GRAY, LIGHT_GRAY, MAGENTA, LIME

# 符文配置表
RUNE_CONFIG = {
    RuneType.FLAME: {
        "name": "火焰符文", "color": ORANGE, "rarity": "common",
        "description": "攻击附带燃烧效果，每秒造成3点伤害，持续3秒",
        "max_stacks": 3,
    },
    RuneType.FROST: {
        "name": "冰霜符文", "color": CYAN, "rarity": "common",
        "description": "攻击附带减速效果，降低敌人30%移速，持续2秒",
        "max_stacks": 3,
    },
    RuneType.POISON: {
        "name": "毒素符文", "color": GREEN, "rarity": "common",
        "description": "攻击附带中毒效果，每秒造成2点伤害，持续5秒",
        "max_stacks": 3,
    },
    RuneType.POWER: {
        "name": "力量符文", "color": RED, "rarity": "uncommon",
        "description": "所有伤害+15%",
        "max_stacks": 5,
    },
    RuneType.VITALITY: {
        "name": "生命符文", "color": GREEN, "rarity": "uncommon",
        "description": "最大生命值+30",
        "max_stacks": 5,
    },
    RuneType.SWIFTNESS: {
        "name": "迅捷符文", "color": CYAN, "rarity": "uncommon",
        "description": "移动速度+10%",
        "max_stacks": 3,
    },
    RuneType.CRITICAL: {
        "name": "暴击符文", "color": YELLOW, "rarity": "uncommon",
        "description": "暴击率+10%",
        "max_stacks": 5,
    },
    RuneType.VAMPIRE: {
        "name": "吸血符文", "color": RED, "rarity": "rare",
        "description": "造成伤害时回复5%生命值",
        "max_stacks": 3,
    },
    RuneType.GUARDIAN: {
        "name": "守护符文", "color": BLUE, "rarity": "uncommon",
        "description": "护甲+10，受到伤害降低",
        "max_stacks": 5,
    },
    RuneType.FRENZY: {
        "name": "狂怒符文", "color": ORANGE, "rarity": "rare",
        "description": "攻击速度+15%",
        "max_stacks": 3,
    },
    RuneType.THUNDER: {
        "name": "雷电符文", "color": YELLOW, "rarity": "epic",
        "description": "攻击有20%几率触发连锁闪电，跳跃3次",
        "max_stacks": 2,
    },
    RuneType.REGEN: {
        "name": "再生符文", "color": GREEN, "rarity": "rare",
        "description": "每秒回复2点生命值",
        "max_stacks": 3,
    },
    RuneType.LUCK: {
        "name": "幸运符文", "color": GOLD, "rarity": "epic",
        "description": "道具掉落率+20%，宝箱品质提升",
        "max_stacks": 2,
    },
    RuneType.SHADOW: {
        "name": "暗影符文", "color": PURPLE, "rarity": "epic",
        "description": "暴击伤害+50%",
        "max_stacks": 3,
    },
    RuneType.TITAN: {
        "name": "泰坦符文", "color": MAGENTA, "rarity": "legendary",
        "description": "体型增大15%，近战攻击范围+20%，伤害+10%",
        "max_stacks": 1,
    },
}

# 稀有度权重（用于随机抽取）
RARITY_WEIGHTS = {
    "common": 40,
    "uncommon": 30,
    "rare": 18,
    "epic": 9,
    "legendary": 3,
}

# 稀有度颜色
RARITY_COLORS = {
    "common": LIGHT_GRAY,
    "uncommon": GREEN,
    "rare": BLUE,
    "epic": PURPLE,
    "legendary": GOLD,
}

# 稀有度名称
RARITY_NAMES = {
    "common": "普通",
    "uncommon": "优秀",
    "rare": "稀有",
    "epic": "史诗",
    "legendary": "传说",
}


class Rune:
    """单枚符文"""
    def __init__(self, rune_type):
        self.rune_type = rune_type
        config = RUNE_CONFIG[rune_type]
        self.name = config["name"]
        self.color = config["color"]
        self.rarity = config["rarity"]
        self.description = config["description"]
        self.max_stacks = config["max_stacks"]


class RuneManager:
    """玩家符文管理器 - 一局游戏内生效"""
    def __init__(self):
        self.runes = {}  # {RuneType: stack_count}
    
    def add_rune(self, rune_type):
        """添加一枚符文，返回是否成功（达到上限返回False）"""
        config = RUNE_CONFIG[rune_type]
        current = self.runes.get(rune_type, 0)
        if current >= config["max_stacks"]:
            return False
        self.runes[rune_type] = current + 1
        return True
    
    def get_stacks(self, rune_type):
        return self.runes.get(rune_type, 0)
    
    def get_total_count(self):
        return sum(self.runes.values())
    
    def get_bonus(self, stat_name):
        """获取某属性的符文加成总值"""
        total = 0
        for rune_type, stacks in self.runes.items():
            config = RUNE_CONFIG[rune_type]
            # 根据符文类型计算属性加成
            if stat_name == "damage_mult" and rune_type == RuneType.POWER:
                total += 0.15 * stacks
            elif stat_name == "max_hp" and rune_type == RuneType.VITALITY:
                total += 30 * stacks
            elif stat_name == "speed_mult" and rune_type == RuneType.SWIFTNESS:
                total += 0.10 * stacks
            elif stat_name == "crit_chance" and rune_type == RuneType.CRITICAL:
                total += 0.10 * stacks
            elif stat_name == "lifesteal" and rune_type == RuneType.VAMPIRE:
                total += 0.05 * stacks
            elif stat_name == "armor" and rune_type == RuneType.GUARDIAN:
                total += 10 * stacks
            elif stat_name == "fire_rate_mult" and rune_type == RuneType.FRENZY:
                total += 0.15 * stacks
            elif stat_name == "regen" and rune_type == RuneType.REGEN:
                total += 2 * stacks
            elif stat_name == "crit_damage_mult" and rune_type == RuneType.SHADOW:
                total += 0.50 * stacks
            elif stat_name == "melee_range_mult" and rune_type == RuneType.TITAN:
                total += 0.20 * stacks
            elif stat_name == "drop_rate_mult" and rune_type == RuneType.LUCK:
                total += 0.20 * stacks
        return total
    
    def has_elemental(self, element):
        """检查是否拥有某元素符文"""
        mapping = {
            "fire": RuneType.FLAME,
            "frost": RuneType.FROST,
            "poison": RuneType.POISON,
            "thunder": RuneType.THUNDER,
        }
        rt = mapping.get(element)
        return rt is not None and self.get_stacks(rt) > 0
    
    def get_all_runes(self):
        """返回所有已拥有符文的列表 [(RuneType, stacks), ...]"""
        return [(rt, s) for rt, s in self.runes.items()]


def random_rune(luck_bonus=0):
    """随机抽取一枚符文，luck_bonus提升稀有度概率"""
    # 计算权重
    weights = {}
    for rarity, base_weight in RARITY_WEIGHTS.items():
        if rarity == "common":
            weights[rarity] = max(5, base_weight - luck_bonus * 10)
        elif rarity in ("rare", "epic", "legendary"):
            weights[rarity] = base_weight + luck_bonus * 5
        else:
            weights[rarity] = base_weight
    
    # 按稀有度加权随机
    total = sum(weights.values())
    r = random.uniform(0, total)
    cumulative = 0
    chosen_rarity = "common"
    for rarity, w in weights.items():
        cumulative += w
        if r <= cumulative:
            chosen_rarity = rarity
            break
    
    # 从该稀有度的符文中随机选一个
    candidates = [rt for rt, cfg in RUNE_CONFIG.items() if cfg["rarity"] == chosen_rarity]
    if not candidates:
        candidates = list(RUNE_CONFIG.keys())
    return random.choice(candidates)
