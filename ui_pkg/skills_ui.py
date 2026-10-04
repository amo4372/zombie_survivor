#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI组件模块 - 完整重写版：技能卡选择、触控按钮位置调整、半透明范围圈"""

import pygame
import math
import random
import os
import time
from config import *


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
        elif skill_type == SkillType.SHIELD_BASH:
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
        elif skill_type == SkillType.SHOCKWAVE:
            range_surf = pygame.Surface((int(300 * scale), int(300 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*ORANGE[:3], 50), (int(150 * scale), int(150 * scale)), int(150 * scale))
            screen.blit(range_surf, (px - int(150 * scale), py - int(100 * scale)))
            pygame.draw.circle(screen, ORANGE, (px, py), int(150 * scale), max(1, int(2 * scale)))
            for i in range(12):
                rad = math.radians(i * 30)
                sx = px + math.cos(rad) * 100 * scale
                sy = py + math.sin(rad) * 100 * scale
                ex = px + math.cos(rad) * 150 * scale
                ey = py + math.sin(rad) * 150 * scale
                pygame.draw.line(screen, ORANGE, (int(sx), int(sy)), (int(ex), int(ey)), max(1, int(2 * scale)))


class SkillCardSelector:
    """技能卡选择界面（支持同屏双人：只在对应玩家半屏区域显示并标注是谁升级）"""
    def __init__(self):
        self.visible = False
        self.cards = []
        self.selected_index = -1
        self.card_rects = []
        self.animation_timer = 0
        self.animation_duration = 0.3
        self.region = None          # pygame.Rect 或 None（None=全屏）
        self.title = "选择一项技能"
        self.subtitle = "升级！选择你的强化"

    def show(self, skills, region=None, title="选择一项技能", subtitle="升级！选择你的强化"):
        self.visible = True
        self.cards = skills
        self.selected_index = -1
        self.animation_timer = 0
        self.region = region
        self.title = title
        self.subtitle = subtitle

    def hide(self):
        self.visible = False
        self.cards = []
        self.selected_index = -1
        self.region = None

    def _get_region(self):
        if self.region is not None:
            return self.region
        w = pygame.display.get_surface().get_width()
        h = pygame.display.get_surface().get_height()
        return pygame.Rect(0, 0, w, h)

    def handle_input(self, mouse_pos, mouse_pressed, touch_events, scale=1.0):
        if not self.visible:
            return None

        self.card_rects = []
        region = self._get_region()
        sw = region.width
        sh = region.height
        rx = region.x
        ry = region.y

        card_w = int(230 * scale)
        card_h = int(400 * scale)
        gap = int(25 * scale)
        total_width = len(self.cards) * card_w + (len(self.cards) - 1) * gap
        # 卡片过宽时按区域缩放卡片宽度
        if total_width > sw - int(20 * scale):
            card_w = int((sw - int(20 * scale) - (len(self.cards) - 1) * gap) / len(self.cards))
            card_w = max(140, card_w)
            total_width = len(self.cards) * card_w + (len(self.cards) - 1) * gap
        start_x = rx + (sw - total_width) // 2
        start_y = ry + (sh - card_h) // 2 + int(10 * scale)

        for i, skill in enumerate(self.cards):
            rect = pygame.Rect(start_x + i * (card_w + gap), start_y, card_w, card_h)
            self.card_rects.append(rect)

            # 检查点击
            clicked = False
            if rect.collidepoint(mouse_pos) and mouse_pressed[0]:
                clicked = True
            if touch_events:
                for event in touch_events:
                    if event["type"] == "down" and rect.collidepoint(event["pos"]):
                        clicked = True

            if clicked:
                self.selected_index = i
                return skill

        return None

    def draw(self, screen, font, large_font, scale=1.0):
        if not self.visible:
            return

        region = self._get_region()
        sw = region.width
        sh = region.height
        rx = region.x
        ry = region.y

        # 暗色背景遮罩（只盖对应区域）
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((*VOID_BLACK[:3], 220))
        screen.blit(overlay, (rx, ry))

        # 标题（含是谁升级）
        title = large_font.render(self.title, True, GOLD)
        title_rect = title.get_rect(center=(rx + sw // 2, ry + int(70 * scale)))
        screen.blit(title, title_rect)

        subtitle = font.render(self.subtitle, True, GRAY)
        subtitle_rect = subtitle.get_rect(center=(rx + sw // 2, ry + int(105 * scale)))
        screen.blit(subtitle, subtitle_rect)

        # 绘制技能卡 - 增大卡片高度保证内容完整显示
        card_w = int(230 * scale)
        card_h = int(400 * scale)
        gap = int(25 * scale)
        total_width = len(self.cards) * card_w + (len(self.cards) - 1) * gap
        if total_width > sw - int(20 * scale):
            card_w = int((sw - int(20 * scale) - (len(self.cards) - 1) * gap) / len(self.cards))
            card_w = max(140, card_w)
            total_width = len(self.cards) * card_w + (len(self.cards) - 1) * gap
        start_x = rx + (sw - total_width) // 2
        start_y = ry + (sh - card_h) // 2 + int(10 * scale)

        for i, skill in enumerate(self.cards):
            x = start_x + i * (card_w + gap)
            y = start_y

            # 卡片背景
            card_rect = pygame.Rect(x, y, card_w, card_h)

            # 悬停效果
            is_new = skill.current_level == 0
            base_color = skill.icon_color if skill.current_level > 0 else DARK_GRAY
            if is_new:
                # 新技能闪烁边框
                pulse = abs(math.sin(pygame.time.get_ticks() / 300)) * 0.5 + 0.5
                border_color = tuple(min(255, int(c + 50 * pulse)) for c in skill.icon_color)
            else:
                border_color = skill.icon_color

            pygame.draw.rect(screen, (*CHARCOAL[:3], 245), card_rect, border_radius=int(12 * scale))
            pygame.draw.rect(screen, border_color, card_rect, max(2, int(3 * scale)), border_radius=int(12 * scale))

            # 技能图标区域
            icon_y = y + int(15 * scale)
            icon_radius = int(32 * scale)
            icon_center = (x + card_w // 2, icon_y + icon_radius)
            pygame.draw.circle(screen, skill.icon_color, icon_center, icon_radius)
            pygame.draw.circle(screen, WHITE, icon_center, icon_radius, max(1, int(2 * scale)))

            # 技能名称（自动缩小字号适配）
            name_y = icon_y + icon_radius * 2 + int(10 * scale)
            name_font = font
            name_text = name_font.render(skill.name, True, WHITE)
            # 如果名称太长，用更小字号
            if name_text.get_width() > card_w - int(30 * scale):
                name_font = pygame.font.Font(None, int(20 * scale))
                name_text = name_font.render(skill.name, True, WHITE)
            name_rect = name_text.get_rect(center=(x + card_w // 2, name_y))
            screen.blit(name_text, name_rect)

            # 等级
            level_y = name_y + int(22 * scale)
            level_text = font.render(f"Lv.{skill.current_level}/{skill.max_level}", True, GOLD)
            level_rect = level_text.get_rect(center=(x + card_w // 2, level_y))
            screen.blit(level_text, level_rect)

            # 类型标签
            type_y = level_y + int(18 * scale)
            type_color = CYAN if skill.is_active else GREEN
            type_text = font.render("【主动】" if skill.is_active else "【被动】", True, type_color)
            type_rect = type_text.get_rect(center=(x + card_w // 2, type_y))
            screen.blit(type_text, type_rect)

            # 描述（使用下一级词条，高等级技能显示不同描述）- 最多4行
            desc_y = type_y + int(22 * scale)
            next_desc = skill.get_next_level_desc()
            desc_lines = self._wrap_text(next_desc, font, card_w - int(24 * scale))
            max_desc_lines = 4
            for j, line in enumerate(desc_lines[:max_desc_lines]):
                desc_text = font.render(line, True, LIGHT_GRAY)
                desc_rect = desc_text.get_rect(center=(x + card_w // 2, desc_y + j * int(19 * scale)))
                screen.blit(desc_text, desc_rect)

            # 实际使用的描述行数
            actual_desc_lines = min(len(desc_lines), max_desc_lines)
            desc_end_y = desc_y + actual_desc_lines * int(19 * scale)

            # 属性加成详情（原属性 -> 新属性）- 动态位置
            stat_change = skill.get_stat_change_text()
            if stat_change:
                old_text, new_text = stat_change
                stat_y = desc_end_y + int(10 * scale)
                # 分隔线
                pygame.draw.line(screen, (*GRAY[:3], 120),
                                 (x + int(18 * scale), stat_y),
                                 (x + card_w - int(18 * scale), stat_y), 1)
                stat_y += int(8 * scale)
                # 原属性
                old_label = font.render("当前", True, GRAY)
                old_val = font.render(old_text, True, GRAY)
                screen.blit(old_label, (x + int(18 * scale), stat_y))
                screen.blit(old_val, (x + card_w - int(18 * scale) - old_val.get_width(), stat_y))
                stat_y += int(16 * scale)
                # 箭头
                arrow = font.render("v", True, GOLD)
                screen.blit(arrow, (x + card_w // 2 - arrow.get_width() // 2, stat_y - int(2 * scale)))
                stat_y += int(14 * scale)
                # 新属性
                new_label = font.render("选择后", True, GOLD)
                new_val = font.render(new_text, True, GREEN)
                screen.blit(new_label, (x + int(18 * scale), stat_y))
                screen.blit(new_val, (x + card_w - int(18 * scale) - new_val.get_width(), stat_y))

            # 前置要求提示
            if is_new and skill.requires:
                req_y = y + card_h - int(32 * scale)
                req_text = font.render("新技能！", True, GOLD)
                req_rect = req_text.get_rect(center=(x + card_w // 2, req_y))
                screen.blit(req_text, req_rect)

            # 点击提示
            hint_y = y + card_h - int(14 * scale)
            hint_text = font.render("点击选择", True, GRAY)
            hint_rect = hint_text.get_rect(center=(x + card_w // 2, hint_y))
            screen.blit(hint_text, hint_rect)

    def _wrap_text(self, text, font, max_width):
        """自动换行"""
        words = []
        for char in text:
            words.append(char)
        lines = []
        current_line = ""
        for char in words:
            test = current_line + char
            if font.size(test)[0] > max_width and current_line:
                lines.append(current_line)
                current_line = char
            else:
                current_line = test
        if current_line:
            lines.append(current_line)
        return lines
