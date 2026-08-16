#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用Buff系统 - 支持正面buff和负面debuff，玩家和僵尸共用"""
import math
from enum import Enum
from config import (RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, CYAN, GRAY, WHITE,
                    CRIMSON, LIME, TEAL, RUST, POISON_GREEN, FIRE_ORANGE, BLOOD_RED, GOLD)


class BuffType(Enum):
    # === 正面 Buff ===
    SPEED_BOOST = "speed_boost"       # 加速
    DAMAGE_BOOST = "damage_boost"     # 伤害提升
    HASTE = "haste"                   # 急速（攻速+换弹加速）
    SHIELD = "shield"                 # 护盾（减伤）
    REGEN = "regen"                   # 生命恢复
    INVINCIBLE = "invincible"         # 无敌
    BERSERK = "berserk"               # 狂暴（攻速翻倍，受伤增加）
    IRON_SKIN = "iron_skin"           # 铁皮（护甲提升）
    LUCKY = "lucky"                   # 幸运（暴击率提升）

    # === 负面 Debuff ===
    BLEED = "bleed"                   # 流血（持续掉血）
    FRACTURE = "fracture"             # 骨折（移动减速）
    BURN = "burn"                     # 燃烧（持续掉血+伤害加深）
    FREEZE = "freeze"                 # 冻结（无法移动）
    POISON = "poison"                 # 中毒（持续掉血）
    SLOW = "slow"                     # 减速
    WEAKEN = "weaken"                 # 虚弱（伤害降低）
    STUN = "stun"                     # 眩晕（无法行动）
    # === 新增正面Buff ===
    EMPOWER = "empower"               # 强化（下次攻击伤害x3）
    GHOST = "ghost"                   # 幽灵化（半透明+穿越敌人）
    THORNS = "thorns"                 # 荆棘（反伤50%）
    BLOOD_FRENZY = "blood_frenzy"     # 血怒（血量越低伤害越高）
    # === 新增负面Debuff ===
    CORROSION = "corrosion"           # 腐蚀（护甲归零+持续伤害）
    FEAR = "fear"                     # 恐惧（无法攻击+随机移动）
    CURSE = "curse"                   # 诅咒（受伤+50%+治疗-50%）
    MARK = "mark"                     # 标记（受到暴击伤害+100%）


