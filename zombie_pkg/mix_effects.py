# -*- coding: utf-8 -*-
"""EffectsMixin - 由 game.py 自动拆分，逻辑等价"""

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

class EffectsMixin:
    def _create_turret_effect(self, tx, ty):
        if not hasattr(self, 'turrets'):
            self.turrets = []
        turret_skill = self.player.skill_tree.get_skill(SkillType.TURRET) if self.player else None
        if turret_skill and turret_skill.current_level > 0:
            t_damage = int(turret_skill.get_effective_damage())
            t_range = int(turret_skill.get_effective_radius())
            is_max = turret_skill.is_maxed()
        else:
            t_damage = 30
            t_range = 250
            is_max = False
        self.turrets.append({"x": tx, "y": ty, "timer": 10.0, "fire_timer": 0, "damage": t_damage, "range": t_range, "multi": is_max})
        if self.session:
            self.session.add_turret_deployed()

    def _update_turrets(self, dt):
        if not hasattr(self, 'turrets'):
            self.turrets = []

        for turret in self.turrets[:]:
            turret["timer"] -= dt
            turret["fire_timer"] -= dt

            if turret["fire_timer"] <= 0:
                turret["fire_timer"] = 0.5
                t_range = turret.get("range", 250)
                t_damage = turret.get("damage", 30)
                t_multi = turret.get("multi", False)
                # 找最近的1-2个目标
                targets = []
                for enemy in self.enemies:
                    dist = math.hypot(enemy.x - turret["x"], enemy.y - turret["y"])
                    if dist < t_range:
                        targets.append((dist, enemy))
                targets.sort(key=lambda t: t[0])
                max_targets = 2 if t_multi else 1
                for _, closest in targets[:max_targets]:
                    dx = closest.x - turret["x"]
                    dy = closest.y - turret["y"]
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        proj = Projectile(
                            turret["x"], turret["y"],
                            dx / dist * 12, dy / dist * 12,
                            t_damage, 300, YELLOW, 4, pierce=2
                        )
                        self.projectiles.append(proj)
                        self.particles.spawn(turret["x"], turret["y"], YELLOW, 3)

            if turret["timer"] <= 0:
                self.particles.spawn_explosion(turret["x"], turret["y"], GRAY, 10)
                self.turrets.remove(turret)

    def _create_plane_run(self, target_x, target_y, effects, direction=0, length=400, width=220, angle_offset=0):
        """长方形区域横扫轰炸：飞机沿direction方向飞过，炸弹网格密铺整个长方形区域"""
        rad = math.radians(direction + angle_offset)
        perp = rad + math.pi / 2
        # 飞机从远处沿direction飞来
        fly_dist = 900
        plane_x = target_x - math.cos(rad) * fly_dist
        plane_y = target_y - math.sin(rad) * fly_dist
        plane_speed = 620
        plane_vx = math.cos(rad) * plane_speed
        plane_vy = math.sin(rad) * plane_speed
        # 长方形区域网格炸弹（沿length列 × 垂直width行）
        cols = max(3, int(length / 70))
        rows = max(2, int(width / 70))
        bombs = []
        for i in range(cols):
            t = (i / max(1, cols - 1)) - 0.5
            lx = target_x + math.cos(rad) * t * length
            ly = target_y + math.sin(rad) * t * length
            for j in range(rows):
                wt = (j / max(1, rows - 1)) - 0.5
                bx = lx + math.cos(perp) * wt * width
                by = ly + math.sin(perp) * wt * width
                bombs.append({"x": bx, "y": by, "exploded": False})
        self.airstrikes.append({
            "type": "plane_run",
            "phase": "incoming",
            "plane_x": plane_x, "plane_y": plane_y,
            "plane_vx": plane_vx, "plane_vy": plane_vy,
            "target_x": target_x, "target_y": target_y,
            "bombs": bombs, "bomb_index": 0,
            "bomb_drop_timer": 0.0, "timer": 0,
            "effects": effects, "warned": False,
        })

    def _update_airstrikes(self, dt):
        """更新空袭效果 - 飞机呼啸+一行炸弹连锁爆炸"""
        if not hasattr(self, 'airstrikes'):
            self.airstrikes = []

        for strike in self.airstrikes[:]:
            strike["timer"] -= dt

            # 旧版单点空袭兼容
            if strike.get("type") != "plane_run":
                if strike["timer"] <= 0:
                    self._explode_airstrike(strike["x"], strike["y"], strike.get("effects", ["basic"]), strike.get("is_nuke", False))
                    self.airstrikes.remove(strike)
                elif strike["timer"] <= 1.0 and not strike.get("warned", False):
                    strike["warned"] = True
                    self.particles.spawn(strike["x"], strike["y"], RED, 30, size_range=(8, 15),
                                        velocity_range=(-5, 5), lifetime_range=(0.3, 0.8))
                continue

            # === 新版飞机轰炸 ===
            if strike["phase"] == "incoming":
                # 飞机飞行
                strike["plane_x"] += strike["plane_vx"] * dt
                strike["plane_y"] += strike["plane_vy"] * dt
                # 警告标记
                if not strike.get("warned", False):
                    strike["warned"] = True
                    for bomb in strike["bombs"]:
                        self.particles.spawn(bomb["x"], bomb["y"], RED, 15, size_range=(6, 12),
                                            velocity_range=(-3, 3), lifetime_range=(0.5, 1.0))
                # 飞机到达投弹点开始投弹
                dist_to_target = math.hypot(strike["plane_x"] - strike["target_x"],
                                           strike["plane_y"] - strike["target_y"])
                if dist_to_target < 200:
                    strike["phase"] = "bombing"
                    strike["bomb_drop_timer"] = 0.0

            elif strike["phase"] == "bombing":
                # 依次投弹并爆炸
                strike["bomb_drop_timer"] -= dt
                if strike["bomb_drop_timer"] <= 0 and strike["bomb_index"] < len(strike["bombs"]):
                    bomb = strike["bombs"][strike["bomb_index"]]
                    if not bomb["exploded"]:
                        bomb["exploded"] = True
                        self._explode_airstrike(bomb["x"], bomb["y"], strike.get("effects", ["basic"]))
                        self.assets.play_sound("explosion")
                    strike["bomb_index"] += 1
                    strike["bomb_drop_timer"] = 0.12  # 每0.12秒一枚，连锁爆炸

                # 飞机继续飞
                strike["plane_x"] += strike["plane_vx"] * dt
                strike["plane_y"] += strike["plane_vy"] * dt

                # 所有炸弹投完后结束
                if strike["bomb_index"] >= len(strike["bombs"]):
                    strike["phase"] = "done"
                    strike["timer"] = 1.0

            elif strike["phase"] == "done":
                if strike["timer"] <= 0:
                    self.airstrikes.remove(strike)

    def _explode_airstrike(self, x, y, effects=None, is_nuke=False):
        """空袭爆炸效果 - 支持累加附魔效果
        effects: ["basic", "fire", "emp", "nuke"]
        is_nuke: 是否为超级核爆（范围/伤害大幅提升）
        """
        if effects is None:
            effects = ["basic"]
        has_fire = "fire" in effects or is_nuke
        has_emp = "emp" in effects or is_nuke
        has_nuke = "nuke" in effects or is_nuke

        # 空袭伤害/半径随技能等级缩放
        airstrike_skill = self.player.skill_tree.get_skill(SkillType.AIRSTRIKE) if self.player else None
        if airstrike_skill and airstrike_skill.current_level > 0:
            as_damage = airstrike_skill.get_effective_damage()
            as_radius = airstrike_skill.get_effective_radius()
        else:
            as_damage = 400
            as_radius = 200
        explosion_radius = int(as_radius * 2.2 if has_nuke else as_radius)
        base_damage = int(as_damage * 3.0 if has_nuke else as_damage)
        shake_intensity = 60 if has_nuke else 25
        shake_duration = 1.5 if has_nuke else 1.0

        self.assets.play_sound("explosion")
        # 核心爆炸粒子
        self.particles.spawn_explosion(x, y, ORANGE, 200 if has_nuke else 150)
        self.particles.spawn_explosion(x, y, RED, 150 if has_nuke else 100)
        self.particles.spawn_explosion(x, y, FIRE_YELLOW, 120 if has_nuke else 80)
        self.particles.spawn_explosion(x, y, WHITE, 100 if has_nuke else 50)
        if has_nuke:
            self.particles.spawn_explosion(x, y, PURPLE, 120)
            self.particles.spawn_explosion(x, y, (255, 255, 255), 200)
            # 核爆冲天蘑菇云（单独渲染：火球+烟柱+蘑菇帽）
            self._spawn_nuke_mushroom(x, y)
        self.camera.shake(shake_intensity, shake_duration)

        # 冲击波环
        ring_count = 16 if has_nuke else 8
        for i in range(ring_count):
            radius = 20 + i * (30 if has_nuke else 25)
            self.particles.spawn(x, y, WHITE, 1, (radius, radius), (0, 0), (0.2, 0.4))

        # 烟雾
        smoke_count = 60 if has_nuke else 30
        for _ in range(smoke_count):
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(20, explosion_radius * 0.7)
            sx = x + math.cos(angle) * dist
            sy = y + math.sin(angle) * dist
            self.particles.spawn(sx, sy, SMOKE_GRAY, 1, (20, 40), (-3, 3), (2.0, 4.0))

        # 火焰粒子
        fire_count = 50 if has_nuke else 25
        for _ in range(fire_count):
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(10, explosion_radius * 0.5)
            fx = x + math.cos(angle) * dist
            fy = y + math.sin(angle) * dist
            self.particles.spawn(fx, fy, FIRE_ORANGE, 1, (10, 25), (-4, 4), (1.0, 2.5))

        # 火花
        for _ in range(30):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(8, 25)
            sx = x + math.cos(angle) * random.uniform(0, 40)
            sy = y + math.sin(angle) * random.uniform(0, 40)
            self.particles.spawn(sx, sy, (255, 255, 200), 1, (4, 10), (-speed, speed), (0.3, 1.5))

        # 燃烧区域（fire 效果）
        if has_fire:
            if not hasattr(self, 'fire_zones'):
                self.fire_zones = []
            fire_radius = 150 if has_nuke else 100
            self.fire_zones.append({
                "x": x, "y": y, "radius": fire_radius,
                "timer": 10.0 if has_nuke else 6.0, "damage_timer": 0.0,
            })
            self.floating_texts.append(FloatingText(x, y - 30, "燃烧区域!", color=FIRE_ORANGE, lifetime=1.5))

        # 伤害 + 击退
        for enemy in self.enemies:
            dist = math.hypot(enemy.x - x, enemy.y - y)
            if dist < explosion_radius:
                damage = base_damage * (1 - dist / explosion_radius)
                if dist > 0:
                    push_force = 200 if has_nuke else 100
                    push_x = (enemy.x - x) / dist * push_force
                    push_y = (enemy.y - y) / dist * push_force
                    enemy.x += push_x
                    enemy.y += push_y
                    enemy.knockdown(1.2 if has_nuke else 0.8)
                enemy.take_damage(damage)
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, damage, is_crit=True))
                # 燃烧DOT
                if has_fire:
                    enemy.apply_buff(BuffType.BURN, duration=5.0)
                # EMP眩晕
                if has_emp:
                    enemy.apply_buff(BuffType.STUN, duration=4.0 if has_nuke else 2.0)
                if not enemy.alive:
                    self._on_enemy_death(enemy)

        # 核爆：对玩家也有轻微自伤（远处），增加真实感
        if has_nuke:
            for _p in self._alive_players():
                pdist = math.hypot(_p.x - x, _p.y - y)
                if pdist < explosion_radius * 0.5:
                    _p.take_damage(20)  # 轻微自伤

    def _spawn_nuke_mushroom(self, x, y):
        """核爆冲天蘑菇云单独渲染：底部火球 + 冲天烟柱 + 顶部蘑菇帽"""
        import math as _m
        # 底部核心火球（更亮更白）
        self.particles.spawn_explosion(x, y, (255, 240, 200), 180)
        self.particles.spawn_explosion(x, y, (255, 200, 100), 120)
        self.particles.spawn_explosion(x, y, (255, 120, 40), 80)
        # 冲天烟柱（从地面高速上升，形成粗柱）
        for _ in range(110):
            px = x + random.uniform(-26, 26)
            py = y + random.uniform(-12, 8)
            self.particles.spawn(px, py, (95, 90, 95), 1,
                                 (28, 55), (random.uniform(-3, 3), -random.uniform(15, 24)), (2.5, 4.2))
        # 顶部蘑菇帽（水平扩散的烟，顶部翻卷）
        for _ in range(120):
            ang = random.uniform(0, _m.pi * 2)
            r = random.uniform(25, 125)
            capx = x + _m.cos(ang) * r
            capy = y - random.uniform(80, 150)
            self.particles.spawn(capx, capy, (130, 122, 115), 1,
                                 (26, 50), (_m.cos(ang) * random.uniform(4, 10), random.uniform(-4, 3)), (2.2, 3.8))
        # 顶部火红内焰（蘑菇帽下方）
        for _ in range(50):
            px = x + random.uniform(-42, 42)
            py = y - random.uniform(60, 105)
            self.particles.spawn(px, py, (255, 160, 70), 1,
                                 (20, 42), (random.uniform(-2, 2), -random.uniform(7, 14)), (1.6, 2.8))
        # 二次冲击烟圈（蘑菇云底部环形烟）
        for _ in range(40):
            ang = random.uniform(0, _m.pi * 2)
            r = random.uniform(20, 90)
            self.particles.spawn(x + _m.cos(ang) * r, y + _m.sin(ang) * r, (110, 105, 100), 1,
                                 (24, 44), (_m.cos(ang) * 4, _m.sin(ang) * 4 - 2), (2.0, 3.2))

    def _update_black_holes(self, dt):
        """更新黑洞效果"""
        if not hasattr(self, 'black_holes'):
            self.black_holes = []
        for bh in self.black_holes[:]:
            bh["timer"] -= dt
            # 吸引敌人
            for enemy in self.enemies:
                dist = math.hypot(enemy.x - bh["x"], enemy.y - bh["y"])
                if dist < bh["radius"] and dist > 20:
                    dx = bh["x"] - enemy.x
                    dy = bh["y"] - enemy.y
                    enemy.x += (dx / dist) * 3
                    enemy.y += (dy / dist) * 3
                if dist < 30:
                    enemy.take_damage(bh.get("damage", 30) * dt)
                    if not enemy.alive:
                        self._on_enemy_death(enemy)
            # 视觉效果
            self.particles.spawn(bh["x"], bh["y"], PURPLE, 5, (2, 5), (-2, 2), (0.3, 0.6))
            if bh["timer"] <= 0:
                self.particles.spawn_explosion(bh["x"], bh["y"], PURPLE, 30)
                self.black_holes.remove(bh)

    def _update_medic_pods(self, dt):
        """更新医疗舱"""
        if not hasattr(self, 'medic_pods'):
            self.medic_pods = []
        for pod in self.medic_pods[:]:
            pod["timer"] -= dt
            pod["heal_timer"] -= dt
            if pod["heal_timer"] <= 0:
                pod["heal_timer"] = 1.0
                dist = math.hypot(self.player.x - pod["x"], self.player.y - pod["y"])
                if dist < pod.get("radius", 100):
                    self.player.heal(15 if pod.get("purify") else 10)
                    if pod.get("purify"):
                        self.player.buff_manager.clear_debuffs()
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 40, "+10", color=GREEN, lifetime=0.5
                    ))
            self.particles.spawn(pod["x"], pod["y"], GREEN, 3, (2, 4), (-1, 1), (0.5, 1.0))
            if pod["timer"] <= 0:
                self.medic_pods.remove(pod)

    def _update_grenades(self, dt):
        """更新飞行中的投掷物"""
        if not hasattr(self, 'grenades_in_flight'):
            self.grenades_in_flight = []
        for g in self.grenades_in_flight[:]:
            g["x"] += g["vx"] * dt
            g["y"] += g["vy"] * dt
            g["timer"] -= dt
            # 拖尾粒子
            if g["type"] == "incendiary":
                self.particles.spawn(g["x"], g["y"], FIRE_ORANGE, 1, (4, 8), (-2, 2), (0.3, 0.6))
            elif g["type"] == "smoke":
                self.particles.spawn(g["x"], g["y"], SMOKE_GRAY, 1, (5, 10), (-2, 2), (0.5, 1.0))
            elif g["type"] == "emp":
                self.particles.spawn(g["x"], g["y"], CYAN, 1, (4, 8), (-2, 2), (0.3, 0.6))
            else:
                self.particles.spawn(g["x"], g["y"], ORANGE, 1, (3, 6), (-2, 2), (0.3, 0.6))

            if g["timer"] <= 0:
                self._detonate_grenade(g)
                self.grenades_in_flight.remove(g)

    def _detonate_grenade(self, g):
        """投掷物爆炸效果"""
        x, y = g["x"], g["y"]
        gtype = g["type"]
        effects = g.get("effects", [gtype])  # 兼容旧格式
        has_nuke = "nuke" in effects
        has_fire = "fire" in effects or has_nuke
        has_frost = "frost" in effects or has_nuke
        has_poison = "poison" in effects or has_nuke

        if gtype == "incendiary":
            # 燃烧弹：大范围持续燃烧区域
            self.assets.play_sound("fire_explosion")
            self.camera.shake(15, 0.8)
            # 初始爆炸
            self.particles.spawn_explosion(x, y, FIRE_ORANGE, 80)
            self.particles.spawn_explosion(x, y, FIRE_YELLOW, 60)
            # 创建持续燃烧区域
            if not hasattr(self, 'fire_zones'):
                self.fire_zones = []
            self.fire_zones.append({
                "x": x, "y": y, "radius": 120,
                "timer": 8.0, "damage_timer": 0.0,
            })
            self.floating_texts.append(FloatingText(x, y - 30, "燃烧区域!", color=FIRE_ORANGE, lifetime=2.0))

        elif gtype == "smoke":
            # 烟雾弹：大范围烟雾，减速致盲
            self.assets.play_sound("smoke_pop")
            if not hasattr(self, 'smoke_zones'):
                self.smoke_zones = []
            self.smoke_zones.append({
                "x": x, "y": y, "radius": 150,
                "timer": 10.0, "damage_timer": 0.0,
            })
            # 大量烟雾粒子
            for _ in range(60):
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(0, 100)
                sx = x + math.cos(angle) * dist
                sy = y + math.sin(angle) * dist
                self.particles.spawn(sx, sy, SMOKE_GRAY, 1, (15, 30), (-3, 3), (3.0, 6.0))
            self.floating_texts.append(FloatingText(x, y - 30, "烟雾弹!", color=SMOKE_GRAY, lifetime=2.0))

        elif gtype == "cluster":
            # 集束炸弹：爆炸后分裂多枚小炸弹
            self.assets.play_sound("explosion")
            self.camera.shake(20, 1.0)
            self.particles.spawn_explosion(x, y, ORANGE, 100)
            self.particles.spawn_explosion(x, y, RED, 80)
            # 分裂6枚小炸弹
            for i in range(6):
                angle = (i / 6) * math.pi * 2
                bx = x + math.cos(angle) * 80
                by = y + math.sin(angle) * 80
                self._explode_airstrike(bx, by)
            self.floating_texts.append(FloatingText(x, y - 30, "集束爆炸!", color=ORANGE, lifetime=2.0))

        elif gtype == "emp":
            # EMP脉冲：范围眩晕+破盾
            self.assets.play_sound("emp_pulse")
            self.camera.shake(10, 0.5)
            # 电磁脉冲环
            for i in range(8):
                radius = 20 + i * 25
                alpha = int(180 - i * 20)
                self.particles.spawn(x, y, CYAN, 1, (radius, radius), (0, 0), (0.3, 0.5))
            # 范围效果
            for enemy in self.enemies:
                dist = math.hypot(enemy.x - x, enemy.y - y)
                if dist < 180:
                    # 眩晕（Boss有抗性，apply_buff内部处理）
                    enemy.apply_buff(BuffType.STUN, duration=3.0)
                    enemy.take_damage(50)
                    self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, 50, color=CYAN))
            self.floating_texts.append(FloatingText(x, y - 30, "EMP脉冲!", color=CYAN, lifetime=2.0))

        elif gtype in ("frag", "frag_fire", "frag_frost", "frag_poison", "frag_nuke"):
            # 技能手雷：根据附魔类型有不同效果，伤害/半径随技能等级缩放
            grenade_skill = self.player.skill_tree.get_skill(SkillType.GRENADE) if self.player else None
            if grenade_skill and grenade_skill.current_level > 0:
                scaled_damage = grenade_skill.get_effective_damage()
                scaled_radius = grenade_skill.get_effective_radius()
            else:
                scaled_damage = 300
                scaled_radius = 200
            explosion_radius = int(scaled_radius * 1.5 if has_nuke else scaled_radius)
            base_damage = int(scaled_damage * 1.6 if has_nuke else scaled_damage)
            
            self.assets.play_sound("explosion")
            self.particles.spawn_explosion(x, y, ORANGE, 120)
            self.particles.spawn_explosion(x, y, RED, 80)
            self.particles.spawn_explosion(x, y, FIRE_YELLOW, 60)
            if has_nuke:
                self.particles.spawn_explosion(x, y, WHITE, 150)
                self.particles.spawn_explosion(x, y, PURPLE, 100)
            self.camera.shake(50 if has_nuke else 35, 1.2 if has_nuke else 1.0)
            
            # 冲击波环
            ring_count = 12 if has_nuke else 8
            for i in range(ring_count):
                radius = 20 + i * 25
                alpha = int(220 - i * 18)
                self.particles.spawn(x, y, WHITE, 1, (radius, radius), (0, 0), (0.2, 0.4))
            
            # 烟雾
            for _ in range(40 if has_nuke else 25):
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(10, explosion_radius * 0.6)
                self.particles.spawn(x + math.cos(angle) * dist, y + math.sin(angle) * dist,
                    SMOKE_GRAY, 1, (15, 30), (-2, 2), (1.0, 2.5))
            
            # 火焰
            for _ in range(30 if has_nuke else 20):
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(5, explosion_radius * 0.4)
                self.particles.spawn(x + math.cos(angle) * dist, y + math.sin(angle) * dist,
                    FIRE_ORANGE, 1, (8, 20), (-3, 3), (0.4, 1.5))
            
            # 范围伤害
            for enemy in self.enemies:
                dist = math.hypot(enemy.x - x, enemy.y - y)
                if dist < explosion_radius:
                    damage = base_damage * (1 - dist / explosion_radius)
                    if dist > 0:
                        push = 180 if has_nuke else 120
                        enemy.x += (enemy.x - x) / dist * push
                        enemy.y += (enemy.y - y) / dist * push
                    enemy.knockdown(0.8 if has_nuke else 0.5)
                    enemy.take_damage(damage)
                    self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, damage, damage_type="explosion"))
                    
                    # 附魔效果
                    if has_fire:
                        enemy.apply_buff(BuffType.BURN, duration=5.0)
                    if has_frost:
                        enemy.apply_buff(BuffType.SLOW, duration=3.0)
                    if has_poison:
                        enemy.apply_buff(BuffType.POISON, duration=5.0)
                    
                    if not enemy.alive:
                        self._on_enemy_death(enemy)
            
            # 燃烧附魔：创建持续燃烧区域
            if has_fire:
                if not hasattr(self, 'fire_zones'):
                    self.fire_zones = []
                self.fire_zones.append({
                    "x": x, "y": y, "radius": 120 if has_nuke else 80,
                    "timer": 8.0 if has_nuke else 5.0, "damage_timer": 0.0,
                })
            
            # 冰霜附魔：创建减速区域
            if has_frost:
                if not hasattr(self, 'smoke_zones'):
                    self.smoke_zones = []
                self.smoke_zones.append({
                    "x": x, "y": y, "radius": 150 if has_nuke else 100,
                    "timer": 6.0 if has_nuke else 4.0, "damage_timer": 0.0,
                })
            
            # 显示附魔名称
            enchant_names = {
                "frag": "手雷爆炸!",
                "frag_fire": "燃烧手雷!",
                "frag_frost": "冰霜手雷!",
                "frag_poison": "剧毒手雷!",
                "frag_nuke": "核弹爆炸!!!",
            }
            enchant_colors = {
                "frag": ORANGE,
                "frag_fire": FIRE_ORANGE,
                "frag_frost": CYAN,
                "frag_poison": POISON_GREEN,
                "frag_nuke": PURPLE,
            }
            self.floating_texts.append(FloatingText(x, y - 30, enchant_names.get(gtype, "手雷爆炸!"), 
                                                     color=enchant_colors.get(gtype, ORANGE), lifetime=2.0))

    def _update_enemy_throwables(self, dt):
        """更新怪物投掷物"""
        if not hasattr(self, 'enemy_throwables'):
            self.enemy_throwables = []
        for g in self.enemy_throwables[:]:
            # 实时追踪最近的存活玩家（投掷物会调整方向砸向玩家，显著提高命中率）
            _tgt = min(self._alive_players(), key=lambda p: math.hypot(p.x - g["x"], p.y - g["y"]), default=self.player)
            dxp = _tgt.x - g["x"]
            dyp = _tgt.y - g["y"]
            dp = math.hypot(dxp, dyp)
            if dp > 1:
                spd = 260
                g["vx"] = dxp / dp * spd
                g["vy"] = dyp / dp * spd
            g["x"] += g["vx"] * dt
            g["y"] += g["vy"] * dt
            g["timer"] -= dt
            # 抛物线高度计算
            progress = 1 - max(0, g["timer"]) / max(0.1, g["timer"] + dt)
            g["height"] = math.sin(progress * math.pi) * 40
            
            # 拖尾粒子
            if g["type"] == "fire":
                self.particles.spawn(g["x"], g["y"], FIRE_ORANGE, 1, (4, 8), (-2, 2), (0.3, 0.6))
            elif g["type"] == "acid":
                self.particles.spawn(g["x"], g["y"], POISON_GREEN, 1, (4, 8), (-2, 2), (0.3, 0.6))
            elif g["type"] == "curse":
                self.particles.spawn(g["x"], g["y"], PURPLE, 1, (4, 8), (-2, 2), (0.3, 0.6))
            else:
                self.particles.spawn(g["x"], g["y"], GRAY, 1, (3, 6), (-2, 2), (0.3, 0.6))
            
            # 检测命中玩家（P1/P2 双判定，判定范围加大，保证能砸中移动中的玩家）
            hit = False
            for _p in self._alive_players():
                if math.hypot(g["x"] - _p.x, g["y"] - _p.y) < 40:
                    self._detonate_enemy_throwable(g)
                    hit = True
                    break
            if hit:
                self.enemy_throwables.remove(g)
                continue
            
            if g["timer"] <= 0:
                self._detonate_enemy_throwable(g)
                self.enemy_throwables.remove(g)

    def _detonate_enemy_throwable(self, g):
        """怪物投掷物爆炸效果
        投掷僵尸的投掷物属于僵尸阵营：对玩家造成伤害，不对僵尸造成伤害
        """
        x, y = g["x"], g["y"]
        gtype = g["type"]
        damage = g["damage"]

        if gtype == "fire":
            # 燃烧瓶：小范围燃烧区域
            self.assets.play_sound("fire_explosion")
            self.camera.shake(8, 0.5)
            self.particles.spawn_explosion(x, y, FIRE_ORANGE, 40)
            if not hasattr(self, 'fire_zones'):
                self.fire_zones = []
            self.fire_zones.append({
                "x": x, "y": y, "radius": 80,
                "timer": 5.0, "damage_timer": 0.0,
                "from_enemy": True,
            })
            # 直接伤害玩家（P1/P2 双判定）
            for _p in self._alive_players():
                if math.hypot(x - _p.x, y - _p.y) < 90:
                    _p.take_damage(int(damage * 0.5), damage_type="fire")
                    _p.buff_manager.add_buff(BuffType.BURN, duration=3.0)

        elif gtype == "acid":
            # 酸液瓶：腐蚀+持续伤害
            self.assets.play_sound("poison_splash")
            self.particles.spawn_explosion(x, y, POISON_GREEN, 50)
            for _p in self._alive_players():
                if math.hypot(x - _p.x, y - _p.y) < 80:
                    _p.take_damage(int(damage), damage_type="melee")
                    _p.buff_manager.add_buff(BuffType.CORROSION, duration=5.0)
                    _p.buff_manager.add_buff(BuffType.POISON, duration=4.0)

        elif gtype == "curse":
            # 诅咒瓶：多种debuff
            self.assets.play_sound("curse_cast")
            self.particles.spawn_explosion(x, y, PURPLE, 40)
            for _p in self._alive_players():
                if math.hypot(x - _p.x, y - _p.y) < 80:
                    _p.take_damage(int(damage * 0.7), damage_type="magic")
                    _p.buff_manager.add_buff(BuffType.CURSE, duration=6.0)
                    _p.buff_manager.add_buff(BuffType.WEAKEN, duration=5.0)

        else:  # rock
            # 石块：物理伤害+眩晕
            self.assets.play_sound("rock_impact")
            self.camera.shake(10, 0.6)
            if self.camera2:
                self.camera2.shake(10, 0.6)
            self.particles.spawn_explosion(x, y, GRAY, 30)
            for _p in self._alive_players():
                if math.hypot(x - _p.x, y - _p.y) < 60:
                    _p.take_damage(int(damage), damage_type="melee")
                    if random.random() < 0.4:
                        _p.buff_manager.add_buff(BuffType.STUN, duration=1.0)

    def _spawn_horde_rewards(self):
        """尸潮过后根据规模刷新奖励"""
        scale = getattr(self.horde_manager, 'current_scale', 1)
        horde_count = getattr(self.horde_manager, 'horde_count', 0)
        
        # 奖励数量和类型根据规模、时间、难度综合计算
        base_count = {1: 1, 2: 2, 3: 3, 4: 4}.get(scale, 1)
        # 时间系数：每存活5分钟，奖励+1（上限+2）
        time_bonus = min(2, int(self.horde_manager.total_time / 300))
        # 难度系数：困难+1，地狱+1（限制奖励泛滥）
        diff_bonus = {"困难": 1, "地狱": 1, "hard": 1, "hell": 1}.get(self.config.difficulty, 0)
        reward_count = min(3, base_count + time_bonus // 2 + diff_bonus)
        
        # 奖励生成中心：优先使用 boss 死亡位置，否则使用玩家位置
        _boss_pos = getattr(self, 'last_boss_death_pos', None)
        center_x, center_y = _boss_pos if _boss_pos else (self.player.x, self.player.y)
        
        for i in range(reward_count):
            # 在中心附近随机位置生成
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(80, 200)
            rx = center_x + math.cos(angle) * dist
            ry = center_y + math.sin(angle) * dist
            
            # 奖励类型选择：根据规模和运气
            luck = self.rune_manager.get_bonus("drop_rate_mult") if hasattr(self, 'rune_manager') else 0
            chest_chance = 0.22 + min(0.18, self.horde_manager.total_time / 900) + diff_bonus * 0.06 + luck * 0.08
            golden_chance = 0.04 + min(0.08, self.horde_manager.total_time / 1500) + luck * 0.04
            rune_chance = 0.13 + luck * 0.08
            mystery_chance = 0.07
            
            roll = random.random()
            if scale >= 4 and roll < golden_chance:
                item_type = ItemType.GOLDEN_CHEST  # 巨型尸潮有概率出黄金宝箱
            elif scale >= 3 and roll < chest_chance + golden_chance:
                item_type = ItemType.TREASURE_CHEST
            elif roll < chest_chance + rune_chance:
                item_type = ItemType.RUNE
            elif roll < chest_chance + rune_chance + mystery_chance:
                item_type = ItemType.MYSTERY_BOX
            else:
                # 武器箱或道具
                if random.random() < 0.55:
                    item_type = ItemType.WEAPON_BOX
                else:
                    item_type = random.choice([
                        ItemType.HEALTH_PACK, ItemType.AMMO_BOX, ItemType.DAMAGE_BOOST,
                        ItemType.SPEED_BOOST, ItemType.SHIELD_REPAIR, ItemType.BUFF_CHARM
                    ])
            
            self.world.items.append(SpecialItem(rx, ry, item_type))
        
        # 显示奖励提示
        scale_names = {1: "小型", 2: "中型", 3: "大型", 4: "巨型"}
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 60,
            f"{scale_names.get(scale, '')}尸潮击退! 奖励已刷新",
            color=GOLD, lifetime=3.0
        ))
        self.assets.play_sound("level_up")

    def _update_fire_zones(self, dt):
        """更新燃烧区域"""
        if not hasattr(self, 'fire_zones'):
            self.fire_zones = []
        for zone in self.fire_zones[:]:
            zone["timer"] -= dt
            zone["damage_timer"] -= dt
            # 持续火焰粒子
            if random.random() < 0.5:
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(0, zone["radius"])
                fx = zone["x"] + math.cos(angle) * dist
                fy = zone["y"] + math.sin(angle) * dist
                self.particles.spawn(fx, fy, FIRE_ORANGE, 1, (8, 16), (-3, 3), (0.8, 1.5))
                self.particles.spawn(fx, fy, FIRE_YELLOW, 1, (5, 10), (-2, 2), (0.5, 1.0))
            # 伤害
            if zone["damage_timer"] <= 0:
                zone["damage_timer"] = 0.5
                for enemy in self.enemies:
                    dist = math.hypot(enemy.x - zone["x"], enemy.y - zone["y"])
                    if dist < zone["radius"]:
                        enemy.take_damage(15)
                        enemy.apply_buff(BuffType.BURN, duration=3.0)
                # 玩家也会被烧（敌方火区对玩家造成伤害，P1/P2 双判定）
                for _p in self._alive_players():
                    pdist = math.hypot(_p.x - zone["x"], _p.y - zone["y"])
                    if pdist < zone["radius"]:
                        _p.take_damage(5, damage_type="fire")
            if zone["timer"] <= 0:
                self.fire_zones.remove(zone)

    def _update_smoke_zones(self, dt):
        """更新烟雾区域"""
        if not hasattr(self, 'smoke_zones'):
            self.smoke_zones = []
        for zone in self.smoke_zones[:]:
            zone["timer"] -= dt
            zone["damage_timer"] -= dt
            # 持续烟雾粒子
            if random.random() < 0.3:
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(0, zone["radius"])
                sx = zone["x"] + math.cos(angle) * dist
                sy = zone["y"] + math.sin(angle) * dist
                self.particles.spawn(sx, sy, SMOKE_GRAY, 1, (10, 20), (-2, 2), (2.0, 4.0))
            # 减速效果
            if zone["damage_timer"] <= 0:
                zone["damage_timer"] = 1.0
                for enemy in self.enemies:
                    dist = math.hypot(enemy.x - zone["x"], enemy.y - zone["y"])
                    if dist < zone["radius"]:
                        enemy.apply_buff(BuffType.SLOW, duration=2.0)
            if zone["timer"] <= 0:
                self.smoke_zones.remove(zone)

    def _update_buff_visuals(self, dt):
        """更新玩家和敌人的buff视觉粒子效果"""
        if not self.config.render_buff_effects:
            return
        from buff import BUFF_CONFIGS
        # 玩家buff
        self._spawn_buff_particles(self.player, dt, BUFF_CONFIGS)
        # 敌人buff
        for enemy in self.enemies:
            if enemy.alive and hasattr(enemy, 'buff_manager'):
                self._spawn_buff_particles(enemy, dt, BUFF_CONFIGS)

    def _spawn_buff_particles(self, entity, dt, buff_configs):
        """为实体的活跃buff生成视觉粒子
        两种模式:
        - splatter(喷溅型): 粒子从身体向外飞溅，受重力下落，如流血
        - attached(附着型): 粒子附着在身体表面，轻微上升或静止，如燃烧/冻结/中毒
        """
        if not hasattr(entity, 'buff_manager') or not entity.buff_manager.buffs:
            return
        # 实体尺寸（用于附着粒子的分布范围）
        ent_size = getattr(entity, 'size', 14)
        ent_radius = ent_size
        ent_height = ent_size * 2

        for buff_type, buff_data in entity.buff_manager.buffs.items():
            config = buff_configs.get(buff_type, {})
            fx_color = config.get("fx_particle")
            if not fx_color:
                continue
            fx_rate = config.get("fx_rate", 0.2)
            fx_count = config.get("fx_count", 1)
            fx_size = config.get("fx_size", (4, 8))
            fx_mode = config.get("fx_mode", "attached")
            fx_second = config.get("fx_second_color")
            fx_attached_lift = config.get("fx_attached_lift", False)

            # 按概率生成粒子
            if random.random() >= fx_rate * dt * 60:
                continue

            for _ in range(fx_count):
                if fx_mode == "splatter":
                    # ===== 喷溅型：从身体中心向外飞溅 =====
                    offset_x = random.uniform(-ent_radius * 0.3, ent_radius * 0.3)
                    offset_y = random.uniform(-ent_height * 0.3, ent_height * 0.1)
                    px = entity.x + offset_x
                    py = entity.y + offset_y
                    # 随机方向向外飞溅，速度中等
                    angle = random.uniform(0, math.pi * 2)
                    speed = random.uniform(25, 70)
                    vx = math.cos(angle) * speed
                    vy = math.sin(angle) * speed - random.uniform(10, 30)  # 略微向上初速度
                    lifetime = random.uniform(0.3, 0.8)
                    size = random.randint(*fx_size)
                    self.particles.spawn_particle(px, py, vx, vy, fx_color, lifetime, size)
                    # 喷溅型偶尔有小血滴
                    if fx_second and random.random() < 0.4:
                        self.particles.spawn_particle(px, py, vx * 0.6, vy * 0.6, fx_second,
                                            random.uniform(0.2, 0.5), size // 2)

                else:  # attached 附着型
                    # ===== 附着型：在身体表面生成，不远离 =====
                    # 在身体轮廓范围内随机位置
                    offset_x = random.uniform(-ent_radius * 0.8, ent_radius * 0.8)
                    offset_y = random.uniform(-ent_height * 0.7, ent_height * 0.1)
                    px = entity.x + offset_x
                    py = entity.y + offset_y
                    # 水平速度极小，保持在身体附近
                    vx = random.uniform(-4, 4)
                    if fx_attached_lift:
                        # 火焰/毒泡：轻微上升，抵消部分重力形成飘动效果
                        vy = random.uniform(-14, -6)
                    else:
                        # 冰霜/骨屑：几乎静止，轻微飘动
                        vy = random.uniform(-3, 2)
                    lifetime = random.uniform(0.15, 0.45)  # 短寿命，不远离身体
                    size = random.randint(*fx_size)
                    self.particles.spawn_particle(px, py, vx, vy, fx_color, lifetime, size)
                    # 附着型的第二颜色（如火焰的黄色内核）
                    if fx_second and random.random() < 0.6:
                        self.particles.spawn_particle(px, py, vx * 0.5, vy * 0.8, fx_second,
                                            random.uniform(0.1, 0.3), max(1, size // 2))

    def _update_scythe_sweep(self, weapon, dt):
        """死神镰刀换弹期间：玩家周围形成大圆形横扫区域，持续伤害 + 环形刀光特效"""
        if not self.player or not self.player.alive:
            return
        r = getattr(weapon, "sweep_radius", 210)
        dps = getattr(weapon, "sweep_damage", 85)
        dps *= (self.player.damage_multiplier *
                self.player.buff_manager.get_damage_mult() *
                getattr(self.player, 'damage_mult', 1.0))
        # 圆形横扫：对范围内所有敌人持续伤害
        for e in list(self.enemies):
            if not getattr(e, "alive", True):
                continue
            dx, dy = e.x - self.player.x, e.y - self.player.y
            if math.hypot(dx, dy) <= r:
                e.take_damage(dps * dt, damage_type="aoe")
        # 视觉特效
        self._sweep_fx_timer = getattr(self, "_sweep_fx_timer", 0.0) - dt
        if self._sweep_fx_timer <= 0:
            self._sweep_fx_timer = 0.09
            self.sweep_rings.append({
                "x": self.player.x, "y": self.player.y,
                "r": r * 0.25, "max_r": r, "color": (175, 60, 220),
                "width": max(4, int(r * 0.05)), "life": 0.38, "max_life": 0.38,
            })
        self._sweep_arc_timer = getattr(self, "_sweep_arc_timer", 0.0) - dt
        if self._sweep_arc_timer <= 0:
            self._sweep_arc_timer = 0.22
            import random as _r
            ang = _r.uniform(0, math.pi * 2)
            self.slash_arcs.append(SlashArc(
                self.player.x, self.player.y, ang, r,
                (180, 60, 220), lifetime=0.4, kind="scythe",
                start_radius=r * 0.55, end_angle_offset=2.9))
        self._sweep_sound_timer = getattr(self, "_sweep_sound_timer", 0.0) - dt
        if self._sweep_sound_timer <= 0:
            self._sweep_sound_timer = 0.42
            self.assets.play_sound_random(["melee_swing", "shoot_pistol"])

    def _check_combos(self):
        """检查组合技（多个技能达到等级后触发），解锁时给被动加成并实时弹出"""
        try:
            unlocked = self.records.get_combo_unlocked()
            p = self.player
            for cname, cfg in COMBO_SKILLS.items():
                if cname in unlocked:
                    continue
                ok = True
                for st_name, min_lvl in cfg["require"].items():
                    st = getattr(SkillType, st_name, None)
                    if st is None:
                        ok = False
                        break
                    sk = p.skill_tree.get_skill(st)
                    if not sk or sk.current_level < min_lvl:
                        ok = False
                        break
                if ok:
                    self.records.unlock_combo(cname)
                    for k, v in cfg["bonus"].items():
                        if k == "damage":
                            p.damage_multiplier += v
                        elif k == "fire_rate":
                            p.fire_rate_mult = getattr(p, 'fire_rate_mult', 1.0) + v
                        elif k == "reduce":
                            p.dmg_reduce = min(0.5, getattr(p, 'dmg_reduce', 0) + v)
                    self.ach_toast_queue.append({"key": "combo", "desc": f"组合技解锁: {cname}", "timer": 3.5})
                    self.floating_texts.append(FloatingText(p.x, p.y - 60, f"组合技! {cname}", color=PURPLE, lifetime=2.0))
        except Exception:
            pass

    def _enemy_coin_reward(self, enemy):
        # 基础金币（按敌人类别）
        if getattr(enemy, 'is_boss', False):
            base = 100
        else:
            et = getattr(enemy, 'enemy_type', None)
            name = getattr(et, 'name', str(et)).upper()
            elite_types = {"ZOMBIE_TANK", "ZOMBIE_BERSERKER", "ZOMBIE_RANGED", "ZOMBIE_EXPLODER",
                           "ZOMBIE_PHANTOM", "ZOMBIE_HEALER", "ZOMBIE_SHIELD", "ZOMBIE_SPLITTER",
                           "ZOMBIE_WRAITH", "ZOMBIE_THROWER", "ZOMBIE_WANG", "BOSS_WANG"}
            if name in elite_types:
                base = random.randint(6, 12)
            else:
                base = random.randint(1, 4)
        # 金币结算根据难度进行加成（难度越高金币越多，鼓励挑战高难度）
        try:
            diff_cfg = DIFFICULTY_CONFIG.get(self.config.difficulty, {})
            mult = diff_cfg.get("enemy_hp_mult", 1.0)
        except Exception:
            mult = 1.0
        return max(1, int(base * mult))

    def _on_enemy_death(self, enemy):
        if getattr(enemy, '_death_processed', False):
            return
        enemy._death_processed = True
        # 记录击杀
        # Mod 敌人死亡钩子
        try:
            trigger_hook(HOOK_ENEMY_DEATH, enemy, self.player)
        except Exception:
            pass
        if self.session:
            self.session.add_kill(enemy.enemy_type)
        # 击杀金币奖励（积分另一形式，跨局即时累加）
        coin_reward = self._enemy_coin_reward(enemy)
        if coin_reward > 0:
            try:
                self.records.add_coins(coin_reward)
                self.session_coins_earned = getattr(self, 'session_coins_earned', 0) + coin_reward
                self.floating_texts.append(FloatingText(
                    enemy.x, enemy.y - 40, f"+{coin_reward}金币", color=GOLD, lifetime=1.2))
            except Exception:
                pass
        # 击败王某标记（解锁死神镰刀购买）
        _et = getattr(enemy, 'enemy_type', None)
        if _et is not None and getattr(_et, 'name', '').upper() in ('ZOMBIE_WANG', 'BOSS_WANG'):
            try:
                self.records.mark_wang_defeated()
                self._unlock_achievement("wang_slayer")
                # 图鉴解锁王某
                try:
                    _cu = codex_unlock_manager.unlock_monster("BOSS_WANG")
                    if _cu:
                        self._codex_unlock_toast(_cu, "王某")
                except Exception:
                    pass
                self.floating_texts.append(FloatingText(
                    enemy.x, enemy.y - 60, "击败王某! 解锁死神镰刀", color=(180, 60, 220), lifetime=3.0))
            except Exception:
                pass
        # 播放击杀音效
        if getattr(enemy, "is_boss", False):
            self.assets.play_sound("boss_death")
            self.last_boss_death_pos = (enemy.x, enemy.y)
            # 击杀Boss获得宝箱奖励（奖励随难度与游戏时间变化）
            self._grant_boss_chest(enemy)
        else:
            self.assets.play_sound_random(["zombie_death", "zombie_groan"])
        self.particles.spawn_blood(enemy.x, enemy.y, 15)
        self.particles.spawn_explosion(enemy.x, enemy.y, enemy.color, 10)
        self.particles.spawn_death_aura(enemy.x, enemy.y, enemy.color)

        # 分裂者分裂+溅射
        if getattr(enemy, "is_splitter", False) and enemy.split_count < 1:
            enemy.split_count += 1
            # 分裂溅射伤害
            splash_r = 80
            self._damage_players_near(enemy.x, enemy.y, splash_r, 15, dtype="aoe")  # 溅射伤害（P1/P2）
            self.particles.spawn_explosion(enemy.x, enemy.y, BLOOD_RED, 25)
            for _ in range(2):
                offset_x = random.uniform(-20, 20)
                offset_y = random.uniform(-20, 20)
                small_enemy = Enemy(enemy.x + offset_x, enemy.y + offset_y, 
                                   EnemyType.ZOMBIE_FAST, 1, self.config.difficulty)
                small_enemy.size = 8
                small_enemy.max_hp = small_enemy.hp = 15
                small_enemy.damage = 5
                self.enemies.append(small_enemy)
                try:
                    _cu = codex_unlock_manager.unlock_monster(small_enemy.enemy_type.name if hasattr(small_enemy, "enemy_type") else small_enemy.type.name)
                    if _cu:
                        self._codex_unlock_toast(_cu, small_enemy.enemy_type.name if hasattr(small_enemy, "enemy_type") else small_enemy.type.name)
                except Exception:
                    pass
            self.floating_texts.append(FloatingText(
                enemy.x, enemy.y - 30, "分裂!", color=BLOOD_RED, lifetime=1.5
            ))

        # 战吼击杀统计
        if self.war_cry_timer > 0 and self.session:
            self.session.add_war_cry_kill()
        # 流血状态下击杀统计
        if self.player.buff_manager.has_buff(BuffType.BLEED) and self.session:
            self.session.add_bleeding_kill()
        # 中毒击杀统计（敌人死时带有中毒buff且血量较低）
        if enemy.buff_manager.has_buff(BuffType.POISON) and self.session:
            self.session.add_poison_kill()

        exp_value = getattr(enemy, "exp", 10)
        self.exp_orbs.append(ExpOrb(enemy.x, enemy.y, exp_value))
        gained_score = getattr(enemy, "score", 10)
        self.player.score += gained_score
        if self.session:
            self.session.add_score(gained_score)

        # 吸血光环
        vampire_skill = self.player.skill_tree.get_skill(SkillType.VAMPIRE_AURA)
        if vampire_skill and vampire_skill.current_level > 0:
            heal_amount = self.player.max_hp * 0.05 * vampire_skill.current_level
            self.player.heal(heal_amount)
            self.lifesteal_flash = min(1.0, self.lifesteal_flash + 0.4)
        # 嗜血：击杀后获得加速buff
        bloodlust_skill = self.player.skill_tree.get_skill(SkillType.BLOODLUST)
        if bloodlust_skill and bloodlust_skill.current_level > 0:
            bl_durations = {1: 3.0, 2: 4.0, 3: 5.0}
            bl_mults = {1: 1.2, 2: 1.35, 3: 1.5}
            dur = bl_durations.get(bloodlust_skill.current_level, 3.0)
            self.player.buff_manager.add_buff(BuffType.SPEED_BOOST, duration=dur)
            sb = self.player.buff_manager.get_buff(BuffType.SPEED_BOOST)
            if sb:
                sb.value = bl_mults.get(bloodlust_skill.current_level, 1.2)

        # 武器掉落
        # 问题3a: 应用难度掉落率倍率
        drop_mult = getattr(self, '_difficulty_drop_mult', 1.0)
        if random.random() < 0.008 * drop_mult:
            weapon_types = [WeaponType.RIFLE, WeaponType.SHOTGUN, WeaponType.SNIPER,
                          WeaponType.MACHINE_GUN, WeaponType.ROCKET_LAUNCHER, WeaponType.FLAMETHROWER,
                          WeaponType.CROSSBOW, WeaponType.GRENADE_LAUNCHER, WeaponType.PLASMA_RIFLE,
                          WeaponType.RAILGUN, WeaponType.MINIGUN, WeaponType.DOUBLE_BARREL,
                          WeaponType.SEMI_AUTO_SNIPER]
            new_weapon = random.choice(weapon_types)
            self.player.add_weapon(new_weapon)
            # 记录武器收集
            if self.session:
                self.session.add_weapon_collected()
            # 播放音效
            self.assets.play_sound("weapon_switch")
            self.floating_texts.append(FloatingText(enemy.x, enemy.y, f"获得{Weapon(new_weapon).name}!"))

        # Boss掉落疫苗（标记drops_vaccine的必出，限时模式必出，其他模式15%概率）
        if getattr(enemy, "is_boss", False) and not self.has_vaccine:
            if getattr(enemy, "drops_vaccine", False) or self.config.game_mode == GameMode.TIMED or random.random() < 0.15:
                self.has_vaccine = True
                try:
                    self._unlock_achievement("vaccine_hunter")
                except Exception:
                    pass
                self.floating_texts.append(FloatingText(enemy.x, enemy.y, "获得疫苗！", color=GREEN, lifetime=3.0))
                if self.session:
                    self.session.set_got_vaccine(True)

        if getattr(enemy, "is_boss", False):
            if enemy.enemy_type == EnemyType.BOSS_LONG:
                self.boss_kills["long"] += 1
            elif enemy.enemy_type == EnemyType.BOSS_XIANG:
                self.boss_kills["xiang"] += 1

        self.enemies.remove(enemy)

    def _grant_boss_chest(self, enemy):
        """击杀Boss掉落宝箱奖励：金币/经验/治疗/符文/弹药，奖励随难度与游戏时间变化"""
        # 难度倍率
        diff_mult = {"简单": 0.8, "普通": 1.0, "困难": 1.4, "噩梦": 2.0}.get(getattr(self, 'difficulty', '普通'), 1.0)
        # 游戏时间（秒）
        elapsed = 0.0
        hm = getattr(self, 'horde_manager', None)
        if hm is not None:
            elapsed = getattr(hm, 'total_time', 0.0)
        time_bonus = 1.0 + min(1.5, elapsed / 600.0)  # 随时间增长，最多+150%
        mult = diff_mult * time_bonus
        if self.session:
            self.session.add_chest_opened()
        rewards = []
        # 金币（随难度与时间）
        coin = int((120 + elapsed * 0.2) * mult)
        try:
            self.records.add_coins(coin)
        except Exception:
            pass
        rewards.append(f"+{coin}金币")
        # 大量经验
        exp = int((400 + elapsed * 0.4) * mult)
        self.player.gain_exp(exp)
        rewards.append(f"+{exp}经验")
        # 治疗
        heal = int(60 * diff_mult)
        self.player.heal(heal)
        rewards.append(f"+{heal}HP")
        # 符文（击杀Boss保底出一个）
        luck = self.rune_manager.get_bonus("drop_rate_mult") if hasattr(self, 'rune_manager') else 0
        rune_type = random_rune(luck_bonus=luck + 0.3)
        if hasattr(self, 'rune_manager') and self._gain_rune(rune_type):
            rewards.append(f"符文: {RUNE_CONFIG[rune_type]['name']}")
            self._apply_rune_bonuses()
        else:
            rewards.append("符文(已满)")
        # 弹药补满
        for weapon in self.player.weapons:
            if hasattr(weapon, 'current_ammo') and weapon.current_ammo != "Inf":
                weapon.current_ammo = weapon.max_ammo
        # 计分
        score_gain = int(800 * diff_mult)
        if self.session:
            self.session.add_score(score_gain)
        self.player.score += score_gain
        # 特效与提示
        particles = getattr(self, 'particles', None)
        flt = getattr(self, 'floating_texts', None)
        self.assets.play_sound("pickup_treasure")
        if particles is not None:
            particles.spawn_explosion(enemy.x, enemy.y, (255, 215, 0), 40)
            particles.spawn(enemy.x, enemy.y, (255, 255, 200), 25)
        reward_text = "击杀奖励: " + ", ".join(rewards[:4])
        if flt is not None:
            flt.append(FloatingText(enemy.x, enemy.y - 60, reward_text, color=(255, 215, 0), lifetime=4.0))
