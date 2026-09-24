#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI组件模块 - 完整重写版：技能卡选择、触控按钮位置调整、半透明范围圈"""

import pygame
import math
import random
import os
import time
from config import *


class FontManager:
    _fonts = {}
    _base_path = None

    @classmethod
    def init(cls, base_path):
        cls._base_path = base_path

    @classmethod
    def get(cls, size):
        key = size
        if key in cls._fonts:
            return cls._fonts[key]
        font = cls._load_font(size)
        cls._fonts[key] = font
        return font

    @classmethod
    def _load_font(cls, size):
        try:
            paths = [
                os.path.join(cls._base_path, "assets/fonts/custom.ttf"),
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/System/Library/Fonts/PingFang.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simsun.ttc"
            ]
            for p in paths:
                if os.path.exists(p):
                    return pygame.font.Font(p, size)
        except:
            pass
        try:
            return pygame.font.SysFont("simhei", size)
        except:
            try:
                return pygame.font.SysFont("microsoftyahei", size)
            except:
                return pygame.font.SysFont("arial", size)


class Button:
    def __init__(self, x, y, width, height, text,
                 color=DARK_GRAY, hover_color=GRAY, text_color=WHITE,
                 font_size=24, border_radius=8):
        self.base_x = x
        self.base_y = y
        self.base_w = width
        self.base_h = height
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.font_size = font_size
        self.border_radius = border_radius
        self.hovered = False
        self.pressed = False
        self.visible = True
        self.enabled = True
        self.was_pressed = False

    def get_scaled_rect(self, scale=1.0):
        return pygame.Rect(
            int(self.base_x * scale),
            int(self.base_y * scale),
            int(self.base_w * scale),
            int(self.base_h * scale)
        )

    def update(self, mouse_pos, mouse_pressed, touch_events=None, scale=1.0):
        if not self.visible or not self.enabled:
            return False
        scaled_rect = self.get_scaled_rect(scale)
        self.hovered = scaled_rect.collidepoint(mouse_pos)
        clicked = False
        touch_down_on_button = False
        if touch_events:
            for event in touch_events:
                if event["type"] == "down":
                    if scaled_rect.collidepoint(event["pos"]):
                        self.pressed = True
                        touch_down_on_button = True
                elif event["type"] == "up":
                    if self.pressed:
                        self.pressed = False
                        if scaled_rect.collidepoint(event["pos"]):
                            clicked = True
                    elif touch_down_on_button and scaled_rect.collidepoint(event["pos"]):
                        # 瞬发点击：同一帧内有down和up
                        clicked = True
        if self.hovered:
            if mouse_pressed[0]:
                if not self.was_pressed:
                    self.pressed = True
                    self.was_pressed = True
            else:
                if self.was_pressed:
                    self.pressed = False
                    self.was_pressed = False
                    clicked = True
        else:
            if not mouse_pressed[0]:
                self.was_pressed = False
            self.pressed = False
        return clicked

    def draw(self, screen, font, scale=1.0):
        if not self.visible:
            return
        scaled_rect = self.get_scaled_rect(scale)
        if not self.enabled:
            color = (60, 60, 60)
        else:
            color = self.hover_color if self.hovered else self.color
        if self.pressed:
            color = tuple(max(0, c - 40) for c in color)
        pygame.draw.rect(screen, color, scaled_rect, border_radius=self.border_radius)
        pygame.draw.rect(screen, self.text_color, scaled_rect, 2, border_radius=self.border_radius)
        text_surf = font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=scaled_rect.center)
        screen.blit(text_surf, text_rect)


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


