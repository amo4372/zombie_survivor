# -*- coding: utf-8 -*-
"""ShopMixin - 由 game.py 自动拆分，逻辑等价"""

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

class ShopMixin:
    def _get_shop_weapons(self):
        """局外可选武器列表（排除投掷物类）"""
        throwable_set = {WeaponType.GRENADE, WeaponType.MOLOTOV, WeaponType.SMOKE_GRENADE}
        return [wt for wt in WeaponType if wt not in throwable_set]

    def get_weapon_shop_rows(self):
        """返回武器商店行数据：[(wt, name, price, owned, level, locked_reason, desc)]"""
        rows = []
        for wt in self._get_shop_weapons():
            name = Weapon(wt).name
            price = WEAPON_PRICES.get(wt.name, 0)
            owned = self.records.is_weapon_owned(wt.name)
            level = self.records.get_weapon_level(wt.name) if owned else 1
            locked_reason = ""
            if wt == WeaponType.SCYTHE and not self.records.has_defeated_wang():
                locked_reason = "需击败王某"
            rows.append((wt, name, price, owned, level, locked_reason, Weapon(wt).desc))
        return rows

    def equip_select_weapon(self, wt):
        """选择（已拥有的）武器"""
        if not self.records.is_weapon_owned(wt.name):
            return False
        self.selected_weapon = wt
        self.selected_weapon_level = self.records.get_weapon_level(wt.name)
        return True

    def equip_buy_weapon(self, wt):
        """购买武器。返回状态字符串"""
        if self.records.is_weapon_owned(wt.name):
            return "owned"
        if wt == WeaponType.SCYTHE and not self.records.has_defeated_wang():
            return "locked_wang"
        price = WEAPON_PRICES.get(wt.name, 0)
        if price <= 0:
            self.records.unlock_weapon_purchase(wt.name)
            self.selected_weapon = wt
            self.selected_weapon_level = 1
            return "ok"
        if self.records.get_coins() < price:
            return "no_coin"
        self.records.spend_coins(price)
        self.records.unlock_weapon_purchase(wt.name)
        self.selected_weapon = wt
        self.selected_weapon_level = 1
        return "ok"

    def get_weapon_upgrade_price(self, wt):
        """当前武器升至下一级的费用（满级返回0）"""
        try:
            cur = self.records.get_weapon_level(wt.name)
            if cur >= 5:
                return 0
            return max(0, int(WEAPON_PRICES.get(wt.name, 0) * 0.6 * (cur + 1)))
        except Exception:
            return 0

    def get_character_upgrade_price(self, name):
        """当前角色升至下一级的费用（满级返回0）"""
        try:
            cur = self.records.get_character_level(name)
            if cur >= 5:
                return 0
            return max(0, int(CHARACTERS.get(name, {}).get("price", 0) * 0.6 * (cur + 1)))
        except Exception:
            return 0

    def upgrade_weapon_shop(self, wt):
        """局外升级武器（花费金币提升等级，最高5级）"""
        cur = self.records.get_weapon_level(wt.name)
        if cur >= 5:
            return "max"
        next_lvl = cur + 1
        price = int(WEAPON_PRICES.get(wt.name, 0) * 0.6 * next_lvl)
        if price <= 0:
            return "ok"
        if self.records.get_coins() < price:
            return "no_coin"
        self.records.spend_coins(price)
        self.records.upgrade_weapon_purchase(wt.name, next_lvl)
        if self.selected_weapon == wt:
            self.selected_weapon_level = next_lvl
        return "ok"

    def get_character_shop_rows(self):
        """返回角色商店行数据：[(name, price, owned, level, desc, ability, locked_reason)]"""
        rows = []
        for name, cfg in CHARACTERS.items():
            if cfg.get("requires_scythe") and not self.records.has_defeated_wang():
                locked_reason = "需击败王某"
            else:
                locked_reason = ""
            owned = self.records.is_character_owned(name)
            level = self.records.get_character_level(name) if owned else 1
            rows.append((name, cfg["price"], owned, level, cfg["desc"], cfg["ability"], locked_reason))
        return rows

    def equip_select_character(self, name):
        if not self.records.is_character_owned(name):
            return False
        self.selected_character = name
        return True

    def equip_buy_character(self, name):
        cfg = CHARACTERS.get(name)
        if not cfg:
            return "err"
        if cfg.get("requires_scythe") and not self.records.has_defeated_wang():
            return "locked_wang"
        if self.records.is_character_owned(name):
            return "owned"
        price = cfg["price"]
        if price <= 0:
            self.records.unlock_character_purchase(name)
            self.selected_character = name
            return "ok"
        if self.records.get_coins() < price:
            return "no_coin"
        self.records.spend_coins(price)
        self.records.unlock_character_purchase(name)
        self.selected_character = name
        return "ok"

    def upgrade_character_shop(self, name):
        cur = self.records.get_character_level(name)
        if cur >= 5:
            return "max"
        next_lvl = cur + 1
        price = int(CHARACTERS.get(name, {}).get("price", 0) * 0.6 * next_lvl)
        if price <= 0:
            return "ok"
        if self.records.get_coins() < price:
            return "no_coin"
        self.records.spend_coins(price)
        self.records.upgrade_character_purchase(name, next_lvl)
        return "ok"

    def equip_confirm(self):
        """确认装备选择，开始游戏（选中项必须已解锁）"""
        if self.selected_weapon and not self.records.is_weapon_owned(self.selected_weapon.name):
            self.equip_hover = "请先解锁所选武器"
            return
        if self.selected_character and not self.records.is_character_owned(self.selected_character):
            self.equip_hover = "请先解锁所选角色"
            return
        # ===== 多人模式：P1/P2 两轮选择 =====
        if self.multiplayer_mode in ("same_screen", "network"):
            if not self.equip_p2_phase:
                self.selected_weapon_p1 = self.selected_weapon
                self.selected_char_p1 = self.selected_character
                self.selected_weapon_p1_level = self.selected_weapon_level
                self.equip_p2_phase = True
                self.selected_weapon = None
                self.selected_character = None
                self.selected_weapon_level = 1
                self.equip_hover = "轮到玩家2选择装备"
                self.equip_tab_weapon = True
                return
            self.selected_weapon_p2 = self.selected_weapon
            self.selected_char_p2 = self.selected_character
            self.selected_weapon_p2_level = self.selected_weapon_level
            self.equip_p2_phase = False
        self.start_game()

    # ===== 网络联机 =====
    def _apply_character_bonuses(self):
        """应用局外角色特殊能力加成（按角色等级缩放）"""
        if not self.selected_character:
            return
        cfg = CHARACTERS.get(self.selected_character)
        if not cfg:
            return
        lvl = self.records.get_character_level(self.selected_character)
        scale_lvl = 1 + (lvl - 1) * 0.2
        p = self.player
        hb = int(cfg.get("hp_bonus", 0) * scale_lvl)
        if hb:
            p.max_hp += hb
            p.hp = min(p.hp + hb, p.max_hp)
        p.base_speed += cfg.get("speed_bonus", 0) * scale_lvl
        p.speed = p.base_speed
        p.damage_multiplier *= (1 + cfg.get("damage_bonus", 0))
        p.crit_bonus_add += cfg.get("crit_bonus", 0)
        p.crit_chance += p.crit_bonus_add
        p.health_regen += cfg.get("regen", 0) * scale_lvl
        p.dmg_reduce += cfg.get("dmg_reduce", 0)

    def _first_available_story_map(self):
        """故事模式第一遍流程：从第一张未通关地图开始；全通关后回到第一张"""
        for m in STORY_MAP_ORDER:
            if not self.records.is_map_cleared(m.name):
                return m
        return STORY_MAP_ORDER[0]
