# -*- coding: utf-8 -*-
"""HudMixin - 由 game.py 自动拆分，逻辑等价"""

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

class HudMixin:
    def _setup_touch_controls(self):
        """触控按钮位置调整 - 重新布局避免重叠，三列两行"""
        # 移动摇杆 - 左下角
        self.joystick = VirtualJoystick(120, BASE_HEIGHT - 120, 70)
        # 攻击/瞄准摇杆 - 右下角
        self.aim_button = AimButton(BASE_WIDTH - 500, BASE_HEIGHT - 145, 62)

        # 触控按钮 - 三列两行布局，避免重叠
        self.touch_buttons = {
            "shoot": TouchButton(BASE_WIDTH - 500, BASE_HEIGHT - 145, 62, "射击", RED),
            "pause": TouchButton(60, 55, 38, "II", GRAY),
            "sprint": TouchButton(210, BASE_HEIGHT - 130, 40, "疾跑", AMBER),
        }
        # 技能切换按钮（右上列）
        self.skill_selector = SkillSelector(BASE_WIDTH - 220, BASE_HEIGHT - 320, 42)
        # 技能释放按钮（右下列）
        self.skill_caster = SkillCaster(BASE_WIDTH - 130, BASE_HEIGHT - 145, 52)
        # 投掷物切换按钮（中上列）
        self.throwable_switch_btn = TouchButton(BASE_WIDTH - 370, BASE_HEIGHT - 320, 42, "投掷", ORANGE)
        # 投掷物释放器（中下列，复用SkillCaster的瞄准逻辑）
        self.throwable_caster = SkillCaster(BASE_WIDTH - 310, BASE_HEIGHT - 145, 48)
        # 触控模式下显示按钮，键盘模式下隐藏
        self.throwable_caster.visible = (self.config.control_mode == ControlMode.TOUCH or getattr(self, 'is_android', False))
        # 投掷物选择系统
        self.throwable_types = ["incendiary", "smoke", "cluster", "emp"]
        self.throwable_names = {"incendiary": "燃烧弹", "smoke": "烟雾弹", "cluster": "集束炸弹", "emp": "EMP脉冲弹"}
        self.throwable_colors = {"incendiary": (255, 100, 0), "smoke": (160, 160, 160), "cluster": (255, 165, 0), "emp": (0, 200, 255)}
        self.selected_throwable = "incendiary"  # 当前选中的投掷物
        # Q键投掷物状态
        self.key_q_press_start = 0
        self.key_q_held = False
        self.q_aim_started = False
        self.key_q_long_threshold = 0.3  # 长按阈值，与G键一致
        self.throwable_max_dist = 450  # 投掷物最大距离
        self._apply_hud_layout()
        logger.info("触控控件初始化完成")

    def _apply_hud_layout(self):
        """应用用户自定义的HUD按钮布局（config.hud_layout: {name: [x, y]} 逻辑坐标）"""
        self._apply_layout_to(self.config.hud_layout or {})

    def _apply_layout_to(self, layout):
        """把布局字典应用到 P1 触控控件"""
        lay = layout or {}
        if not lay:
            return
        def _set(ctrl, key):
            if ctrl is not None and key in lay:
                try:
                    ctrl.base_x = int(lay[key][0])
                    ctrl.base_y = int(lay[key][1])
                except (TypeError, IndexError, ValueError):
                    pass
        _set(self.joystick, "joystick")
        _set(self.aim_button, "aim")
        _set(self.touch_buttons.get("shoot"), "shoot")
        _set(self.touch_buttons.get("pause"), "pause")
        _set(self.touch_buttons.get("sprint"), "sprint")
        _set(self.skill_selector, "skill_selector")
        _set(self.skill_caster, "skill_caster")
        _set(self.throwable_switch_btn, "throwable_switch")
        _set(self.throwable_caster, "throwable_caster")

    def _save_hud_layout(self, target="单机"):
        """保存触控布局（单机→hud_layout / P1→mp_p1_layout / P2→p2_hud_layout）"""
        layout = {}
        def _put(ctrl, key):
            if ctrl is not None:
                layout[key] = [int(ctrl.base_x), int(ctrl.base_y)]
        if target == "P2" and self.p2_controls:
            c2 = self.p2_controls
            _put(c2["joystick"], "joystick")
            _put(c2["aim"], "aim")
            _put(c2["shoot"], "shoot")
            _put(c2["pause"], "pause")
            _put(c2["sprint"], "sprint")
            _put(c2["skill_selector"], "skill_selector")
            _put(c2["skill_caster"], "skill_caster")
            _put(c2["throwable_switch"], "throwable_switch")
            _put(c2["throwable_caster"], "throwable_caster")
            self.config.p2_hud_layout = layout
        elif target == "P1":
            _put(self.joystick, "joystick")
            _put(self.aim_button, "aim")
            _put(self.touch_buttons.get("shoot"), "shoot")
            _put(self.touch_buttons.get("pause"), "pause")
            _put(self.touch_buttons.get("sprint"), "sprint")
            _put(self.skill_selector, "skill_selector")
            _put(self.skill_caster, "skill_caster")
            _put(self.throwable_switch_btn, "throwable_switch")
            _put(self.throwable_caster, "throwable_caster")
            self.config.mp_p1_layout = layout
        else:
            _put(self.joystick, "joystick")
            _put(self.aim_button, "aim")
            _put(self.touch_buttons.get("shoot"), "shoot")
            _put(self.touch_buttons.get("pause"), "pause")
            _put(self.touch_buttons.get("sprint"), "sprint")
            _put(self.skill_selector, "skill_selector")
            _put(self.skill_caster, "skill_caster")
            _put(self.throwable_switch_btn, "throwable_switch")
            _put(self.throwable_caster, "throwable_caster")
            self.config.hud_layout = layout
        self.config.save()
        logger.info(f"HUD布局已保存({target}): {len(layout)} 个控件")

    def _reset_hud_layout(self, target="单机"):
        """重置HUD布局为默认（单机→hud_layout / P1→mp_p1_layout / P2→p2_hud_layout）"""
        if target == "P2" and self.p2_controls:
            self.config.p2_hud_layout = {}
            self.config.save()
            self._setup_multiplayer_controls()
            logger.info("P2 HUD布局已重置为默认")
            return
        if target == "P1":
            self.config.mp_p1_layout = {}
            self.config.save()
            self._setup_multiplayer_controls()
            logger.info("P1 HUD布局已重置为默认")
            return
        self.config.hud_layout = {}
        self.config.save()
        self._setup_touch_controls()
        logger.info("HUD布局已重置为默认")

    # ===== 多人模式：P2 控件与玩家 =====
    def _reset_touch_controls(self):
        """重置所有触控控件状态（状态切换时调用，防止摇杆卡死）"""
        try:
            if hasattr(self, 'joystick') and self.joystick:
                self.joystick.active = False
                self.joystick.touch_id = None
                self.joystick.knob_x = self.joystick.base_x
                self.joystick.knob_y = self.joystick.base_y
                self.joystick.value_x = 0
                self.joystick.value_y = 0
        except Exception:
            pass
        try:
            if hasattr(self, 'aim_button') and self.aim_button:
                self.aim_button.pressed = False
                self.aim_button.touch_id = None
                self.aim_button.just_pressed = False
                self.aim_button.just_released = False
        except Exception:
            pass
        try:
            if hasattr(self, 'skill_selector') and self.skill_selector:
                self.skill_selector.pressed = False
                self.skill_selector.touch_id = None
        except Exception:
            pass
        try:
            if hasattr(self, 'throwable_caster') and self.throwable_caster:
                self.throwable_caster.is_aiming = False
        except Exception:
            pass
        try:
            if hasattr(self, 'skill_tree_renderer') and self.skill_tree_renderer:
                self.skill_tree_renderer._dragging = False
        except Exception:
            pass

    def _synthesize_touch_ups(self):
        """状态切换时，为仍按住的触摸手指合成 up 事件，防止控件被留在按下态。"""
        for fid in list(self._active_touch_ids):
            pos = self._active_touch_pos.get(fid, (0, 0))
            self.touch_events.append({"type": "up", "pos": pos, "id": fid})
        self._active_touch_ids.clear()
        self._active_touch_pos.clear()
        self._active_touch_last.clear()

    def _reset_touch_state(self):
        """强制重置所有触控控件状态，防止游戏状态切换后摇杆/攻击/按钮卡死。

        关键：多指操控时（如一只手移动、一只手攻击）按下菜单键返回暂停，
        仍按住的攻击/摇杆手指的 up 事件在状态切换后不再被 _update_playing 消费，
        因此必须完整清掉所有控件的按下/射击/绑定状态，否则回到游戏后
        攻击摇杆会持续处于 is_shooting 状态（射击按钮卡死）。
        """
        # 虚拟摇杆
        if hasattr(self, 'joystick') and self.joystick:
            if hasattr(self.joystick, 'reset'):
                self.joystick.reset()
            else:
                self.joystick.active = False
                self.joystick.touch_id = None
                self.joystick.knob_x = self.joystick.base_x
                self.joystick.knob_y = self.joystick.base_y
                self.joystick.value_x = 0
                self.joystick.value_y = 0
        # 重置所有触控按钮的 pressed / 绑定手指 / 长按状态
        if hasattr(self, 'touch_buttons'):
            for btn in self.touch_buttons.values():
                for _a in ('pressed', 'was_pressed', 'just_released', 'just_pressed', 'is_long_press'):
                    if hasattr(btn, _a):
                        setattr(btn, _a, False)
                if hasattr(btn, 'touch_id'):
                    btn.touch_id = None
        # 重置攻击摇杆 / 技能施法器 / 投掷物施法器 / 技能选择器
        # 必须清掉 active / is_shooting / is_aiming / touch_id / knob 偏移，才能彻底解除卡死
        for attr in ['aim_button', 'skill_caster', 'throwable_caster', 'skill_selector']:
            obj = getattr(self, attr, None)
            if not obj:
                continue
            for _a in ('active', 'pressed', 'is_shooting', 'is_aiming', 'was_pressed',
                       'just_released', 'just_pressed', 'wheel_active', 'is_long_press',
                       'should_open_wheel'):
                if hasattr(obj, _a):
                    setattr(obj, _a, False)
            if hasattr(obj, 'touch_id'):
                obj.touch_id = None
            if hasattr(obj, 'knob_offset_x'):
                obj.knob_offset_x = 0
            if hasattr(obj, 'knob_offset_y'):
                obj.knob_offset_y = 0
        # 技能轮盘 / 武器轮盘：关闭活动状态
        for _w in (getattr(self, 'skill_wheel', None), getattr(self, 'weapon_wheel', None)):
            if _w and hasattr(_w, 'active'):
                _w.active = False
        # 注意：这里不清空 touch_events，状态切换时合成的 up 交由各控件消费；
        # 由于上面已把 touch_id 全部置空，残留的合成 up 会被控件安全忽略。
