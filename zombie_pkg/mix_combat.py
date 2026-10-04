# -*- coding: utf-8 -*-
"""CombatMixin - 由 game.py 自动拆分，逻辑等价"""

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

class CombatMixin:
    def _spawn_grenade(self, x, y, angle_deg, player):
        """生成手雷（P2 用）"""
        ang = math.radians(angle_deg)
        proj = Projectile(x, y, math.cos(ang) * 12, math.sin(ang) * 12,
                          250 * player.damage_multiplier, 400, ORANGE, 6,
                          explosive=True, explosion_radius=180, gravity=0.1)
        self.projectiles.append(proj)

    def _collect_drop(self, drop, player):
        """拾取掉落物（玩家参数化版）"""
        try:
            from codex import PICKABLE_TEXTS
            from config import ItemType
            if drop.item_type == ItemType.HEALTH_PACK:
                player.heal(30)
                self.floating_texts.append(FloatingText(drop.x, drop.y - 20, "+30HP", color=GREEN, lifetime=1.2))
            elif drop.item_type == ItemType.AMMO_BOX:
                for w in player.weapons:
                    if hasattr(w, 'current_ammo') and w.current_ammo != "∞":
                        w.current_ammo = min(w.max_ammo, w.current_ammo + 15)
            elif drop.item_type == ItemType.SPEED_BOOST:
                player.speed = player.base_speed * 1.5
                self.floating_texts.append(FloatingText(drop.x, drop.y - 20, "加速!", color=AMBER, lifetime=1.2))
            elif drop.item_type == ItemType.EXP_BOOST:
                pass
            if drop.alive:
                drop.alive = False
            if drop in list(getattr(getattr(self, 'world', None), 'items', [])):
                self.world.items.remove(drop)
        except Exception:
            pass

    def _throw_grenade_at(self, target_x, target_y):
        """在指定位置投掷手雷 - 超增强爆炸效果"""
        # 多层冲击波
        self.particles.spawn_explosion(target_x, target_y, ORANGE, 120)
        self.particles.spawn_explosion(target_x, target_y, RED, 80)
        self.particles.spawn_explosion(target_x, target_y, FIRE_YELLOW, 60)
        self.camera.shake(35, 1.0)

        # 多层冲击波环
        for i in range(8):
            radius = 20 + i * 25
            alpha = int(220 - i * 25)
            shock_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(shock_surf, (255, 255, 255, alpha), (radius, radius), radius, max(2, int(4 - i * 0.4)))
            self.screen.blit(shock_surf, (int((target_x - self.camera.x) * self.scale) - radius,
                                         int((target_y - self.camera.y) * self.scale) - radius))

        # 烟雾 - 大量
        for _ in range(35):
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(10, 120)
            sx = target_x + math.cos(angle) * dist
            sy = target_y + math.sin(angle) * dist
            self.particles.spawn(sx, sy, SMOKE_GRAY, 1, (20, 40), (-2, 2), (1.5, 3.5))

        # 火焰 - 大量
        for _ in range(25):
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(5, 80)
            fx = target_x + math.cos(angle) * dist
            fy = target_y + math.sin(angle) * dist
            self.particles.spawn(fx, fy, FIRE_ORANGE, 1, (10, 25), (-3, 3), (0.5, 2.0))
            self.particles.spawn(fx, fy, FIRE_YELLOW, 1, (5, 15), (-2, 2), (0.3, 1.5))

        # 火花
        for _ in range(30):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(5, 20)
            sx = target_x + math.cos(angle) * random.uniform(0, 30)
            sy = target_y + math.sin(angle) * random.uniform(0, 30)
            self.particles.spawn(sx, sy, (255, 255, 200), 1, (3, 8), (-speed, speed), (0.2, 1.0))

        self.particles.spawn(target_x, target_y, RED, 35, (8, 25), (-15, 15), (0.3, 1.2))
        self.particles.spawn(target_x, target_y, YELLOW, 25, (5, 18), (-12, 12), (0.2, 1.0))
        self.particles.spawn(target_x, target_y, WHITE, 15, (3, 10), (-8, 8), (0.1, 0.5))

        for enemy in self.enemies:
            dist = math.hypot(enemy.x - target_x, enemy.y - target_y)
            if dist < 200:
                damage = 300 * (1 - dist / 200)
                if dist > 0:
                    push_x = (enemy.x - target_x) / dist * 120
                    push_y = (enemy.y - target_y) / dist * 120
                    enemy.x += push_x
                    enemy.y += push_y
                    enemy.knockdown(0.5)
                enemy.take_damage(damage)
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, damage))
                if not enemy.alive:
                    self._on_enemy_death(enemy)

    def _call_airstrike_at(self, target_x, target_y):
        """在指定位置呼叫空袭"""
        self.floating_texts.append(FloatingText(
            target_x, target_y - 50, "空袭来袭!", color=CRIMSON, lifetime=2.0
        ))
        if not hasattr(self, 'airstrikes'):
            self.airstrikes = []
        self.airstrikes.append({"x": target_x, "y": target_y, "timer": 2.0, "warned": False})

    def _cycle_throwable(self):
        """切换到下一种有库存的投掷物"""
        if not hasattr(self.player, 'throwables'):
            self.player.throwables = {}
        # 从当前选中的下一个开始找有库存的
        start_idx = self.throwable_types.index(self.selected_throwable) if self.selected_throwable in self.throwable_types else 0
        for i in range(1, len(self.throwable_types) + 1):
            idx = (start_idx + i) % len(self.throwable_types)
            gtype = self.throwable_types[idx]
            if self.player.throwables.get(gtype, 0) > 0:
                self.selected_throwable = gtype
                name = self.throwable_names.get(gtype, gtype)
                count = self.player.throwables[gtype]
                self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                    f"切换: {name} x{count}", color=self.throwable_colors.get(gtype, WHITE), lifetime=1.2))
                return
        # 没有任何有库存的投掷物
        self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
            "没有投掷物！", color=RED, lifetime=1.0))

    def _get_selected_throwable(self):
        """获取当前选中且有库存的投掷物类型，没有则返回None"""
        if not hasattr(self.player, 'throwables'):
            self.player.throwables = {}
        gtype = self.selected_throwable
        if self.player.throwables.get(gtype, 0) > 0:
            return gtype
        # 当前选中的没库存了，自动找第一个有库存的
        for t in self.throwable_types:
            if self.player.throwables.get(t, 0) > 0:
                self.selected_throwable = t
                return t
        return None

    def _throw_grenade(self):
        """投掷物：朝鼠标/瞄准方向投掷"""
        grenade_type = self._get_selected_throwable()
        if not grenade_type:
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                "没有投掷物！(按E切换)", color=RED, lifetime=1.0))
            return

        self.player.throwables[grenade_type] -= 1

        # 计算投掷方向
        if self.config.control_mode == ControlMode.KEYBOARD:
            mouse_pos = pygame.mouse.get_pos()
            target_x = mouse_pos[0] / self.scale + self.camera.x
            target_y = mouse_pos[1] / self.scale + self.camera.y
        else:
            angle_rad = math.radians(self.player.facing_angle)
            target_x = self.player.x + math.cos(angle_rad) * 300
            target_y = self.player.y + math.sin(angle_rad) * 300

        dx = target_x - self.player.x
        dy = target_y - self.player.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            vx = dx / dist * 400
            vy = dy / dist * 400
        else:
            vx, vy = 0, -400

        if not hasattr(self, 'grenades_in_flight'):
            self.grenades_in_flight = []

        self.grenades_in_flight.append({
            "type": grenade_type,
            "x": self.player.x, "y": self.player.y,
            "vx": vx, "vy": vy,
            "timer": 1.5,  # 飞行时间
            "target_x": target_x, "target_y": target_y,
        })
        self.assets.play_sound("grenade_throw")

    def _throw_grenade_aimed(self, angle, distance_ratio):
        """瞄准投掷：根据角度和距离比例投掷到指定位置"""
        grenade_type = self._get_selected_throwable()
        if not grenade_type:
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                "没有投掷物！(按E切换)", color=RED, lifetime=1.0))
            return

        self.player.throwables[grenade_type] -= 1

        # 根据瞄准角度和距离比例计算目标位置
        dist = self.throwable_max_dist * max(0.1, min(1.0, distance_ratio))
        target_x = self.player.x + math.cos(angle) * dist
        target_y = self.player.y + math.sin(angle) * dist

        dx = target_x - self.player.x
        dy = target_y - self.player.y
        total_dist = math.hypot(dx, dy)
        # 飞行速度根据距离调整，保持飞行时间约1.2秒
        speed = total_dist / 1.2 if total_dist > 0 else 300
        if total_dist > 0:
            vx = dx / total_dist * speed
            vy = dy / total_dist * speed
        else:
            vx, vy = 0, -300

        if not hasattr(self, 'grenades_in_flight'):
            self.grenades_in_flight = []

        self.grenades_in_flight.append({
            "type": grenade_type,
            "x": self.player.x, "y": self.player.y,
            "vx": vx, "vy": vy,
            "timer": 1.2,
            "target_x": target_x, "target_y": target_y,
        })
        self.assets.play_sound("grenade_throw")

    def _start_melee_attack(self, weapon, angle):
        """开始近战攻击"""
        self.melee_attack_active = True
        base_rate = getattr(weapon, "fire_rate", 0.3)
        
        # 应用近战攻速技能
        melee_speed_skill = self.player.skill_tree.get_skill(SkillType.MELEE_SPEED)
        speed_mult = 1.0
        if melee_speed_skill and melee_speed_skill.current_level > 0:
            speed_mult = 1.0 + melee_speed_skill.current_level * 0.2
        effective_rate = base_rate / speed_mult
        
        self.melee_attack_timer = effective_rate * 0.8
        self.melee_attack_duration = effective_rate * 0.8
        self.melee_attack_angle = angle
        
        # 应用近战范围技能
        base_range = getattr(weapon, "range", 60)
        melee_range_skill = self.player.skill_tree.get_skill(SkillType.MELEE_RANGE)
        if melee_range_skill and melee_range_skill.current_level > 0:
            base_range *= (1.0 + melee_range_skill.current_level * 0.15)
        # 泰坦符文：近战攻击范围+20%
        if hasattr(self, 'rune_manager'):
            base_range *= (1.0 + self.rune_manager.get_bonus("melee_range_mult"))
        self.melee_attack_range = base_range
        
        self.melee_attack_damage = weapon.melee_attack_damage
        self.melee_attack_weapon = weapon
        self.melee_hit_enemies = set()
        
        # 连击系统：增加连击计数
        if not hasattr(self, 'melee_combo_count'):
            self.melee_combo_count = 0
            self.melee_combo_timer = 0
        self.melee_combo_count += 1
        self.melee_combo_timer = 2.0  # 连击2秒内有效
        
        if weapon.weapon_type == WeaponType.CHAINSAW:
            self.melee_attack_duration = 0.15
            self.melee_attack_timer = 0.15

    def _update_melee_attack(self, dt):
        """更新近战攻击，进行伤害判定"""
        if not self.melee_attack_active:
            return
        
        self.melee_attack_timer -= dt
        attack_progress = 1 - (self.melee_attack_timer / max(0.01, self.melee_attack_duration))
        
        if attack_progress < 0.7:
            attack_arc = math.pi * 0.8
            for enemy in self.enemies:
                if id(enemy) in self.melee_hit_enemies:
                    continue
                dx = enemy.x - self.player.x
                dy = enemy.y - self.player.y
                dist = math.hypot(dx, dy)
                if dist > self.melee_attack_range + enemy.size:
                    continue
                enemy_angle = math.atan2(dy, dx)
                angle_diff = abs(((enemy_angle - self.melee_attack_angle + math.pi) % (math.pi * 2)) - math.pi)
                if angle_diff > attack_arc / 2:
                    continue
                damage = self.melee_attack_damage
                
                # 应用近战伤害技能
                melee_dmg_skill = self.player.skill_tree.get_skill(SkillType.MELEE_DAMAGE)
                if melee_dmg_skill and melee_dmg_skill.current_level > 0:
                    damage *= (1.0 + melee_dmg_skill.current_level * 0.25)
                
                # 应用狂暴技能（低血量增伤）
                berserker_skill = self.player.skill_tree.get_skill(SkillType.BERSERKER)
                if berserker_skill and berserker_skill.current_level > 0:
                    hp_ratio = self.player.hp / self.player.max_hp
                    if hp_ratio < 0.5:
                        dmg_bonus = berserker_skill.current_level * 0.3
                        if berserker_skill.current_level >= 3 and hp_ratio < 0.2:
                            dmg_bonus += 0.5
                        damage *= (1.0 + dmg_bonus)
                
                # 应用连击大师技能
                combo_skill = self.player.skill_tree.get_skill(SkillType.COMBO_MASTER)
                if combo_skill and combo_skill.current_level > 0:
                    max_layers = [0, 5, 8, 10][combo_skill.current_level]
                    per_layer = [0, 0.05, 0.08, 0.10][combo_skill.current_level]
                    combo_count = min(getattr(self, 'melee_combo_count', 0), max_layers)
                    damage *= (1.0 + combo_count * per_layer)
                
                # 匕首暴击
                if self.melee_attack_weapon and self.melee_attack_weapon.weapon_type == WeaponType.KNIFE:
                    crit_chance = getattr(self.melee_attack_weapon, "crit_chance", 0.3)
                    if random.random() < crit_chance:
                        damage *= 2
                        self.damage_numbers.append(DamageNumber(enemy.x, enemy.y - 20, int(damage), is_crit=True))
                
                # 近战吸血
                lifesteal_skill = self.player.skill_tree.get_skill(SkillType.MELEE_LIFESTEAL)
                if lifesteal_skill and lifesteal_skill.current_level > 0:
                    steal_amount = damage * lifesteal_skill.current_level * 0.1
                    self.player.hp = min(self.player.max_hp, self.player.hp + steal_amount)
                
                if self.melee_attack_weapon and self.melee_attack_weapon.weapon_type == WeaponType.BAT:
                    knockback = getattr(self.melee_attack_weapon, "knockback", 15)
                    enemy.x += math.cos(self.melee_attack_angle) * knockback
                    enemy.y += math.sin(self.melee_attack_angle) * knockback
                enemy.take_damage(damage)
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, int(damage)))
                self.melee_hit_enemies.add(id(enemy))
                self.particles.spawn(enemy.x, enemy.y, enemy.color, 8, size_range=(3, 6), velocity_range=(-50, 50), lifetime_range=(0.3, 0.6))
                if not enemy.alive:
                    self._on_enemy_death(enemy)
        
        if self.melee_attack_timer <= 0:
            self.melee_attack_active = False
            self.melee_attack_weapon = None
        
        # 更新连击计时器
        if hasattr(self, 'melee_combo_timer') and self.melee_combo_timer > 0:
            self.melee_combo_timer -= dt
            if self.melee_combo_timer <= 0:
                self.melee_combo_count = 0

    def _spawn_enemy_throwable(self, throw_data):
        """生成怪物投掷物"""
        dx = throw_data["target_x"] - throw_data["x"]
        dy = throw_data["target_y"] - throw_data["y"]
        dist = math.hypot(dx, dy)
        if dist > 0:
            speed = 250
            vx = dx / dist * speed
            vy = dy / dist * speed
        else:
            vx, vy = 0, -250
        
        self.enemy_throwables.append({
            "type": throw_data["type"],
            "x": throw_data["x"], "y": throw_data["y"],
            "vx": vx, "vy": vy,
            "timer": dist / 250 if dist > 0 else 1.0,
            "target_x": throw_data["target_x"], "target_y": throw_data["target_y"],
            "damage": throw_data["damage"],
            "height": 0,  # 抛物线高度
            "owner": throw_data.get("owner", "boss"),
        })
        self.assets.play_sound("grenade_throw")
