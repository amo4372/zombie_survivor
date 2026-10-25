#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI组件模块 - 完整重写版：技能卡选择、触控按钮位置调整、半透明范围圈"""

import pygame
import math
import random
import os
import time
from config import *
from .fx import draw_dashed_line
from .scroll import ScrollablePanel


class SkillSelector:
    """技能切换按钮 - 短按切换下一个技能，长按显示技能轮盘"""
    def __init__(self, x, y, radius=55):
        self.base_x = x
        self.base_y = y
        self.base_radius = radius
        self.visible = True
        self.touch_id = None
        self.pressed = False
        self.just_released = False
        self.press_start_time = 0
        self.long_press_threshold = 0.4
        self.is_long_press = False
        self.wheel_active = False
        self.should_open_wheel = False  # 新增：标记应该打开轮盘

    def get_scaled_pos(self, scale=1.0):
        return (self.base_x * scale, self.base_y * scale, self.base_radius * scale)

    def handle_touch(self, touch_events, scale=1.0):
        bx, by, r = self.get_scaled_pos(scale)
        bx, by, r = int(bx), int(by), int(r)
        self.just_released = False
        self.is_long_press = False
        # 关键修复：不要每帧重置should_open_wheel，只在up事件后重置
        # 这样game.py可以在多帧中检测到轮盘应该打开
        had_wheel_active = self.wheel_active

        for event in touch_events:
            pos = event["pos"]
            dist = math.hypot(pos[0] - bx, pos[1] - by)
            if event["type"] == "down":
                if dist < r and not self.pressed:
                    self.pressed = True
                    self.touch_id = event.get("id", 0)
                    self.press_start_time = time.time()
                    self.wheel_active = False
                    self.should_open_wheel = False
            elif event["type"] == "move" and self.pressed:
                if event.get("id", 0) == self.touch_id:
                    if not self.wheel_active and time.time() - self.press_start_time >= self.long_press_threshold:
                        self.wheel_active = True
                        self.is_long_press = True
                        self.should_open_wheel = True
            elif event["type"] == "up":
                if event.get("id", 0) == self.touch_id:
                    press_duration = time.time() - self.press_start_time
                    if self.pressed and not self.wheel_active:
                        self.just_released = True
                    self.pressed = False
                    # 如果轮盘已经激活，保持should_open_wheel为True直到外部处理
                    if had_wheel_active or self.wheel_active:
                        self.should_open_wheel = True
                    self.wheel_active = False
                    self.touch_id = None
        return self.just_released

    def is_showing_wheel(self):
        return self.should_open_wheel

    def draw(self, screen, font, skill_name="技", skill_color=BLUE, scale=1.0):
        if not self.visible:
            return
        bx, by, r = self.get_scaled_pos(scale)
        bx, by, r = int(bx), int(by), int(r)

        # 长按状态显示不同颜色
        if self.wheel_active:
            color = GOLD
            outer_r = int(r * 1.3)
            pygame.draw.circle(screen, (*GOLD[:3], 100), (bx, by), outer_r)
        else:
            color = tuple(min(255, c + 40) for c in skill_color) if self.pressed else skill_color

        pygame.draw.circle(screen, DARK_GRAY, (bx, by), int(r * 1.15))
        pygame.draw.circle(screen, WHITE, (bx, by), int(r * 1.15), 2)
        pygame.draw.circle(screen, color, (bx, by), r)
        pygame.draw.circle(screen, WHITE, (bx, by), r, 2)
        text = font.render(skill_name, True, WHITE)
        text_rect = text.get_rect(center=(bx, by))
        screen.blit(text, text_rect)
        label = font.render("技能", True, GRAY)
        screen.blit(label, (bx - label.get_width() // 2, by - r - label.get_height() - 2))


class SkillCaster:
    """技能释放按钮 - 支持长按瞄准+拖拽改变方向和距离"""
    def __init__(self, x, y, radius=55):
        self.base_x = x
        self.base_y = y
        self.base_radius = radius
        self.visible = True
        self.touch_id = None
        self.pressed = False
        self.just_released = False
        self.is_aiming = False
        self.was_aiming_on_release = False
        self.press_start_time = 0
        self.aim_threshold = 0.3
        self.angle = 0
        self.distance_ratio = 1.0  # 拖拽距离比例 (0.1 ~ 1.0)
        self.knob_offset_x = 0
        self.knob_offset_y = 0
        self.player_x = 0
        self.player_y = 0
        self.camera_x = 0
        self.camera_y = 0
        self.cooldown = 0
        self.max_cooldown = 0
        self.reload_progress = 0
        self.is_reloading = False
        self.max_skill_distance = 500  # 默认最大技能距离

    def get_scaled_pos(self, scale=1.0):
        return (self.base_x * scale, self.base_y * scale, self.base_radius * scale)

    def set_player_pos(self, px, py, cx, cy):
        self.player_x = px
        self.player_y = py
        self.camera_x = cx
        self.camera_y = cy

    def set_cooldown(self, seconds):
        self.cooldown = seconds
        self.max_cooldown = seconds

    def set_max_distance(self, distance):
        self.max_skill_distance = distance

    def set_aim_angle(self, angle):
        self.angle = angle

    def set_distance_ratio(self, ratio):
        self.distance_ratio = max(0.1, min(1.0, ratio))

    def handle_touch(self, touch_events, scale=1.0):
        bx, by, r = self.get_scaled_pos(scale)
        bx, by, r = int(bx), int(by), int(r)
        self.just_released = False
        self.was_aiming_on_release = False
        for event in touch_events:
            pos = event["pos"]
            dist = math.hypot(pos[0] - bx, pos[1] - by)
            if event["type"] == "down":
                if dist < r * 1.5 and not self.pressed:
                    self.pressed = True
                    self.touch_id = event.get("id", 0)
                    self.press_start_time = time.time()
                    self.is_aiming = False
                    self.distance_ratio = 1.0
                    self._update_aim(pos[0], pos[1], bx, by, scale)
            elif event["type"] == "move" and self.pressed:
                if event.get("id", 0) == self.touch_id:
                    self._update_aim(pos[0], pos[1], bx, by, scale)
            elif event["type"] == "up":
                if event.get("id", 0) == self.touch_id:
                    if self.pressed:
                        self.just_released = True
                        self.was_aiming_on_release = self.is_aiming
                    self.pressed = False
                    self.touch_id = None
                    self.knob_offset_x = 0
                    self.knob_offset_y = 0
                    # 保持最后的angle和distance_ratio供读取
                    self.is_aiming = False
        # 每帧检测长按阈值（即使没有move事件）
        if self.pressed and not self.is_aiming and time.time() - self.press_start_time >= self.aim_threshold:
            self.is_aiming = True
        return self.just_released

    def _update_aim(self, tx, ty, bx, by, scale):
        dx = tx - bx
        dy = ty - by
        dist = math.hypot(dx, dy)
        r = self.base_radius
        if dist > 0:
            self.angle = math.atan2(dy, dx)
            # 计算距离比例：拖拽越远，距离比例越大
            max_drag = r * 2.5
            self.distance_ratio = min(1.0, max(0.1, dist / max_drag))
            if dist > r:
                ratio = r / dist
                self.knob_offset_x = dx * ratio
                self.knob_offset_y = dy * ratio
            else:
                self.knob_offset_x = dx
                self.knob_offset_y = dy

    def get_target_pos(self):
        """获取技能目标位置（基于方向和距离比例）"""
        dist = self.max_skill_distance * self.distance_ratio
        target_x = self.player_x + math.cos(self.angle) * dist
        target_y = self.player_y + math.sin(self.angle) * dist
        return target_x, target_y

    def draw(self, screen, font, skill_type=None, skill_name="放", skill_color=ORANGE, scale=1.0):
        if not self.visible:
            return
        bx, by, r = self.get_scaled_pos(scale)
        bx, by, r = int(bx), int(by), int(r)
        kx = int(bx + self.knob_offset_x * scale)
        ky = int(by + self.knob_offset_y * scale)

        # 绘制CD遮罩 - 纯黑色遮罩覆盖整个按钮
        if self.cooldown > 0 and self.max_cooldown > 0:
            ratio = self.cooldown / self.max_cooldown
            # 全圆黑色遮罩（不透明度随CD减少）
            mask_alpha = max(0, min(255, int(200 * ratio + 30)))
            mask_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(mask_surf, (0, 0, 0, mask_alpha), (r, r), r)
            screen.blit(mask_surf, (bx - r, by - r))

            # 红色外圈进度环
            start_angle = -math.pi / 2
            end_angle = start_angle + ratio * 2 * math.pi
            pygame.draw.arc(screen, RED, (bx - r - 3, by - r - 3, (r+3)*2, (r+3)*2), 
                          start_angle, end_angle, max(2, int(4*scale)))

            # 黑色内圈进度环
            pygame.draw.arc(screen, (30, 30, 30), (bx - r + 2, by - r + 2, (r-2)*2, (r-2)*2), 
                          start_angle, end_angle, max(1, int(2*scale)))

        if self.is_aiming and skill_type:
            self._draw_aim_preview(screen, skill_type, scale)

        color = tuple(min(255, c + 40) for c in skill_color) if self.pressed else skill_color
        pygame.draw.circle(screen, color, (bx, by), r)
        pygame.draw.circle(screen, WHITE, (bx, by), r, 2)
        if self.pressed:
            line_end_x = bx + math.cos(self.angle) * r
            line_end_y = by + math.sin(self.angle) * r
            pygame.draw.line(screen, WHITE, (bx, by), (line_end_x, line_end_y), 2)
            pygame.draw.circle(screen, WHITE, (kx, ky), r // 3)
        text = font.render(skill_name, True, WHITE)
        text_rect = text.get_rect(center=(bx, by))
        screen.blit(text, text_rect)

        # CD文字 - 更大更显眼
        if self.cooldown > 0:
            cd_text = font.render(f"{self.cooldown:.1f}", True, WHITE)
            cd_rect = cd_text.get_rect(center=(bx, by))
            # CD文字背景
            cd_bg = pygame.Surface((cd_rect.width + 8, cd_rect.height + 4), pygame.SRCALPHA)
            cd_bg.fill((0, 0, 0, 150))
            screen.blit(cd_bg, (cd_rect.x - 4, cd_rect.y - 2))
            screen.blit(cd_text, cd_rect)

    def _draw_aim_preview(self, screen, skill_type, scale):
        px = int((self.player_x - self.camera_x) * scale)
        py = int((self.player_y - self.camera_y) * scale)

        # 使用distance_ratio计算实际距离
        dist = self.max_skill_distance * self.distance_ratio
        target_x = px + math.cos(self.angle) * dist * scale
        target_y = py + math.sin(self.angle) * dist * scale

        if skill_type == SkillType.GRENADE:
            points = []
            for t in range(0, 21):
                ratio = t / 20.0
                arc_x = px + (target_x - px) * ratio
                arc_y = py + (target_y - py) * ratio - math.sin(ratio * math.pi) * 60 * scale
                points.append((arc_x, arc_y))
            if len(points) >= 2:
                pygame.draw.lines(screen, ORANGE, False, points, max(1, int(2 * scale)))
            range_surf = pygame.Surface((int(300 * scale), int(300 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*ORANGE[:3], 40), (int(150 * scale), int(150 * scale)), int(150 * scale))
            screen.blit(range_surf, (int(target_x - 150 * scale), int(target_y - 150 * scale)))
            pygame.draw.circle(screen, ORANGE, (int(target_x), int(target_y)), int(150 * scale), max(1, int(2 * scale)))
            # 距离指示
            dist_text = f"{int(dist)}m"
            dt_surf = pygame.font.SysFont("arial", 12).render(dist_text, True, ORANGE)
            screen.blit(dt_surf, (int(target_x) + 10, int(target_y) - 20))
        elif skill_type == SkillType.AIRSTRIKE:
            draw_dashed_line(screen, RED, (px, py), (target_x, target_y),
                           dash_length=15 * scale, gap_length=8 * scale, width=max(1, int(3 * scale)))
            range_surf = pygame.Surface((int(400 * scale), int(400 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*RED[:3], 40), (int(200 * scale), int(200 * scale)), int(200 * scale))
            screen.blit(range_surf, (int(target_x - 200 * scale), int(target_y - 200 * scale)))
            pygame.draw.circle(screen, RED, (int(target_x), int(target_y)), int(200 * scale), max(1, int(3 * scale)))
            cs = int(15 * scale)
            pygame.draw.line(screen, RED, (int(target_x) - cs, int(target_y)), (int(target_x) + cs, int(target_y)), 2)
            pygame.draw.line(screen, RED, (int(target_x), int(target_y) - cs), (int(target_x), int(target_y) + cs), 2)
            dist_text = f"{int(dist)}m"
            dt_surf = pygame.font.SysFont("arial", 12).render(dist_text, True, RED)
            screen.blit(dt_surf, (int(target_x) + 10, int(target_y) - 20))
        elif skill_type == SkillType.DASH:
            end_x = px + math.cos(self.angle) * dist * scale
            end_y = py + math.sin(self.angle) * dist * scale
            draw_dashed_line(screen, CYAN, (px, py), (end_x, end_y),
                           dash_length=10 * scale, gap_length=5 * scale, width=max(1, int(3 * scale)))
            pygame.draw.circle(screen, (*CYAN[:3], 80), (int(end_x), int(end_y)), int(15 * scale))
            pygame.draw.circle(screen, CYAN, (int(end_x), int(end_y)), int(15 * scale), max(1, int(2 * scale)))
        elif skill_type == SkillType.GRAPPLE_PULL:
            end_x = px + math.cos(self.angle) * dist * scale
            end_y = py + math.sin(self.angle) * dist * scale
            draw_dashed_line(screen, GREEN, (px, py), (end_x, end_y),
                           dash_length=15 * scale, gap_length=8 * scale, width=max(1, int(2 * scale)))
            pygame.draw.circle(screen, GREEN, (int(end_x), int(end_y)), int(8 * scale), max(1, int(2 * scale)))
            pygame.draw.circle(screen, (*GREEN[:3], 80), (int(end_x), int(end_y)), int(8 * scale))
        elif skill_type == SkillType.FEARLESS_CHARGE:
            # v2.7.0 无畏冲锋预瞄：沿面朝方向的冲锋轨迹箭头
            _ch_len = dist * scale
            _a = self.angle
            _ex = px + math.cos(_a) * _ch_len
            _ey = py + math.sin(_a) * _ch_len
            _col = (255, 130, 60)
            pygame.draw.line(screen, _col, (px, py), (int(_ex), int(_ey)), max(2, int(5 * scale)))
            for _s in (0.45, 0.7, 0.95):
                _sx = px + math.cos(_a) * _ch_len * _s
                _sy = py + math.sin(_a) * _ch_len * _s
                pygame.draw.circle(screen, (*_col[:3], 120), (int(_sx), int(_sy)), max(3, int(9 * scale)))
            _hx = _ex - math.cos(_a) * 16 * scale
            _hy = _ey - math.sin(_a) * 16 * scale
            _pa = _a + 2.5
            _pb = _a - 2.5
            pygame.draw.line(screen, WHITE, (int(_ex), int(_ey)),
                             (int(_hx + math.cos(_pa) * 16 * scale), int(_hy + math.sin(_pa) * 16 * scale)),
                             max(1, int(3 * scale)))
            pygame.draw.line(screen, WHITE, (int(_ex), int(_ey)),
                             (int(_hx + math.cos(_pb) * 16 * scale), int(_hy + math.sin(_pb) * 16 * scale)),
                             max(1, int(3 * scale)))
            bash_range = dist * scale
            arc_angle = 60
            start_angle = math.degrees(self.angle) - arc_angle / 2
            end_angle = math.degrees(self.angle) + arc_angle / 2
            for offset in [-30, 0, 30]:
                rad = math.radians(math.degrees(self.angle) + offset)
                ex = px + math.cos(rad) * bash_range
                ey = py + math.sin(rad) * bash_range
                pygame.draw.line(screen, CYAN, (px, py), (ex, ey), max(1, int(2 * scale)))
            arc_surf = pygame.Surface((int(bash_range * 2), int(bash_range * 2)), pygame.SRCALPHA)
            pygame.draw.arc(arc_surf, (*CYAN[:3], 60),
                          pygame.Rect(0, 0, bash_range * 2, bash_range * 2),
                          math.radians(start_angle), math.radians(end_angle), max(1, int(2 * scale)))
            screen.blit(arc_surf, (px - bash_range, py - bash_range))
        elif skill_type == SkillType.RIOT_GEAR:
            pygame.draw.circle(screen, (*BLUE[:3], 80), (px, py), int(40 * scale))
            pygame.draw.circle(screen, BLUE, (px, py), int(40 * scale), max(1, int(2 * scale)))
        elif skill_type == SkillType.BLINK:
            # 闪烁技能 - 支持拖拽改变方向和距离
            end_x = px + math.cos(self.angle) * dist * scale
            end_y = py + math.sin(self.angle) * dist * scale
            draw_dashed_line(screen, CYAN, (px, py), (end_x, end_y),
                           dash_length=8 * scale, gap_length=4 * scale, width=max(1, int(2 * scale)))
            pygame.draw.circle(screen, (*CYAN[:3], 100), (int(end_x), int(end_y)), int(20 * scale))
            pygame.draw.circle(screen, CYAN, (int(end_x), int(end_y)), int(20 * scale), max(1, int(2 * scale)))
            # 传送点标记
            pygame.draw.circle(screen, WHITE, (int(end_x), int(end_y)), int(5 * scale))
            dist_text = f"{int(dist)}m"
            dt_surf = pygame.font.SysFont("arial", 12).render(dist_text, True, CYAN)
            screen.blit(dt_surf, (int(end_x) + 10, int(end_y) - 20))
        elif skill_type == SkillType.BLACK_HOLE:
            draw_dashed_line(screen, PURPLE, (px, py), (target_x, target_y),
                           dash_length=15 * scale, gap_length=8 * scale, width=max(1, int(2 * scale)))
            range_surf = pygame.Surface((int(300 * scale), int(300 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*PURPLE[:3], 50), (int(150 * scale), int(150 * scale)), int(150 * scale))
            screen.blit(range_surf, (int(target_x - 150 * scale), int(target_y - 150 * scale)))
            pygame.draw.circle(screen, PURPLE, (int(target_x), int(target_y)), int(150 * scale), max(1, int(2 * scale)))
            for i in range(3):
                swirl_r = int((50 + i * 30) * scale)
                pygame.draw.arc(screen, PURPLE, 
                              (int(target_x - swirl_r), int(target_y - swirl_r), swirl_r * 2, swirl_r * 2),
                              0, math.pi * 1.5, max(1, int(2 * scale)))
        elif skill_type == SkillType.ICE_NOVA:
            range_surf = pygame.Surface((int(400 * scale), int(400 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*BLUE[:3], 50), (int(200 * scale), int(200 * scale)), int(200 * scale))
            screen.blit(range_surf, (px - int(200 * scale), py - int(200 * scale)))
            pygame.draw.circle(screen, BLUE, (px, py), int(200 * scale), max(1, int(2 * scale)))
            for i in range(8):
                rad = math.radians(i * 45)
                ex = px + math.cos(rad) * 200 * scale
                ey = py + math.sin(rad) * 200 * scale
                pygame.draw.line(screen, (*BLUE[:3], 100), (px, py), (ex, ey), max(1, int(1 * scale)))
        elif skill_type == SkillType.CHAIN_LIGHTNING:
            end_x = px + math.cos(self.angle) * dist * scale
            end_y = py + math.sin(self.angle) * dist * scale
            draw_dashed_line(screen, YELLOW, (px, py), (end_x, end_y),
                           dash_length=10 * scale, gap_length=5 * scale, width=max(1, int(3 * scale)))
            pygame.draw.circle(screen, YELLOW, (int(end_x), int(end_y)), int(10 * scale))
        elif skill_type == SkillType.BERSERK:
            range_surf = pygame.Surface((int(200 * scale), int(200 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*RED[:3], 60), (int(100 * scale), int(100 * scale)), int(100 * scale))
            screen.blit(range_surf, (px - int(100 * scale), py - int(100 * scale)))
            pygame.draw.circle(screen, RED, (px, py), int(100 * scale), max(1, int(2 * scale)))
        elif skill_type == SkillType.PHANTOM_STRIKE:
            for offset in [0, 120, 240]:
                rad = math.radians(math.degrees(self.angle) + offset)
                ex = px + math.cos(rad) * 100 * scale
                ey = py + math.sin(rad) * 100 * scale
                pygame.draw.circle(screen, (*LIME[:3], 80), (int(ex), int(ey)), int(15 * scale))
                pygame.draw.circle(screen, LIME, (int(ex), int(ey)), int(15 * scale), max(1, int(2 * scale)))
        elif skill_type == SkillType.MEDIC_POD:
            draw_dashed_line(screen, GREEN, (px, py), (target_x, target_y),
                           dash_length=10 * scale, gap_length=5 * scale, width=max(1, int(2 * scale)))
            range_surf = pygame.Surface((int(200 * scale), int(200 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*GREEN[:3], 50), (int(100 * scale), int(100 * scale)), int(100 * scale))
            screen.blit(range_surf, (int(target_x - 100 * scale), int(target_y - 100 * scale)))
            pygame.draw.circle(screen, GREEN, (int(target_x), int(target_y)), int(100 * scale), max(1, int(2 * scale)))
            cs = int(10 * scale)
            pygame.draw.line(screen, GREEN, (int(target_x) - cs, int(target_y)), (int(target_x) + cs, int(target_y)), 2)
            pygame.draw.line(screen, GREEN, (int(target_x), int(target_y) - cs), (int(target_x), int(target_y) + cs), 2)
        elif skill_type == SkillType.FEARLESS_CHARGE:
            # v2.7.0 无畏冲锋：沿面朝方向的冲锋轨迹
            _col = (255, 130, 60)
            _ex = px + math.cos(self.angle) * dist * scale
            _ey = py + math.sin(self.angle) * dist * scale
            pygame.draw.line(screen, _col, (px, py), (int(_ex), int(_ey)), max(2, int(4 * scale)))
            pygame.draw.circle(screen, _col, (int(_ex), int(_ey)), max(3, int(10 * scale)), max(1, int(2 * scale)))
            for i in range(12):
                rad = math.radians(i * 30)
                sx = px + math.cos(rad) * 100 * scale
                sy = py + math.sin(rad) * 100 * scale
                ex = px + math.cos(rad) * 150 * scale
                ey = py + math.sin(rad) * 150 * scale
                pygame.draw.line(screen, ORANGE, (int(sx), int(sy)), (int(ex), int(ey)), max(1, int(2 * scale)))
        elif skill_type == SkillType.SCYTHE_DANCE:
            # v2.5.7：死亡轮回长按预瞄圈（此前完全缺失 → 长按没有任何提示）
            # 自身周围 AoE 半径（等级 1~5 = 300~400，按最大射程显示）
            _sr = int(self.max_skill_distance * scale)
            if _sr < 8:
                _sr = int(340 * scale)
            _surf = pygame.Surface((_sr * 2, _sr * 2), pygame.SRCALPHA)
            pygame.draw.circle(_surf, (*LIME[:3], 45), (_sr, _sr), _sr)
            screen.blit(_surf, (int(px - _sr), int(py - _sr)))
            pygame.draw.circle(screen, LIME, (int(px), int(py)), _sr, max(1, int(2 * scale)))
            for i in range(4):
                _rad = math.radians(math.degrees(self.angle) + i * 90)
                _ex = px + math.cos(_rad) * _sr
                _ey = py + math.sin(_rad) * _sr
                pygame.draw.line(screen, (*LIME[:3], 110), (int(px), int(py)),
                                 (int(_ex), int(_ey)), max(1, int(1 * scale)))
            _tt = pygame.font.SysFont("arial", 12).render("死亡轮回", True, LIME)
            screen.blit(_tt, (int(px) + 6, int(py) - _sr - _tt.get_height()))
        elif skill_type == SkillType.RAILGUN_ANNIHILATION:
            # v2.5.7：湮灭射线预瞄线（方向即释放方向——此前释放恒定朝向前方）
            _ex = px + math.cos(self.angle) * dist * scale
            _ey = py + math.sin(self.angle) * dist * scale
            pygame.draw.line(screen, (140, 200, 245), (int(px), int(py)), (int(_ex), int(_ey)),
                             max(3, int(12 * scale)))
            pygame.draw.line(screen, (225, 245, 255), (int(px), int(py)), (int(_ex), int(_ey)),
                             max(1, int(3 * scale)))
            pygame.draw.circle(screen, (140, 200, 245), (int(_ex), int(_ey)), int(12 * scale),
                               max(1, int(2 * scale)))
            _tt2 = pygame.font.SysFont("arial", 12).render("湮灭射线", True, (170, 220, 255))
            screen.blit(_tt2, (int(_ex) + 10, int(_ey) - 20))


class SkillCardSelector:
    """v2.7.0 全新技能卡界面（全模式通用）

    布局自上而下：
      ① 顶部细栏目：三个技能「代表缩略图」选项，点击切换
      ② 中部大页面：当前选中技能详情（效果 / 词条 / 前后对比 / 背景介绍），
         内容超出时使用可滑动文字框（滚轮 / 拖拽 / 触控滑动）
      ③ 底部升级按钮：点击后应用当前选中的技能升级

    默认打开第一个选项；键控 1/2/3 切换、回车（或空格）确认，触控/鼠标点击同样支持。
    """
    def __init__(self):
        self.visible = False
        self.cards = []
        self.selected_index = 0      # 默认打开第一个选项
        self.tab_rects = []
        self.detail_rect = None
        self.confirm_rect = None
        self.animation_timer = 0
        self.animation_duration = 0.3
        self.region = None           # pygame.Rect 或 None（None=全屏）
        self.title = "选择一项技能"
        self.subtitle = "升级！选择你的强化"
        # 滑动文字框状态
        self.scroll_y = 0
        self.max_scroll = 0
        self._panel = None
        self._content_sig = None
        self._dragging = False
        self._drag_id = None
        self._drag_start_y = 0
        self._drag_start_scroll = 0

    # ---------------- 显示 / 隐藏 ----------------
    def show(self, skills, region=None, title="选择一项技能", subtitle="升级！选择你的强化"):
        self.visible = True
        self.cards = list(skills) if skills else []
        self.selected_index = 0      # 默认打开第一个选项
        self.animation_timer = 0
        self.region = region
        self.title = title
        self.subtitle = subtitle
        # 重置布局与滑动状态，避免上一张卡残留
        self.tab_rects = []
        self.detail_rect = None
        self.confirm_rect = None
        self.scroll_y = 0
        self.max_scroll = 0
        self._panel = None
        self._content_sig = None
        self._dragging = False
        self._drag_id = None

    def hide(self):
        self.visible = False
        self.cards = []
        self.selected_index = 0
        self.region = None
        self._panel = None
        self._dragging = False

    def _get_region(self):
        if self.region is not None:
            return self.region
        surf = pygame.display.get_surface()
        return pygame.Rect(0, 0, surf.get_width(), surf.get_height())

    # ---------------- 布局 ----------------
    def _layout(self, scale=1.0):
        region = self._get_region()
        sw, sh = region.width, region.height
        rx, ry = region.x, region.y
        pad = max(8, int(14 * scale))
        title_h = int(92 * scale)
        # 顶部栏目（较细）
        tab_h = int(72 * scale) if sh > 430 else int(60 * scale)
        tab_gap = max(6, int(10 * scale))
        n = max(1, len(self.cards))
        tab_total = max(60, sw - pad * 2)
        tab_w = int((tab_total - tab_gap * (n - 1)) / n)
        tab_y = ry + title_h
        # 底部升级按钮
        btn_h = int(54 * scale)
        btn_w = min(int(380 * scale), max(120, sw - pad * 2))
        # 中部大页面
        detail_y = tab_y + tab_h + int(10 * scale)
        detail_h = sh - title_h - tab_h - btn_h - int(40 * scale)
        detail_h = max(int(110 * scale), detail_h)
        # 大页面底部不越过按钮
        max_detail_h = sh - detail_y - btn_h - int(26 * scale)
        if max_detail_h > 40:
            detail_h = min(detail_h, max_detail_h)
        detail_rect = pygame.Rect(rx + pad, detail_y, sw - pad * 2, int(detail_h))
        btn_rect = pygame.Rect(rx + (sw - btn_w) // 2,
                               int(detail_y + detail_h + int(12 * scale)),
                               int(btn_w), int(btn_h))
        tab_rects = [pygame.Rect(rx + pad + i * (tab_w + tab_gap), tab_y, tab_w, tab_h)
                     for i in range(n)]
        return {"region": region, "tab_rects": tab_rects,
                "detail": detail_rect, "confirm": btn_rect}

    # ---------------- 详情内容 ----------------
    def _build_content(self, skill):
        """生成详情行：[(text, color, indent, is_header)]"""
        lines = []
        lv = skill.current_level
        lines.append((f"{skill.name}", GOLD, 0, True))
        kind = "【主动技能】" if skill.is_active else "【被动技能】"
        lines.append((f"{kind}    等级 Lv.{lv} / {skill.max_level}",
                      CYAN if skill.is_active else GREEN, 0, False))
        lines.append(("", GRAY, 0, False))
        # 效果
        lines.append(("【效果】", GOLD, 0, True))
        eff = ""
        try:
            eff = skill.get_next_level_desc() or ""
        except Exception:
            eff = ""
        if not eff:
            eff = skill.description or ""
        lines.append((eff, LIGHT_GRAY, 0, False))
        if lv == 0:
            lines.append(("（新技能：本次升级后解锁）", GOLD, 0, False))
        if skill.max_level_bonus:
            lines.append((f"满级奖励：{skill.max_level_bonus}", ORANGE, 0, False))
        lines.append(("", GRAY, 0, False))
        # 词条
        try:
            lds = dict(skill.level_descriptions or {})
        except Exception:
            lds = {}
        if lds:
            lines.append(("【词条】", GOLD, 0, True))
            for k in sorted(lds.keys()):
                txt = lds[k]
                if k == lv + 1:
                    lines.append((f"▶ Lv.{k}（本次升级）{txt}", GREEN, 0, False))
                elif k <= lv:
                    lines.append((f"· Lv.{k} {txt}", GRAY, 0, False))
                else:
                    lines.append((f"· Lv.{k} {txt}", LIGHT_GRAY, 0, False))
            lines.append(("", GRAY, 0, False))
        # 前后对比
        stat = None
        try:
            stat = skill.get_stat_change_text()
        except Exception:
            stat = None
        if stat:
            old_v, new_v = stat
            lines.append(("【前后对比】", GOLD, 0, True))
            lines.append((f"当前   ：{old_v}", GRAY, 0, False))
            lines.append((f"选择后 ：{new_v}", GREEN, 0, False))
            lines.append(("", GRAY, 0, False))
        # 背景介绍
        lore = getattr(skill, 'lore', None)
        if not lore:
            lore = "资料库残页：该强化的来源已不可考，只留下幸存者口口相传的只言片语。"
        lines.append(("【背景介绍】", GOLD, 0, True))
        lines.append((lore, (205, 195, 175), 0, False))
        return lines

    def _ensure_panel(self, lay, font, large_font):
        d = lay["detail"]
        sig = (self.selected_index, len(self.cards), int(d.width), int(d.height))
        if self._panel is None or self._content_sig != sig:
            panel = ScrollablePanel(int(d.x), int(d.y), int(d.width), int(d.height),
                                    title="", font=font, title_font=large_font)
            try:
                panel.bg_color = (16, 16, 24, 230)
                panel.border_color = (90, 100, 130)
                panel.scrollbar_color = (60, 65, 90)
                panel.scrollbar_thumb_color = (170, 175, 210)
            except Exception:
                pass
            if 0 <= self.selected_index < len(self.cards):
                panel.set_content(self._build_content(self.cards[self.selected_index]), font=font)
            self._panel = panel
            self._content_sig = sig
        else:
            self._panel.x = int(d.x)
            self._panel.y = int(d.y)
            self._panel.width = int(d.width)
            self._panel.height = int(d.height)
        return self._panel

    # ---------------- 输入 ----------------
    def select_tab(self, index):
        """切换到第 index 个选项（键控 1/2/3 或点击缩略图）"""
        if 0 <= index < len(self.cards) and index != self.selected_index:
            self.selected_index = index
            self.scroll_y = 0
            self._panel = None

    def confirm(self):
        """确认升级当前选中的技能，返回技能对象"""
        if self.visible and 0 <= self.selected_index < len(self.cards):
            return self.cards[self.selected_index]
        return None

    def handle_wheel(self, dy):
        """滚轮滑动详情"""
        self.scroll_y = max(0, min(self.max_scroll, self.scroll_y - dy * 40))

    def handle_input(self, mouse_pos, mouse_pressed, touch_events, scale=1.0):
        """返回被确认升级的技能（点击升级按钮时）；仅切换选项时返回 None"""
        if not self.visible or not self.cards:
            return None
        lay = self._layout(scale)
        self.tab_rects = lay["tab_rects"]
        self.detail_rect = lay["detail"]
        self.confirm_rect = lay["confirm"]
        if self.selected_index >= len(self.cards):
            self.selected_index = len(self.cards) - 1
        if self.selected_index < 0:
            self.selected_index = 0
        result = None
        for te in (touch_events or []):
            t = te.get("type", "")
            pos = te.get("pos", (0, 0))
            tid = te.get("id", 0)
            if t == "wheel":
                self.handle_wheel(te.get("dy", 0))
                continue
            if t == "down":
                if self.detail_rect.collidepoint(pos):
                    self._dragging = True
                    self._drag_id = tid
                    self._drag_start_y = pos[1]
                    self._drag_start_scroll = self.scroll_y
                elif self.confirm_rect.collidepoint(pos):
                    result = self.confirm()
                else:
                    for i, r in enumerate(self.tab_rects):
                        if r.collidepoint(pos):
                            self.select_tab(i)
                            break
            elif t == "move" and self._dragging and tid == self._drag_id:
                delta = pos[1] - self._drag_start_y
                self.scroll_y = max(0, min(self.max_scroll, self._drag_start_scroll - delta))
            elif t == "up":
                if tid == self._drag_id:
                    self._dragging = False
                    self._drag_id = None
        # 键控模式：鼠标按住拖拽滑动
        if mouse_pressed and mouse_pressed[0] and self.detail_rect.collidepoint(mouse_pos):
            if not self._dragging:
                self._dragging = True
                self._drag_id = -1
                self._drag_start_y = mouse_pos[1]
                self._drag_start_scroll = self.scroll_y
            else:
                delta = mouse_pos[1] - self._drag_start_y
                self.scroll_y = max(0, min(self.max_scroll, self._drag_start_scroll - delta))
        elif self._drag_id == -1:
            self._dragging = False
            self._drag_id = None
        return result

    # ---------------- 绘制 ----------------
    def _draw_thumb(self, screen, rect, skill, scale, selected, font):
        """技能代表缩略图"""
        border = skill.icon_color
        if selected:
            pulse = abs(math.sin(pygame.time.get_ticks() / 300)) * 0.5 + 0.5
            border = tuple(min(255, int(c + 60 * pulse)) for c in skill.icon_color)
        pygame.draw.rect(screen, (*CHARCOAL[:3], 248), rect, border_radius=int(10 * scale))
        pygame.draw.rect(screen, border, rect, max(2, int(3 if selected else 2) * 1), border_radius=int(10 * scale))
        r = max(9, int(min(rect.height * 0.30, rect.width * 0.17)))
        cx = rect.x + rect.width // 2
        cy = rect.y + int(rect.height * 0.40)
        pygame.draw.circle(screen, skill.icon_color, (cx, cy), r)
        pygame.draw.circle(screen, WHITE if selected else LIGHT_GRAY, (cx, cy), r, max(1, int(2 * scale)))
        try:
            ch = (skill.name[:1] or "技")
            ts = font.render(ch, True, WHITE)
            screen.blit(ts, (cx - ts.get_width() // 2, cy - ts.get_height() // 2))
        except Exception:
            pass
        # 技能名（过长自动缩小）
        try:
            nm = skill.name
            nt = font.render(nm, True, WHITE if selected else LIGHT_GRAY)
            if nt.get_width() > rect.width - int(10 * scale):
                small = pygame.font.Font(None, max(11, int(15 * scale)))
                nt = small.render(nm, True, WHITE if selected else LIGHT_GRAY)
            screen.blit(nt, (rect.x + (rect.width - nt.get_width()) // 2,
                             rect.y + rect.height - int(21 * scale)))
        except Exception:
            pass
        # 新技能 / 等级 角标
        try:
            tag = "NEW" if skill.current_level == 0 else f"Lv.{skill.current_level}"
            tt = pygame.font.Font(None, max(10, int(14 * scale))).render(tag, True, GOLD)
            screen.blit(tt, (rect.x + int(5 * scale), rect.y + int(4 * scale)))
        except Exception:
            pass

    def draw(self, screen, font, large_font, scale=1.0):
        if not self.visible or not self.cards:
            return
        lay = self._layout(scale)
        region = lay["region"]
        sw, sh = region.width, region.height
        rx, ry = region.x, region.y

        # 暗色遮罩（只盖对应区域）
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((*VOID_BLACK[:3], 225))
        screen.blit(overlay, (rx, ry))

        # 标题 / 副标题
        try:
            title = large_font.render(self.title, True, GOLD)
            title_rect = title.get_rect(center=(rx + sw // 2, ry + int(46 * scale)))
            screen.blit(title, title_rect)
            subtitle = font.render(self.subtitle, True, GRAY)
            subtitle_rect = subtitle.get_rect(center=(rx + sw // 2, ry + int(74 * scale)))
            screen.blit(subtitle, subtitle_rect)
        except Exception:
            pass

        # ① 顶部细栏目：三个技能缩略图
        for i, skill in enumerate(self.cards):
            if i >= len(lay["tab_rects"]):
                break
            self._draw_thumb(screen, lay["tab_rects"][i], skill, scale,
                             i == self.selected_index, font)

        # ② 中部大页面（可滑动文字框）
        panel = self._ensure_panel(lay, font, large_font)
        if panel is not None:
            try:
                panel.scroll_y = max(0, min(panel.max_scroll, self.scroll_y))
                panel.draw(screen)
                self.max_scroll = panel.max_scroll
                self.scroll_y = panel.scroll_y
            except Exception:
                pass
            # 可滑动提示
            if self.max_scroll > 0:
                try:
                    hint = pygame.font.Font(None, max(10, int(14 * scale))).render(
                        "可滑动查看更多", True, (150, 160, 190))
                    screen.blit(hint, (panel.x + panel.width - hint.get_width() - int(12 * scale),
                                       panel.y + panel.height - int(16 * scale)))
                except Exception:
                    pass

        # ③ 底部升级按钮
        b = lay["confirm"]
        try:
            _name = self.cards[self.selected_index].name if 0 <= self.selected_index < len(self.cards) else ""
            pygame.draw.rect(screen, (40, 70, 45), b, border_radius=int(10 * scale))
            pygame.draw.rect(screen, GOLD, b, max(2, int(3 * scale)), border_radius=int(10 * scale))
            txt = large_font.render(f"升级：{_name}", True, GOLD)
            screen.blit(txt, (b.x + (b.width - txt.get_width()) // 2,
                              b.y + (b.height - txt.get_height()) // 2))
            tip = pygame.font.Font(None, max(10, int(15 * scale))).render(
                "点击上方缩略图切换 · 点击此处确认升级", True, GRAY)
            screen.blit(tip, (rx + (sw - tip.get_width()) // 2, b.y + b.height + int(4 * scale)))
        except Exception:
            pass

    def _wrap_text(self, text, font, max_width):
        """自动换行"""
        lines = []
        current_line = ""
        for char in text:
            test = current_line + char
            if font.size(test)[0] > max_width and current_line:
                lines.append(current_line)
                current_line = char
            else:
                current_line = test
        if current_line:
            lines.append(current_line)
        return lines