class SkillCardSelector:
    """技能卡选择界面"""
    def __init__(self):
        self.visible = False
        self.cards = []
        self.selected_index = -1
        self.card_rects = []
        self.animation_timer = 0
        self.animation_duration = 0.3

    def show(self, skills):
        self.visible = True
        self.cards = skills
        self.selected_index = -1
        self.animation_timer = 0

    def hide(self):
        self.visible = False
        self.cards = []
        self.selected_index = -1

    def handle_input(self, mouse_pos, mouse_pressed, touch_events, scale=1.0):
        if not self.visible:
            return None

        self.card_rects = []
        sw = pygame.display.get_surface().get_width()
        sh = pygame.display.get_surface().get_height()

        card_w = int(230 * scale)
        card_h = int(400 * scale)
        gap = int(25 * scale)
        total_width = len(self.cards) * card_w + (len(self.cards) - 1) * gap
        start_x = (sw - total_width) // 2
        start_y = (sh - card_h) // 2 + int(10 * scale)

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

        sw = screen.get_width()
        sh = screen.get_height()

        # 暗色背景遮罩
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((*VOID_BLACK[:3], 220))
        screen.blit(overlay, (0, 0))

        # 标题
        title = large_font.render("选择一项技能", True, GOLD)
        title_rect = title.get_rect(center=(sw // 2, int(80 * scale)))
        screen.blit(title, title_rect)

        subtitle = font.render("升级！选择你的强化", True, GRAY)
        subtitle_rect = subtitle.get_rect(center=(sw // 2, int(115 * scale)))
        screen.blit(subtitle, subtitle_rect)

        # 绘制技能卡 - 增大卡片高度保证内容完整显示
        card_w = int(230 * scale)
        card_h = int(400 * scale)
        gap = int(25 * scale)
        total_width = len(self.cards) * card_w + (len(self.cards) - 1) * gap
        start_x = (sw - total_width) // 2
        start_y = (sh - card_h) // 2 + int(10 * scale)

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


class DeathAura:
    """敌人死亡光环效果"""
    def __init__(self, x, y, color, max_radius=80, duration=1.5):
        self.x = x
        self.y = y
        self.color = color
        self.max_radius = max_radius
        self.duration = duration
        self.lifetime = duration
        self.rings = 2

    def update(self, dt):
        self.lifetime -= dt
        return self.lifetime > 0

    def draw(self, screen, camera_x, camera_y, scale=1.0):
        progress = 1.0 - (self.lifetime / self.duration)
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        for i in range(self.rings):
            ring_progress = min(1.0, progress * (self.rings - i) / self.rings)
            radius = int(self.max_radius * ring_progress * scale)
            alpha = int(200 * (1.0 - ring_progress))
            if radius > 0:
                ring_color = tuple(min(255, int(c * (1.0 - ring_progress * 0.5))) for c in self.color[:3])
                pygame.draw.circle(screen, ring_color, (px, py), radius, max(1, int(2 * scale)))
                if ring_progress < 0.5:
                    fill_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                    pygame.draw.circle(fill_surf, (*ring_color[:3], alpha // 2), (radius, radius), radius)
                    screen.blit(fill_surf, (px - radius, py - radius))


class DamageNumber:
    # 伤害类型对应的颜色
    TYPE_COLORS = {
        "normal": WHITE,
        "melee": (255, 220, 180),
        "ranged": (180, 220, 255),
        "crit": (255, 200, 50),
        "dot": (255, 120, 80),
        "fire": (255, 100, 20),
        "poison": (120, 200, 50),
        "bleed": (200, 30, 30),
        "corrosion": (150, 200, 50),
        "freeze": (100, 200, 255),
        "explosion": (255, 150, 0),
        "aoe": (255, 180, 50),
        "magic": (200, 100, 255),
        "heal": (80, 255, 120),
    }

    def __init__(self, x, y, damage, color=None, is_crit=False, damage_type="normal"):
        self.x = x
        self.y = y
        self.damage = damage
        self.damage_type = damage_type
        self.is_crit = is_crit
        # 暴击优先用暴击色
        if is_crit:
            self.color = self.TYPE_COLORS["crit"]
        elif color is not None:
            self.color = color
        else:
            self.color = self.TYPE_COLORS.get(damage_type, WHITE)
        self.lifetime = 1.0
        self.vy = -2
        # 是否为buff持续伤害
        self.is_dot = damage_type in ("fire", "poison", "bleed", "corrosion", "freeze", "dot")
        # 根据伤害大小计算字号倍率（整体放大20%）
        if damage < 10:
            self.size_mult = 0.85
        elif damage < 30:
            self.size_mult = 1.0
        elif damage < 60:
            self.size_mult = 1.2
        elif damage < 100:
            self.size_mult = 1.4
        elif damage < 200:
            self.size_mult = 1.65
        else:
            self.size_mult = 2.0
        # 暴击额外放大
        if is_crit:
            self.size_mult *= 1.35
        # buff持续伤害额外放大15%
        if self.is_dot:
            self.size_mult *= 1.15

    def update(self, dt):
        self.y += self.vy * dt * 60
        self.vy += 0.05 * dt * 60
        self.lifetime -= dt

    def draw(self, screen, font, camera_x=0, camera_y=0, scale=1.0):
        alpha = int(255 * self.lifetime)
        # 暴击显示!，其余纯数字
        text = f"{int(self.damage)}" + ("!" if self.is_crit else "")
        text_surf = font.render(text, True, self.color)
        # 根据size_mult缩放表面
        if self.size_mult != 1.0:
            import pygame
            orig_w, orig_h = text_surf.get_size()
            new_w = max(4, int(orig_w * self.size_mult))
            new_h = max(4, int(orig_h * self.size_mult))
            text_surf = pygame.transform.smoothscale(text_surf, (new_w, new_h))
        text_surf.set_alpha(alpha)
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        # 居中对齐
        text_rect = text_surf.get_rect(center=(px, py))
        # buff伤害数字添加描边增强可读性
        if self.is_dot and self.lifetime > 0.3:
            import pygame
            outline = pygame.Surface(text_surf.get_size(), pygame.SRCALPHA)
            outline.fill((0, 0, 0, 80))
            outline.blit(text_surf, (0, 0))
            screen.blit(outline, text_rect)
        else:
            screen.blit(text_surf, text_rect)

    def is_alive(self):
        return self.lifetime > 0


class FloatingText:
    def __init__(self, x, y, text, color=YELLOW, lifetime=2.0):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.vy = -1.5

    def update(self, dt):
        self.y += self.vy * dt * 60
        self.lifetime -= dt

    def draw(self, screen, font, camera_x=0, camera_y=0, scale=1.0):
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        text_surf = font.render(self.text, True, self.color)
        text_surf.set_alpha(alpha)
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        screen.blit(text_surf, (px, py))

    def is_alive(self):
        return self.lifetime > 0


class Particle:
    def __init__(self, x, y, color, size, velocity, lifetime):
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        self.vx, self.vy = velocity
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.gravity = 0.1

    def update(self, dt):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.vy += self.gravity * dt * 60
        self.lifetime -= dt
        self.size = max(1, self.size * (self.lifetime / self.max_lifetime))

    def draw(self, screen, camera_x=0, camera_y=0, scale=1.0):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(1, int(self.size * scale))
        pygame.draw.circle(screen, self.color, (px, py), s)

    def is_alive(self):
        return self.lifetime > 0


class ParticleSystem:
    def __init__(self):
        self.particles = []
        self.death_auras = []

    def spawn(self, x, y, color, count=5, size_range=(2, 6),
              velocity_range=(-3, 3), lifetime_range=(0.3, 1.0)):
        # 兼容 float 参数（mod 可能传入浮点值）
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 5
        try:
            lo, hi = int(size_range[0]), int(size_range[1])
        except (TypeError, ValueError, IndexError):
            lo, hi = 2, 6
        for _ in range(count):
            size = random.randint(lo, hi)
            vx = random.uniform(*velocity_range)
            vy = random.uniform(*velocity_range)
            lifetime = random.uniform(*lifetime_range)
            self.particles.append(Particle(x, y, color, size, (vx, vy), lifetime))

    def spawn_particle(self, x, y, vx, vy, color, lifetime, size):
        """生成单个粒子，带固定速度（用于环形冲击波、拖尾等定向效果）"""
        self.particles.append(Particle(x, y, color, size, (vx, vy), lifetime))

    def spawn_explosion(self, x, y, color, count=20):
        self.spawn(x, y, color, count, (3, 10), (-8, 8), (0.5, 1.5))

    def add(self, x, y, color, count=5, size_range=(2, 6),
            velocity_range=(-3, 3), lifetime_range=(0.3, 1.0)):
        """Mod 兼容别名：等同于 spawn()"""
        self.spawn(x, y, color, count, size_range, velocity_range, lifetime_range)

    def spawn_blood(self, x, y, count=8):
        self.spawn(x, y, RED, count, (2, 5), (-4, 4), (0.3, 0.8))

    def spawn_heal_particles(self, x, y, count=15):
        """生成治疗粒子（绿色向上飘动）"""
        for _ in range(count):
            size = random.randint(3, 7)
            vx = random.uniform(-1.5, 1.5)
            vy = random.uniform(-4, -1.5)
            lifetime = random.uniform(0.5, 1.2)
            self.particles.append(Particle(x, y, LIME, size, (vx, vy), lifetime))

    def spawn_death_aura(self, x, y, color):
        self.death_auras.append(DeathAura(x, y, color))

    def update(self, dt):
        for p in self.particles[:]:
            p.update(dt)
            if not p.is_alive():
                self.particles.remove(p)
        for aura in self.death_auras[:]:
            if not aura.update(dt):
                self.death_auras.remove(aura)

    def draw(self, screen, camera_x=0, camera_y=0, scale=1.0):
        for aura in self.death_auras:
            aura.draw(screen, camera_x, camera_y, scale)
        for p in self.particles:
            p.draw(screen, camera_x, camera_y, scale)


def draw_dashed_line(surface, color, start_pos, end_pos, dash_length=10, gap_length=5, width=1):
    x1, y1 = start_pos
    x2, y2 = end_pos
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    dx_unit = dx / dist
    dy_unit = dy / dist
    step = dash_length + gap_length
    current = 0
    while current < dist:
        seg_start = (x1 + dx_unit * current, y1 + dy_unit * current)
        seg_end_dist = min(current + dash_length, dist)
        seg_end = (x1 + dx_unit * seg_end_dist, y1 + dy_unit * seg_end_dist)
        pygame.draw.line(surface, color, seg_start, seg_end, width)
        current += step



class ScrollablePanel:
    """可滚动文本面板 - 支持滚轮/触控拖动，用于显示大量信息"""
    
    def __init__(self, x, y, width, height, title="", font=None, title_font=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.title = title
        self.font = font
        self.title_font = title_font
        
        self.scroll_y = 0
        self.content_height = 0
        self.max_scroll = 0
        
        # 触控拖动
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_scroll = 0
        self._touch_id = None
        
        # 样式
        self.bg_color = (20, 20, 30, 220)
        self.border_color = (100, 100, 140)
        self.text_color = (220, 220, 220)
        self.title_color = (255, 215, 0)
        self.scrollbar_color = (80, 80, 120)
        self.scrollbar_thumb_color = (150, 150, 200)
        
        # 内容行：[(text, color, indent, is_header)]
        self._lines = []
        self._line_height = 20
        
    def set_content(self, text_or_lines, font=None):
        """设置内容，可以是字符串或行列表"""
        if font:
            self.font = font
        self._lines = []
        if isinstance(text_or_lines, str):
            self._wrap_text(text_or_lines, self.width - 40)
        elif isinstance(text_or_lines, list):
            for item in text_or_lines:
                if isinstance(item, str):
                    self._wrap_text(item, self.width - 40, color=self.text_color)
                elif isinstance(item, tuple):
                    text = item[0]
                    color = item[1] if len(item) > 1 else self.text_color
                    indent = item[2] if len(item) > 2 else 0
                    is_header = item[3] if len(item) > 3 else False
                    self._wrap_text(text, self.width - 40 - indent, color=color, indent=indent, is_header=is_header)
        self._update_content_height()
        
    def _wrap_text(self, text, max_width, color=None, indent=0, is_header=False):
        """自动换行"""
        if color is None:
            color = self.text_color
        if not self.font:
            self._lines.append((text, color, indent, is_header))
            return
        # 按换行符分割
        paragraphs = text.split('\n')
        for para in paragraphs:
            if not para:
                self._lines.append(("", color, indent, is_header))
                continue
            words = list(para)  # 中文按字符
            current = ""
            for ch in words:
                test = current + ch
                if self.font.size(test)[0] > max_width and current:
                    self._lines.append((current, color, indent, is_header))
                    current = ch
                else:
                    current = test
            if current:
                self._lines.append((current, color, indent, is_header))
    
    def _update_content_height(self):
        """计算内容总高度"""
        header_height = 30 if self.title else 0
        line_h = self._line_height
        self.content_height = header_height + len(self._lines) * line_h + 20
        self.max_scroll = max(0, self.content_height - self.height + 10)
        self.scroll_y = min(self.scroll_y, self.max_scroll)
    
    def handle_wheel(self, y):
        """处理滚轮"""
        self.scroll_y = max(0, min(self.max_scroll, self.scroll_y - y * 40))
    
    def handle_touch(self, touch_events):
        """处理触控事件（dict列表）"""
        for te in touch_events:
            te_type = te.get("type", "")
            te_pos = te.get("pos", (0, 0))
            te_id = te.get("id", 0)
            # 检查是否在面板内
            if not (self.x <= te_pos[0] <= self.x + self.width and
                    self.y <= te_pos[1] <= self.y + self.height):
                continue
            if te_type == "down":
                self._dragging = True
                self._drag_start_y = te_pos[1]
                self._drag_start_scroll = self.scroll_y
                self._touch_id = te_id
            elif te_type == "move" and self._dragging and te_id == self._touch_id:
                delta = te_pos[1] - self._drag_start_y
                self.scroll_y = max(0, min(self.max_scroll, self._drag_start_scroll - delta))
            elif te_type == "up":
                if te_id == self._touch_id:
                    self._dragging = False
                    self._touch_id = None
    
    def handle_mouse(self, mouse_pos, mouse_pressed):
        """处理鼠标拖动"""
        in_panel = (self.x <= mouse_pos[0] <= self.x + self.width and
                    self.y <= mouse_pos[1] <= self.y + self.height)
        if mouse_pressed[0] and in_panel:
            if not self._dragging:
                self._dragging = True
                self._drag_start_y = mouse_pos[1]
                self._drag_start_scroll = self.scroll_y
            else:
                delta = mouse_pos[1] - self._drag_start_y
                self.scroll_y = max(0, min(self.max_scroll, self._drag_start_scroll - delta))
        else:
            self._dragging = False
    
    def draw(self, screen):
        """绘制面板"""
        # 背景
        bg_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        bg_surface.fill(self.bg_color)
        screen.blit(bg_surface, (self.x, self.y))
        # 边框
        pygame.draw.rect(screen, self.border_color, (self.x, self.y, self.width, self.height), 2)
        
        # 标题
        y_offset = 10
        if self.title and self.title_font:
            title_surf = self.title_font.render(self.title, True, self.title_color)
            screen.blit(title_surf, (self.x + 15, self.y + y_offset))
            y_offset += 30
        
        # 裁剪内容区域
        clip_rect = pygame.Rect(self.x + 5, self.y + y_offset, self.width - 20, self.height - y_offset - 10)
        old_clip = screen.get_clip()
        screen.set_clip(clip_rect)
        
        # 绘制文本行
        line_y = self.y + y_offset - self.scroll_y
        for text, color, indent, is_header in self._lines:
            if line_y > self.y + self.height:
                break
            if line_y + self._line_height > self.y + y_offset:
                if text:
                    font = self.title_font if is_header and self.title_font else self.font
                    if font:
                        text_surf = font.render(text, True, color)
                        screen.blit(text_surf, (self.x + 15 + indent, line_y))
            line_y += self._line_height
        
        screen.set_clip(old_clip)
        
        # 滚动条
        if self.max_scroll > 0:
            bar_x = self.x + self.width - 8
            bar_y = self.y + y_offset
            bar_h = self.height - y_offset - 10
            thumb_h = max(20, int(bar_h * (self.height / self.content_height)))
            thumb_y = bar_y + int((bar_h - thumb_h) * (self.scroll_y / self.max_scroll)) if self.max_scroll > 0 else bar_y
            pygame.draw.rect(screen, self.scrollbar_color, (bar_x, bar_y, 4, bar_h))
            pygame.draw.rect(screen, self.scrollbar_thumb_color, (bar_x, thumb_y, 4, thumb_h))
