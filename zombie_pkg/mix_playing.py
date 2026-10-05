# -*- coding: utf-8 -*-
"""PlayingMixin - 由 game.py 自动拆分，逻辑等价"""

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

class PlayingMixin:
    def _update_rescue(self, dt):
        """双人救援系统：倒地→队友救援复活（同屏靠近自动救援 / 网络 8 秒自动复活）；全倒地则结束"""
        p1, p2 = self.player, self.player2
        if not p1 or not p2:
            return False
        # 1) 触发倒地：hp<=0 且未倒地 → 倒地（不立即死亡；alive 可能已被 take_damage 置 False，必须照常倒地）
        for p in (p1, p2):
            if p.hp <= 0 and not p.downed:
                p.downed = True
                p.alive = False
                p.downed_timer = 0.0
                p.rescue_progress = 0.0
                self.floating_texts.append(FloatingText(
                    p.x, p.y - 40, "倒地！等待救援...", color=(240, 230, 120), lifetime=2.0))
                self.assets.play_sound_random(["player_hurt", "hurt"])
        # 2) 救援 / 自动复活
        for p in (p1, p2):
            if not p.downed:
                continue
            p.downed_timer += dt
            mate = p2 if p is p1 else p1
            rescued = False
            if self.multiplayer_mode == "same_screen":
                near = mate is not None and not mate.downed and math.hypot(mate.x - p.x, mate.y - p.y) < 120
                if near:
                    p.rescue_progress += dt
                    if p.rescue_progress >= 2.5:
                        rescued = True
                else:
                    p.rescue_progress = 0.0
            else:
                # 网络联机：8 秒自动复活（跨设备救援不便，给保底）
                if p.downed_timer >= 8.0:
                    rescued = True
            if rescued:
                p.downed = False
                p.alive = True
                p.hp = int(p.max_hp * 0.5)
                p.rescue_progress = 0.0
                p.invincible_timer = 1.5
                self.floating_texts.append(FloatingText(p.x, p.y - 40, "已复活!", color=GREEN, lifetime=1.5))
                try:
                    self.assets.play_sound("heal")
                except Exception:
                    pass
        # 3) 双人全部倒地 → 游戏结束
        return bool((p1.downed or not p1.alive) and (p2.downed or not p2.alive))

    def _alive_players(self):
        """返回存活的玩家列表（单人=[P1]，双人=[P1,P2]）"""
        ps = [self.player]
        if self.player2:
            ps.append(self.player2)
        return [p for p in ps if p is not None and getattr(p, 'alive', True) and not getattr(p, 'downed', False)]

    def _damage_players_near(self, x, y, radius, damage, dtype="melee", from_front=True, shake_cam=None):
        """对半径内所有存活玩家造成伤害（双人双判定），shake_cam=(cam, intensity, dur) 可选震屏"""
        hit_any = False
        for p in self._alive_players():
            if math.hypot(x - p.x, y - p.y) < radius:
                p.take_damage(damage, damage_type=dtype, from_front=from_front, attack_x=x, attack_y=y)
                hit_any = True
        if hit_any and shake_cam:
            cam, intensity, dur = shake_cam
            if cam is not None:
                cam.shake(intensity, dur)
        return hit_any

    def _enemy_collide_damage(self, enemy, player, camera):
        """近战碰撞伤害（P1/P2 共用）：推挤、伤害、盾反、debuff、震屏"""
        if (not enemy.grappled) and enemy.get_rect().colliderect(player.get_rect()):
            dx = enemy.x - player.x
            dy = enemy.y - player.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                min_dist = enemy.size + player.size + 2
                if dist < min_dist:
                    push_x = (dx / dist) * (min_dist - dist) * 0.5
                    push_y = (dy / dist) * (min_dist - dist) * 0.5
                    enemy.x += push_x
                    enemy.y += push_y
                    player.x -= push_x
                    player.y -= push_y
            if enemy.knockdown_timer <= 0:
                angle_to_enemy = math.atan2(dy, dx)
                facing_rad = math.radians(player.facing_angle)
                angle_diff = abs(math.atan2(math.sin(angle_to_enemy - facing_rad),
                                           math.cos(angle_to_enemy - facing_rad)))
                from_front = angle_diff < math.pi / 3
                if player.riot_gear.equipped and from_front:
                    shield_rect = player.riot_gear.get_shield_rect(player.x, player.y)
                    if shield_rect and shield_rect.colliderect(enemy.get_rect()):
                        push_back = 15
                        enemy.x += math.cos(angle_to_enemy) * push_back
                        enemy.y += math.sin(angle_to_enemy) * push_back
                        player.take_damage(enemy.damage, "melee", True, enemy.x, enemy.y)
                    else:
                        player.take_damage(enemy.damage, "melee", from_front, enemy.x, enemy.y)
                else:
                    player.take_damage(enemy.damage, "melee", from_front, enemy.x, enemy.y)
                etype = enemy.enemy_type
                if etype == EnemyType.ZOMBIE_FAST and random.random() < 0.25:
                    player.buff_manager.add_buff(BuffType.BLEED, duration=4.0)
                elif etype == EnemyType.ZOMBIE_TANK and random.random() < 0.3:
                    player.buff_manager.add_buff(BuffType.FRACTURE, duration=5.0)
                elif etype == EnemyType.ZOMBIE_NORMAL and random.random() < 0.1:
                    player.buff_manager.add_buff(BuffType.BLEED, duration=3.0)
                player.ensure_safe_position(self.world)
                if self.config.screen_shake and camera is not None:
                    camera.shake(6, 0.4)

    def _update_playing(self, dt):
        # 衰减吸血屏幕效果
        # Mod 每帧钩子
        try:
            trigger_hook(HOOK_GAME_TICK, self, dt)
        except Exception:
            pass
        if self.lifesteal_flash > 0:
            self.lifesteal_flash = max(0, self.lifesteal_flash - dt * 1.5)

        # 角色技能：随时间缓慢回血（如医护兵）
        if getattr(self.player, 'health_regen', 0) > 0 and self.player.alive and not self.player.downed:
            self._char_regen_timer = getattr(self, '_char_regen_timer', 0) + dt
            if self._char_regen_timer >= 2.0:
                self._char_regen_timer = 0
                self.player.heal(self.player.health_regen * 2)

        # 聊天输入模式：游戏继续运行，仅跳过玩家输入处理
        keys = pygame.key.get_pressed()
        move_x, move_y = 0, 0
        mouse_angle = 0.0
        sprinting = False  # 默认值，确保所有路径都有定义

        import time
        if self.config.control_mode == ControlMode.KEYBOARD:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                move_y = -1
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                move_y = 1
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                move_x = -1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                move_x = 1
            # 疾跑检测（Ctrl键）
            sprinting = (keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL])
            player_screen_x = (self.player.x - self.camera.x) * self.scale
            player_screen_y = (self.player.y - self.camera.y) * self.scale
            mouse_pos = pygame.mouse.get_pos()
            mouse_angle = math.atan2(mouse_pos[1] - player_screen_y, mouse_pos[0] - player_screen_x)
            self.mouse_angle = mouse_angle

            # ========= G键按住：只更新skill_caster内部数据，不绘制 =========
            if keys[pygame.K_g] and self.key_g_held:
                hold_t = time.time() - self.key_g_press_start
                if not self.g_aim_started and hold_t >= self.key_g_long_threshold:
                    self.g_aim_started = True
                    self.player.riot_gear.start_aim(self.mouse_angle)
                    # 【重要】打开瞄准标记，_draw_aim_preview才会执行绘制
                    self.skill_caster.is_aiming = True

                if self.g_aim_started:
                    self.player.riot_gear.update_aim(self.mouse_angle, dt)
                    # 填充skill_caster，复用触控全部数据
                    self.skill_caster.set_player_pos(self.player.x, self.player.y, self.camera.x, self.camera.y)
                    max_dist = self._get_skill_max_distance(self.selected_skill)
                    self.skill_caster.set_max_distance(max_dist)
                    self.skill_caster.set_aim_angle(self.mouse_angle)
                    # 根据鼠标到玩家的屏幕距离动态计算距离比例（范围圈跟随鼠标）
                    mouse_screen_dist = math.hypot(mouse_pos[0] - player_screen_x, mouse_pos[1] - player_screen_y)
                    max_screen_dist = max_dist * self.scale
                    distance_ratio = min(1.0, max(0.1, mouse_screen_dist / max_screen_dist)) if max_screen_dist > 0 else 1.0
                    self.skill_caster.set_distance_ratio(distance_ratio)
            else:
                self.g_aim_started = False

            # ========= Q键按住：投掷物瞄准（复用SkillCaster逻辑） =========
            if keys[pygame.K_q] and self.key_q_held:
                hold_t = time.time() - self.key_q_press_start
                if not self.q_aim_started and hold_t >= self.key_q_long_threshold:
                    self.q_aim_started = True
                    self.throwable_caster.is_aiming = True

                if self.q_aim_started:
                    self.throwable_caster.set_player_pos(self.player.x, self.player.y, self.camera.x, self.camera.y)
                    self.throwable_caster.set_max_distance(self.throwable_max_dist)
                    self.throwable_caster.set_aim_angle(self.mouse_angle)
                    # 范围圈跟随鼠标：根据鼠标到玩家的屏幕距离计算距离比例
                    mouse_screen_dist = math.hypot(mouse_pos[0] - player_screen_x, mouse_pos[1] - player_screen_y)
                    max_screen_dist = self.throwable_max_dist * self.scale
                    distance_ratio = min(1.0, max(0.1, mouse_screen_dist / max_screen_dist)) if max_screen_dist > 0 else 1.0
                    self.throwable_caster.set_distance_ratio(distance_ratio)
            else:
                self.q_aim_started = False
        else:
            # 触控模式
            # 防全卡死兜底：逐根手指按"无任何事件的时间"超时强制释放（事件彻底丢失时也能恢复）
            _now_t = time.time()
            for _fid in list(self._active_touch_ids):
                if _now_t - self._active_touch_last.get(_fid, 0) > self.touch_stuck_timeout:
                    self.touch_events.append({
                        "type": "up", "pos": self._active_touch_pos.get(_fid, (0, 0)), "id": _fid})
                    self._active_touch_ids.discard(_fid)
                    self._active_touch_pos.pop(_fid, None)
                    self._active_touch_last.pop(_fid, None)
                    logger.debug(f"触控超时强制释放: 手指id={_fid}")
            _tev = []
            for _e in self.touch_events:
                _r = trigger_hook(HOOK_TOUCH_EVENT, _e, self)
                if not (True in _r):
                    _tev.append(_e)
            # 双人同屏：P1 控件只接收左半屏的按下事件（防止右半屏触摸误触 P1；up 全收防卡死）
            if self.is_multiplayer_active() and self.state == GameState.PLAYING:
                _half_px = self.scaled_width // 2
                _tev = [e for e in _tev if e["type"] != "down" or e.get("pos", (0, 0))[0] < _half_px]
            self.joystick.handle_touch(_tev, self.scale, self._active_touch_ids)
            # Windows 触控一体机（班班通等）的触摸以鼠标事件合成为主，up 可能被系统手势/驱动吞掉：
            # 用 mouse.get_pressed 兜底释放"鼠标手指(id=-1)"，防止摇杆/攻击按钮卡在按下态
            mouse_btn = pygame.mouse.get_pressed()
            if not (mouse_btn and mouse_btn[0]):
                if self.joystick.active and self.joystick.touch_id == -1:
                    self.joystick.reset()
                if self.aim_button.active and self.aim_button.touch_id == -1:
                    self.aim_button.active = False
                    self.aim_button.touch_id = None
                    self.aim_button.is_shooting = False
                    self.aim_button.is_aiming = False
                    self.aim_button.knob_offset_x = 0
                    self.aim_button.knob_offset_y = 0
                if self.skill_selector.pressed and self.skill_selector.touch_id == -1:
                    self.skill_selector.pressed = False
                    self.skill_selector.touch_id = None
                    self.skill_selector.wheel_active = False
                    self.skill_selector.is_long_press = False
                    self.skill_selector.should_open_wheel = False
            move_x, move_y = self.joystick.get_direction()

            # 触控疾跑按钮：按住期间疾跑
            sprint_btn = self.touch_buttons.get("sprint")
            if sprint_btn and sprint_btn.pressed:
                sprinting = True

            # 攻击/瞄准摇杆
            self.aim_button.handle_touch(_tev, self.scale)
            mouse_angle = self.aim_button.get_angle()
            self.player.facing_angle = math.degrees(mouse_angle)

            # === 技能轮盘处理 ===
            if self.skill_wheel_active:
                selected_skill = self.skill_wheel.handle_touch(_tev, self.scale)
                if selected_skill is not None:
                    self.selected_skill = selected_skill.skill_type if hasattr(selected_skill, 'skill_type') else selected_skill
                    self.skill_wheel_active = False
                    self.skill_wheel.hide()
                    skill = self.player.skill_tree.get_skill(self.selected_skill)
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 40,
                        f"选择技能: {skill.name if skill else '?'}", color=GOLD, lifetime=1.5
                    ))
                elif not self.skill_wheel.active:
                    self.skill_wheel_active = False
            
            if not self.skill_wheel_active:
                self.skill_selector.handle_touch(_tev, self.scale)
                if self.skill_selector.is_showing_wheel():
                    unlocked_objs = self._get_unlocked_skill_objects()
                    current_skill_obj = self.player.skill_tree.get_skill(self.selected_skill)
                    self.skill_wheel.show(unlocked_objs, current_skill_obj)
                    self.skill_wheel_active = True
                elif self.skill_selector.just_released:
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

            # === 武器轮盘处理 ===
            if self.weapon_wheel_active:
                selected_idx = self.weapon_wheel.handle_touch(_tev, self.scale)
                if selected_idx is not None:
                    self.player.switch_weapon(selected_idx)
                    self.weapon_wheel_active = False
                    self.weapon_wheel.hide()
                    weapon = self.player.get_current_weapon()
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 40,
                        f"选择武器: {weapon.name}", color=PURPLE, lifetime=1.0
                    ))
            # === 单武器模式：无武器轮盘/切换（局内只有一种武器） ===

            # 技能释放按钮 - 支持拖拽改变方向和距离
            self.skill_caster.set_player_pos(self.player.x, self.player.y, self.camera.x, self.camera.y)
            self.skill_caster.set_max_distance(self._get_skill_max_distance(self.selected_skill))
            # 保存释放前的瞄准状态（handle_touch会在up时重置is_aiming）
            cast_result = self.skill_caster.handle_touch(_tev, self.scale)
            if cast_result:
                if self.skill_caster.was_aiming_on_release:
                    self._use_skill_aimed(self.selected_skill, self.skill_caster.angle, self.skill_caster.distance_ratio)
                else:
                    self._use_skill(self.selected_skill)

            # 投掷物释放按钮 - 支持短按快投、长按瞄准
            self.throwable_caster.set_player_pos(self.player.x, self.player.y, self.camera.x, self.camera.y)
            self.throwable_caster.set_max_distance(self.throwable_max_dist)
            throw_result = self.throwable_caster.handle_touch(_tev, self.scale)
            if throw_result:
                if self.throwable_caster.was_aiming_on_release:
                    self._throw_grenade_aimed(self.throwable_caster.angle, self.throwable_caster.distance_ratio)
                else:
                    self._throw_grenade()

            # 投掷物切换按钮
            self.throwable_switch_btn.handle_touch(_tev, self.scale)
            if self.throwable_switch_btn.just_released:
                self._cycle_throwable()

            # 其他按钮
            for name, btn in self.touch_buttons.items():
                if name == "weapon_switch":
                    continue  # 已在上面处理
                btn.handle_touch(_tev, self.scale)
                if name == "shoot" and btn.just_released:
                    if self.player.riot_gear.equipped:
                        self._perform_bash(self.player.facing_angle)
                elif name == "pause" and btn.just_released:
                    self.state = GameState.PAUSED

        move_len = math.hypot(move_x, move_y)
        if move_len > 1:
            move_x /= move_len
            move_y /= move_len

        # 盾牌冲撞中：锁定玩家移动方向
        if self.player.riot_gear.charge_active:
            move_x, move_y = 0, 0

        # === 恐惧(FEAR)状态：无法自控，随机乱走 ===
        _fear_buff = self.player.buff_manager.get_buff(BuffType.FEAR) if hasattr(self.player, 'buff_manager') else None
        if _fear_buff is not None and not _fear_buff.is_expired():
            if not hasattr(self, '_fear_rand_angle'):
                self._fear_rand_angle = random.uniform(0, math.pi * 2)
            if not hasattr(self, '_fear_phase'):
                self._fear_phase = 0.0
            # 恐惧：随机乱走（不响应玩家输入），攻击已被 attack_speed_mult=0 禁用
            _fear_speed = 0.9
            _fa = self._fear_rand_angle + math.sin(self._fear_phase * 0.8) * 0.6
            self._fear_phase += dt
            move_x = math.cos(_fa) * _fear_speed
            move_y = math.sin(_fa) * _fear_speed
            sprinting = False

        # 更新防爆套装动画
        self._update_riot_animation(dt)

        # 更新武器切换冷却
        if self.weapon_switch_cooldown > 0:
            self.weapon_switch_cooldown -= dt

        # 应用符文速度加成
        rune_speed_mult = 1.0 + getattr(self, 'rune_buffs', {}).get("speed", 0)
        orig_speed_mult = self.player.speed_mult
        self.player.speed_mult *= rune_speed_mult
        # Mod 钩子：玩家移动覆盖
        for _mv in trigger_hook(HOOK_PLAYER_MOVE, self, move_x, move_y, dt):
            if isinstance(_mv, (tuple, list)) and len(_mv) >= 2:
                try:
                    move_x, move_y = float(_mv[0]), float(_mv[1])
                except Exception:
                    pass
        # v2.0.13：.zmap 效果区（水坑减速 / 尖刺伤害）
        _zone_mult = 1.0
        if getattr(self.world, "zones", None):
            try:
                from zombie_pkg.map_loader import apply_player_zones
                _zone_mult = apply_player_zones(self.world, self.player, dt)
            except Exception:
                pass
        self.player.update(dt, move_x * _zone_mult, move_y * _zone_mult,
                           mouse_angle, self.world, sprinting=sprinting)
        # 符文：再生效果
        if hasattr(self, 'rune_manager'):
            regen = self.rune_manager.get_bonus("regen")
            if regen > 0 and self.player.hp < self.player.max_hp:
                self.player.hp = min(self.player.max_hp, self.player.hp + regen * dt)
        self.player.speed_mult = orig_speed_mult
        # 盾牌冲撞更新（移动+碰撞伤害）
        self._update_charge(dt)
        # 过热倾泻：计时 + 射速加成（冷却额外递减）+ 灼烧枪口特效
        if getattr(self.player, 'overdrive_timer', 0) > 0:
            self.player.overdrive_timer -= dt
            if self.player.overdrive_timer <= 0:
                self.player.overdrive_timer = 0
                self.player.overdrive_burn = False
            _ow = self.player.get_current_weapon()
            if _ow and _ow.cooldown_timer > 0:
                _ow.cooldown_timer -= (getattr(self.player, 'overdrive_mult', 2.0) - 1.0) * dt
            self.particles.spawn(self.player.x, self.player.y, (255, 160, 60), 2, (1, 3), (-2, 2), (0.1, 0.4))
        # 显示玩家受到的buff伤害数字
        for dmg, dtype in getattr(self.player, 'buff_damage_events', []):
            if dmg > 0:
                self.damage_numbers.append(DamageNumber(
                    self.player.x + random.uniform(-15, 15), 
                    self.player.y - 20, 
                    dmg, damage_type=dtype
                ))
        self.player.buff_damage_events = []
        self.player.x, self.player.y = self.world.clamp_position(
            self.player.x, self.player.y, self.player.size)
        # 战吼计时器
        if self.war_cry_timer > 0:
            self.war_cry_timer -= dt
        # debuff统计和燃烧存活时间
        if self.session:
            debuff_count = len([b for b in self.player.buff_manager.get_active_buffs() if b.is_debuff])
            self.session.update_max_debuffs(debuff_count)
            if self.player.buff_manager.has_buff(BuffType.BURN):
                self.session.add_burning_survive_time(dt)

        # 更新世界
        self.world.update(dt, self.player.x, self.player.y)

        # === Buff视觉效果 ===
        self._update_buff_visuals(dt)

        # 更新尸潮管理器
        self.horde_manager.update(dt)

        # 尸潮音乐切换
        if self.horde_manager.is_horde_active():
            self.assets.play_music("horde")
            self._music_context = 'horde'
        elif hasattr(self, '_was_horde') and self._was_horde and not self.horde_manager.is_horde_active():
            # 尸潮结束，记录存活
            if self.session:
                self.session.add_horde_survived()
            # 尸潮结束，恢复地图专属音乐
            map_name = self.world.map_type.name.lower() if hasattr(self.world, 'map_type') else 'school'
            map_music = MAP_MUSIC_MAP.get(map_name, 'school')
            self.assets.play_music(map_music)
            self._music_context = 'explore'
            # 尸潮奖励：根据规模刷新对应奖励
            self._spawn_horde_rewards()
        self._was_horde = self.horde_manager.is_horde_active()

        # ========== 故事模式核心逻辑 ==========
        if self.config.game_mode == GameMode.STORY:
            self._update_story_mode(dt)

        # 检查升级选择（同屏双人：P1/P2 各自升级，半屏显示并标注是谁）
        if self.state != GameState.SKILL_SELECT:
            for _pl, _tag in ((self.player, "P1"), (self.player2, "P2")):
                if not _pl or not _pl.pending_level_up:
                    continue
                if _pl.skill_cards:
                    self.state = GameState.SKILL_SELECT
                    self.pending_upgrade_for = _tag
                    _region = None
                    if self.is_multiplayer_active() and self.multiplayer_mode == "same_screen":
                        _half = max(320, self.scaled_width // 2)
                        _region = pygame.Rect(0 if _tag == "P1" else self.scaled_width - _half, 0, _half, self.scaled_height)
                    self.skill_card_selector.show(_pl.skill_cards, region=_region,
                                                  title=f"{_tag} 升级！选择你的强化",
                                                  subtitle=f"{_tag} 等级 {_pl.level} → 选择技能卡")
                    # 记录升级
                    if self.session:
                        self.session.add_level_up()
                    # 播放升级音效
                    self.assets.play_sound("level_up")
                else:
                    _pl.pending_level_up = False
                break

        # 自动射击 / 盾肘击【修改】
        auto_shoot = False
        if self.config.control_mode == ControlMode.KEYBOARD:
            mouse_left = pygame.mouse.get_pressed()[0]
            # 装备防爆套装，鼠标左键执行肘击，不再开火
            if mouse_left and self.player.can_act():
                if self.player.riot_gear.equipped and self.riot_anim_state == "idle":
                    self._perform_bash(math.degrees(mouse_angle))
                else:
                    auto_shoot = True
        else:
            auto_shoot = self.aim_button.is_shooting

        if auto_shoot and self.player.can_act() and not self.player.riot_gear.equipped and self.riot_anim_state != "equipping":
            weapon = self.player.get_current_weapon()
            if weapon.can_fire():
                # 过热倾泻buff：无限弹药
                if getattr(self.player, 'overdrive_timer', 0) > 0 and hasattr(weapon, 'current_ammo') and weapon.current_ammo != "∞":
                    weapon.current_ammo = min(weapon.max_ammo, weapon.current_ammo + 1)
                # 符文伤害加成
                rune_dmg_mult = 1.0 + getattr(self, 'rune_buffs', {}).get("damage", 0)
                trigger_hook(HOOK_PLAYER_FIRE, weapon, self.player)
                proj_list = weapon.fire(
                    self.player.x, self.player.y, mouse_angle,
                    self.player.damage_mult * self.player.damage_boost_mult * self.player.buff_manager.get_damage_mult() * rune_dmg_mult * self.player.damage_multiplier, self.player.speed_mult,
                    player=self.player
                )
                self.projectiles.extend(proj_list)
                # 过热倾泻灼烧：子弹附带火焰
                if getattr(self.player, 'overdrive_burn', False):
                    for _p in proj_list:
                        _p.is_flame = True
                
                # 近战武器攻击处理
                if getattr(weapon, "melee_attack_triggered", False):
                    weapon.melee_attack_triggered = False
                    self._start_melee_attack(weapon, mouse_angle)
                
                # 记录射击
                if self.session:
                    self.session.add_shot_fired()
                # 播放射击音效
                if getattr(weapon, "is_melee", False):
                    self.assets.play_sound_random(["melee_swing", "shoot_pistol"])
                elif getattr(weapon, "is_scythe", False):
                    # 死神镰刀：剑气挥砍音效
                    self.assets.play_sound_random(["melee_swing", "shoot_pistol"])
                elif getattr(weapon, "is_throwable", False):
                    self.assets.play_sound("grenade_throw")
                else:
                    wtype = weapon.weapon_type.name.lower()
                    sound_key = wtype if wtype in SOUND_MAP else "pistol"
                    self.assets.play_sound_random(SOUND_MAP.get(sound_key, ["shoot_pistol"]))
                if self.config.screen_shake:
                    self.camera.shake(weapon.shake_intensity, 0.08)

        # 同步换弹状态到射击按钮 - 增强
        if self.config.control_mode == ControlMode.TOUCH:
            weapon = self.player.get_current_weapon()
            shoot_btn = self.touch_buttons.get("shoot")
            if shoot_btn and weapon:
                if weapon.is_reloading:
                    shoot_btn.is_reloading = True
                    shoot_btn.reload_progress = 1.0 - (weapon.reload_timer / weapon.reload_time) if weapon.reload_time > 0 else 0
                else:
                    shoot_btn.is_reloading = False
                    # 武器自身冷却也显示
                    if weapon.cooldown_timer > 0 and weapon.fire_rate > 0:
                        shoot_btn.cooldown = weapon.cooldown_timer
                        shoot_btn.max_cooldown = weapon.fire_rate
                    else:
                        shoot_btn.cooldown = 0

        # 死神镰刀换弹期间：形成大圆形横扫区域（持续伤害+特效）
        _cw = self.player.get_current_weapon()
        if getattr(_cw, "is_scythe", False) and _cw.is_reloading:
            self._update_scythe_sweep(_cw, dt)

        # 防爆套装自动肘击
        if self.player.riot_gear.equipped and self.config.control_mode == ControlMode.TOUCH:
            if self.aim_button.is_shooting and self.player.riot_gear.can_bash():
                self._perform_bash(self.player.facing_angle)

        # 生成敌人 - 尸潮期间大量刷新，非尸潮期间少量刷新
        # 双人/联机：怪物按玩家人数调整难度（上限×1.8 + 额外刷新频率）
        spawn_type = self.horde_manager.should_spawn()
        mp_mult = 1.8 if self.is_multiplayer_active() else 1.0
        max_enemies = 80 if self.horde_manager.is_horde_active() else 25
        if not hasattr(self, 'time_slow_active') or not self.time_slow_active:
            pass
        else:
            max_enemies = int(max_enemies * 0.7)
        max_enemies = int(max_enemies * mp_mult)
        if spawn_type and len(self.enemies) < max_enemies:
            # 处理元组返回：(boss_type, drops_vaccine)
            drops_vaccine = False
            if isinstance(spawn_type, tuple):
                spawn_type, drops_vaccine = spawn_type
            # 故事模式：使用地图配置的怪物权重（Boss除外）
            boss_types = (EnemyType.BOSS_LONG, EnemyType.BOSS_XIANG, EnemyType.BOSS_MUTANT,
                         EnemyType.BOSS_QUEEN, EnemyType.BOSS_TITAN, EnemyType.BOSS_WANG)
            if self.config.game_mode == GameMode.STORY and spawn_type not in boss_types:
                enemy_weights = self.map_config.get("enemy_weights", {})
                if enemy_weights:
                    total_weight = sum(enemy_weights.values())
                    r = random.uniform(0, total_weight)
                    cumulative = 0
                    for etype, w in enemy_weights.items():
                        cumulative += w
                        if r <= cumulative:
                            spawn_type = etype
                            break
            angle = random.uniform(0, math.pi * 2)
            dist = random.randint(400, 700)
            spawn_x = self.player.x + math.cos(angle) * dist
            spawn_y = self.player.y + math.sin(angle) * dist
            spawn_x, spawn_y = self.world.clamp_position(spawn_x, spawn_y, 20)
            enemy = Enemy(spawn_x, spawn_y, spawn_type, 1, self.config.difficulty)
            # v2.0.13：RL 强化学习 AI 挂载（未启用时 rl_ai=None，回退原 AI）
            if getattr(self, "rl_ai", None) is not None:
                enemy.ai_rl = self.rl_ai
            if drops_vaccine:
                enemy.drops_vaccine = True  # 标记此Boss必爆疫苗
            self.enemies.append(enemy)
            # 见到怪物即解锁图鉴（在 mod 钩子之前，确保不被吞掉）
            try:
                _cu = codex_unlock_manager.unlock_monster(spawn_type.name)
                if _cu:
                    self._codex_unlock_toast(_cu, spawn_type.name)
            except Exception:
                pass
            # mod 钩子：敌人生成
            try:
                trigger_hook(HOOK_ENEMY_SPAWN, enemy)
            except:
                pass
            if getattr(enemy, "is_boss", False):
                self._boss_dialogue(spawn_type)
                # 尸潮规模提示
                scale_name = self.horde_manager.get_current_scale_name()
                scale_color = self.horde_manager.get_scale_color()
                self.floating_texts.append(FloatingText(
                    self.player.x, self.player.y - 80,
                    f"【{scale_name}】", color=scale_color, lifetime=3.0
                ))

        # 双人/联机：额外刷新频率（难度随玩家数调整）
        if self.is_multiplayer_active():
            self._mp_spawn_timer = getattr(self, '_mp_spawn_timer', 0) + dt
            if self._mp_spawn_timer >= 0.35 and len(self.enemies) < max_enemies:
                self._mp_spawn_timer -= 0.35
                _extra = self.horde_manager.should_spawn()
                if _extra:
                    if isinstance(_extra, tuple):
                        _extra, _dv = _extra
                    _ang2 = random.uniform(0, math.pi * 2)
                    _dist2 = random.randint(400, 700)
                    _sx, _sy = self.world.clamp_position(
                        self.player.x + math.cos(_ang2) * _dist2,
                        self.player.y + math.sin(_ang2) * _dist2, 20)
                    self.enemies.append(Enemy(_sx, _sy, _extra, 1, self.config.difficulty))

        # 更新敌人
        for enemy in self.enemies[:]:
            # 选择最近的玩家作为目标（双人模式支持多目标，倒地玩家不成为目标）
            if self.player2:
                d1 = (enemy.x - self.player.x) ** 2 + (enemy.y - self.player.y) ** 2 \
                    if not getattr(self.player, 'downed', False) else 1e18
                d2 = (enemy.x - self.player2.x) ** 2 + (enemy.y - self.player2.y) ** 2 \
                    if (self.player2 and not getattr(self.player2, 'downed', False)) else 1e18
                if d2 < d1:
                    target_x, target_y, target_obj = self.player2.x, self.player2.y, self.player2
                else:
                    target_x, target_y, target_obj = self.player.x, self.player.y, self.player
            else:
                target_x, target_y, target_obj = self.player.x, self.player.y, self.player
            try:
                trigger_hook(HOOK_ENEMY_UPDATE, enemy, dt)
            except Exception:
                pass
            result = enemy.update(dt, target_x, target_y, target_obj, self.world)
            # 显示敌人受到的buff伤害数字（Enemy.update内部已处理buff_manager.update）
            for dmg, dtype in getattr(enemy, 'buff_damage_events', []):
                if dmg > 0:
                    self.damage_numbers.append(DamageNumber(
                        enemy.x + random.uniform(-15, 15), 
                        enemy.y - 20, 
                        dmg, damage_type=dtype
                    ))
            enemy.buff_damage_events = []

            # 光照系统更新（同步画质设置）
            if hasattr(self, 'lighting'):
                if self.lighting.quality != self.config.graphics_quality:
                    self.lighting.set_quality(self.config.graphics_quality)
                self.lighting.update(dt)

            # 粒子系统同步画质（性能档削减粒子密度，质量档增强）
            if getattr(self.particles, 'quality', None) != self.config.graphics_quality:
                self.particles.quality = self.config.graphics_quality

            # 爆炸僵尸自爆
            if result == "explode":
                self.particles.spawn_explosion(enemy.x, enemy.y, RUST, 40)
                self.camera.shake(10, 0.5)
                # 爆炸光源（性能模式下跳过）
                if hasattr(self, 'lighting') and getattr(self.lighting, 'quality', 'balanced') != 'performance':
                    self.lighting.add_light(enemy.x, enemy.y, 200, (255, 150, 50), intensity=1.0, lifetime=0.4, flicker=True)
                for other in self.enemies[:]:
                    if other is not enemy and other.alive:
                        dist = math.hypot(other.x - enemy.x, other.y - enemy.y)
                        if dist < getattr(enemy, "explode_radius", 100):
                            other.take_damage(getattr(enemy, "explode_damage", 80) * (1 - dist / getattr(enemy, "explode_radius", 100)))
                # 对玩家造成伤害（P1/P2 双判定）
                self._damage_players_near(enemy.x, enemy.y, getattr(enemy, "explode_radius", 100),
                                          getattr(enemy, "explode_damage", 80) * 0.5, dtype="aoe")
                self._on_enemy_death(enemy)
                continue

            # ========== Boss行为返回处理 ==========
            if result == "boss_aoe":
                # 龙某 AOE地面震荡攻击
                aoe_radius = 190
                aoe_damage = int(enemy.damage * 1.4)
                self._damage_players_near(enemy.x, enemy.y, aoe_radius, aoe_damage, dtype="aoe")
                self.camera.shake(int(6), 0.3)
                if self.camera2:
                    self.camera2.shake(int(6), 0.3)

            elif result == "boss_execution_slash":
                # --------龙某【处决重劈】--------
                exec_radius = 230
                exec_dmg = int(enemy.damage * 3.2)
                self._damage_players_near(enemy.x, enemy.y, exec_radius, exec_dmg, dtype="aoe")
                self.camera.shake(int(18), 0.9)
                if self.camera2:
                    self.camera2.shake(int(18), 0.9)
                self.particles.spawn_explosion(enemy.x, enemy.y, CRIMSON, 60)

            elif result == "boss_execution_salvo":
                # --------向某【处决霰弹爆发】近距离多段伤害--------
                pellet_count = 12
                pellet_dmg = int(enemy.damage * 0.6)
                for _ in range(pellet_count):
                    self._damage_players_near(enemy.x, enemy.y, 230, pellet_dmg, dtype="melee")
                self.camera.shake(int(16),0.8)
                self.particles.spawn_explosion(enemy.x, enemy.y, ORANGE,55)

            elif result == "boss_execution_mutant":
                # --------变异体【毁灭连招终结】超高伤害AOE--------
                exec_radius = 240
                exec_dmg = int(enemy.damage * 3.6)
                self._damage_players_near(enemy.x, enemy.y, exec_radius, exec_dmg, dtype="aoe")
                self.camera.shake(22, 0.9)
                if self.camera2:
                    self.camera2.shake(22, 0.9)
                self.particles.spawn_explosion(enemy.x, enemy.y, BLOOD_RED, 70)
                self.particles.spawn_explosion(enemy.x, enemy.y, CRIMSON, 40)

            elif result == "boss_execution_queen":
                # --------尸潮女王【虫群吞噬】召唤大量小怪+持续伤害--------
                for _ in range(10):
                    angle = random.uniform(0, math.pi * 2)
                    spawn_x = enemy.x + math.cos(angle) * 100
                    spawn_y = enemy.y + math.sin(angle) * 100
                    minion = Enemy(spawn_x, spawn_y, random.choice([EnemyType.ZOMBIE_FAST, EnemyType.ZOMBIE_CRAWLER, EnemyType.ZOMBIE_SPITTER]), 1, self.difficulty)
                    self.enemies.append(minion)
                    try:
                        _cu = codex_unlock_manager.unlock_monster(minion.enemy_type.name if hasattr(minion, "enemy_type") else minion.type.name)
                        if _cu:
                            self._codex_unlock_toast(_cu, minion.enemy_type.name if hasattr(minion, "enemy_type") else minion.type.name)
                    except Exception:
                        pass
                for p in self._alive_players():
                    p.buff_manager.add_buff(BuffType.POISON, 10.0)
                self.camera.shake(12, 0.6)
                if self.camera2:
                    self.camera2.shake(12, 0.6)
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 60)

            elif result == "boss_execution_titan":
                # --------泰坦【泰坦之怒】超大范围地震--------
                exec_radius = 320
                exec_dmg = int(enemy.damage * 3.0)
                self._damage_players_near(enemy.x, enemy.y, exec_radius, exec_dmg, dtype="aoe")
                self.camera.shake(30, 1.2)
                if self.camera2:
                    self.camera2.shake(30, 1.2)
                self.particles.spawn_explosion(enemy.x, enemy.y, GRAY, 80)
                self.particles.spawn_explosion(enemy.x, enemy.y, CHARCOAL, 50)

            # === 新增Boss技能处理 ===
            elif result == "boss_ground_slam":
                # 龙某地震波：大范围环形AOE
                slam_radius = 280
                slam_dmg = int(enemy.damage * 1.8)
                self._damage_players_near(enemy.x, enemy.y, slam_radius, slam_dmg, dtype="aoe")
                self.camera.shake(10, 0.5)
                if self.camera2:
                    self.camera2.shake(10, 0.5)
                self.particles.spawn_explosion(enemy.x, enemy.y, ORANGE, 50)
                # 环形冲击波粒子
                for i in range(24):
                    angle = i * math.pi * 2 / 24
                    self.particles.spawn_particle(
                        enemy.x + math.cos(angle) * 30,
                        enemy.y + math.sin(angle) * 30,
                        math.cos(angle) * 5, math.sin(angle) * 5,
                        ORANGE, 0.6, 8
                    )

            elif result == "boss_charge_trail":
                # 龙某狂暴冲锋拖尾+碰撞伤害（P1/P2 双判定）
                self.particles.spawn_particle(enemy.x, enemy.y, 0, 0, CRIMSON, 0.3, 12)
                for p in self._alive_players():
                    dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y) if p is self.player \
                        else math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if dist_pl < enemy.size + p.size + 5:
                        p.take_damage(int(enemy.damage * 0.8), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)

            elif result == "boss_summon_melee":
                # 龙某召唤普通僵尸
                for _ in range(3):
                    angle = random.uniform(0, math.pi * 2)
                    sx = enemy.x + math.cos(angle) * 80
                    sy = enemy.y + math.sin(angle) * 80
                    self.enemies.append(Enemy(sx, sy, EnemyType.ZOMBIE_NORMAL, 1, self.config.difficulty))
                self.particles.spawn_explosion(enemy.x, enemy.y, DARK_GREEN, 30)

            elif result == "boss_summon_ranged":
                # 向某召唤远程僵尸
                for _ in range(2):
                    angle = random.uniform(0, math.pi * 2)
                    sx = enemy.x + math.cos(angle) * 80
                    sy = enemy.y + math.sin(angle) * 80
                    self.enemies.append(Enemy(sx, sy, EnemyType.ZOMBIE_RANGED, 1, self.config.difficulty))
                self.assets.play_sound("boss_queen_summon")
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 30)

            elif result == "boss_regen":
                # 龙某护盾再生/回血
                self.particles.spawn_heal_particles(enemy.x, enemy.y, 15)
                self.floating_texts.append(FloatingText(enemy.x, enemy.y - 30, "护盾再生!", color=GREEN, lifetime=1.5))

            elif result == "boss_barrage":
                # 向某弹幕扫射：环形16发子弹
                for i in range(16):
                    angle = i * math.pi * 2 / 16
                    proj = Projectile(
                        enemy.x, enemy.y,
                        math.cos(angle) * 6, math.sin(angle) * 6,
                        int(enemy.damage * 0.7), 420, PURPLE, 4
                    )
                    self.enemy_projectiles.append(proj)
                self.camera.shake(4, 0.2)

            # ===== 王某技能（枪械+死神镰刀双形态）=====
            elif result == "wang_gunfire":
                # 枪械形态：4连发子弹朝玩家 + 曳光弹道
                base_ang = math.atan2(self.player.y - enemy.y, self.player.x - enemy.x)
                for _ in range(4):
                    ang = base_ang + random.uniform(-0.12, 0.12)
                    proj = Projectile(
                        enemy.x, enemy.y,
                        math.cos(ang) * 7, math.sin(ang) * 7,
                        int(enemy.damage * 0.8), 440, FIRE_ORANGE, 4
                    )
                    self.enemy_projectiles.append(proj)
                    # 曳光弹道（火橙直线）
                    self.slash_arcs.append(SlashArc(
                        enemy.x, enemy.y, ang, 300, FIRE_ORANGE,
                        lifetime=0.28, kind="tracer", end_angle_offset=0.3))
                self.assets.play_sound("shoot_pistol")
                self.particles.spawn(enemy.x, enemy.y, FIRE_ORANGE, 6, (3, 6), (-2, 2), (0.2, 0.5))

            elif result == "wang_grenade":
                # 枪榴弹：范围爆炸对玩家造成伤害+击退
                self.camera.shake(12, 0.6)
                if self.camera2:
                    self.camera2.shake(12, 0.6)
                self.assets.play_sound("explosion")
                self.particles.spawn_explosion(enemy.x, enemy.y, FIRE_ORANGE, 60)
                for p in self._alive_players():
                    gdist = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if gdist < 230:
                        p.take_damage(int(enemy.damage * 2.2), damage_type="explosion", attack_x=enemy.x, attack_y=enemy.y)
                        if gdist > 0:
                            p.x += (p.x - enemy.x) / gdist * 40
                            p.y += (p.y - enemy.y) / gdist * 40

            elif result == "wang_scythe_sweep":
                # 死神镰刀：大范围横扫，玩家受伤+强击退（紫色刀光弧斩可见）
                self.camera.shake(15, 0.7)
                if self.camera2:
                    self.camera2.shake(15, 0.7)
                self.assets.play_sound("melee_swing")
                self.particles.spawn_explosion(enemy.x, enemy.y, CRIMSON, 70)
                _tgt = min(self._alive_players(), key=lambda p: math.hypot(p.x - enemy.x, p.y - enemy.y), default=self.player)
                s_ang = math.atan2(_tgt.y - enemy.y, _tgt.x - enemy.x)
                for _off in (-0.5, 0.0, 0.5):
                    self.slash_arcs.append(SlashArc(
                        enemy.x, enemy.y, s_ang + _off, 240 + abs(_off) * 90,
                        (196, 100, 240), lifetime=0.45, kind="scythe",
                        start_radius=40, end_angle_offset=1.1))
                for p in self._alive_players():
                    sdist = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if sdist < 290:
                        p.take_damage(int(enemy.damage * 2.4), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                        if sdist > 0:
                            p.x += (p.x - enemy.x) / sdist * 55
                            p.y += (p.y - enemy.y) / sdist * 55

            elif result == "wang_execution_scythe":
                # 王某处决斩击：超高伤害AOE（血红满月斩 + 双镰刀弧）
                self.camera.shake(20, 1.0)
                if self.camera2:
                    self.camera2.shake(20, 1.0)
                self.assets.play_sound("melee_swing")
                self.particles.spawn_explosion(enemy.x, enemy.y, CRIMSON, 90)
                self.particles.spawn_explosion(enemy.x, enemy.y, BLOOD_RED, 60)
                _tgt = min(self._alive_players(), key=lambda p: math.hypot(p.x - enemy.x, p.y - enemy.y), default=self.player)
                e_ang = math.atan2(_tgt.y - enemy.y, _tgt.x - enemy.x)
                self.slash_arcs.append(SlashArc(
                    enemy.x, enemy.y, e_ang, 330, CRIMSON,
                    lifetime=0.6, kind="scythe", start_radius=60, end_angle_offset=6.2))
                self.slash_arcs.append(SlashArc(
                    enemy.x, enemy.y, e_ang + math.pi, 260, (210, 90, 240),
                    lifetime=0.5, kind="scythe", start_radius=30, end_angle_offset=6.2))
                for p in self._alive_players():
                    edist = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if edist < 280:
                        p.take_damage(int(enemy.damage * 4.0), damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                        if edist > 0:
                            p.x += (p.x - enemy.x) / edist * 80
                            p.y += (p.y - enemy.y) / edist * 80

            elif result == "boss_smoke":
                # 向某烟雾弹：在玩家位置生成减速烟雾区域
                if not hasattr(self, 'smoke_zones'):
                    self.smoke_zones = []
                self.smoke_zones.append({
                    "x": self.player.x, "y": self.player.y,
                    "radius": 120, "timer": 5.0
                })
                self.particles.spawn_explosion(self.player.x, self.player.y, GRAY, 40)

            elif result == "boss_grenade":
                # 向某手雷：延迟爆炸
                if not hasattr(self, 'grenades'):
                    self.grenades = []
                self.grenades.append({
                    "x": enemy.x, "y": enemy.y,
                    "target_x": self.player.x, "target_y": self.player.y,
                    "timer": 1.5, "damage": int(enemy.damage * 1.5), "radius": 100
                })

            elif result == "boss_teleport":
                # 向某闪现特效
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 25)
                self.particles.spawn_explosion(enemy.x, enemy.y, CYAN, 15)

            # === 特种僵尸能力处理 ===
            elif result == "fast_dash":
                # 快速僵尸冲刺（前摇结束后高速冲刺+路径碰撞伤害）
                fd = getattr(enemy, "fast_dash_dir", (1, 0))
                dash_steps = 10
                hit = False
                for _ in range(dash_steps):
                    enemy.x += fd[0] * 8
                    enemy.y += fd[1] * 8
                    for p in self._alive_players():
                        pd = math.hypot(p.x - enemy.x, p.y - enemy.y)
                        if pd < enemy.size + p.size + 4:
                            p.take_damage(int(enemy.damage * 1.5), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                            hit = True
                    if hit:
                        break
                if hit:
                    self.camera.shake(4, 0.2)
                self.particles.spawn_particle(enemy.x, enemy.y, 0, 0, POISON_GREEN, 0.2, 8)

            elif result == "tank_slam":
                # 坦克重击AOE
                slam_r = 70
                self._damage_players_near(enemy.x, enemy.y, slam_r, int(enemy.damage * 1.3), dtype="aoe")
                self.camera.shake(5, 0.25)
                self.particles.spawn_explosion(enemy.x, enemy.y, GRAY, 25)

            elif result == "healer_wave":
                # 治疗僵尸治疗波：治疗周围所有敌人
                heal_r = 150
                heal_amt = 30
                for other in self.enemies:
                    if other is not enemy and other.alive:
                        d = math.hypot(other.x - enemy.x, other.y - enemy.y)
                        if d < heal_r:
                            other.hp = min(other.max_hp, other.hp + heal_amt)
                self.particles.spawn_heal_particles(enemy.x, enemy.y, 20)

            # 统一死亡清理：DOT/buff/钩爪等路径致死后在此触发掉落与移除
            if not enemy.alive:
                self._on_enemy_death(enemy)

            elif result == "phantom_teleport":
                # 幻影瞬移特效
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 20)

            elif result == "shield_charge":
                # 盾兵冲锋碰撞伤害（P1/P2 双判定）
                for p in self._alive_players():
                    dist_pl = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if dist_pl < enemy.size + p.size + 10:
                        p.take_damage(int(enemy.damage * 1.5), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.particles.spawn_particle(enemy.x, enemy.y, 0, 0, CHARCOAL, 0.3, 10)

            # === 新普通僵尸技能 ===
            elif result == "leaper_strike":
                # 跳跃僵尸扑击（前摇结束后扑向玩家+落地伤害）
                ld = getattr(enemy, "leap_dir", (1, 0))
                # 扑向最近的存活玩家
                _tgt = min(self._alive_players(), key=lambda p: math.hypot(p.x - enemy.x, p.y - enemy.y), default=self.player)
                leap_dist = min(math.hypot(_tgt.x - enemy.x, _tgt.y - enemy.y), getattr(enemy, "leap_range", 200))
                enemy.x += ld[0] * leap_dist
                enemy.y += ld[1] * leap_dist
                for p in self._alive_players():
                    dist_pl = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if dist_pl < enemy.size + p.size + 15:
                        p.take_damage(int(enemy.damage * getattr(enemy, "leap_damage_mult", 2.0)), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.assets.play_sound("zombie_leap")
                self.particles.spawn_explosion(enemy.x, enemy.y, ORANGE, 12)

            elif result == "wraith_fear":
                # 怨灵恐惧
                for p in self._alive_players():
                    dist_pl = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if dist_pl < 120:
                        p.buff_manager.add_buff(BuffType.FEAR, 2.0)
                self.assets.play_sound("fear_scream")
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 15)

            # === 精英怪技能 ===
            elif result == "elite_heavy_slam":
                # 精英蛮兵重击
                slam_r = 80
                self._damage_players_near(enemy.x, enemy.y, slam_r,
                                          int(enemy.damage * getattr(enemy, "heavy_damage_mult", 2.5)), dtype="aoe")
                self.camera.shake(6, 0.3)
                self.assets.play_sound("elite_heavy_attack")
                self.particles.spawn_explosion(enemy.x, enemy.y, DARK_RED, 20)

            elif result == "elite_assassin_dash":
                # 精英刺客冲刺
                for p in self._alive_players():
                    dist_pl = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if dist_pl < enemy.size + p.size + 10:
                        p.take_damage(int(enemy.damage * getattr(enemy, "dash_damage_mult", 3.0)), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.assets.play_sound("elite_dash")
                self.particles.spawn_particle(enemy.x, enemy.y, 0, 0, CYAN, 0.3, 12)

            # === 新Boss技能 ===
            elif result == "mutant_combo_hit":
                # 变异体连招攻击
                for p in self._alive_players():
                    dist_pl = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if dist_pl < enemy.size + p.size + 20:
                        p.take_damage(int(enemy.damage * 1.2), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.assets.play_sound("boss_mutant_combo")
                self.particles.spawn_explosion(enemy.x, enemy.y, BLOOD_RED, 15)
                self.camera.shake(4, 0.15)

            elif result == "mutant_combo_finisher":
                # 变异体连招终结AOE
                finisher_r = 120
                self._damage_players_near(enemy.x, enemy.y, finisher_r,
                                          int(enemy.damage * getattr(enemy, "combo_damage_mult", 2.5)), dtype="aoe")
                self.assets.play_sound("boss_mutant_combo", 1.5)
                self.camera.shake(10, 0.4)
                self.particles.spawn_explosion(enemy.x, enemy.y, BLOOD_RED, 40)

            elif result == "queen_summon":
                # 尸潮女王召唤小怪
                for _ in range(3):
                    angle = random.uniform(0, math.pi * 2)
                    spawn_x = enemy.x + math.cos(angle) * 80
                    spawn_y = enemy.y + math.sin(angle) * 80
                    minion = Enemy(spawn_x, spawn_y, random.choice([EnemyType.ZOMBIE_NORMAL, EnemyType.ZOMBIE_FAST, EnemyType.ZOMBIE_CRAWLER]), 1, self.difficulty)
                    self.enemies.append(minion)
                    try:
                        _cu = codex_unlock_manager.unlock_monster(minion.enemy_type.name if hasattr(minion, "enemy_type") else minion.type.name)
                        if _cu:
                            self._codex_unlock_toast(_cu, minion.enemy_type.name if hasattr(minion, "enemy_type") else minion.type.name)
                    except Exception:
                        pass
                self.assets.play_sound("boss_queen_summon")
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 30)

            elif result == "queen_mind_control":
                # 女王精神控制（恐惧）
                for p in self._alive_players():
                    dist_pl = math.hypot(p.x - enemy.x, p.y - enemy.y)
                    if dist_pl < 300:
                        p.buff_manager.add_buff(BuffType.FEAR, 3.0)
                self.assets.play_sound("boss_queen_tentacle")
                self.particles.spawn_explosion(self.player.x, self.player.y, PURPLE, 20)

            elif result == "queen_poison_cloud":
                # 女王毒雾
                for p in self._alive_players():
                    p.buff_manager.add_buff(BuffType.POISON, 5.0)
                self.particles.spawn_explosion(self.player.x, self.player.y, POISON_GREEN, 25)

            elif result == "queen_tentacle":
                # 女王触手突袭
                tentacle_r = 60
                self._damage_players_near(enemy.x, enemy.y, tentacle_r, int(enemy.damage * 1.5), dtype="aoe")
                self.assets.play_sound("boss_queen_tentacle")
                self.particles.spawn_explosion(self.player.x, self.player.y, PURPLE, 20)

            elif result == "titan_stomp":
                # 泰坦地震踩踏
                stomp_r = getattr(enemy, "stomp_radius", 150)
                self._damage_players_near(enemy.x, enemy.y, stomp_r, getattr(enemy, "stomp_damage", 120), dtype="aoe")
                self.assets.play_sound("boss_titan_stomp")
                self.camera.shake(15, 0.5)
                if self.camera2:
                    self.camera2.shake(15, 0.5)
                self.particles.spawn_explosion(enemy.x, enemy.y, GRAY, 50)
                self.particles.spawn_explosion(enemy.x, enemy.y, CHARCOAL, 30)

            elif isinstance(result, list):
                # 远程僵尸散射子弹（list格式）
                for bullet in result:
                    dx = bullet["target_x"] - bullet["x"]
                    dy = bullet["target_y"] - bullet["y"]
                    d = math.hypot(dx, dy)
                    if d > 0:
                        proj = Projectile(
                            bullet["x"], bullet["y"],
                            dx / d * 7, dy / d * 7,
                            bullet["damage"], 400, PURPLE, 4
                        )
                        self.enemy_projectiles.append(proj)

            elif isinstance(result, dict):
                # Boss向某远程射击，生成投射物，复用现有远程敌人子弹格式
                dx = result["target_x"] - result["x"]
                dy = result["target_y"] - result["y"]
                dist = math.hypot(dx, dy)
                if dist > 0:
                    proj = Projectile(
                        result["x"], result["y"],
                        dx / dist * 8, dy / dist * 8,
                        result["damage"], 500, RED, 5
                    )
                    self.enemy_projectiles.append(proj)

            # 怪物与障碍物碰撞
            if self.world.check_collision(enemy.get_rect()):
                enemy.x -= enemy.speed * dt * 60 * 0.5
                enemy.y -= enemy.speed * dt * 60 * 0.5

            # 怪物之间碰撞
            enemy._collision_skip += 1
            if enemy._collision_skip >= 3:
                enemy._collision_skip = 0
                for other in self.enemies:
                    if other is not enemy and other.alive:
                        dx = enemy.x - other.x
                        dy = enemy.y - other.y
                        if abs(dx) > enemy.size + other.size + 10 or abs(dy) > enemy.size + other.size + 10:
                            continue
                        if enemy.get_rect().colliderect(other.get_rect()):
                            dist = math.hypot(dx, dy)
                            if dist > 0 and dist < enemy.size + other.size:
                                push_x = (dx / dist) * 2
                                push_y = (dy / dist) * 2
                                enemy.x += push_x
                                enemy.y += push_y

            # 治疗僵尸治疗周围僵尸
            if getattr(enemy, "is_healer", False) and enemy.heal_timer <= 0:
                enemy.heal_timer = enemy.heal_interval
                for other in self.enemies:
                    if other is not enemy and other.alive:
                        dist = math.hypot(other.x - enemy.x, other.y - enemy.y)
                        if dist < enemy.heal_radius:
                            other.hp = min(other.max_hp, other.hp + enemy.heal_amount)

            # 限制怪物在地图内
            enemy.x, enemy.y = self.world.clamp_position(enemy.x, enemy.y, enemy.size)

            # 怪物与玩家碰撞（被钩爪拉回中的敌人无法造成任何伤害）——P1/P2 双判定
            self._enemy_collide_damage(enemy, self.player, self.camera)
            if self.player2:
                self._enemy_collide_damage(enemy, self.player2, self.camera2)

            # 确保玩家被推动后不在障碍物内
            self.player.ensure_safe_position(self.world)

            # 普通远程敌人攻击（选择最近玩家作为目标）
            if (not enemy.grappled) and getattr(enemy, "attack_range", 0) > 0 and not getattr(enemy, "is_boss", False):
                # 选择最近的玩家作为远程攻击目标
                r_target_x, r_target_y = self.player.x, self.player.y
                dist_e_p = math.hypot(enemy.x - r_target_x, enemy.y - r_target_y)
                r_result = enemy._ranged_attack(dt, r_target_x, r_target_y, dist_e_p)
                if r_result:
                    dx = r_result["target_x"] - r_result["x"]
                    dy = r_result["target_y"] - r_result["y"]
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        proj = Projectile(
                            r_result["x"], r_result["y"],
                            dx / dist * 8, dy / dist * 8,
                            r_result["damage"], 500, RED, 5
                        )
                        self.enemy_projectiles.append(proj)
            
            # 怪物投掷道具
            if not enemy.grappled:
                dist_e_p = math.hypot(enemy.x - self.player.x, enemy.y - self.player.y)
                throw_result = enemy.try_throw(dt, self.player.x, self.player.y, dist_e_p)
                if throw_result:
                    self._spawn_enemy_throwable(throw_result)

        # 更新钩爪碰撞检测
        self._update_grapple_collision()

        # 更新按钮CD显示
        if self.config.control_mode == ControlMode.TOUCH:
            if self.selected_skill in self.player.active_skills:
                self.skill_caster.set_cooldown(self.player.active_skills[self.selected_skill])
            else:
                self.skill_caster.set_cooldown(0)

        # 更新投射物
        for proj in self.projectiles[:]:
            result = proj.update(dt)
            if result == "explode":
                self.particles.spawn_explosion(proj.x, proj.y, ORANGE, 30)
                self.camera.shake(5, 0.3)
                for enemy in self.enemies:
                    dist = math.hypot(enemy.x - proj.x, enemy.y - proj.y)
                    if dist < proj.explosion_radius:
                        damage = proj.damage * (1 - dist / proj.explosion_radius)
                        enemy.take_damage(damage)
                        self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, damage))
                        if not enemy.alive:
                            self._on_enemy_death(enemy)

            if not proj.alive:
                self.projectiles.remove(proj)
                continue

            # 激光束碰撞检测
            if proj.is_laser:
                # 激光束对路径上的所有敌人造成伤害
                for enemy in self.enemies:
                    if enemy in proj.hits:
                        continue
                    # 计算敌人到激光线段的距离
                    dx = proj.laser_end_x - proj.x
                    dy = proj.laser_end_y - proj.y
                    line_len_sq = dx * dx + dy * dy
                    if line_len_sq == 0:
                        continue
                    t = max(0, min(1, ((enemy.x - proj.x) * dx + (enemy.y - proj.y) * dy) / line_len_sq))
                    closest_x = proj.x + t * dx
                    closest_y = proj.y + t * dy
                    dist = math.hypot(enemy.x - closest_x, enemy.y - closest_y)
                    if dist < enemy.size + proj.laser_width:
                        proj.hits.append(enemy)
                        is_crit = random.random() < self.player.crit_chance
                        actual_damage = proj.damage * (self.player.crit_damage if is_crit else 1)
                        enemy.take_damage(actual_damage)
                        self._apply_rune_elemental_on_hit(enemy, actual_damage)
                        self._vampire_heal(actual_damage)
                        self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, actual_damage, is_crit=is_crit, damage_type="ranged"))
                        self.particles.spawn(enemy.x, enemy.y, PURPLE, 5, (2, 5), (-3, 3), (0.2, 0.5))
                        if not enemy.alive:
                            self._on_enemy_death(enemy)
                continue

            proj_rect = proj.get_rect()
            for enemy in self.enemies:
                if enemy in proj.hits:
                    continue
                if proj_rect.colliderect(enemy.get_rect()):
                    proj.hits.append(enemy)
                    proj.pierce -= 1

                    # 应用元素符文效果（火焰/冰霜/毒素/雷电）
                    self._apply_rune_elemental_on_hit(enemy, proj.damage)

                    # 爆炸弹击中敌人时触发爆炸 - 超增强效果
                    if proj.explosive:
                        result = proj.hit_and_explode()
                        if result == "explode":
                            self.particles.spawn_explosion(proj.x, proj.y, ORANGE, 80)
                            self.particles.spawn_explosion(proj.x, proj.y, RED, 50)
                            self.particles.spawn_explosion(proj.x, proj.y, FIRE_YELLOW, 40)
                            self.particles.spawn_explosion(proj.x, proj.y, WHITE, 25)
                            self.camera.shake(20, 0.8)

                            # 多层冲击波
                            for i in range(6):
                                radius = 20 + i * 20
                                alpha = int(200 - i * 30)
                                shock_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                                pygame.draw.circle(shock_surf, (255, 255, 255, alpha), (radius, radius), radius, max(2, int(4 - i * 0.5)))
                                self.screen.blit(shock_surf, (int((proj.x - self.camera.x) * self.scale) - radius,
                                                             int((proj.y - self.camera.y) * self.scale) - radius))

                            # 烟雾
                            for _ in range(20):
                                angle = random.uniform(0, math.pi * 2)
                                dist = random.uniform(10, 80)
                                sx = proj.x + math.cos(angle) * dist
                                sy = proj.y + math.sin(angle) * dist
                                self.particles.spawn(sx, sy, SMOKE_GRAY, 1, (15, 30), (-2, 2), (1.0, 2.5))

                            # 火焰
                            for _ in range(15):
                                angle = random.uniform(0, math.pi * 2)
                                dist = random.uniform(5, 50)
                                fx = proj.x + math.cos(angle) * dist
                                fy = proj.y + math.sin(angle) * dist
                                self.particles.spawn(fx, fy, FIRE_ORANGE, 1, (8, 18), (-3, 3), (0.5, 1.5))
                                self.particles.spawn(fx, fy, FIRE_YELLOW, 1, (4, 12), (-2, 2), (0.3, 1.0))

                            # 火花
                            for _ in range(20):
                                angle = random.uniform(0, math.pi * 2)
                                speed = random.uniform(5, 20)
                                sx = proj.x + math.cos(angle) * random.uniform(0, 30)
                                sy = proj.y + math.sin(angle) * random.uniform(0, 30)
                                self.particles.spawn(sx, sy, (255, 255, 200), 1, (3, 8), (-speed, speed), (0.2, 1.0))

                            self.particles.spawn(proj.x, proj.y, RED, 25, (8, 20), (-10, 10), (0.3, 1.0))
                            self.particles.spawn(proj.x, proj.y, YELLOW, 15, (5, 15), (-8, 8), (0.2, 0.8))

                            for e in self.enemies:
                                dist = math.hypot(e.x - proj.x, e.y - proj.y)
                                if dist < proj.explosion_radius:
                                    damage = proj.damage * (1 - dist / proj.explosion_radius)
                                    if dist > 0:
                                        push_x = (e.x - proj.x) / dist * 80
                                        push_y = (e.y - proj.y) / dist * 80
                                        e.x += push_x
                                        e.y += push_y
                                        e.knockdown(0.3)
                                    is_crit = random.random() < self.player.crit_chance
                                    actual_damage = damage * (self.player.crit_damage if is_crit else 1)
                                    e.take_damage(actual_damage)
                                    self._vampire_heal(actual_damage)
                                    # 火箭筒爆炸施加燃烧
                                    if getattr(proj, 'explosive', False) and random.random() < 0.6:
                                        e.apply_buff(BuffType.BURN, duration=3.0)
                                    self.damage_numbers.append(DamageNumber(e.x, e.y, actual_damage, is_crit=is_crit, damage_type="explosion"))
                                    if not e.alive:
                                        self._on_enemy_death(e)
                            
                            # 投掷物特殊效果：燃烧瓶创建持续燃烧区域
                            if hasattr(proj, 'is_grenade_type') and proj.is_grenade_type == WeaponType.MOLOTOV:
                                if not hasattr(self, 'fire_zones'):
                                    self.fire_zones = []
                                burn_r = getattr(proj, 'burn_radius', 80)
                                burn_d = getattr(proj, 'burn_duration', 5.0)
                                self.fire_zones.append({
                                    "x": proj.x, "y": proj.y, "radius": burn_r,
                                    "timer": burn_d, "damage_timer": 0.0,
                                })
                                self.floating_texts.append(FloatingText(proj.x, proj.y - 30, "燃烧区域!", color=(255,120,30), lifetime=1.5))
                            # 投掷物特殊效果：烟雾弹创建减速烟雾区域
                            if hasattr(proj, 'is_grenade_type') and proj.is_grenade_type == WeaponType.SMOKE_GRENADE:
                                if not hasattr(self, 'smoke_zones'):
                                    self.smoke_zones = []
                                slow_r = getattr(proj, 'slow_radius', 100)
                                slow_d = getattr(proj, 'slow_duration', 8.0)
                                self.smoke_zones.append({
                                    "x": proj.x, "y": proj.y, "radius": slow_r,
                                    "timer": slow_d, "damage_timer": 0.0,
                                })
                                self.floating_texts.append(FloatingText(proj.x, proj.y - 30, "烟雾区域!", color=(180,180,180), lifetime=1.5))
                        break  # 爆炸后不再继续检测

                    is_crit = random.random() < self.player.crit_chance
                    actual_damage = proj.damage * (self.player.crit_damage if is_crit else 1)
                    # 记录伤害和暴击
                    if self.session:
                        self.session.add_damage_dealt(actual_damage)
                        if is_crit:
                            self.session.add_critical_hit()

                    # 机枪压制效果 - 大幅增强
                    weapon = self.player.get_current_weapon()
                    if hasattr(weapon, 'suppression') and weapon.suppression:
                        push_angle = math.atan2(enemy.y - self.player.y, enemy.x - self.player.x)
                        enemy.x += math.cos(push_angle) * 15
                        enemy.y += math.sin(push_angle) * 15
                        enemy.knockdown_timer = max(enemy.knockdown_timer, 0.3)
                        self.particles.spawn_blood(enemy.x, enemy.y, 18)
                        # 压制特效
                        self.particles.spawn(enemy.x, enemy.y, (255, 80, 30), 3, (2, 5), (-3, 3), (0.2, 0.5))
                        if random.random() < 0.2:
                            self.floating_texts.append(FloatingText(
                                enemy.x, enemy.y - 30, "压制!", color=RED, lifetime=0.8
                            ))

                    enemy.take_damage(actual_damage)
                    self._vampire_heal(actual_damage)
                    # 根据武器类型施加debuff
                    wtype = weapon.weapon_type
                    if wtype == WeaponType.FLAMETHROWER or getattr(weapon, 'is_flame', False):
                        enemy.apply_buff(BuffType.BURN, duration=4.0)
                    elif wtype == WeaponType.CROSSBOW:
                        if random.random() < 0.5:
                            enemy.apply_buff(BuffType.BLEED, duration=5.0)
                    elif wtype == WeaponType.PLASMA_RIFLE:
                        if random.random() < 0.3:
                            enemy.apply_buff(BuffType.SLOW, duration=2.0)
                    # === 附魔技能debuff ===
                    # 元素精通加成
                    elem_skill = self.player.skill_tree.get_skill(SkillType.ELEMENTAL_MASTERY)
                    elem_mult = 1.0 + (0.3 * (elem_skill.current_level if elem_skill else 0))
                    # 火焰附魔
                    flame_skill = self.player.skill_tree.get_skill(SkillType.FLAME_ENCHANT)
                    if flame_skill and flame_skill.current_level > 0:
                        flame_chances = {1: 0.2, 2: 0.3, 3: 0.4, 4: 0.5, 5: 0.6}
                        flame_durs = {1: 3, 2: 4, 3: 5, 4: 6, 5: 8}
                        if random.random() < flame_chances.get(flame_skill.current_level, 0.2):
                            enemy.apply_buff(BuffType.BURN, duration=flame_durs.get(flame_skill.current_level, 3) * elem_mult)
                    # 冰霜附魔
                    frost_skill = self.player.skill_tree.get_skill(SkillType.FROST_ENCHANT)
                    if frost_skill and frost_skill.current_level > 0:
                        frost_chances = {1: 0.2, 2: 0.3, 3: 0.4, 4: 0.5, 5: 0.6}
                        frost_durs = {1: 3, 2: 4, 3: 5, 4: 2, 5: 3}
                        if random.random() < frost_chances.get(frost_skill.current_level, 0.2):
                            if frost_skill.current_level >= 4:
                                enemy.apply_buff(BuffType.FREEZE, duration=frost_durs.get(frost_skill.current_level, 2) * elem_mult)
                                if self.session:
                                    self.session.add_enemy_frozen()
                            else:
                                enemy.apply_buff(BuffType.SLOW, duration=frost_durs.get(frost_skill.current_level, 3) * elem_mult)
                    # 剧毒附魔
                    poison_skill = self.player.skill_tree.get_skill(SkillType.POISON_ENCHANT)
                    if poison_skill and poison_skill.current_level > 0:
                        poison_chances = {1: 0.15, 2: 0.25, 3: 0.35, 4: 0.45, 5: 0.55}
                        poison_durs = {1: 5, 2: 6, 3: 7, 4: 8, 5: 10}
                        if random.random() < poison_chances.get(poison_skill.current_level, 0.15):
                            enemy.apply_buff(BuffType.POISON, duration=poison_durs.get(poison_skill.current_level, 5) * elem_mult)
                    self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, actual_damage, is_crit=is_crit, damage_type="ranged"))
                    self.particles.spawn_blood(enemy.x, enemy.y, 5)

                    if self.player.life_steal > 0:
                        heal_amt = actual_damage * self.player.life_steal
                        self.player.heal(heal_amt)
                        # 吸血屏幕效果，强度与吸血量挂钩
                        self.lifesteal_flash = min(1.0, self.lifesteal_flash + heal_amt / 30.0)

                    if not enemy.alive:
                        self._on_enemy_death(enemy)

                    if proj.pierce <= 0:
                        proj.alive = False
                        break

        for proj in self.enemy_projectiles[:]:
            proj.update(dt)
            if not proj.alive:
                self.enemy_projectiles.remove(proj)
                continue
            hit_any = False
            for _p in self._alive_players():
                if proj.get_rect().colliderect(_p.get_rect()):
                    hit_any = True
                    # 检测是否被盾牌阻挡
                    dx = proj.x - _p.x
                    dy = proj.y - _p.y
                    attack_angle = math.atan2(dy, dx)
                    facing_rad = math.radians(_p.facing_angle)
                    angle_diff = abs(math.atan2(math.sin(attack_angle - facing_rad),
                                               math.cos(attack_angle - facing_rad)))
                    from_front = angle_diff < math.pi / 3
                    if _p.riot_gear.equipped and from_front and not _p.riot_gear.shield_broken:
                        # 盾牌阻挡远程攻击
                        _p.riot_gear.take_damage(proj.damage * 0.3, "ranged", True, proj.x, proj.y)
                        proj.alive = False
                        self.particles.spawn(proj.x, proj.y, CYAN, 5, (2, 4), (-2, 2), (0.2, 0.5))
                        self.floating_texts.append(FloatingText(proj.x, proj.y - 20, "格挡!", color=CYAN, lifetime=0.5))
                    else:
                        _p.take_damage(proj.damage, "ranged")
                        proj.alive = False
                        if self.config.screen_shake:
                            (self.camera if _p is self.player else self.camera2).shake(2, 0.15)
                    break
            if hit_any:
                continue

        # 更新烟雾区域
        if hasattr(self, 'smoke_zones'):
            for zone in self.smoke_zones[:]:
                zone["timer"] -= dt
                if zone["timer"] <= 0:
                    self.smoke_zones.remove(zone)
                else:
                    dist_pl = math.hypot(self.player.x - zone["x"], self.player.y - zone["y"])
                    if dist_pl < zone["radius"]:
                        self.player.speed_mult = 0.5
                    if random.random() < 0.3:
                        angle = random.uniform(0, math.pi * 2)
                        r = random.uniform(0, zone["radius"])
                        self.particles.spawn_particle(
                            zone["x"] + math.cos(angle) * r,
                            zone["y"] + math.sin(angle) * r,
                            random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5),
                            GRAY, 1.0, 10
                        )

        # 更新手雷
        if hasattr(self, 'grenades'):
            for grenade in self.grenades[:]:
                grenade["timer"] -= dt
                if grenade["timer"] <= 0:
                    self.particles.spawn_explosion(grenade["target_x"], grenade["target_y"], ORANGE, 50)
                    self.camera.shake(8, 0.4)
                    if self.camera2:
                        self.camera2.shake(8, 0.4)
                    for _p in self._alive_players():
                        dist_pl = math.hypot(_p.x - grenade["target_x"], _p.y - grenade["target_y"])
                        if dist_pl < grenade["radius"]:
                            dmg = grenade["damage"] * (1 - dist_pl / grenade["radius"])
                            _p.take_damage(int(dmg), damage_type="aoe", attack_x=grenade["target_x"], attack_y=grenade["target_y"])
                    self.grenades.remove(grenade)

        # 更新经验球
        for orb in self.exp_orbs[:]:
            orb.update(dt, self.player.x, self.player.y, self.player.pickup_range)
            if math.hypot(orb.x - self.player.x, orb.y - self.player.y) < 20:
                self.player.gain_exp(orb.value)
                # 记录经验收集
                if self.session:
                    self.session.add_exp(orb.value)
                # 播放拾取音效
                self.assets.play_sound("pickup_exp")
                self.exp_orbs.remove(orb)
            elif not orb.alive:
                self.exp_orbs.remove(orb)

        # 拾取特殊道具
        for item in self.world.items[:]:
            if math.hypot(item.x - self.player.x, item.y - self.player.y) < 25:
                self._apply_item_effect(item.item_type)
                item.alive = False
            if not item.alive:
                self.world.items.remove(item)

        # 更新和拾取文本资料
        for text_item in self.text_items[:]:
            text_item.update(dt, self.player.x, self.player.y)
            if math.hypot(text_item.x - self.player.x, text_item.y - self.player.y) < 25:
                # 拾取文本资料
                self.collected_texts.add(text_item.text_id)
                self.current_viewing_text = text_item.text_id
                self.text_items.remove(text_item)
                self.assets.play_sound("pickup_exp")
                self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "获得文本资料！", (200, 180, 100)))
                # 保存已收集文本
                try:
                    self._save_collected_texts()
                except Exception:
                    pass
                # 进入文本查看界面
                self.state = GameState.TEXT_VIEWER
                continue
            if not text_item.alive:
                self.text_items.remove(text_item)

        self.particles.update(dt)
        for dn in self.damage_numbers[:]:
            dn.update(dt)
            if not dn.is_alive():
                self.damage_numbers.remove(dn)
        for ft in self.floating_texts[:]:
            ft.update(dt)
            if not ft.is_alive():
                self.floating_texts.remove(ft)
        # v2.0.9：渲染列表有界，防止极端时刻（大伤害/大规模AOE）瞬时爆炸导致卡顿
        if len(self.damage_numbers) > 120:
            del self.damage_numbers[:len(self.damage_numbers) - 120]
        if len(self.floating_texts) > 60:
            del self.floating_texts[:len(self.floating_texts) - 60]
        for sa in self.slash_arcs[:]:
            sa.update(dt)
            if not sa.is_alive():
                self.slash_arcs.remove(sa)
        for sr in self.sweep_rings[:]:
            sr["life"] -= dt
            if sr["life"] <= 0:
                self.sweep_rings.remove(sr)

        # 摄像机跟随
        self.camera.follow(self.player.x, self.player.y, dt)
        if self.player2:
            if self.camera2:
                self.camera2.follow(self.player2.x, self.player2.y, dt)
            self._update_player2(dt)

        if self.is_multiplayer_active():
            # 双人/联机：救援系统——全部倒地才游戏结束
            if self._update_rescue(dt):
                self._trigger_multiplayer_game_over()
        elif self.player.hp <= 0:
            self._trigger_multiplayer_game_over()

    def _trigger_multiplayer_game_over(self):
        """触发游戏结束结算（单/双人共用）"""
        if self.state != GameState.PLAYING:
            return
        # 单人模式：正常游戏结束
        if self.session:
            self.session.set_died(True)
            new_unlock_keys = self.session.finalize() or []
            for k in new_unlock_keys:
                ach_data = self.records.data["achievements"].get(k)
                if ach_data:
                    self.ach_toast_queue.append({
                        "key":k,
                        "desc": ach_data["desc"],
                        "timer":4.0
                    })
            self.session = None
        # 播放失败音乐
        self.assets.play_music("gameover")
        self.delete_saved_game()
        self.state = GameState.GAME_OVER

        if self.horde_manager.is_timed_over():
            self._final_dialogue()

        if self.config.game_mode == GameMode.ENDLESS:
            if self.boss_kills["long"] >= 3 and self.boss_kills["xiang"] >= 3:
                self._final_dialogue()
        # 更新成就toast提示队列（此处无帧dt，用固定步长清理过期项）
        remove_list = []
        for toast in self.ach_toast_queue:
            toast["timer"] -= 0.1
            if toast["timer"] <= 0:
                remove_list.append(toast)
        for t in remove_list:
            self.ach_toast_queue.remove(t)

    def _get_all_player_targets(self):
        """获取所有存活玩家目标列表（单人模式只有本地玩家），用于怪物AI选择目标"""
        targets = []
        if self.player and self.player.alive:
            targets.append({
                "id": "player",
                "x": self.player.x, "y": self.player.y,
                "obj": self.player, "is_local": True
            })
        if self.player2 and self.player2.alive:
            targets.append({
                "id": "player2",
                "x": self.player2.x, "y": self.player2.y,
                "obj": self.player2, "is_local": False
            })
        return targets

    def _damage_player_target(self, target, damage, damage_type="melee", attack_x=0, attack_y=0):
        """对玩家目标造成伤害（单人模式只有本地玩家）"""
        if target.get("obj") is not None:
            target["obj"].take_damage(damage, damage_type=damage_type, attack_x=attack_x, attack_y=attack_y)

    def _update_grapple_collision(self):
        """更新钩爪碰撞检测 - 敌人/道具/经验球/文本资料/宝箱全部可勾"""
        if not self.player.riot_gear.grapple_active:
            return
        if self.player.riot_gear.grapple_state != "shooting":
            return

        head_pos = self.player.riot_gear.grapple_head_pos
        if not head_pos:
            return

        grapple_skill = self.player.skill_tree.get_skill(SkillType.GRAPPLE_PULL)
        grapple_lvl = grapple_skill.current_level if grapple_skill else 1

        # 检测钩爪头与敌人的碰撞
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = math.hypot(enemy.x - head_pos[0], enemy.y - head_pos[1])
            if dist < enemy.size + 12:
                # 钩爪伤害
                base_dmg = 15 + grapple_lvl * 10
                enemy.take_damage(base_dmg)
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, base_dmg, color=ORANGE))
                # 高等级AOE
                if grapple_lvl >= 5:
                    aoe_radius = 120
                    aoe_dmg = base_dmg * 2
                    for e2 in self.enemies:
                        if e2 is not enemy and e2.alive:
                            d2 = math.hypot(e2.x - enemy.x, e2.y - enemy.y)
                            if d2 < aoe_radius:
                                e2.take_damage(aoe_dmg)
                                self.damage_numbers.append(DamageNumber(e2.x, e2.y, aoe_dmg, color=RED))
                    # 爆炸特效
                    for _ in range(20):
                        ang = random.uniform(0, math.pi * 2)
                        spd = random.uniform(2, 6)
                        self.particles.spawn(enemy.x, enemy.y, FIRE_ORANGE, 1, (6, 12),
                                            (math.cos(ang)*spd, math.sin(ang)*spd), (0.5, 1.0))
                elif grapple_lvl >= 3:
                    aoe_radius = 60
                    aoe_dmg = int(base_dmg * 0.5)
                    for e2 in self.enemies:
                        if e2 is not enemy and e2.alive:
                            d2 = math.hypot(e2.x - enemy.x, e2.y - enemy.y)
                            if d2 < aoe_radius:
                                e2.take_damage(aoe_dmg)
                # 4级以上眩晕
                if grapple_lvl >= 4:
                    enemy.apply_buff(BuffType.STUN, duration=1.0)
                # Boss 免勾取：只能命中产生僵直/眩晕，不能拉回
                if getattr(enemy, "is_boss", False):
                    rg = self.player.riot_gear
                    rg.grapple_state = "retracting"
                    rg.grapple_hit_stun_timer = rg.grapple_hit_stun_duration * 0.5
                    rg.grapple_target = None
                    enemy.apply_buff(BuffType.STUN, duration=0.8)
                    self.floating_texts.append(FloatingText(
                        enemy.x, enemy.y - 30, "僵直!", color=YELLOW, lifetime=1.0
                    ))
                    return
                # 勾中敌人
                self.player.riot_gear.set_grapple_target(enemy)
                self.player.riot_gear.grapple_state = "hit"
                self.player.riot_gear.grapple_hit_stun_timer = self.player.riot_gear.grapple_hit_stun_duration
                enemy.grappled = True
                self.floating_texts.append(FloatingText(
                    enemy.x, enemy.y - 30, "勾中!", color=GREEN, lifetime=1.0
                ))
                return

        # 检测经验球 - 磁化拉向玩家
        for orb in self.exp_orbs:
            if not orb.alive:
                continue
            dist = math.hypot(orb.x - head_pos[0], orb.y - head_pos[1])
            if dist < orb.size + 12:
                orb.magnetized = True
                self.player.riot_gear._reset_grapple()
                return

        # 检测世界道具 - 磁化拉向玩家
        for item in self.world.items:
            if not item.alive:
                continue
            dist = math.hypot(item.x - head_pos[0], item.y - head_pos[1])
            if dist < item.size + 12:
                item.magnetized = True
                self.player.riot_gear._reset_grapple()
                return

        # 检测文本资料
        if hasattr(self, 'text_items'):
            for ti in self.text_items:
                if not ti.alive:
                    continue
                dist = math.hypot(ti.x - head_pos[0], ti.y - head_pos[1])
                if dist < 20:
                    ti.magnetized = True
                    self.player.riot_gear._reset_grapple()
                    return

        # 检测剧情碎片
        if hasattr(self, 'story_fragment_items'):
            for si in self.story_fragment_items:
                dist = math.hypot(si["x"] - head_pos[0], si["y"] - head_pos[1])
                if dist < 20:
                    si["magnetized"] = True
                    self.player.riot_gear._reset_grapple()
                    return

        # 检测特殊道具/宝箱
        if hasattr(self, 'special_items'):
            for si in self.special_items:
                if not si.alive:
                    continue
                dist = math.hypot(si.x - head_pos[0], si.y - head_pos[1])
                if dist < getattr(si, 'size', 15) + 12:
                    si.magnetized = True
                    self.player.riot_gear._reset_grapple()
                    return
