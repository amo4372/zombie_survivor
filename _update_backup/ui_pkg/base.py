#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI组件模块 - 完整重写版：技能卡选择、触控按钮位置调整、半透明范围圈"""

import pygame
import math
import random
import os
import time
from config import *


class SafeFont:
    """字体渲染兜底：空文本/渲染异常时返回透明 surface，避免 pygame 'Text has zero width' 崩溃。
    用于 changelog 含空行等场景，render('') 不再抛 pygame.error。"""
    def __init__(self, font):
        self._font = font

    def render(self, text, antialias=True, color=(255, 255, 255), bgcolor=None):
        if text is None or (isinstance(text, str) and not text.strip()):
            return pygame.Surface((1, 1), pygame.SRCALPHA)
        try:
            return self._font.render(text, antialias, color, bgcolor)
        except pygame.error:
            return pygame.Surface((1, 1), pygame.SRCALPHA)

    def __getattr__(self, name):
        return getattr(self._font, name)


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
        cls._fonts[key] = SafeFont(font)
        return cls._fonts[key]

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
        self.touch_pressed = False  # 触控按下状态（跨帧保持，独立于鼠标悬停）
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
        if touch_events:
            for event in touch_events:
                if event["type"] == "down":
                    if scaled_rect.collidepoint(event["pos"]):
                        self.touch_pressed = True
                elif event["type"] == "up":
                    if self.touch_pressed:
                        self.touch_pressed = False
                        if scaled_rect.collidepoint(event["pos"]):
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
            # 仅重置鼠标按下态；触控按下用独立 touch_pressed 保持，
            # 不会被此处清掉（纯触控设备鼠标光标不在按钮上，原逻辑会吞掉触控点击）
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
        if self.pressed or self.touch_pressed:
            color = tuple(max(0, c - 40) for c in color)
        pygame.draw.rect(screen, color, scaled_rect, border_radius=self.border_radius)
        pygame.draw.rect(screen, self.text_color, scaled_rect, 2, border_radius=self.border_radius)
        text_surf = font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=scaled_rect.center)
        screen.blit(text_surf, text_rect)
