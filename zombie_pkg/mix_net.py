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
        # v2.5.7 同屏多人房间配置持久化（名字/武器/角色/阵营）
        self.mp_room_cfgs = {}  # {"1": {"name": str, "weapon": str, "char": str, "team": int}, ...}
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
                    # v2.5.7 多人房间配置持久化
                    _mrc = data.get("mp_room_cfgs", {})
                    if isinstance(_mrc, dict):
                        self.mp_room_cfgs = {}
                        for _k, _v in _mrc.items():
                            if isinstance(_v, dict):
                                self.mp_room_cfgs[str(_k)] = {
                                    k2: v2 for k2, v2 in _v.items()
                                    if isinstance(v2, (str, int, float, bool))}
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
            "mp_room_cfgs": getattr(self, 'mp_room_cfgs', {}) or {},
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
        # v2.5.8：网络客户端的开发者面板交互（本地 P1）
        try:
            if self.dev_mode:
                _any_open = any(st.panel_open for st in (getattr(self, 'dev_states', None) or {}).values())
                if _any_open:
                    self._update_dev_panel(pygame.mouse.get_pos(), pygame.mouse.get_pressed(),
                                           self.touch_events, self.scale)
        except Exception:
            pass
        # v2.2.9 应用主机下发的房间配置（幂等，welcome 到达后生效一次）
        try:
            _rc = getattr(self.net_client, 'room_cfg', None)
            if _rc and not getattr(self, '_net_room_cfg_applied', False):
                self._net_room_cfg_applied = True
                try:
                    from config import GameMode
                    if _rc.get("game_mode"):
                        _gm = _rc["game_mode"]
                        if hasattr(GameMode, _gm):
                            self.config.game_mode = GameMode[_gm]
                    if _rc.get("difficulty"):
                        self.config.difficulty = _rc["difficulty"]
                    if "pvp_enabled" in _rc:
                        self.config.pvp_enabled = bool(_rc["pvp_enabled"])
                    if "pvp_teams" in _rc:
                        self.config.pvp_teams = max(1, int(_rc["pvp_teams"]) or 2)
                    if "coop_player_count" in _rc:
                        self.coop_player_count = max(2, min(4, int(_rc["coop_player_count"]) or 2))
                    if "map" in _rc:
                        self.room_map_idx = int(_rc["map"]) % 6
                except Exception:
                    pass
        except Exception:
            pass
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
            # v2.2.13 触控端附带瞄准角（主机据此驱动客户端玩家实体射击方向）
            _aim = None
            try:
                if self.config.control_mode == ControlMode.TOUCH:
                    _aim = round(float(math.degrees(getattr(self.client_aim, 'angle', 0))), 1)
            except Exception:
                _aim = None
            self.net_client.send_input({
                "mx": round(float(mx), 3), "my": round(float(my), 3),
                "shoot": bool(shoot), "skill": bool(skill),
                "throw": False, "sprint": False,
                "aim": _aim,
            })
        # 主机断开 → 返回联机界面
        if not self.net_client.connected:
            self.floating_texts.append(FloatingText(0, 0, "与主机断开连接", color=CRIMSON, lifetime=2.0))
            self._net_stop()
            self.state = GameState.NET_MULTIPLAYER

    def _update_net_host(self, dt):
        """v2.2.13 主机驱动客户端玩家实体：消费 net_host.inputs（移动/射击/技能）。
        此前输入只入库无人消费 → 网络玩家原地木桩、无法战斗（核心修复）"""
        if not self.net_host or not self.net_started:
            return
        if self.state not in (GameState.PLAYING, GameState.DIALOGUE, GameState.PAUSED):
            return
        try:
            for _idx in list(self.net_host.clients.keys()):
                _inp = self.net_host.get_input(_idx)
                _ent = getattr(self, f"player{_idx + 1}", None)
                if _ent is None or not getattr(_ent, 'alive', True) or getattr(_ent, 'downed', False):
                    continue
                # 移动
                _mx = float(_inp.get("mx", 0) or 0)
                _my = float(_inp.get("my", 0) or 0)
                _spd = getattr(_ent, 'move_speed', 180) * getattr(_ent, 'speed_mult', 1.0)
                _n = math.hypot(_mx, _my)
                if _n > 0.01:
                    _ent.x += _mx / _n * _spd * dt
                    _ent.y += _my / _n * _spd * dt
                # 射击（aim 为 None/缺失时用实体朝向）
                # v2.5.6：蓄力武器（AWM/轨道炮）按住蓄力，松开才开火一次（与本地一致）
                _shoot_now = bool(_inp.get("shoot", False))
                _w = _ent.get_current_weapon()
                _fire_ang = None
                if _w is not None and getattr(_w, "hold_charge", False):
                    _saved = getattr(_ent, "_awm_saved", None)
                    if _shoot_now:
                        _aim0 = _inp.get("aim")
                        _ent._awm_saved = (math.radians(float(_aim0)) if _aim0 is not None
                                           else math.radians(getattr(_ent, 'facing_angle', 0)))
                        _shoot_now = False
                    elif _saved is not None:
                        _fire_ang = _saved
                        _ent._awm_saved = None
                elif getattr(_ent, "_awm_saved", None) is not None:
                    _ent._awm_saved = None
                if _shoot_now or _fire_ang is not None:
                    if _w and _w.can_fire():
                        if _fire_ang is not None:
                            _ang = _fire_ang
                        else:
                            _aim = _inp.get("aim")
                            _ang = math.radians(float(_aim)) if _aim is not None else math.radians(getattr(_ent, 'facing_angle', 0))
                        try:
                            _dmg_m = getattr(getattr(_ent, 'buff_manager', None), 'get_damage_mult', lambda: 1.0)()
                        except Exception:
                            _dmg_m = 1.0
                        _projs = _w.fire(_ent.x, _ent.y, _ang,
                                         getattr(_ent, 'damage_mult', 1.0) * _dmg_m * getattr(_ent, 'damage_multiplier', 1.0),
                                         getattr(_ent, 'speed_mult', 1.0), player=_ent)
                        if _projs:
                            self.projectiles.extend(_projs)
                # 技能（简化为实体已解锁的首个技能：手雷/钩爪等）
                if bool(_inp.get("skill", False)):
                    self._net_drive_skill(_ent, _idx)
        except Exception as _e:
            logger.warning(f"主机驱动客户端玩家失败: {_e}")

    def _net_drive_skill(self, ent, idx):
        """主机端驱动客户端玩家实体施放技能（仅常见技能最小实现）"""
        try:
            from weapons import Weapon, WeaponType
            from config import SkillType
            sts = [k for k, sk in getattr(ent, 'skill_tree', None).skills.items() if sk and sk.current_level > 0] if getattr(ent, 'skill_tree', None) else []
            if not sts:
                return
            st = sts[0]
            _ang = getattr(ent, 'facing_angle', 0)
            if st == SkillType.GRENADE:
                _w = Weapon(WeaponType.GRENADE)
                self.projectiles.extend(_w.fire(ent.x, ent.y, math.radians(_ang),
                                                getattr(ent, 'damage_multiplier', 1.0), 1.0, player=ent))
            elif st == SkillType.GRAPPLE_PULL:
                rg = getattr(ent, 'riot_gear', None)
                if rg is not None and rg.grapple_cooldown <= 0 and not rg.grapple_active:
                    _r = rg.grapple_max_range
                    rg.use_grapple(ent.x + math.cos(math.radians(_ang)) * _r,
                                   ent.y + math.sin(math.radians(_ang)) * _r,
                                   ent.x, ent.y, None)
        except Exception:
            pass

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
            # v2.5.7 PvP 毒圈：同步给客户端（否则客户端看不到圈外遮罩）
            _zone = None
            try:
                _z = getattr(self, 'pvp_zone', None)
                if _z:
                    _zone = {"cx": round(_z["cx"], 1), "cy": round(_z["cy"], 1),
                             "r": round(_z["r"], 1), "dps": round(_z.get("dps", 0.0), 1),
                             "phase": int(_z.get("phase", 0))}
            except Exception:
                _zone = None
            snap = {
                "started": True,
                "time_left": getattr(self, 'time_left', 0),
                "wave": getattr(self, 'wave_count', 0) if hasattr(self, 'wave_count') else 0,
                "players": self._snapshot_players(),
                "enemies": enems,
                "projectiles": projs,
                "effects": effects,
                "zone": _zone,
            }
            self.net_host.send_snapshot({"type": "snapshot", "data": snap})
        except Exception as e:
            logger.warning(f"快照发送失败: {e}")

    def _snapshot_players(self):
        """主机：把所有玩家（P1..P4）序列化为快照 players 列表（与客户端索引对应）"""
        _slots = [("player", self.player)]
        for _attr in ("player2", "player3", "player4"):
            _slots.append((_attr, getattr(self, _attr, None)))
        out = []
        for _attr, _p in _slots:
            if _p is None:
                out.append({"x": 0.0, "y": 0.0, "hp": 0, "max_hp": 1, "alive": False,
                            "downed": False, "weapon": "PISTOL"})
                continue
            out.append({
                "x": round(_p.x, 1), "y": round(_p.y, 1), "hp": int(_p.hp),
                "max_hp": int(_p.max_hp), "alive": bool(_p.alive),
                "downed": bool(getattr(_p, 'downed', False)),
                "weapon": _p.get_current_weapon().name if _p.get_current_weapon() else "PISTOL",
                # v2.2.13 PvPvE：同步阵营（客户端区分敌我渲染）
                "team": int(getattr(_p, 'team_id', 0) or 0),
            })
        return out

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
        # v2.2.9 网络房间配置同步：主机把房间配置随欢迎消息下发客户端
        try:
            _rc = {
                "game_mode": self.config.game_mode.name if hasattr(self.config, 'game_mode') and hasattr(self.config.game_mode, 'name') else "TIMED",
                "difficulty": getattr(self.config, 'difficulty', 'normal'),
                "pvp_enabled": bool(getattr(self.config, 'pvp_enabled', False)),
                "pvp_teams": int(getattr(self.config, 'pvp_teams', 2) or 2),
                "coop_player_count": int(getattr(self, 'coop_player_count', 2) or 2),
                "map": int(getattr(self, 'room_map_idx', 0) or 0),
            }
        except Exception:
            _rc = {}
        try:
            self.net_port = max(1024, min(65535, int(getattr(self, 'net_port_input', '26000') or '26000')))
        except Exception:
            self.net_port = 26000
        self.net_host = NetHost(self.net_port, room_cfg=_rc)
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
        try:
            self.net_port = max(1024, min(65535, int(getattr(self, 'net_port_input', '26000') or '26000')))
        except Exception:
            self.net_port = 26000
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
