# -*- coding: utf-8 -*-
"""MultiplayerMixin - 由 game.py 自动拆分，逻辑等价"""

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

class MultiplayerMixin:
    def _setup_multiplayer_controls(self):
        """同屏双人：P1 控件移到左半屏，新建 P2 控件（右半屏）；默认布局各自半屏内分散，避免误触"""
        # P1 控件重定位（左半屏 0-640 逻辑坐标）
        self.joystick = VirtualJoystick(130, BASE_HEIGHT - 120, 70)
        self.aim_button = AimButton(500, BASE_HEIGHT - 150, 62)
        self.touch_buttons["shoot"] = TouchButton(500, BASE_HEIGHT - 150, 62, "射击", RED)
        self.touch_buttons["pause"] = TouchButton(60, 55, 38, "II", GRAY)
        self.touch_buttons["sprint"] = TouchButton(220, BASE_HEIGHT - 135, 40, "疾跑", AMBER)
        self.skill_selector = SkillSelector(490, BASE_HEIGHT - 340, 42)
        self.skill_caster = SkillCaster(590, BASE_HEIGHT - 100, 52)
        self.throwable_switch_btn = TouchButton(370, BASE_HEIGHT - 340, 42, "投掷", ORANGE)
        self.throwable_caster = SkillCaster(415, BASE_HEIGHT - 120, 48)
        # 注意：双人模式禁用已保存的全屏 HUD 布局（会覆盖 P1 控件回右半屏与 P2 重叠）
        # P2 控件（右半屏 640-1280 逻辑坐标）
        self.p2_controls = {
            "joystick": VirtualJoystick(640 + 130, BASE_HEIGHT - 120, 70),
            "aim": AimButton(640 + 500, BASE_HEIGHT - 150, 62),
            "shoot": TouchButton(640 + 500, BASE_HEIGHT - 150, 62, "射击", RED),
            "pause": TouchButton(640 + 60, 55, 38, "II", GRAY),
            "sprint": TouchButton(640 + 220, BASE_HEIGHT - 135, 40, "疾跑", AMBER),
            "skill_selector": SkillSelector(640 + 490, BASE_HEIGHT - 340, 42),
            "skill_caster": SkillCaster(640 + 580, BASE_HEIGHT - 100, 52),
            "throwable_switch": TouchButton(640 + 370, BASE_HEIGHT - 340, 42, "投掷", ORANGE),
            "throwable_caster": SkillCaster(640 + 415, BASE_HEIGHT - 120, 48),
        }
        self.p2_selected_skill = SkillType.GRENADE  # P2 基础技能默认手雷（与单机一致）
        # P2 键控技能 U 长按预瞄状态（照 G 键模板）
        self.key_u_press_start = 0
        self.key_u_held = False
        self.u_aim_started = False
        self.key_u_long_threshold = 0.4
        self.p2_selected_throwable = "incendiary"
        self.p2_fire_held = False
        self._p2_finger_ids = set()  # P2 触控手指（右半屏）
        # 双人独立 HUD 布局：P1 用 mp_p1_layout，P2 用 p2_hud_layout（单机 hud_layout 完全独立）
        if getattr(self.config, 'mp_p1_layout', None):
            self._apply_layout_to(self.config.mp_p1_layout)
        lay2 = getattr(self.config, 'p2_hud_layout', None) or {}
        if lay2:
            def _set2(ctrl, key):
                if ctrl is not None and key in lay2:
                    try:
                        ctrl.base_x = int(lay2[key][0])
                        ctrl.base_y = int(lay2[key][1])
                    except (TypeError, IndexError, ValueError):
                        pass
            c2 = self.p2_controls
            _set2(c2["joystick"], "joystick")
            _set2(c2["aim"], "aim")
            _set2(c2["shoot"], "shoot")
            _set2(c2["pause"], "pause")
            _set2(c2["sprint"], "sprint")
            _set2(c2["skill_selector"], "skill_selector")
            _set2(c2["skill_caster"], "skill_caster")
            _set2(c2["throwable_switch"], "throwable_switch")
            _set2(c2["throwable_caster"], "throwable_caster")
        logger.info("同屏双人控件初始化完成")

    def _update_player2(self, dt):
        """更新第二位玩家：移动/射击/技能/投掷/拾取（同屏键控或网络输入）"""
        p2 = self.player2
        if not p2 or not getattr(p2, "alive", True):
            return
        # ===== 输入来源 =====
        if self.multiplayer_mode == "network" and self.net_host:
            ci = self.net_host.get_input()
            mx = float(ci.get("mx", 0))
            my = float(ci.get("my", 0))
            shoot = bool(ci.get("shoot", False))
            skill = bool(ci.get("skill", False))
            throw = bool(ci.get("throw", False))
            sprint = bool(ci.get("sprint", False))
        else:
            # 触控模式：先把触摸事件分发给 P2 控件（右半屏）
            if self.config.control_mode == ControlMode.TOUCH and self.p2_controls:
                for _tev in self.touch_events:
                    if _tev["type"] == "down":
                        x, y = _tev["pos"]
                        if x >= self.scaled_width // 2:
                            self._p2_finger_ids.add(_tev["id"])
                    elif _tev["type"] == "up":
                        self._p2_finger_ids.discard(_tev["id"])
                self.p2_controls["joystick"].handle_touch(self.touch_events, self.scale, self._p2_finger_ids)
                self.p2_controls["aim"].handle_touch(self.touch_events, self.scale)
                for name in ("shoot", "sprint", "skill_selector", "skill_caster", "throwable_switch", "throwable_caster"):
                    self.p2_controls[name].handle_touch(self.touch_events, self.scale)
            mx, my, shoot, skill, throw, sprint = self._get_p2_local_input()
            # P2 键控技能 U 长按：预瞄瞄准（照 G 键模板）
            if self.config.control_mode != ControlMode.TOUCH and self.key_u_held and self.p2_controls:
                hold_t = time.time() - self.key_u_press_start
                c2 = self.p2_controls
                c2["skill_caster"].set_player_pos(p2.x, p2.y, self.camera2.x, self.camera2.y)
                c2["skill_caster"].set_max_distance(self._get_skill_max_distance(self.p2_selected_skill or SkillType.GRENADE))
                if not self.u_aim_started and hold_t >= self.key_u_long_threshold:
                    self.u_aim_started = True
                    c2["skill_caster"].is_aiming = True
                if self.u_aim_started:
                    aim_ang = math.radians(self._p2_auto_aim_angle(p2))
                    c2["skill_caster"].set_aim_angle(aim_ang)
                    c2["skill_caster"].set_distance_ratio(1.0)
            # 触控模式：P2 控件输入（右半屏）
            if self.config.control_mode == ControlMode.TOUCH and self.p2_controls:
                joystick2 = self.p2_controls["joystick"]
                if joystick2.active:
                    dx, dy = joystick2.get_direction()
                    if dx or dy:
                        mx, my = dx, dy
                aim2 = self.p2_controls["aim"]
                if aim2.is_shooting:
                    shoot = True
                if aim2.is_aiming:
                    pass
                if self.p2_controls["sprint"].pressed:
                    sprint = True
                # 填充 P2 技能释放控件数据（长按/拖拽预瞄用）
                c2sc = self.p2_controls["skill_caster"]
                c2sc.set_player_pos(p2.x, p2.y, self.camera2.x, self.camera2.y)
                c2sc.set_max_distance(self._get_skill_max_distance(self.p2_selected_skill or SkillType.GRENADE))
                if self.p2_controls["skill_caster"].just_released:
                    skill = True
                    # 触控长按/拖拽预瞄状态（handle_touch 会在 up 时重置 is_aiming）
                    self._p2_cast_aimed = self.p2_controls["skill_caster"].was_aiming_on_release
                    self._p2_cast_angle = self.p2_controls["skill_caster"].angle
                    self._p2_cast_ratio = self.p2_controls["skill_caster"].distance_ratio
                if self.p2_controls["throwable_caster"].just_released:
                    throw = True
                # P2 技能切换（短按）
                if self.p2_controls["skill_selector"].just_released:
                    sts = self._get_unlocked_skills_for(p2)
                    if sts:
                        if self.p2_selected_skill not in sts:
                            self.p2_selected_skill = sts[0]
                        else:
                            idx = sts.index(self.p2_selected_skill)
                            self.p2_selected_skill = sts[(idx + 1) % len(sts)]
                        skill_obj = p2.skill_tree.get_skill(self.p2_selected_skill)
                        self.floating_texts.append(FloatingText(
                            p2.x, p2.y - 40,
                            f"P2技能: {skill_obj.name if skill_obj else '空'}", color=GOLD, lifetime=1.5))
        # ===== 瞄准角度：触控摇杆 / 最近敌人 / 保持原朝向 =====
        angle = p2.facing_angle
        if self.config.control_mode == ControlMode.TOUCH and self.p2_controls:
            a2 = self.p2_controls["aim"]
            if a2.active and (a2.knob_offset_x or a2.knob_offset_y):
                angle = math.degrees(math.atan2(a2.knob_offset_y, a2.knob_offset_x))
            else:
                angle = self._p2_auto_aim_angle(p2)
        else:
            angle = self._p2_auto_aim_angle(p2)
        # ===== 移动 =====
        if mx != 0 or my != 0:
            p2.update(dt, mx, my, angle, self.world, sprinting=sprint)
        else:
            p2.update(dt, 0, 0, angle, self.world, sprinting=sprint)
        p2.facing_angle = angle
        # ===== 射击 =====
        if shoot and p2.can_act():
            weapon = p2.get_current_weapon()
            if weapon.can_fire():
                projs = weapon.fire(
                    p2.x, p2.y, math.radians(angle),
                    p2.damage_mult * p2.buff_manager.get_damage_mult() * p2.damage_multiplier,
                    p2.speed_mult, player=p2)
                self.projectiles.extend(projs)
                self.assets.play_sound_random(["shoot_pistol", "melee_swing"])
        # ===== 技能 =====
        if skill:
            st = self.p2_selected_skill
            if st is None:
                sts = self._get_unlocked_skills_for(p2)
                if sts:
                    st = sts[0]
            if st:
                if getattr(self, '_p2_cast_aimed', False):
                    # 触控长按/拖拽预瞄释放（方向+距离）
                    self._use_skill_p2_aimed(st, getattr(self, '_p2_cast_angle', p2.facing_angle),
                                             getattr(self, '_p2_cast_ratio', 1.0))
                else:
                    self._use_skill_p2(st)
        # ===== 投掷 =====
        if throw:
            self._throw_p2()
        # ===== 拾取 =====
        self._pickup_for_player(p2)
        # ===== 受击数字/死亡 =====
        # v2.0.9 修复：遍历后必须清空事件列表（此前未清空导致持续累积、大伤害时严重卡顿）
        for dmg, dtype in getattr(p2, 'buff_damage_events', []):
            if dmg > 0:
                self.damage_numbers.append(DamageNumber(
                    p2.x + random.uniform(-15, 15), p2.y - 20, dmg, damage_type=dtype))
        p2.buff_damage_events = []

    def _p2_auto_aim_angle(self, p2):
        """P2 自动瞄准：朝向最近敌人"""
        best = None
        best_d = 1e9
        for e in self.enemies:
            if not getattr(e, 'alive', True):
                continue
            d = (e.x - p2.x) ** 2 + (e.y - p2.y) ** 2
            if d < best_d:
                best_d = d
                best = e
        if best is not None:
            return math.degrees(math.atan2(best.y - p2.y, best.x - p2.x))
        return p2.facing_angle

    def _use_skill_p2(self, skill_type):
        """玩家2使用技能（P2 精简实现，覆盖常用主动技与传说专属技）"""
        p2 = self.player2
        if not p2:
            return
        if skill_type in p2.active_skills:
            self.floating_texts.append(FloatingText(p2.x, p2.y - 40, "冷却中...", color=GRAY, lifetime=1.0))
            return
        cd = 10.0 * p2.cooldown_mult
        # 简易执行
        ok = False
        if skill_type == SkillType.DASH:
            ok = True
            p2.invincible_timer = max(p2.invincible_timer, 0.3)
            p2.x += math.cos(math.radians(p2.facing_angle)) * 120
            p2.y += math.sin(math.radians(p2.facing_angle)) * 120
            cd = 5.0
        elif skill_type == SkillType.GRENADE:
            ok = True
            self._spawn_grenade(p2.x, p2.y, p2.facing_angle, p2)
            cd = 8.0
        elif skill_type == SkillType.SHOCKWAVE:
            ok = True
            for e in self.enemies:
                if not getattr(e, 'alive', True): continue
                if math.hypot(e.x - p2.x, e.y - p2.y) <= 200:
                    e.take_damage(60 * p2.damage_multiplier, damage_type="aoe")
                    e.knockdown_timer = 0.8
            self.slash_arcs.append(SlashArc(p2.x, p2.y, 0, 200, (255, 220, 100), lifetime=0.4, kind="scythe",
                                            start_radius=150, end_angle_offset=3.0))
            cd = 12.0
        elif skill_type == SkillType.ICE_NOVA:
            ok = True
            from buff import BuffType
            for e in self.enemies:
                if not getattr(e, 'alive', True): continue
                if math.hypot(e.x - p2.x, e.y - p2.y) <= 240:
                    e.buff_manager.add_buff(BuffType.FROST, duration=3.0)
                    e.take_damage(40 * p2.damage_multiplier, damage_type="aoe")
            cd = 20.0
        elif skill_type == SkillType.SCYTHE_DANCE:
            ok = self._skill_p2_scythe_dance(p2)
            cd = 30.0
        elif skill_type == SkillType.MINIGUN_OVERDRIVE:
            p2.overdrive_timer = 5.0
            p2.overdrive_mult = 3.0
            ok = True
            cd = 25.0
        elif skill_type == SkillType.RAILGUN_ANNIHILATION:
            ok = True
            dmg = 300 * p2.damage_multiplier
            proj = Projectile(p2.x, p2.y, math.cos(math.radians(p2.facing_angle)) * 3,
                              math.sin(math.radians(p2.facing_angle)) * 3, dmg, 1200, (140, 200, 245), 15,
                              pierce=99, explosive=True, explosion_radius=90,
                              is_laser=True, laser_width=50, laser_duration=0.85)
            self.projectiles.append(proj)
            cd = 35.0
        else:
            self.floating_texts.append(FloatingText(p2.x, p2.y - 40, "该技能暂不支持双人", color=GRAY, lifetime=1.2))
            return
        if ok:
            p2.active_skills[skill_type] = cd
            self.floating_texts.append(FloatingText(p2.x, p2.y - 45, "技能释放!", color=GOLD, lifetime=1.5))

    def _use_skill_p2_aimed(self, skill_type, angle, distance_ratio=1.0):
        """P2 带瞄准方向/距离的技能释放（触控长按拖拽/键控长按）"""
        p2 = self.player2
        if not p2:
            return False
        if not p2.can_act():
            return False
        if skill_type in p2.active_skills:
            self.floating_texts.append(FloatingText(p2.x, p2.y - 40, "冷却中...", color=GRAY, lifetime=1.0))
            return False
        cd = 10.0 * p2.cooldown_mult
        ok = False
        if skill_type == SkillType.GRENADE:
            actual_dist = self._get_skill_max_distance(SkillType.GRENADE) * max(0.1, distance_ratio)
            tx = p2.x + math.cos(angle) * actual_dist
            ty = p2.y + math.sin(angle) * actual_dist
            self._throw_skill_grenade_p2(tx, ty, p2)
            ok = True
            cd = 8.0
        elif skill_type == SkillType.RAILGUN_ANNIHILATION:
            lv = self._legendary_skill_level(SkillType.RAILGUN_ANNIHILATION, p2)
            dmg = (300 + 80 * (lv - 1)) * p2.damage_multiplier * p2.buff_manager.get_damage_mult()
            width = {1: 40, 2: 40, 3: 55, 4: 70, 5: 85}[lv]
            proj = Projectile(p2.x, p2.y, math.cos(angle) * 3, math.sin(angle) * 3,
                              dmg, 1200, (140, 200, 245), 15,
                              pierce=99, explosive=True, explosion_radius=90,
                              is_laser=True, laser_width=width, laser_duration=0.85)
            self.projectiles.append(proj)
            ok = True
            cd = 35.0
        elif skill_type == SkillType.SCYTHE_DANCE:
            ok = self._skill_p2_scythe_dance(p2)
            cd = 30.0
        elif skill_type == SkillType.MINIGUN_OVERDRIVE:
            p2.overdrive_timer = 5.0
            p2.overdrive_mult = 3.0
            ok = True
            cd = 25.0
        elif skill_type == SkillType.SHOCKWAVE:
            ok = True
            for e in self.enemies:
                if not getattr(e, 'alive', True):
                    continue
                if math.hypot(e.x - p2.x, e.y - p2.y) <= 200:
                    e.take_damage(60 * p2.damage_multiplier, damage_type="aoe")
                    e.knockdown_timer = 0.8
            self.slash_arcs.append(SlashArc(p2.x, p2.y, 0, 200, (255, 220, 100), lifetime=0.4, kind="scythe",
                                            start_radius=150, end_angle_offset=3.0))
            cd = 12.0
        else:
            return self._use_skill_p2(skill_type)
        if ok:
            p2.active_skills[skill_type] = cd
            self.floating_texts.append(FloatingText(p2.x, p2.y - 45, "技能释放!", color=GOLD, lifetime=1.5))
        return ok

    def _skill_p2_scythe_dance(self, p2):
        """P2 死神镰刀专属技能（等级随 P2 武器等级成长）"""
        lv = self._legendary_skill_level(SkillType.SCYTHE_DANCE, p2)
        seg = {1: 3, 2: 4, 3: 5, 4: 6, 5: 8}[lv]
        radius = {1: 300, 2: 320, 3: 340, 4: 360, 5: 400}[lv]
        dmg = 60 * seg * p2.damage_multiplier * p2.buff_manager.get_damage_mult()
        for e in list(self.enemies):
            if not getattr(e, 'alive', True):
                continue
            if math.hypot(e.x - p2.x, e.y - p2.y) <= radius:
                e.take_damage(dmg, damage_type="aoe")
        for i in range(seg):
            ang = (math.pi * 2 / seg) * i
            self.slash_arcs.append(SlashArc(p2.x, p2.y, ang, radius * 0.8, (190, 80, 230), lifetime=0.55,
                                            kind="scythe", start_radius=radius * 0.5, end_angle_offset=3.0))
        self.sweep_rings.append({"x": p2.x, "y": p2.y, "r": radius * 0.3, "max_r": radius,
                                 "color": (190, 80, 230), "width": 10, "life": 0.5, "max_life": 0.5})
        return True

    def _throw_skill_grenade_p2(self, tx, ty, p2):
        """P2 定向手雷：向目标点投掷（带附魔，与 P1 一致走 grenades_in_flight）"""
        if not hasattr(self, 'grenades_in_flight'):
            self.grenades_in_flight = []
        dx = tx - p2.x
        dy = ty - p2.y
        total_dist = math.hypot(dx, dy)
        speed = total_dist / 1.1 if total_dist > 0 else 300
        if total_dist > 0:
            vx = dx / total_dist * speed
            vy = dy / total_dist * speed
        else:
            vx, vy = 0, -300
        p2.facing_angle = math.degrees(math.atan2(dy, dx)) if total_dist > 0 else p2.facing_angle
        skill = p2.skill_tree.get_skill(SkillType.GRENADE)
        skill_level = skill.current_level if skill else 1
        g_effects = ["frag"]
        if skill_level >= 2:
            g_effects.append("fire")
        if skill_level >= 3:
            g_effects.append("frost")
        if skill_level >= 4:
            g_effects.append("poison")
        if skill_level >= 5:
            g_effects.append("nuke")
        self.grenades_in_flight.append({
            "type": "frag",
            "effects": g_effects,
            "x": p2.x, "y": p2.y,
            "vx": vx, "vy": vy,
            "timer": 1.1,
            "target_x": tx, "target_y": ty,
        })
        self.assets.play_sound("grenade_throw")

    def _throw_p2(self):
        """P2 投掷物释放（简化：燃烧弹）"""
        p2 = self.player2
        if not p2:
            return
        ang = math.radians(p2.facing_angle)
        proj = Projectile(p2.x, p2.y, math.cos(ang) * 10, math.sin(ang) * 10,
                          30, 300, (255, 100, 0), 6, is_flame=True)
        self.projectiles.append(proj)
        self.assets.play_sound("grenade_throw")

    def _pickup_for_player(self, player):
        """玩家拾取掉落物（world.items）"""
        items = getattr(getattr(self, 'world', None), 'items', None)
        if not items:
            return
        for drop in list(items):
            d = math.hypot(drop.x - player.x, drop.y - player.y)
            if d <= getattr(player, 'pickup_range', 50):
                self._collect_drop(drop, player)
