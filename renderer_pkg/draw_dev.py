# -*- coding: utf-8 -*-
"""DevMixin - 由 renderer.py 自动拆分，逻辑等价"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染系统模块 - 黑暗色调版：技能卡选择、防爆套装动画、半透明范围圈"""

import pygame
import mod_loader
import math
import random
from config import *
from buff import BuffType
from codex import codex_unlock_manager
from weapons import Weapon

class DevMixin:
    def _dev_confirm(self, g):
        """确认开发者密码（触控/鼠标按钮兜底，键盘用回车）"""
        if g.dev_input_str == g._DEV_PASSWORD:
            g.dev_mode = True
            g.dev_input_active = False
            g.dev_input_str = ""
            g._blur_dev_input()
            g.update_status_text = "开发者模式已开启！局内按 F9 键打开调试面板"
        else:
            g.dev_input_active = False
            g.dev_input_str = ""
            g._blur_dev_input()
            g.update_status_text = "密码错误，请重试（连点版本号重新输入）"

    def _draw_dev_password(self):
        """绘制开发者密码文本输入框：点击（触控/鼠标/键盘）聚焦后接受系统输入法输入"""
        g = self.game
        scale = g.scale
        sw = g.scaled_width
        sh = g.scaled_height
        # 半透明遮罩
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        self.screen.blit(ov, (0, 0))
        # 文本输入框
        box_w, box_h = int(420 * scale), int(56 * scale)
        box_x = sw // 2 - box_w // 2
        box_y = int(140 * scale)
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        focused = g.dev_input_focused
        pygame.draw.rect(self.screen, (40, 40, 52), box_rect, border_radius=6)
        border_col = (120, 210, 130) if focused else (100, 100, 130)
        pygame.draw.rect(self.screen, border_col, box_rect, 3 if focused else 2, border_radius=6)
        title = g.font.render("开发者密码", True, (240, 220, 120))
        self.screen.blit(title, (sw // 2 - title.get_width() // 2, int(92 * scale)))
        # 密码文本 + 光标（聚焦时闪烁）
        pw_txt = g.font.render("*" * len(g.dev_input_str), True, (255, 255, 255))
        self.screen.blit(pw_txt, (box_x + 18, box_y + box_h // 2 - pw_txt.get_height() // 2))
        if focused:
            cx = box_x + 18 + pw_txt.get_width() + 6
            if int(pygame.time.get_ticks() / 500) % 2 == 0:
                pygame.draw.line(self.screen, (255, 255, 255),
                                 (cx, box_y + 14), (cx, box_y + box_h - 14), 2)
        # 提示文字
        if focused:
            hint = g.font_small.render("系统输入法中… 回车确认 · 退格删除 · ESC 失焦", True, (180, 225, 185))
        else:
            hint = g.font_small.render("点击输入框唤起系统输入法 · 回车/空格聚焦 · ESC 关闭", True, GRAY)
        self.screen.blit(hint, (sw // 2 - hint.get_width() // 2, box_y + box_h + 10))
        status = g.font_small.render(g.update_status_text or "", True, (255, 180, 120))
        self.screen.blit(status, (sw // 2 - status.get_width() // 2, box_y + box_h + 44))

        # 底部操作按钮：确认 / 取消（触控兜底；键盘可用回车确认）
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        btn_w, btn_h = int(150 * scale), int(42 * scale)
        btn_y = box_y + box_h + 86
        ok_rect = pygame.Rect(sw // 2 - btn_w - 10, btn_y, btn_w, btn_h)
        cancel_rect = pygame.Rect(sw // 2 + 10, btn_y, btn_w, btn_h)
        # 确认
        hover = ok_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, (60, 130, 70) if not hover else (85, 165, 95), ok_rect, border_radius=5)
        pygame.draw.rect(self.screen, (160, 160, 180), ok_rect, 1, border_radius=5)
        t = g.font.render("确认", True, (255, 255, 255))
        self.screen.blit(t, (ok_rect.centerx - t.get_width() // 2, ok_rect.centery - t.get_height() // 2))
        # 取消
        hover = cancel_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, (120, 70, 70) if not hover else (150, 90, 90), cancel_rect, border_radius=5)
        pygame.draw.rect(self.screen, (160, 160, 180), cancel_rect, 1, border_radius=5)
        t = g.font.render("取消", True, (255, 255, 255))
        self.screen.blit(t, (cancel_rect.centerx - t.get_width() // 2, cancel_rect.centery - t.get_height() // 2))

        # ===== 点击交互（顺序：按钮 → 输入框聚焦 → 外部失焦）=====
        # 1) 按钮点击（鼠标按下 / 触控抬起）
        if ok_rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            self._dev_confirm(g)
        for te in g.touch_events:
            if te["type"] == "up" and ok_rect.collidepoint(te["pos"]):
                self._dev_confirm(g)
        if cancel_rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            g.dev_input_active = False
            g.dev_input_str = ""
            g._blur_dev_input()
        for te in g.touch_events:
            if te["type"] == "up" and cancel_rect.collidepoint(te["pos"]):
                g.dev_input_active = False
                g.dev_input_str = ""
                g._blur_dev_input()
        # 2) 点击输入框 → 聚焦（接受系统输入法输入）
        if box_rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            g._focus_dev_input()
        for te in g.touch_events:
            if te["type"] == "up" and box_rect.collidepoint(te["pos"]):
                g._focus_dev_input()
        # 3) 点击输入框/按钮之外的区域 → 失焦（关闭系统输入法）
        outside = not (box_rect.collidepoint(mouse_pos) or ok_rect.collidepoint(mouse_pos)
                       or cancel_rect.collidepoint(mouse_pos))
        if outside and mouse_pressed[0]:
            g._blur_dev_input()
        for te in g.touch_events:
            if te["type"] == "up" and not (box_rect.collidepoint(te["pos"]) or ok_rect.collidepoint(te["pos"])
                                           or cancel_rect.collidepoint(te["pos"])):
                g._blur_dev_input()

    def _draw_dev_panel(self):
        """绘制局内开发者调试面板"""
        g = self.game
        scale = g.scale
        sw = g.scaled_width
        ov = pygame.Surface((sw, g.scaled_height), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 120))
        self.screen.blit(ov, (0, 0))
        head = g.font.render("开发者调试面板", True, (60, 220, 60))
        self.screen.blit(head, (sw - 210, 40))
        tip = g.font_small.render("F9 键 关闭面板 · 无敌/倍率等", True, (200, 200, 210))
        self.screen.blit(tip, (sw - 250, 66))
        bx, by = sw - 190, 90
        for btn in g.dev_buttons:
            btn.base_x = bx
            btn.base_y = by
            # 注意：bx/by 已是屏幕像素坐标，Button 内部不再缩放（传 scale=1.0）
            btn.draw(self.screen, g.font_large, 1.0)
            by += 42