# Buff 预设配置
BUFF_CONFIGS = {
    BuffType.SPEED_BOOST: {
        "name": "加速", "icon": "⚡", "color": LIME, "is_debuff": False,
        "desc": "移动速度提升50%",
        "speed_mult": 1.5,
    },
    BuffType.DAMAGE_BOOST: {
        "name": "伤害提升", "icon": "⚔", "color": ORANGE, "is_debuff": False,
        "desc": "造成伤害提升100%",
        "damage_mult": 2.0,
    },
    BuffType.HASTE: {
        "name": "急速", "icon": "⏱", "color": YELLOW, "is_debuff": False,
        "desc": "攻击速度和换弹速度提升40%",
        "attack_speed_mult": 1.4, "reload_speed_mult": 1.4,
    },
    BuffType.SHIELD: {
        "name": "护盾", "icon": "🛡", "color": BLUE, "is_debuff": False,
        "desc": "受到伤害降低50%",
        "damage_taken_mult": 0.5,
    },
    BuffType.REGEN: {
        "name": "恢复", "icon": "✚", "color": GREEN, "is_debuff": False,
        "desc": "每秒恢复5%最大生命值",
        "tick_interval": 1.0, "heal_percent": 0.05,
    },
    BuffType.INVINCIBLE: {
        "name": "无敌", "icon": "★", "color": GOLD, "is_debuff": False,
        "desc": "免疫所有伤害",
        "damage_taken_mult": 0.0,
    },
    BuffType.BERSERK: {
        "name": "狂暴", "icon": "🔥", "color": CRIMSON, "is_debuff": False,
        "desc": "攻速翻倍，移动速度+20%，但受到伤害+30%",
        "attack_speed_mult": 2.0, "speed_mult": 1.2, "damage_taken_mult": 1.3,
    },
    BuffType.IRON_SKIN: {
        "name": "铁皮", "icon": "⛨", "color": GRAY, "is_debuff": False,
        "desc": "受到伤害降低30%",
        "damage_taken_mult": 0.7,
    },
    BuffType.LUCKY: {
        "name": "幸运", "icon": "♦", "color": YELLOW, "is_debuff": False,
        "desc": "暴击率提升20%",
        "crit_chance_add": 0.2,
    },
    # === Debuff ===
    BuffType.BLEED: {
        "name": "流血", "icon": "🩸", "color": BLOOD_RED, "is_debuff": True,
        "desc": "每秒流失3%最大生命值",
        "tick_interval": 0.5, "damage_percent": 0.015,
    },
    BuffType.FRACTURE: {
        "name": "骨折", "icon": "🦴", "color": GRAY, "is_debuff": True,
        "desc": "移动速度降低50%",
        "speed_mult": 0.5,
    },
    BuffType.BURN: {
        "name": "燃烧", "icon": "🔥", "color": FIRE_ORANGE, "is_debuff": True,
        "desc": "每秒流失4%生命值，受到伤害+20%",
        "tick_interval": 0.5, "damage_percent": 0.02, "damage_taken_mult": 1.2,
    },
    BuffType.FREEZE: {
        "name": "冻结", "icon": "❄", "color": CYAN, "is_debuff": True,
        "desc": "无法移动和攻击",
        "speed_mult": 0.0, "stunned": True,
    },
    BuffType.POISON: {
        "name": "中毒", "icon": "☠", "color": POISON_GREEN, "is_debuff": True,
        "desc": "每秒流失2%生命值，移动速度-20%",
        "tick_interval": 1.0, "damage_percent": 0.02, "speed_mult": 0.8,
    },
    BuffType.SLOW: {
        "name": "减速", "icon": "🐌", "color": TEAL, "is_debuff": True,
        "desc": "移动速度降低40%",
        "speed_mult": 0.6,
    },
    BuffType.WEAKEN: {
        "name": "虚弱", "icon": "💔", "color": PURPLE, "is_debuff": True,
        "desc": "造成伤害降低30%",
        "damage_mult": 0.7,
    },
    BuffType.STUN: {
        "name": "眩晕", "icon": "💫", "color": YELLOW, "is_debuff": True,
        "desc": "无法行动",
        "speed_mult": 0.0, "stunned": True,
    },
    BuffType.EMPOWER: {
        "name": "强化", "icon": "🔆", "color": GOLD, "is_debuff": False,
        "desc": "下次攻击伤害提升200%",
        "damage_mult": 3.0, "consume_on_attack": True,
    },
    BuffType.GHOST: {
        "name": "幽灵化", "icon": "👻", "color": CYAN, "is_debuff": False,
        "desc": "半透明，穿越敌人，受到伤害-40%",
        "damage_taken_mult": 0.6, "ghost_mode": True,
    },
    BuffType.THORNS: {
        "name": "荆棘", "icon": "🌵", "color": LIME, "is_debuff": False,
        "desc": "受到近战攻击时反弹50%伤害",
        "thorns_damage": 0.5,
    },
    BuffType.BLOOD_FRENZY: {
        "name": "血怒", "icon": "🩸", "color": CRIMSON, "is_debuff": False,
        "desc": "血量越低伤害越高，最多+100%",
        "blood_frenzy": True,
    },
    BuffType.CORROSION: {
        "name": "腐蚀", "icon": "🧪", "color": LIME, "is_debuff": True,
        "desc": "护甲归零，每秒受到8点伤害",
        "tick_interval": 1.0, "tick_damage": 8, "armor_mult": 0.0,
    },
    BuffType.FEAR: {
        "name": "恐惧", "icon": "😱", "color": PURPLE, "is_debuff": True,
        "desc": "无法攻击，随机方向移动",
        "attack_speed_mult": 0.0, "fear_move": True,
    },
    BuffType.CURSE: {
        "name": "诅咒", "icon": "☠", "color": PURPLE, "is_debuff": True,
        "desc": "受到伤害+50%，治疗效果-50%",
        "damage_taken_mult": 1.5, "heal_mult": 0.5,
    },
    BuffType.MARK: {
        "name": "标记", "icon": "🎯", "color": RED, "is_debuff": True,
        "desc": "受到暴击伤害+100%",
        "crit_taken_mult": 2.0,
    },
}


class Buff:
    """单个Buff实例"""
    def __init__(self, buff_type, duration=None, stacks=1):
        self.buff_type = buff_type
        self.config = BUFF_CONFIGS[buff_type]
        self.name = self.config["name"]
        self.icon = self.config["icon"]
        self.color = self.config["color"]
        self.is_debuff = self.config["is_debuff"]
        self.description = self.config["desc"]
        self.duration = duration  # None = 永久
        self.remaining = duration
        self.stacks = stacks
        self.tick_timer = 0

    def refresh(self, duration=None):
        """刷新持续时间"""
        if duration is not None:
            self.remaining = duration
        elif self.duration is not None:
            self.remaining = self.duration

    def add_stack(self):
        """叠加层数"""
        self.stacks += 1

    def is_expired(self):
        return self.duration is not None and self.remaining <= 0

    def get_effect(self, key, default=1.0):
        """获取效果值（乘区），受层数影响"""
        val = self.config.get(key, default)
        if key in ("speed_mult", "damage_mult", "attack_speed_mult",
                   "reload_speed_mult", "damage_taken_mult"):
            # 乘区效果：多层时非线性叠加（1 + (val-1)*stacks）
            return 1.0 + (val - 1.0) * self.stacks
        return val

    def get_flat_effect(self, key, default=0.0):
        """获取扁平加成效果，受层数影响"""
        val = self.config.get(key, default)
        return val * self.stacks


