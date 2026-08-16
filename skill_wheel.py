#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能轮盘组件 - 支持长按拖拽选择"""

import pygame
import math
from config import WHITE, BLACK, GRAY, DARK_GRAY, GOLD, CYAN, ORANGE, PURPLE, RED, GREEN, BLUE, YELLOW, LIME, TEAL, RUST, POISON_GREEN, CRIMSON, AMBER, MUTED_GOLD

class SkillWheel:
    """技能轮盘 - 长按显示，拖拽选择技能"""
    def __init__(self, radius=180):
        self.base_radius = radius
        self.active = False
        self.center_x = 640  # BASE_WIDTH // 2
        self.center_y = 360  # BASE_HEIGHT // 2
        self.selected_skill = None
        self.skills = []
        self.skill_angles = []
        self.touch_id = None
        self.drag_pos = None
        self.just_selected = False
        self.wheel_alpha = 0
        self.target_alpha = 220

    def show(self, skills, current_skill):
        self.active = True
        self.skills = skills
        self.selected_skill = current_skill
        self.just_selected = False
        self.drag_pos = None
        self.wheel_alpha = 0
        n = len(skills)
        if n > 0:
            self.skill_angles = [i * (2 * math.pi / n) - math.pi / 2 for i in range(n)]
        else:
            self.skill_angles = []

    def hide(self):
        self.active = False
        self.just_selected = False
        self.drag_pos = None

    def handle_touch(self, touch_events, scale=1.0):
        if not self.active:
            return None

        cx = int(self.center_x * scale)
        cy = int(self.center_y * scale)
        r = int(self.base_radius * scale)

        for event in touch_events:
            if event["type"] == "down":
                self.touch_id = event.get("id", 0)
                self.drag_pos = event["pos"]
            elif event["type"] == "move" and self.touch_id is not None:
                if event.get("id", 0) == self.touch_id:
                    self.drag_pos = event["pos"]
                    # 计算选择
                    dx = self.drag_pos[0] - cx
                    dy = self.drag_pos[1] - cy
                    dist = math.hypot(dx, dy)
                    if dist > r * 0.3 and len(self.skills) > 0:
                        angle = math.atan2(dy, dx)
                        # 找到最近的技能
                        min_diff = float('inf')
                        selected = None
                        for i, skill_angle in enumerate(self.skill_angles):
                            diff = abs((angle - skill_angle + math.pi) % (2 * math.pi) - math.pi)
                            if diff < min_diff:
                                min_diff = diff
                                selected = self.skills[i]
                        if min_diff < math.pi / len(self.skills):
                            self.selected_skill = selected
            elif event["type"] == "up":
                if event.get("id", 0) == self.touch_id:
                    self.touch_id = None
                    self.just_selected = True
                    self.active = False
                    return self.selected_skill
        return None

    def handle_mouse(self, screen_mouse_pos, scale=1.0):
        """键盘鼠标模式：传入屏幕鼠标坐标，更新轮盘悬浮选中项"""
        if not self.active:
            return
        cx = int(self.center_x * scale)
        cy = int(self.center_y * scale)
        r = int(self.base_radius * scale)
        mx, my = screen_mouse_pos
        dx = mx - cx
        dy = my - cy
        dist = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)

        if dist > r * 0.3 and len(self.skills) > 0:
            min_diff = float('inf')
            selected = None
            for i, skill_angle in enumerate(self.skill_angles):
                diff = abs((angle - skill_angle + math.pi) % (2 * math.pi) - math.pi)
                if diff < min_diff:
                    min_diff = diff
                    selected = self.skills[i]
            if min_diff < math.pi / len(self.skills):
                self.selected_skill = selected

    def update(self, dt):
        if self.active and self.wheel_alpha < self.target_alpha:
            self.wheel_alpha = min(self.target_alpha, self.wheel_alpha + 800 * dt)

    def draw(self, screen, font, large_font, scale=1.0):
        if not self.active:
            return

        cx = int(self.center_x * scale)
        cy = int(self.center_y * scale)
        r = int(self.base_radius * scale)
        inner_r = int(r * 0.35)

        # 背景遮罩
        overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        overlay.fill((5, 5, 8, min(180, self.wheel_alpha)))
        screen.blit(overlay, (0, 0))

        # 轮盘背景
        wheel_surf = pygame.Surface((r * 2 + 20, r * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(wheel_surf, (30, 30, 35, self.wheel_alpha), (r + 10, r + 10), r)
        pygame.draw.circle(wheel_surf, (80, 80, 85, self.wheel_alpha), (r + 10, r + 10), r, max(2, int(3 * scale)))
        screen.blit(wheel_surf, (cx - r - 10, cy - r - 10))

        # 中心圆
        pygame.draw.circle(screen, DARK_GRAY, (cx, cy), inner_r)
        pygame.draw.circle(screen, WHITE, (cx, cy), inner_r, 2)

        # 绘制技能扇区
        n = len(self.skills)
        if n == 0:
            return

        sector_angle = 2 * math.pi / n
        for i, (skill, base_angle) in enumerate(zip(self.skills, self.skill_angles)):
            is_selected = skill == self.selected_skill

            # 扇区颜色
            color = skill.icon_color if hasattr(skill, 'icon_color') else GOLD
            if is_selected:
                color = tuple(min(255, c + 60) for c in color)
                # 高亮扇区
                highlight_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                start_a = base_angle - sector_angle / 2 + 0.05
                end_a = base_angle + sector_angle / 2 - 0.05
                points = [(r, r)]
                steps = 20
                for j in range(steps + 1):
                    a = start_a + (end_a - start_a) * j / steps
                    points.append((r + math.cos(a) * r * 0.95, r + math.sin(a) * r * 0.95))
                points.append((r, r))
                pygame.draw.polygon(highlight_surf, (*color[:3], 60), points)
                screen.blit(highlight_surf, (cx - r, cy - r))

            # 技能图标位置
            icon_dist = (r + inner_r) / 2
            icon_x = cx + math.cos(base_angle) * icon_dist
            icon_y = cy + math.sin(base_angle) * icon_dist
            icon_r = int(28 * scale)

            # 图标背景
            pygame.draw.circle(screen, color, (int(icon_x), int(icon_y)), icon_r)
            pygame.draw.circle(screen, WHITE, (int(icon_x), int(icon_y)), icon_r, 2)

            # 技能名称
            name = skill.name if hasattr(skill, 'name') else str(skill)
            name_text = font.render(name, True, WHITE)
            name_rect = name_text.get_rect(center=(int(icon_x), int(icon_y)))
            screen.blit(name_text, name_rect)

            # 等级显示
            if hasattr(skill, 'current_level') and skill.current_level > 0:
                lv_text = font.render(f"Lv.{skill.current_level}", True, GOLD)
                lv_rect = lv_text.get_rect(center=(int(icon_x), int(icon_y) + icon_r + int(12 * scale)))
                screen.blit(lv_text, lv_rect)
            elif hasattr(skill, 'current_level') and skill.current_level == 0:
                new_text = font.render("新!", True, GOLD)
                new_rect = new_text.get_rect(center=(int(icon_x), int(icon_y) + icon_r + int(12 * scale)))
                screen.blit(new_text, new_rect)

        # 中心显示当前选中技能
        if self.selected_skill:
            sel_name = self.selected_skill.name if hasattr(self.selected_skill, 'name') else str(self.selected_skill)
            sel_text = large_font.render(sel_name, True, GOLD)
            sel_rect = sel_text.get_rect(center=(cx, cy))
            screen.blit(sel_text, sel_rect)

        # 拖拽指示线
        if self.drag_pos and self.touch_id is not None:
            pygame.draw.line(screen, WHITE, (cx, cy), self.drag_pos, 2)
            pygame.draw.circle(screen, WHITE, self.drag_pos, 5)


class WeaponWheel:
    """武器轮盘 - 长按显示，拖拽选择武器"""
    def __init__(self, radius=160):
        self.base_radius = radius
        self.active = False
        self.center_x = 640
        self.center_y = 360
        self.selected_weapon_idx = 0
        self.weapons = []
        self.weapon_angles = []
        self.touch_id = None
        self.drag_pos = None
        self.just_selected = False
        self.wheel_alpha = 0

    def show(self, weapons, current_idx):
        self.active = True
        self.weapons = weapons
        self.selected_weapon_idx = current_idx
        self.just_selected = False
        self.drag_pos = None
        self.wheel_alpha = 0
        n = len(weapons)
        if n > 0:
            self.weapon_angles = [i * (2 * math.pi / n) - math.pi / 2 for i in range(n)]
        else:
            self.weapon_angles = []

    def hide(self):
        self.active = False
        self.just_selected = False
        self.drag_pos = None

    def handle_touch(self, touch_events, scale=1.0):
        if not self.active:
            return None

        cx = int(self.center_x * scale)
        cy = int(self.center_y * scale)
        r = int(self.base_radius * scale)

        for event in touch_events:
            if event["type"] == "down":
                self.touch_id = event.get("id", 0)
                self.drag_pos = event["pos"]
            elif event["type"] == "move" and self.touch_id is not None:
                if event.get("id", 0) == self.touch_id:
                    self.drag_pos = event["pos"]
                    dx = self.drag_pos[0] - cx
                    dy = self.drag_pos[1] - cy
                    dist = math.hypot(dx, dy)
                    if dist > r * 0.3 and len(self.weapons) > 0:
                        angle = math.atan2(dy, dx)
                        min_diff = float('inf')
                        selected_idx = self.selected_weapon_idx
                        for i, w_angle in enumerate(self.weapon_angles):
                            diff = abs((angle - w_angle + math.pi) % (2 * math.pi) - math.pi)
                            if diff < min_diff:
                                min_diff = diff
                                selected_idx = i
                        if min_diff < math.pi / len(self.weapons):
                            self.selected_weapon_idx = selected_idx
            elif event["type"] == "up":
                if event.get("id", 0) == self.touch_id:
                    self.touch_id = None
                    self.just_selected = True
                    self.active = False
                    return self.selected_weapon_idx
        return None

    def handle_mouse(self, screen_mouse_pos, scale=1.0):
        """键盘鼠标模式：传入屏幕鼠标坐标，更新轮盘悬浮武器索引"""
        if not self.active:
            return
        cx = int(self.center_x * scale)
        cy = int(self.center_y * scale)
        r = int(self.base_radius * scale)
        mx, my = screen_mouse_pos
        dx = mx - cx
        dy = my - cy
        dist = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)

        if dist > r * 0.3 and len(self.weapons) > 0:
            min_diff = float('inf')
            selected_idx = self.selected_weapon_idx
            for i, w_angle in enumerate(self.weapon_angles):
                diff = abs((angle - w_angle + math.pi) % (2 * math.pi) - math.pi)
                if diff < min_diff:
                    min_diff = diff
                    selected_idx = i
            if min_diff < math.pi / len(self.weapons):
                self.selected_weapon_idx = selected_idx

    def update(self, dt):
        if self.active and self.wheel_alpha < 220:
            self.wheel_alpha = min(220, self.wheel_alpha + 800 * dt)

    def draw(self, screen, font, large_font, scale=1.0):
        if not self.active:
            return

        cx = int(self.center_x * scale)
        cy = int(self.center_y * scale)
        r = int(self.base_radius * scale)
        inner_r = int(r * 0.35)

        overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        overlay.fill((5, 5, 8, min(180, self.wheel_alpha)))
        screen.blit(overlay, (0, 0))

        wheel_surf = pygame.Surface((r * 2 + 20, r * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(wheel_surf, (30, 30, 35, self.wheel_alpha), (r + 10, r + 10), r)
        pygame.draw.circle(wheel_surf, (80, 80, 85, self.wheel_alpha), (r + 10, r + 10), r, max(2, int(3 * scale)))
        screen.blit(wheel_surf, (cx - r - 10, cy - r - 10))

        pygame.draw.circle(screen, DARK_GRAY, (cx, cy), inner_r)
        pygame.draw.circle(screen, WHITE, (cx, cy), inner_r, 2)

        n = len(self.weapons)
        if n == 0:
            return

        sector_angle = 2 * math.pi / n
        for i, (weapon, base_angle) in enumerate(zip(self.weapons, self.weapon_angles)):
            is_selected = i == self.selected_weapon_idx
            color = weapon.color if hasattr(weapon, 'color') else ORANGE

            if is_selected:
                color = tuple(min(255, c + 60) for c in color)
                highlight_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                start_a = base_angle - sector_angle / 2 + 0.05
                end_a = base_angle + sector_angle / 2 - 0.05
                points = [(r, r)]
                steps = 20
                for j in range(steps + 1):
                    a = start_a + (end_a - start_a) * j / steps
                    points.append((r + math.cos(a) * r * 0.95, r + math.sin(a) * r * 0.95))
                points.append((r, r))
                pygame.draw.polygon(highlight_surf, (*color[:3], 60), points)
                screen.blit(highlight_surf, (cx - r, cy - r))

            icon_dist = (r + inner_r) / 2
            icon_x = cx + math.cos(base_angle) * icon_dist
            icon_y = cy + math.sin(base_angle) * icon_dist
            icon_r = int(28 * scale)

            pygame.draw.circle(screen, color, (int(icon_x), int(icon_y)), icon_r)
            pygame.draw.circle(screen, WHITE, (int(icon_x), int(icon_y)), icon_r, 2)

            name = weapon.name if hasattr(weapon, 'name') else f"武器{i+1}"
            name_text = font.render(name, True, WHITE)
            name_rect = name_text.get_rect(center=(int(icon_x), int(icon_y)))
            screen.blit(name_text, name_rect)

            if hasattr(weapon, 'level'):
                lv_text = font.render(f"Lv.{weapon.level}", True, GOLD)
                lv_rect = lv_text.get_rect(center=(int(icon_x), int(icon_y) + icon_r + int(12 * scale)))
                screen.blit(lv_text, lv_rect)

        if self.weapons and 0 <= self.selected_weapon_idx < len(self.weapons):
            sel_name = self.weapons[self.selected_weapon_idx].name
            sel_text = large_font.render(sel_name, True, GOLD)
            sel_rect = sel_text.get_rect(center=(cx, cy))
            screen.blit(sel_text, sel_rect)

        if self.drag_pos and self.touch_id is not None:
            pygame.draw.line(screen, WHITE, (cx, cy), self.drag_pos, 2)
            pygame.draw.circle(screen, WHITE, self.drag_pos, 5)
