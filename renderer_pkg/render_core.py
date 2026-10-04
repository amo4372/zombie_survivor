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

class RenderCore:

    def __init__(self, screen, game):
        self.screen = screen
        self.game = game
        self._touch_clicks = {}  # 符文界面等：跨帧触控按下状态（key -> bool）

    def _clicked(self, rect, mouse_pos, mouse_pressed, touch_events, key):
        """统一鼠标+触控点击检测（带跨帧触控状态）。
        rect 为已缩放的屏幕坐标矩形。
        鼠标：按下且在 rect 内即触发（保持原有即时反馈）。
        触控：down 在 rect 内记录，手指抬起仍在 rect 内时触发。"""
        if rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            return True
        if touch_events:
            for e in touch_events:
                if e["type"] == "down" and rect.collidepoint(e["pos"]):
                    self._touch_clicks[key] = True
                elif e["type"] == "up":
                    was = self._touch_clicks.pop(key, False)
                    if was and rect.collidepoint(e["pos"]):
                        return True
        return False

    def render(self):
        state = self.game.state

        if state == GameState.MENU:
            self._draw_menu()
        elif state == GameState.SETTINGS:
            self._draw_settings()
        elif state == GameState.HUD_EDIT:
            self._draw_hud_edit()
        elif state == GameState.PLAY_SELECT:
            self._draw_play_select()
        elif state == GameState.MULTIPLAYER_SELECT:
            self._draw_multiplayer_select()
        elif state == GameState.NET_MULTIPLAYER:
            self._draw_net_multiplayer()
        elif state == GameState.NET_WAIT:
            self._draw_net_wait()
        elif state == GameState.NET_CLIENT_PLAY:
            self._draw_net_client()
        elif state == GameState.TUTORIAL:
            self._draw_tutorial()
        elif state == GameState.PLAYING:
            self._draw_playing()
            if getattr(self.game, 'dev_mode', False) and getattr(self.game, 'dev_panel_open', False):
                self._draw_dev_panel()
        elif state == GameState.PAUSED:
            self._draw_playing()
            self._draw_pause()
        elif state == GameState.SKILL_SELECT:
            self._draw_playing()
            self._draw_skill_select()
        elif state == GameState.DIALOGUE:
            self._draw_playing()
            self._draw_dialogue()
        elif state == GameState.GAME_OVER:
            self._draw_game_over()
        elif state == GameState.VICTORY:
            self._draw_victory()
        elif state == GameState.ENDING:
            self._draw_ending()
        elif state == GameState.RECORDS:
            self._draw_records()
        elif state == GameState.ACHIEVEMENTS:
            self._draw_achievements()
        elif state == GameState.MODE_SELECT:
            self._draw_mode_select()
        elif state == GameState.DIFFICULTY_SELECT:
            self._draw_difficulty_select()
        elif state == GameState.EQUIP_SELECT:
            self._draw_equip_select()
        elif state == GameState.STORY_ARCHIVE:
            self._draw_story_archive()
        elif state == GameState.CODEX:
            self._draw_codex()
        elif state == GameState.SKILL_TREE:
            self._draw_playing()
            self._draw_skill_tree()
        elif state == GameState.TEXT_VIEWER:
            self._draw_playing()
            self._draw_text_viewer()
        elif state == GameState.MOD_MANAGER:
            self._draw_mod_manager()
        elif state == GameState.UPDATE:
            self._draw_update()
        elif state == GameState.UPDATE_NOTES:
            self._draw_update_notes()
        elif state == GameState.RUNE_VIEW:
            self._draw_playing()
            self._draw_rune_view()

        pygame.display.flip()

    def _paint_weapon_icon(self, entry_key, x, y, w, h):
        """程序化绘制武器图标（按武器类型画剪影）"""
        cx, cy = x + w // 2, y + h // 2
        key_u = entry_key.upper()
        body = (75, 75, 88)
        if key_u in ("KNIFE", "BAT", "CHAINSAW", "SCYTHE"):
            if key_u == "KNIFE":
                pygame.draw.polygon(self.screen, (200, 205, 215),
                                    [(cx - 6, cy - 6), (cx + 26, cy - 6), (cx + 32, cy + 2), (cx - 10, cy + 2)])
                pygame.draw.rect(self.screen, (130, 95, 60), (cx - 26, cy - 4, 24, 10))
            elif key_u == "SCYTHE":
                pygame.draw.arc(self.screen, (220, 225, 235), (cx - 30, cy - 26, 66, 56), 0, 3.3, 9)
                pygame.draw.line(self.screen, (145, 115, 80), (cx + 28, cy + 2), (cx - 26, cy + 42), 8)
                pygame.draw.circle(self.screen, (160, 130, 90), (cx + 28, cy + 2), 8)
            elif key_u == "CHAINSAW":
                pygame.draw.rect(self.screen, (120, 120, 132), (cx - 30, cy - 4, 60, 14))
                for i in range(-26, 30, 9):
                    pygame.draw.circle(self.screen, (90, 90, 100), (cx + i, cy + 3), 3)
                pygame.draw.rect(self.screen, (150, 80, 60), (cx - 4, cy + 10, 24, 16))
            else:
                pygame.draw.line(self.screen, (150, 120, 70), (cx - 30, cy + 2), (cx + 30, cy + 2), 10)
                pygame.draw.rect(self.screen, (120, 90, 60), (cx - 6, cy + 2, 22, 12))
        else:
            # 枪械：枪身+枪管+弹匣+瞄准
            pygame.draw.rect(self.screen, body, (cx - 20, cy - 6, 54, 14))
            pygame.draw.rect(self.screen, body, (cx + 28, cy - 3, 20, 8))
            pygame.draw.rect(self.screen, (70, 70, 80), (cx - 16, cy + 8, 24, 14))
            pygame.draw.rect(self.screen, (200, 60, 60), (cx - 30, cy - 3, 7, 7))

    def _wrap_text(self, text, max_width, font):
        """简单的文本换行（按字符分割，支持中文）"""
        lines = []
        current_line = ""
        for char in text:
            if char == '\n':
                lines.append(current_line)
                current_line = ""
                continue
            test_line = current_line + char
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        return lines

    def _rune_level_effect_text(self, rt, stacks):
        """返回符文当前等级对应的效果描述文本"""
        from runes import RUNE_CONFIG
        from config import RuneType
        cfg = RUNE_CONFIG[rt]
        if rt == RuneType.POWER:
            return f"所有伤害 +{int(15 * stacks)}%"
        if rt == RuneType.VITALITY:
            return f"最大生命值 +{30 * stacks}"
        if rt == RuneType.SWIFTNESS:
            return f"移动速度 +{int(10 * stacks)}%"
        if rt == RuneType.CRITICAL:
            return f"暴击率 +{int(10 * stacks)}%"
        if rt == RuneType.VAMPIRE:
            return f"攻击回复 {int(5 * stacks)}% 生命"
        if rt == RuneType.GUARDIAN:
            return f"护甲 +{10 * stacks}"
        if rt == RuneType.FRENZY:
            return f"攻击速度 +{int(15 * stacks)}%"
        if rt == RuneType.REGEN:
            return f"每秒回复 {2 * stacks} 生命"
        if rt == RuneType.SHADOW:
            return f"暴击伤害 +{int(50 * stacks)}%"
        if rt == RuneType.LUCK:
            return f"掉落率 +{int(20 * stacks)}%"
        if rt == RuneType.TITAN:
            return f"体型 +{int(15 * stacks)}%  近战范围+20%  伤害+10%"
        if rt == RuneType.FLAME:
            return f"攻击灼烧敌人"
        if rt == RuneType.FROST:
            return f"攻击减速敌人"
        if rt == RuneType.POISON:
            return f"攻击使敌人中毒"
        if rt == RuneType.THUNDER:
            return f"攻击触发连锁闪电"
        return ""
