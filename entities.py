#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏实体模块 - 玩家、敌人(含新机制僵尸)、经验球、防爆套装等"""

import pygame
import math
import random
from config import (EnemyType, WeaponType, SkillType, ItemType,
                   RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, GRAY, DARK_GRAY, GOLD,
                   LIGHT_GRAY, CYAN, WHITE, BLACK, DARK_GREEN, DARK_RED, BROWN, CRIMSON,
                   RUST, POISON_GREEN, BLOOD_RED, LIME, SLATE, CHARCOAL)
from weapons import Weapon, Projectile
from skills import SkillTree
from buff import BuffManager, BuffType

class RiotGear:
    def __init__(self):
        self.equipped = False
        self.shield_hp = 500
        self.max_shield_hp = 500
        self.shield_broken = False
        self.viewing_window_hp = 400
        self.max_viewing_window_hp = 400
        self.facing_angle = 0
        self.stamina = 100
        self.max_stamina = 100
        self.stamina_regen = 20
        self.bash_cooldown = 0
        self.bash_max_cooldown = 0.5
        self.grapple_cooldown = 0
        self.grapple_max_cooldown = 4.0
        self.melee_reduction = 0.5
        self.ranged_reduction = 0.7
        self.magic_immunity = True
        self.shield_width = 60
        self.shield_height = 80
        self.shield_offset = 25
        self.grapple_active = False
        self.grapple_target = None
        self.grapple_target_pos = None
        self.grapple_head_pos = None
        self.grapple_state = "idle"
        self.grapple_speed = 80
        self.grapple_pull_speed = 5
        self.grapple_hit_stun_timer = 0
        self.grapple_hit_stun_duration = 0.4
        self.grapple_max_range = 800
        self.grapple_stamina_cost = 0
        self.bash_auto = False
        self.bash_direction = 0
        self.bash_stamina_cost = 25
        self.bash_anim_timer = 0
        self.bash_anim_duration = 0.2
        self.bash_hit_pos = None
        self.equip_time = 0
        self.debuff_threshold = 60.0
        self.has_debuff = False
        self.debuff_speed_penalty = 0.3
        self.aim_line_active = False
        self.aim_line_angle = 0
        self.aim_line_press_time = 0
        self.aim_threshold = 0.25

        # =========【新增冷却】卸下防爆套装才开始CD =========
        self.riot_gear_cd_timer = 0.0
        self.riot_gear_base_cd = 30.0

    def equip(self):
        """装备防爆套装：不启动冷却，冷却在unequip时触发"""
        if self.riot_gear_cd_timer > 0:
            return False
        self.equipped = True
        self.shield_hp = self.max_shield_hp
        self.shield_broken = False
        self.viewing_window_hp = self.max_viewing_window_hp
        self.equip_time = 0
        self.has_debuff = False
        return True

    def unequip(self, cd_reduction_mult=1.0):
        """卸下防爆套装，立刻启动冷却，受冷却缩减倍率"""
        if not self.equipped:
            return
        self.equipped = False
        self.grapple_active = False
        self.grapple_target = None
        self.grapple_target_pos = None
        self.grapple_head_pos = None
        self.grapple_state = "idle"
        self.bash_auto = False
        self.has_debuff = False
        self.aim_line_active = False
        # 卸下瞬间开启冷却
        self.riot_gear_cd_timer = self.riot_gear_base_cd * cd_reduction_mult

    def update(self, dt, player_x, player_y, facing_angle, move_speed_mult=1.0, cd_reduction_mult=1.0):
        self.facing_angle = facing_angle
        # 冷却计时
        if self.riot_gear_cd_timer > 0:
            self.riot_gear_cd_timer -= dt

        # 体力恢复
        if self.stamina < self.max_stamina:
            regen = self.stamina_regen * dt
            if self.has_debuff:
                regen *= 0.5
            self.stamina = min(self.max_stamina, self.stamina + regen)
        if self.bash_cooldown > 0:
            self.bash_cooldown -= dt
        if self.grapple_cooldown > 0:
            self.grapple_cooldown -= dt
        if self.bash_anim_timer > 0:
            self.bash_anim_timer -= dt

        self._update_grapple(dt, player_x, player_y)

        if self.equipped:
            self.equip_time += dt
            if self.equip_time > self.debuff_threshold and not self.has_debuff:
                self.has_debuff = True
            # 装备超时自动卸下
            if self.equip_time >= self.debuff_threshold + 10.0:
                self.unequip(cd_reduction_mult)

    def get_debuff_speed_mult(self):
        if self.has_debuff:
            return 1.0 - self.debuff_speed_penalty
        return 1.0

    def _update_grapple(self, dt, player_x, player_y):
        """更新钩爪状态 - 新逻辑"""
        if not self.grapple_active:
            return

        if self.grapple_state == "shooting":
            # 钩爪头飞向目标
            dx = self.grapple_target_pos[0] - self.grapple_head_pos[0]
            dy = self.grapple_target_pos[1] - self.grapple_head_pos[1]
            dist = math.hypot(dx, dy)

            move_dist = min(dist, self.grapple_speed * dt * 60)
            if dist > 0:
                self.grapple_head_pos[0] += (dx / dist) * move_dist
                self.grapple_head_pos[1] += (dy / dist) * move_dist

            # 检查是否到达目标或超出射程
            new_dist = math.hypot(
                self.grapple_target_pos[0] - self.grapple_head_pos[0],
                self.grapple_target_pos[1] - self.grapple_head_pos[1]
            )
            total_dist = math.hypot(
                self.grapple_head_pos[0] - player_x,
                self.grapple_head_pos[1] - player_y
            )

            if new_dist < 5:  # 到达目标位置
                if self.grapple_target:
                    # 勾中目标，进入僵直
                    self.grapple_state = "hit"
                    self.grapple_hit_stun_timer = self.grapple_hit_stun_duration
                else:
                    self.grapple_state = "retracting"
            elif total_dist >= self.grapple_max_range:
                self.grapple_state = "retracting"

        elif self.grapple_state == "hit":
            # 僵直阶段 - 钩爪绷紧
            self.grapple_hit_stun_timer -= dt
            if self.grapple_hit_stun_timer <= 0:
                self.grapple_state = "pulling"
            # 同步更新目标位置到钩爪头
            if self.grapple_target and hasattr(self.grapple_target, 'alive') and self.grapple_target.alive:
                self.grapple_head_pos = [self.grapple_target.x, self.grapple_target.y]
                # 给目标添加被勾状态
                if hasattr(self.grapple_target, 'grappled'):
                    self.grapple_target.grappled = True

        elif self.grapple_state == "pulling":
            if self.grapple_target and hasattr(self.grapple_target, 'alive') and self.grapple_target.alive:
                # 慢速同步拉回
                dx = player_x - self.grapple_target.x
                dy = player_y - self.grapple_target.y
                dist = math.hypot(dx, dy)

                if dist > 60:
                    pull_speed = self.grapple_pull_speed * dt * 60
                    self.grapple_target.x += (dx / dist) * pull_speed
                    self.grapple_target.y += (dy / dist) * pull_speed
                    self.grapple_head_pos = [self.grapple_target.x, self.grapple_target.y]
                else:
                    # 到达玩家附近，释放
                    if hasattr(self.grapple_target, 'grappled'):
                        self.grapple_target.grappled = False
                    self._reset_grapple()
            else:
                self.grapple_state = "retracting"

        elif self.grapple_state == "retracting":
            dx = player_x - self.grapple_head_pos[0]
            dy = player_y - self.grapple_head_pos[1]
            dist = math.hypot(dx, dy)

            if dist < self.grapple_speed * 1.5 * dt * 60:
                self._reset_grapple()
            else:
                move_dist = self.grapple_speed * 1.5 * dt * 60
                self.grapple_head_pos[0] += (dx / dist) * move_dist
                self.grapple_head_pos[1] += (dy / dist) * move_dist

    def _reset_grapple(self):
        """重置钩爪状态"""
        self.grapple_active = False
        if self.grapple_target and hasattr(self.grapple_target, 'grappled'):
            self.grapple_target.grappled = False
        self.grapple_target = None
        self.grapple_target_pos = None
        self.grapple_head_pos = None
        self.grapple_state = "idle"

    def get_shield_rect(self, player_x, player_y):
        if not self.equipped:
            return None
        angle_rad = math.radians(self.facing_angle)
        shield_cx = player_x + math.cos(angle_rad) * self.shield_offset
        shield_cy = player_y + math.sin(angle_rad) * self.shield_offset
        return pygame.Rect(
            shield_cx - self.shield_width // 2,
            shield_cy - self.shield_height // 2,
            self.shield_width,
            self.shield_height
        )

    def get_shield_front_arc(self, player_x, player_y):
        if not self.equipped:
            return None
        angle_rad = math.radians(self.facing_angle)
        shield_cx = player_x + math.cos(angle_rad) * self.shield_offset
        shield_cy = player_y + math.sin(angle_rad) * self.shield_offset
        return (shield_cx, shield_cy, self.facing_angle, 60)

    def check_shield_block(self, player_x, player_y, attack_x, attack_y):
        if not self.equipped or self.shield_broken:
            return False
        shield_rect = self.get_shield_rect(player_x, player_y)
        if shield_rect and shield_rect.collidepoint(attack_x, attack_y):
            return True
        dx = attack_x - player_x
        dy = attack_y - player_y
        attack_angle = math.degrees(math.atan2(dy, dx))
        angle_diff = abs((attack_angle - self.facing_angle + 180) % 360 - 180)
        return angle_diff < 60

    def take_damage(self, damage, damage_type="melee", from_front=True, attack_x=None, attack_y=None):
        if not self.equipped:
            return damage
        if from_front and not self.shield_broken:
            if damage_type == "magic" or damage_type == "aoe":
                return 0
            self.viewing_window_hp -= damage
            if self.viewing_window_hp <= 0:
                self.viewing_window_hp = 0
                self.shield_broken = True
                self.shield_hp -= damage * 2
                if self.shield_hp <= 0:
                    self.shield_hp = 0
            return 0
        else:
            if self.shield_broken:
                if damage_type == "melee":
                    return damage * (1 - self.melee_reduction)
                elif damage_type == "ranged":
                    return damage * (1 - self.ranged_reduction)
                elif damage_type == "magic":
                    return 0 if self.magic_immunity else damage
                return damage
            else:
                return damage * 0.5

    def can_bash(self):
        return self.equipped and self.bash_cooldown <= 0 and self.stamina >= self.bash_stamina_cost

    def bash(self, direction_angle=None, is_sprint=False):
        if not self.can_bash():
            return 0, False, 0
        self.stamina -= self.bash_stamina_cost
        self.bash_cooldown = self.bash_max_cooldown
        damage = 180 if not is_sprint else 250
        bash_range = 120 if not is_sprint else 90
        if direction_angle is not None:
            self.bash_direction = direction_angle
        else:
            self.bash_direction = self.facing_angle
        self.bash_anim_timer = self.bash_anim_duration
        angle_rad = math.radians(self.bash_direction)
        self.bash_hit_pos = (
            self.shield_offset * math.cos(angle_rad),
            self.shield_offset * math.sin(angle_rad)
        )
        return damage, True, bash_range

    def can_grapple(self):
        return self.equipped and self.grapple_cooldown <= 0

    def use_grapple(self, target_x, target_y, player_x, player_y, target=None):
        """使用钩爪 - 新逻辑：直接发射"""
        if not self.can_grapple():
            return False

        dx = target_x - player_x
        dy = target_y - player_y
        dist = math.hypot(dx, dy)

        if dist > self.grapple_max_range:
            ratio = self.grapple_max_range / dist
            dx *= ratio
            dy *= ratio
            target_x = player_x + dx
            target_y = player_y + dy
            dist = self.grapple_max_range

        # 只消耗CD，不消耗体力
        self.grapple_cooldown = self.grapple_max_cooldown
        self.grapple_active = True
        self.grapple_target_pos = (target_x, target_y)
        self.grapple_head_pos = [player_x, player_y]
        self.grapple_state = "shooting"
        self.grapple_target = target
        return True

    def start_aim(self, angle):
        """开始瞄准（长按）"""
        self.aim_line_active = True
        self.aim_line_angle = angle
        self.aim_line_press_time = 0

    def update_aim(self, angle, dt):
        """更新瞄准方向"""
        if self.aim_line_active:
            self.aim_line_angle = angle
            self.aim_line_press_time += dt

    def is_long_press(self):
        """检查是否长按"""
        return self.aim_line_active and self.aim_line_press_time >= self.aim_threshold

    def end_aim(self):
        """结束瞄准"""
        was_long = self.is_long_press()
        self.aim_line_active = False
        self.aim_line_press_time = 0
        return was_long

    def set_grapple_target(self, enemy):
        self.grapple_target = enemy
        if enemy:
            self.grapple_target_pos = (enemy.x, enemy.y)

    def draw(self, screen, player_x, player_y, camera_x, camera_y, scale=1.0):
        if not self.equipped:
            return

        px = int((player_x - camera_x) * scale)
        py = int((player_y - camera_y) * scale)

        shield_width = int(self.shield_width * scale)
        shield_height = int(self.shield_height * scale)

        angle_rad = math.radians(self.facing_angle)
        shield_offset_x = math.cos(angle_rad) * self.shield_offset * scale
        shield_offset_y = math.sin(angle_rad) * self.shield_offset * scale

        shield_rect = pygame.Rect(
            px + shield_offset_x - shield_width // 2,
            py + shield_offset_y - shield_height // 2,
            shield_width, shield_height
        )

        # 盾牌颜色根据状态变化
        if self.shield_broken:
            color = DARK_GRAY
        elif self.viewing_window_hp < self.max_viewing_window_hp * 0.3:
            color = (*RED[:3], 180)
        elif self.viewing_window_hp < self.max_viewing_window_hp * 0.6:
            color = (*ORANGE[:3], 200)
        else:
            color = BLUE

        pygame.draw.rect(screen, color, shield_rect, border_radius=max(1, int(5 * scale)))
        pygame.draw.rect(screen, WHITE, shield_rect, max(1, int(2 * scale)), border_radius=max(1, int(5 * scale)))

        # 观察窗
        if not self.shield_broken:
            ww = max(2, int(20 * scale))
            wh = max(2, int(30 * scale))
            window_rect = pygame.Rect(
                px + shield_offset_x - ww // 2,
                py + shield_offset_y - wh // 2,
                ww, wh
            )
            if self.viewing_window_hp > 50:
                window_color = CYAN
            elif self.viewing_window_hp > 20:
                window_color = YELLOW
            else:
                window_color = RED
            pygame.draw.rect(screen, window_color, window_rect)
            pygame.draw.rect(screen, WHITE, window_rect, max(1, int(scale)))

            # 观察窗HP条
            if self.viewing_window_hp < self.max_viewing_window_hp:
                bar_w = ww
                bar_h = max(2, int(3 * scale))
                bar_y = window_rect.bottom + 2
                hp_ratio = self.viewing_window_hp / self.max_viewing_window_hp
                pygame.draw.rect(screen, RED, (window_rect.x, bar_y, bar_w, bar_h))
                pygame.draw.rect(screen, GREEN, (window_rect.x, bar_y, int(bar_w * hp_ratio), bar_h))

        # DEBUFF警告
        if self.has_debuff:
            if int(pygame.time.get_ticks() / 500) % 2 == 0:
                pygame.draw.rect(screen, RED, shield_rect, max(2, int(3 * scale)), border_radius=max(1, int(5 * scale)))

        # 绘制钩爪
        if self.grapple_active and self.grapple_head_pos:
            hx = int((self.grapple_head_pos[0] - camera_x) * scale)
            hy = int((self.grapple_head_pos[1] - camera_y) * scale)

            # 绿色轨迹线
            pygame.draw.line(screen, GREEN, (px, py), (hx, hy), max(2, int(4 * scale)))

            # 钩爪头
            head_size = max(4, int(10 * scale))
            pygame.draw.circle(screen, ORANGE, (hx, hy), head_size)
            pygame.draw.circle(screen, YELLOW, (hx, hy), head_size - 2)
            pygame.draw.circle(screen, WHITE, (hx, hy), head_size, max(1, int(2 * scale)))

            # 僵直时的火花
            if self.grapple_state == "hit":
                for _ in range(8):
                    spark_x = hx + random.randint(-12, 12)
                    spark_y = hy + random.randint(-12, 12)
                    pygame.draw.circle(screen, YELLOW, (spark_x, spark_y), max(1, int(2 * scale)))
                # 绷紧效果
                tension = abs(math.sin(pygame.time.get_ticks() / 100))
                pygame.draw.circle(screen, (*RED[:3], int(150 * tension)), (hx, hy), int(head_size * (1 + tension * 0.5)))

            # 拉回时的火花
            if self.grapple_state == "pulling":
                for _ in range(5):
                    spark_x = hx + random.randint(-8, 8)
                    spark_y = hy + random.randint(-8, 8)
                    pygame.draw.circle(screen, YELLOW, (spark_x, spark_y), max(1, int(2 * scale)))

        # 绘制预瞄线
        if self.aim_line_active:
            aim_dist = self.grapple_max_range * scale
            aim_end_x = px + math.cos(self.aim_line_angle) * aim_dist
            aim_end_y = py + math.sin(self.aim_line_angle) * aim_dist
            # 虚线预瞄
            dash_len = 15
            gap_len = 8
            total_dist = aim_dist
            current = 0
            while current < total_dist:
                ratio_start = current / total_dist
                ratio_end = min((current + dash_len) / total_dist, 1.0)
                sx = px + (aim_end_x - px) * ratio_start
                sy = py + (aim_end_y - py) * ratio_start
                ex = px + (aim_end_x - px) * ratio_end
                ey = py + (aim_end_y - py) * ratio_end
                pygame.draw.line(screen, (*GREEN[:3], 120), (sx, sy), (ex, ey), max(1, int(2 * scale)))
                current += dash_len + gap_len
            # 终点标记
            pygame.draw.circle(screen, (*GREEN[:3], 80), (int(aim_end_x), int(aim_end_y)), int(8 * scale))
            pygame.draw.circle(screen, GREEN, (int(aim_end_x), int(aim_end_y)), int(8 * scale), max(1, int(2 * scale)))

        # 绘制肘击动画
        if self.bash_anim_timer > 0:
            progress = 1 - (self.bash_anim_timer / self.bash_anim_duration)
            bash_dist = 40 * progress * scale
            angle_rad = math.radians(self.bash_direction)
            bx = px + math.cos(angle_rad) * bash_dist
            by = py + math.sin(angle_rad) * bash_dist

            wave_size = int(25 * scale * (1 - progress))
            pygame.draw.circle(screen, (*CYAN[:3], 150), (int(bx), int(by)), wave_size, 2)
            pygame.draw.circle(screen, CYAN, (int(bx), int(by)), max(2, int(10 * scale)))
            line_len = 30 * scale
            for offset in [-20, 0, 20]:
                off_rad = math.radians(self.bash_direction + offset)
                sx = bx + math.cos(off_rad) * line_len * 0.5
                sy = by + math.sin(off_rad) * line_len * 0.5
                ex = bx + math.cos(off_rad) * line_len
                ey = by + math.sin(off_rad) * line_len
                pygame.draw.line(screen, WHITE, (sx, sy), (ex, ey), max(1, int(2 * scale)))

        # 绘制体力条
        sw = int(50 * scale)
        sh = max(2, int(6 * scale))
        sx = px - sw // 2
        sy = py + int(45 * scale)
        pygame.draw.rect(screen, DARK_GRAY, (sx, sy, sw, sh))
        pygame.draw.rect(screen, GREEN, (sx, sy, int(sw * (self.stamina / self.max_stamina)), sh))
        pygame.draw.rect(screen, WHITE, (sx, sy, sw, sh), max(1, int(scale)))

        if self.stamina < self.bash_stamina_cost:
            pygame.draw.rect(screen, (*RED[:3], 100), (sx, sy, sw, sh))


