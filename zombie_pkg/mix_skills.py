# -*- coding: utf-8 -*-
"""SkillsMixin - 由 game.py 自动拆分，逻辑等价"""

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

class SkillsMixin:
    def _sync_legendary_skill_level(self, player=None):
        """传说专属技能等级与武器等级同步（player 缺省= P1）"""
        pl = player if player is not None else self.player
        if not pl:
            return None
        try:
            w = pl.get_current_weapon()
            ls = self.LEGENDARY_WEAPON_SKILLS.get(w.weapon_type.name)
            if ls:
                sk = pl.skill_tree.get_skill(ls)
                if sk:
                    sk.current_level = min(sk.max_level, max(1, int(getattr(w, 'level', 1))))
                    return ls
        except Exception:
            pass
        return None

    def _get_unlocked_skills_for(self, player):
        """获取某玩家的已解锁主动技能列表（技能树主动 + 传说武器专属；初始无技能，手雷需技能树解锁）"""
        if not player:
            return []
        skills = list(player.skill_tree.get_unlocked_active_skills())
        ls = self._sync_legendary_skill_level(player)
        if ls and ls not in skills:
            skills.append(ls)
        return skills

    def _get_unlocked_skills(self):
        """获取已解锁的主动技能列表（基础 + 传说武器专属）"""
        return self._get_unlocked_skills_for(self.player)

    def _get_unlocked_skill_objects(self):
        """获取已解锁的主动技能对象列表（用于轮盘显示）"""
        if not self.player:
            return []
        unlocked = self._get_unlocked_skills()
        return [self.player.skill_tree.get_skill(st) for st in unlocked if self.player.skill_tree.get_skill(st)]

    def _get_skill_max_distance(self, skill_type):
        """获取技能的最大瞄准距离"""
        distances = {
            SkillType.GRENADE: 400,
            SkillType.AIRSTRIKE: 500,
            SkillType.GRAPPLE_PULL: 800,
            SkillType.BLINK: 300,
            SkillType.BLACK_HOLE: 400,
            SkillType.MEDIC_POD: 150,
            SkillType.CHAIN_LIGHTNING: 350,
            SkillType.DASH: 150,
            SkillType.FEARLESS_CHARGE: 120,   # v2.7.0 无畏冲锋（沿面朝方向冲撞，不需瞄准）
            # v2.5.7 传说级：湮灭射线（射线长度）/ 死亡轮回（AoE 半径）
            SkillType.RAILGUN_ANNIHILATION: 900,
            SkillType.SCYTHE_DANCE: 400,
        }
        return distances.get(skill_type, 500)

    def _grapple_cd_for(self, player):
        """v2.5.7 统一钩爪冷却（P1/P2 同一套规则）：
        技能 CD（SKILL_COOLDOWNS，2.0s × 冷却缩减）与防爆装备自带 CD 取较大者。
        修复：P2 此前只吃装备 CD（0.8s），比 P1（2.0s）快 2.5 倍。"""
        cd = get_skill_cooldown(SkillType.GRAPPLE_PULL, getattr(player, 'cooldown_mult', 1.0))
        rg = getattr(player, 'riot_gear', None)
        if rg is not None:
            try:
                gear_cd = (rg.grapple_scythe_max_cooldown if self._is_wielding_scythe_for(player)
                           else rg.grapple_max_cooldown)
                cd = max(cd, float(gear_cd))
            except Exception:
                pass
        return cd

    def _charge_locked(self, player=None):
        """v2.8.8：该玩家是否正处于无畏冲锋中（此时禁用一切主动操作，只能转向）"""
        _p = player if player is not None else getattr(self, 'player', None)
        if _p is None:
            return False
        return bool(getattr(_p, 'fearless_charge_active', False)) or \
               bool(getattr(getattr(_p, 'riot_gear', None), 'charge_active', False))

    def _blocked_by_charge(self, action="操作", player=None):
        """冲锋中禁用某项操作并给出提示"""
        try:
            self.floating_texts.append(FloatingText(
                getattr(player or self.player, 'x', 0),
                getattr(player or self.player, 'y', 0) - 50,
                f"冲锋中无法{action}!", color=(255, 130, 60), lifetime=1.0))
        except Exception:
            pass
        return False

    def _use_skill(self, skill_type):
        """使用指定技能"""
        try:
            trigger_hook(HOOK_SKILL_USE, skill_type, self.player)
        except Exception:
            pass
        if not self.player:
            return False
        # v2.8.8：无畏冲锋期间禁用技能释放键
        if self._charge_locked(self.player):
            return self._blocked_by_charge("使用技能", self.player)
        if not self.player.can_act():
            return False
        # v2.7.0 无畏冲锋期间：无法使用任何技能（冲锋中只能转向）
        if getattr(self.player, 'fearless_charge_active', False):
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 50, "冲锋中无法使用技能!", color=(255, 130, 60), lifetime=1.0))
            return False
        self._sync_legendary_skill_level()  # 传说专属技能等级与武器同步

        skill = self.player.skill_tree.get_skill(skill_type)
        if not skill or skill.current_level == 0:
            # 所有技能（含手雷）0级=未解锁，需先点技能树
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                f"技能未解锁!", color=GRAY, lifetime=1.5
            ))
            return False

        if skill_type in self.player.active_skills:
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                f"冷却中...", color=GRAY, lifetime=1.0
            ))
            return False

        # 检查并设置冷却（v2.5.7：统一走 config.SKILL_COOLDOWNS，P1/P2/预瞄一致）
        cd = get_skill_cooldown(skill_type, self.player.cooldown_mult)
        # v2.7.0 无畏冲锋：冷却按技能等级递减
        if skill_type == SkillType.FEARLESS_CHARGE:
            cd = get_fearless_charge_cooldown(skill.current_level, self.player.cooldown_mult)

        # 执行技能效果
        success = self._execute_skill(skill_type)

        if success:
            # v2.5.7 钩爪 CD 统一（技能 CD 与装备 CD 取大者，P1/P2 一致）
            if skill_type == SkillType.GRAPPLE_PULL:
                cd = self._grapple_cd_for(self.player)
            # v2.2.3 载具召唤不在释放时进入冷却：CD 从载具报废或主动退出后才开始
            if skill_type != SkillType.RIOT_GEAR and skill_type != SkillType.VEHICLE_SUMMON:
                self.player.active_skills[skill_type] = cd
            skill_name = skill.name if skill else "未知技能"
            # 记录技能使用
            if self.session:
                self.session.add_skill_use(skill_name)
            # 播放技能音效
            sk_key = skill_type.name.lower()
            self.assets.play_sound_random(SOUND_MAP.get(sk_key, ["ui_click"]))
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                f"使用 {skill_name}!", color=GOLD, lifetime=1.5
            ))
            return True
        return False

    def _use_skill_aimed(self, skill_type, angle, distance_ratio=1.0, force_self_pull=False):
        """使用带瞄准方向和距离的技能 - distance_ratio: 0.1~1.0
        force_self_pull: v2.2.12 长按瞄准未锁定时钩爪直接自我拉拽到锚点（不检查路径僵尸）"""
        if not self.player:
            return False
        if not self.player.can_act():
            return False
        # v2.7.0 无畏冲锋期间：无法使用任何技能（冲锋中只能转向）
        if getattr(self.player, 'fearless_charge_active', False):
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 50, "冲锋中无法使用技能!", color=(255, 130, 60), lifetime=1.0))
            return False
        self._sync_legendary_skill_level()  # 传说专属技能等级与武器同步

        skill = self.player.skill_tree.get_skill(skill_type)
        if not skill or skill.current_level == 0:
            # 所有技能（含手雷）0级=未解锁，需先点技能树
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                f"技能未解锁!", color=GRAY, lifetime=1.5
            ))
            return False

        if skill_type in self.player.active_skills:
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                f"冷却中...", color=GRAY, lifetime=1.0
            ))
            return False

        cooldowns = {
            SkillType.DASH: 5.0, 
            SkillType.GRENADE: 8.0,
            SkillType.TURRET: 15.0,
            SkillType.AIRSTRIKE: 20.0,
            SkillType.GRAPPLE_PULL: 2.0,
            SkillType.TIME_SLOW: 25.0, 
            SkillType.OVERLOAD: 30.0,
            SkillType.RIOT_GEAR: 30.0,
            SkillType.BLINK: 8.0,
            SkillType.BLACK_HOLE: 25.0,
            SkillType.ICE_NOVA: 20.0,
            SkillType.CHAIN_LIGHTNING: 15.0,
            SkillType.BERSERK: 20.0,
            SkillType.PHANTOM_STRIKE: 18.0,
            SkillType.MEDIC_POD: 30.0,
        }
        # v2.5.7：预瞄释放的冷却同样走统一表（原来这里缺传说级技能 → 一律 10s）
        cd = get_skill_cooldown(skill_type, self.player.cooldown_mult)
        # v2.7.0 无畏冲锋：冷却按技能等级递减
        if skill_type == SkillType.FEARLESS_CHARGE:
            cd = get_fearless_charge_cooldown(skill.current_level, self.player.cooldown_mult)

        # 根据 distance_ratio 计算实际距离
        max_dist = self._get_skill_max_distance(skill_type)
        actual_dist = max_dist * distance_ratio

        success = False
        if skill_type == SkillType.GRENADE:
            target_x = self.player.x + math.cos(angle) * actual_dist
            target_y = self.player.y + math.sin(angle) * actual_dist
            self._throw_skill_grenade(target_x, target_y)
            success = True
        elif skill_type == SkillType.AIRSTRIKE:
            target_x = self.player.x + math.cos(angle) * actual_dist
            target_y = self.player.y + math.sin(angle) * actual_dist
            self._call_airstrike_at(target_x, target_y)
            success = True
        elif skill_type == SkillType.DASH:
            self.player.facing_angle = math.degrees(angle)
            # 冲刺距离也受 distance_ratio 影响
            success = self._skill_dash_aimed(angle, actual_dist)
        elif skill_type == SkillType.GRAPPLE_PULL:
            success = self._perform_grapple_aimed(angle, actual_dist)
        elif skill_type == SkillType.SHIELD_BASH:
            success = self._perform_bash(math.degrees(angle))
        elif skill_type == SkillType.BLINK:
            # 闪烁支持方向和距离
            success = self._skill_blink_aimed(angle, actual_dist)
        elif skill_type == SkillType.BLACK_HOLE:
            target_x = self.player.x + math.cos(angle) * actual_dist
            target_y = self.player.y + math.sin(angle) * actual_dist
            success = self._skill_black_hole(target_x, target_y)
        elif skill_type == SkillType.CHAIN_LIGHTNING:
            success = self._skill_chain_lightning(angle)
        elif skill_type == SkillType.MEDIC_POD:
            target_x = self.player.x + math.cos(angle) * actual_dist
            target_y = self.player.y + math.sin(angle) * actual_dist
            success = self._skill_medic_pod(target_x, target_y)
        elif skill_type == SkillType.RAILGUN_ANNIHILATION:
            # v2.5.7 修复：湮灭射线按预瞄方向释放（原来忽略瞄准角，恒定朝 facing_angle）
            success = self._skill_railgun_annihilation(angle=angle)
        elif skill_type == SkillType.SCYTHE_DANCE:
            # v2.5.7：死亡轮回为自身周围 AoE（有预瞄圈），方向不影响效果
            success = self._skill_scythe_dance()
        else:
            success = self._execute_skill(skill_type)

        if success:
            # v2.5.7 钩爪 CD 统一（技能 CD 与装备 CD 取大者，P1/P2 一致）
            if skill_type == SkillType.GRAPPLE_PULL:
                cd = self._grapple_cd_for(self.player)
            # v2.2.3 载具召唤不在释放时进入冷却：CD 从载具报废或主动退出后才开始
            if skill_type != SkillType.RIOT_GEAR and skill_type != SkillType.VEHICLE_SUMMON:
                self.player.active_skills[skill_type] = cd
            skill_name = skill.name if skill else "未知技能"
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                f"使用 {skill_name}!", color=GOLD, lifetime=1.5
            ))
        return success

    def _skill_dash(self):
        """冲刺技能"""
        self.player.dash_timer = 0.3
        self.player.invincible_timer = 0.5
        angle_rad = math.radians(self.player.facing_angle)
        dash_dist = 150
        new_x = self.player.x + math.cos(angle_rad) * dash_dist
        new_y = self.player.y + math.sin(angle_rad) * dash_dist
        # 检查新位置是否安全
        if self.world and self.world.is_position_safe(new_x, new_y, self.player.size):
            self.player.x = new_x
            self.player.y = new_y
        else:
            # 如果目标位置不安全，尝试缩短距离
            for dist in range(150, 0, -10):
                test_x = self.player.x + math.cos(angle_rad) * dist
                test_y = self.player.y + math.sin(angle_rad) * dist
                if self.world.is_position_safe(test_x, test_y, self.player.size):
                    self.player.x = test_x
                    self.player.y = test_y
                    break
        self.player.ensure_safe_position(self.world)
        self.particles.spawn_explosion(self.player.x, self.player.y, CYAN, 20)
        self.camera.shake(8, 0.3)
        return True

    def _skill_blink(self, angle):
        """闪烁技能 - 短按固定距离"""
        blink_dist = 200
        new_x = self.player.x + math.cos(angle) * blink_dist
        new_y = self.player.y + math.sin(angle) * blink_dist
        if self.world and self.world.is_position_safe(new_x, new_y, self.player.size):
            self.player.x = new_x
            self.player.y = new_y
        else:
            for dist in range(200, 0, -10):
                test_x = self.player.x + math.cos(angle) * dist
                test_y = self.player.y + math.sin(angle) * dist
                if self.world.is_position_safe(test_x, test_y, self.player.size):
                    self.player.x = test_x
                    self.player.y = test_y
                    break
        self.player.ensure_safe_position(self.world)
        self.particles.spawn_explosion(self.player.x, self.player.y, CYAN, 15)
        self.camera.shake(5, 0.2)
        return True

    def _skill_blink_aimed(self, angle, distance):
        """闪烁技能 - 长按指定方向和距离"""
        new_x = self.player.x + math.cos(angle) * distance
        new_y = self.player.y + math.sin(angle) * distance
        if self.world and self.world.is_position_safe(new_x, new_y, self.player.size):
            self.player.x = new_x
            self.player.y = new_y
        else:
            for dist in range(int(distance), 0, -10):
                test_x = self.player.x + math.cos(angle) * dist
                test_y = self.player.y + math.sin(angle) * dist
                if self.world.is_position_safe(test_x, test_y, self.player.size):
                    self.player.x = test_x
                    self.player.y = test_y
                    break
        self.player.ensure_safe_position(self.world)
        self.particles.spawn_explosion(self.player.x, self.player.y, CYAN, 15)
        self.camera.shake(3, 0.2)
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, 
            f"闪烁!", color=CYAN, lifetime=1.0
        ))
        return True

    def _skill_dash_aimed(self, angle, distance):
        """冲刺技能 - 支持指定距离"""
        self.player.dash_timer = 0.3
        self.player.invincible_timer = 0.5
        new_x = self.player.x + math.cos(angle) * distance
        new_y = self.player.y + math.sin(angle) * distance
        if self.world and self.world.is_position_safe(new_x, new_y, self.player.size):
            self.player.x = new_x
            self.player.y = new_y
        else:
            for dist in range(int(distance), 0, -10):
                test_x = self.player.x + math.cos(angle) * dist
                test_y = self.player.y + math.sin(angle) * dist
                if self.world.is_position_safe(test_x, test_y, self.player.size):
                    self.player.x = test_x
                    self.player.y = test_y
                    break
        self.player.ensure_safe_position(self.world)
        self.particles.spawn_explosion(self.player.x, self.player.y, CYAN, 20)
        self.camera.shake(8, 0.3)
        return True

    def _skill_grenade(self):
        """手雷技能：抛物线投掷，不消耗库存"""
        angle_rad = math.radians(self.player.facing_angle)
        target_x = self.player.x + math.cos(angle_rad) * 350
        target_y = self.player.y + math.sin(angle_rad) * 350
        self._throw_skill_grenade(target_x, target_y)
        return True

    def _skill_turret(self):
        """自动炮塔技能"""
        angle_rad = math.radians(self.player.facing_angle)
        turret_x = self.player.x + math.cos(angle_rad) * 80
        turret_y = self.player.y + math.sin(angle_rad) * 80
        self.particles.spawn_explosion(turret_x, turret_y, GRAY, 20)
        self.floating_texts.append(FloatingText(
            turret_x, turret_y - 30, "炮塔部署!", color=GRAY, lifetime=2.0
        ))
        self._create_turret_effect(turret_x, turret_y)
        return True

    def _skill_airstrike(self):
        """空袭技能 - 重写为长方形区域横扫轰炸（效果强）
        Lv1: 小矩形区域密集轰炸
        Lv2+: 大矩形区域横扫轰炸
        Lv3+: +燃烧区域
        Lv4+: 双机双向横扫
        Lv5: 超级核爆中心 + 双机横扫 + 燃烧 + EMP
        """
        if self.config.control_mode == ControlMode.KEYBOARD:
            mouse_pos = pygame.mouse.get_pos()
            target_x = mouse_pos[0] / self.scale + self.camera.x
            target_y = mouse_pos[1] / self.scale + self.camera.y
            direction = math.degrees(math.atan2(target_y - self.player.y, target_x - self.player.x))
        else:
            direction = self.player.facing_angle
            angle_rad = math.radians(direction)
            target_x = self.player.x + math.cos(angle_rad) * 500
            target_y = self.player.y + math.sin(angle_rad) * 500

        if not hasattr(self, 'airstrikes'):
            self.airstrikes = []

        # 获取技能等级
        airstrike_skill = self.player.skill_tree.get_skill(SkillType.AIRSTRIKE)
        skill_level = airstrike_skill.current_level if airstrike_skill else 1

        # 累加效果列表
        effects = ["basic"]
        if skill_level >= 3:
            effects.append("fire")
        if skill_level >= 5:
            effects.append("emp")
            effects.append("nuke")

        # 长方形区域参数：随等级扩大
        length = 360 + skill_level * 70
        width = 180 + skill_level * 50
        label = "超级核爆!" if skill_level >= 5 else ("燃烧空袭!" if skill_level >= 3 else "空袭来袭!")
        label_color = (255, 200, 0) if skill_level >= 5 else (FIRE_ORANGE if skill_level >= 3 else RED)
        self.floating_texts.append(FloatingText(
            target_x, target_y - 50, label, color=label_color, lifetime=2.5
        ))
        # 主飞机沿direction横扫矩形区域
        self._create_plane_run(target_x, target_y, effects, direction=direction, length=length, width=width)
        # Lv4+: 第二架垂直方向横扫
        if skill_level >= 4:
            self._create_plane_run(target_x, target_y, effects, direction=direction + 90, length=length * 0.7, width=width * 0.8)
        # Lv5: 中心超级核爆（延迟1.5秒后引爆）
        if skill_level >= 5:
            self.airstrikes.append({
                "x": target_x, "y": target_y, "timer": 1.5, "warned": False,
                "effects": ["nuke", "fire", "emp"], "is_nuke": True
            })
        return True

    # v2.7.0：盾牌肘击技能已从技能池移除，改为防爆套装自带机制（Q / 射击键）
    def _skill_fearless_charge(self, player=None):
        """v2.7.0 无畏冲锋：进入限时冲撞状态
        未装备防爆套装时先装备（并强行重置防爆套装技能冷却CD），装备中同样重置CD。
        冲锋期间：任意伤害减伤50%、移速+50%、无法肘击与使用技能、只能缓慢改变朝向。
        """
        pl = player if player is not None else self.player
        if pl is None:
            return False
        skill = pl.skill_tree.get_skill(SkillType.FEARLESS_CHARGE)
        if not skill or skill.current_level == 0:
            self.floating_texts.append(FloatingText(
                pl.x, pl.y - 40, "未解锁无畏冲锋!", color=RED, lifetime=1.5))
            return False
        rg = getattr(pl, 'riot_gear', None)
        if rg is None:
            return False
        # 已在冲锋中：不重复触发
        if getattr(rg, 'charge_active', False):
            self.floating_texts.append(FloatingText(
                pl.x, pl.y - 50, "正在冲锋!", color=GRAY, lifetime=1.0))
            return False
        # 载具中禁止
        if getattr(pl, 'vehicle', None) is not None and getattr(pl.vehicle, 'alive', False):
            self.floating_texts.append(FloatingText(
                pl.x, pl.y - 40, "载具中无法冲锋!", color=(255, 160, 60), lifetime=1.2))
            return False
        riot_skill = pl.skill_tree.get_skill(SkillType.RIOT_GEAR)
        if not riot_skill or riot_skill.current_level == 0:
            self.floating_texts.append(FloatingText(
                pl.x, pl.y - 40, "需要先解锁防爆套装!", color=RED, lifetime=1.5))
            return False
        # 未装备 → 先装备防爆套装（无视冷却）
        if not getattr(rg, 'equipped', False):
            try:
                rg.riot_gear_cd_timer = 0.0
                rg.equip()
            except Exception:
                pass
            self.floating_texts.append(FloatingText(
                pl.x, pl.y - 62, "防爆套装·强制装备!", color=(120, 200, 255), lifetime=1.2))
        # 强行重置防爆套装技能冷却CD
        pl.riot_gear_cooldown = 0.0
        try:
            pl.active_skills.pop(SkillType.RIOT_GEAR, None)
        except Exception:
            pass
        lv = max(1, int(skill.current_level))
        dur = get_fearless_charge_duration(lv)
        # 冲锋速度 = 当前实际移动速度 ×1.5
        try:
            base_px = pl.speed * getattr(pl, 'speed_mult', 1.0) * 60.0
            base_px *= pl.buff_manager.get_speed_mult()
        except Exception:
            base_px = 270.0
        rg.charge_active = True
        rg.charge_timer = dur
        rg.charge_duration = dur
        rg.charge_direction = pl.facing_angle
        rg.charge_speed = base_px * FEARLESS_CHARGE_SPEED_MULT
        rg.charge_hit_ids = set()
        rg.fearless_active = True
        rg.fearless_level = lv
        pl.fearless_charge_active = True
        pl.fearless_charge_level = lv
        self.floating_texts.append(FloatingText(
            pl.x, pl.y - 50, "无畏冲锋!", color=(255, 130, 60), lifetime=1.5))
        self.particles.spawn_explosion(pl.x, pl.y, (255, 130, 60), 26)
        self.camera.shake(7, 0.25)
        try:
            self.assets.play_sound("bash")
        except Exception:
            pass
        return True

    def _skill_grapple(self):
        """钩爪技能（独立技能，无需防爆套装）
        v2.2.5：持有死神镰刀时切换为『死神钩爪』——CD 3s，长按显示锁定圈：
        松开后圈内锁定僵尸→无视沿途直飞锁定目标；未锁定→自我拉拽+沿途旋转镰刀伤害+全程免伤"""
        self._perform_grapple()
        return True

    def _is_wielding_scythe(self, player=None):
        """判断玩家当前武器是否为死神镰刀（切换钩爪索引为死神钩爪）

        v2.7.2：支持传入任意玩家；不传则默认 P1（兼容旧调用）。
        """
        try:
            _pl = player if player is not None else self.player
            _w = _pl.get_current_weapon()
            if _w is None:
                return False
            _wt = getattr(_w, "weapon_type", None)
            return _wt is not None and getattr(_wt, "name", "") == "SCYTHE"
        except Exception:
            return False

    def _skill_time_slow(self):
        """时间减缓技能"""
        if not hasattr(self, 'time_slow_active'):
            self.time_slow_active = False
            self.time_slow_timer = 0
        self.time_slow_active = True
        self.time_slow_timer = 5.0
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, 
            "时间减缓!", color=PURPLE, lifetime=2.0
        ))
        return True

    def _skill_overload(self):
        """超载模式技能（v2.1.8：特效加强——金色电弧+双光环+闪光+强震屏）"""
        _sk = self.player.skill_tree.get_skill(SkillType.OVERLOAD) if self.player.skill_tree else None
        lv = _sk.current_level if _sk is not None else 1
        self.player.damage_boost_timer = 8.0
        self.player.damage_boost_mult = 2.5
        self.particles.spawn_explosion(self.player.x, self.player.y, RED, 40)
        self.camera.shake(12, 0.5)
        # v2.1.8 加强：金色电弧粒子 + 双扩散光环 + 全屏浮字 + 音效
        try:
            _cnt = 16 + lv * 2
            for i in range(_cnt):
                ang = math.pi * 2 * i / _cnt + random.uniform(-0.4, 0.4)
                rr = random.uniform(20, 60)
                self.particles.spawn_particle(
                    self.player.x + math.cos(ang) * rr,
                    self.player.y + math.sin(ang) * rr,
                    math.cos(ang) * random.uniform(60, 140),
                    math.sin(ang) * random.uniform(60, 140),
                    (255, 200, 60) if i % 3 else (255, 240, 150), 0.6, 4)
            if hasattr(self, 'sweep_rings'):
                for _clr, _mr in (((255, 220, 80), 260), ((255, 160, 40), 180)):
                    self.sweep_rings.append({
                        "x": self.player.x, "y": self.player.y,
                        "r": 30, "max_r": _mr, "color": _clr,
                        "width": 7, "life": 0.55, "max_life": 0.55,
                    })
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 60, "超载爆发!", color=(255, 220, 80), lifetime=1.4))
            self.assets.play_sound_random(["boss_death", "explosion"])
        except Exception:
            pass
        return True

    def _skill_ice_nova(self):
        """冰霜新星 - 伤害/半径随技能等级缩放"""
        ice_skill = self.player.skill_tree.get_skill(SkillType.ICE_NOVA) if self.player else None
        if ice_skill and ice_skill.current_level > 0:
            nova_radius = int(ice_skill.get_effective_radius())
            nova_damage = int(ice_skill.get_effective_damage())
            is_max = ice_skill.is_maxed()
        else:
            nova_radius = 200
            nova_damage = 40
            is_max = False
        freeze_dur = 4.0 if is_max else 2.0
        for enemy in self.enemies:
            dist = math.hypot(enemy.x - self.player.x, enemy.y - self.player.y)
            if dist < nova_radius:
                enemy.frozen_timer = freeze_dur
                if nova_damage > 0:
                    enemy.take_damage(nova_damage)
                    self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, nova_damage, color=CYAN))
        self.particles.spawn_explosion(self.player.x, self.player.y, BLUE, 60)
        self.camera.shake(8, 0.3)
        label = "绝对零度!" if is_max else "冰霜新星!"
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, label, color=BLUE, lifetime=1.5
        ))
        return True

    def _skill_black_hole(self, x, y):
        """黑洞技能 - 半径随技能等级缩放"""
        bh_skill = self.player.skill_tree.get_skill(SkillType.BLACK_HOLE) if self.player else None
        if bh_skill and bh_skill.current_level > 0:
            bh_radius = int(bh_skill.get_effective_radius())
            bh_damage = int(bh_skill.get_effective_damage())
            is_max = bh_skill.is_maxed()
        else:
            bh_radius = 150
            bh_damage = 30
            is_max = False
        if not hasattr(self, 'black_holes'):
            self.black_holes = []
        self.black_holes.append({"x": x, "y": y, "timer": 10.0 if is_max else 5.0, "radius": bh_radius, "damage": bh_damage})
        label = "奇点生成!" if is_max else "黑洞生成!"
        self.floating_texts.append(FloatingText(
            x, y - 30, label, color=PURPLE, lifetime=1.5
        ))
        return True

    def _skill_chain_lightning(self, angle):
        """连锁闪电 - 伤害/范围随技能等级缩放，满级雷神之怒"""
        cl_skill = self.player.skill_tree.get_skill(SkillType.CHAIN_LIGHTNING) if self.player else None
        if cl_skill and cl_skill.current_level > 0:
            cl_damage = int(cl_skill.get_effective_damage())
            cl_range = int(cl_skill.get_effective_radius())
            is_max = cl_skill.is_maxed()
        else:
            cl_damage = 50
            cl_range = 200
            is_max = False
        start_x = self.player.x
        start_y = self.player.y
        initial_range = cl_range + 150  # 初始搜索范围略大
        target_x = start_x + math.cos(angle) * initial_range
        target_y = start_y + math.sin(angle) * initial_range

        # 寻找最近的敌人作为起点
        closest = None
        closest_dist = initial_range
        for enemy in self.enemies:
            dist = math.hypot(enemy.x - target_x, enemy.y - target_y)
            if dist < closest_dist:
                closest_dist = dist
                closest = enemy

        if closest:
            # 连锁伤害
            hit_enemies = [closest]
            current_target = closest
            max_chains = 7 if is_max else 4  # 满级更多连锁
            for _ in range(max_chains):
                next_target = None
                next_dist = cl_range
                for enemy in self.enemies:
                    if enemy not in hit_enemies:
                        dist = math.hypot(enemy.x - current_target.x, enemy.y - current_target.y)
                        if dist < next_dist:
                            next_dist = dist
                            next_target = enemy
                if next_target:
                    hit_enemies.append(next_target)
                    current_target = next_target
                else:
                    break

            # 造成伤害
            for i, enemy in enumerate(hit_enemies):
                damage = cl_damage * (0.7 ** i)  # 递减伤害
                enemy.take_damage(damage)
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, damage, color=YELLOW, is_crit=is_max))
                self.particles.spawn(enemy.x, enemy.y, YELLOW, 8)
                if not enemy.alive:
                    self._on_enemy_death(enemy)

            self.particles.spawn_explosion(self.player.x, self.player.y, YELLOW, 20)
            self.camera.shake(6, 0.25)
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, f"连锁闪电! x{len(hit_enemies)}", color=YELLOW, lifetime=1.5
            ))
            return True
        return False

    def _skill_berserk(self):
        """狂暴技能（v2.1.8：特效加强——火焰环绕+红色光环+音效）"""
        _sk = self.player.skill_tree.get_skill(SkillType.BERSERK) if self.player.skill_tree else None
        lv = _sk.current_level if _sk is not None else 1
        self.player.berserk_active = True
        self.player.damage_boost_timer = 10.0
        self.player.damage_boost_mult = 2.0
        self.player.fire_rate_mult *= 2.0
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, "狂暴!", color=RED, lifetime=2.0
        ))
        self.particles.spawn_explosion(self.player.x, self.player.y, RED, 35)
        self.camera.shake(10, 0.4)
        # v2.1.8 加强：火焰环绕粒子（玩家四周一圈）+ 扩散红色光环 + 音效
        try:
            _cnt = 14 + lv * 3
            for i in range(_cnt):
                ang = math.pi * 2 * i / _cnt + random.uniform(-0.3, 0.3)
                rr = 30.0
                self.particles.spawn_particle(
                    self.player.x + math.cos(ang) * rr,
                    self.player.y + math.sin(ang) * rr,
                    math.cos(ang) * random.uniform(40, 90),
                    math.sin(ang) * random.uniform(40, 90),
                    (255, 60, 40) if i % 2 else (255, 140, 40), 0.5, 4)
            if hasattr(self, 'sweep_rings'):
                self.sweep_rings.append({
                    "x": self.player.x, "y": self.player.y,
                    "r": 40, "max_r": 220, "color": (255, 60, 40),
                    "width": 8, "life": 0.6, "max_life": 0.6,
                })
            self.assets.play_sound_random(["boss_death", "zombie_leap"])
        except Exception:
            pass
        return True

    def _skill_phantom_strike(self):
        """幻影打击"""
        angle_rad = math.radians(self.player.facing_angle)
        for offset in [0, 120, 240]:
            rad = math.radians(self.player.facing_angle + offset)
            fx = self.player.x + math.cos(rad) * 100
            fy = self.player.y + math.sin(rad) * 100
            # 幻影造成伤害
            for enemy in self.enemies:
                dist = math.hypot(enemy.x - fx, enemy.y - fy)
                if dist < 40:
                    enemy.take_damage(60)
                    self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, 60, color=LIME))
                    if not enemy.alive:
                        self._on_enemy_death(enemy)
            self.particles.spawn_explosion(fx, fy, LIME, 25)
            # 幻影突袭刀光（三个方向的绿色弧斩）
            self.slash_arcs.append(SlashArc(
                fx, fy, rad, 90, LIME, lifetime=0.4, kind="scythe",
                start_radius=20, end_angle_offset=1.3))
            self.camera.shake(5, 0.2)
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, "幻影打击!", color=LIME, lifetime=1.5
        ))
        return True

    def _skill_medic_pod(self, x, y):
        """医疗舱 - 半径随技能等级缩放，满级清除debuff"""
        mp_skill = self.player.skill_tree.get_skill(SkillType.MEDIC_POD) if self.player else None
        if mp_skill and mp_skill.current_level > 0:
            mp_radius = int(mp_skill.get_effective_radius())
            is_max = mp_skill.is_maxed()
        else:
            mp_radius = 100
            is_max = False
        if not hasattr(self, 'medic_pods'):
            self.medic_pods = []
        self.medic_pods.append({"x": x, "y": y, "timer": 8.0, "heal_timer": 0, "radius": mp_radius, "purify": is_max})
        label = "生命之泉!" if is_max else "医疗舱部署!"
        self.floating_texts.append(FloatingText(
            x, y - 30, label, color=GREEN, lifetime=1.5
        ))
        return True

    # v2.7.0：冲击波技能已从技能池移除，由无畏冲锋取代

    def _skill_war_cry(self):
        """战吼：获得伤害+攻速+护盾三重buff"""
        skill = self.player.skill_tree.get_skill(SkillType.WAR_CRY)
        level = skill.current_level if skill else 1
        durations = {1: 5.0, 2: 7.0, 3: 10.0}
        damage_mults = {1: 1.5, 2: 1.8, 3: 2.2}
        attack_mults = {1: 1.3, 2: 1.5, 3: 1.8}
        dur = durations.get(level, 5.0)
        self.player.buff_manager.add_buff(BuffType.DAMAGE_BOOST, duration=dur)
        self.player.buff_manager.add_buff(BuffType.HASTE, duration=dur)
        self.player.buff_manager.add_buff(BuffType.SHIELD, duration=dur)
        db = self.player.buff_manager.get_buff(BuffType.DAMAGE_BOOST)
        if db:
            db.value = damage_mults.get(level, 1.5)
        hb = self.player.buff_manager.get_buff(BuffType.HASTE)
        if hb:
            hb.value = attack_mults.get(level, 1.3)
        self.floating_texts.append(FloatingText(self.player.x, self.player.y - 50, "战吼！", color=GOLD, lifetime=2.0))
        self.particles.spawn_explosion(self.player.x, self.player.y, GOLD, 20)
        self.camera.shake(3, 0.2)
        self.assets.play_sound("weapon_switch")
        self.war_cry_timer = dur
        return True

    def _skill_purify(self):
        """净化：清除所有debuff并获得短暂无敌"""
        skill = self.player.skill_tree.get_skill(SkillType.PURIFY)
        level = skill.current_level if skill else 1
        self.player.buff_manager.clear_debuffs()
        inv_durations = {1: 2.0, 2: 3.0, 3: 5.0}
        self.player.buff_manager.add_buff(BuffType.INVINCIBLE, duration=inv_durations.get(level, 2.0))
        if level >= 2:
            heal_amount = self.player.max_hp * (0.3 if level == 2 else 1.0)
            self.player.heal(heal_amount)
        self.floating_texts.append(FloatingText(self.player.x, self.player.y - 50, "净化！", color=WHITE, lifetime=2.0))
        self.particles.spawn(self.player.x, self.player.y, WHITE, 30, (2, 6), (-4, 4), (0.3, 0.8))
        self.particles.spawn(self.player.x, self.player.y, (200, 220, 255), 20)
        self.assets.play_sound("pickup_item")
        return True

    # ========== 传说级武器专属技能 ==========
    def _legendary_skill_level(self, skill_type, player=None):
        """读取传说专属技能当前等级（与武器等级同步，施放前先同步一次）"""
        try:
            pl = player if player is not None else self.player
            self._sync_legendary_skill_level(pl)
            sk = pl.skill_tree.get_skill(skill_type)
            if sk:
                return max(1, min(sk.max_level, sk.current_level))
        except Exception:
            pass
        return 1

    def _skill_scythe_dance(self):
        """死神镰刀专属·死亡轮回：360°满月斩风暴，多段收割周围所有敌人"""
        lv = self._legendary_skill_level(SkillType.SCYTHE_DANCE)
        seg = {1: 3, 2: 4, 3: 5, 4: 6, 5: 8}[lv]
        radius = {1: 300, 2: 320, 3: 340, 4: 360, 5: 400}[lv]
        dmg = 60 * seg
        dmg *= (self.player.damage_multiplier *
                self.player.buff_manager.get_damage_mult() *
                getattr(self.player, 'damage_mult', 1.0))
        # 对范围内所有敌人造成多段收割伤害
        for e in list(self.enemies):
            if not getattr(e, 'alive', True):
                continue
            if math.hypot(e.x - self.player.x, e.y - self.player.y) <= radius:
                e.take_damage(dmg, damage_type="aoe")
        # 特效：满月紫刃 × seg 道 + 双层扩散环 + 屏幕震动
        for i in range(seg):
            ang = (math.pi * 2 / seg) * i + random.uniform(-0.12, 0.12)
            self.slash_arcs.append(SlashArc(
                self.player.x, self.player.y, ang, radius * 0.85,
                (190, 80, 230), lifetime=0.6, kind="scythe",
                start_radius=radius * 0.5, end_angle_offset=3.0))
        for rr, tt in ((radius, 0.55), (radius * 0.65, 0.7)):
            self.sweep_rings.append({
                "x": self.player.x, "y": self.player.y,
                "r": rr * 0.3, "max_r": rr, "color": (190, 80, 230),
                "width": max(5, int(rr * 0.05)), "life": tt, "max_life": tt,
            })
        self.camera.shake(14, 0.5)
        self.particles.spawn(self.player.x, self.player.y, (200, 110, 245), 40, (2, 7), (-6, 6), (0.3, 0.9))
        self.assets.play_sound_random(["melee_swing", "scythe_sweep", "shoot_pistol"])
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 55, "死亡轮回！", color=(210, 130, 250), lifetime=1.6))
        return True

    def _skill_minigun_overdrive(self):
        """加特林专属·过热倾泻：射速暴增 + 弹药无限"""
        lv = self._legendary_skill_level(SkillType.MINIGUN_OVERDRIVE)
        dur = {1: 3.0, 2: 4.0, 3: 5.0, 4: 6.0, 5: 8.0}[lv]
        mult = {1: 2.5, 2: 3.0, 3: 3.5, 4: 4.0, 5: 4.5}[lv]
        self.player.overdrive_timer = dur
        self.player.overdrive_mult = mult
        self.player.overdrive_burn = (lv >= 4)
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 55, f"过热倾泻 ×{mult:.1f}！", color=(255, 160, 60), lifetime=1.6))
        self.particles.spawn(self.player.x, self.player.y, (255, 170, 60), 30, (2, 6), (-5, 5), (0.2, 0.7))
        self.assets.play_sound("minigun")
        return True

    def _skill_railgun_annihilation(self, angle=None):
        """轨道炮专属·湮灭射线：超粗贯穿激光 + 命中爆炸
        v2.5.7：支持传入瞄准角（长按预瞄时按预瞄方向释放，而不是固定朝向前方）"""
        lv = self._legendary_skill_level(SkillType.RAILGUN_ANNIHILATION)
        width = {1: 40, 2: 40, 3: 55, 4: 70, 5: 85}[lv]
        dmg = 300
        dmg *= (self.player.damage_multiplier *
                self.player.buff_manager.get_damage_mult() *
                getattr(self.player, 'damage_mult', 1.0))
        if angle is None:
            angle = math.radians(self.player.facing_angle)
        proj = Projectile(
            self.player.x, self.player.y,
            math.cos(angle) * 3, math.sin(angle) * 3,
            dmg, 1200, (140, 200, 245), 15, pierce=99,
            explosive=True, explosion_radius=90 + 30 * (lv >= 3),
            is_laser=True, laser_width=width, laser_duration=0.85)
        self.projectiles.append(proj)
        self.camera.shake(20, 0.7)
        self.particles.spawn(self.player.x, self.player.y, (160, 210, 255), 30, (2, 8), (-8, 8), (0.3, 1.0))
        self.assets.play_sound_random(["railgun", "shoot_pistol"])
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 55, "湮灭射线！", color=(170, 220, 255), lifetime=1.6))
        return True

    def _toggle_riot_gear(self):
        """切换防爆套装（带动画保护）"""
        self._toggle_riot_gear_skill()

    def _toggle_riot_gear_skill(self):
        """切换防爆套装（技能模式）"""
        if self.riot_anim_state != "idle":
            return False

        riot_skill = self.player.skill_tree.get_skill(SkillType.RIOT_GEAR)
        if not riot_skill or riot_skill.current_level == 0:
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                "未解锁防爆套装!", color=RED, lifetime=1.5
            ))
            return False

        if self.player.riot_gear.equipped:
            self.riot_anim_state = "unequipping"
            self.riot_anim_timer = self.riot_anim_duration
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                "卸下防爆套装...", color=ORANGE, lifetime=1.0
            ))
            return True
        else:
            # v2.2.3 载具期间禁止装备防爆套装（触控入口同样拦截）
            if getattr(self.player, 'vehicle', None) is not None and getattr(self.player.vehicle, 'alive', False):
                self.floating_texts.append(FloatingText(
                    self.player.x, self.player.y - 40,
                    "载具内无法装备防爆套装!", color=(255, 160, 60), lifetime=1.2))
                return False
            if self.player.riot_gear_cooldown <= 0:
                self.riot_anim_state = "equipping"
                self.riot_anim_timer = self.riot_anim_duration
                self.floating_texts.append(FloatingText(
                    self.player.x, self.player.y - 40, 
                    "装备防爆套装...", color=BLUE, lifetime=1.0
                ))
                return True
            else:
                self.floating_texts.append(FloatingText(
                    self.player.x, self.player.y - 40, 
                    f"冷却中 {int(self.player.riot_gear_cooldown)}s", color=GRAY, lifetime=1.0
                ))
                return False

    def _perform_bash(self, direction_angle=None, player=None):
        """盾牌肘击（v2.2.0 原地肘击：一次性范围伤害+击退+眩晕，不位移）
        v2.2.7：player 参数化，P2 可复用"""
        if player is None:
            player = self.player
        # v2.7.0 无畏冲锋期间：无法肘击
        if getattr(player, 'fearless_charge_active', False):
            self.floating_texts.append(FloatingText(
                player.x, player.y - 50, "冲锋中无法肘击!", color=(255, 130, 60), lifetime=1.0))
            return False
        if self.session:
            self.session.add_bash()
        self.assets.play_sound("bash")
        rg = player.riot_gear
        success = rg.bash(direction_angle)
        if success:
            # 体力回流共享池
            player.stamina = rg.stamina
            # v2.2.3 肘击：盾牌前方扇形区域（±75°，半径约70）一次性结算
            hit_any = False
            bash_r = 70
            bash_angle = direction_angle if direction_angle is not None else player.facing_angle
            half_arc = 75.0
            for enemy in self.enemies:
                dist = math.hypot(enemy.x - player.x, enemy.y - player.y)
                if dist > bash_r + enemy.size:
                    continue
                # 前方扇形判定
                if dist > 1:
                    ang_to = math.degrees(math.atan2(enemy.y - player.y, enemy.x - player.x))
                    diff = abs((ang_to - bash_angle + 180) % 360 - 180)
                    if diff > half_arc:
                        continue
                is_crit = random.random() < player.crit_chance
                actual_damage = rg.charge_damage * 1.6 * player.damage_mult * player.buff_manager.get_damage_mult() * (player.crit_damage if is_crit else 1)
                enemy.take_damage(actual_damage)
                self._vampire_heal(actual_damage)
                _is_boss = getattr(enemy, "is_boss", False)
                enemy.apply_buff(BuffType.STUN, duration=rg.charge_stun_duration * (0.5 if _is_boss else 1.0))
                enemy.knockdown(1.0 if not _is_boss else 0.5)
                if dist > 0:
                    _kb = rg.charge_knockback * (0.4 if _is_boss else 1.2)
                    enemy.x += (enemy.x - player.x) / dist * _kb
                    enemy.y += (enemy.y - player.y) / dist * _kb
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, actual_damage, is_crit=is_crit, damage_type="melee"))
                self.particles.spawn_blood(enemy.x, enemy.y, 12)
                hit_any = True
                if not enemy.alive:
                    self._on_enemy_death(enemy)
            self.floating_texts.append(FloatingText(
                player.x, player.y - 40, "盾牌肘击!", color=CYAN, lifetime=1.0
            ))
            self.particles.spawn_explosion(player.x, player.y, CYAN, 22)
            self.camera.shake(6 if hit_any else 3, 0.25)
            # 前方扇形冲击波
            if hasattr(self, 'sweep_rings'):
                self.sweep_rings.append({
                    "x": player.x + math.cos(math.radians(bash_angle)) * 30,
                    "y": player.y + math.sin(math.radians(bash_angle)) * 30,
                    "r": 20, "max_r": bash_r + 30, "color": (80, 220, 255),
                    "width": 6, "life": 0.35, "max_life": 0.35,
                })

    def _update_charge(self, dt, player=None):
        """更新盾牌冲撞 / v2.7.0 无畏冲锋：移动玩家，检测沿途敌人与敌对玩家碰撞"""
        pl = player if player is not None else self.player
        rg = getattr(pl, 'riot_gear', None)
        if rg is None or not getattr(rg, 'charge_active', False):
            return
        fearless = bool(getattr(rg, 'fearless_active', False))
        lv = max(1, int(getattr(rg, 'fearless_level', 0) or 1))
        rg.charge_timer -= dt
        # 无畏冲锋：方向实时跟随玩家朝向（朝向已在 Player.update 中被限速转向）
        if fearless:
            rg.charge_direction = pl.facing_angle
        angle_rad = math.radians(rg.charge_direction)
        move_x = math.cos(angle_rad) * rg.charge_speed * dt
        move_y = math.sin(angle_rad) * rg.charge_speed * dt
        # 尝试移动（受世界边界限制）
        new_x = pl.x + move_x
        new_y = pl.y + move_y
        try:
            clamped_x, clamped_y = self.world.clamp_position(new_x, new_y, pl.size)
        except Exception:
            clamped_x, clamped_y = new_x, new_y
        # 如果被墙挡住，提前结束冲撞
        if abs(clamped_x - new_x) > 1 or abs(clamped_y - new_y) > 1:
            rg.charge_timer = min(rg.charge_timer, 0.0)
        pl.x, pl.y = clamped_x, clamped_y
        # 检测沿途敌人碰撞
        hit_any = False
        for enemy in list(self.enemies):
            if not getattr(enemy, 'alive', True):
                continue
            if id(enemy) in rg.charge_hit_ids:
                continue
            dist = math.hypot(enemy.x - pl.x, enemy.y - pl.y)
            hit_radius = pl.size + getattr(enemy, 'size', 12) + (16 if fearless else 10)
            if dist >= hit_radius:
                continue
            rg.charge_hit_ids.add(id(enemy))
            _is_boss = getattr(enemy, "is_boss", False)
            if fearless and not _is_boss:
                # 无畏冲锋：沿途普通僵尸直接秒杀（Boss 受常规伤害）
                _kill = max(99999, int(getattr(enemy, 'max_hp', 100) * 100))
                enemy.take_damage(_kill, damage_type="melee")
                enemy._last_hit_player = pl
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, int(getattr(enemy, 'max_hp', 100)),
                                                        color=(255, 130, 60), damage_type="melee"))
                self.particles.spawn_blood(enemy.x, enemy.y, 16)
                self.particles.spawn_explosion(enemy.x, enemy.y, (255, 130, 60), 14)
                if dist > 0:
                    _kb = rg.charge_knockback * 1.4
                    enemy.x += (enemy.x - pl.x) / dist * _kb
                    enemy.y += (enemy.y - pl.y) / dist * _kb
                hit_any = True
                if not enemy.alive:
                    self._on_enemy_death(enemy)
                continue
            is_crit = random.random() < pl.crit_chance
            _mult = (1.0 + 0.2 * (lv - 1)) if fearless else 1.0
            actual_damage = rg.charge_damage * _mult * pl.damage_mult * pl.buff_manager.get_damage_mult() * (pl.crit_damage if is_crit else 1)
            enemy.take_damage(actual_damage)
            enemy._last_hit_player = pl
            self._vampire_heal(actual_damage)
            # 强控制：眩晕（对 boss 控制效果减半）
            enemy.apply_buff(BuffType.STUN, duration=rg.charge_stun_duration * (0.5 if _is_boss else 1.0))
            enemy.knockdown(1.0 if not _is_boss else 0.5)
            # 击退（对 boss 大幅减弱）
            if dist > 0:
                _kb = rg.charge_knockback * (0.3 if _is_boss else 1.0)
                enemy.x += math.cos(angle_rad) * _kb
                enemy.y += math.sin(angle_rad) * _kb
            self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, actual_damage, is_crit=is_crit, damage_type="melee"))
            self.particles.spawn_blood(enemy.x, enemy.y, 12)
            self.particles.spawn_explosion(enemy.x, enemy.y, CYAN, 15)
            hit_any = True
            if not enemy.alive:
                self._on_enemy_death(enemy)
        # v2.7.0 无畏冲锋：撞到敌对阵营玩家 → 强眩晕 + 直接扣除 50% 最大生命
        if fearless and getattr(self.config, 'pvp_enabled', False):
            for _pp in self._all_players():
                if _pp is pl or not getattr(_pp, 'alive', True) or getattr(_pp, 'downed', False):
                    continue
                if getattr(_pp, 'team_id', 1) == getattr(pl, 'team_id', 0):
                    continue
                _key = ("pl", id(_pp))
                if _key in rg.charge_hit_ids:
                    continue
                _d = math.hypot(_pp.x - pl.x, _pp.y - pl.y)
                if _d > pl.size + getattr(_pp, 'size', 16) + 18:
                    continue
                rg.charge_hit_ids.add(_key)
                _drain = max(1.0, getattr(_pp, 'max_hp', 100.0) * FEARLESS_PLAYER_HP_DRAIN)
                try:
                    _pp.buff_manager.add_buff(BuffType.STUN, duration=FEARLESS_PLAYER_STUN)
                except Exception:
                    pass
                _pp.hp = max(0, getattr(_pp, 'hp', 0) - _drain)
                self.damage_numbers.append(DamageNumber(_pp.x, _pp.y, int(_drain), color=RED, damage_type="melee"))
                self.particles.spawn_blood(_pp.x, _pp.y, 14)
                self.camera.shake(10, 0.3)
                self.floating_texts.append(FloatingText(
                    _pp.x, _pp.y - 45, "撞飞!", color=(255, 130, 60), lifetime=1.2))
                if getattr(_pp, 'hp', 1) <= 0:
                    # 交由既有救援/倒地系统接管（同屏双人会自动判定倒地）
                    _pp.alive = False
                hit_any = True
        if hit_any:
            self.camera.shake(8, 0.3)
        # 冲撞拖尾粒子
        _trail = (255, 130, 60) if fearless else CYAN
        self.particles.spawn(pl.x, pl.y, _trail, 2, (4, 10), (-3, 3), (0.15, 0.35))
        # 冲撞结束
        if rg.charge_timer <= 0:
            rg.charge_active = False
            rg.charge_hit_ids = set()
            _was_fearless = fearless
            rg.fearless_active = False
            pl.fearless_charge_active = False
            pl.fearless_charge_level = 0
            # 结束冲击波
            self.particles.spawn_explosion(pl.x, pl.y, _trail, 20)
            self.camera.shake(6, 0.25)
            if _was_fearless:
                # 3级起：结束时爆裂冲击波，击退周围敌人
                if lv >= 3:
                    try:
                        self.slash_arcs.append(SlashArc(
                            pl.x, pl.y, 0.0, 150 + 20 * lv, (255, 150, 60),
                            lifetime=0.45, kind="scythe", start_radius=40, end_angle_offset=6.2))
                    except Exception:
                        pass
                    for _e in list(self.enemies):
                        if not getattr(_e, 'alive', True):
                            continue
                        _d = math.hypot(_e.x - pl.x, _e.y - pl.y)
                        if _d < 150 + 20 * lv and _d > 0:
                            _kb = 130 * (0.3 if getattr(_e, 'is_boss', False) else 1.0)
                            _e.x += (_e.x - pl.x) / _d * _kb
                            _e.y += (_e.y - pl.y) / _d * _kb
                            _e.apply_buff(BuffType.STUN, duration=0.6)
                # 5级：冲锋结束后 1 秒无敌
                if lv >= 5:
                    pl.invincible_timer = max(getattr(pl, 'invincible_timer', 0.0), 1.0)
                    self.floating_texts.append(FloatingText(
                        pl.x, pl.y - 60, "绝境突进!", color=GOLD, lifetime=1.4))

    def _perform_grapple_aimed(self, angle, max_dist=800):
        """带瞄准方向和距离的钩爪（独立技能，无需防爆套装）"""
        target_x = self.player.x + math.cos(angle) * max_dist
        target_y = self.player.y + math.sin(angle) * max_dist
        return self._perform_grapple_at(target_x, target_y)

    def _perform_grapple(self):
        """键盘模式钩爪 - 短按直接沿当前方向发射"""
        max_grapple_range = 800
        angle_rad = math.radians(self.player.facing_angle)
        target_x = self.player.x + math.cos(angle_rad) * max_grapple_range
        target_y = self.player.y + math.sin(angle_rad) * max_grapple_range
        return self._perform_grapple_at(target_x, target_y)

    def _perform_grapple_at(self, target_x, target_y, player=None, force_self_pull=False):
        """在指定位置执行钩爪核心逻辑 - 新逻辑（独立技能）

        v2.7.2 重构：**唯一**的钩爪核心实现，P1..Pn 共用。
          player=None → 作用于 self.player（旧调用全部兼容）
          player=p2    → 作用于 P2，行为与 P1 逐条一致
        force_self_pull=True → 强制自我拉拽到锚点（不做路径勾取）
        """
        _p = player if player is not None else self.player
        # v2.5.0 锚点钳制到地图界内（修复钩爪锚点出界）
        # v2.7.2 修复方向歪斜：旧写法对 x/y 各自独立 clamp，当玩家位于边界外侧时
        #   （例如被击退到地图边缘）会把某个轴硬抬到 lo，导致锚点方向相对玩家偏转，
        #   表现为"朝敌人发射却勾到旁边的空气"。
        #   改为：仅在锚点越界时**沿原方向按比例缩短**到边界交点，方向恒定不变。
        try:
            _b = getattr(getattr(self, 'world', None), 'bounds', None)
            if _b:
                _lo, _hi = float(_b[0]), float(_b[1])
                _dx0 = target_x - _p.x
                _dy0 = target_y - _p.y
                _scale = 1.0
                if _dx0 > 0 and target_x > _hi:
                    _scale = min(_scale, (_hi - _p.x) / _dx0)
                elif _dx0 < 0 and target_x < _lo:
                    _scale = min(_scale, (_lo - _p.x) / _dx0)
                if _dy0 > 0 and target_y > _hi:
                    _scale = min(_scale, (_hi - _p.y) / _dy0)
                elif _dy0 < 0 and target_y < _lo:
                    _scale = min(_scale, (_lo - _p.y) / _dy0)
                _scale = max(0.0, min(1.0, _scale))
                target_x = _p.x + _dx0 * _scale
                target_y = _p.y + _dy0 * _scale
        except Exception:
            pass
        # v2.2.7 载具中禁用钩爪
        _v = getattr(_p, 'vehicle', None)
        if _v is not None and getattr(_v, 'alive', False):
            self.floating_texts.append(FloatingText(
                _p.x, _p.y - 40, "载具中无法使用钩爪", color=GRAY, lifetime=1.2))
            return False
        # 寻找钩爪路径上的目标
        dx = target_x - _p.x
        dy = target_y - _p.y
        dist = math.hypot(dx, dy)
        if dist > _p.riot_gear.grapple_max_range:
            ratio = _p.riot_gear.grapple_max_range / dist
            dx *= ratio
            dy *= ratio
            target_x = _p.x + dx
            target_y = _p.y + dy
            dist = _p.riot_gear.grapple_max_range

        dir_x = dx / dist if dist > 0 else 1
        dir_y = dy / dist if dist > 0 else 0

        # v2.7.1：目标解算统一走通用实现（倒地队友 > 异阵营玩家 > 同阵营玩家 > 僵尸）
        # P1/P2、键控/触控、单人/多人共用同一份逻辑，避免两套实现行为分叉。
        target = None
        target_dist = dist
        search_radius = 30  # 搜索半径
        try:
            _t = self.resolve_grapple_target(_p, dir_x, dir_y, dist, search_radius)
            if _t is not None:
                target = _t
                _ex = _t.x - _p.x
                _ey = _t.y - _p.y
                target_dist = _ex * dir_x + _ey * dir_y
        except Exception:
            target = None
        # 搜索经验球
        for orb in self.exp_orbs:
            if not orb.alive:
                continue
            ex = orb.x - _p.x
            ey = orb.y - _p.y
            proj = ex * dir_x + ey * dir_y
            if proj < 0 or proj > dist:
                continue
            perp_x = ex - proj * dir_x
            perp_y = ey - proj * dir_y
            perp_dist = math.hypot(perp_x, perp_y)
            if perp_dist < search_radius + orb.size and proj < target_dist:
                # 经验球直接拉取
                target_dist = proj
                # 经验球没有 grappled 属性，直接设置为目标位置
                pass

        # 搜索道具
        for item in self.world.items:
            if not item.alive:
                continue
            ex = item.x - _p.x
            ey = item.y - _p.y
            proj = ex * dir_x + ey * dir_y
            if proj < 0 or proj > dist:
                continue
            perp_x = ex - proj * dir_x
            perp_y = ey - proj * dir_y
            perp_dist = math.hypot(perp_x, perp_y)
            if perp_dist < search_radius + item.size and proj < target_dist:
                target_dist = proj

        # v2.2.5/12 钩爪发射决策：
        # 1) 瞄准圈锁定的僵尸/道具 → 无视沿途可勾取物，直飞锁定目标（沿途可造成伤害）
        # 2) 长按瞄准但未锁定（force_self_pull）→ 直接自我拉拽到锚点，不检查路径上是否有僵尸
        # 3) 短按直发：路径上检测到敌人 → 勾取拉回
        # 4) 其余 → 自我拉拽（把自己拉向目标点；死神钩爪沿途旋转镰刀伤害）
        scythe = self._is_wielding_scythe(_p)
        rg = _p.riot_gear
        locked = getattr(rg, "grapple_locked_target", None)
        if locked is not None and getattr(locked, "alive", False) and not getattr(locked, "is_boss", False):
            success = rg.use_grapple(locked.x, locked.y, _p.x, _p.y, locked, scythe=scythe)
            _locked_name = "锁定直飞"
        elif force_self_pull or getattr(rg, 'grapple_direct_pull', False):
            # v2.4.0 修复：force_self_pull 残留未定义引用 → 改用钩爪直拉标志
            success = rg.use_grapple(target_x, target_y, _p.x, _p.y, None, scythe=scythe,
                                     direct_pull=True)
            _locked_name = "拉拽自身"
        elif target:
            success = rg.use_grapple(target.x, target.y, _p.x, _p.y, target, scythe=scythe)
            _locked_name = "勾取拉回"
        else:
            success = rg.use_grapple(target_x, target_y, _p.x, _p.y, None, scythe=scythe)
            _locked_name = "自我拉拽"

        # 发射后关闭瞄准锁定态
        rg.grapple_aiming = False
        rg.grapple_locked_target = None

        if success:
            # 记录钩爪使用
            if self.session:
                self.session.add_grapple()
            # 播放音效
            self.assets.play_sound("grapple")
            _txt = "死神钩爪·" + _locked_name if scythe else "钩爪·" + _locked_name
            self.floating_texts.append(FloatingText(
                _p.x, _p.y - 40, _txt,
                color=(200, 120, 255) if scythe else GREEN, lifetime=1.2
            ))
        return success

    def _select_skill_card(self, index):
        """选择技能卡（双人：作用于当前升级的玩家）"""
        # v2.5.8 修复：与 _apply_skill_card 保持一致的玩家选择逻辑
        _upw = getattr(self, '_upgrade_pause_player', None)
        player = self.player2 if (_upw == "P2" or getattr(self, 'pending_upgrade_for', None) == "P2") and self.player2 else self.player
        if 0 <= index < len(player.skill_cards):
            skill = player.skill_cards[index]
            self._apply_skill_card(skill)

    def _apply_skill_card(self, skill):
        """应用选中的技能卡（双人：作用于当前升级的玩家）"""
        # v2.1.3：双人 per-player 升级优先读 _upgrade_pause_player（单机仍走 pending_upgrade_for）
        _upw = getattr(self, '_upgrade_pause_player', None)
        player = self.player2 if (_upw == "P2" or getattr(self, 'pending_upgrade_for', None) == "P2") and self.player2 else self.player
        tag = _upw or getattr(self, 'pending_upgrade_for', "P1") or "P1"
        # v2.5.6：防重复应用（超时自动选卡与玩家点击可能同帧发生 → 同一技能被升两级）
        if not (getattr(player, 'pending_level_up', False) or getattr(player, 'skill_cards', None)):
            return
        if player.skill_tree.upgrade_skill(skill.skill_type):
            self.floating_texts.append(FloatingText(
                player.x, player.y - 40, 
                f"{tag} 升级: {skill.name}!", color=GOLD, lifetime=2.0
            ))
            # 记录技能升级
            if self.session:
                self.session.add_skill_upgrade()
                # 记录附魔拥有情况
                if skill.skill_type == SkillType.FLAME_ENCHANT:
                    self.session.set_has_enchant("flame", True)
                elif skill.skill_type == SkillType.FROST_ENCHANT:
                    self.session.set_has_enchant("frost", True)
                elif skill.skill_type == SkillType.POISON_ENCHANT:
                    self.session.set_has_enchant("poison", True)
            # 肾上腺素：应用体力加成
            if skill.skill_type == SkillType.ADRENALINE:
                ad_skill = player.skill_tree.get_skill(SkillType.ADRENALINE)
                if ad_skill:
                    player.riot_gear.adrenaline_level = ad_skill.current_level
            # 播放音效
            self.assets.play_sound("skill_select")
        # 升级后检查组合技
        try:
            self._check_combos()
        except Exception:
            pass
        # v2.5.2/2.5.8 多级连升逐级弹卡：还有剩余级数则重新生成卡片再次触发选卡
        _left = getattr(player, 'pending_levels', 0) - 1
        player.pending_levels = max(0, _left)
        if _left > 0:
            player.skill_cards = player.skill_tree.get_random_skill_cards(getattr(player, 'skill_slot_count', 3))
            player.pending_level_up = True
            # v2.6.1 修复：连升多级时重新调用 show 方法（确保卡片列表正确初始化）
            try:
                if hasattr(self, 'skill_card_selector') and self.skill_card_selector:
                    _tag = "P1" if player is self.player else ("P2" if player is getattr(self, 'player2', None) else "P1")
                    # v2.7.0 修复：半屏 region 只用于同屏双人；单机连升多级时若用半屏，
                    # 第二张及以后的技能卡只会显示在左半屏（与首次全屏不一致）。
                    try:
                        _mp_now = (self.is_multiplayer_active()
                                   and getattr(self, 'multiplayer_mode', None) == "same_screen")
                    except Exception:
                        _mp_now = False
                    _region = None
                    if _mp_now:
                        import pygame
                        _half = max(320, getattr(self, 'scaled_width', 1280) // 2)
                        _region = pygame.Rect(0 if _tag == "P1" else getattr(self, 'scaled_width', 1280) - _half,
                                              0, _half, getattr(self, 'scaled_height', 720))
                    self.skill_card_selector.show(player.skill_cards, region=_region,
                                                  title=f"{_tag} 升级！选择你的强化",
                                                  subtitle=f"{_tag} 等级 {player.level} → 选择技能卡")
            except Exception:
                pass
        else:
            player.pending_level_up = False
            player.skill_cards = []
            self.pending_upgrade_for = None
        # v2.1.3：双人 per-player 升级结束 → 恢复该玩家（重新可被怪物锁定/可移动）
        if getattr(self, '_upgrade_pause_player', None):
            self._upgrade_pause_player = None
            player.upgrade_paused = False
            # v2.5.6：清除限时免伤保护
            player.upgrade_grace_timer = 0.0
        if _left > 0:
            # 还有下一级：多人 per-player 立即重新进入暂停选卡（恢复会在下一级确认后再执行）
            # v2.6.5 修复：确保 _tag 正确确定（优先使用已知的 tag 值）
            _tag = tag if tag in ("P1", "P2") else ("P1" if player is self.player else "P2")
            self._upgrade_pause_player = _tag
            player.upgrade_paused = True
            # v2.5.8 修复：确保 pending_upgrade_for 同步更新（防止状态不一致）
            self.pending_upgrade_for = _tag
            # v2.5.6：新一轮选卡重新计时（保护限时 + 超时自动选）
            player.upgrade_grace_timer = self.UPGRADE_GRACE_TIME
            self._upgrade_pause_timer = self.UPGRADE_AUTO_PICK_TIME
        # v2.5.2 每次技能卡选择完毕：对玩家周围一定范围僵尸眩晕+击退（选卡保底防围死）
        try:
            _sr = 260.0
            for _e in list(self.enemies):
                if not getattr(_e, 'alive', False):
                    continue
                _dx = _e.x - player.x
                _dy = _e.y - player.y
                _dd = math.hypot(_dx, _dy)
                if _dd < _sr:
                    _e.apply_buff(BuffType.STUN, duration=1.2)
                    if _dd > 1:
                        _k = 230.0 / _dd
                        _e.x += _dx * _k
                        _e.y += _dy * _k
                    self.particles.spawn(_e.x, _e.y, (255, 220, 120), 6, size_range=(2, 5),
                                         velocity_range=(-60, 60), lifetime_range=(0.2, 0.4))
        except Exception:
            pass
        # v2.7.0 修复：连升多级时不能无条件 hide()+PLAYING。
        # 上面 _left>0 分支刚为下一级 show() 了新卡片，这里再 hide() 会立刻把它关掉，
        # 玩家看不到后续升级页（表现为「连升多级选卡异常 / 卡在 PLAYING」）。
        if _left <= 0:
            self.skill_card_selector.hide()
            self.state = GameState.PLAYING
        else:
            # 还有剩余级数：保持选择器可见，并把状态切回选卡（避免中间帧漏掉输入）
            try:
                _mp_now = (self.is_multiplayer_active()
                           and getattr(self, 'multiplayer_mode', None) == "same_screen")
            except Exception:
                _mp_now = False
            if not _mp_now and not getattr(self, '_upgrade_pause_player', None):
                self.state = GameState.SKILL_SELECT
