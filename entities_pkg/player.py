#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏实体模块 - 玩家、敌人(含新机制僵尸)、经验球、防爆套装等"""

import pygame
import math
import random
import time
from config import *
from .gear import RiotGear
from weapons import Weapon, Projectile
from skills import SkillTree
from buff import BuffManager, BuffType


class Player:
    def __init__(self, x, y, start_weapon=WeaponType.PISTOL, start_weapon_level=1):
        # v2.1.3：防御 None 武器（存档/联机同步异常时兜底手枪，避免 weapon_type 为 None 导致崩溃）
        if start_weapon is None:
            start_weapon = WeaponType.PISTOL
        self.x = x
        self.y = y
        self.size = 16
        self.speed = 3.5
        self.base_speed = 3.5

        self.max_hp = 100
        self.hp = 100
        self.alive = True
        self.downed = False
        self.downed_timer = 0.0    # 倒地时长（救援/自动复活用）
        # v2.5.0/v2.5.5 PvP 钩爪勾取玩家：被勾状态 + 打断绳索 QTE（0.8s 内单击绳索附近扇形即打断）
        self.grappled = False          # 被敌方钩爪勾中（位置由钩爪控制，禁用输入移动）
        self.qte_window = 0.0          # QTE 剩余时间（秒，0.8s）
        self.qte_hit_flash = 0.0       # QTE 命中/打断闪光计时（画面反馈）
        self.qte_success_timer = 0.0   # 打断成功提示计时
        self.qte_fail_timer = 0.0      # 打断失败提示计时
        self.qte_immune_timer = 0.0    # 打断成功后短暂免疫被勾
        # v2.5.5 打断绳索：绳索几何 + 待判定单击点 + 提示显示
        self.qte_break_tap = None      # 被勾期间玩家单击的世界坐标（待 gear 判定扇形）
        self.qte_rope_from = (0.0, 0.0)  # 绳索起点（钩爪源）
        self.qte_rope_to = (0.0, 0.0)    # 绳索终点（被勾玩家）
        self.qte_break_hint = 0.0        # 打断提示显示计时
        self.rescue_progress = 0.0  # 队友救援进度（0~2.5）
        # v2.5.7 永久死亡标记（救援超时后不再被重新判定倒地）
        self.permanently_dead = False
        self.last_rescue_time = -999.0  # 上次被救起的时间（救援冷却用）
        self.level = 1
        self.exp = 0
        self.exp_to_level = 100
        self.score = 0

        # 局外选定武器，局内仅一种武器，不可切换
        # v2.2.12：装备投掷物（手雷/燃烧瓶/烟雾弹）开局时附带一把手枪备用，
        # 投掷物 3 发弹药耗尽后可切换手枪继续战斗
        self.weapons = [Weapon(start_weapon, level=start_weapon_level)]
        if getattr(self.weapons[0], "is_throwable", False):
            self.weapons.append(Weapon(WeaponType.PISTOL))
        self.current_weapon_idx = 0

        self.skill_tree = SkillTree()
        self.active_skills = {}

        # v2.7.0 修复：玩家必须显式初始化 team_id（合作模式全队 0）
        # 此前 Player 从未设置该属性，而队友判定用 getattr(_p,'team_id',1) 取默认 1、
        # 自身用默认 0 —— 双方永远不同队，导致钩爪永远勾不到队友（P2 勾不到 P1）。
        self.team_id = 0

        # 角色加成（局外角色特殊能力）
        self.damage_multiplier = 1.0   # 射击伤害倍率加成
        self.crit_bonus_add = 0.0       # 额外暴击率
        self.health_regen = 0.0         # 每2秒回血
        self.dmg_reduce = 0.0           # 受伤减免

        self.riot_gear = RiotGear()
        self.riot_gear_cooldown = 0
        self.riot_gear_equip_cooldown = 30.0
        # v2.7.0 无畏冲锋限时状态（减伤/加速/禁技能，由防爆套装冲撞系统驱动）
        self.fearless_charge_active = False
        self.fearless_charge_level = 0

        # 加特林专属技能·过热倾泻 buff（射速暴增+弹药无限）
        self.overdrive_timer = 0
        self.overdrive_mult = 2.0
        self.overdrive_burn = False

        # 钢铁意志特效
        self.steel_will_active = False
        self.steel_will_flash_timer = 0

        self.invincible_timer = 0
        self.dash_timer = 0
        self.facing_angle = 0
        # v2.5.6：升级选卡保护倒计时（仅选卡刚开始的一小段时间免伤+脱锁，
        # 防止"卡在升级界面无限无敌"）
        self.upgrade_paused = False
        self.upgrade_grace_timer = 0.0

        self.damage_mult = 1.0
        self.speed_mult = 1.0
        self.fire_rate_mult = 1.0
        self.reload_speed_mult = 1.0  # 新增：换弹速度加成
        # v2.5.8 开发者：无敌 / 抗尸（免疫僵尸伤害但仍会被玩家打伤）
        self.dev_god = False
        self.dev_zombie_immune = False
        self.crit_chance = 0.05
        self.crit_damage = 1.5
        self.life_steal = 0.0
        self.pickup_range = 80
        self.exp_mult = 1.0
        self.cooldown_mult = 1.0
        self.armor = 0.0  # 新增：护甲减伤
        self.dodge_chance = 0.0  # 新增：闪避几率
        self.regen_rate = 0.0  # 新增：生命恢复
        self.fortress_active = False  # 新增：堡垒状态

        # 临时增益（保留兼容，实际由buff_manager管理）
        self.speed_boost_timer = 0
        self.speed_boost_mult = 1.0
        self.damage_boost_timer = 0
        self.damage_boost_mult = 1.0
        self.berserk_active = False  # 新增：狂暴状态
        # Buff系统
        self.buff_manager = BuffManager()
        self.buff_damage_events = []

        # 升级选择状态
        self.pending_level_up = False
        self.pending_levels = 0  # v2.5.2 待结算升级次数（多级连升逐级弹卡）
        self.skill_cards = []
        self.skill_slot_count = 3  # 升级时可选技能卡数量

        # 创伤效果 - 增强
        self.trauma = 0.0
        # v2.8.0 死亡详情：最近受到的伤害来源流水（环形缓冲）
        # 记录于 take_damage 的统一扣血出口，因此自动覆盖
        # 僵尸 / 敌对玩家 / 技能 / AOE / DOT 等全部来源，无需改各处调用点。
        self.damage_log = []
        self.MAX_DAMAGE_LOG = 40
        self.trauma_decay = 1.5
        self.recoil_offset = [0, 0]
        self.recoil_recovery = 3.0
        self.muzzle_flash_timer = 0
        self.muzzle_flash_duration = 0.08

        # === 疾跑体力系统 ===
        self.max_stamina = 100.0
        self.stamina = 100.0
        self.stamina_regen_rate = 18.0
        self.sprint_stamina_cost = 28.0
        self.sprint_speed_mult = 1.6
        self.sprinting = False
        self.stamina_exhausted = False

        # v2.2.0 载具召唤物（玩家骑乘时非 None）
        self.vehicle = None
        self.riding_vehicle = None  # v2.5.1 阵营载具乘客：乘坐他人载具时指向载具

    def can_act(self):
        """检查玩家是否可以执行主动操作（射击/技能/切换武器等）
        死亡、眩晕、冻结、恐惧状态下不可操作"""
        if not self.alive:
            return False
        # 检查Buff系统的眩晕/冻结状态
        if hasattr(self, 'buff_manager') and self.buff_manager:
            if self.buff_manager.is_stunned() or self.buff_manager.is_frozen():
                return False
            # 恐惧：无法攻击/施放技能
            _fear = self.buff_manager.get_buff(BuffType.FEAR)
            if _fear is not None and not _fear.is_expired():
                return False
        # 兼容直接属性
        if getattr(self, 'stunned', False) or getattr(self, 'frozen', False):
            return False
        return True

    def get_current_weapon(self):
        return self.weapons[self.current_weapon_idx]

    def switch_weapon(self, idx):
        if 0 <= idx < len(self.weapons):
            self.current_weapon_idx = idx
            return True
        return False

    def next_weapon(self):
        if len(self.weapons) > 1:
            self.current_weapon_idx = (self.current_weapon_idx + 1) % len(self.weapons)
            return True
        return False

    def add_weapon(self, weapon_type):
        """添加武器，已有同类型则升级，避免重复"""
        # v2.1.3：防御 None 武器（避免 Weapon(None) 进列表后 weapon_type 崩溃）
        if weapon_type is None:
            return
        # 统一转为枚举值进行比较（兼容int和枚举）
        from weapons import WeaponType
        if isinstance(weapon_type, int):
            try:
                weapon_type = WeaponType(weapon_type)
            except:
                pass
        wt_val = weapon_type.value if hasattr(weapon_type, 'value') else weapon_type
        for w in self.weapons:
            w_val = w.weapon_type.value if hasattr(w.weapon_type, 'value') else w.weapon_type
            if w_val == wt_val:
                w.upgrade()
                return
        self.weapons.append(Weapon(weapon_type))
        # 添加后去重（防止历史遗留的重复武器）
        self._dedupe_weapons()

    def _dedupe_weapons(self):
        """合并重复武器，同类型保留等级最高的，其余等级累加"""
        from weapons import WeaponType
        seen = {}
        for w in self.weapons:
            w_val = w.weapon_type.value if hasattr(w.weapon_type, 'value') else w.weapon_type
            if w_val in seen:
                existing = seen[w_val]
                existing.level += w.level - 1  # 累加等级（减去重复的1级基础）
                existing._setup_weapon()
            else:
                seen[w_val] = w
        self.weapons = list(seen.values())
        if self.current_weapon_idx >= len(self.weapons):
            self.current_weapon_idx = 0

    def equip_riot_gear(self):
        riot_skill = self.skill_tree.get_skill(SkillType.RIOT_GEAR)
        if not riot_skill or riot_skill.current_level == 0:
            return False
        if self.riot_gear.equipped:
            self.riot_gear.unequip()
            return True
        if self.riot_gear_cooldown <= 0:
            self.riot_gear.equip()
            self.riot_gear_cooldown = self.riot_gear_equip_cooldown
            return True
        return False

    def update(self, dt, move_x, move_y, mouse_angle, world=None, sprinting=False):
        # 倒地状态处理（单人模式倒地即死亡）
        if self.downed:
            self.hp = 0
            self.alive = False
            return

        # v2.2.0：肾上腺素体力加成动态应用（上限+25/级、回复+4/s，装备防爆套装时生效）
        try:
            _rg = getattr(self, 'riot_gear', None)
            if _rg is not None:
                _adl = getattr(_rg, 'adrenaline_level', 0)
                _new_max = 100.0 + (_adl * 25 if getattr(_rg, 'equipped', False) else 0)
                _new_regen = 18.0 + (_adl * 4 if getattr(_rg, 'equipped', False) else 0)
                if abs(_new_max - self.max_stamina) > 0.01:
                    _old_max = self.max_stamina
                    self.max_stamina = _new_max
                    if _old_max > 0 and self.stamina > 0:
                        self.stamina = min(_new_max, self.stamina * _new_max / _old_max)
                    self.stamina = min(self.max_stamina, self.stamina)
                self.stamina_regen_rate = _new_regen
        except Exception:
            pass

        self._update_stats()
        # Buff系统对攻速/换弹/暴击的加成
        self.fire_rate_mult *= self.buff_manager.get_attack_speed_mult()
        self.reload_speed_mult *= self.buff_manager.get_reload_speed_mult()
        self.crit_chance += self.buff_manager.get_crit_chance_add()

        # 更新Buff系统（处理持续伤害/治疗等）
        _, self.buff_damage_events = self.buff_manager.update(dt, self)
        # 兼容旧接口：把旧的临时增益转换为Buff
        if self.speed_boost_timer > 0:
            self.buff_manager.add_buff(BuffType.SPEED_BOOST, self.speed_boost_timer)
            self.speed_boost_timer = 0
        if self.damage_boost_timer > 0:
            self.buff_manager.add_buff(BuffType.DAMAGE_BOOST, self.damage_boost_timer)
            self.damage_boost_timer = 0
        if self.berserk_active and not self.buff_manager.has_buff(BuffType.BERSERK):
            self.buff_manager.add_buff(BuffType.BERSERK, 10.0)

        if self.dash_timer > 0:
            self.dash_timer -= dt
            speed_mult = 4.0
        else:
            speed_mult = 1.0

        # === 疾跑体力系统 ===
        is_moving = (abs(move_x) > 0.05 or abs(move_y) > 0.05)
        gear_equipped = self.riot_gear.equipped
        sprint_cost_mult = 1.9 if gear_equipped else 1.0
        regen_mult = 0.65 if gear_equipped else 1.0
        gear_move_drain = 5.5 if gear_equipped else 0.0

        if sprinting and is_moving and not self.stamina_exhausted and self.stamina > 0:
            self.sprinting = True
            cost = self.sprint_stamina_cost * sprint_cost_mult * dt
            self.stamina = max(0, self.stamina - cost)
            speed_mult *= self.sprint_speed_mult
            if self.stamina <= 0:
                self.stamina_exhausted = True
        else:
            self.sprinting = False
            if gear_equipped and is_moving and not self.stamina_exhausted:
                self.stamina = max(0, self.stamina - gear_move_drain * dt)
                if self.stamina <= 0:
                    self.stamina_exhausted = True
            if self.stamina < self.max_stamina:
                regen = self.stamina_regen_rate * regen_mult * dt
                if self.stamina_exhausted:
                    regen *= 0.5
                self.stamina = min(self.max_stamina, self.stamina + regen)
                if self.stamina_exhausted and self.stamina >= self.max_stamina * 0.25:
                    self.stamina_exhausted = False

        # 同步体力到防爆套装（共用同一体力池）
        self.riot_gear.stamina = self.stamina
        self.riot_gear.max_stamina = self.max_stamina

        # 应用Buff速度加成
        speed_mult *= self.buff_manager.get_speed_mult()

        # 防爆套装DEBUFF减速
        if self.riot_gear.equipped and self.riot_gear.has_debuff:
            speed_mult *= self.riot_gear.get_debuff_speed_mult()

        # 生命恢复
        if self.regen_rate > 0 and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + self.regen_rate * dt)

        # v2.5.0/v2.5.5 PvP 钩爪被勾：输入位移禁用（位置由钩爪拉取控制），打断改为单击绳索扇形判定
        if self.grappled:
            move_x, move_y = 0.0, 0.0
        # v2.5.3 QTE 反馈计时衰减
        if self.qte_hit_flash > 0:
            self.qte_hit_flash = max(0.0, self.qte_hit_flash - dt)
        if self.qte_success_timer > 0:
            self.qte_success_timer = max(0.0, self.qte_success_timer - dt)
        if self.qte_fail_timer > 0:
            self.qte_fail_timer = max(0.0, self.qte_fail_timer - dt)
        if self.qte_immune_timer > 0:
            self.qte_immune_timer = max(0.0, self.qte_immune_timer - dt)
        if getattr(self, 'qte_break_hint', 0) > 0:
            self.qte_break_hint = max(0.0, self.qte_break_hint - dt)
        # v2.7.0 无畏冲锋：冲锋期间位移完全由冲撞系统接管（玩家只能转向）
        if getattr(self, 'fearless_charge_active', False):
            move_x, move_y = 0.0, 0.0
        new_x = self.x + move_x * self.speed * self.speed_mult * speed_mult * dt * 60
        new_y = self.y + move_y * self.speed * self.speed_mult * speed_mult * dt * 60

        # v2.2.6：记录本帧实际输入位移（供钩爪自我拉拽叠加，移动中也能被快速拉过去）
        _ox, _oy = self.x, self.y
        if world:
            new_rect_x = pygame.Rect(new_x - self.size, self.y - self.size, self.size * 2, self.size * 2)
            new_rect_y = pygame.Rect(self.x - self.size, new_y - self.size, self.size * 2, self.size * 2)
            if not world.check_collision(new_rect_x):
                self.x = new_x
            if not world.check_collision(new_rect_y):
                self.y = new_y
        else:
            self.x = new_x
            self.y = new_y
        self._inp_dx = self.x - _ox
        self._inp_dy = self.y - _oy

        # v2.7.0 无畏冲锋：冲锋期间玩家仅能改变方向，且转向速度大幅降低
        if getattr(self, 'fearless_charge_active', False):
            _target = math.degrees(mouse_angle)
            _diff = (_target - self.facing_angle + 180) % 360 - 180
            _max_step = FEARLESS_CHARGE_TURN_RATE * dt
            if abs(_diff) <= _max_step:
                self.facing_angle = _target
            else:
                self.facing_angle += _max_step if _diff > 0 else -_max_step
            self.facing_angle = (self.facing_angle + 360) % 360
        else:
            self.facing_angle = math.degrees(mouse_angle)

        for w in self.weapons:
            w.reload_speed_mult = self.reload_speed_mult
            w.update(dt)

        for skill_type in list(self.active_skills.keys()):
            self.active_skills[skill_type] -= dt
            if self.active_skills[skill_type] <= 0:
                del self.active_skills[skill_type]

        if self.riot_gear.equipped or self.riot_gear.riot_gear_cd_timer > 0 or self.riot_gear.grapple_active or self.riot_gear.grapple_cooldown > 0:
            self.riot_gear.update(dt, self.x, self.y, self.facing_angle, self.speed_mult, cd_reduction_mult=self.cooldown_mult, player=self)

        if self.riot_gear_cooldown > 0:
            self.riot_gear_cooldown -= dt

        if self.invincible_timer > 0:
            self.invincible_timer -= dt

        # 钢铁意志检测
        steel_skill = self.skill_tree.get_skill(SkillType.STEEL_WILL)
        if steel_skill and steel_skill.current_level > 0:
            hp_threshold = 0.3
            if self.hp / self.max_hp < hp_threshold and not self.steel_will_active:
                self.steel_will_active = True
                self.steel_will_flash_timer = 2.0
            elif self.hp / self.max_hp >= hp_threshold + 0.05:
                self.steel_will_active = False
        if self.steel_will_active:
            self.steel_will_flash_timer -= dt

        # 堡垒检测
        fortress_skill = self.skill_tree.get_skill(SkillType.FORTRESS)
        if fortress_skill and fortress_skill.current_level > 0:
            self.fortress_active = (abs(move_x) < 0.1 and abs(move_y) < 0.1)

        # 创伤效果衰减
        if self.trauma > 0:
            self.trauma = max(0, self.trauma - self.trauma_decay * dt)

        # 后坐力恢复
        self.recoil_offset[0] *= max(0, 1 - self.recoil_recovery * dt)
        self.recoil_offset[1] *= max(0, 1 - self.recoil_recovery * dt)

        # 枪口闪光衰减
        if self.muzzle_flash_timer > 0:
            self.muzzle_flash_timer -= dt

    def ensure_safe_position(self, world):
        """确保玩家不在障碍物内"""
        if world and not world.is_position_safe(self.x, self.y, self.size):
            self.x, self.y = world.find_safe_position(self.x, self.y, self.size)

    def _update_stats(self):
        skill = self.skill_tree

        health_skill = skill.get_skill(SkillType.HEALTH_UP)
        if health_skill:
            self.max_hp = 100 * (1 + health_skill.current_level * 0.2)

        speed_skill = skill.get_skill(SkillType.SPEED_UP)
        if speed_skill:
            self.speed_mult = 1.0 + speed_skill.current_level * 0.1

        damage_skill = skill.get_skill(SkillType.DAMAGE_UP)
        if damage_skill:
            self.damage_mult = 1.0 + damage_skill.current_level * 0.15

        fire_rate_skill = skill.get_skill(SkillType.FIRE_RATE_UP)
        if fire_rate_skill:
            self.fire_rate_mult = 1.0 + fire_rate_skill.current_level * 0.1

        reload_skill = skill.get_skill(SkillType.RELOAD_SPEED)
        if reload_skill:
            self.reload_speed_mult = 1.0 + reload_skill.current_level * 0.15

        crit_skill = skill.get_skill(SkillType.CRIT_CHANCE)
        if crit_skill:
            self.crit_chance = 0.05 + crit_skill.current_level * 0.05

        crit_dmg_skill = skill.get_skill(SkillType.CRIT_DAMAGE)
        if crit_dmg_skill:
            self.crit_damage = 1.5 + crit_dmg_skill.current_level * 0.25

        ls_skill = skill.get_skill(SkillType.LIFE_STEAL)
        if ls_skill:
            self.life_steal = ls_skill.current_level * 0.03

        pickup_skill = skill.get_skill(SkillType.PICKUP_RANGE)
        if pickup_skill:
            self.pickup_range = 80 + pickup_skill.current_level * 25  # v2.5.0 与词条 +25/级 对齐

        exp_skill = skill.get_skill(SkillType.EXP_BOOST)
        if exp_skill:
            self.exp_mult = 1.0 + exp_skill.current_level * 0.15

        cd_skill = skill.get_skill(SkillType.COOLDOWN_REDUCTION)
        if cd_skill:
            self.cooldown_mult = 1.0 - cd_skill.current_level * 0.1

        armor_skill = skill.get_skill(SkillType.ARMOR_UP)
        if armor_skill:
            self.armor = armor_skill.current_level * 0.08

        dodge_skill = skill.get_skill(SkillType.DODGE_CHANCE)
        if dodge_skill:
            self.dodge_chance = dodge_skill.current_level * 0.05

        # v2.2.0：肾上腺素等级同步（体力加成在 update 动态应用）
        ad_skill = skill.get_skill(SkillType.ADRENALINE)
        if ad_skill and getattr(self, 'riot_gear', None) is not None:
            self.riot_gear.adrenaline_level = ad_skill.current_level

        regen_skill = skill.get_skill(SkillType.REGENERATION)
        if regen_skill:
            self.regen_rate = regen_skill.current_level * 0.01 * self.max_hp

    def gain_exp(self, amount):
        self.exp += int(amount * self.exp_mult)
        while self.exp >= self.exp_to_level:
            self.exp -= self.exp_to_level
            self.level_up()

    def level_up(self):
        self.level += 1
        self.exp_to_level = int(100 * (1.2 ** (self.level - 1)))
        self.skill_tree.skill_points += 1
        self.max_hp += 10
        self.hp = min(self.hp + 20, self.max_hp)
        # v2.5.2 多级连升逐级弹卡：累计待结算次数，仅首次生成卡片；
        # 选卡确认后若还有剩余级数则再次弹卡（玩家升级属性已全部结算）
        self.pending_levels = getattr(self, 'pending_levels', 0) + 1
        self.pending_level_up = True
        if self.pending_levels == 1:
            self.skill_cards = self.skill_tree.get_random_skill_cards(getattr(self, 'skill_slot_count', 3))
        # 解锁全局技能树（三选一出现过就算）
        try:
            from skill_tree_view import skill_tree_unlock_manager
            for sc in self.skill_cards:
                stype = getattr(sc, 'skill_type', getattr(sc, 'type', None))
                if stype:
                    skill_tree_unlock_manager.unlock_skill(stype)
        except Exception:
            pass

    def take_damage(self, damage, damage_type="melee", from_front=False, attack_x=None, attack_y=None, bypass_dodge=False, source="zombie"):
        # 开发者模式：无敌
        if getattr(self, 'dev_god', False):
            return 0
        # v2.5.8 开发者：抗尸——只免疫僵尸造成的伤害，玩家造成的伤害照吃
        # （PvP 调试核心：可以安心刷怪，但依然会被敌对玩家击杀）
        if getattr(self, 'dev_zombie_immune', False) and source != "player":
            return 0
        # v2.5.1 阵营载具乘客：受到的伤害记在载具血条上（乘客本体不扣血）
        _rv = getattr(self, 'riding_vehicle', None)
        if _rv is not None and getattr(_rv, 'alive', False):
            _rv.take_damage(max(1, int(damage)), damage_type=damage_type)
            return 0
        # v2.1.3：同屏双人升级选卡期间该玩家免伤（临时脱锁，选卡完成后恢复）
        # v2.5.6：改为「限时免伤」——只保护选卡刚开始的 grace 秒数，
        # 防止玩家故意停在升级界面无限吃无敌（且怪物不再锁定他）
        if getattr(self, 'upgrade_paused', False) and getattr(self, 'upgrade_grace_timer', 0) > 0:
            return 0
        # v2.1.6：倒地（等待救援）期间无敌——脱锁无敌机制完整闭环：
        # 怪物目标选择已排除倒地者，此处兜底所有遗漏路径（锁定技能/AOE/DOT/盾冲/钩爪/残留投射物）
        if getattr(self, 'downed', False):
            return 0
        # 角色受伤减免（如铁壁）
        dmg_reduce = getattr(self, 'dmg_reduce', 0.0)
        if dmg_reduce > 0:
            damage = max(0, damage * (1.0 - dmg_reduce))
        # v2.7.0 无畏冲锋：冲锋期间任意伤害减伤 50%
        if getattr(self, 'fearless_charge_active', False):
            damage = max(0, damage * (1.0 - FEARLESS_CHARGE_DAMAGE_REDUCTION))
        # Mod 钩子：玩家受伤 - 允许 mod 修改伤害值
        try:
            import mod_loader
            results = mod_loader.trigger_hook("on_player_damage", damage)
            if results:
                # 取最后一个非 None 的返回值作为新伤害
                for r in reversed(results):
                    if r is not None and isinstance(r, (int, float)):
                        damage = r
                        break
        except Exception:
            pass
        # Mod 钩子：伤害结算（受害者=玩家）
        try:
            import mod_loader
            for _v in reversed(mod_loader.trigger_hook("on_damage_dealt", self, damage, damage_type, None)):
                if isinstance(_v, (int, float)):
                    damage = _v
                    break
        except Exception:
            pass
        
        # v2.6.5 修复：来自玩家的远程伤害（子弹）跳过无敌帧检查，允许多发子弹连续命中
        _skip_invincible = (source == "player" and damage_type == "ranged")
        if not _skip_invincible and self.invincible_timer > 0:
            return

        # v2.2.0 载具期间：玩家无敌，伤害转移给载具专属血条（不应用回血）
        _veh = getattr(self, 'vehicle', None)
        if _veh is not None and getattr(_veh, 'alive', False):
            _veh.take_damage(damage, damage_type)
            return

        # 闪避检测（PvP 弹道/爆炸/激光命中时 bypass_dodge=True，命中必然扣血，修复"数字有但没扣血"）
        if not bypass_dodge and random.random() < self.dodge_chance:
            return  # 完全闪避

        # 钢铁意志减伤
        steel_skill = self.skill_tree.get_skill(SkillType.STEEL_WILL)
        if steel_skill and steel_skill.current_level > 0 and self.steel_will_active:
            reduction = 0.3 + steel_skill.current_level * 0.1
            damage *= (1 - reduction)

        # 堡垒减伤
        if self.fortress_active:
            fortress_skill = self.skill_tree.get_skill(SkillType.FORTRESS)
            if fortress_skill:
                damage *= (1 - 0.3)

        # 护甲减伤
        damage *= (1 - self.armor)

        # Buff系统受伤倍率（包含狂暴、护盾、燃烧等）
        damage *= self.buff_manager.get_damage_taken_mult()

        # v2.2.0 优化格挡判定：盾牌几何命中优先（矩形碰撞或60°方向），再交给防爆套装结算
        blocked = False
        if self.riot_gear.equipped and not self.riot_gear.shield_broken and attack_x is not None and attack_y is not None:
            try:
                blocked = self.riot_gear.check_shield_block(self.x, self.y, attack_x, attack_y)
            except Exception:
                blocked = from_front
        actual_damage = self.riot_gear.take_damage(damage, damage_type, from_front, attack_x, attack_y, blocked=blocked)
        self.hp -= actual_damage
        # v2.8.0 死亡详情：登记本次伤害来源（actual_damage 为格挡/护甲后的真实扣血）
        if actual_damage > 0:
            self._log_damage(actual_damage, damage_type, source, attack_x, attack_y)
        # v2.6.4 修复：来自玩家的远程伤害（子弹）不设置无敌帧，允许多发子弹连续命中
        # 只有僵尸伤害或近战伤害才设置无敌帧
        if source != "player" or damage_type != "ranged":
            self.invincible_timer = 0.3

        # 创伤效果 - 增强
        trauma_add = min(0.7, actual_damage / self.max_hp * 3)
        self.trauma = min(1.0, self.trauma + trauma_add)

        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            # v2.8.2：致命一击已记录 → 冻结日志，保住真正的死因数据
            self._damage_log_frozen = True

    def _log_damage(self, amount, dtype, source, attack_x, attack_y):
        """v2.8.2 死亡详情：登记一条伤害记录（环形缓冲，最多 MAX_DAMAGE_LOG 条）

        关键修复：玩家倒地/死亡后**立即冻结**日志。
        旧实现会继续记录后续伤害（尸体被 AOE 溅射、残留 DOT 等），
        把真正致死那几秒的数据挤出环形缓冲 —— 用户看到的死亡详情
        就变成了"死后挨的无关伤害"，找不到真正死因。
        """
        try:
            if getattr(self, '_damage_log_frozen', False):
                return
            if getattr(self, 'downed', False) or getattr(self, 'permanently_dead', False) \
                    or not getattr(self, 'alive', True):
                self._damage_log_frozen = True
                return
            self.damage_log.append({
                "t": time.monotonic(),
                "amount": round(float(amount), 1),
                "type": str(dtype),
                "source": str(source),
                "x": attack_x, "y": attack_y,
                "hp": max(0, float(self.hp)),
            })
            if len(self.damage_log) > self.MAX_DAMAGE_LOG:
                del self.damage_log[:len(self.damage_log) - self.MAX_DAMAGE_LOG]
        except Exception:
            pass

    def death_detail(self, window=12.0, limit=20):
        """v2.8.0 死亡详情面板数据：最近 window 秒内对本人造成伤害的来源与数值

        返回 [(距死亡秒数, 伤害值, 类型, 来源描述, 剩余HP)]，按时间倒序（最近在前）。
        """
        try:
            _now = getattr(self, '_damage_log_frozen_at', None) or time.monotonic()
            _out = []
            for _r in reversed(self.damage_log):
                # v2.8.4：基准是冻结时刻（死亡瞬间），不是实时时钟
                _ago = _now - _r.get("t", _now)
                if _ago > window:
                    break
                _out.append({
                    "ago": round(_ago, 2),
                    "amount": _r.get("amount", 0.0),
                    "type": _r.get("type", ""),
                    "source": _r.get("source", ""),
                    "hp": _r.get("hp", 0),
                    "x": _r.get("x"), "y": _r.get("y"),
                })
                if len(_out) >= limit:
                    break
            return _out
        except Exception:
            return []

    def freeze_damage_log(self):
        """v2.8.2：死亡瞬间冻结伤害日志，并返回快照（供死亡详情页面使用）

        v2.8.4：同时记录**冻结时刻** `_damage_log_frozen_at`。
        此后所有"距死亡 N 秒"都以这个时刻为基准计算 —— 不再用实时
        `time.monotonic()`，否则玩家在结算页多停留一会儿，
        每条伤害的"距死亡"就会一直往后走，超过窗口后被过滤掉，
        表现为"看一会伤害全没了"。
        """
        try:
            self._damage_log_frozen = True
            self._damage_log_frozen_at = time.monotonic()
            return list(self.damage_log)
        except Exception:
            return []

    def heal(self, amount):
        self.hp = min(self.hp + amount, self.max_hp)

    def use_skill(self, skill_type):
        if skill_type in self.active_skills:
            return False
        skill = self.skill_tree.get_skill(skill_type)
        if not skill or skill.current_level == 0:
            return False

        cooldowns = {
            SkillType.DASH: 5.0, 
            SkillType.GRENADE: 8.0, 
            SkillType.TURRET: 15.0,
            SkillType.AIRSTRIKE: 20.0,
            SkillType.GRAPPLE_PULL: 6.0,
            SkillType.TIME_SLOW: 25.0, 
            SkillType.OVERLOAD: 30.0,
            SkillType.RIOT_GEAR: 30.0,
            SkillType.BLINK: 8.0,
            SkillType.BLACK_HOLE: 25.0,
            SkillType.ICE_NOVA: 20.0,
            SkillType.CHAIN_LIGHTNING: 15.0,
            SkillType.BERSERK: 20.0,
            SkillType.PHANTOM_STRIKE: 18.0,
            SkillType.MEDIC_POD: 30.0,
            SkillType.FEARLESS_CHARGE: 18.0,
        }
        cd = cooldowns.get(skill_type, 10.0) * self.cooldown_mult
        self.active_skills[skill_type] = cd
        return True

    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, 
                          self.size * 2, self.size * 2)

    def draw(self, screen, camera_x, camera_y, font, scale=1.0, assets=None,
             own_view=True):
        """绘制玩家

        v2.8.7：`own_view=False` 表示"这是别人的视口"。
        钩爪的瞄准预瞄/锁定圈只在本人的视口绘制（详见 gear.draw 注释）。
        """
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        # 用 render_size（泰坦符文体型增大用），碰撞仍用原 size
        draw_size = getattr(self, 'render_size', self.size)
        s = max(2, int(draw_size * scale))

        if self.invincible_timer > 0 and int(self.invincible_timer * 10) % 2 == 0:
            pass
        else:
            # 优先使用玩家贴图（防爆套装在身用护盾贴图）；缺失时退回几何绘制
            use_img = assets is not None and assets.has_image("player")
            shield_img = assets is not None and getattr(self.riot_gear, 'equipped', False) and assets.has_image("player_shield")
            if use_img or shield_img:
                key = "player_shield" if shield_img else "player"
                pimg = assets.get_image(key, s * 2, s * 2)
                screen.blit(pimg, (px - s, py - s))
                # 朝向指示线
                angle_rad = math.radians(self.facing_angle)
                end_x = px + math.cos(angle_rad) * int(25 * scale)
                end_y = py + math.sin(angle_rad) * int(25 * scale)
                pygame.draw.line(screen, WHITE, (px, py), (end_x, end_y), max(1, int(2 * scale)))
            else:
                pygame.draw.circle(screen, BLUE, (px, py), s)
                angle_rad = math.radians(self.facing_angle)
                end_x = px + math.cos(angle_rad) * int(25 * scale)
                end_y = py + math.sin(angle_rad) * int(25 * scale)
                pygame.draw.line(screen, WHITE, (px, py), (end_x, end_y), max(1, int(3 * scale)))

        # 武器程序化贴图（局内可见，随朝向旋转，独立于身体）
        try:
            from weapons import render_weapon_icon
            _cw = self.get_current_weapon()
            _wicon = render_weapon_icon(_cw.weapon_type)
            _off = int(16 * scale)
            _arad = math.radians(self.facing_angle)
            _wx = px + math.cos(_arad) * _off
            _wy = py + math.sin(_arad) * _off
            _rot = pygame.transform.rotate(_wicon, -self.facing_angle)
            _wrect = _rot.get_rect(center=(_wx, _wy))
            screen.blit(_rot, _wrect)
        except Exception:
            pass

        self.riot_gear.draw(screen, self.x, self.y, camera_x, camera_y, scale,
                             own_view=own_view)

        bar_width = int(40 * scale)
        bar_height = max(2, int(6 * scale))
        hp_ratio = self.hp / self.max_hp
        pygame.draw.rect(screen, RED, (px - bar_width // 2, py - s - max(6, int(12 * scale)), 
                                     bar_width, bar_height))
        pygame.draw.rect(screen, GREEN, (px - bar_width // 2, py - s - max(6, int(12 * scale)), 
                                       int(bar_width * hp_ratio), bar_height))

        level_text = font.render(f"Lv.{self.level}", True, WHITE)
        screen.blit(level_text, (px - int(20 * scale), py + s + max(2, int(5 * scale))))

        # 钢铁意志特效
        if self.steel_will_active:
            flash = abs(math.sin(self.steel_will_flash_timer * 5)) if self.steel_will_flash_timer > 0 else 0.5
            aura_color = (220, 20, 60, int(100 + 80 * flash))
            aura_surf = pygame.Surface((int(80*scale), int(80*scale)), pygame.SRCALPHA)
            pygame.draw.circle(aura_surf, aura_color, (int(40*scale), int(40*scale)), int(35*scale))
            screen.blit(aura_surf, (px - int(40*scale), py - int(40*scale)))
            if int(pygame.time.get_ticks() / 200) % 2 == 0:
                pygame.draw.circle(screen, CRIMSON, (px, py), int((s + 8) * scale), max(1, int(2*scale)))

        # v2.2.13 PvPvE 阵营标识：合作模式 team_id=0 不显示，PvP 时头顶 A/B 标签
        _tid = getattr(self, 'team_id', 0)
        if _tid and font is not None:
            try:
                _tc = (230, 90, 90) if _tid == 1 else (90, 200, 250)
                _tt = font.render('AB'[_tid % 2], True, _tc)
                screen.blit(_tt, _tt.get_rect(centerx=px, top=py - s - int(22 * scale)))
            except Exception:
                pass