class BuffManager:
    """Buff管理器 - 玩家和僵尸共用"""
    def __init__(self):
        self.buffs = {}  # {BuffType: Buff}

    def add_buff(self, buff_type, duration=None, stacks=1):
        """添加buff，已存在则刷新时间+叠加层数"""
        if buff_type in self.buffs:
            self.buffs[buff_type].refresh(duration)
            self.buffs[buff_type].stacks = min(
                self.buffs[buff_type].stacks + stacks, 5)
        else:
            self.buffs[buff_type] = Buff(buff_type, duration, stacks)

    def remove_buff(self, buff_type):
        if buff_type in self.buffs:
            del self.buffs[buff_type]

    def has_buff(self, buff_type):
        return buff_type in self.buffs

    def get_buff(self, buff_type):
        return self.buffs.get(buff_type)

    def update(self, dt, entity):
        """
        更新所有buff，处理tick伤害/治疗
        entity需要有 hp, max_hp, take_damage(), heal() 方法
        返回：造成的伤害总量（用于屏幕特效）
        """
        damage_dealt = 0
        expired = []
        for btype, buff in self.buffs.items():
            if buff.duration is not None:
                buff.remaining -= dt
            # 处理tick效果
            tick_interval = buff.config.get("tick_interval", 0)
            if tick_interval > 0:
                buff.tick_timer -= dt
                if buff.tick_timer <= 0:
                    buff.tick_timer = tick_interval
                    # 持续伤害
                    dmg_pct = buff.config.get("damage_percent", 0)
                    if dmg_pct > 0 and hasattr(entity, 'max_hp'):
                        dmg = entity.max_hp * dmg_pct * buff.stacks
                        if hasattr(entity, 'take_damage'):
                            entity.take_damage(dmg, damage_type="dot")
                        damage_dealt += dmg
                    # 持续治疗
                    heal_pct = buff.config.get("heal_percent", 0)
                    if heal_pct > 0 and hasattr(entity, 'max_hp') and hasattr(entity, 'heal'):
                        entity.heal(entity.max_hp * heal_pct * buff.stacks)
            if buff.is_expired():
                expired.append(btype)
        for btype in expired:
            del self.buffs[btype]
        return damage_dealt

    # === 效果计算（所有乘区相乘）===
    def get_speed_mult(self):
        mult = 1.0
        for buff in self.buffs.values():
            mult *= buff.get_effect("speed_mult", 1.0)
        return mult

    def get_damage_mult(self):
        mult = 1.0
        for buff in self.buffs.values():
            mult *= buff.get_effect("damage_mult", 1.0)
        return mult

    def get_attack_speed_mult(self):
        mult = 1.0
        for buff in self.buffs.values():
            mult *= buff.get_effect("attack_speed_mult", 1.0)
        return mult

    def get_reload_speed_mult(self):
        mult = 1.0
        for buff in self.buffs.values():
            mult *= buff.get_effect("reload_speed_mult", 1.0)
        return mult

    def get_damage_taken_mult(self):
        mult = 1.0
        for buff in self.buffs.values():
            mult *= buff.get_effect("damage_taken_mult", 1.0)
        return mult

    def get_crit_chance_add(self):
        add = 0.0
        for buff in self.buffs.values():
            add += buff.get_flat_effect("crit_chance_add", 0.0)
        return add

    def is_stunned(self):
        for buff in self.buffs.values():
            if buff.config.get("stunned", False):
                return True
        return False

    def is_frozen(self):
        return BuffType.FREEZE in self.buffs

    def is_burning(self):
        return BuffType.BURN in self.buffs

    def is_bleeding(self):
        return BuffType.BLEED in self.buffs

    def get_active_buffs(self):
        """返回所有激活的buff列表"""
        return list(self.buffs.values())

    def clear(self):
        self.buffs.clear()

    def clear_debuffs(self):
        """清除所有负面buff"""
        to_remove = [bt for bt, b in self.buffs.items() if b.is_debuff]
        for bt in to_remove:
            del self.buffs[bt]
        return len(to_remove)
