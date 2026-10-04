#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏实体模块 - 玩家、敌人(含新机制僵尸)、经验球、防爆套装等"""

import pygame
import math
import random
from config import *
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
        self.base_max_stamina = 100
        self.stamina_regen = 8
        self.base_stamina_regen = 8
        self.adrenaline_level = 0  # 肾上腺素技能等级，装备时提升体力
        self.bash_cooldown = 0
        self.bash_max_cooldown = 0.5
        self.grapple_cooldown = 0
        self.grapple_max_cooldown = 0.8
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
        self.grapple_speed = 150
        self.grapple_pull_speed = 55
        self.grapple_hit_stun_timer = 0
        self.grapple_hit_stun_duration = 0.6
        self.grapple_max_range = 800
        self.grapple_stamina_cost = 0
        self.bash_auto = False
        self.bash_direction = 0
        self.bash_stamina_cost = 14
        self.bash_anim_timer = 0
        self.bash_anim_duration = 0.2
        self.bash_hit_pos = None
        # === 盾牌冲撞系统 ===
        self.charge_active = False
        self.charge_timer = 0
        self.charge_duration = 0.45
        self.charge_speed = 680
        self.charge_direction = 0
        self.charge_hit_ids = set()  # 已命中的敌人id，避免重复伤害
        self.charge_damage = 160
        self.charge_stun_duration = 1.2
        self.charge_knockback = 150
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
        self.charge_active = False
        self.charge_hit_ids = set()
        self.has_debuff = False
        self.aim_line_active = False
        # 卸下瞬间开启冷却
        self.riot_gear_cd_timer = self.riot_gear_base_cd * cd_reduction_mult

    def update(self, dt, player_x, player_y, facing_angle, move_speed_mult=1.0, cd_reduction_mult=1.0):
        self.facing_angle = facing_angle
        # 冷却计时
        if self.riot_gear_cd_timer > 0:
            self.riot_gear_cd_timer -= dt

        # 体力由Player统一管理（与玩家疾跑共用同一体力池）
        # self.stamina 和 self.max_stamina 由 Player.update 同步
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
        """更新钩爪状态 - 修复秒断勾：追踪目标、稳定拉回、最小拉回时间"""
        if not self.grapple_active:
            return

        if self.grapple_state == "shooting":
            # 如果有目标，追踪目标当前位置（而非固定的发射位置）
            if self.grapple_target and hasattr(self.grapple_target, 'alive') and self.grapple_target.alive:
                self.grapple_target_pos = (self.grapple_target.x, self.grapple_target.y)

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

            if new_dist < 10:  # 到达目标位置（放宽阈值，避免速度快时越过）
                if self.grapple_target:
                    # Boss免控：只能命中产生僵直，不能勾取
                    if getattr(self.grapple_target, 'is_boss', False):
                        self.grapple_hit_stun_timer = self.grapple_hit_stun_duration * 0.5
                        if hasattr(self.grapple_target, 'grappled'):
                            self.grapple_target.grappled = False
                        self.grapple_target = None
                        self.grapple_state = "retracting"
                    else:
                        # 勾中普通目标，立即设置grappled=True防止敌人移动
                        if hasattr(self.grapple_target, 'grappled'):
                            self.grapple_target.grappled = True
                        self.grapple_head_pos = [self.grapple_target.x, self.grapple_target.y]
                        self.grapple_state = "hit"
                        self.grapple_hit_stun_timer = self.grapple_hit_stun_duration
                        self._pulling_timer = 0.0  # 初始化拉回计时器
                else:
                    self.grapple_state = "retracting"
            elif total_dist >= self.grapple_max_range:
                self.grapple_state = "retracting"

        elif self.grapple_state == "hit":
            # 僵直阶段 - 钩爪绷紧
            self.grapple_hit_stun_timer -= dt
            if self.grapple_hit_stun_timer <= 0:
                self.grapple_state = "pulling"
                self._pulling_timer = 0.0
            # 同步更新目标位置到钩爪头
            if self.grapple_target and hasattr(self.grapple_target, 'alive') and self.grapple_target.alive:
                self.grapple_head_pos = [self.grapple_target.x, self.grapple_target.y]
                # 确保目标保持被勾状态
                if hasattr(self.grapple_target, 'grappled'):
                    self.grapple_target.grappled = True
            else:
                # 目标死亡，收回钩爪
                self.grapple_state = "retracting"

        elif self.grapple_state == "pulling":
            if not hasattr(self, '_pulling_timer'):
                self._pulling_timer = 0.0
            self._pulling_timer += dt

            if self.grapple_target and hasattr(self.grapple_target, 'alive') and self.grapple_target.alive:
                dx = player_x - self.grapple_target.x
                dy = player_y - self.grapple_target.y
                dist = math.hypot(dx, dy)

                # 最小拉回时间0.2秒，确保不会秒断
                min_pull_time = 0.2
                if dist > 90 or self._pulling_timer < min_pull_time:
                    pull_speed = self.grapple_pull_speed * dt * 60
                    # 距离越远拉得越快（倍率1.5而非2.0，更稳定）
                    if dist > 200:
                        pull_speed *= 1.5
                    if dist > 0:
                        self.grapple_target.x += (dx / dist) * pull_speed
                        self.grapple_target.y += (dy / dist) * pull_speed
                    self.grapple_head_pos = [self.grapple_target.x, self.grapple_target.y]
                    # 确保敌人保持被勾状态
                    if hasattr(self.grapple_target, 'grappled'):
                        self.grapple_target.grappled = True
                else:
                    # 到达玩家90像素外且超过最小拉回时间，释放
                    if hasattr(self.grapple_target, 'grappled'):
                        self.grapple_target.grappled = False
                    # 拉回完成：给予长僵直，使目标短时间内无法移动/攻击玩家
                    try:
                        if hasattr(self.grapple_target, 'apply_buff'):
                            self.grapple_target.apply_buff(BuffType.STUN, duration=1.5)
                        if hasattr(self.grapple_target, 'knockdown'):
                            self.grapple_target.knockdown(1.0)
                    except Exception:
                        pass
                    # 释放时给敌人一个短暂的击退，让它停在玩家面前
                    if hasattr(self.grapple_target, 'knockback_x'):
                        kb_dir_x = (self.grapple_target.x - player_x) / max(1, dist)
                        kb_dir_y = (self.grapple_target.y - player_y) / max(1, dist)
                        self.grapple_target.knockback_x = kb_dir_x * 50
                        self.grapple_target.knockback_y = kb_dir_y * 50
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
                if dist > 0:
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
        return self.equipped and self.bash_cooldown <= 0 and self.stamina >= self.bash_stamina_cost and not self.charge_active

    def bash(self, direction_angle=None, is_sprint=False):
        """盾牌冲撞：启动冲撞状态，由game.py处理移动和伤害"""
        if not self.can_bash():
            return False
        self.stamina -= self.bash_stamina_cost
        self.bash_cooldown = self.bash_max_cooldown
        if direction_angle is not None:
            self.charge_direction = direction_angle
        else:
            self.charge_direction = self.facing_angle
        self.charge_active = True
        self.charge_timer = self.charge_duration
        self.charge_hit_ids = set()
        self.bash_anim_timer = self.bash_anim_duration
        return True

    def can_grapple(self):
        # 钩爪为独立技能，无需装备防爆套装
        return self.grapple_cooldown <= 0

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
        px = int((player_x - camera_x) * scale)
        py = int((player_y - camera_y) * scale)

        # 钩爪始终绘制（独立技能，无需防爆套装）
        if self.grapple_active and self.grapple_head_pos:
            hx = int((self.grapple_head_pos[0] - camera_x) * scale)
            hy = int((self.grapple_head_pos[1] - camera_y) * scale)
            # 绳索
            pygame.draw.line(screen, (80, 80, 80), (px, py), (hx, hy), max(2, int(3 * scale)))
            pygame.draw.line(screen, (160, 160, 160), (px, py), (hx, hy), max(1, int(1 * scale)))
            # 钩爪头
            head_size = max(4, int(8 * scale))
            pygame.draw.circle(screen, (60, 60, 60), (hx, hy), head_size)
            pygame.draw.circle(screen, (180, 180, 180), (hx, hy), head_size - 2)
            # 钩子三叉
            hook_len = int(6 * scale)
            for ha in (-0.5, 0, 0.5):
                angle = math.atan2(hy - py, hx - px) + ha
                ex = hx + math.cos(angle) * hook_len
                ey = hy + math.sin(angle) * hook_len
                pygame.draw.line(screen, (200, 200, 200), (hx, hy), (ex, ey), max(1, int(2 * scale)))
            # 命中僵直火花
            if self.grapple_state == "hit":
                for _ in range(6):
                    sx = hx + random.randint(-10, 10)
                    sy = hy + random.randint(-10, 10)
                    pygame.draw.circle(screen, YELLOW, (sx, sy), max(1, int(2 * scale)))
            # 拉回火花
            if self.grapple_state == "pulling":
                for _ in range(4):
                    sx = hx + random.randint(-6, 6)
                    sy = hy + random.randint(-6, 6)
                    pygame.draw.circle(screen, ORANGE, (sx, sy), max(1, int(2 * scale)))

        if not self.equipped:
            return

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
