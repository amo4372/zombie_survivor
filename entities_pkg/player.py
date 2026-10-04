#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏实体模块 - 玩家、敌人(含新机制僵尸)、经验球、防爆套装等"""

import pygame
import math
import random
from config import *
from .gear import RiotGear
from weapons import Weapon, Projectile
from skills import SkillTree
from buff import BuffManager, BuffType


class Player:
    def __init__(self, x, y, start_weapon=WeaponType.PISTOL, start_weapon_level=1):
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
        self.rescue_progress = 0.0  # 队友救援进度（0~2.5）
        self.level = 1
        self.exp = 0
        self.exp_to_level = 100
        self.score = 0

        # 局外选定武器，局内仅一种武器，不可切换
        self.weapons = [Weapon(start_weapon, level=start_weapon_level)]
        self.current_weapon_idx = 0

        self.skill_tree = SkillTree()
        self.active_skills = {}

        # 角色加成（局外角色特殊能力）
        self.damage_multiplier = 1.0   # 射击伤害倍率加成
        self.crit_bonus_add = 0.0       # 额外暴击率
        self.health_regen = 0.0         # 每2秒回血
        self.dmg_reduce = 0.0           # 受伤减免

        self.riot_gear = RiotGear()
        self.riot_gear_cooldown = 0
        self.riot_gear_equip_cooldown = 30.0

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

        self.damage_mult = 1.0
        self.speed_mult = 1.0
        self.fire_rate_mult = 1.0
        self.reload_speed_mult = 1.0  # 新增：换弹速度加成
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
        self.skill_cards = []
        self.skill_slot_count = 3  # 升级时可选技能卡数量

        # 创伤效果 - 增强
        self.trauma = 0.0
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

        new_x = self.x + move_x * self.speed * self.speed_mult * speed_mult * dt * 60
        new_y = self.y + move_y * self.speed * self.speed_mult * speed_mult * dt * 60

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

        self.facing_angle = math.degrees(mouse_angle)

        for w in self.weapons:
            w.reload_speed_mult = self.reload_speed_mult
            w.update(dt)

        for skill_type in list(self.active_skills.keys()):
            self.active_skills[skill_type] -= dt
            if self.active_skills[skill_type] <= 0:
                del self.active_skills[skill_type]

        if self.riot_gear.equipped or self.riot_gear.riot_gear_cd_timer > 0 or self.riot_gear.grapple_active or self.riot_gear.grapple_cooldown > 0:
            self.riot_gear.update(dt, self.x, self.y, self.facing_angle, self.speed_mult, cd_reduction_mult=self.cooldown_mult)

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
            self.pickup_range = 80 + pickup_skill.current_level * 20

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
        # 触发技能选择
        self.pending_level_up = True
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

    def take_damage(self, damage, damage_type="melee", from_front=False, attack_x=None, attack_y=None):
        # 开发者模式：无敌
        if getattr(self, 'dev_god', False):
            return 0
        # 角色受伤减免（如铁壁）
        dmg_reduce = getattr(self, 'dmg_reduce', 0.0)
        if dmg_reduce > 0:
            damage = max(0, damage * (1.0 - dmg_reduce))
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
        
        if self.invincible_timer > 0:
            return

        # 闪避检测
        if random.random() < self.dodge_chance:
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

        actual_damage = self.riot_gear.take_damage(damage, damage_type, from_front, attack_x, attack_y)
        self.hp -= actual_damage
        self.invincible_timer = 0.3

        # 创伤效果 - 增强
        trauma_add = min(0.7, actual_damage / self.max_hp * 3)
        self.trauma = min(1.0, self.trauma + trauma_add)

        if self.hp <= 0:
            self.hp = 0
            self.alive = False

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
            SkillType.SHIELD_BASH: 3.0,
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
            SkillType.SHOCKWAVE: 12.0,
        }
        cd = cooldowns.get(skill_type, 10.0) * self.cooldown_mult
        self.active_skills[skill_type] = cd
        return True

    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, 
                          self.size * 2, self.size * 2)

    def draw(self, screen, camera_x, camera_y, font, scale=1.0, assets=None):
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

        self.riot_gear.draw(screen, self.x, self.y, camera_x, camera_y, scale)

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
