# -*- coding: utf-8 -*-
"""InputMixin - 由 game.py 自动拆分，逻辑等价"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主游戏逻辑模块 - 重写版：技能卡系统、尸潮、钩爪新逻辑、触控修复、黑暗色调"""

import pygame
import random
import math
import sys
import json
import os
import traceback
import datetime
import time
import socket

from config import *
from assets import AssetManager, SOUND_MAP, MUSIC_MAP, MAP_MUSIC_MAP
from records import GameRecords, GameSession
from codex import MONSTER_CODEX, WEAPON_CODEX, MONSTER_CATEGORIES, WEAPON_CATEGORIES, codex_unlock_manager
from skill_tree_view import SkillTreeRenderer, skill_tree_unlock_manager
from mod_loader import (load_all_mods, trigger_hook, HOOK_GAME_START, HOOK_GAME_TICK, HOOK_ENEMY_SPAWN, HOOK_ENEMY_DEATH, HOOK_PLAYER_DAMAGE, HOOK_KEYDOWN, HOOK_RENDER_HUD, HOOK_GAME_OVER, HOOK_WAVE_COMPLETE, HOOK_TOUCH_EVENT, HOOK_PLAYER_MOVE, HOOK_PLAYER_FIRE, HOOK_SKILL_USE, HOOK_ENEMY_UPDATE, HOOK_DAMAGE_DEALT)
from logger import GameLogger
import updater

# ============ 存档加密工具（内联，避免加密打包后外部依赖） ============
_SAVE_CRYPT_KEY = b"Z0mb13_Surv1v0r_Save_Crypt_2024!@#$%"
_SAVE_CRYPT_SALT = b"ZombieSaveSalt_2024"

def _save_derive_key(password: bytes, salt: bytes = _SAVE_CRYPT_SALT, iterations: int = 5000) -> bytes:
    """从密码派生密钥"""
    import hashlib
    return hashlib.pbkdf2_hmac('sha256', password, salt, iterations, dklen=32)

def _save_xor_crypt(data: bytes, key: bytes) -> bytes:
    """XOR 加密/解密"""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))

def _save_encrypt(data: bytes, key: bytes = _SAVE_CRYPT_KEY) -> bytes:
    """多层加密存档：XOR + 字节反转 + base64 + XOR"""
    import base64
    import hashlib
    # 第一层：XOR
    layer1 = _save_xor_crypt(data, key)
    # 第二层：字节反转
    layer2 = layer1[::-1]
    # 第三层：base64
    layer3 = base64.b64encode(layer2)
    # 第四层：再次XOR（派生密钥）
    key2 = hashlib.sha256(key + b"save_layer2").digest()
    layer4 = _save_xor_crypt(layer3, key2)
    return layer4

def _save_decrypt(data: bytes, key: bytes = _SAVE_CRYPT_KEY) -> bytes:
    """多层解密存档"""
    import base64
    import hashlib
    # 第四层反向：XOR
    key2 = hashlib.sha256(key + b"save_layer2").digest()
    layer4 = _save_xor_crypt(data, key2)
    # 第三层反向：base64解码
    layer3 = base64.b64decode(layer4)
    # 第二层反向：字节反转
    layer2 = layer3[::-1]
    # 第一层反向：XOR
    layer1 = _save_xor_crypt(layer2, key)
    return layer1
from ui import (FontManager, Button, VirtualJoystick, TouchButton, DamageNumber, 
                FloatingText, SlashArc, ParticleSystem, AimButton, SkillSelector, SkillCaster, 
                SkillCardSelector, WeaponSwitchButton, draw_dashed_line)
from skills import SkillTree
from weapons import Weapon, Projectile
from entities import Player, Enemy, ExpOrb, RiotGear
from buff import BuffType
from world import GameWorld, HordeManager, SpecialItem, TextItem
from lighting import LightingSystem
from runes import RuneManager, random_rune, RUNE_CONFIG, RuneType
import mod_loader
from dialogue import DialogueSystem
from skill_wheel import SkillWheel, WeaponWheel
from renderer import Camera, Renderer

# 向 Mod 钩子系统注入已加载的常用类引用（mod 回调可直接使用 FloatingText 等）
mod_loader.mod_hooks._global_classes = {
    "FloatingText": FloatingText,
    "WeaponType": WeaponType,
    "EnemyType": EnemyType,
    "BuffType": BuffType,
    "SkillType": SkillType,
    "ParticleSystem": ParticleSystem,
    "Player": Player,
    "Enemy": Enemy,
}

