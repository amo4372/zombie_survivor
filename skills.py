#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能系统模块 - 技能卡选择系统，带前置解锁条件、等级词条变化、属性详情"""
import random
from config import SkillType, RED, GREEN, ORANGE, YELLOW, PURPLE, CYAN, BLUE, GRAY, WHITE, CRIMSON, LIME, TEAL, RUST, POISON_GREEN, MUTED_GOLD


class Skill:
    def __init__(self, skill_type, name, description, max_level=5, current_level=0,
                 icon_color=WHITE, requires=None, is_active=False,
                 level_descriptions=None, effect_key=None, effect_per_level=None):
        self.skill_type = skill_type
        self.name = name
        self.description = description
        self.max_level = max_level
        self.current_level = current_level
        self.icon_color = icon_color
        self.requires = requires or []
        self.is_active = is_active
        # 等级词条：{等级: 描述}，高等级技能显示不同词条
        self.level_descriptions = level_descriptions or {}
        # 效果属性键（用于属性详情显示）
        self.effect_key = effect_key
        # 每级效果数值（用于计算属性变化）
        self.effect_per_level = effect_per_level

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

    def get_description(self):
        """根据当前等级获取描述词条（高等级有不同词条）"""
        if self.current_level in self.level_descriptions:
            return self.level_descriptions[self.current_level]
        return self.description

    def get_next_level_desc(self):
        """获取下一级的效果描述词条"""
        next_lv = self.current_level + 1
        if next_lv in self.level_descriptions:
            return self.level_descriptions[next_lv]
        return self.description

    def get_effect_value(self, level=None):
        """获取指定等级的效果数值"""
        if level is None:
            level = self.current_level
        if self.effect_per_level is not None:
            return self.effect_per_level * level
        return None

    def get_stat_change_text(self):
        """获取属性变化详情文本，返回 (原属性文本, 新属性文本) 或 None"""
        if self.effect_key is None or self.effect_per_level is None:
            return None
        old_val = self.effect_per_level * self.current_level
        new_val = self.effect_per_level * (self.current_level + 1)
        key = self.effect_key
        if key == "max_hp":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "speed":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "damage":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "fire_rate":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "reload_speed":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "crit_chance":
            return (f"{5 + old_val * 100:.0f}%", f"{5 + new_val * 100:.0f}%")
        elif key == "crit_damage":
            return (f"{150 + old_val * 100:.0f}%", f"{150 + new_val * 100:.0f}%")
        elif key == "life_steal":
            return (f"{old_val * 100:.0f}%", f"{new_val * 100:.0f}%")
        elif key == "pickup_range":
            return (f"{80 + old_val:.0f}", f"{80 + new_val:.0f}")
        elif key == "exp_mult":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "cooldown":
            return (f"{100 - old_val * 100:.0f}%", f"{100 - new_val * 100:.0f}%")
        elif key == "armor":
            return (f"{old_val * 100:.0f}%", f"{new_val * 100:.0f}%")
        elif key == "dodge":
            return (f"{old_val * 100:.0f}%", f"{new_val * 100:.0f}%")
        elif key == "regen":
            return (f"{old_val * 100:.1f}%/s", f"{new_val * 100:.1f}%/s")
        return None