class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = 16
        self.speed = 3.5
        self.base_speed = 3.5

        self.max_hp = 100
        self.hp = 100
        self.level = 1
        self.exp = 0
        self.exp_to_level = 100
        self.score = 0

        self.weapons = [Weapon(WeaponType.PISTOL)]
        self.current_weapon_idx = 0

        self.skill_tree = SkillTree()
        self.active_skills = {}

        self.riot_gear = RiotGear()
        self.riot_gear_cooldown = 0
        self.riot_gear_equip_cooldown = 30.0

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
        for w in self.weapons:
            if w.weapon_type == weapon_type:
                w.upgrade()
                return
        self.weapons.append(Weapon(weapon_type))

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

    def update(self, dt, move_x, move_y, mouse_angle, world=None):
        self._update_stats()
        # Buff系统对攻速/换弹/暴击的加成
        self.fire_rate_mult *= self.buff_manager.get_attack_speed_mult()
        self.reload_speed_mult *= self.buff_manager.get_reload_speed_mult()
        self.crit_chance += self.buff_manager.get_crit_chance_add()

        # 更新Buff系统（处理持续伤害/治疗等）
        self.buff_manager.update(dt, self)
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

        if self.riot_gear.equipped or self.riot_gear.riot_gear_cd_timer > 0:
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

    def take_damage(self, damage, damage_type="melee", from_front=False, attack_x=None, attack_y=None):
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

    def draw(self, screen, camera_x, camera_y, font, scale=1.0):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(2, int(self.size * scale))

        if self.invincible_timer > 0 and int(self.invincible_timer * 10) % 2 == 0:
            pass
        else:
            pygame.draw.circle(screen, BLUE, (px, py), s)
            angle_rad = math.radians(self.facing_angle)
            end_x = px + math.cos(angle_rad) * int(25 * scale)
            end_y = py + math.sin(angle_rad) * int(25 * scale)
            pygame.draw.line(screen, WHITE, (px, py), (end_x, end_y), max(1, int(3 * scale)))

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