class Config:
    def __init__(self):
        self.control_mode = ControlMode.KEYBOARD
        self.game_mode = GameMode.TIMED
        self.sound_volume = 0.7
        self.music_volume = 0.5
        self.difficulty = "普通"
        self.show_damage_numbers = True
        self.screen_shake = True
        self.use_external_assets = True  # 是否使用外部图片资源
        self.render_buff_effects = True  # 是否渲染buff等额外效果
        self.graphics_quality = "balanced"  # performance / balanced / quality
        self.enable_logging = True      # 游戏日志开关（用户可选）
        self.update_auto_check = True   # 启动时自动检查更新并弹窗提示（用户可选）
        self.hud_layout = {}  # HUD触控按钮自定义布局：{控件名: [base_x, base_y]}（单机模式）
        self.mp_p1_layout = {}  # 双人模式 P1 触控布局（独立于单机）
        self.p2_hud_layout = {}  # 双人模式 P2 触控布局
        self.hud_layout_version = 0  # HUD 布局方案版本：v2.0.6 起=2（双人默认布局大改，旧布局需重置）
        self.config_file = "config.json"
        self.load()
        # v2.0.6 布局版本升级：旧版双人布局（v2.0.2 前全屏坐标）会堆叠/缺摇杆，重置为默认并持久化
        if self.hud_layout_version < 2:
            if self.mp_p1_layout or self.p2_hud_layout:
                logger.info("检测到旧版双人 HUD 布局，已重置为 v2.0.6 默认（避免按钮堆叠/缺摇杆）")
            self.mp_p1_layout = {}
            self.p2_hud_layout = {}
            self.hud_layout_version = 2
            try:
                self.save()
            except Exception:
                pass

    def load(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.control_mode = ControlMode[data.get("control_mode", "KEYBOARD")]
                    self.game_mode = GameMode[data.get("game_mode", "TIMED")]
                    self.sound_volume = data.get("sound_volume", 0.7)
                    self.music_volume = data.get("music_volume", 0.5)
                    self.difficulty = data.get("difficulty", "普通")
                    self.show_damage_numbers = data.get("show_damage_numbers", True)
                    self.screen_shake = data.get("screen_shake", True)
                    self.use_external_assets = data.get("use_external_assets", True)
                    self.render_buff_effects = data.get("render_buff_effects", True)
                    self.graphics_quality = data.get("graphics_quality", "balanced")
                    self.enable_logging = data.get("enable_logging", True)
                    self.update_auto_check = data.get("update_auto_check", True)
                    _hl = data.get("hud_layout", {})
                    if isinstance(_hl, dict):
                        self.hud_layout = {k: list(v) for k, v in _hl.items() if isinstance(v, (list, tuple)) and len(v) == 2}
                    _p1 = data.get("mp_p1_layout", {})
                    if isinstance(_p1, dict):
                        self.mp_p1_layout = {k: list(v) for k, v in _p1.items() if isinstance(v, (list, tuple)) and len(v) == 2}
                    _p2 = data.get("p2_hud_layout", {})
                    if isinstance(_p2, dict):
                        self.p2_hud_layout = {k: list(v) for k, v in _p2.items() if isinstance(v, (list, tuple)) and len(v) == 2}
                    self.hud_layout_version = data.get("hud_layout_version", 0)
        except Exception as e:
            logger.error(f"配置加载失败: {e}")

    def save(self):
        data = {
            "control_mode": self.control_mode.name,
            "game_mode": self.game_mode.name,
            "sound_volume": self.sound_volume,
            "music_volume": self.music_volume,
            "difficulty": self.difficulty,
            "show_damage_numbers": self.show_damage_numbers,
            "screen_shake": self.screen_shake,
            "use_external_assets": self.use_external_assets,
            "render_buff_effects": self.render_buff_effects,
            "graphics_quality": self.graphics_quality,
            "enable_logging": self.enable_logging,
            "update_auto_check": self.update_auto_check,
            "hud_layout": self.hud_layout,
            "mp_p1_layout": self.mp_p1_layout,
            "p2_hud_layout": self.p2_hud_layout,
            "hud_layout_version": getattr(self, 'hud_layout_version', 2),
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"配置保存失败: {e}")

logger = GameLogger()

class InputMixin:
    def handle_events(self):
        # ===== 统一事件收集（所有状态共享，避免重复消费导致事件丢失）=====
        all_events = pygame.event.get()
        self.touch_events = []
        # 预处理：将所有 FINGER 事件和鼠标事件统一转换为 touch_events（dict 格式）
        # Windows 触控一体机（班班通等）的触摸会被 SDL 同时合成 FINGER 与鼠标事件，
        # 先收集本帧 FINGER 事件位置用于去重，避免同一根手指被当成两个事件源反复抢绑控件。
        _finger_down_pos = set()
        _finger_up_pos = set()
        _has_finger_move = False
        for event in all_events:
            if event.type == pygame.FINGERDOWN:
                _finger_down_pos.add((event.x * self.scaled_width, event.y * self.scaled_height))
            elif event.type == pygame.FINGERUP:
                _finger_up_pos.add((event.x * self.scaled_width, event.y * self.scaled_height))
            elif event.type == pygame.FINGERMOTION:
                _has_finger_move = True
        _near_finger = lambda p, s: any(math.hypot(p[0] - q[0], p[1] - q[1]) <= 24 for q in s)
        for event in all_events:
            if event.type == pygame.FINGERDOWN:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self._active_touch_ids.add(event.finger_id)
                self._active_touch_pos[event.finger_id] = (x, y)
                self._active_touch_last[event.finger_id] = time.time()
                self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.FINGERUP:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self._active_touch_ids.discard(event.finger_id)
                self._active_touch_pos.pop(event.finger_id, None)
                self._active_touch_last.pop(event.finger_id, None)
                self.touch_events.append({"type": "up", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.FINGERMOTION:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                if event.finger_id in self._active_touch_ids:
                    self._active_touch_pos[event.finger_id] = (x, y)
                    self._active_touch_last[event.finger_id] = time.time()
                self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if _near_finger(event.pos, _finger_down_pos):
                    continue  # 同一手指的鼠标合成事件，去重
                self._active_touch_ids.add(-1)
                self._active_touch_pos[-1] = event.pos
                self._active_touch_last[-1] = time.time()
                self.touch_events.append({"type": "down", "pos": event.pos, "id": -1})
            elif event.type == pygame.MOUSEBUTTONUP:
                if _near_finger(event.pos, _finger_up_pos):
                    continue  # 同一手指的鼠标合成事件，去重
                self._active_touch_ids.discard(-1)
                self._active_touch_pos.pop(-1, None)
                self._active_touch_last.pop(-1, None)
                self.touch_events.append({"type": "up", "pos": event.pos, "id": -1})
            elif event.type == pygame.MOUSEMOTION:
                if _has_finger_move:
                    continue  # 手指移动时跳过鼠标合成移动
                if -1 in self._active_touch_ids:
                    self._active_touch_last[-1] = time.time()
                self.touch_events.append({"type": "move", "pos": event.pos, "id": -1})

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        # 开发者模式：密码输入 / 局内面板开关
        self._handle_dev_keys(all_events)

        # 技能卡选择界面
        if self.state == GameState.SKILL_SELECT:
            _up_pl = self.player2 if getattr(self, 'pending_upgrade_for', None) == "P2" and self.player2 else self.player
            for event in all_events:
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self.is_android:
                        self.screen = pygame.display.set_mode(
                            (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self._update_scale()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1 and len(_up_pl.skill_cards) > 0:
                        self._select_skill_card(0)
                    elif event.key == pygame.K_2 and len(_up_pl.skill_cards) > 1:
                        self._select_skill_card(1)
                    elif event.key == pygame.K_3 and len(_up_pl.skill_cards) > 2:
                        self._select_skill_card(2)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        selected = self.skill_card_selector.handle_input(
                            event.pos, (1, 0, 0), [], self.scale
                        )
                        if selected:
                            self._apply_skill_card(selected)
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    selected = self.skill_card_selector.handle_input(
                        (0, 0), (0, 0, 0), [{"type": "down", "pos": (x, y), "id": event.finger_id}], self.scale
                    )
                    if selected:
                        self._apply_skill_card(selected)
            return mouse_pos, mouse_pressed

        if self.state == GameState.DIALOGUE and self.dialogue.active:
            for event in all_events:
                if event.type == pygame.QUIT:
                    logger.info("收到退出事件")
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self.is_android:
                        self.screen = pygame.display.set_mode(
                            (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self._update_scale()
                        logger.info(f"窗口调整: {event.w}x{event.h}")
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        logger.debug("对话：空格/回车键推进")
                        self._advance_dialogue()
                    elif event.key == pygame.K_1 and self.dialogue.choices:
                        effect = self.dialogue.choices[0].get("effect")
                        self._apply_choice_effect(effect)
                        self.dialogue.select_choice(0)
                        logger.info("对话：选择选项1")
                    elif event.key == pygame.K_2 and len(self.dialogue.choices) > 1:
                        effect = self.dialogue.choices[1].get("effect")
                        self._apply_choice_effect(effect)
                        self.dialogue.select_choice(1)
                        logger.info("对话：选择选项2")
                    elif event.key == pygame.K_3 and len(self.dialogue.choices) > 2:
                        effect = self.dialogue.choices[2].get("effect")
                        self._apply_choice_effect(effect)
                        self.dialogue.select_choice(2)
                        logger.info("对话：选择选项3")
                    elif event.key == pygame.K_4 and len(self.dialogue.choices) > 3:
                        effect = self.dialogue.choices[3].get("effect")
                        self._apply_choice_effect(effect)
                        self.dialogue.select_choice(3)
                        logger.info("对话：选择选项4")
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mouse_pos = event.pos
                        if self.dialogue.choices and len(self.dialogue.displayed_text) >= len(self.dialogue.text):
                            choice_clicked = self._check_choice_click(mouse_pos)
                            if choice_clicked >= 0:
                                effect = self.dialogue.choices[choice_clicked].get("effect")
                                self._apply_choice_effect(effect)
                                self.dialogue.select_choice(choice_clicked)
                                logger.info(f"对话：鼠标选择选项 {choice_clicked + 1}")
                            else:
                                self._advance_dialogue()
                        else:
                            self._advance_dialogue()
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    touch_pos = (x, y)
                    if self.dialogue.choices and len(self.dialogue.displayed_text) >= len(self.dialogue.text):
                        choice_clicked = self._check_choice_click(touch_pos)
                        if choice_clicked >= 0:
                            effect = self.dialogue.choices[choice_clicked].get("effect")
                            self._apply_choice_effect(effect)
                            self.dialogue.select_choice(choice_clicked)
                            logger.info(f"对话：手指选择选项 {choice_clicked + 1}")
                        else:
                            self._advance_dialogue()
                    else:
                        self._advance_dialogue()
                elif event.type == pygame.FINGERMOTION:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
            return mouse_pos, mouse_pressed

        # 菜单/设置/教程/剧情资料库/难度选择的滚轮和触摸滚动
        if self.state in (GameState.MENU, GameState.SETTINGS, GameState.TUTORIAL, GameState.RECORDS, GameState.STORY_ARCHIVE, GameState.CODEX, GameState.MODE_SELECT, GameState.DIFFICULTY_SELECT, GameState.MOD_MANAGER, GameState.ACHIEVEMENTS, GameState.UPDATE, GameState.UPDATE_NOTES, GameState.EQUIP_SELECT):
            for event in all_events:
                if event.type == pygame.QUIT:
                    logger.info("收到退出事件")
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self.is_android:
                        self.screen = pygame.display.set_mode(
                            (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self._update_scale()
                        logger.info(f"窗口调整: {event.w}x{event.h}")
                elif event.type == pygame.MOUSEWHEEL:
                    if self.state == GameState.SKILL_TREE and hasattr(self, 'skill_tree_renderer'):
                        self.skill_tree_renderer.handle_wheel(event.y, getattr(event, 'x', 0))
                    elif self.state == GameState.MENU:
                        self.menu_scroll_offset = max(0, self.menu_scroll_offset - event.y * 40)
                    elif self.state == GameState.SETTINGS:
                        self.settings_scroll_offset = max(0, self.settings_scroll_offset - event.y * 40)
                    elif self.state == GameState.TUTORIAL:
                        self.tutorial_scroll_offset = max(0, self.tutorial_scroll_offset - event.y * 40)
                    elif self.state == GameState.RECORDS:
                        self.records_scroll_offset = max(0, getattr(self, 'records_scroll_offset', 0) - event.y * 40)
                    elif self.state == GameState.STORY_ARCHIVE:
                        self.story_archive_scroll = max(0, self.story_archive_scroll - event.y * 40)
                    elif self.state == GameState.CODEX:
                        self.codex_scroll = max(0, self.codex_scroll - event.y * 40)
                    elif self.state == GameState.MOD_MANAGER:
                        self.mod_manager_scroll = max(0, self.mod_manager_scroll - event.y * 40)
                    elif self.state == GameState.ACHIEVEMENTS:
                        self.ach_scroll_offset = max(0, self.ach_scroll_offset - event.y * 40)
                    elif self.state == GameState.UPDATE_NOTES:
                        if hasattr(self, '_update_notes_panel') and self._update_notes_panel:
                            self._update_notes_panel.handle_wheel(event.y)
                    elif self.state == GameState.EQUIP_SELECT:
                        try:
                            mx, _ = pygame.mouse.get_pos()
                            if mx < 640 * self.scale:
                                n = len(self.get_weapon_shop_rows())
                                visible = max(1, int((330 - 30) / (58 * self.scale)))
                                self.equip_weapon_scroll = max(0, min(max(0, n - visible), int(self.equip_weapon_scroll) - event.y))
                            else:
                                nc = len(self.get_character_shop_rows())
                                visiblec = max(1, int((330 - 30) / (78 * self.scale)))
                                self.equip_character_scroll = max(0, min(max(0, nc - visiblec), int(self.equip_character_scroll) - event.y))
                        except Exception:
                            pass
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
                    self.is_menu_dragging = True
                    self.menu_drag_start_y = y
                    if self.state == GameState.MENU:
                        self.menu_drag_start_offset = self.menu_scroll_offset
                    elif self.state == GameState.SETTINGS:
                        self.menu_drag_start_offset = self.settings_scroll_offset
                    elif self.state == GameState.TUTORIAL:
                        self.menu_drag_start_offset = self.tutorial_scroll_offset
                    elif self.state == GameState.RECORDS:
                        self.menu_drag_start_offset = getattr(self, 'records_scroll_offset', 0)
                    elif self.state == GameState.STORY_ARCHIVE:
                        self.menu_drag_start_offset = self.story_archive_scroll
                    elif self.state == GameState.CODEX:
                        self.menu_drag_start_offset = self.codex_scroll
                    elif self.state == GameState.MOD_MANAGER:
                        self.menu_drag_start_offset = self.mod_manager_scroll
                    elif self.state == GameState.ACHIEVEMENTS:
                        self.menu_drag_start_offset = self.ach_scroll_offset
                    elif self.state == GameState.EQUIP_SELECT:
                        # 拖动起点：按落点栏位存储对应滚动值
                        self.menu_drag_start_offset = self.equip_character_scroll if x >= 660 * self.scale else self.equip_weapon_scroll
                elif event.type == pygame.FINGERMOTION:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
                    if self.is_menu_dragging:
                        dy = self.menu_drag_start_y - y
                        new_offset = max(0, self.menu_drag_start_offset + dy)
                        if self.state == GameState.MENU:
                            self.menu_scroll_offset = new_offset
                        elif self.state == GameState.SETTINGS:
                            self.settings_scroll_offset = new_offset
                        elif self.state == GameState.TUTORIAL:
                            self.tutorial_scroll_offset = new_offset
                        elif self.state == GameState.RECORDS:
                            self.records_scroll_offset = new_offset
                        elif self.state == GameState.STORY_ARCHIVE:
                            self.story_archive_scroll = new_offset
                        elif self.state == GameState.CODEX:
                            self.codex_scroll = new_offset
                        elif self.state == GameState.MOD_MANAGER:
                            self.mod_manager_scroll = new_offset
                        elif self.state == GameState.ACHIEVEMENTS:
                            self.ach_scroll_offset = new_offset
                        elif self.state == GameState.EQUIP_SELECT:
                            try:
                                # 拖动像素换算为行数（合理速度：拖动约一行高才滚一行）
                                if x < 640 * self.scale:
                                    row_h = 58 * self.scale
                                    base = int(getattr(self, 'menu_drag_start_offset', self.equip_weapon_scroll))
                                    n = len(self.get_weapon_shop_rows())
                                    visible = max(1, int((330 - 30) / row_h))
                                    self.equip_weapon_scroll = max(0, min(max(0, n - visible), base + int(dy / row_h)))
                                else:
                                    row_h = 78 * self.scale
                                    base = int(getattr(self, 'menu_drag_start_offset', self.equip_character_scroll))
                                    nc = len(self.get_character_shop_rows())
                                    visiblec = max(1, int((330 - 30) / row_h))
                                    self.equip_character_scroll = max(0, min(max(0, nc - visiblec), base + int(dy / row_h)))
                            except Exception:
                                pass
                elif event.type == pygame.FINGERUP:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "up", "pos": (x, y), "id": event.finger_id})
                    self.is_menu_dragging = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.config.control_mode == ControlMode.TOUCH:
                        self.touch_events.append({"type": "down", "pos": mouse_pos, "id": 0})
                elif event.type == pygame.MOUSEBUTTONUP:
                    if self.config.control_mode == ControlMode.TOUCH:
                        self.touch_events.append({"type": "up", "pos": mouse_pos, "id": 0})
                elif event.type == pygame.MOUSEMOTION:
                    if self.config.control_mode == ControlMode.TOUCH:
                        self.touch_events.append({"type": "move", "pos": mouse_pos, "id": 0})
            return mouse_pos, mouse_pressed

        # PAUSED和GAME_OVER状态需要处理鼠标/触摸事件用于按钮点击
        is_paused_or_over = self.state in (GameState.PAUSED, GameState.GAME_OVER)

        if self.state == GameState.ACHIEVEMENTS:
            for event in all_events:
                if event.type == pygame.QUIT:
                    logger.info("收到退出事件")
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self.is_android:
                        self.screen = pygame.display.set_mode(
                            (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self._update_scale()
                elif event.type == pygame.MOUSEWHEEL:
                    self.ach_scroll_offset -= event.y * 32
                    self.ach_scroll_offset = max(0, self.ach_scroll_offset)
                elif event.type == pygame.FINGERMOTION:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    # 触控拖动滚动
                    if hasattr(self, '_ach_touch_last_y') and self._ach_touch_last_y is not None:
                        delta = y - self._ach_touch_last_y
                        self.ach_scroll_offset -= delta
                        self.ach_scroll_offset = max(0, self.ach_scroll_offset)
                    self._ach_touch_last_y = y
                    self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self._ach_touch_last_y = y
                    self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
                elif event.type == pygame.FINGERUP:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self._ach_touch_last_y = None
                    self.touch_events.append({"type": "up", "pos": (x, y), "id": event.finger_id})
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = GameState.MENU
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button ==1:
                        self.touch_events.append({"type":"down","pos":event.pos,"id":0})
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button ==1:
                        self.touch_events.append({"type":"up","pos":event.pos,"id":0})
            return mouse_pos, mouse_pressed
        
        for event in all_events:
            if event.type == pygame.QUIT:
                logger.info("收到退出事件")
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                if not self.is_android:
                    self.screen = pygame.display.set_mode(
                        (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                    )
                    self._update_scale()
                    logger.info(f"窗口调整: {event.w}x{event.h}")

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

            elif event.type == pygame.KEYUP:
                self._handle_keyup(event.key)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # 触摸事件已在预处理统一收集到 touch_events，这里只保留日志
                    if self.config.control_mode == ControlMode.TOUCH:
                        logger.debug(f"鼠标触控按下: {event.pos}")

            elif event.type == pygame.MOUSEWHEEL:
                # 剧情资料库滚动
                if self.state == GameState.STORY_ARCHIVE:
                    self.story_archive_scroll -= event.y * 40
                    self.story_archive_scroll = max(0, self.story_archive_scroll)

            elif event.type == pygame.FINGERDOWN:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self.last_touch_pos = (x, y)
                logger.debug(f"手指按下: ({x:.0f}, {y:.0f}), id={event.finger_id}")

            elif event.type == pygame.FINGERUP:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                logger.debug(f"手指抬起: ({x:.0f}, {y:.0f}), id={event.finger_id}")

        return mouse_pos, mouse_pressed

    # ================= 开发者测试模式 =================
    def _handle_net_ip_keyboard(self, events):
        """网络联机界面 IP 输入框：聚焦时接受系统输入法输入"""
        for ev in events:
            if ev.type == pygame.TEXTINPUT:
                if len(self.net_ip_input) < 30:
                    self.net_ip_input += ev.text
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    self.net_ip_focused = False
                    self.stop_text_input()
                    self._net_join()
                elif ev.key == pygame.K_BACKSPACE:
                    self.net_ip_input = self.net_ip_input[:-1]
                elif ev.key == pygame.K_ESCAPE:
                    self.net_ip_focused = False
                    self.stop_text_input()

    def _handle_dev_keys(self, events):
        """处理开发者密码输入与局内调试面板开关（键盘）"""
        # 网络联机 IP 输入框：聚焦时优先接受系统输入法输入
        if self.state == GameState.NET_MULTIPLAYER and self.net_ip_focused:
            self._handle_net_ip_keyboard(events)
            return
        if self.dev_input_active:
            for ev in events:
                # SDL_IME 系统输入法：TEXTINPUT 是最终合成字符事件（含中文候选），
                # 同一按键还会伴随 KEYDOWN，字符追加只走 TEXTINPUT，避免双重输入。
                # 只有输入框聚焦后才接受输入（点击输入框/回车/空格/Tab 聚焦）
                if ev.type == pygame.TEXTINPUT:
                    if self.dev_input_focused and len(self.dev_input_str) < 16:
                        self.dev_input_str += ev.text
                    continue
                if ev.type == pygame.KEYDOWN:
                    if not self.dev_input_focused:
                        # 未聚焦：回车/空格/Tab = 键盘"点击"输入框聚焦；ESC 关闭密码框
                        if ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_TAB):
                            self._focus_dev_input()
                        elif ev.key == pygame.K_ESCAPE:
                            self._blur_dev_input()
                            self.dev_input_active = False
                            self.dev_input_str = ""
                        continue
                    # ===== 聚焦态：接受系统输入法输入 =====
                    if ev.key == pygame.K_RETURN:
                        if self.dev_input_str == self._DEV_PASSWORD:
                            self.dev_mode = True
                            self.dev_input_active = False
                            self.dev_input_str = ""
                            self._blur_dev_input()
                            self.update_status_text = "开发者模式已开启！局内按 F9 键打开调试面板"
                        else:
                            self.dev_input_active = False
                            self.dev_input_str = ""
                            self._blur_dev_input()
                            self.update_status_text = "密码错误，请重试（连点版本号重新输入）"
                    elif ev.key == pygame.K_BACKSPACE:
                        self.dev_input_str = self.dev_input_str[:-1]
                    elif ev.key == pygame.K_ESCAPE:
                        self._blur_dev_input()
            return
        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F9:
                if self.state == GameState.PLAYING and self.dev_mode:
                    self.dev_panel_open = not self.dev_panel_open
                    self._rebuild_dev_buttons()

    def start_text_input(self):
        """唤起系统输入法（SDL_IME），供网络IP输入框/开发者密码框使用"""
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def stop_text_input(self):
        """收起系统输入法"""
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    def _focus_dev_input(self):
        """聚焦开发者密码输入框：激活系统输入法（SDL_IME），开始接受输入"""
        if not self.dev_input_active:
            return
        self.dev_input_focused = True
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def _blur_dev_input(self):
        """失焦：关闭系统输入法候选框，不再接受输入"""
        self.dev_input_focused = False
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    def _rebuild_dev_buttons(self):
        """重建局内调试面板按钮（依据当前 dev 状态）"""
        # Button 已在 game.py 顶部 from ui import 导入
        self.dev_buttons = [
            Button(0, 0, 150, 36, f"无敌:{'开' if self.dev_god else '关'}", color=(60, 60, 220)),
            Button(0, 0, 150, 36, f"倍率:x{self.dev_time_scale}", color=(40, 140, 80)),
            Button(0, 0, 150, 36, "生成Boss", color=(180, 60, 60)),
            Button(0, 0, 150, 36, "生成精英", color=(120, 80, 160)),
            Button(0, 0, 150, 36, "生成小怪", color=(90, 130, 80)),
            Button(0, 0, 150, 36, "清空敌人", color=(120, 120, 130)),
            Button(0, 0, 150, 36, "+5000金币", color=(200, 170, 60)),
            Button(0, 0, 150, 36, "+5000经验", color=(90, 160, 200)),
            Button(0, 0, 150, 36, "满血满弹", color=(60, 200, 120)),
            Button(0, 0, 150, 36, "关闭面板", color=(130, 60, 60)),
        ]

    def _update_dev_panel(self, mouse_pos, mouse_pressed, touch_events, scale):
        """局内调试面板：按钮点击检测与功能执行"""
        if not (self.dev_mode and self.dev_panel_open):
            return
        from config import EnemyType
        bx, by = self.scaled_width - 190, 90
        for idx, btn in enumerate(self.dev_buttons):
            btn.base_x = bx
            btn.base_y = by + idx * 42
            # 注意：bx/by 已是屏幕像素坐标，Button 内部不再缩放（传 scale=1.0）
            if btn.update(mouse_pos, mouse_pressed, touch_events, 1.0):
                self._dev_action(idx)

    def _dev_action(self, idx):
        """执行调试面板按钮动作"""
        if idx == 0:
            self.dev_god = not self.dev_god
            if self.player:
                self.player.dev_god = self.dev_god
            self._rebuild_dev_buttons()
        elif idx == 1:
            self.dev_time_scale = {1.0: 2.0, 2.0: 4.0, 4.0: 0.5, 0.5: 1.0}.get(self.dev_time_scale, 1.0)
            self._rebuild_dev_buttons()
        elif idx == 2:
            from config import EnemyType as _ET
            bs = [_ET.BOSS_LONG, _ET.BOSS_XIANG, _ET.BOSS_MUTANT, _ET.BOSS_QUEEN, _ET.BOSS_TITAN, _ET.BOSS_WANG]
            import random as _r
            et = _r.choice(bs)
            e = Enemy(self.player.x + _r.randint(-100, 100), self.player.y + _r.randint(-100, 100), et, 1, self.config.difficulty)
            self.enemies.append(e)
            self.floating_texts.append(FloatingText(e.x, e.y, f"生成 {getattr(e,'name','')}", color=(255, 80, 80), lifetime=2.0))
        elif idx == 3:
            import random as _r
            from config import EnemyType as _ET
            ets = [_ET.ELITE_BRUTE, _ET.ELITE_ASSASSIN, _ET.ELITE_SORCERER, _ET.ELITE_GUARDIAN]
            for _ in range(5):
                e = Enemy(self.player.x + _r.randint(-150, 150), self.player.y + _r.randint(-150, 150), _r.choice(ets), 1, self.config.difficulty)
                self.enemies.append(e)
        elif idx == 4:
            import random as _r
            from config import EnemyType as _ET
            ets = [_ET.ZOMBIE_NORMAL, _ET.ZOMBIE_FAST, _ET.ZOMBIE_CRAWLER, _ET.ZOMBIE_RANGED]
            for _ in range(12):
                e = Enemy(self.player.x + _r.randint(-200, 200), self.player.y + _r.randint(-200, 200), _r.choice(ets), 1, self.config.difficulty)
                self.enemies.append(e)
        elif idx == 5:
            self.enemies.clear()
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "已清空敌人", color=(200, 200, 210), lifetime=1.5))
        elif idx == 6:
            try:
                self.records.add_coins(5000)
            except Exception:
                pass
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "+5000金币", color=(255, 215, 0), lifetime=1.5))
        elif idx == 7:
            self.player.gain_exp(5000)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "+5000经验", color=(90, 200, 240), lifetime=1.5))
        elif idx == 8:
            self.player.hp = self.player.max_hp
            for w in self.player.weapons:
                if hasattr(w, 'current_ammo') and w.current_ammo != "Inf":
                    w.current_ammo = w.max_ammo
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "已回复满", color=(60, 220, 120), lifetime=1.5))
        elif idx == 9:
            self.dev_panel_open = False

    def _handle_keydown(self, key):
        import time
        # Mod 按键钩子：返回 True 则阻止默认处理
        try:
            results = trigger_hook(HOOK_KEYDOWN, key)
            if any(r is True for r in results):
                return
        except Exception:
            pass
        if self.state == GameState.PLAYING:
            # 单武器模式：删除武器切换键控（K1/K2/K3/R 不再切武器）
            if key == pygame.K_TAB:
                # Tab：短按切换下一个技能（非观战模式且玩家可操作时）
                if self.player.can_act():
                    unlocked = self._get_unlocked_skills()
                    if len(unlocked) > 0:
                        current_idx = unlocked.index(self.selected_skill) if self.selected_skill in unlocked else -1
                        next_idx = (current_idx + 1) % len(unlocked)
                        self.selected_skill = unlocked[next_idx]
                        skill = self.player.skill_tree.get_skill(self.selected_skill)
                        self.floating_texts.append(FloatingText(
                            self.player.x, self.player.y - 40,
                            f"技能: {skill.name if skill else '空'}", color=GOLD, lifetime=1.5
                        ))
            elif key == pygame.K_t:
                # T：打开技能树
                self.prev_state = self.state
                self.state = GameState.SKILL_TREE
                self.skill_tree_renderer.show()
            elif key == pygame.K_g:
                import time
                self.key_g_press_start = time.time()
                self.key_g_held = True
                self.g_aim_started = False
                self.skill_caster.is_aiming = False
                # 只记录按下，不释放技能
            elif key == pygame.K_q:
                # Q：投掷物（短按快投，长按瞄准）
                import time
                self.key_q_press_start = time.time()
                self.key_q_held = True
                self.q_aim_started = False
                self.throwable_caster.is_aiming = False
            elif key == pygame.K_e:
                # E：切换投掷物类型
                if self.player.can_act():
                    self._cycle_throwable()
            elif key == pygame.K_u:
                # U：P2 技能（短按快放，长按预瞄释放）
                if self.multiplayer_mode == "same_screen" and self.player2:
                    import time as _t
                    self.key_u_press_start = _t.time()
                    self.key_u_held = True
                    self.u_aim_started = False
                    if self.p2_controls:
                        self.p2_controls["skill_caster"].is_aiming = False
            elif key == pygame.K_f:
                    pass
            elif key == pygame.K_ESCAPE:
                self.state = GameState.PAUSED
        elif self.state == GameState.PAUSED:
            if key == pygame.K_ESCAPE:
                self.state = GameState.PLAYING
        elif self.state == GameState.RUNE_VIEW:
            if key == pygame.K_ESCAPE:
                self.state = GameState.PAUSED
                self.rune_selected = None
        elif self.state == GameState.HUD_EDIT:
            if key == pygame.K_ESCAPE:
                self.state = GameState.SETTINGS
        elif self.state == GameState.SETTINGS:
            if key == pygame.K_ESCAPE:
                self.config.save()
                if getattr(self, 'settings_from_pause', False):
                    self.settings_from_pause = False
                    self.state = GameState.PAUSED
                else:
                    self.state = GameState.MENU
        elif self.state == GameState.RECORDS:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
        elif self.state == GameState.CODEX:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
                self.codex_scroll = 0
                self.codex_selected = None
        elif self.state == GameState.SKILL_TREE:
            if key == pygame.K_ESCAPE or key == pygame.K_t:
                self.state = getattr(self, 'prev_state', GameState.PLAYING)
                self.skill_tree_renderer.hide()
            elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                if hasattr(self, 'skill_tree_renderer'):
                    self.skill_tree_renderer.handle_key(key)
        elif self.state == GameState.TEXT_VIEWER:
            if key == pygame.K_ESCAPE or key == pygame.K_e or key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.state = getattr(self, 'prev_state', GameState.PLAYING)
                self.current_viewing_text = None
        elif self.state == GameState.STORY_ARCHIVE:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
                self.story_archive_scroll = 0
                self.story_archive_selected = None
        elif self.state == GameState.MOD_MANAGER:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
                self.mod_manager_scroll = 0
                self.mod_selected = None
        elif self.state == GameState.UPDATE:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
        elif self.state == GameState.UPDATE_NOTES:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU

    def _handle_keyup(self, key):
        import time
        # 技能树方向键释放
        if self.state == GameState.SKILL_TREE and hasattr(self, 'skill_tree_renderer'):
            self.skill_tree_renderer.handle_key_up(key)
            return
        if self.state != GameState.PLAYING:
            return
        if key == pygame.K_g:
            hold_time = time.time() - self.key_g_press_start
            self.key_g_held = False
            self.skill_caster.is_aiming = False #松开关闭瞄准标记

            if not self.player.can_act():
                self.g_aim_started = False
                self.player.riot_gear.end_aim()
                return

            selected_skill = self.selected_skill
            if hold_time < self.key_g_long_threshold:
                # --------短按快放--------
                if selected_skill == SkillType.RIOT_GEAR:
                    riot_skill = self.player.skill_tree.get_skill(SkillType.RIOT_GEAR)
                    if riot_skill is not None and riot_skill.current_level > 0:
                        cd_mult = self.player.cooldown_mult
                        if self.player.riot_gear.equipped:
                            self.player.riot_gear.unequip(cd_reduction_mult=cd_mult)
                            self.floating_texts.append(FloatingText(self.player.x,self.player.y-50,"卸下防爆套装",ORANGE,1.2))
                        else:
                            ok = self.player.riot_gear.equip()
                            if ok:
                                self.floating_texts.append(FloatingText(self.player.x,self.player.y-50,"装备防爆套装",GREEN,1.2))
                            else:
                                self.floating_texts.append(FloatingText(self.player.x,self.player.y-50,"防爆套装冷却中！",RED,1.2))
                else:
                    self._use_skill(selected_skill)
            else:
                # --------长按瞄准释放，复用原有 _use_skill_aimed 接口--------
                angle = self.skill_caster.angle
                ratio = self.skill_caster.distance_ratio
                self._use_skill_aimed(selected_skill, angle, ratio)

            self.g_aim_started = False
            self.player.riot_gear.end_aim()

        elif key == pygame.K_q:
            # Q键释放：短按快投，长按瞄准投掷
            import time
            hold_time = time.time() - self.key_q_press_start
            self.key_q_held = False
            self.throwable_caster.is_aiming = False

            if not self.player.can_act():
                self.q_aim_started = False
                return

            if hold_time < self.key_q_long_threshold:
                # 短按：朝鼠标方向快速投掷
                self._throw_grenade()
            else:
                # 长按：按瞄准方向和距离投掷
                angle = self.throwable_caster.angle
                ratio = self.throwable_caster.distance_ratio
                self._throw_grenade_aimed(angle, ratio)

            self.q_aim_started = False

        elif key == pygame.K_u:
            # U键释放：P2 技能（短按快放，长按预瞄释放）
            if self.multiplayer_mode != "same_screen" or not self.player2:
                return
            import time as _t
            hold_time = _t.time() - self.key_u_press_start
            self.key_u_held = False
            if self.p2_controls:
                self.p2_controls["skill_caster"].is_aiming = False
            if not self.player2.can_act():
                self.u_aim_started = False
                return
            st = self.p2_selected_skill
            if st is None:
                sts = self._get_unlocked_skills_for(self.player2)
                if sts:
                    st = sts[0]
            if not st:
                self.u_aim_started = False
                return
            if hold_time < self.key_u_long_threshold:
                # 短按快放（当前朝向）
                self._use_skill_p2(st)
            else:
                # 长按：按预瞄方向+距离释放
                c2 = self.p2_controls
                if self.u_aim_started:
                    self._use_skill_p2_aimed(st, c2["skill_caster"].angle, c2["skill_caster"].distance_ratio)
                else:
                    self._use_skill_p2_aimed(st, math.radians(self.player2.facing_angle), 1.0)
            self.u_aim_started = False
