#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对话系统模块 - 修复交互问题"""

import pygame
from config import *

class DialogueSystem:
    def __init__(self):
        self.active = False
        self.current_dialogue = []
        self.current_index = 0
        self.speaker = ""
        self.text = ""
        self.text_timer = 0
        self.text_speed = 0.03
        self.displayed_text = ""
        self.on_complete = None
        self.choices = []
        self.selected_choice = 0
        self.dialog_rect = None

    def start_dialogue(self, dialogues, on_complete=None):
        self.active = True
        self.current_dialogue = dialogues
        self.current_index = 0
        self.on_complete = on_complete
        self._load_current()

    def _load_current(self):
        if self.current_index < len(self.current_dialogue):
            entry = self.current_dialogue[self.current_index]
            self.speaker = entry.get("speaker", "")
            self.text = entry.get("text", "")
            self.choices = entry.get("choices", [])
            self.selected_choice = 0
            self.displayed_text = ""
            self.text_timer = 0
        else:
            self.active = False
            if self.on_complete:
                self.on_complete()

    def update(self, dt):
        if not self.active:
            return
        if len(self.displayed_text) < len(self.text):
            self.text_timer += dt
            while self.text_timer >= self.text_speed and len(self.displayed_text) < len(self.text):
                self.text_timer -= self.text_speed
                self.displayed_text += self.text[len(self.displayed_text)]

    def advance(self):
        """推进对话。"""
        if len(self.displayed_text) < len(self.text):
            self.displayed_text = self.text
            return
        if self.choices:
            return
        self.current_index += 1
        self._load_current()

    def select_choice(self, choice_idx):
        if 0 <= choice_idx < len(self.choices):
            choice = self.choices[choice_idx]
            self.current_index += 1
            self._load_current()
            return choice.get("effect", None)
        return None

    # ==================== v2.5.6 选项布局（多选项自动换行）====================
    def get_choice_layout(self, font, screen_width, screen_height):
        """计算选项的排版（返回 [(index, rect, text)]）

        v2.5.5 之前选项是固定单行横排（每项 280px），选项一多就会超出屏幕
        （故事结局选项增加到 5~6 个后必然溢出、点不到）。
        这里改成「按宽度自动换行 + 居中」，与 draw() / 点击判定共用同一份布局。
        """
        try:
            if not self.choices:
                return []
            _items = []
            for i, ch in enumerate(self.choices):
                _t = f"{i+1}. {ch['text']}"
                _w = font.size(_t)[0] + 16
                _items.append((i, _t, _w))
            _dlg_h = min(220, screen_height // 3)
            _dlg_rect = pygame.Rect(20, screen_height - _dlg_h - 10,
                                    screen_width - 40, _dlg_h)
            _max_w = max(120, _dlg_rect.width - 40)
            _rows = []
            _cur = []
            _cur_w = 0
            for it in _items:
                if _cur and (_cur_w + it[2] > _max_w):
                    _rows.append(_cur)
                    _cur = []
                    _cur_w = 0
                _cur.append(it)
                _cur_w += it[2] + 8
            if _cur:
                _rows.append(_cur)
            _line_h = 26
            _y = _dlg_rect.y + _dlg_rect.height - 14 - _line_h * len(_rows)
            if _y < _dlg_rect.y + 50:
                _y = _dlg_rect.y + 50
            _out = []
            for _row in _rows:
                _row_w = sum(it[2] for it in _row)
                _x = _dlg_rect.x + 20 + max(0, (_dlg_rect.width - 40 - _row_w) // 2)
                for (i, t, w) in _row:
                    _out.append((i, pygame.Rect(_x, _y, w, _line_h), t))
                    _x += w + 8
                _y += _line_h
            return _out
        except Exception:
            return []

    def draw(self, screen, font, large_font, screen_width, screen_height):
        if not self.active:
            return

        dialog_height = min(220, screen_height // 3)
        dialog_rect = pygame.Rect(20, screen_height - dialog_height - 10, 
                                  screen_width - 40, dialog_height)
        self.dialog_rect = dialog_rect

        overlay = pygame.Surface((dialog_rect.width, dialog_rect.height), pygame.SRCALPHA)
        overlay.fill((*CHARCOAL[:3], 240))
        screen.blit(overlay, (dialog_rect.x, dialog_rect.y))
        pygame.draw.rect(screen, WHITE, dialog_rect, 3)
        pygame.draw.rect(screen, YELLOW, dialog_rect, 1)

        if self.speaker:
            speaker_text = large_font.render(self.speaker, True, YELLOW)
            screen.blit(speaker_text, (dialog_rect.x + 15, dialog_rect.y + 8))
            pygame.draw.line(screen, YELLOW, 
                           (dialog_rect.x + 15, dialog_rect.y + 8 + speaker_text.get_height() + 2),
                           (dialog_rect.x + 15 + speaker_text.get_width(), dialog_rect.y + 8 + speaker_text.get_height() + 2), 2)

        text_y = dialog_rect.y + 50
        words = self.displayed_text
        lines = []
        current_line = ""
        for char in words:
            test_line = current_line + char
            if font.size(test_line)[0] > dialog_rect.width - 30:
                lines.append(current_line)
                current_line = char
            else:
                current_line += char
        lines.append(current_line)

        for i, line in enumerate(lines[:6]):
            text_surf = font.render(line, True, WHITE)
            screen.blit(text_surf, (dialog_rect.x + 15, text_y + i * 24))

        if self.choices and len(self.displayed_text) >= len(self.text):
            # v2.5.6：选项自动换行（与点击判定共用 get_choice_layout）
            _layout = self.get_choice_layout(font, screen_width, screen_height)
            if _layout:
                _rows = max(1, len(_layout) // max(1, len(self.choices)))
                _bg_top = min(r.y for _, r, _ in _layout) - 6
                choice_bg = pygame.Rect(dialog_rect.x + 10, _bg_top,
                                        dialog_rect.width - 20,
                                        dialog_rect.bottom - 10 - _bg_top)
                pygame.draw.rect(screen, (50, 50, 50), choice_bg, border_radius=5)
            for i, _rect, _txt in _layout:
                color = YELLOW if i == self.selected_choice else WHITE
                choice_text = font.render(_txt, True, color)
                screen.blit(choice_text, (_rect.x + 8, _rect.y + 2))
        elif len(self.displayed_text) >= len(self.text) and not self.choices:
            hint_text = "【点击屏幕或按空格键继续】"
            hint = font.render(hint_text, True, CYAN)
            hint_x = dialog_rect.centerx - hint.get_width() // 2
            hint_y = dialog_rect.bottom - 35
            hint_bg = pygame.Rect(hint_x - 10, hint_y - 5, hint.get_width() + 20, hint.get_height() + 10)
            pygame.draw.rect(screen, (0, 0, 0, 180), hint_bg, border_radius=5)
            screen.blit(hint, (hint_x, hint_y))
            if pygame.time.get_ticks() % 1000 < 500:
                pygame.draw.rect(screen, CYAN, hint_bg, 2, border_radius=5)
