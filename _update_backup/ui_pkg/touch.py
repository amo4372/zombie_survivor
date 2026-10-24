#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI组件模块 - 完整重写版：技能卡选择、触控按钮位置调整、半透明范围圈"""

import pygame
import math
import random
import os
import time
from config import *


class VirtualJoystick:
    def __init__(self, x, y, radius=80):
        self.base_x = x
        self.base_y = y
        self.base_radius = radius
        self.knob_x = x
        self.knob_y = y
        self.active = False
        self.touch_id = None
        self.value_x = 0
        self.value_y = 0
        self.visible = True

    def get_scaled_pos(self, scale=1.0):
        return (self.base_x * scale, self.base_y * scale, self.base_radius * scale)

    def reset(self):
        """强制重置摇杆状态（用于游戏状态切换后防卡死）"""
        self.active = False
        self.touch_id = None
        self.knob_x = self.base_x
        self.knob_y = self.base_y
        self.value_x = 0
        self.value_y = 0

    def handle_touch(self, touch_events, scale=1.0, active_ids=None):
        bx, by, r = self.get_scaled_pos(scale)
        # 收集当前帧所有活跃的touch_id（down或move事件中的id）
        frame_active = set()
        for event in touch_events:
            if event["type"] in ("down", "move"):
                frame_active.add(event.get("id", 0))

        # 持久手指集合优先（来自 game 层，跨帧、跨状态准确）；未传入时退回当帧判断
        held = active_ids if active_ids is not None else frame_active

        # 防卡死：摇杆active但绑定的手指已不在按住集合中，且当帧也没有该手指 → 强制重置
        # 用持久集合后，静止不动的摇杆手指不会被其他手指的点击误判为"消失"
        if self.active and self.touch_id is not None \
                and self.touch_id not in held and self.touch_id not in frame_active:
            # 检查是否有up事件对应这个id
            has_up = any(e["type"] == "up" and e.get("id", 0) == self.touch_id for e in touch_events)
            if not has_up:
                self.reset()

        for event in touch_events:
            pos = event["pos"]
            dist = math.hypot(pos[0] - bx, pos[1] - by)
            if event["type"] == "down":
                if dist < r * 1.5 and not self.active:
                    self.active = True
                    self.touch_id = event.get("id", 0)
                    self._update_knob(pos[0], pos[1], scale)
                elif dist < r * 1.5 and self.active and self.touch_id != event.get("id", 0):
                    # 新手指按下且在摇杆范围内，接管摇杆（防止旧手指卡死时无法操作）
                    self.touch_id = event.get("id", 0)
                    self._update_knob(pos[0], pos[1], scale)
            elif event["type"] == "move" and self.active:
                if event.get("id", 0) == self.touch_id:
                    self._update_knob(pos[0], pos[1], scale)
            elif event["type"] == "up" and self.active:
                if event.get("id", 0) == self.touch_id:
                    self.active = False
                    self.touch_id = None
                    self.knob_x = self.base_x
                    self.knob_y = self.base_y
                    self.value_x = 0
                    self.value_y = 0

    def _update_knob(self, x, y, scale):
        bx, by, r = self.get_scaled_pos(scale)
        dx = x - bx
        dy = y - by
        dist = math.hypot(dx, dy)
        if dist > r:
            ratio = r / dist
            dx *= ratio
            dy *= ratio
        self.knob_x = (bx + dx) / scale
        self.knob_y = (by + dy) / scale
        if dist > 0:
            self.value_x = dx / r
            self.value_y = dy / r
        else:
            self.value_x = 0
            self.value_y = 0

    def draw(self, screen, scale=1.0):
        if not self.visible:
            return
        bx, by, r = self.get_scaled_pos(scale)
        bx, by, r = int(bx), int(by), int(r)
        kx = int(self.knob_x * scale)
        ky = int(self.knob_y * scale)
        pygame.draw.circle(screen, GRAY, (bx, by), r)
        pygame.draw.circle(screen, WHITE, (bx, by), r, 2)
        pygame.draw.circle(screen, LIGHT_GRAY, (kx, ky), r // 3)
        pygame.draw.circle(screen, WHITE, (kx, ky), r // 3, 2)

    def get_direction(self):
        return self.value_x, self.value_y


class TouchButton:
    """触控按钮 - 支持短按/长按检测"""
    def __init__(self, x, y, radius=60, label="", color=RED):
        self.base_x = x
        self.base_y = y
        self.base_radius = radius
        self.label = label
        self.color = color
        self.pressed = False
        self.touch_id = None
        self.visible = True
        self.cooldown = 0
        self.max_cooldown = 0
        self.reload_progress = 0
        self.is_reloading = False
        self.was_pressed = False
        self.press_start_time = 0
        self.long_press_threshold = 0.3
        self.is_long_press = False
        self.just_released = False
        self.just_pressed = False

    def get_scaled_pos(self, scale=1.0):
        return (self.base_x * scale, self.base_y * scale, self.base_radius * scale)

    def handle_touch(self, touch_events, scale=1.0):
        if self.cooldown > 0:
            self.cooldown -= 1 / 60
        tx, ty, tr = self.get_scaled_pos(scale)
        tx, ty, tr = int(tx), int(ty), int(tr)
        self.just_released = False
        self.just_pressed = False
        for event in touch_events:
            pos = event["pos"]
            dist = math.hypot(pos[0] - tx, pos[1] - ty)
            if event["type"] == "down":
                if dist < tr and not self.pressed:
                    self.pressed = True
                    self.just_pressed = True
                    self.touch_id = event.get("id", 0)
                    self.press_start_time = time.time()
                    self.is_long_press = False
                    self.was_pressed = True
            elif event["type"] == "move" and self.pressed:
                if event.get("id", 0) == self.touch_id:
                    if not self.is_long_press and time.time() - self.press_start_time >= self.long_press_threshold:
                        self.is_long_press = True
            elif event["type"] == "up":
                if event.get("id", 0) == self.touch_id:
                    if self.pressed:
                        self.just_released = True
                    self.pressed = False
                    self.is_long_press = False
                    self.touch_id = None
        return self.just_released

    def draw(self, screen, font, scale=1.0):
        if not self.visible:
            return
        tx, ty, tr = self.get_scaled_pos(scale)
        tx, ty, tr = int(tx), int(ty), int(tr)
        color = tuple(min(255, c + 40) for c in self.color) if self.pressed else self.color
        pygame.draw.circle(screen, color, (tx, ty), tr)
        pygame.draw.circle(screen, WHITE, (tx, ty), tr, 3)
        if self.label:
            text = font.render(self.label, True, WHITE)
            text_rect = text.get_rect(center=(tx, ty))
            screen.blit(text, text_rect)

        # 换弹CD遮罩（逆时针，琥珀色）- 增强
        if self.is_reloading and self.reload_progress > 0:
            start_angle = math.pi / 2
            end_angle = start_angle - self.reload_progress * 2 * math.pi
            points = [(tx, ty)]
            steps = 30
            for i in range(steps + 1):
                angle = start_angle - (start_angle - end_angle) * (i / steps)
                points.append((tx + math.cos(angle) * tr, ty + math.sin(angle) * tr))
            points.append((tx, ty))
            pygame.draw.polygon(screen, (*AMBER[:3], 220), points)
            # 黑色半透明覆盖
            mask_surf = pygame.Surface((tr * 2, tr * 2), pygame.SRCALPHA)
            pygame.draw.circle(mask_surf, (0, 0, 0, 100), (tr, tr), tr)
            screen.blit(mask_surf, (tx - tr, ty - tr))
            reload_text = font.render("换弹", True, WHITE)
            reload_rect = reload_text.get_rect(center=(tx, ty))
            # 文字背景
            cd_bg = pygame.Surface((reload_rect.width + 8, reload_rect.height + 4), pygame.SRCALPHA)
            cd_bg.fill((0, 0, 0, 150))
            screen.blit(cd_bg, (reload_rect.x - 4, reload_rect.y - 2))
            screen.blit(reload_text, reload_rect)

        # 技能/冷却CD遮罩（顺时针）- 增强黑色
        elif self.cooldown > 0 and self.max_cooldown > 0:
            ratio = self.cooldown / self.max_cooldown
            # 全圆黑色遮罩
            mask_alpha = max(0, min(255, int(200 * ratio + 40)))
            mask_surf = pygame.Surface((tr * 2, tr * 2), pygame.SRCALPHA)
            pygame.draw.circle(mask_surf, (0, 0, 0, mask_alpha), (tr, tr), tr)
            screen.blit(mask_surf, (tx - tr, ty - tr))

            # 红色进度环
            start_angle = -math.pi / 2
            end_angle = start_angle + ratio * 2 * math.pi
            pygame.draw.arc(screen, RED, (tx - tr - 2, ty - tr - 2, (tr+2)*2, (tr+2)*2), 
                          start_angle, end_angle, max(2, int(3*scale)))

            cd_text = font.render(f"{self.cooldown:.1f}", True, WHITE)
            cd_rect = cd_text.get_rect(center=(tx, ty))
            # CD文字背景
            cd_bg = pygame.Surface((cd_rect.width + 8, cd_rect.height + 4), pygame.SRCALPHA)
            cd_bg.fill((0, 0, 0, 150))
            screen.blit(cd_bg, (cd_rect.x - 4, cd_rect.y - 2))
            screen.blit(cd_text, cd_rect)

    def set_cooldown(self, seconds):
        self.cooldown = seconds
        self.max_cooldown = seconds


class AimButton:
    """瞄准/攻击摇杆 - 右下区域"""
    def __init__(self, x, y, radius=70):
        self.base_x = x
        self.base_y = y
        self.base_radius = radius
        self.angle = 0
        self.active = False
        self.touch_id = None
        self.visible = True
        self.knob_offset_x = 0
        self.knob_offset_y = 0
        self.is_shooting = False
        self.press_start_time = 0
        self.is_aiming = False
        self.just_tapped = False
        self.tap_threshold = 0.25

    def get_scaled_pos(self, scale=1.0):
        return (self.base_x * scale, self.base_y * scale, self.base_radius * scale)

    def handle_touch(self, touch_events, scale=1.0):
        bx, by, r = self.get_scaled_pos(scale)
        bx, by, r = int(bx), int(by), int(r)
        self.just_tapped = False
        for event in touch_events:
            pos = event["pos"]
            dist = math.hypot(pos[0] - bx, pos[1] - by)
            if event["type"] == "down":
                if dist < r * 1.5 and not self.active:
                    self.active = True
                    self.touch_id = event.get("id", 0)
                    self.press_start_time = time.time()
                    self.is_aiming = False
                    self.is_shooting = True
                    self._update_angle(pos[0], pos[1], bx, by)
            elif event["type"] == "move" and self.active:
                if event.get("id", 0) == self.touch_id:
                    self._update_angle(pos[0], pos[1], bx, by)
                    if not self.is_aiming and time.time() - self.press_start_time >= self.tap_threshold:
                        self.is_aiming = True
            elif event["type"] == "up":
                if event.get("id", 0) == self.touch_id:
                    press_duration = time.time() - self.press_start_time
                    if press_duration < self.tap_threshold:
                        self.just_tapped = True
                    self.active = False
                    self.touch_id = None
                    self.knob_offset_x = 0
                    self.knob_offset_y = 0
                    self.is_shooting = False
                    self.is_aiming = False

    def _update_angle(self, tx, ty, bx, by):
        dx = tx - bx
        dy = ty - by
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.angle = math.atan2(dy, dx)
            r = self.base_radius
            if dist > r:
                ratio = r / dist
                self.knob_offset_x = dx * ratio
                self.knob_offset_y = dy * ratio
            else:
                self.knob_offset_x = dx
                self.knob_offset_y = dy

    def draw(self, screen, font, scale=1.0):
        if not self.visible:
            return
        bx, by, r = self.get_scaled_pos(scale)
        bx, by, r = int(bx), int(by), int(r)
        kx = int(bx + self.knob_offset_x * scale)
        ky = int(by + self.knob_offset_y * scale)
        base_color = ORANGE if self.is_aiming else DARK_GRAY
        pygame.draw.circle(screen, base_color, (bx, by), r)
        pygame.draw.circle(screen, WHITE, (bx, by), r, 2)
        line_end_x = bx + math.cos(self.angle) * r
        line_end_y = by + math.sin(self.angle) * r
        line_color = RED if self.is_shooting else CYAN
        pygame.draw.line(screen, line_color, (bx, by), (line_end_x, line_end_y), 3)
        knob_color = RED if self.is_shooting else CYAN
        pygame.draw.circle(screen, knob_color, (kx, ky), r // 3)
        pygame.draw.circle(screen, WHITE, (kx, ky), r // 3, 2)
        if self.is_aiming:
            pygame.draw.circle(screen, (*AMBER[:3], 100), (bx, by), r + 5, 2)

    def get_angle(self):
        return self.angle


class WeaponSwitchButton(TouchButton):
    """武器切换按钮 - 短按切换下一个武器，长按显示武器轮盘"""
    def __init__(self, x, y, radius=55, label="换", color=PURPLE):
        super().__init__(x, y, radius, label, color)
        self.long_press_threshold = 0.4
        self.is_long_press = False
        self.wheel_active = False
        self.wheel_just_activated = False
        self.should_open_wheel = False  # 新增

    def handle_touch(self, touch_events, scale=1.0):
        if self.cooldown > 0:
            self.cooldown -= 1 / 60
        tx, ty, tr = self.get_scaled_pos(scale)
        tx, ty, tr = int(tx), int(ty), int(tr)
        self.just_released = False
        self.wheel_just_activated = False
        had_wheel_active = self.wheel_active
        # 关键修复：不要每帧重置should_open_wheel

        for event in touch_events:
            pos = event["pos"]
            dist = math.hypot(pos[0] - tx, pos[1] - ty)
            if event["type"] == "down":
                if dist < tr and not self.pressed:
                    self.pressed = True
                    self.just_pressed = True
                    self.touch_id = event.get("id", 0)
                    self.press_start_time = time.time()
                    self.is_long_press = False
                    self.wheel_active = False
                    self.should_open_wheel = False
                    self.was_pressed = True
            elif event["type"] == "move" and self.pressed:
                if event.get("id", 0) == self.touch_id:
                    if not self.wheel_active and time.time() - self.press_start_time >= self.long_press_threshold:
                        self.wheel_active = True
                        self.is_long_press = True
                        self.wheel_just_activated = True
                        self.should_open_wheel = True
            elif event["type"] == "up":
                if event.get("id", 0) == self.touch_id:
                    press_duration = time.time() - self.press_start_time
                    if self.pressed and not self.wheel_active:
                        self.just_released = True
                    self.pressed = False
                    if had_wheel_active or self.wheel_active:
                        self.should_open_wheel = True
                    self.wheel_active = False
                    self.is_long_press = False
                    self.touch_id = None
        return self.just_released


    def is_showing_wheel(self):
        return self.should_open_wheel

    def wheel_just_opened(self):
        return self.wheel_just_activated
