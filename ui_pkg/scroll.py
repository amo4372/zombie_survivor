#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI组件模块 - 完整重写版：技能卡选择、触控按钮位置调整、半透明范围圈"""

import pygame
import math
import random
import os
import time
from config import *


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
