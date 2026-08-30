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
            choice_y = dialog_rect.y + dialog_rect.height - 45
            choice_bg = pygame.Rect(dialog_rect.x + 10, choice_y - 5, dialog_rect.width - 20, 40)
            pygame.draw.rect(screen, (50, 50, 50), choice_bg, border_radius=5)
            for i, choice in enumerate(self.choices):
                color = YELLOW if i == self.selected_choice else WHITE
                choice_text = font.render(f"{i+1}. {choice['text']}", True, color)
                screen.blit(choice_text, (dialog_rect.x + 20 + i * min(280, screen_width // 4), choice_y))
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
