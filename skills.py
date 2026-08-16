#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能系统模块 - 技能卡选择系统，带前置解锁条件"""

import random
from config import SkillType, RED, GREEN, ORANGE, YELLOW, PURPLE, CYAN, BLUE, GRAY, WHITE, CRIMSON, LIME, TEAL, RUST, POISON_GREEN, MUTED_GOLD

class Skill:
    def __init__(self, skill_type, name, description, max_level=5, current_level=0, icon_color=WHITE, requires=None, is_active=False):
        self.skill_type = skill_type
        self.name = name
        self.description = description
        self.max_level = max_level
        self.current_level = current_level
        self.icon_color = icon_color
        self.requires = requires or []  # 前置技能要求 [(SkillType, min_level), ...]
        self.is_active = is_active  # 是否为主动技能

    def is_maxed(self):
        return self.current_level >= self.max_level

    def can_upgrade(self, player_skills):
        if self.is_maxed():
            return False
        for req_type, req_level in self.requires:
            found = False
            for ps in player_skills:
                if ps.skill_type == req_type and ps.current_level >= req_level:
                    found = True
                    break
            if not found:
                return False
        return True

    def get_next_level_desc(self):
        """获取下一级的效果描述"""
        return self.description


class SkillTree:
    def __init__(self):
        self.skills = self._create_skills()
        self.skill_points = 0
        self._skill_pool = []  # 用于随机选择的技能池

    def _create_skills(self):
        return [
            # === 被动技能 ===
            Skill(SkillType.HEALTH_UP, "生命强化", "最大生命值+20%", 5, icon_color=RED),
            Skill(SkillType.SPEED_UP, "速度强化", "移动速度+10%", 5, icon_color=GREEN),
            Skill(SkillType.DAMAGE_UP, "伤害强化", "武器伤害+15%", 5, icon_color=ORANGE),
            Skill(SkillType.FIRE_RATE_UP, "射速强化", "攻击速度+10%", 5, icon_color=YELLOW),
            Skill(SkillType.CRIT_CHANCE, "暴击率", "暴击几率+5%", 5, icon_color=PURPLE, requires=[(SkillType.DAMAGE_UP, 1)]),
            Skill(SkillType.CRIT_DAMAGE, "暴击伤害", "暴击伤害+25%", 5, icon_color=PURPLE, requires=[(SkillType.CRIT_CHANCE, 1)]),
            Skill(SkillType.LIFE_STEAL, "生命偷取", "造成伤害的3%转化为生命", 5, icon_color=RED, requires=[(SkillType.HEALTH_UP, 1)]),
            Skill(SkillType.PICKUP_RANGE, "拾取范围", "经验/道具拾取范围+25%", 5, icon_color=CYAN, requires=[(SkillType.SPEED_UP, 1)]),
            Skill(SkillType.EXP_BOOST, "经验加成", "获得经验+15%", 5, icon_color=CYAN, requires=[(SkillType.PICKUP_RANGE, 1)]),
            Skill(SkillType.COOLDOWN_REDUCTION, "冷却缩减", "技能冷却-10%", 5, icon_color=BLUE, requires=[(SkillType.FIRE_RATE_UP, 1)]),
            Skill(SkillType.ARMOR_UP, "护甲强化", "受到伤害-8%", 5, icon_color=GRAY),
            Skill(SkillType.REGENERATION, "生命恢复", "每秒恢复1%最大生命值", 5, icon_color=GREEN, requires=[(SkillType.HEALTH_UP, 2)]),
            Skill(SkillType.DODGE_CHANCE, "闪避", "有5%几率完全闪避攻击", 5, icon_color=LIME, requires=[(SkillType.SPEED_UP, 2)]),
            Skill(SkillType.VAMPIRE_AURA, "吸血光环", "击杀敌人时恢复5%生命", 3, icon_color=RUST, requires=[(SkillType.LIFE_STEAL, 2)]),
            Skill(SkillType.FORTRESS, "不动堡垒", "静止不动时受到伤害-30%", 3, icon_color=TEAL, requires=[(SkillType.ARMOR_UP, 2)]),

            # === 主动技能 ===
            Skill(SkillType.DASH, "冲刺", "快速向一个方向冲刺，获得短暂无敌", 3, icon_color=BLUE, requires=[(SkillType.SPEED_UP, 1)], is_active=True),
            Skill(SkillType.GRENADE, "手雷", "投掷爆炸手雷，造成范围伤害", 3, icon_color=ORANGE, requires=[(SkillType.DAMAGE_UP, 1)], is_active=True),
            Skill(SkillType.TURRET, "自动炮塔", "部署自动攻击炮塔，持续10秒", 3, icon_color=GRAY, requires=[(SkillType.FIRE_RATE_UP, 1)], is_active=True),
            Skill(SkillType.AIRSTRIKE, "空袭", "呼叫空袭轰炸指定区域", 3, icon_color=RED, requires=[(SkillType.GRENADE, 1)], is_active=True),
            Skill(SkillType.SHIELD_BASH, "盾牌肘击", "使用防爆盾进行强力肘击并击退敌人", 3, icon_color=BLUE, requires=[(SkillType.RIOT_GEAR, 1)], is_active=True),
            Skill(SkillType.GRAPPLE_PULL, "钩爪牵引", "发射钩爪抓取敌人或道具", 3, icon_color=GREEN, requires=[(SkillType.DASH, 1)], is_active=True),
            Skill(SkillType.TIME_SLOW, "时间减缓", "短时间内大幅减缓周围时间", 3, icon_color=PURPLE, requires=[(SkillType.COOLDOWN_REDUCTION, 1)], is_active=True),
            Skill(SkillType.OVERLOAD, "超载模式", "短时间内伤害翻倍但受到伤害+50%", 3, icon_color=RED, requires=[(SkillType.CRIT_DAMAGE, 1)], is_active=True),
            Skill(SkillType.RIOT_GEAR, "防爆套装", "解锁防爆盾牌、肘击和钩爪系统", 1, icon_color=BLUE, requires=[(SkillType.HEALTH_UP, 2)], is_active=True),
            Skill(SkillType.STEEL_WILL, "钢铁意志", "生命值低于30%时获得大幅减伤", 3, icon_color=CRIMSON, requires=[(SkillType.HEALTH_UP, 3)], is_active=True),
            Skill(SkillType.BLINK, "闪烁", "瞬移到鼠标/瞄准方向位置", 3, icon_color=CYAN, requires=[(SkillType.DASH, 2)], is_active=True),
            Skill(SkillType.BLACK_HOLE, "黑洞", "在指定位置生成黑洞吸引敌人", 3, icon_color=PURPLE, requires=[(SkillType.GRENADE, 2)], is_active=True),
            Skill(SkillType.ICE_NOVA, "冰霜新星", "冻结周围所有敌人2秒", 3, icon_color=BLUE, requires=[(SkillType.TIME_SLOW, 1)], is_active=True),
            Skill(SkillType.CHAIN_LIGHTNING, "连锁闪电", "释放闪电在敌人间弹射", 3, icon_color=YELLOW, requires=[(SkillType.CRIT_CHANCE, 2)], is_active=True),
            Skill(SkillType.BERSERK, "狂暴", "攻速翻倍，受到伤害+30%", 3, icon_color=RED, requires=[(SkillType.OVERLOAD, 1)], is_active=True),
            Skill(SkillType.PHANTOM_STRIKE, "幻影打击", "召唤3个幻影分身同时攻击", 3, icon_color=LIME, requires=[(SkillType.DODGE_CHANCE, 2)], is_active=True),
            Skill(SkillType.MEDIC_POD, "医疗舱", "部署持续回血区域", 3, icon_color=GREEN, requires=[(SkillType.REGENERATION, 1)], is_active=True),
            Skill(SkillType.SHOCKWAVE, "冲击波", "推开周围所有敌人并造成伤害", 3, icon_color=ORANGE, requires=[(SkillType.SHIELD_BASH, 1)], is_active=True),
        ]

    def get_skill(self, skill_type):
        for s in self.skills:
            if s.skill_type == skill_type:
                return s
        return None

    def upgrade_skill(self, skill_type):
        skill = self.get_skill(skill_type)
        if skill and skill.can_upgrade(self.skills) and self.skill_points > 0:
            skill.current_level += 1
            self.skill_points -= 1
            return True
        return False

    def get_available_skills(self):
        """获取当前可升级的技能列表"""
        available = []
        for skill in self.skills:
            if not skill.is_maxed() and skill.can_upgrade(self.skills):
                available.append(skill)
        return available

    def get_random_skill_cards(self, count=3):
        """随机获取技能卡供选择"""
        available = self.get_available_skills()
        if len(available) <= count:
            return available
        # 权重：未解锁的技能权重更高
        weights = []
        for skill in available:
            if skill.current_level == 0:
                weights.append(3.0)  # 新技能权重高
            else:
                weights.append(1.0)
        # 使用加权随机选择
        selected = []
        temp_available = available.copy()
        temp_weights = weights.copy()
        while len(selected) < count and temp_available:
            total = sum(temp_weights)
            if total == 0:
                break
            r = random.uniform(0, total)
            cumsum = 0
            for i, (skill, w) in enumerate(zip(temp_available, temp_weights)):
                cumsum += w
                if r <= cumsum:
                    selected.append(skill)
                    temp_available.pop(i)
                    temp_weights.pop(i)
                    break
        return selected

    def get_unlocked_active_skills(self):
        """获取已解锁的主动技能"""
        unlocked = []
        for skill in self.skills:
            if skill.is_active and skill.current_level > 0:
                unlocked.append(skill.skill_type)
        return unlocked
