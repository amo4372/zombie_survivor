# -*- coding: utf-8 -*-
"""NetMixin - 由 game.py 自动拆分，逻辑等价"""

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

class NetMixin:
    def _update_net_client(self, dt):
        """网络客户端：采集本地输入发送给主机，检测断开"""
        if not self.net_client:
            self.state = GameState.NET_MULTIPLAYER
            return
        snap = self.net_client.get_snapshot()
        keys = pygame.key.get_pressed()
        mx = (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)
        my = (1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0)
        shoot = bool(keys[pygame.K_SPACE])
        skill = bool(keys[pygame.K_e])
        if self.config.control_mode == ControlMode.TOUCH:
            for _tev in self.touch_events:
                if _tev["type"] == "down":
                    self._client_finger_ids.add(_tev["id"])
                elif _tev["type"] == "up":
                    self._client_finger_ids.discard(_tev["id"])
            self.client_joystick.handle_touch(self.touch_events, self.scale, self._client_finger_ids)
            self.client_aim.handle_touch(self.touch_events, self.scale)
            self.client_shoot.handle_touch(self.touch_events, self.scale)
            self.client_skill.handle_touch(self.touch_events, self.scale)
            if self.client_joystick.active:
                dx, dy = self.client_joystick.get_direction()
                if dx or dy:
                    mx, my = dx, dy
            if self.client_aim.is_shooting:
                shoot = True
            if self.client_skill.just_released:
                skill = True
        # 发送输入帧（20Hz 节流，减少无效包）
        self.net_input_timer = getattr(self, 'net_input_timer', 0) - dt
        if self.net_input_timer <= 0:
            self.net_input_timer = 0.05
            self.net_client.send_input({
                "mx": round(float(mx), 3), "my": round(float(my), 3),
                "shoot": bool(shoot), "skill": bool(skill),
                "throw": False, "sprint": False,
            })
        # 主机断开 → 返回联机界面
        if not self.net_client.connected:
            self.floating_texts.append(FloatingText(0, 0, "与主机断开连接", color=CRIMSON, lifetime=2.0))
            self._net_stop()
            self.state = GameState.NET_MULTIPLAYER

    def _net_send_snapshot(self):
        """主机：每帧广播世界快照给客户端（20Hz 节流 + 坐标量化）"""
        if not self.net_host or not self.net_host.connected or not self.net_started:
            return
        self.net_snap_timer = getattr(self, 'net_snap_timer', 0) - 1 / 60
        if self.net_snap_timer > 0:
            return
        self.net_snap_timer = 0.05
        try:
            projs = []
            for p in self.projectiles[:50]:
                col = getattr(p, 'color', (255, 255, 255))
                try:
                    col = tuple(col)[:3]
                except Exception:
                    col = (255, 255, 255)
                projs.append({"x": round(p.x, 1), "y": round(p.y, 1),
                              "size": getattr(p, 'size', 6), "color": list(col)})
            enems = []
            for e in self.enemies[:80]:
                enems.append({"x": round(e.x, 1), "y": round(e.y, 1), "hp": int(getattr(e, 'hp', 0)),
                              "size": getattr(e, 'size', getattr(e, 'radius', 12))})
            # 特效快照：环形横扫 / 挥砍弧线（让客户端看到技能效果）
            effects = []
            for sr in self.sweep_rings[:10]:
                effects.append({"t": "ring", "x": round(sr["x"], 1), "y": round(sr["y"], 1),
                                "r": round(sr["r"], 1), "max_r": round(sr.get("max_r", sr["r"]), 1),
                                "color": list(sr.get("color", (190, 80, 230))[:3]), "life": round(sr.get("life", 0.3), 2)})
            for sa in self.slash_arcs[:8]:
                effects.append({"t": "arc", "x": round(sa.x, 1), "y": round(sa.y, 1),
                                "angle": round(sa.angle, 2), "radius": round(sa.radius, 1),
                                "color": list(getattr(sa, 'color', (190, 80, 230))[:3]),
                                "life": round(sa.lifetime, 2)})
            snap = {
                "started": True,
                "time_left": getattr(self, 'time_left', 0),
                "wave": getattr(self, 'wave_count', 0) if hasattr(self, 'wave_count') else 0,
                "players": [
                    {"x": round(self.player.x, 1), "y": round(self.player.y, 1), "hp": int(self.player.hp),
                     "max_hp": int(self.player.max_hp), "alive": self.player.alive,
                     "downed": bool(getattr(self.player, 'downed', False)),
                     "weapon": self.player.get_current_weapon().name if self.player.get_current_weapon() else "PISTOL"},
                    {"x": round(self.player2.x, 1) if self.player2 else round(self.player.x, 1),
                     "y": round(self.player2.y, 1) if self.player2 else round(self.player.y, 1),
                     "hp": int(self.player2.hp) if self.player2 else 0,
                     "max_hp": int(self.player2.max_hp) if self.player2 else 1,
                     "alive": bool(self.player2 and self.player2.alive),
                     "downed": bool(self.player2 and getattr(self.player2, 'downed', False)),
                     "weapon": self.player2.get_current_weapon().name if (self.player2 and self.player2.get_current_weapon()) else "PISTOL"},
                ],
                "enemies": enems,
                "projectiles": projs,
                "effects": effects,
            }
            self.net_host.send_snapshot({"type": "snapshot", "data": snap})
        except Exception as e:
            logger.warning(f"快照发送失败: {e}")

    def _get_local_ip(self):
        """获取本机局域网IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _net_start_host(self):
        """启动主机监听"""
        from net import NetHost
        self._net_stop()
        self.net_role = "host"
        self.net_host = NetHost(self.net_port)
        if self.net_host.start():
            self.state = GameState.NET_WAIT
            self.floating_texts = []
        else:
            self.net_role = None
            self.net_host = None

    def _net_join(self):
        """以客户端身份连接主机"""
        from net import NetClient
        self._net_stop()
        self.net_role = "client"
        ip = (self.net_ip_input or "127.0.0.1").strip()
        self.net_client = NetClient(ip, self.net_port)
        ok = self.net_client.start()
        if not ok:
            self.net_role = None
            self.net_client = None
            self.state = GameState.NET_MULTIPLAYER
            return
        self.state = GameState.NET_WAIT

    def _net_stop(self):
        """停止网络会话（返回联机界面）"""
        if self.net_host:
            self.net_host.stop()
            self.net_host = None
        if self.net_client:
            self.net_client.stop()
            self.net_client = None
        self.net_role = None
        self.net_started = False
        self.state = GameState.NET_MULTIPLAYER

    def _net_host_start_game(self):
        """主机：客户端已连接，进入装备选择（P1/P2），完成后开始双人网络游戏"""
        if not self.net_host or not self.net_host.connected:
            return
        self.multiplayer_mode = "network"
        self.net_started = True
        self.equip_p2_phase = False
        self.selected_weapon = None
        self.selected_character = None
        self.state = GameState.EQUIP_SELECT