class SkillTree:
    def __init__(self):
        self.skills = self._create_skills()
        self.skill_points = 0
        self._skill_pool = []

    def _create_skills(self):
        return [
            # === 被动技能 ===
            Skill(SkillType.HEALTH_UP, "生命强化", "最大生命值+20%", 99, icon_color=RED,
                  level_descriptions={1: "体魄强健：最大生命+20%", 2: "钢筋铁骨：最大生命+40%",
                                      3: "铜皮铁骨：最大生命+60%", 4: "不灭之躯：最大生命+80%",
                                      5: "泰坦血脉：最大生命+100%"},
                  effect_key="max_hp", effect_per_level=0.2),
            Skill(SkillType.SPEED_UP, "速度强化", "移动速度+10%", 99, icon_color=GREEN,
                  level_descriptions={1: "疾步：移动速度+10%", 2: "风行者：移动速度+20%",
                                      3: "闪电疾走：移动速度+30%", 4: "瞬息千里：移动速度+40%",
                                      5: "幻影步法：移动速度+50%"},
                  effect_key="speed", effect_per_level=0.1),
            Skill(SkillType.DAMAGE_UP, "伤害强化", "武器伤害+15%", 99, icon_color=ORANGE,
                  level_descriptions={1: "锐利：武器伤害+15%", 2: "锋刃：武器伤害+30%",
                                      3: "破甲：武器伤害+45%", 4: "毁灭：武器伤害+60%",
                                      5: "湮灭：武器伤害+75%"},
                  effect_key="damage", effect_per_level=0.15),
            Skill(SkillType.FIRE_RATE_UP, "射速强化", "攻击速度+10%", 99, icon_color=YELLOW,
                  level_descriptions={1: "快手：攻击速度+10%", 2: "连发：攻击速度+20%",
                                      3: "弹幕：攻击速度+30%", 4: "倾泻：攻击速度+40%",
                                      5: "风暴：攻击速度+50%"},
                  effect_key="fire_rate", effect_per_level=0.1),
            Skill(SkillType.RELOAD_SPEED, "快速换弹", "换弹速度+15%", 99, icon_color=CYAN,
                  requires=[(SkillType.FIRE_RATE_UP, 1)],
                  level_descriptions={1: "熟练装填：换弹速度+15%", 2: "战术换弹：换弹速度+30%",
                                      3: "极速装填：换弹速度+45%", 4: "闪电换弹：换弹速度+60%",
                                      5: "弹匣大师：换弹速度+75%"},
                  effect_key="reload_speed", effect_per_level=0.15),
            Skill(SkillType.CRIT_CHANCE, "暴击率", "暴击几率+5%", 99, icon_color=PURPLE,
                  requires=[(SkillType.DAMAGE_UP, 1)],
                  level_descriptions={1: "精准：暴击率+5%", 2: "致命：暴击率+10%",
                                      3: "绝杀：暴击率+15%", 4: "死神之眼：暴击率+20%",
                                      5: "必中要害：暴击率+25%"},
                  effect_key="crit_chance", effect_per_level=0.05),
            Skill(SkillType.CRIT_DAMAGE, "暴击伤害", "暴击伤害+25%", 99, icon_color=PURPLE,
                  requires=[(SkillType.CRIT_CHANCE, 1)],
                  level_descriptions={1: "重击：暴击伤害+25%", 2: "重创：暴击伤害+50%",
                                      3: "致命一击：暴击伤害+75%", 4: "毁天灭地：暴击伤害+100%",
                                      5: "诸神黄昏：暴击伤害+125%"},
                  effect_key="crit_damage", effect_per_level=0.25),
            Skill(SkillType.LIFE_STEAL, "生命偷取", "造成伤害的3%转化为生命", 99, icon_color=RED,
                  requires=[(SkillType.HEALTH_UP, 1)],
                  level_descriptions={1: "吸血：伤害3%回血", 2: "汲取：伤害6%回血",
                                      3: "血祭：伤害9%回血", 4: "血怒：伤害12%回血",
                                      5: "血魔：伤害15%回血"},
                  effect_key="life_steal", effect_per_level=0.03),
            Skill(SkillType.PICKUP_RANGE, "拾取范围", "经验/道具拾取范围+25", 99, icon_color=CYAN,
                  requires=[(SkillType.SPEED_UP, 1)],
                  level_descriptions={1: "磁吸：拾取范围+25", 2: "引力：拾取范围+50",
                                      3: "黑洞：拾取范围+75", 4: "奇点：拾取范围+100",
                                      5: "万物归宗：拾取范围+125"},
                  effect_key="pickup_range", effect_per_level=25),
            Skill(SkillType.EXP_BOOST, "经验加成", "获得经验+15%", 99, icon_color=CYAN,
                  requires=[(SkillType.PICKUP_RANGE, 1)],
                  level_descriptions={1: "好学：经验+15%", 2: "勤奋：经验+30%",
                                      3: "顿悟：经验+45%", 4: "开窍：经验+60%",
                                      5: "醍醐灌顶：经验+75%"},
                  effect_key="exp_mult", effect_per_level=0.15),
            Skill(SkillType.COOLDOWN_REDUCTION, "冷却缩减", "技能冷却-10%", 99, icon_color=BLUE,
                  requires=[(SkillType.FIRE_RATE_UP, 1)],
                  level_descriptions={1: "冷静：技能冷却-10%", 2: "迅捷：技能冷却-20%",
                                      3: "极速：技能冷却-30%", 4: "瞬发：技能冷却-40%",
                                      5: "无冷却：技能冷却-50%"},
                  effect_key="cooldown", effect_per_level=0.1),
            Skill(SkillType.ARMOR_UP, "护甲强化", "受到伤害-8%", 99, icon_color=GRAY,
                  level_descriptions={1: "皮甲：减伤8%", 2: "锁甲：减伤16%",
                                      3: "板甲：减伤24%", 4: "重甲：减伤32%",
                                      5: "金刚不坏：减伤40%"},
                  effect_key="armor", effect_per_level=0.08),
            Skill(SkillType.REGENERATION, "生命恢复", "每秒恢复1%最大生命值", 99, icon_color=GREEN,
                  requires=[(SkillType.HEALTH_UP, 2)],
                  level_descriptions={1: "自愈：每秒回血1%", 2: "恢复：每秒回血2%",
                                      3: "再生：每秒回血3%", 4: "不死：每秒回血4%",
                                      5: "永生：每秒回血5%"},
                  effect_key="regen", effect_per_level=0.01),
            Skill(SkillType.DODGE_CHANCE, "闪避", "有5%几率完全闪避攻击", 99, icon_color=LIME,
                  requires=[(SkillType.SPEED_UP, 2)],
                  level_descriptions={1: "灵巧：闪避5%", 2: "敏捷：闪避10%",
                                      3: "飘忽：闪避15%", 4: "幻影：闪避20%",
                                      5: "无形：闪避25%"},
                  effect_key="dodge", effect_per_level=0.05),
            Skill(SkillType.VAMPIRE_AURA, "吸血光环", "击杀敌人时恢复5%生命", 3, icon_color=RUST,
                  requires=[(SkillType.LIFE_STEAL, 2)]),
            Skill(SkillType.FORTRESS, "不动堡垒", "静止不动时受到伤害-30%", 3, icon_color=TEAL,
                  requires=[(SkillType.ARMOR_UP, 2)]),
            # === 主动技能 ===
            Skill(SkillType.DASH, "冲刺", "快速向一个方向冲刺，获得短暂无敌", 3, icon_color=BLUE,
                  requires=[(SkillType.SPEED_UP, 1)], is_active=True),
            Skill(SkillType.GRENADE, "手雷", "投掷爆炸手雷，造成范围伤害", 3, icon_color=ORANGE,
                  requires=[(SkillType.DAMAGE_UP, 1)], is_active=True),
            Skill(SkillType.TURRET, "自动炮塔", "部署自动攻击炮塔，持续10秒", 3, icon_color=GRAY,
                  requires=[(SkillType.FIRE_RATE_UP, 1)], is_active=True),
            Skill(SkillType.AIRSTRIKE, "空袭", "呼叫空袭轰炸指定区域", 3, icon_color=RED,
                  requires=[(SkillType.GRENADE, 1)], is_active=True),
            Skill(SkillType.SHIELD_BASH, "盾牌肘击", "使用防爆盾进行强力肘击并击退敌人", 3, icon_color=BLUE,
                  requires=[(SkillType.RIOT_GEAR, 1)], is_active=True),
            Skill(SkillType.GRAPPLE_PULL, "钩爪牵引", "发射钩爪抓取敌人或道具", 3, icon_color=GREEN,
                  requires=[(SkillType.DASH, 1)], is_active=True),
            Skill(SkillType.TIME_SLOW, "时间减缓", "短时间内大幅减缓周围时间", 3, icon_color=PURPLE,
                  requires=[(SkillType.COOLDOWN_REDUCTION, 1)], is_active=True),
            Skill(SkillType.OVERLOAD, "超载模式", "短时间内伤害翻倍但受到伤害+50%", 3, icon_color=RED,
                  requires=[(SkillType.CRIT_DAMAGE, 1)], is_active=True),
            Skill(SkillType.RIOT_GEAR, "防爆套装", "解锁防爆盾牌、肘击和钩爪系统", 1, icon_color=BLUE,
                  requires=[(SkillType.HEALTH_UP, 2)], is_active=True),
            Skill(SkillType.STEEL_WILL, "钢铁意志", "生命值低于30%时获得大幅减伤", 3, icon_color=CRIMSON,
                  requires=[(SkillType.HEALTH_UP, 3)], is_active=True),
            Skill(SkillType.BLINK, "闪烁", "瞬移到鼠标/瞄准方向位置", 3, icon_color=CYAN,
                  requires=[(SkillType.DASH, 2)], is_active=True),
            Skill(SkillType.BLACK_HOLE, "黑洞", "在指定位置生成黑洞吸引敌人", 3, icon_color=PURPLE,
                  requires=[(SkillType.GRENADE, 2)], is_active=True),
            Skill(SkillType.ICE_NOVA, "冰霜新星", "冻结周围所有敌人2秒", 3, icon_color=BLUE,
                  requires=[(SkillType.TIME_SLOW, 1)], is_active=True),
            Skill(SkillType.CHAIN_LIGHTNING, "连锁闪电", "释放闪电在敌人间弹射", 3, icon_color=YELLOW,
                  requires=[(SkillType.CRIT_CHANCE, 2)], is_active=True),
            Skill(SkillType.BERSERK, "狂暴", "攻速翻倍，受到伤害+30%", 3, icon_color=RED,
                  requires=[(SkillType.OVERLOAD, 1)], is_active=True),
            Skill(SkillType.PHANTOM_STRIKE, "幻影打击", "召唤3个幻影分身同时攻击", 3, icon_color=LIME,
                  requires=[(SkillType.DODGE_CHANCE, 2)], is_active=True),
            Skill(SkillType.MEDIC_POD, "医疗舱", "部署持续回血区域", 3, icon_color=GREEN,
                  requires=[(SkillType.REGENERATION, 1)], is_active=True),
            Skill(SkillType.SHOCKWAVE, "冲击波", "推开周围所有敌人并造成伤害", 3, icon_color=ORANGE,
                  requires=[(SkillType.SHIELD_BASH, 1)], is_active=True),
            # === Buff相关技能 ===
            Skill(SkillType.FLAME_ENCHANT, "火焰附魔", "攻击有20%几率使敌人燃烧", 5, icon_color=ORANGE,
                  requires=[(SkillType.DAMAGE_UP, 1)],
                  level_descriptions={1: "火花：20%几率燃烧3秒", 2: "烈焰：30%几率燃烧4秒",
                                      3: "狱火：40%几率燃烧5秒", 4: "焚天：50%几率燃烧6秒",
                                      5: "凤凰之焰：60%几率燃烧8秒"},
                  effect_key="damage", effect_per_level=0.0),
            Skill(SkillType.FROST_ENCHANT, "冰霜附魔", "攻击有20%几率使敌人减速", 5, icon_color=CYAN,
                  requires=[(SkillType.FIRE_RATE_UP, 1)],
                  level_descriptions={1: "寒霜：20%几率减速3秒", 2: "冰刺：30%几率减速4秒",
                                      3: "冰封：40%几率减速5秒", 4: "极寒：50%几率冻结2秒",
                                      5: "绝对零度：60%几率冻结3秒"},
                  effect_key="damage", effect_per_level=0.0),
            Skill(SkillType.POISON_ENCHANT, "剧毒附魔", "攻击有15%几率使敌人中毒", 5, icon_color=POISON_GREEN,
                  requires=[(SkillType.CRIT_CHANCE, 1)],
                  level_descriptions={1: "蛇毒：15%几率中毒5秒", 2: "蝎毒：25%几率中毒6秒",
                                      3: "蛛毒：35%几率中毒7秒", 4: "蛊毒：45%几率中毒8秒",
                                      5: "鸩毒：55%几率中毒10秒"},
                  effect_key="damage", effect_per_level=0.0),
            Skill(SkillType.BLOODLUST, "嗜血", "击杀敌人后获得短暂加速", 3, icon_color=CRIMSON,
                  requires=[(SkillType.LIFE_STEAL, 1)],
                  level_descriptions={1: "饥渴：击杀后加速20%持续3秒", 2: "狂热：击杀后加速35%持续4秒",
                                      3: "嗜血狂魔：击杀后加速50%持续5秒"},
                  effect_key="speed", effect_per_level=0.0),
            Skill(SkillType.ELEMENTAL_MASTERY, "元素精通", "所有施加的debuff效果+30%", 3, icon_color=PURPLE,
                  requires=[(SkillType.FLAME_ENCHANT, 1), (SkillType.FROST_ENCHANT, 1)],
                  level_descriptions={1: "元素亲和：debuff效果+30%", 2: "元素掌控：debuff效果+60%",
                                      3: "元素主宰：debuff效果+100%"},
                  effect_key="damage", effect_per_level=0.0),
            Skill(SkillType.WAR_CRY, "战吼", "获得伤害+攻速+护盾三重buff", 3, icon_color=GOLD if 'GOLD' in dir() else YELLOW,
                  requires=[(SkillType.BERSERK, 1)], is_active=True,
                  level_descriptions={1: "怒吼：伤害+50%攻速+30%护盾5秒", 2: "战吼：伤害+80%攻速+50%护盾7秒",
                                      3: "战神降临：伤害+120%攻速+80%护盾10秒"}),
            Skill(SkillType.PURIFY, "净化", "清除所有debuff并获得短暂无敌", 3, icon_color=WHITE,
                  requires=[(SkillType.REGENERATION, 2)], is_active=True,
                  level_descriptions={1: "净化：清除debuff+无敌2秒", 2: "圣洁：清除debuff+无敌3秒+回血30%",
                                      3: "神圣庇护：清除debuff+无敌5秒+满血"}),
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
                weights.append(3.0)
            else:
                weights.append(1.0)
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