class Enemy:
    def __init__(self, x, y, enemy_type, wave, difficulty="normal"):
        self.x = x
        self.y = y
        self.enemy_type = enemy_type
        self.wave = wave
        self.difficulty = difficulty
        self.alive = True
        self.knockdown_timer = 0
        self.frozen_timer = 0
        self.grappled = False
        self._collision_skip = 0

        # 特殊状态
        self.invisible = False
        self.invisible_timer = 0
        self.invisible_cooldown = 0
        self.split_count = 0  # 分裂次数
        self.heal_radius = 100  # 治疗半径
        self.heal_timer = 0
        self.explode_timer = 0  # 爆炸倒计时
        self.is_exploding = False
        self.phantom_flicker = 0  # 幻影闪烁
        # Buff系统
        self.buff_manager = BuffManager()
        self._setup_enemy()

        # =========【新增Boss技能计时器】=========
        self.boss_dash_cd = 0.0
        self.boss_aoe_cd = 0.0
        self.boss_shoot_cd = 0.0
        self.boss_shield_cd = 0.0
        self.is_dashing = False
        self.dash_target_x = 0.0
        self.dash_target_y = 0.0
        self.dash_speed = 0.0
        self.dash_timer = 0.0
        self.boss_hold_shield = False

        self.boss_execution_cd = 0.0       # 处决大招CD
        self.boss_execution_windup = 0.0  # 处决前摇时间（提示阶段）
        self.boss_is_executing = False     # 是否正在处决前摇
        self.boss_salvo_cd = 0.0          # 向某连射CD
        self.boss_backstep_cd = 0.0       # 向某后撤滑步CD
        # === 新增Boss技能计时器 ===
        self.boss_summon_cd = 0.0         # 召唤小怪CD
        self.boss_charge_cd = 0.0         # 狂暴冲锋CD
        self.boss_regen_cd = 0.0          # 护盾再生/回血CD
        self.boss_ground_slam_cd = 0.0    # 地震波CD
        self.boss_barrage_cd = 0.0        # 弹幕扫射CD
        self.boss_smoke_cd = 0.0          # 烟雾弹CD
        self.boss_teleport_cd = 0.0       # 闪现CD
        self.boss_grenade_cd = 0.0        # 手雷CD
        self.boss_is_charging = False     # 是否正在冲锋
        self.boss_charge_timer = 0.0      # 冲锋持续时间
        self.boss_charge_dir = (0, 0)     # 冲锋方向
        # === 特种僵尸能力计时器 ===
        self.special_ability_cd = 0.0     # 通用特种能力CD
        self.fast_dash_ready = True       # 快速僵尸冲刺就绪
        self.tank_slam_cd = 0.0           # 坦克重击CD
        self.ranged_burst_cd = 0.0        # 远程连射CD
        self.phantom_teleport_cd = 0.0    # 幻影瞬移CD
        self.shield_charge_cd = 0.0       # 盾兵冲锋CD
        self.healer_wave_cd = 0.0         # 治疗波CD

    def _setup_enemy(self):
        base_configs = {
            EnemyType.ZOMBIE_NORMAL: {
                "hp": 35, "speed": 1.8, "damage": 12, "size": 15,
                "color": DARK_GREEN, "exp": 10, "score": 10
            },
            EnemyType.ZOMBIE_FAST: {
                "hp": 20, "speed": 3.5, "damage": 10, "size": 12,
                "color": POISON_GREEN, "exp": 15, "score": 15
            },
            EnemyType.ZOMBIE_TANK: {
                "hp": 120, "speed": 1.0, "damage": 25, "size": 22,
                "color": GRAY, "exp": 30, "score": 30
            },
            EnemyType.ZOMBIE_RANGED: {
                "hp": 30, "speed": 1.5, "damage": 18, "size": 14,
                "color": PURPLE, "exp": 20, "score": 20,
                "attack_range": 300, "attack_cooldown": 2.0
            },
            # === 新机制僵尸 ===
            EnemyType.ZOMBIE_EXPLODER: {
                "hp": 40, "speed": 2.5, "damage": 8, "size": 16,
                "color": RUST, "exp": 25, "score": 25,
                "is_exploder": True, "explode_radius": 100, "explode_damage": 100
            },
            EnemyType.ZOMBIE_CRAWLER: {
                "hp": 15, "speed": 4.0, "damage": 8, "size": 8,
                "color": SLATE, "exp": 12, "score": 12,
                "is_crawler": True, "dodge_chance": 0.3
            },
            EnemyType.ZOMBIE_SPLITTER: {
                "hp": 80, "speed": 1.3, "damage": 15, "size": 18,
                "color": BLOOD_RED, "exp": 35, "score": 35,
                "is_splitter": True, "split_into": 2
            },
            EnemyType.ZOMBIE_SHIELD: {
                "hp": 60, "speed": 1.2, "damage": 15, "size": 17,
                "color": CHARCOAL, "exp": 22, "score": 22,
                "is_shield": True, "front_reduction": 0.6
            },
            EnemyType.ZOMBIE_HEALER: {
                "hp": 35, "speed": 1.0, "damage": 10, "size": 14,
                "color": GREEN, "exp": 30, "score": 30,
                "is_healer": True, "heal_amount": 5, "heal_interval": 2.0
            },
            EnemyType.ZOMBIE_PHANTOM: {
                "hp": 45, "speed": 2.0, "damage": 20, "size": 15,
                "color": PURPLE, "exp": 28, "score": 28,
                "is_phantom": True, "invisible_duration": 2.0, "visible_duration": 3.0
            },
            EnemyType.BOSS_LONG: {
                "hp": 3000, "speed": 1.5, "damage": 50, "size": 35,
                "color": BLOOD_RED, "exp": 500, "score": 1000,
                "is_boss": True, "name": "龙某"
            },
            EnemyType.BOSS_XIANG: {
                "hp": 2500, "speed": 1.8, "damage": 30, "size": 32,
                "color": RUST, "exp": 500, "score": 1000,
                "is_boss": True, "name": "向某"
            },
            # === 新Boss ===
            EnemyType.BOSS_MUTANT: {
                "hp": 4000, "speed": 2.2, "damage": 45, "size": 38,
                "color": BLOOD_RED, "exp": 800, "score": 1500,
                "is_boss": True, "name": "变异体·深渊",
                "has_combo": True, "combo_damage_mult": 2.5,
            },
            EnemyType.BOSS_QUEEN: {
                "hp": 3500, "speed": 1.3, "damage": 25, "size": 40,
                "color": PURPLE, "exp": 800, "score": 1500,
                "is_boss": True, "name": "尸潮女王",
                "summons_minions": True, "summon_interval": 8.0,
            },
            EnemyType.BOSS_TITAN: {
                "hp": 6000, "speed": 0.9, "damage": 70, "size": 50,
                "color": CHARCOAL, "exp": 1000, "score": 2000,
                "is_boss": True, "name": "泰坦",
                "is_titan": True, "stomp_damage": 120, "stomp_radius": 150,
            },
            # === 精英怪 ===
            EnemyType.ELITE_BRUTE: {
                "hp": 300, "speed": 1.4, "damage": 35, "size": 24,
                "color": DARK_RED, "exp": 80, "score": 80,
                "is_elite": True, "name": "精英蛮兵",
                "heavy_attack_chance": 0.3, "heavy_damage_mult": 2.5,
            },
            EnemyType.ELITE_ASSASSIN: {
                "hp": 150, "speed": 4.5, "damage": 40, "size": 14,
                "color": CYAN, "exp": 80, "score": 80,
                "is_elite": True, "name": "精英刺客",
                "dash_chance": 0.25, "dash_damage_mult": 3.0,
            },
            EnemyType.ELITE_SORCERER: {
                "hp": 180, "speed": 1.2, "damage": 25, "size": 16,
                "color": PURPLE, "exp": 90, "score": 90,
                "is_elite": True, "name": "精英术士",
                "is_ranged": True, "projectile_damage": 30, "attack_range": 350,
                "applies_curse": True,
            },
            EnemyType.ELITE_GUARDIAN: {
                "hp": 400, "speed": 1.0, "damage": 20, "size": 22,
                "color": GOLD, "exp": 100, "score": 100,
                "is_elite": True, "name": "精英守卫",
                "aura_heal": True, "aura_radius": 120, "aura_heal_amount": 3,
                "shield_reduction": 0.5,
            },
            # === 新普通僵尸 ===
            EnemyType.ZOMBIE_SPITTER: {
                "hp": 30, "speed": 1.5, "damage": 10, "size": 14,
                "color": LIME, "exp": 18, "score": 18,
                "is_ranged": True, "projectile_damage": 12, "attack_range": 250,
                "applies_corrosion": True,
            },
            EnemyType.ZOMBIE_LEAPER: {
                "hp": 25, "speed": 2.0, "damage": 18, "size": 13,
                "color": ORANGE, "exp": 20, "score": 20,
                "leap_chance": 0.15, "leap_range": 200, "leap_damage_mult": 2.0,
            },
            EnemyType.ZOMBIE_CORPSE_EATER: {
                "hp": 50, "speed": 1.3, "damage": 15, "size": 17,
                "color": BROWN, "exp": 25, "score": 25,
                "eats_corpses": True, "grow_per_corpse": 1.2,
            },
            EnemyType.ZOMBIE_WRAITH: {
                "hp": 35, "speed": 2.5, "damage": 15, "size": 15,
                "color": PURPLE, "exp": 30, "score": 30,
                "is_wraith": True, "phase_through": True,
                "applies_fear": True, "fear_chance": 0.2,
            }
        }

        config = base_configs.get(self.enemy_type, base_configs[EnemyType.ZOMBIE_NORMAL])
        for k, v in config.items():
            setattr(self, k, v)

        diff_mult = {"简单": 0.7, "普通": 1.0, "困难": 1.5, "地狱": 2.2}
        dm = diff_mult.get(self.difficulty, 1.0)

        # 区分：普通敌人wave=波次数字，Boss wave=horde_manager实例
        if isinstance(self.wave, (int, float)):
            wave_mult = 1 + (self.wave - 1) * 0.3
            wave_num = self.wave
        else:
            # Boss，wave是horde_manager，波次取固定1
            wave_mult = 1.0
            wave_num = 1

        time_scale = 1.0
        if hasattr(self.wave, "total_time"):
            time_scale = min(1.8, 1.0 + self.wave.total_time / 300.0)

        self.max_hp = self.hp = int(config["hp"] * wave_mult * dm * time_scale)
        self.speed = config["speed"] * (1 + (wave_num - 1) * 0.1)
        self.damage = int(config["damage"] * wave_mult * dm * time_scale)
        self.attack_timer = 0
        self.anim_frame = 0
        self.anim_timer = 0

    def update(self, dt, player_x, player_y, player):
        # 更新Buff系统（持续伤害/治疗等）
        self.buff_manager.update(dt, self)
        self._buff_speed_mult = self.buff_manager.get_speed_mult()
        # Buff冻结/眩晕优先
        if self.buff_manager.is_stunned() or self.buff_manager.is_frozen():
            return
        if self.knockdown_timer > 0:
            self.knockdown_timer -= dt
            return
        if self.frozen_timer > 0:
            self.frozen_timer -= dt
            return
        if self.grappled:
            dx = player_x - self.x
            dy = player_y - self.y
            dist = math.hypot(dx, dy)
            if dist > 50:
                self.x += (dx / dist) * self.speed * 3 * self._buff_speed_mult * dt * 60
                self.y += (dy / dist) * self.speed * 3 * self._buff_speed_mult * dt * 60
            else:
                self.grappled = False
            return

        # 幻影僵尸隐身逻辑
        if getattr(self, "is_phantom", False):
            self.invisible_timer -= dt
            self.invisible_cooldown -= dt
            if self.invisible_timer > 0:
                self.invisible = True
            else:
                self.invisible = False
                if self.invisible_cooldown <= 0:
                    self.invisible_timer = self.invisible_duration
                    self.invisible_cooldown = self.visible_duration

        # 治疗僵尸逻辑
        if getattr(self, "is_healer", False):
            self.heal_timer -= dt
            if self.heal_timer <= 0:
                self.heal_timer = self.heal_interval
                # 治疗周围僵尸
                # 这个在 game.py 中处理

        # 爆炸僵尸逻辑
        if getattr(self, "is_exploder", False):
            dist_to_player = math.hypot(player_x - self.x, player_y - self.y)
            if dist_to_player < 60 and not self.is_exploding:
                self.is_exploding = True
                self.explode_timer = 1.5  # 1.5秒后爆炸
            if self.is_exploding:
                self.explode_timer -= dt
                if self.explode_timer <= 0:
                    self.alive = False  # 自爆死亡
                    return "explode"

        dx = player_x - self.x
        dy = player_y - self.y
        dist = math.hypot(dx, dy)

        if dist > 0:
            if getattr(self, "is_boss", False):
                self._boss_behavior(dt, player_x, player_y, dist, player)
            else:
                # === 特种僵尸特色能力 ===
                special_result = self._special_ability(dt, player_x, player_y, dist)
                if special_result:
                    return special_result

                if getattr(self, "attack_range", 0) > 0 and dist < self.attack_range:
                    if dist < self.attack_range * 0.5:
                        self.x -= (dx / dist) * self.speed * self._buff_speed_mult * dt * 60
                        self.y -= (dy / dist) * self.speed * self._buff_speed_mult * dt * 60
                    else:
                        self._ranged_attack(dt, player_x, player_y, dist)
                else:
                    self.x += (dx / dist) * self.speed * self._buff_speed_mult * dt * 60
                    self.y += (dy / dist) * self.speed * self._buff_speed_mult * dt * 60

        self.anim_timer += dt
        if self.anim_timer > 0.2:
            self.anim_timer = 0
            self.anim_frame = (self.anim_frame + 1) % 4

    def _boss_behavior(self, dt, player_x, player_y, dist, player):
        """
        BOSS_LONG(龙某):近战盾Boss，血量低释放重劈处决
        BOSS_XIANG(向某):远程Boss，新增后撤滑步、连射，低血量霰弹处决爆发
        返回: None / "boss_aoe" / "boss_execution_slash" / "boss_execution_salvo" / dict(子弹)
        """
        # 更新全部技能CD
        if self.boss_dash_cd > 0:
            self.boss_dash_cd -= dt
        if self.boss_aoe_cd > 0:
            self.boss_aoe_cd -= dt
        if self.boss_shoot_cd > 0:
            self.boss_shoot_cd -= dt
        if self.boss_shield_cd > 0:
            self.boss_shield_cd -= dt
        if self.boss_execution_cd > 0:
            self.boss_execution_cd -= dt
        if self.boss_salvo_cd > 0:
            self.boss_salvo_cd -= dt
        if self.boss_backstep_cd > 0:
            self.boss_backstep_cd -= dt
        if self.boss_summon_cd > 0:
            self.boss_summon_cd -= dt
        if self.boss_charge_cd > 0:
            self.boss_charge_cd -= dt
        if self.boss_regen_cd > 0:
            self.boss_regen_cd -= dt
        if self.boss_ground_slam_cd > 0:
            self.boss_ground_slam_cd -= dt
        if self.boss_barrage_cd > 0:
            self.boss_barrage_cd -= dt
        if self.boss_smoke_cd > 0:
            self.boss_smoke_cd -= dt
        if self.boss_teleport_cd > 0:
            self.boss_teleport_cd -= dt
        if self.boss_grenade_cd > 0:
            self.boss_grenade_cd -= dt

        # ========= 狂暴冲锋处理 =========
        if self.boss_is_charging:
            self.boss_charge_timer -= dt
            if self.boss_charge_timer <= 0:
                self.boss_is_charging = False
            else:
                dx, dy = self.boss_charge_dir
                self.x += dx * 12.0 * dt * 60
                self.y += dy * 12.0 * dt * 60
                return "boss_charge_trail"

        # ========= 处决前摇处理 =========
        if self.boss_is_executing:
            self.boss_execution_windup -= dt
            if self.boss_execution_windup <= 0:
                self.boss_is_executing = False
                # 根据boss类型返回处决攻击标记
                if self.enemy_type == EnemyType.BOSS_LONG:
                    return "boss_execution_slash"
                elif self.enemy_type == EnemyType.BOSS_XIANG:
                    return "boss_execution_salvo"
                elif self.enemy_type == EnemyType.BOSS_MUTANT:
                    return "boss_execution_mutant"
                elif self.enemy_type == EnemyType.BOSS_QUEEN:
                    return "boss_execution_queen"
                elif self.enemy_type == EnemyType.BOSS_TITAN:
                    return "boss_execution_titan"
            return None

        # 冲刺移动逻辑
        if self.is_dashing:
            self.dash_timer -= dt
            dx = self.dash_target_x - self.x
            dy = self.dash_target_y - self.y
            d = math.hypot(dx, dy)
            if d < 12 or self.dash_timer <= 0:
                self.is_dashing = False
            else:
                self.x += (dx / d) * self.dash_speed * dt * 60
                self.y += (dy / d) * self.dash_speed * dt * 60
            return None

        hp_ratio = self.hp / self.max_hp
        # 血量低于30%，可以释放处决大招，有冷却
        can_execution = (hp_ratio <= 0.30) and (self.boss_execution_cd <= 0)

        if self.enemy_type == EnemyType.BOSS_LONG:
            # ----龙某：近战盾Boss----
            # 举盾：距离远时概率举盾，减少受到远程伤害
            if dist > 220 and self.boss_shield_cd <= 0 and random.random() < 0.02:
                self.boss_hold_shield = True
                self.boss_shield_cd = 7.0
            if dist < 160:
                self.boss_hold_shield = False

            # 【处决重劈】血量低概率启动前摇
            if can_execution and dist < 170 and random.random() < 0.025:
                self.boss_is_executing = True
                self.boss_execution_windup = 1.1   # 1.1秒红色前摇警告
                self.boss_execution_cd = 14.0
                return None

            # 冲刺
            if dist > 110 and self.boss_dash_cd <= 0 and random.random() < 0.025:
                self.is_dashing = True
                self.dash_target_x = player_x
                self.dash_target_y = player_y
                self.dash_speed = 7.5
                self.dash_timer = 0.45
                self.boss_dash_cd = 4.5
                return None

            # AOE地面震荡
            if dist < 140 and self.boss_aoe_cd <= 0 and random.random() < 0.03:
                self.boss_aoe_cd = 5.0
                return "boss_aoe"

            # 【地震波】大范围环形AOE，低血量更频繁
            slam_chance = 0.02 if hp_ratio > 0.5 else 0.04
            if dist < 200 and self.boss_ground_slam_cd <= 0 and random.random() < slam_chance:
                self.boss_ground_slam_cd = 8.0
                return "boss_ground_slam"

            # 【狂暴冲锋】向玩家方向高速冲锋，带拖尾
            if dist > 150 and dist < 400 and self.boss_charge_cd <= 0 and random.random() < 0.02:
                self.boss_charge_cd = 6.0
                self.boss_is_charging = True
                self.boss_charge_timer = 0.5
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.boss_charge_dir = ((player_x - self.x) / d, (player_y - self.y) / d)
                return None

            # 【召唤小怪】低血量时召唤普通僵尸
            if hp_ratio < 0.5 and self.boss_summon_cd <= 0 and random.random() < 0.015:
                self.boss_summon_cd = 15.0
                return "boss_summon_melee"

            # 【护盾再生】低血量时回血
            if hp_ratio < 0.4 and self.boss_regen_cd <= 0 and random.random() < 0.01:
                self.boss_regen_cd = 20.0
                self.hp = min(self.max_hp, self.hp + self.max_hp * 0.15)
                return "boss_regen"

            # 普通向玩家移动
            if dist > 0:
                self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        elif self.enemy_type == EnemyType.BOSS_XIANG:
            # ----向某：远程Boss【增强：后撤滑步、连射模式、霰弹处决】----
            # 【处决霰弹爆发】近距离+残血启动前摇
            if can_execution and dist <160 and random.random() <0.025:
                self.boss_is_executing = True
                self.boss_execution_windup = 1.0
                self.boss_execution_cd =13.0
                return None

            # 后撤滑步：玩家靠近，拉开距离
            if dist <140 and self.boss_backstep_cd <=0 and random.random()<0.02:
                self.boss_backstep_cd =6.0
                back_dx = self.x - player_x
                back_dy = self.y - player_y
                b_dist = math.hypot(back_dx,back_dy)
                if b_dist>0:
                    self.x += (back_dx / b_dist)*90
                    self.y += (back_dy / b_dist)*90
                return None

            # 连射模式
            if dist>130 and self.boss_salvo_cd <=0 and random.random() <0.035:
                self.boss_salvo_cd =2.8
                # 连续3发子弹
                for _ in range(3):
                    return {
                        "x": self.x, "y": self.y,
                        "target_x": player_x, "target_y": player_y,
                        "damage": int(self.damage * 0.55)
                    }
            # 普通单发射击
            elif dist > 130 and self.boss_shoot_cd <=0 and random.random() <0.035:
                self.boss_shoot_cd = 1.6
                return {
                    "x": self.x, "y": self.y,
                    "target_x": player_x, "target_y": player_y,
                    "damage": int(self.damage * 0.65)
                }

            # 【弹幕扫射】环形发射多方向子弹
            barrage_chance = 0.02 if hp_ratio > 0.5 else 0.035
            if self.boss_barrage_cd <= 0 and random.random() < barrage_chance:
                self.boss_barrage_cd = 7.0
                return "boss_barrage"

            # 【烟雾弹】在玩家位置生成烟雾区域减速
            if dist > 100 and self.boss_smoke_cd <= 0 and random.random() < 0.015:
                self.boss_smoke_cd = 10.0
                return "boss_smoke"

            # 【手雷】投掷延迟爆炸手雷
            if dist > 120 and dist < 350 and self.boss_grenade_cd <= 0 and random.random() < 0.02:
                self.boss_grenade_cd = 6.0
                return "boss_grenade"

            # 【闪现】低血量时瞬移到玩家侧后方
            if hp_ratio < 0.6 and self.boss_teleport_cd <= 0 and random.random() < 0.015:
                self.boss_teleport_cd = 12.0
                angle = math.atan2(player_y - self.y, player_x - self.x) + math.radians(random.choice([120, -120]))
                teleport_dist = 150
                self.x = player_x + math.cos(angle) * teleport_dist
                self.y = player_y + math.sin(angle) * teleport_dist
                return "boss_teleport"

            # 【召唤远程小怪】低血量时召唤远程僵尸
            if hp_ratio < 0.5 and self.boss_summon_cd <= 0 and random.random() < 0.015:
                self.boss_summon_cd = 18.0
                return "boss_summon_ranged"

            # 近身冲刺
            if dist >90 and dist <240 and self.boss_dash_cd <=0 and random.random() <0.022:
                self.is_dashing = True
                self.dash_target_x = player_x
                self.dash_target_y = player_y
                self.dash_speed = 8.2
                self.dash_timer = 0.42
                self.boss_dash_cd = 5.0
                return None

            # 普通移动
            if dist > 0:
                self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        elif self.enemy_type == EnemyType.BOSS_MUTANT:
            # ----变异体·深渊：高伤害连招Boss----
            # 连招状态机
            if not hasattr(self, 'combo_state'):
                self.combo_state = 0
                self.combo_timer = 0
            if self.combo_timer > 0:
                self.combo_timer -= dt

            # 【处决：毁灭连招】残血+近距离启动
            if can_execution and dist < 180 and random.random() < 0.02:
                self.boss_is_executing = True
                self.boss_execution_windup = 0.8
                self.boss_execution_cd = 15.0
                self.combo_state = 1
                self.combo_timer = 2.5
                return None

            # 连招进行中：连续高伤害攻击
            if self.combo_state > 0 and self.combo_timer > 0:
                if self.combo_state == 1 and self.combo_timer < 2.0:
                    self.combo_state = 2
                    return "mutant_combo_hit"  # 第一击：上挑
                elif self.combo_state == 2 and self.combo_timer < 1.5:
                    self.combo_state = 3
                    d = math.hypot(player_x - self.x, player_y - self.y)
                    if d > 0:
                        self.x += (player_x - self.x) / d * 60
                        self.y += (player_y - self.y) / d * 60
                    return "mutant_combo_hit"  # 第二击：横斩
                elif self.combo_state == 3 and self.combo_timer < 0.8:
                    self.combo_state = 0
                    return "mutant_combo_finisher"  # 终结：下砸AOE
                return None

            # 【变异冲刺】高速冲刺
            if dist > 150 and self.boss_dash_cd <= 0 and random.random() < 0.03:
                self.is_dashing = True
                self.dash_target_x = player_x
                self.dash_target_y = player_y
                self.dash_speed = 10.0
                self.dash_timer = 0.35
                self.boss_dash_cd = 4.0
                return None

            # 【酸液喷射】远程扇形攻击
            if dist < 300 and self.boss_shoot_cd <= 0 and random.random() < 0.025:
                self.boss_shoot_cd = 3.0
                results = []
                base_angle = math.atan2(player_y - self.y, player_x - self.x)
                for offset in [-0.3, -0.15, 0, 0.15, 0.3]:
                    angle = base_angle + offset
                    results.append({
                        "x": self.x, "y": self.y,
                        "target_x": self.x + math.cos(angle) * 300,
                        "target_y": self.y + math.sin(angle) * 300,
                        "damage": int(self.damage * 0.5),
                        "applies_corrosion": True,
                    })
                return results

            # 【狂暴】血量低于50%时攻速移速提升
            if hp_ratio < 0.5:
                self.speed = getattr(self, 'base_speed', self.speed) * 1.3
                if not hasattr(self, 'base_speed'):
                    self.base_speed = self.speed / 1.3

            # 普通移动
            if dist > 0:
                self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        elif self.enemy_type == EnemyType.BOSS_QUEEN:
            # ----尸潮女王：召唤+控制Boss----
            # 【召唤小怪】定期召唤
            if self.boss_summon_cd <= 0 and random.random() < 0.02:
                self.boss_summon_cd = getattr(self, "summon_interval", 8.0)
                return "queen_summon"

            # 【精神控制】让玩家随机移动（恐惧效果）
            if dist < 250 and self.boss_smoke_cd <= 0 and random.random() < 0.015:
                self.boss_smoke_cd = 12.0
                return "queen_mind_control"

            # 【毒雾】在玩家位置生成毒雾
            if dist > 100 and self.boss_grenade_cd <= 0 and random.random() < 0.02:
                self.boss_grenade_cd = 7.0
                return "queen_poison_cloud"

            # 【触手攻击】地下触手突袭
            if dist < 200 and self.boss_ground_slam_cd <= 0 and random.random() < 0.02:
                self.boss_ground_slam_cd = 5.0
                return "queen_tentacle"

            # 【处决：虫群吞噬】残血启动
            if can_execution and dist < 200 and random.random() < 0.015:
                self.boss_is_executing = True
                self.boss_execution_windup = 1.2
                self.boss_execution_cd = 18.0
                return None

            # 女王移动较慢，保持中距离
            if dist < 150:
                if dist > 0:
                    self.x -= (player_x - self.x) / dist * self.speed * 0.5 * self._buff_speed_mult * dt * 60
                    self.y -= (player_y - self.y) / dist * self.speed * 0.5 * self._buff_speed_mult * dt * 60
            elif dist > 300:
                if dist > 0:
                    self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                    self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        elif self.enemy_type == EnemyType.BOSS_TITAN:
            # ----泰坦：巨型坦克Boss----
            # 【地震踩踏】大范围AOE
            if dist < 150 and self.boss_ground_slam_cd <= 0 and random.random() < 0.025:
                self.boss_ground_slam_cd = 6.0
                return "titan_stomp"

            # 【巨石投掷】远程攻击
            if dist > 200 and self.boss_shoot_cd <= 0 and random.random() < 0.02:
                self.boss_shoot_cd = 4.0
                return {
                    "x": self.x, "y": self.y,
                    "target_x": player_x, "target_y": player_y,
                    "damage": int(self.damage * 0.8),
                    "is_boulder": True,
                }

            # 【狂暴冲锋】长距离冲锋
            if dist > 250 and self.boss_charge_cd <= 0 and random.random() < 0.015:
                self.boss_charge_cd = 10.0
                self.boss_is_charging = True
                self.boss_charge_timer = 1.2
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.boss_charge_dir = ((player_x - self.x) / d, (player_y - self.y) / d)
                return None

            # 【处决：泰坦之怒】残血+大范围
            if can_execution and dist < 200 and random.random() < 0.015:
                self.boss_is_executing = True
                self.boss_execution_windup = 1.5
                self.boss_execution_cd = 20.0
                return None

            # 普通移动（缓慢但坚定）
            if dist > 0:
                self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        return None

    def _special_ability(self, dt, player_x, player_y, dist):
        """特种僵尸特色能力，返回None表示继续普通逻辑，返回字符串/dict表示触发技能"""
        # 更新通用CD
        if self.special_ability_cd > 0:
            self.special_ability_cd -= dt
        if self.tank_slam_cd > 0:
            self.tank_slam_cd -= dt
        if self.ranged_burst_cd > 0:
            self.ranged_burst_cd -= dt
        if self.phantom_teleport_cd > 0:
            self.phantom_teleport_cd -= dt
        if self.shield_charge_cd > 0:
            self.shield_charge_cd -= dt
        if self.healer_wave_cd > 0:
            self.healer_wave_cd -= dt

        # 快速僵尸：冲刺攻击（接近时突然加速冲刺）
        if self.enemy_type == EnemyType.ZOMBIE_FAST:
            if 60 < dist < 200 and self.fast_dash_ready and random.random() < 0.03:
                self.fast_dash_ready = False
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.x += (player_x - self.x) / d * 80
                    self.y += (player_y - self.y) / d * 80
                return "fast_dash"
            if dist > 250:
                self.fast_dash_ready = True

        # 坦克僵尸：重击AOE（近身时范围伤害）
        elif self.enemy_type == EnemyType.ZOMBIE_TANK:
            if dist < 80 and self.tank_slam_cd <= 0 and random.random() < 0.025:
                self.tank_slam_cd = 4.0
                return "tank_slam"

        # 远程僵尸：散射连射
        elif self.enemy_type == EnemyType.ZOMBIE_RANGED:
            if dist < 280 and self.ranged_burst_cd <= 0 and random.random() < 0.015:
                self.ranged_burst_cd = 5.0
                # 三连发散射
                results = []
                base_angle = math.atan2(player_y - self.y, player_x - self.x)
                for offset in [-0.2, 0, 0.2]:
                    angle = base_angle + offset
                    results.append({
                        "x": self.x, "y": self.y,
                        "target_x": self.x + math.cos(angle) * 300,
                        "target_y": self.y + math.sin(angle) * 300,
                        "damage": int(self.damage * 0.6)
                    })
                return results

        # 分裂僵尸：死亡时溅射（在take_damage中处理，这里添加分裂前兆）
        elif self.enemy_type == EnemyType.ZOMBIE_SPLITTER:
            if self.hp < self.max_hp * 0.3 and self.special_ability_cd <= 0:
                self.special_ability_cd = 3.0
                # 分裂前兆：加速
                pass

        # 治疗僵尸：治疗波（范围大量治疗）
        elif self.enemy_type == EnemyType.ZOMBIE_HEALER:
            if self.healer_wave_cd <= 0 and random.random() < 0.01:
                self.healer_wave_cd = 8.0
                return "healer_wave"

        # 幻影僵尸：瞬移到玩家附近
        elif self.enemy_type == EnemyType.ZOMBIE_PHANTOM:
            if dist > 200 and self.phantom_teleport_cd <= 0 and random.random() < 0.015:
                self.phantom_teleport_cd = 10.0
                angle = random.uniform(0, math.pi * 2)
                teleport_dist = random.randint(80, 150)
                self.x = player_x + math.cos(angle) * teleport_dist
                self.y = player_y + math.sin(angle) * teleport_dist
                return "phantom_teleport"

        # 盾兵：冲锋盾击
        elif self.enemy_type == EnemyType.ZOMBIE_SHIELD:
            if 100 < dist < 300 and self.shield_charge_cd <= 0 and random.random() < 0.02:
                self.shield_charge_cd = 6.0
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.x += (player_x - self.x) / d * 100
                    self.y += (player_y - self.y) / d * 100
                return "shield_charge"

        # 吐酸僵尸：远程酸液弹（已通过is_ranged处理，这里添加腐蚀溅射）
        elif self.enemy_type == EnemyType.ZOMBIE_SPITTER:
            pass  # 腐蚀效果在命中时由game.py处理

        # 跳跃僵尸：远距离扑击
        elif self.enemy_type == EnemyType.ZOMBIE_LEAPER:
            if 100 < dist < 250 and self.special_ability_cd <= 0 and random.random() < getattr(self, "leap_chance", 0.15):
                self.special_ability_cd = 4.0
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    leap_dist = min(dist, getattr(self, "leap_range", 200))
                    self.x += (player_x - self.x) / d * leap_dist
                    self.y += (player_y - self.y) / d * leap_dist
                return "leaper_strike"

        # 食尸者：吞噬尸体变强（在game.py中检测尸体）
        elif self.enemy_type == EnemyType.ZOMBIE_CORPSE_EATER:
            pass

        # 怨灵：穿墙+恐惧光环
        elif self.enemy_type == EnemyType.ZOMBIE_WRAITH:
            if dist < 100 and self.special_ability_cd <= 0 and random.random() < getattr(self, "fear_chance", 0.2):
                self.special_ability_cd = 6.0
                return "wraith_fear"

        # === 精英怪 ===
        # 精英蛮兵：重击
        elif self.enemy_type == EnemyType.ELITE_BRUTE:
            if dist < 80 and self.special_ability_cd <= 0 and random.random() < getattr(self, "heavy_attack_chance", 0.3):
                self.special_ability_cd = 3.5
                return "elite_heavy_slam"

        # 精英刺客：高速冲刺
        elif self.enemy_type == EnemyType.ELITE_ASSASSIN:
            if 80 < dist < 300 and self.special_ability_cd <= 0 and random.random() < getattr(self, "dash_chance", 0.25):
                self.special_ability_cd = 4.0
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.x += (player_x - self.x) / d * 150
                    self.y += (player_y - self.y) / d * 150
                return "elite_assassin_dash"

        # 精英术士：诅咒弹（已通过is_ranged处理）
        elif self.enemy_type == EnemyType.ELITE_SORCERER:
            pass

        # 精英守卫：治疗光环（在game.py中范围处理）
        elif self.enemy_type == EnemyType.ELITE_GUARDIAN:
            pass

        return None

    def _ranged_attack(self, dt, player_x, player_y, dist):
        if self.attack_timer > 0:
            self.attack_timer -= dt
            return None
        self.attack_timer = getattr(self, "attack_cooldown", 2.0)
        return {
            "x": self.x, "y": self.y,
            "target_x": player_x, "target_y": player_y,
            "damage": self.damage
        }

    def take_damage(self, damage, damage_type="normal"):
        # DOT伤害跳过特殊防御机制
        if damage_type != "dot":
            # 盾兵正面减伤
            if getattr(self, "is_shield", False) and getattr(self, "front_reduction", 0) > 0:
                # 简化：50%几率触发正面减伤
                if random.random() < 0.5:
                    damage *= (1 - self.front_reduction)

            # 爬行者闪避
            if getattr(self, "is_crawler", False) and getattr(self, "dodge_chance", 0) > 0:
                if random.random() < self.dodge_chance:
                    return False  # 闪避了

        # Buff系统受伤倍率（燃烧加深伤害等）
        damage *= self.buff_manager.get_damage_taken_mult()
        self.hp -= damage
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def knockdown(self, duration=2.0):
        self.knockdown_timer = duration

    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, 
                          self.size * 2, self.size * 2)

    def draw(self, screen, camera_x, camera_y, font, scale=1.0):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(2, int(self.size * scale))

        # 幻影僵尸隐身效果
        alpha = 255
        if getattr(self, "is_phantom", False) and self.invisible:
            alpha = 60
            if random.random() < 0.3:  # 偶尔闪烁可见
                alpha = 180

        # 爆炸僵尸倒计时闪烁
        if getattr(self, "is_exploder", False) and self.is_exploding:
            flash = abs(math.sin(pygame.time.get_ticks() / 100))
            if flash > 0.5:
                color = RED
            else:
                color = YELLOW
        else:
            color = self.color

        if self.knockdown_timer > 0:
            pygame.draw.ellipse(screen, DARK_GRAY, 
                              (px - s, py - s // 2, s * 2, s))
        else:
            # 绘制身体
            body_surf = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
            pygame.draw.circle(body_surf, (*color[:3], alpha), (s, s), s)
            screen.blit(body_surf, (px - s, py - s))

            # 眼睛
            if alpha > 100:
                eye_offset = max(2, int(5 * scale))
                pygame.draw.circle(screen, RED, (px - eye_offset, py - max(1, int(3 * scale))), max(1, int(3 * scale)))
                pygame.draw.circle(screen, RED, (px + eye_offset, py - max(1, int(3 * scale))), max(1, int(3 * scale)))

        # 特殊标识
        if getattr(self, "is_exploder", False) and not self.is_exploding:
            # 爆炸标识
            pygame.draw.circle(screen, RUST, (px, py - s - 5), max(2, int(3 * scale)))
        if getattr(self, "is_healer", False):
            # 治疗光环
            heal_pulse = abs(math.sin(pygame.time.get_ticks() / 300)) * 0.5 + 0.5
            heal_surf = pygame.Surface((int(self.heal_radius * 2 * scale), int(self.heal_radius * 2 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(heal_surf, (*GREEN[:3], int(30 * heal_pulse)), 
                             (int(self.heal_radius * scale), int(self.heal_radius * scale)), 
                             int(self.heal_radius * scale))
            screen.blit(heal_surf, (px - int(self.heal_radius * scale), py - int(self.heal_radius * scale)))
        if getattr(self, "is_shield", False):
            # 盾牌标识
            pygame.draw.rect(screen, CHARCOAL, (px - s - 2, py - s - 2, s * 2 + 4, s * 2 + 4), max(1, int(2 * scale)))
        if getattr(self, "is_crawler", False):
            # 爬行者更小
            pass  # 已经在size中体现
        if getattr(self, "is_splitter", False):
            # 分裂标识
            pygame.draw.circle(screen, BLOOD_RED, (px, py + s + 5), max(2, int(3 * scale)))

        if self.hp < self.max_hp:
            bar_width = s * 2
            bar_height = max(2, int(4 * scale))
            hp_ratio = self.hp / self.max_hp
            pygame.draw.rect(screen, RED, (px - bar_width // 2, py - s - max(4, int(8 * scale)), 
                                         bar_width, bar_height))
            pygame.draw.rect(screen, GREEN, (px - bar_width // 2, py - s - max(4, int(8 * scale)), 
                                           int(bar_width * hp_ratio), bar_height))

        if getattr(self, "is_boss", False):
            name_text = font.render(self.name, True, YELLOW)
            name_rect = name_text.get_rect(center=(px, py - s - max(10, int(20 * scale))))
            screen.blit(name_text, name_rect)
        if getattr(self, "is_boss", False) and self.enemy_type == EnemyType.BOSS_LONG and self.boss_hold_shield:
            # 龙某举盾特效
            shield_s = int(35 * scale)
            pygame.draw.circle(screen, BLUE, (px, py), shield_s, max(2,int(3*scale)))
        # =========处决前摇红色闪烁警告【新增】=========
        if getattr(self,"boss_is_executing",False):
            flash = abs(math.sin(pygame.time.get_ticks() / 80))
            r = int(220*flash)
            g = int(30*flash)
            b = int(30*flash)
            pygame.draw.circle(screen,(r,g,b),(px,py),int((s+25)*scale),max(3,int(4*scale)))


class ExpOrb:
    def __init__(self, x, y, value):
        self.x = x
        self.y = y
        self.value = value
        self.size = 6
        self.alive = True
        self.magnetized = False
        self.lifetime = 30.0

    def update(self, dt, player_x, player_y, pickup_range):
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False
            return

        dx = player_x - self.x
        dy = player_y - self.y
        dist = math.hypot(dx, dy)

        if dist < pickup_range:
            self.magnetized = True

        if self.magnetized and dist > 10:
            speed = 8 if dist < pickup_range else 3
            self.x += (dx / dist) * speed * dt * 60
            self.y += (dy / dist) * speed * dt * 60

    def draw(self, screen, camera_x, camera_y, scale=1.0):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(1, int(self.size * scale))
        # 发光效果
        glow_s = s + 3
        glow_surf = pygame.Surface((glow_s * 2, glow_s * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*CYAN[:3], 60), (glow_s, glow_s), glow_s)
        screen.blit(glow_surf, (px - glow_s, py - glow_s))
        pygame.draw.circle(screen, CYAN, (px, py), s)
        pygame.draw.circle(screen, WHITE, (px, py), s, max(1, int(scale)))
