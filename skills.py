#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能系统模块 - 技能卡选择系统，带前置解锁条件、等级词条变化、属性详情"""
import random
from config import *


class Skill:
    def __init__(self, skill_type, name, description, max_level=5, current_level=0,
                 icon_color=WHITE, requires=None, is_active=False,
                 level_descriptions=None, effect_key=None, effect_per_level=None,
                 weight=1.0, base_damage=0, damage_per_level=0,
                 base_radius=0, radius_per_level=0, max_level_bonus=None):
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
        # 刷新权重（爆率系统，数值越高越常见）
        self.weight = weight
        # AoE技能伤害/半径缩放
        self.base_damage = base_damage
        self.damage_per_level = damage_per_level
        self.base_radius = base_radius
        self.radius_per_level = radius_per_level
        # 满级特殊效果描述
        self.max_level_bonus = max_level_bonus

    def get_effective_damage(self):
        """获取当前等级的技能伤害（AoE技能）"""
        if self.current_level <= 0:
            return self.base_damage
        return self.base_damage + self.damage_per_level * self.current_level

    def get_effective_radius(self):
        """获取当前等级的技能影响半径"""
        if self.current_level <= 0:
            return self.base_radius
        return self.base_radius + self.radius_per_level * self.current_level

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
        elif key == "stamina":
            return (f"{100 + old_val:.0f}", f"{100 + new_val:.0f}")
        elif key == "melee_damage":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "melee_range":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "melee_speed":
            return (f"{100 + old_val * 100:.0f}%", f"{100 + new_val * 100:.0f}%")
        elif key == "melee_lifesteal":
            return (f"{old_val * 100:.0f}%", f"{new_val * 100:.0f}%")
        elif key == "berserker":
            return (f"+{old_val * 100:.0f}%", f"+{new_val * 100:.0f}%")
        elif key == "combo":
            return (f"每层+{old_val * 100:.0f}%", f"每层+{new_val * 100:.0f}%")
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
                  effect_key="fire_rate", effect_per_level=0.1, requires=[(SkillType.DAMAGE_UP, 1)]),
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
                  effect_key="armor", effect_per_level=0.08, requires=[(SkillType.HEALTH_UP, 1)]),
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
            # === 近战专属技能 ===
            Skill(SkillType.MELEE_DAMAGE, "近战精通", "近战武器伤害+25%", 5, icon_color=CRIMSON,
                  level_descriptions={1: "利刃：近战伤害+25%", 2: "嗜血：近战伤害+50%",
                                      3: "狂暴：近战伤害+75%", 4: "屠戮：近战伤害+100%",
                                      5: "战神：近战伤害+150%"},
                  effect_key="melee_damage", effect_per_level=0.25),
            Skill(SkillType.MELEE_RANGE, "长臂", "近战攻击范围+15%", 3, icon_color=ORANGE,
                  requires=[(SkillType.MELEE_DAMAGE, 1)],
                  level_descriptions={1: "伸展：近战范围+15%", 2: "长臂：近战范围+30%",
                                      3: "触不可及：近战范围+50%"},
                  effect_key="melee_range", effect_per_level=0.15),
            Skill(SkillType.MELEE_SPEED, "疾风斩", "近战攻击速度+20%", 3, icon_color=YELLOW,
                  requires=[(SkillType.MELEE_DAMAGE, 1)],
                  level_descriptions={1: "快斩：近战攻速+20%", 2: "疾风：近战攻速+40%",
                                      3: "残影：近战攻速+60%"},
                  effect_key="melee_speed", effect_per_level=0.2),
            Skill(SkillType.MELEE_LIFESTEAL, "吸血斩", "近战攻击造成伤害的10%转化为生命", 3, icon_color=RED,
                  requires=[(SkillType.MELEE_DAMAGE, 2)],
                  level_descriptions={1: "吸血：10%生命偷取", 2: "嗜血：20%生命偷取",
                                      3: "汲取：35%生命偷取"},
                  effect_key="melee_lifesteal", effect_per_level=0.1),
            Skill(SkillType.BERSERKER, "狂暴", "生命值低于50%时，近战伤害+30%", 3, icon_color=BLOOD_RED,
                  requires=[(SkillType.MELEE_DAMAGE, 2), (SkillType.HEALTH_UP, 2)],
                  level_descriptions={1: "狂战士：半血以下近战+30%", 2: "浴血：半血以下近战+60%",
                                      3: "不死不休：半血以下近战+100%，20%血以下额外+50%"},
                  effect_key="berserker", effect_per_level=0.30),
            Skill(SkillType.COMBO_MASTER, "连击大师", "连续近战攻击每次叠加5%伤害，最多5层", 3, icon_color=PURPLE,
                  requires=[(SkillType.MELEE_SPEED, 1)],
                  level_descriptions={1: "连击：每层+5%伤害，最多5层", 2: "连招：每层+8%伤害，最多8层",
                                      3: "无限连击：每层+10%伤害，最多10层"},
                  effect_key="combo", effect_per_level=0.05),
            # === 主动技能（全部5级上限，高级解锁额外效果）===
            Skill(SkillType.DASH, "冲刺", "快速向一个方向冲刺，获得短暂无敌", 5, icon_color=BLUE,
                  requires=[(SkillType.SPEED_UP, 1)], is_active=True,
                  level_descriptions={1: "短距冲刺：距离8m，无敌0.3秒", 2: "强化冲刺：距离12m，无敌0.5秒，冷却-20%",
                                      3: "疾风步：距离16m，无敌0.7秒，可穿越敌人", 4: "影袭：距离20m，无敌1秒，穿越时对敌人造成伤害",
                                      5: "次元跳跃：距离25m，无敌1.5秒，穿越造成范围伤害+短暂残影迷惑敌人"}),
            Skill(SkillType.GRENADE, "手雷", "投掷爆炸手雷，造成范围伤害。升级可解锁附魔：火焰/冰霜/剧毒/核弹", 5, icon_color=ORANGE,
                  requires=[(SkillType.DAMAGE_UP, 1)], is_active=True, weight=2.0,
                  base_damage=250, damage_per_level=50, base_radius=180, radius_per_level=20,
                  max_level_bonus="核弹：范围+50%，附加燃烧+减速+中毒三重效果",
                  level_descriptions={1: "破片手雷：普通范围爆炸", 2: "燃烧附魔：爆炸后留下燃烧区域",
                                      3: "冰霜附魔：爆炸减速敌人50%，持续3秒", 4: "剧毒附魔：爆炸施加中毒，持续掉血",
                                      5: "核弹附魔：超大范围爆炸+燃烧+减速+中毒三重效果"}),
            Skill(SkillType.TURRET, "自动炮塔", "部署自动攻击炮塔，持续10秒", 5, icon_color=GRAY,
                  requires=[(SkillType.FIRE_RATE_UP, 1)], is_active=True, weight=2.0,
                  base_damage=15, damage_per_level=8, base_radius=200, radius_per_level=20,
                  max_level_bonus="双管炮塔：同时攻击2个目标+伤害+50%",
                  level_descriptions={1: "单管炮塔：攻击1目标，持续10秒", 2: "强化炮塔：伤害+30%，持续12秒",
                                      3: "速射炮塔：攻速+50%，持续15秒", 4: "双管炮塔：同时攻击2目标，伤害+50%",
                                      5: "毁灭者炮塔：同时攻击3目标，伤害+100%，持续20秒，攻击附带燃烧"}),
            Skill(SkillType.AIRSTRIKE, "空袭", "呼叫空袭轰炸指定区域，持续多轮轰炸", 5, icon_color=RED,
                  requires=[(SkillType.GRENADE, 1)], is_active=True, weight=1.0,
                  base_damage=350, damage_per_level=80, base_radius=180, radius_per_level=25,
                  max_level_bonus="超级核爆：3轮持续轰炸+超大范围+屏幕震动",
                  level_descriptions={1: "单轮空袭：1轮轰炸，中等范围", 2: "双轮空袭：2轮轰炸，范围+20%",
                                      3: "地毯式轰炸：3轮轰炸，范围+40%，附带燃烧", 4: "精准打击：4轮轰炸，范围+60%，每轮伤害递增",
                                      5: "超级核爆：5轮持续轰炸+超大范围+屏幕剧烈震动+辐射区域持续伤害"}),
            Skill(SkillType.SHIELD_BASH, "盾牌肘击", "使用防爆盾进行强力肘击并击退敌人", 5, icon_color=BLUE,
                  requires=[(SkillType.RIOT_GEAR, 1)], is_active=True,
                  level_descriptions={1: "盾击：击退敌人，造成基础伤害", 2: "重击：击退距离+50%，伤害+30%",
                                      3: "盾冲：可蓄力，满蓄力眩晕1秒", 4: "雷霆盾击：攻击附带闪电，连锁3个敌人",
                                      5: "神圣制裁：超大范围击退+眩晕2秒+伤害+100%+破甲效果"}),
            Skill(SkillType.GRAPPLE_PULL, "钩爪牵引", "发射钩爪抓取敌人/道具/地形，独立技能无需防爆套装", 5, icon_color=GREEN,
                  requires=[], is_active=True, weight=2.0,
                  level_descriptions={1: "基础钩爪：射程15m，可抓取道具和小型敌人",
                                      2: "强化钩爪：射程20m，可抓取中型敌人，抓取速度+30%",
                                      3: "战斗钩爪：射程25m，可抓取所有敌人，拉回时造成撞击伤害",
                                      4: "闪电钩爪：射程30m，命中后敌人眩晕1秒，可连续发射2次",
                                      5: "湮灭钩爪：射程40m，拉回敌人造成范围爆炸，可连续发射3次，命中即秒杀小怪"}),
            Skill(SkillType.TIME_SLOW, "时间减缓", "短时间内大幅减缓周围时间", 5, icon_color=PURPLE,
                  requires=[(SkillType.COOLDOWN_REDUCTION, 1)], is_active=True,
                  level_descriptions={1: "时间减速：敌人速度-40%，持续3秒", 2: "时间停滞：敌人速度-60%，持续4秒",
                                      3: "时间冻结：敌人速度-80%，持续5秒，玩家攻速+30%", 4: "时空裂隙：敌人速度-90%，持续6秒，玩家伤害+30%",
                                      5: "时间停止：敌人完全静止2秒后减速90%共8秒，玩家全属性+50%"}),
            Skill(SkillType.OVERLOAD, "超载模式", "短时间内伤害翻倍但受到伤害+50%", 5, icon_color=RED,
                  requires=[(SkillType.CRIT_DAMAGE, 1)], is_active=True,
                  level_descriptions={1: "超载：伤害x2，受伤+50%，持续5秒", 2: "强超载：伤害x2.5，受伤+40%，持续6秒",
                                      3: "极限超载：伤害x3，受伤+30%，持续7秒，攻速+30%", 4: "过载爆发：伤害x3.5，受伤+20%，持续8秒，移速+30%",
                                      5: "神化：伤害x4，无受伤惩罚，持续10秒，全属性+50%，击杀回血"}),
            Skill(SkillType.RIOT_GEAR, "防爆套装", "解锁防爆盾牌、肘击系统（钩爪已独立）", 1, icon_color=BLUE,
                  requires=[(SkillType.HEALTH_UP, 2)], is_active=True),
            Skill(SkillType.STEEL_WILL, "钢铁意志", "生命值低于30%时获得大幅减伤", 5, icon_color=CRIMSON,
                  requires=[(SkillType.HEALTH_UP, 3)], is_active=True,
                  level_descriptions={1: "坚韧：30%血以下减伤30%", 2: "不屈：30%血以下减伤45%，20%血以下额外+15%",
                                      3: "钢铁：30%血以下减伤60%，10%血以下免疫即死", 4: "不灭：30%血以下减伤75%，每秒回复2%最大生命",
                                      5: "泰坦之躯：30%血以下减伤90%，受到攻击有50%几率完全免疫，血量越低越强"}),
            Skill(SkillType.BLINK, "闪烁", "瞬移到鼠标/瞄准方向位置", 5, icon_color=CYAN,
                  requires=[(SkillType.DASH, 2)], is_active=True,
                  level_descriptions={1: "短距闪烁：距离10m，冷却8秒", 2: "中距闪烁：距离15m，冷却6秒，瞬移后短暂隐身",
                                      3: "长距闪烁：距离20m，冷却5秒，瞬移后攻速+50%持续2秒", 4: "双重闪烁：距离25m，可连续闪烁2次，每次留下幻影",
                                      5: "空间折跃：距离35m，可连续闪烁3次，闪烁路径上的敌人受到伤害并被标记"}),
            Skill(SkillType.BLACK_HOLE, "黑洞", "在指定位置生成黑洞吸引敌人", 5, icon_color=PURPLE,
                  requires=[(SkillType.GRENADE, 2)], is_active=True, weight=1.0,
                  base_damage=30, damage_per_level=15, base_radius=80, radius_per_level=20,
                  max_level_bonus="奇点：吸引范围+100%，持续时间翻倍",
                  level_descriptions={1: "微型黑洞：吸引范围80，持续3秒，造成少量伤害", 2: "小型黑洞：范围100，持续4秒，伤害+50%",
                                      3: "中型黑洞：范围120，持续5秒，吸引强度+50%", 4: "大型黑洞：范围150，持续6秒，敌人无法挣脱",
                                      5: "奇点：范围200，持续8秒，吸引强度翻倍，结束时爆炸造成巨额伤害"}),
            Skill(SkillType.ICE_NOVA, "冰霜新星", "冻结周围所有敌人并造成伤害", 5, icon_color=BLUE,
                  requires=[(SkillType.TIME_SLOW, 1)], is_active=True, weight=1.0,
                  base_damage=40, damage_per_level=20, base_radius=100, radius_per_level=20,
                  max_level_bonus="绝对零度：冻结4秒+范围+50%+受到伤害增加",
                  level_descriptions={1: "冰霜爆发：范围100，冻结1秒，基础伤害", 2: "寒冰爆发：范围120，冻结2秒，伤害+30%",
                                      3: "极寒爆发：范围140，冻结3秒，减速额外持续3秒", 4: "冰封万里：范围170，冻结3秒，敌人受到伤害+30%",
                                      5: "绝对零度：范围200，冻结4秒，受到伤害+50%，冻结结束后敌人脆弱5秒"}),
            Skill(SkillType.CHAIN_LIGHTNING, "连锁闪电", "释放闪电在敌人间弹射", 5, icon_color=YELLOW,
                  requires=[(SkillType.CRIT_CHANCE, 2)], is_active=True, weight=1.0,
                  base_damage=50, damage_per_level=25, base_radius=200, radius_per_level=30,
                  max_level_bonus="雷神之怒：弹射次数+3+范围+50%+暴击率100%",
                  level_descriptions={1: "闪电链：弹射3次，基础伤害", 2: "强化闪电：弹射4次，伤害+30%，范围+20%",
                                      3: "雷霆链：弹射5次，伤害+60%，命中敌人眩晕0.5秒", 4: "风暴链：弹射6次，伤害+100%，可暴击",
                                      5: "雷神之怒：弹射8次，范围+50%，暴击率100%，每次弹射范围扩散"}),
            Skill(SkillType.BERSERK, "狂暴", "攻速翻倍，受到伤害+30%", 5, icon_color=RED,
                  requires=[(SkillType.OVERLOAD, 1)], is_active=True,
                  level_descriptions={1: "狂暴：攻速x2，受伤+30%，持续6秒", 2: "狂怒：攻速x2.2，受伤+25%，持续7秒，移速+20%",
                                      3: "血怒：攻速x2.5，受伤+20%，持续8秒，击杀回血", 4: "魔怔：攻速x2.8，受伤+15%，持续9秒，伤害+30%",
                                      5: "战神：攻速x3，无受伤惩罚，持续12秒，伤害+50%，免疫控制"}),
            Skill(SkillType.PHANTOM_STRIKE, "幻影打击", "召唤3个幻影分身同时攻击", 5, icon_color=LIME,
                  requires=[(SkillType.DODGE_CHANCE, 2)], is_active=True,
                  level_descriptions={1: "三幻影：召唤3个分身，每个造成30%伤害，持续5秒", 2: "五幻影：召唤5个分身，每个造成40%伤害，持续6秒",
                                      3: "幻影军团：召唤7个分身，每个造成50%伤害，持续7秒，分身可吸引敌人", 4: "幻影风暴：召唤9个分身，每个造成60%伤害，持续8秒，分身在消失时爆炸",
                                      5: "千影：召唤12个分身，每个造成80%伤害，持续10秒，分身会模仿玩家技能"}),
            Skill(SkillType.MEDIC_POD, "医疗舱", "部署持续回血区域", 5, icon_color=GREEN,
                  requires=[(SkillType.REGENERATION, 1)], is_active=True, weight=1.5,
                  base_damage=0, damage_per_level=0, base_radius=80, radius_per_level=20,
                  max_level_bonus="生命之泉：回血速度翻倍+范围+50%+清除debuff",
                  level_descriptions={1: "医疗站：范围80，每秒回5血，持续8秒", 2: "强化医疗站：范围100，每秒回8血，持续10秒",
                                      3: "急救站：范围120，每秒回12血，持续12秒，回复护甲", 4: "生命之泉：范围150，每秒回18血，持续15秒，清除debuff",
                                      5: "伊甸园：范围200，每秒回25血，持续20秒，清除debuff+复活一次（濒死时回满）"}),
            Skill(SkillType.SHOCKWAVE, "冲击波", "推开周围所有敌人并造成伤害", 5, icon_color=ORANGE,
                  requires=[(SkillType.SHIELD_BASH, 1)], is_active=True, weight=1.5,
                  base_damage=60, damage_per_level=25, base_radius=120, radius_per_level=15,
                  max_level_bonus="地震波：击退距离翻倍+范围+50%+眩晕1秒",
                  level_descriptions={1: "冲击波：范围120，击退敌人，基础伤害", 2: "强冲击波：范围140，击退距离+50%，伤害+30%",
                                      3: "大地震击：范围160，击退距离翻倍，眩晕0.5秒", 4: "裂地波：范围190，击退距离翻倍，眩晕1秒，地面持续伤害",
                                      5: "天崩地裂：范围250，超大击退，眩晕2秒，范围地震持续3秒+破甲"}),
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
            Skill(SkillType.WAR_CRY, "战吼", "获得伤害+攻速+护盾三重buff", 5, icon_color=GOLD,
                  requires=[(SkillType.BERSERK, 1)], is_active=True,
                  level_descriptions={1: "怒吼：伤害+50%攻速+30%护盾5秒", 2: "战吼：伤害+80%攻速+50%护盾7秒",
                                      3: "战神降临：伤害+120%攻速+80%护盾10秒", 4: "军神：伤害+150%攻速+100%护盾12秒，周围友军也获得buff",
                                      5: "不朽战吼：伤害+200%攻速+120%护盾15秒，期间免疫死亡，结束后回血50%"}),
            Skill(SkillType.PURIFY, "净化", "清除所有debuff并获得短暂无敌", 5, icon_color=WHITE,
                  requires=[(SkillType.REGENERATION, 2)], is_active=True,
                  level_descriptions={1: "净化：清除debuff+无敌2秒", 2: "圣洁：清除debuff+无敌3秒+回血30%",
                                      3: "神圣庇护：清除debuff+无敌5秒+满血", 4: "圣光：清除debuff+无敌6秒+满血+全属性+30%持续5秒",
                                      5: "神降：清除debuff+无敌8秒+满血+复活所有幻影分身+下一个技能无冷却"}),
            Skill(SkillType.ADRENALINE, "肾上腺素", "装备防爆套装时体力上限+25，回复+4/s", 5, icon_color=CRIMSON,
                  requires=[(SkillType.RIOT_GEAR, 1)],
                  level_descriptions={1: "兴奋：装备时体力+25，回复+4/s", 2: "激昂：装备时体力+50，回复+8/s",
                                      3: "狂热：装备时体力+75，回复+12/s", 4: "暴走：装备时体力+100，回复+16/s",
                                      5: "极限：装备时体力+125，回复+20/s"},
                  effect_key="stamina", effect_per_level=25),
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
        """随机获取技能卡供选择（基于技能权重的归一化爆率系统）
        
        权重规则：
        - 技能自身 weight 属性（稀有度）
        - 未解锁技能额外 ×2（鼓励尝试新技能）
        - 满级技能不出现（已在 get_available_skills 中过滤）
        """
        available = self.get_available_skills()
        if len(available) <= count:
            return available
        # 计算归一化权重
        weights = []
        for skill in available:
            w = skill.weight
            if skill.current_level == 0:
                w *= 2.0  # 未解锁技能权重翻倍
            weights.append(max(0.01, w))
        selected = []
        temp_available = available.copy()
        temp_weights = weights.copy()
        while len(selected) < count and temp_available:
            total = sum(temp_weights)
            if total <= 0:
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
