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

class PlayingMixin:
    # v2.2.6：救援平衡参数（防"挨得近无限互救根本死不掉"）
    RESCUE_COOLDOWN = 15.0      # 被救活后再次可被救援的冷却（秒）
    # v2.8.8：合作模式倒地时间 20s → 45s（原时长太短，队友根本来不及赶到）
    DOWNED_DEATH_TIME = 45.0    # 同屏倒地超过该时间未获救 → 彻底死亡

    def _update_rescue(self, dt):
        """双人救援系统：倒地→队友救援复活（同屏靠近自动救援 / 网络 8 秒自动复活）；全倒地则结束
        v2.2.6：加救援冷却（防无限互救）+ 倒地超时死亡 + 受击清空救援进度"""
        p1, p2 = self.player, self.player2
        if not p1 or not p2:
            return False
        _now = time.monotonic()
        # 1) 触发倒地：hp<=0 且未倒地 → 倒地（不立即死亡；alive 可能已被 take_damage 置 False，必须照常倒地）
        for p in (p1, p2):
            # v2.5.7 修复：永久死亡（救援超时）的玩家不再被重新判定为倒地
            # （此前超时死亡后 hp 仍为 0 → 下一帧又被判倒地 → 可反复被救起）
            if getattr(p, 'permanently_dead', False):
                continue
            if p.hp <= 0 and not p.downed:
                p.downed = True
                p.alive = False
                p.downed_timer = 0.0
                p.rescue_progress = 0.0
                p.last_rescue_time = getattr(p, 'last_rescue_time', -999.0)
                p._rescue_last_hp = p.hp
                p._rescue_mate_last_hp = (p2 if p is p1 else p1).hp if (p2 if p is p1 else p1) else 0
                self.floating_texts.append(FloatingText(
                    p.x, p.y - 40, "倒地！等待救援...", color=(240, 230, 120), lifetime=2.0))
                self.assets.play_sound_random(["player_hurt", "hurt"])
                # v2.2.7 倒地瞬间重置该玩家触控按钮（防按住状态残留导致救起后卡死）
                try:
                    tag = "P2" if p is p2 else "P1"
                    self._reset_touch_state_for(tag)
                except Exception:
                    pass
                # v2.2.7 倒地瞬间强制清除换弹状态（换弹中被击倒→救起后不再卡死无法开火）
                self._reset_weapons_reload(p)
        # 2) 救援 / 自动复活
        for p in (p1, p2):
            if not p.downed:
                continue
            p.downed_timer += dt
            mate = p2 if p is p1 else p1
            rescued = False
            _cdh = getattr(p, '_rescue_cd_hint', 0.0) - dt
            p._rescue_cd_hint = max(0.0, _cdh)
            # v2.5.7 修复：救援者被怪物打中 → 救援被打断（此前只检测被救者掉血，
            #   而倒地的玩家不会被怪物选中 → 救援永远不被打断）
            if mate is not None:
                _mlh = getattr(p, '_rescue_mate_last_hp', mate.hp)
                if _mlh > mate.hp and p.rescue_progress > 0:
                    p.rescue_progress = 0.0
                    self.floating_texts.append(FloatingText(
                        mate.x, mate.y - 60, "救援被打断!", color=(230, 140, 120), lifetime=0.9))
                p._rescue_mate_last_hp = mate.hp
            if self.multiplayer_mode == "same_screen":
                _cd_ok = (_now - getattr(p, 'last_rescue_time', -999.0)) >= self.RESCUE_COOLDOWN
                # v2.4.0 PvPvE：只有同阵营队友可救援（异阵营不能互相救）
                _same_team = True
                if getattr(self.config, 'pvp_enabled', False):
                    _same_team = getattr(p, 'team_id', 0) == getattr(mate, 'team_id', 1)
                near = (mate is not None and not mate.downed and _same_team
                        and math.hypot(mate.x - p.x, mate.y - p.y) < 120)
                if near and not _cd_ok and getattr(p, '_rescue_cd_hint', 0.0) <= 0:
                    # 冷却中给个提示（否则队友就在旁边却救不了，玩家毫无反馈）
                    p._rescue_cd_hint = 3.0
                    self.floating_texts.append(FloatingText(
                        p.x, p.y - 70, "救援冷却中...", color=(200, 180, 140), lifetime=1.4))
                if near and _cd_ok:
                    p.rescue_progress += dt
                    # v2.2.7 救援者 UI 反馈：救援者与被救者都看到进度（0.5s 节流浮字）
                    _fb = getattr(self, '_rescue_fb_timer', 0.0) - dt
                    self._rescue_fb_timer = _fb
                    if _fb <= 0:
                        self._rescue_fb_timer = 0.5
                        _pct = int(p.rescue_progress / 2.5 * 100)
                        _rtag = "P2" if p is p2 else "P1"
                        self.floating_texts.append(FloatingText(
                            mate.x, mate.y - 55, f"正在救援 {_rtag}... {_pct}%", color=(120, 230, 140), lifetime=0.6))
                        self.floating_texts.append(FloatingText(
                            p.x, p.y - 70, f"队友正在救援... {_pct}%", color=(120, 230, 140), lifetime=0.6))
                    if p.rescue_progress >= 2.5:
                        rescued = True
                else:
                    p.rescue_progress = 0.0
                # 倒地超时 → 彻底死亡（防无限拖延；全倒地由调用方判定结束）
                if p.downed_timer >= self.DOWNED_DEATH_TIME:
                    p.downed = False
                    p.alive = False
                    # v2.5.7：标记永久死亡（不再被重新判定倒地）
                    p.permanently_dead = True
                    self.floating_texts.append(FloatingText(
                        p.x, p.y - 40, "救援超时，未能生还...", color=(200, 60, 60), lifetime=2.5))
                    continue
            else:
                # 网络联机：8 秒自动复活（跨设备救援不便，给保底）
                if p.downed_timer >= 8.0:
                    rescued = True
            if rescued:
                p.downed = False
                p.alive = True
                p.permanently_dead = False
                p._rescue_cd_hint = 0.0
                # v2.5.2 救援统计（成就 mp_rescue_10）
                try:
                    if getattr(self, 'records', None) is not None:
                        self.records.add_mp_stat("mp_rescues")
                except Exception:
                    pass
                p.hp = int(p.max_hp * 0.5)
                p.rescue_progress = 0.0
                p.last_rescue_time = _now  # 进入救援冷却
                p.invincible_timer = 1.5
                self.floating_texts.append(FloatingText(p.x, p.y - 40, "已复活!", color=GREEN, lifetime=1.5))
                # v2.2.7 被救起后重置该玩家触控按钮（防倒地期间按住的按钮残留卡死）
                try:
                    tag = "P2" if p is p2 else "P1"
                    self._reset_touch_state_for(tag)
                except Exception:
                    pass
                # v2.2.7 被救起后强制清除换弹状态（换弹卡死根因修复）
                self._reset_weapons_reload(p)
                try:
                    self.assets.play_sound("heal")
                except Exception:
                    pass
        # 3) 双人全部倒地 → 游戏结束
        return bool((p1.downed or not p1.alive) and (p2.downed or not p2.alive))

    def _update_overdrive(self, player, dt):
        """v2.5.7 过热倾泻统一更新（P1/P2 共用）：
        1) 倒计时递减——此前只有 P1 递减，P2 的 overdrive_timer 只被赋值 → 永久过热；
        2) 当前武器冷却额外削减（射速暴增的真正实现，P2 此前完全缺失）；
        3) 枪口灼烧粒子。
        """
        if player is None:
            return
        _t = getattr(player, 'overdrive_timer', 0)
        if _t <= 0:
            return
        player.overdrive_timer = max(0.0, _t - dt)
        if player.overdrive_timer <= 0:
            player.overdrive_burn = False
        try:
            _ow = player.get_current_weapon()
        except Exception:
            _ow = None
        if _ow is not None and getattr(_ow, 'cooldown_timer', 0) > 0:
            try:
                _ow.cooldown_timer -= (getattr(player, 'overdrive_mult', 2.0) - 1.0) * dt
            except Exception:
                pass
        try:
            self.particles.spawn(player.x, player.y, (255, 160, 60), 2, (1, 3), (-2, 2), (0.1, 0.4))
        except Exception:
            pass

    def _reset_weapons_reload(self, player):
        """v2.2.7：强制清除玩家所有武器换弹状态（退出重载/倒地救起后调用，
        防止 reload_timer 残留导致永远无法开火）"""
        if player is None:
            return
        try:
            for _w in (getattr(player, 'weapons', None) or []):
                if hasattr(_w, 'reset_reload'):
                    _w.reset_reload()
            _cw = player.get_current_weapon() if hasattr(player, 'get_current_weapon') else None
            if _cw is not None and hasattr(_cw, 'reset_reload'):
                _cw.reset_reload()
        except Exception:
            pass

    def _alive_players(self):
        """返回存活的玩家列表（单人=[P1]，双人=[P1,P2]）"""
        ps = [self.player]
        if self.player2:
            ps.append(self.player2)
        return [p for p in ps if p is not None and getattr(p, 'alive', True) and not getattr(p, 'downed', False)]

    def _all_players(self):
        """v2.2.7 PvPvE：返回全部玩家实体（P1~P4，含 AI 补位）"""
        ps = []
        for _a in ("player", "player2", "player3", "player4"):
            _p = getattr(self, _a, None)
            if _p is not None:
                ps.append(_p)
        return ps

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
        # v2.2.3 争分夺秒加时反馈计时（HUD "+N 秒"淡出）
        if getattr(self, 'race_gain_timer', 0) > 0:
            self.race_gain_timer = max(0.0, self.race_gain_timer - dt)
            if self.race_gain_timer <= 0:
                self.race_last_gain = 0
        # v2.0.19 BOSS 锁定必中标记推进（蓄力结束 → 必中伤害）
        locks = getattr(self, "boss_lock_marks", [])
        if locks:
            alive = []
            for lm in locks:
                _e, _pl, _t = lm
                _t -= dt
                if _t <= 0:
                    try:
                        _dmg = int(getattr(_e, "damage", 20) * 4.0)  # 必中高伤（4倍普攻）
                        _dodge = getattr(_pl, "dodge_chance", 0.0)
                        _pl.dodge_chance = 0.0   # 锁定必中：不可闪避
                        _pl.take_damage(_dmg, "magic")
                        _pl.dodge_chance = _dodge
                        self.floating_texts.append(FloatingText(_pl.x, _pl.y - 40, "被锁定重创!", color=(255, 60, 60), lifetime=1.2))
                        if hasattr(self, "camera") and self.camera is not None:
                            self.camera.shake(8, 0.5)
                    except Exception:
                        pass
                    continue
                alive.append([_e, _pl, _t])
            self.boss_lock_marks = alive
        # 衰减吸血屏幕效果
        # Mod 每帧钩子
        try:
            trigger_hook(HOOK_GAME_TICK, self, dt)
        except Exception:
            pass
        if self.lifesteal_flash > 0:
            self.lifesteal_flash = max(0, self.lifesteal_flash - dt * 1.5)

        # 角色技能：随时间缓慢回血（如医护兵）
        # v2.8.8 修复：此前**只给 P1 回血**，P2/P3/P4 选了医护兵却完全不回血
        # —— 这就是"P2 没有角色效果"的直接原因。改为遍历全部注册玩家。
        self._char_regen_timer = getattr(self, '_char_regen_timer', 0) + dt
        if self._char_regen_timer >= 2.0:
            self._char_regen_timer = 0.0
            for _p in self.registered_players():
                try:
                    if getattr(_p, 'health_regen', 0) > 0 and \
                            getattr(_p, 'alive', False) and not getattr(_p, 'downed', False):
                        _p.heal(_p.health_regen * 2)
                except Exception:
                    pass

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
            # v2.5.5 打断绳索 QTE：被勾期间任意"按下"即登记为待判定单击点（世界坐标，P1 视口 x 偏移 0）
            try:
                if self.player.grappled and self.player.qte_window > 0 and self.player.qte_break_tap is None:
                    for _e2 in _tev:
                        if _e2.get("type") == "down":
                            _sx, _sy = _e2.get("pos", (0, 0))
                            self.player.qte_break_tap = (
                                self.camera.x + _sx / self.scale,
                                self.camera.y + _sy / self.scale)
                            break
            except Exception:
                pass
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

            # ===== v2.2.5/11 钩爪瞄准锁定圈：长按瞄准期间每帧更新圈内锁定目标 =====
            _rg_aim = self.player.riot_gear
            if self.skill_caster.is_aiming and self.selected_skill == SkillType.GRAPPLE_PULL:
                _rg_aim.grapple_aiming = True
                # v2.2.11 触控：锚点跟随瞄准方向/距离实时移动（skill_caster.angle 弧度→度）
                _aim_ang = math.degrees(self.skill_caster.angle)
                _aim_dist = self._get_skill_max_distance(self.selected_skill) * self.skill_caster.distance_ratio
                _rg_aim.update_grapple_lock(self.player.x, self.player.y, self.enemies,
                                            items=getattr(self.world, 'items', None),
                                            aim_angle=_aim_ang, aim_dist=_aim_dist,
                                            players_down=self._downed_teammates_of(self.player),
                                            players_enemy=self._enemy_players_of(self.player),
                                            players_teammate=self._alive_teammates_of(self.player))
            else:
                _rg_aim.grapple_aiming = False
                if not _rg_aim.grapple_active:
                    _rg_aim.grapple_locked_target = None

            # 技能释放按钮 - 支持拖拽改变方向和距离
            self.skill_caster.set_player_pos(self.player.x, self.player.y, self.camera.x, self.camera.y)
            self.skill_caster.set_max_distance(self._get_skill_max_distance(self.selected_skill))
            # 保存释放前的瞄准状态（handle_touch会在up时重置is_aiming）
            cast_result = self.skill_caster.handle_touch(_tev, self.scale)
            # v2.2.9 触控长按瞄准：钩爪锁定圈同步更新（修复触控端锁定圈完全失效/中心错位）
            try:
                _rg_t = self.player.riot_gear
                if self.skill_caster.is_aiming and self.selected_skill == SkillType.GRAPPLE_PULL:
                    _rg_t.grapple_aiming = True
                    _aim_t_ang = math.degrees(self.skill_caster.angle)
                    _aim_t_dist = self._get_skill_max_distance(self.selected_skill) * self.skill_caster.distance_ratio
                    _rg_t.update_grapple_lock(self.player.x, self.player.y, self.enemies,
                                              items=getattr(self.world, 'items', None),
                                              aim_angle=_aim_t_ang, aim_dist=_aim_t_dist,
                                              players_down=self._downed_teammates_of(self.player),
                                              players_enemy=self._enemy_players_of(self.player),
                                              players_teammate=self._alive_teammates_of(self.player))
                else:
                    # v2.2.12 修复：释放帧（up 后 is_aiming=False）不得清 locked_target——
                    # 否则"红色锁定"在松开瞬间被清空，钩爪决策拿不到锁定目标导致未勾取。
                    # 锁定态由发射决策（_use_skill_aimed 后）统一清理。
                    _rg_t.grapple_aiming = False
                    if not _rg_t.grapple_active and not cast_result:
                        _rg_t.grapple_locked_target = None
            except Exception:
                pass
            if cast_result:
                # v2.2.3 载具存活时长按技能按钮 → 退出载具（不执行预瞄/施放）
                # v2.5.7 修复：只有当前技能为「载具召唤」时长按才退出载具；
                #   其它技能在载具中照常释放（原来任何技能长按都会被吞掉并强制下车）
                _veh_t = getattr(self.player, 'vehicle', None)
                _is_veh_skill = (self.selected_skill == SkillType.VEHICLE_SUMMON)
                if _veh_t is not None and _veh_t.alive and _is_veh_skill:
                    if self.skill_caster.was_aiming_on_release:
                        self._exit_vehicle(self.player)
                    else:
                        self.floating_texts.append(FloatingText(
                            self.player.x, self.player.y - 50, "长按技能按钮退出载具", (160, 160, 160), 1.2))
                elif getattr(self.player, 'riding_vehicle', None) is not None and _is_veh_skill:
                    # v2.5.1 乘客：长按技能按钮下车
                    if self.skill_caster.was_aiming_on_release:
                        self._exit_vehicle(self.player)
                    else:
                        self.floating_texts.append(FloatingText(
                            self.player.x, self.player.y - 50, "长按技能按钮下车", (160, 160, 160), 1.2))
                elif self._find_board_candidate(self.player) is not None and self.is_multiplayer_active():
                    # v2.5.1 附近有同阵营载具：按下技能按钮即上车
                    _bc = self._find_board_candidate(self.player)
                    if _bc is not None:
                        self._board_vehicle(self.player, _bc)
                elif self.skill_caster.was_aiming_on_release:
                    self._use_skill_aimed(self.selected_skill, self.skill_caster.angle, self.skill_caster.distance_ratio,
                                            force_self_pull=self.skill_caster.was_aiming_on_release)
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
                elif name == "settle" and btn.just_released:
                    # v2.2.0 争分夺秒：主动结算关卡
                    _ss = getattr(self, '_settle_race_manual', None)
                    if _ss is not None:
                        _ss()

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
        # v2.1.3：同屏双人 P1 升级选卡时暂停 P1 移动/受击（怪物脱锁由目标选择处处理）
        _p1_paused = self.is_multiplayer_active() and getattr(self, '_upgrade_pause_player', None) == "P1"
        if not _p1_paused:
            # v2.2.0 载具期间：载具移动/撞击/开火逻辑接管玩家移动
            _veh = getattr(self.player, 'vehicle', None)
            if _veh is not None and _veh.alive:
                _veh.update(dt)
                _veh.move(move_x * _zone_mult, move_y * _zone_mult, dt, self.world.clamp_position)
                self.player.x, self.player.y = _veh.x, _veh.y
                # 载具撞击伤害
                try:
                    _hits = _veh.ram_enemies(self.enemies, self.damage_numbers, self.particles)
                    for _e in _hits:
                        if not getattr(_e, 'alive', False):
                            self._on_enemy_death(_e)
                except Exception:
                    pass
                # 玩家 update 只处理状态/冷却（移动已由载具接管）
                self.player.update(dt, 0.0, 0.0, mouse_angle, self.world, sprinting=False)
            # v2.2.6：载具被打爆检测移到独立分支（原嵌套在 alive 块内，dead 后永远进不去 → CD 不触发）
            if _veh is not None and not _veh.alive:
                self._vehicle_destroyed()
            elif _veh is None:
                # v2.5.1 阵营载具乘客：位置由载具 update 同步，禁用玩家位移（射击/技能照常）
                _rv2 = getattr(self.player, 'riding_vehicle', None)
                if _rv2 is not None and getattr(_rv2, 'alive', False):
                    self.player.update(dt, 0.0, 0.0, mouse_angle, self.world, sprinting=False)
                else:
                    # v2.2.10 修复：钩爪自我拉拽期间禁用玩家额外位移（拉回独占位移，
                    # 防"故意不走蹭无敌"）——玩家输入 move 清零，仅由 gear self_pull 拉回
                    try:
                        if getattr(self.player, 'riot_gear', None) is not None and \
                                getattr(self.player.riot_gear, 'grapple_state', None) == "self_pull":
                            move_x, move_y = 0.0, 0.0
                    except Exception:
                        pass
                    self.player.update(dt, move_x * _zone_mult, move_y * _zone_mult,
                                       mouse_angle, self.world, sprinting=sprinting)
                # 符文：再生效果
                if hasattr(self, 'rune_manager'):
                    regen = self.rune_manager.get_bonus("regen")
                    if regen > 0 and self.player.hp < self.player.max_hp:
                        self.player.hp = min(self.player.max_hp, self.player.hp + regen * dt)
        # speed_mult 已乘符文加成，无论暂停与否都必须恢复
        self.player.speed_mult = orig_speed_mult
        # 盾牌冲撞 / v2.7.0 无畏冲锋更新（移动+碰撞伤害；P1 升级暂停时不更新）
        if not _p1_paused:
            self._update_charge(dt)
        # v2.7.0：同屏双人时同步更新 P2 的冲撞/无畏冲锋
        _p2c = getattr(self, 'player2', None)
        if _p2c is not None and getattr(_p2c, 'riot_gear', None) is not None:
            if getattr(_p2c.riot_gear, 'charge_active', False):
                self._update_charge(dt, player=_p2c)
        # 过热倾泻：计时 + 射速加成（冷却额外递减）+ 灼烧枪口特效
        # v2.5.7：抽成 P1/P2 共用函数（此前 P2 只被赋值，计时器从不递减 → 永久过热）
        self._update_overdrive(self.player, dt)
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
        # v2.5.7：PvP 毒圈更新（收缩 + 圈外伤害）
        try:
            self._update_pvp_zone(dt)
        except Exception:
            pass
        # v2.5.7：世界更新考虑所有活跃玩家（道具刷新/区块生成按每个玩家进行）
        _wpos = []
        try:
            for _pp in self._all_players():
                if _pp is None or _pp is self.player:
                    continue
                if not getattr(_pp, 'alive', True) or getattr(_pp, 'downed', False):
                    continue
                _wpos.append((_pp.x, _pp.y))
        except Exception:
            _wpos = []
        # v2.8.1 防御：world 缺失时不要抛 NoneType 异常打断整帧
        if getattr(self, 'world', None) is not None:
            self.world.update(dt, self.player.x, self.player.y, _wpos)

        # === Buff视觉效果 ===
        self._update_buff_visuals(dt)

        # 更新尸潮管理器
        if getattr(self, 'horde_manager', None) is not None:
            self.horde_manager.update(dt)

        # 尸潮音乐切换
        if self.horde_manager.is_horde_active():
            self.assets.play_music("horde")
            self._music_context = 'horde'
        elif hasattr(self, '_was_horde') and self._was_horde and not self.horde_manager.is_horde_active():
            # 尸潮结束，记录存活
            if self.session:
                self.session.add_horde_survived()
            # 尸潮结束，恢复地图专属音乐（争分夺秒模式恢复 race 专用配乐）
            map_music = self._resolve_map_music()
            self.assets.play_music(map_music)
            self._music_context = 'explore'
            # 尸潮奖励：根据规模刷新对应奖励
            self._spawn_horde_rewards()
        self._was_horde = self.horde_manager.is_horde_active()

        # ========== 故事模式核心逻辑 ==========
        if self.config.game_mode == GameMode.STORY:
            self._update_story_mode(dt)

        # 检查升级选择（同屏双人：P1/P2 各自升级，半屏显示并标注是谁）
        # v2.1.3：双人模式改为 per-player 暂停升级 —— 不再切全局 SKILL_SELECT，
        # 升级玩家进入选卡弹窗（半屏）且怪物脱锁/免伤，另一玩家游戏完全不受影响
        _mp = self.is_multiplayer_active() and self.multiplayer_mode == "same_screen"
        if self.state != GameState.SKILL_SELECT and not (_mp and self._upgrade_pause_player):
            for _pl, _tag in ((self.player, "P1"), (self.player2, "P2")):
                if not _pl or not _pl.pending_level_up:
                    continue
                if _pl.skill_cards:
                    if _mp:
                        # 双人：per-player 暂停，不切全局状态
                        self.pending_upgrade_for = _tag
                        self._upgrade_pause_player = _tag
                        _pl.upgrade_paused = True
                        # v2.5.6：限时免伤保护 + 超时自动选卡
                        # （防"故意停在升级界面"吃永久无敌：保护只持续数秒，超时自动选卡）
                        _pl.upgrade_grace_timer = self.UPGRADE_GRACE_TIME
                        self._upgrade_pause_timer = self.UPGRADE_AUTO_PICK_TIME
                        # v2.2.6：暂停瞬间重置该玩家触控控件（per-player 不切状态，
                        # 状态切换重置不会触发，防止升级玩家射击/摇杆残留卡死）
                        try:
                            self._reset_touch_state_for(_tag)
                        except Exception:
                            pass
                        _half = max(320, self.scaled_width // 2)
                        _region = pygame.Rect(0 if _tag == "P1" else self.scaled_width - _half, 0, _half, self.scaled_height)
                        self.skill_card_selector.show(_pl.skill_cards, region=_region,
                                                      title=f"{_tag} 升级！选择你的强化",
                                                      subtitle=f"{_tag} 等级 {_pl.level} → 选择技能卡")
                    else:
                        self.state = GameState.SKILL_SELECT
                        self.pending_upgrade_for = _tag
                        self.skill_card_selector.show(_pl.skill_cards, region=None,
                                                      title=f"{_tag} 升级！选择你的强化",
                                                      subtitle=f"{_tag} 等级 {_pl.level} → 选择技能卡")
                    # 记录升级
                    if self.session:
                        self.session.add_level_up()
                    # 播放升级音效
                    self.assets.play_sound("level_up")
                else:
                    _pl.pending_level_up = False
                    _pl.pending_levels = 0  # v2.5.2 无可用卡时清空待结算次数
                break

        # v2.5.6：升级选卡保护倒计时 + 超时自动选卡（防卡界面无限无敌）
        self._update_upgrade_pause(dt)
        # v2.7.1：BOSS 台词字幕（非阻塞，游戏全程继续运行）
        try:
            self._update_subtitles(dt)
        except Exception:
            pass
        # v2.8.0 全局回放采样 + 打击反馈推进
        try:
            self._replay_tick(dt)
        except Exception:
            pass
        try:
            self._feedback_tick(dt)
        except Exception:
            pass

        # 自动射击 / 盾肘击【修改】
        auto_shoot = False
        # v2.1.3：P1 升级选卡暂停射击/肘击（触控模式下 P1 输入也已暂停）
        if not (self.is_multiplayer_active() and getattr(self, '_upgrade_pause_player', None) == "P1"):
            if self.config.control_mode == ControlMode.KEYBOARD:
                mouse_left = pygame.mouse.get_pressed()[0]
                # 装备防爆套装，鼠标左键执行肘击，不再开火
                # v2.8.8：无畏冲锋期间禁用肘击（冲锋只能靠摇杆/方向键转向）
                if mouse_left and self.player.can_act() and \
                        not getattr(self.player, 'fearless_charge_active', False):
                    if self.player.riot_gear.equipped and self.riot_anim_state == "idle":
                        self._perform_bash(math.degrees(mouse_angle))
                    else:
                        auto_shoot = True
                elif not getattr(self.player, 'fearless_charge_active', False):
                    auto_shoot = bool(mouse_left and self.player.can_act())
            else:
                auto_shoot = self.aim_button.is_shooting

        # ========== v2.5.6 蓄力预瞄武器（AWM / 轨道炮）============
        # 规则：按住开火键 = 蓄力（显示弹道预瞄线，角度随摇杆/鼠标实时更新），松开 = 开火一次。
        # v2.5.5 实现存在三处 bug，本版全部修正：
        #   ① 蓄力中只置 auto_shoot=False，但开火分支并未检查该标记 → 「未松开就发射」；
        #   ② 松开分支被包在「要求 auto_shoot 为真」的外层 elif 内 → 永远不可达 → 松开不开火；
        #   ③ 蓄力角度从不清除 → 「预瞄线卡死，不消失也不改变」。
        _fire_angle = None       # 本帧实际开火角度（松开瞬间的蓄力角）
        _charge_blocked = False  # True=按住蓄力中，本帧禁止开火
        _charge_weapon = None
        try:
            _veh_now = getattr(self.player, 'vehicle', None)
            if _veh_now is None or not _veh_now.alive:
                _charge_weapon = self.player.get_current_weapon()
        except Exception:
            _charge_weapon = None
        if _charge_weapon is not None and getattr(_charge_weapon, "hold_charge", False):
            _saved_aim = getattr(self.player, "_awm_saved", None)
            if auto_shoot and not _p1_paused:
                # 按住：实时更新蓄力角（拖拽时预瞄线跟随摇杆），本帧不开火
                self.player._awm_saved = mouse_angle
                _charge_blocked = True
                # v2.8.8 蓄力收敛：记录蓄力起始时间，供散布扇形收敛 + 视野拉大使用
                if getattr(self.player, '_charge_start_t', None) is None:
                    self.player._charge_start_t = time.time()
            elif _saved_aim is not None and not _p1_paused:
                # 松开：按蓄力角开火一次，并立刻清空预瞄（预瞄线立即消失，不再卡死）
                _fire_angle = _saved_aim
                self.player._awm_saved = None
                self.player._charge_start_t = None
        elif getattr(self.player, "_awm_saved", None) is not None:
            self.player._awm_saved = None
            self.player._charge_start_t = None

        # ==================================================================
        # v2.8.8 蓄力武器的"散布收敛"与"视野拉远"
        # ------------------------------------------------------------------
        # 按住开火键时：
        #   1) 子弹散布由一个**大扇形**逐渐收窄（圆心角随蓄力时长变小），
        #      收敛到阈值后达到该武器最小散布 —— 直观表达"越稳越准"；
        #   2) 视野（摄像机缩放）随蓄力逐渐拉远，直至能看见子弹的极限射程，
        #      模拟狙击手"屏息拉远观察"的体验。
        # 松开即恢复。
        # ==================================================================
        _charge_t = 0.0
        _charge_ratio = 0.0
        _charge_w = _charge_weapon
        if _charge_w is not None and getattr(_charge_w, "hold_charge", False) \
                and getattr(self.player, "_awm_saved", None) is not None:
            _st = getattr(self.player, "_charge_start_t", None)
            if _st is not None:
                _charge_t = max(0.0, time.time() - _st)
            _full = float(getattr(_charge_w, "charge_full_time", 1.2) or 1.2)
            _charge_ratio = max(0.0, min(1.0, _charge_t / _full))
            # 1) 散布收敛：扇形圆心角从 spread 上限线性收敛到下限
            try:
                _sp_max = float(getattr(_charge_w, "charge_spread_max",
                                        getattr(_charge_w, "spread", 0.06) or 0.06) or 0.06)
                _sp_min = float(getattr(_charge_w, "charge_spread_min", 0.0) or 0.0)
                _cur_spread = _sp_max + (_sp_min - _sp_max) * _charge_ratio
                self.player._charge_spread = _cur_spread
                self.player._charge_ratio = _charge_ratio
            except Exception:
                pass
            # 2) 视野拉远：随蓄力把摄像机 zoom 拉低（拉远）到能覆盖射程
            try:
                _cam = getattr(self, "camera", None)
                if _cam is not None and hasattr(_cam, "zoom"):
                    _z0 = float(getattr(_cam, "_zoom_base", 0.0) or 0.0)
                    if _z0 <= 0.0:
                        _cam._zoom_base = float(getattr(_cam, "zoom", 1.0) or 1.0)
                        _z0 = _cam._zoom_base
                    _z_min = float(getattr(_charge_w, "charge_zoom_min", 0.62) or 0.62)
                    _cam.zoom = _z0 + (_z_min - _z0) * _charge_ratio
                    self.player._charge_zoom_active = True
            except Exception:
                pass
        elif getattr(self.player, "_charge_zoom_active", False):
            # 松开 / 切换武器：恢复原视野
            try:
                _cam = getattr(self, "camera", None)
                if _cam is not None and hasattr(_cam, "zoom"):
                    _z0 = float(getattr(_cam, "_zoom_base", 0.0) or 0.0)
                    if _z0 > 0.0:
                        _cam.zoom = _z0
                    _cam._zoom_base = 0.0
            except Exception:
                pass
            self.player._charge_zoom_active = False
            self.player._charge_spread = None
            self.player._charge_ratio = 0.0
        elif getattr(self.player, "_awm_saved", None) is not None:
            # 当前武器不是蓄力武器（切武器/装备被卸下等）：清理残留预瞄，避免预瞄线卡死
            self.player._awm_saved = None

        # v2.2.3 载具开火独立于防爆套装/装备动画条件（装备防爆套装也能发射载具武器）
        _veh = getattr(self.player, 'vehicle', None)
        if _veh is not None and _veh.alive and _veh.can_shoot:
            if auto_shoot and self.player.can_act():
                rune_dmg_mult = 1.0 + getattr(self, 'rune_buffs', {}).get("damage", 0)
                _projs = _veh.fire(
                    self.player.x, self.player.y, self.player.facing_angle,
                    self.player.damage_mult * self.player.damage_boost_mult * self.player.buff_manager.get_damage_mult() * rune_dmg_mult)
                self.projectiles.extend(_projs)
                if _projs:
                    self.assets.play_sound_random(["shoot_pistol", "shoot_smg"])
        elif (auto_shoot or _fire_angle is not None) and self.player.can_act() and not self.player.riot_gear.equipped and self.riot_anim_state != "equipping":
            weapon = None  # 防御：weapon_type 为 None（异常存档/联机同步兜底）
            if _veh is None or not _veh.alive:
                weapon = self.player.get_current_weapon()
            # v2.5.6 蓄力武器：按住期间抑制开火（仅在松开瞬间开火一次）
            _shot_angle = _fire_angle if _fire_angle is not None else mouse_angle
            if weapon is not None and getattr(weapon, "hold_charge", False) and _charge_blocked:
                pass  # 蓄力中 → 本帧不开火（预瞄线由 draw 渲染）
            # v2.1.3：防御 weapon/weapon_type 为 None（异常存档/联机同步兜底，不再崩溃）
            elif weapon is not None and getattr(weapon, "weapon_type", None) is not None and weapon.can_fire():
                # 过热倾泻buff：无限弹药
                if getattr(self.player, 'overdrive_timer', 0) > 0 and hasattr(weapon, 'current_ammo') and weapon.current_ammo != "∞":
                    weapon.current_ammo = min(weapon.max_ammo, weapon.current_ammo + 1)
                # 符文伤害加成
                rune_dmg_mult = 1.0 + getattr(self, 'rune_buffs', {}).get("damage", 0)
                trigger_hook(HOOK_PLAYER_FIRE, weapon, self.player)
                _fire_mult = self.player.damage_mult * self.player.damage_boost_mult * self.player.buff_manager.get_damage_mult() * rune_dmg_mult * self.player.damage_multiplier
                # v2.5.2 近战武器（死神镰刀等）吃全部近战系列技能：
                # MELEE_DAMAGE / BERSERKER / COMBO_MASTER 并入火力乘区；
                # MELEE_SPEED 压缩发射冷却；MELEE_RANGE 临时扩剑气射程；LIFESTEAL 命中回血
                _is_near = getattr(weapon, "is_scythe", False) or getattr(weapon, "is_melee", False)
                _melee_bonus_speed = 1.0
                _melee_bonus_range = 1.0
                if _is_near and getattr(self.player, 'skill_tree', None):
                    _st = self.player.skill_tree
                    # 近战伤害
                    _melee_dmg_skill = _st.get_skill(SkillType.MELEE_DAMAGE)
                    if _melee_dmg_skill and _melee_dmg_skill.current_level > 0:
                        _fire_mult *= (1.0 + _melee_dmg_skill.current_level * 0.25)
                    # 狂暴（低血量增伤）
                    _berserker_skill = _st.get_skill(SkillType.BERSERKER)
                    if _berserker_skill and _berserker_skill.current_level > 0:
                        _hp_ratio = self.player.hp / max(1, self.player.max_hp)
                        if _hp_ratio < 0.5:
                            _dmg_bonus = _berserker_skill.current_level * 0.3
                            if _berserker_skill.current_level >= 3 and _hp_ratio < 0.2:
                                _dmg_bonus += 0.5
                            _fire_mult *= (1.0 + _dmg_bonus)
                    # 连击大师
                    _combo_skill = _st.get_skill(SkillType.COMBO_MASTER)
                    if _combo_skill and _combo_skill.current_level > 0:
                        _max_layers = [0, 5, 8, 10][_combo_skill.current_level]
                        _per_layer = [0, 0.05, 0.08, 0.10][_combo_skill.current_level]
                        _cc = min(getattr(self, 'melee_combo_count', 0), _max_layers)
                        _fire_mult *= (1.0 + _cc * _per_layer)
                    # 近战攻速（发射后压缩冷却）
                    _melee_speed_skill = _st.get_skill(SkillType.MELEE_SPEED)
                    if _melee_speed_skill and _melee_speed_skill.current_level > 0:
                        _melee_bonus_speed = 1.0 + _melee_speed_skill.current_level * 0.2
                    # 近战范围（发射前临时扩射程）
                    _melee_range_skill = _st.get_skill(SkillType.MELEE_RANGE)
                    if _melee_range_skill and _melee_range_skill.current_level > 0:
                        _melee_bonus_range = 1.0 + _melee_range_skill.current_level * 0.15
                _orig_range = weapon.range
                if _melee_bonus_range != 1.0:
                    weapon.range = int(weapon.range * _melee_bonus_range)
                try:
                    proj_list = weapon.fire(
                        self.player.x, self.player.y, _shot_angle,
                        _fire_mult, self.player.speed_mult,
                        player=self.player
                    )
                finally:
                    weapon.range = _orig_range
                if _melee_bonus_speed != 1.0:
                    weapon.cooldown_timer = max(0.0, weapon.cooldown_timer / _melee_bonus_speed)
                self.projectiles.extend(proj_list)
                # 过热倾泻灼烧：子弹附带火焰
                if getattr(self.player, 'overdrive_burn', False):
                    for _p in proj_list:
                        _p.is_flame = True
                
                # 近战武器攻击处理
                if getattr(weapon, "melee_attack_triggered", False):
                    weapon.melee_attack_triggered = False
                    self._start_melee_attack(weapon, _shot_angle)
                
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
                    # v2.1.3：weapon_type 兜底（防御 Weapon(None) 遗留对象）
                    _wt = getattr(weapon, "weapon_type", None)
                    wtype = _wt.name.lower() if _wt is not None else "pistol"
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

        # v2.6.0：开发者面板禁用僵尸刷新（任一玩家开启则全局禁用）
        _spawn_disabled = False
        try:
            for _idx in (1, 2, 3, 4):
                _dst = self._dev_state(_idx)
                if getattr(_dst, 'disable_zombie_spawn', False):
                    _spawn_disabled = True
                    break
        except Exception:
            pass
        # 生成敌人 - 尸潮期间大量刷新，非尸潮期间少量刷新
        # 双人/联机：怪物按玩家人数调整难度（上限×1.8 + 额外刷新频率）
        spawn_type = self.horde_manager.should_spawn() if not _spawn_disabled else None
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
            # 故事/争分夺秒模式：使用地图配置的怪物权重（Boss除外）——v2.2.3 两模式僵尸池同步合并
            boss_types = (EnemyType.BOSS_LONG, EnemyType.BOSS_XIANG, EnemyType.BOSS_MUTANT,
                         EnemyType.BOSS_QUEEN, EnemyType.BOSS_TITAN, EnemyType.BOSS_WANG)
            if self.config.game_mode in (GameMode.STORY, GameMode.TIMED) and spawn_type not in boss_types:
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
            # v2.5.3 多人刷怪：随机一个活跃玩家为中心（每个玩家周围都会刷新，不再只围最近者）
            _sc = self._random_spawn_center()
            spawn_x = _sc.x + math.cos(angle) * dist
            spawn_y = _sc.y + math.sin(angle) * dist
            spawn_x, spawn_y = self.world.clamp_position(spawn_x, spawn_y, 20)
            enemy = Enemy(spawn_x, spawn_y, spawn_type, 1, self.config.difficulty)
            # v2.2.4：决策树 AI（无训练硬编程）挂载；未挂载/异常 → 回退原规则 AI
            if getattr(self, "ai_controller", None) is not None:
                enemy.ai_rl = self.ai_controller
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
                # v2.4.0 boss 软性限制圈：中心=生成点，半径随波次增大（出圈减速拉回，不硬阻挡）
                try:
                    _bzr = 420.0 + min(260.0, getattr(self.horde_manager, 'wave_count', 0) * 12.0)
                    enemy.boss_zone = (float(enemy.x), float(enemy.y), _bzr)
                except Exception:
                    pass
                try:
                    self._boss_dialogue(spawn_type)
                except Exception:
                    # v2.2.7 防御：BOSS对话触发异常不得中断本帧/卡死游戏
                    try:
                        self.state = GameState.PLAYING
                    except Exception:
                        pass
                # 尸潮规模提示
                scale_name = self.horde_manager.get_current_scale_name()
                scale_color = self.horde_manager.get_scale_color()
                self.floating_texts.append(FloatingText(
                    self.player.x, self.player.y - 80,
                    f"【{scale_name}】", color=scale_color, lifetime=3.0
                ))

        # 双人/联机：额外刷新频率（难度随玩家数调整）
        if self.is_multiplayer_active() and not _spawn_disabled:
            self._mp_spawn_timer = getattr(self, '_mp_spawn_timer', 0) + dt
            if self._mp_spawn_timer >= 0.35 and len(self.enemies) < max_enemies:
                self._mp_spawn_timer -= 0.35
                _extra = self.horde_manager.should_spawn()
                if _extra:
                    if isinstance(_extra, tuple):
                        _extra, _dv = _extra
                    _ang2 = random.uniform(0, math.pi * 2)
                    _dist2 = random.randint(400, 700)
                    _sc2 = self._next_spawn_center()
                    _sx, _sy = self.world.clamp_position(
                        _sc2.x + math.cos(_ang2) * _dist2,
                        _sc2.y + math.sin(_ang2) * _dist2, 20)
                    self.enemies.append(Enemy(_sx, _sy, _extra, 1, self.config.difficulty))

        # 更新敌人
        for enemy in self.enemies[:]:
            # v2.2.11 多人目标选择：所有存活玩家（P1~P4）取最近，倒地/升级暂停中不成为目标
            target_x = target_y = None
            target_obj = None
            _best_d = 1e18
            for _pp in self._all_players():
                # v2.5.6：升级选卡保护改为限时（见 _player_is_protected），
                # 超时后玩家会重新被怪物锁定，不再"停在升级界面永久无敌"
                _pf = self._player_is_protected(_pp)
                if _pf:
                    continue
                _d = (enemy.x - _pp.x) ** 2 + (enemy.y - _pp.y) ** 2
                # v2.5.4 低血玩家优先（狩猎残血）：血量越低权重越小 → 越优先成为目标
                _hp_r = max(0.0, min(1.0, getattr(_pp, 'hp', 100) / max(1, getattr(_pp, 'max_hp', 100))))
                _score = _d * (0.6 + 0.8 * _hp_r)
                if _score < _best_d:
                    _best_d = _score
                    target_x, target_y, target_obj = _pp.x, _pp.y, _pp
            if target_obj is None:
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

            # 光照系统更新（同步画质设置；lighting 可能因初始化失败为 None，防御跳过）
            if getattr(self, 'lighting', None) is not None:
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
                if getattr(self, 'lighting', None) is not None and getattr(self.lighting, 'quality', 'balanced') != 'performance':
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

            elif isinstance(result, dict) and result.get("type") in ("rock", "fire", "acid", "bomb", "curse"):
                # v2.0.14.1：RL 投掷物技能 → 复用怪物投掷物生成链路
                self._spawn_enemy_throwable(result)

            elif result == "boss_summon":
                # v2.0.14：RL 召唤技能
                for _ in range(2):
                    angle = random.uniform(0, math.pi * 2)
                    sx = enemy.x + math.cos(angle) * 80
                    sy = enemy.y + math.sin(angle) * 80
                    _e = Enemy(sx, sy, EnemyType.ZOMBIE_NORMAL, 1, self.config.difficulty)
                    if getattr(self, "ai_controller", None) is not None:
                        _e.ai_rl = self.ai_controller
                    self.enemies.append(_e)
                self.particles.spawn_explosion(enemy.x, enemy.y, DARK_GREEN, 24)
                if hasattr(self, "assets"):
                    self.assets.play_sound("boss_queen_summon")

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

            elif result == "boss_lockon":
                # v2.0.19 锁定必中：标记目标玩家，蓄力 0.9s 后必中高伤（不可闪避）
                if not hasattr(self, "boss_lock_marks"):
                    self.boss_lock_marks = []
                _tgt = None
                for _pl in self._alive_players():
                    if math.hypot(enemy.x - _pl.x, enemy.y - _pl.y) < 520:
                        _tgt = _pl
                        break
                if _tgt is not None:
                    self.boss_lock_marks.append([enemy, _tgt, 0.9])
                    self.floating_texts.append(FloatingText(_tgt.x, _tgt.y - 50, "⚠ 已被锁定!", color=(255, 50, 50), lifetime=0.9))
                    if hasattr(self, "assets"):
                        self.assets.play_sound("curse_cast")

            elif result == "boss_debuff":
                # v2.0.19 恶心人：减速+虚弱+诅咒（缴械等效=虚弱降伤害）
                for _pl in self._alive_players():
                    if math.hypot(enemy.x - _pl.x, enemy.y - _pl.y) < 380:
                        _pl.buff_manager.add_buff(BuffType.SLOW, duration=4.0)
                        _pl.buff_manager.add_buff(BuffType.WEAKEN, duration=4.0)
                        _pl.buff_manager.add_buff(BuffType.CURSE, duration=4.0)
                        self.floating_texts.append(FloatingText(_pl.x, _pl.y - 40, "被诅咒! 减速+虚弱", color=(160, 60, 220), lifetime=1.4))
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 30)
                if hasattr(self, "assets"):
                    self.assets.play_sound("curse_cast")

            elif result == "boss_elite_summon":
                # v2.0.19 特种召唤：1~2 只精英怪（brute/assassin/sorcerer/guardian 随机）
                _elites = [EnemyType.ELITE_BRUTE, EnemyType.ELITE_ASSASSIN,
                           EnemyType.ELITE_SORCERER, EnemyType.ELITE_GUARDIAN]
                _n = random.choice([1, 2])
                for _ in range(_n):
                    angle = random.uniform(0, math.pi * 2)
                    sx = enemy.x + math.cos(angle) * 90
                    sy = enemy.y + math.sin(angle) * 90
                    _e = Enemy(sx, sy, random.choice(_elites), 1, self.config.difficulty)
                    if getattr(self, "ai_controller", None) is not None:
                        _e.ai_rl = self.ai_controller
                    self.enemies.append(_e)
                self.particles.spawn_explosion(enemy.x, enemy.y, DARK_GREEN, 34)
                self.floating_texts.append(FloatingText(enemy.x, enemy.y - 40, "召唤精英护卫!", color=(120, 255, 120), lifetime=1.5))
                if hasattr(self, "assets"):
                    self.assets.play_sound("boss_queen_summon")

            elif result == "boss_heal":
                # v2.0.19 回血：恢复 25% 最大生命
                _heal = int(enemy.max_hp * 0.25)
                enemy.hp = min(enemy.max_hp, enemy.hp + _heal)
                self.particles.spawn_heal_particles(enemy.x, enemy.y, 20)
                self.floating_texts.append(FloatingText(enemy.x, enemy.y - 30, f"+{_heal} 回血!", color=GREEN, lifetime=1.5))

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
                # v2.8.1 修复：此区域此前缺 damage_timer 字段，
                # _update_smoke_zones 里 zone["damage_timer"] -= dt 直接抛
                # KeyError: 'damage_timer'（向某烟雾弹一命中就崩）。
                self.smoke_zones.append({
                    "x": self.player.x, "y": self.player.y,
                    "radius": 120, "timer": 5.0, "damage_timer": 0.0
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

            # 治疗僵尸治疗周围僵尸（v2.2.5：修复重置互踩 bug——enemy.update 不再提前重置，
            # 这里触发后统一重置；并新增持续范围回血光环）
            if getattr(enemy, "is_healer", False):
                # 持续光环：半径内僵尸平滑回血（等效 heal_amount/秒，按帧平滑）
                _per_sec = max(getattr(enemy, "heal_amount", 5), 1) / max(getattr(enemy, "heal_interval", 2.0), 0.5)
                for other in self.enemies:
                    if other is not enemy and other.alive and other.hp < other.max_hp:
                        dist = math.hypot(other.x - enemy.x, other.y - enemy.y)
                        if dist < enemy.heal_radius:
                            other.hp = min(other.max_hp, other.hp + _per_sec * dt)
                # 间隔脉冲治疗
                if enemy.heal_timer <= 0:
                    enemy.heal_timer = enemy.heal_interval
                    for other in self.enemies:
                        if other is not enemy and other.alive and other.hp < other.max_hp:
                            dist = math.hypot(other.x - enemy.x, other.y - enemy.y)
                            if dist < enemy.heal_radius:
                                other.hp = min(other.max_hp, other.hp + enemy.heal_amount * 2.0)

            # v2.4.0 boss 软性限制圈：出圈越远拉回越强（软性，圈内完全自由）
            _z = getattr(enemy, 'boss_zone', None)
            if _z and getattr(enemy, 'is_boss', False) and enemy.alive:
                _zx, _zy, _zr = _z
                _zd = math.hypot(enemy.x - _zx, enemy.y - _zy)
                if _zd > _zr:
                    _pull = min(1.0, (_zd - _zr) / max(50.0, _zr * 0.5))
                    _fx = (_zx - enemy.x) / _zd
                    _fy = (_zy - enemy.y) / _zd
                    enemy.x += _fx * 90.0 * _pull * dt
                    enemy.y += _fy * 90.0 * _pull * dt
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
        # v2.7.1：改为逐玩家执行（旧版只跑 self.player → P2 及后续玩家
        # 的钩爪飞行碰撞从不触发，表现为「P2 勾不到僵尸/道具/玩家」）
        self.update_grapple_collisions()

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
                _ht = getattr(getattr(proj, 'owner', None), 'team_id', 0)
                for enemy in self.enemies:
                    dist = math.hypot(enemy.x - proj.x, enemy.y - proj.y)
                    if dist < proj.explosion_radius:
                        damage = proj.damage * (1 - dist / proj.explosion_radius)
                        enemy._last_hit_team = _ht  # v2.4.0 击杀归属阵营（争分夺秒分阵营加时）
                        enemy._last_hit_player = getattr(proj, 'owner', None)  # v2.5.2 击杀归属玩家
                        enemy.take_damage(damage)
                        self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, damage))
                        if not enemy.alive:
                            self._on_enemy_death(enemy)
                # v2.2.7 PvPvE：爆炸对非队友玩家造成伤害
                if getattr(self.config, 'pvp_enabled', False):
                    for _pp in self._all_players():
                        if _pp is proj.owner or not getattr(_pp, 'alive', True) or getattr(_pp, 'downed', False):
                            continue
                        if getattr(_pp, 'team_id', 1) == getattr(proj.owner, 'team_id', 0):
                            continue
                        _d = math.hypot(_pp.x - proj.x, _pp.y - proj.y)
                        if _d < proj.explosion_radius:
                            _dmg = proj.damage * (1 - _d / proj.explosion_radius)
                            _pvp_d = self._pvp_dmg_to_player(_dmg, proj)
                            _pp.take_damage(_pvp_d, damage_type='ranged', attack_x=proj.x, attack_y=proj.y, bypass_dodge=True, source='player')
                            self.damage_numbers.append(DamageNumber(_pp.x, _pp.y, _pvp_d, color=RED))

            if not proj.alive:
                self.projectiles.remove(proj)
                continue

            # v2.2.7 PvPvE：投射物直接命中非队友玩家
            if getattr(self.config, 'pvp_enabled', False) and proj.owner is not None and proj.is_laser is False:
                for _pp in self._all_players():
                    if _pp is proj.owner or not getattr(_pp, 'alive', True) or getattr(_pp, 'downed', False):
                        continue
                    if getattr(_pp, 'team_id', 1) == getattr(proj.owner, 'team_id', 0):
                        continue
                    # v2.6.4 修复：检查是否已经命中过该玩家（穿透效果）
                    if _pp in proj.hits:
                        continue
                    # v2.5.6：扫掠碰撞（防高速弹丸穿透玩家）
                    if proj.swept_hit_rect(_pp.get_rect()):
                        proj.hits.append(_pp)
                        # v2.6.4 修复：只有当穿透次数用尽时才销毁子弹
                        if len(proj.hits) >= proj.pierce:
                            proj.alive = False
                        _pvp_d = self._pvp_dmg_to_player(proj.damage, proj)
                        _pp.take_damage(_pvp_d, damage_type='ranged', attack_x=proj.x, attack_y=proj.y, bypass_dodge=True, source='player')
                        self.damage_numbers.append(DamageNumber(_pp.x, _pp.y, _pvp_d, color=RED))
                        self._on_player_hit_by_projectile(_pp, proj)

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
                        enemy._last_hit_team = getattr(getattr(proj, 'owner', None), 'team_id', 0)  # v2.4.0
                        enemy._last_hit_player = getattr(proj, 'owner', None)  # v2.5.2 击杀归属玩家
                        enemy.take_damage(actual_damage)
                        self._apply_rune_elemental_on_hit(enemy, actual_damage)
                        self._vampire_heal(actual_damage, sx=enemy.x, sy=enemy.y)
                        self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, actual_damage, is_crit=is_crit, damage_type="ranged"))
                        self.particles.spawn(enemy.x, enemy.y, PURPLE, 5, (2, 5), (-3, 3), (0.2, 0.5))
                        if not enemy.alive:
                            self._on_enemy_death(enemy)
                # v2.5.5 激光武器 PvP：粗激光对敌对玩家同样造成伤害（轨道炮修复"激光不打玩家"）
                if getattr(self.config, 'pvp_enabled', False):
                    _lo = getattr(proj, 'owner', None)
                    if _lo is not None:
                        _lldx = proj.laser_end_x - proj.x
                        _lldy = proj.laser_end_y - proj.y
                        _lll = _lldx * _lldx + _lldy * _lldy
                        for _pp in self._all_players():
                            if _pp is _lo or not getattr(_pp, 'alive', True) or getattr(_pp, 'downed', False):
                                continue
                            if getattr(_pp, 'team_id', 1) == getattr(_lo, 'team_id', 0):
                                continue
                            _t2 = 0.0
                            if _lll > 0:
                                _t2 = max(0.0, min(1.0, ((_pp.x - proj.x) * _lldx + (_pp.y - proj.y) * _lldy) / _lll))
                            _clx = proj.x + _t2 * _lldx
                            _cly = proj.y + _t2 * _lldy
                            if math.hypot(_pp.x - _clx, _pp.y - _cly) < getattr(_pp, 'size', 20) + proj.laser_width:
                                _pvp_d = self._pvp_dmg_to_player(proj.damage, proj)
                                _pp.take_damage(_pvp_d, damage_type='ranged', attack_x=proj.x, attack_y=proj.y, bypass_dodge=True, source='player')
                                self.damage_numbers.append(DamageNumber(_pp.x, _pp.y, _pvp_d, color=RED))
                continue

            # v2.5.6：扫掠碰撞——按整段飞行路径判定命中，
            # 修复高速弹丸（AWM 34/帧、加特林弹幕、低帧率 dt=0.05）穿过目标导致碰撞事件丢失
            for enemy in self.enemies:
                if enemy in proj.hits:
                    continue
                if proj.swept_hit_rect(enemy.get_rect()):
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
                                    self._vampire_heal(actual_damage, sx=e.x, sy=e.y)
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
                    self._vampire_heal(actual_damage, sx=enemy.x, sy=enemy.y)
                    # v2.5.2 死神镰刀吃近战吸血（MELEE_LIFESTEAL）
                    if getattr(proj, "is_scythe_slash", False) and getattr(self.player, 'skill_tree', None):
                        _ls_skill = self.player.skill_tree.get_skill(SkillType.MELEE_LIFESTEAL)
                        if _ls_skill and _ls_skill.current_level > 0:
                            self.player.hp = min(self.player.max_hp, self.player.hp + actual_damage * _ls_skill.current_level * 0.1)
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
                # v2.5.6：扫掠碰撞（敌人投射物高速时同样可能穿过玩家）
                if proj.swept_hit_rect(_p.get_rect()):
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
        # v2.1.3：同屏双人经验球按距离磁吸到最近玩家，P1/P2 均可吸经验
        # （此前只吸 self.player，P2 永远吃不到经验）
        for orb in self.exp_orbs[:]:
            _targets = [self.player]
            if self.is_multiplayer_active() and self.player2 and getattr(self.player2, 'alive', True):
                _targets.append(self.player2)
            if len(_targets) > 1:
                _best = min(_targets, key=lambda _pl: math.hypot(orb.x - _pl.x, orb.y - _pl.y))
            else:
                _best = _targets[0]
            orb.update(dt, _best.x, _best.y, _best.pickup_range)
            if math.hypot(orb.x - _best.x, orb.y - _best.y) < 20:
                _best.gain_exp(orb.value)
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

        if getattr(self, 'particles', None) is not None:
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

        # 摄像机跟随（v2.5.0：钳制到有限地图界内）
        # v2.5.6：先同步视口尺寸（窗口缩放后玩家仍居中）
        self._sync_camera_viewports()
        _wbo = getattr(getattr(self, 'world', None), 'bounds', None)
        self.camera.follow(self.player.x, self.player.y, dt, bounds=_wbo)
        if self.player2:
            if self.camera2:
                self.camera2.follow(self.player2.x, self.player2.y, dt, bounds=_wbo)
            # v2.1.3：P2 升级选卡时暂停 P2 游戏进程（怪物已脱锁，选卡完成后恢复）
            if not (self.is_multiplayer_active() and getattr(self, '_upgrade_pause_player', None) == "P2"):
                self._update_player2(dt)
        # v2.2.7：3/4 号玩家（网络联机补位/AI 队友）更新
        for _i in (3, 4):
            _pn = getattr(self, f"player{_i}", None)
            _cam = getattr(self, f"camera{_i}", None)
            if _pn is not None and _cam is not None:
                _cam.follow(_pn.x, _pn.y, dt, bounds=_wbo)
                try:
                    self._update_ai_companion(_pn, dt)
                except Exception:
                    pass

        if self.is_multiplayer_active():
            # 双人/联机：救援系统——全部倒地才游戏结束
            # v2.8.0：不再立刻结算，先进死亡反应时间（慢放+镜头），给玩家反应余地
            # v2.8.8：合作模式下若仍有队友存活，则**不结算**，转为观战
            if self._update_rescue(dt):
                try:
                    if hasattr(self, 'update_spectate') and self.update_spectate(dt):
                        # 还有队友活着 → 进入观战，本局继续
                        pass
                    else:
                        self._begin_death_reaction()
                except Exception:
                    self._begin_death_reaction()
            else:
                try:
                    if hasattr(self, 'update_spectate'):
                        self.update_spectate(dt)
                except Exception:
                    pass
        elif self.player.hp <= 0:
            self._begin_death_reaction()
        # v2.2.0 争分夺秒：倒计时耗尽 → 挑战结算（非死亡）
        if self.config.game_mode == GameMode.TIMED and self.state == GameState.PLAYING:
            try:
                if self.horde_manager.is_timed_over():
                    self._settle_race_auto()
            except Exception:
                pass

    # ==================== v2.4.0 阵营胜负判定 ====================
    def _update_upgrade_pause(self, dt):
        """v2.5.6 升级选卡保护：
        1) 免伤/脱锁保护倒计时（仅开始的一小段时间）；
        2) 选卡超时自动选卡——杜绝"故意停在升级界面"无限吃无敌。
        """
        try:
            _tag = getattr(self, '_upgrade_pause_player', None)
            if not _tag:
                return
            _pl = self.player if _tag == "P1" else (self.player2 if _tag == "P2" else None)
            if _pl is None:
                self._upgrade_pause_player = None
                return
            # 1) 保护倒计时
            _g = getattr(_pl, "upgrade_grace_timer", 0.0)
            if _g > 0:
                _pl.upgrade_grace_timer = max(0.0, _g - dt)
            # 2) 超时自动选卡
            _t = getattr(self, '_upgrade_pause_timer', 0.0) - dt
            self._upgrade_pause_timer = max(0.0, _t)
            if _t > 0:
                return
            _cards = getattr(_pl, "skill_cards", None) or []
            if not _cards or not getattr(_pl, "pending_level_up", False):
                # 没有可选项：直接解除暂停（避免卡死）
                self._upgrade_pause_player = None
                _pl.upgrade_paused = False
                _pl.upgrade_grace_timer = 0.0
                return
            try:
                self.floating_texts.append(FloatingText(
                    _pl.x, _pl.y - 50, "升级超时，自动选择", color=(200, 200, 120), lifetime=1.6))
            except Exception:
                pass
            self._apply_skill_card(_cards[0])
        except Exception:
            pass

    # v2.5.6：多人争分夺秒每阵营只给 1 分钟（旧版 race_max_time=300s 太过充裕）
    TEAM_RACE_TIME = 60.0

    def _init_team_race(self):
        """争分夺秒：为每个阵营初始化独立计时器（阵营内共享；单人=单一阵营 0）

        v2.5.6：每阵营只给 1 分钟（击杀可加时，但最多攒到 1 分钟）"""
        if getattr(self, '_team_race_inited', False):
            return
        self._team_race_inited = True
        self.team_race = {}
        _init = float(self.TEAM_RACE_TIME)
        _teams = set()
        for _pp in self._all_players():
            if _pp is not None:
                _teams.add(getattr(_pp, 'team_id', 0))
        for _t in _teams or {0}:
            self.team_race[int(_t)] = {"time": float(_init), "out": False}

    def _team_race_add_time(self, team, amount):
        """分阵营加时（击杀归属阵营，上限 1 分钟）"""
        try:
            _init = float(self.TEAM_RACE_TIME)
            _tr = self.team_race.get(int(team))
            if _tr is not None:
                _tr["time"] = min(_init, _tr["time"] + max(0.0, float(amount)))
        except Exception:
            pass

    def _check_round_end(self, dt):
        """v2.4.0 阵营胜负判定（多人）：
        故事/无尽 PvPvE：只剩一个阵营有存活玩家 → 该阵营胜利；
        争分夺秒：每阵营独立计时（阵营内共享），计时尽或全灭 → 出局，最后一阵营胜利。
        返回胜利阵营 team_id（int）或 None（继续游戏）。"""
        if not self.is_multiplayer_active():
            return None
        _players = [p for p in self._all_players() if p is not None]
        if not _players:
            return None
        # v2.8.1 关键修复：合作模式（所有玩家同一阵营）不做『阵营胜负』判定。
        # 旧逻辑在争分夺秒下：合作时全场只有 team 0 一个阵营，
        # _active 长度恒为 1 → 开局第一帧就返回 0 判为"阵营 0 胜利"
        # → 立刻 GAME_OVER。这就是"合作模式争分夺秒一打开就结束"。
        # 阵营胜负只在真正多阵营（PvP）时有意义。
        _all_teams = {int(getattr(_pp, 'team_id', 0) or 0) for _pp in _players}
        if len(_all_teams) <= 1 and not getattr(self.config, 'pvp_enabled', False):
            return None
        _alive_teams = set()
        for _pp in _players:
            if getattr(_pp, 'alive', False) and not getattr(_pp, 'downed', False):
                _alive_teams.add(getattr(_pp, 'team_id', 0))
        if self.config.game_mode == GameMode.TIMED:
            if not getattr(self, '_team_race_inited', False):
                self._init_team_race()
            # 阵营计时递减 / 全灭出局
            for _t in list(getattr(self, 'team_race', {}).keys()):
                _tr = self.team_race[_t]
                if _t in _alive_teams and not _tr["out"]:
                    _tr["time"] = max(0.0, _tr["time"] - dt)
                    if _tr["time"] <= 0.0:
                        _tr["out"] = True
                elif _t not in _alive_teams:
                    _tr["out"] = True
            _active = [t for t, v in self.team_race.items() if not v["out"]]
            if len(_active) <= 1:
                return _active[0] if _active else None
            return None
        # 故事/无尽 PvP：只剩一个阵营存活 → 胜利
        if getattr(self.config, 'pvp_enabled', False):
            if len(_alive_teams) <= 1:
                return next(iter(_alive_teams), None)
        return None

    def _trigger_team_victory(self, team):
        """v2.4.0 阵营胜利结算：显示阵营胜利页面"""
        if self.state != GameState.PLAYING:
            return
        # v2.8.7：PvP/阵营胜利**此前完全不归档** —— 不冻结伤害日志、不保存回放，
        # 导致结算页「死亡详情」空白、「观看回放」无录像可用。
        # 现在与死亡路径统一走 finalize_replay()。
        try:
            if hasattr(self, 'finalize_replay'):
                self.finalize_replay(tag="victory")
        except Exception:
            pass
        self.victory_team = int(team or 0)
        self.victory_timer = 3.0
        # v2.5.2 多人胜利统计与成就（mp_first_win / mp_pvp_win / mp_team_win）
        try:
            if self.is_multiplayer_active() and getattr(self, 'records', None) is not None:
                self.records.add_mp_stat("mp_wins")
                if getattr(self.config, 'pvp_enabled', False):
                    self.records.add_mp_stat("mp_pvp_wins")
                else:
                    _tm = self.records.data["achievements"].get("mp_team_win")
                    if _tm and not _tm.get("unlocked", False):
                        import datetime as _dt
                        _tm["unlocked"] = True
                        _tm["date"] = _dt.datetime.now().isoformat()
                        self.records._save()
        except Exception:
            pass
        try:
            if self.config.game_mode == GameMode.TIMED:
                self._record_race_result(victory=True)
            if self.session:
                self.session.end_session(victory=True)
                _unlocks = self.session.finalize() or []
                for _k in _unlocks:
                    _ad = self.records.data["achievements"].get(_k)
                    if _ad:
                        self.ach_toast_queue.append({"key": _k, "desc": _ad["desc"], "timer": 4.0})
            self.session = None
        except Exception:
            pass
        self.assets.play_music("gameover")
        self.delete_saved_game()
        self.state = GameState.GAME_OVER

    # ==================== 争分夺秒结算（v2.2.0） ====================
    def _record_race_result(self, victory=True):
        """争分夺秒：写入排行榜 + 达标金币奖励 + 成就（含多人模式全体生效）"""
        try:
            if self.config.game_mode != GameMode.TIMED:
                return
            if getattr(self, '_race_recorded', False):
                return
            self._race_recorded = True
            score = getattr(self.player, 'score', 0)
            if self.player2 is not None:
                score = max(score, getattr(self.player2, 'score', 0))
            time_left = getattr(self.horde_manager, 'race_time_left', 0.0)
            kills = 0
            if self.session:
                kills = sum(self.session.data.get("kills_by_type", {}).values())
            coins = self.records.record_race_result(score, time_left, kills, victory)
            if coins > 0:
                # 金币奖励到账提示（双人全体）
                txt = f"争分夺秒达标奖励 +{coins} 金币!"
                self.floating_texts.append(FloatingText(
                    self.player.x, self.player.y - 60, txt, color=GOLD, lifetime=2.5))
                if self.player2 is not None:
                    self.floating_texts.append(FloatingText(
                        self.player2.x, self.player2.y - 60, txt, color=GOLD, lifetime=2.5))
        except Exception:
            pass

    def _settle_race_auto(self):
        """倒计时耗尽：挑战失败（游戏失败结算页）

        v2.5.6：旧版把"倒计时归零"当成挑战成功（victory=True），
        甚至会跳到结局页面——语义完全错了。倒计时归零 = 失败。
        """
        if self.state != GameState.PLAYING:
            return
        self._record_race_result(victory=False)
        self._trigger_multiplayer_game_over(victory=False,
                                            title="挑战失败！时间耗尽")

    def _settle_race_manual(self):
        """玩家主动结算关卡（键盘 K / HUD 按钮）→ 挑战完成（成功结算）"""
        if self.config.game_mode != GameMode.TIMED or self.state != GameState.PLAYING:
            return
        if self.state != GameState.PLAYING:
            return
        self._record_race_result(victory=True)
        if self.session:
            try:
                self.session.end_session(victory=True)
            except Exception:
                pass
        self._trigger_multiplayer_game_over(victory=True, title="挑战完成！")

    def _trigger_multiplayer_game_over(self, victory=False, title=None):
        """触发游戏结束结算（单/双人共用）

        v2.5.6：新增 victory / title 参数——争分夺秒倒计时结束 = 失败，
        主动结算 = 完成，结局页只属于故事模式通关流程。
        """
        if self.state != GameState.PLAYING:
            return
        self.result_title = title
        # v2.5.6：清理蓄力预瞄状态（避免结算页仍残留预瞄线）
        try:
            for _p in self._all_players():
                if _p is not None:
                    _p._awm_saved = None
        except Exception:
            pass
        # 单人模式：正常游戏结束
        if self.session:
            # v2.2.0 争分夺秒：主动结算视为挑战完成；倒计时耗尽视为失败
            if victory:
                try:
                    self.session.end_session(victory=True)
                except Exception:
                    pass
            else:
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

        # v2.5.6：争分夺秒倒计时结束 = 挑战失败 → 停留在「游戏失败」结算页，
        # 不再跳到结局页面（结局抉择只属于故事模式通关流程）
        if self.config.game_mode == GameMode.TIMED:
            pass
        elif self.horde_manager.is_timed_over():
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

    def _on_player_hit_by_projectile(self, p, proj):
        """v2.2.7 PvPvE：玩家被玩家投射物命中时的反馈"""
        try:
            self.floating_texts.append(FloatingText(
                p.x, p.y - 40, f"被 {getattr(proj.owner, 'name', '对方')} 击中!", color=RED, lifetime=1.0))
            if hasattr(p, 'invincible_timer'):
                p.invincible_timer = max(getattr(p, 'invincible_timer', 0), 0.3)
        except Exception:
            pass

    def _damage_player_target(self, target, damage, damage_type="melee", attack_x=0, attack_y=0):
        """对玩家目标造成伤害（单人模式只有本地玩家）"""
        if target.get("obj") is not None:
            target["obj"].take_damage(damage, damage_type=damage_type, attack_x=attack_x, attack_y=attack_y)

    def _update_grapple_collision(self):
        # v2.7.1 委托给通用实现（以 player 为参数），旧名保留以兼容其它调用点。
        # 通用实现见 mix_players.PlayerRegistryMixin._update_grapple_collision_for
        return self._update_grapple_collision_for(self.player)

        # v2.2.12 直拉模式：长按未锁定钩爪不勾取路径上任何僵尸/道具，
        # 直接飞向锚点后自我拉拽（碰撞勾取整体跳过，齿轮 _update_grapple 处理到点 self_pull）
        if getattr(self.player.riot_gear, 'grapple_direct_pull', False):
            return
        """更新钩爪碰撞检测 - 敌人/道具/经验球/文本资料/宝箱全部可勾
        v2.2.5：新增自我拉拽沿途伤害 / 锁定目标直飞 / 拉敌撞击词条"""
        rg = self.player.riot_gear
        if not rg.grapple_active:
            return

        # ===== v2.2.5 自我拉拽状态：沿途伤害处理（每帧调用） =====
        if rg.grapple_state == "self_pull":
            _p = self.player
            # 死神钩爪：沿途旋转挥舞镰刀造成范围伤害（间隔 ticks）+ 旋转刀光特效
            if getattr(rg, "grapple_is_scythe", False):
                rg.grapple_swing_timer -= self.dt if hasattr(self, "dt") else 1 / 60
                if rg.grapple_swing_timer <= 0:
                    rg.grapple_swing_timer = rg.grapple_swing_interval
                    _swing_r = 85
                    for e in self.enemies:
                        if not e.alive:
                            continue
                        d = math.hypot(e.x - _p.x, e.y - _p.y)
                        if d < _swing_r + getattr(e, "size", 20):
                            e.take_damage(35)
                            self.damage_numbers.append(DamageNumber(e.x, e.y, 35, color=(210, 130, 255)))
                            # 击退
                            if hasattr(e, "knockback_x"):
                                _a = math.atan2(e.y - _p.y, e.x - _p.x)
                                e.knockback_x = math.cos(_a) * 90
                                e.knockback_y = math.sin(_a) * 90
                    # 旋转刀光特效（环绕整圆）
                    self.slash_arcs.append(SlashArc(
                        _p.x, _p.y, _p.facing_angle, _swing_r, (200, 120, 255),
                        lifetime=0.22, kind="scythe", start_radius=_swing_r * 0.6,
                        end_angle_offset=4.8))
            else:
                # 普通钩爪自我拉拽：无范围伤害，仅免伤（gear 已刷新无敌）
                pass
            return

        # ===== v2.2.5 拉敌撞击词条：被拉回敌人沿途撞击其他敌人造成伤害 =====
        if rg.grapple_state == "pulling" and rg.grapple_target is not None \
                and getattr(rg.grapple_target, "alive", False):
            _gt = rg.grapple_target
            _impact = getattr(rg, "_grapple_impact_damage", 25)
            for e2 in self.enemies:
                if e2 is _gt or not e2.alive:
                    continue
                if id(e2) in rg.grapple_pull_impact_hit:
                    continue
                if math.hypot(e2.x - _gt.x, e2.y - _gt.y) < getattr(e2, "size", 20) + getattr(_gt, "size", 20):
                    rg.grapple_pull_impact_hit.add(id(e2))
                    e2.take_damage(_impact)
                    self.damage_numbers.append(DamageNumber(e2.x, e2.y, _impact, color=ORANGE))
                    if hasattr(e2, "knockback_x"):
                        _a = math.atan2(e2.y - _gt.y, e2.x - _gt.x)
                        e2.knockback_x = math.cos(_a) * 120
                        e2.knockback_y = math.sin(_a) * 120

        if rg.grapple_state != "shooting":
            return

        head_pos = rg.grapple_head_pos
        if not head_pos:
            return

        grapple_skill = self.player.skill_tree.get_skill(SkillType.GRAPPLE_PULL)
        grapple_lvl = grapple_skill.current_level if grapple_skill else 1

        # ===== v2.2.5 锁定目标直飞：无视沿途其他可勾取物，只检测锁定目标 =====
        _locked = rg.grapple_target
        if _locked is not None and getattr(_locked, "alive", False) \
                and not getattr(_locked, "is_boss", False):
            dist = math.hypot(_locked.x - head_pos[0], _locked.y - head_pos[1])
            if dist < getattr(_locked, "size", 20) + 12:
                if hasattr(_locked, "take_damage"):
                    base_dmg = 15 + grapple_lvl * 10
                    _locked.take_damage(base_dmg)
                    self.damage_numbers.append(DamageNumber(_locked.x, _locked.y, base_dmg, color=ORANGE))
                    rg._grapple_impact_damage = base_dmg
                    # 4级以上眩晕
                    if grapple_lvl >= 4:
                        _locked.apply_buff(BuffType.STUN, duration=1.0)
                    rg.set_grapple_target(_locked)
                    rg.grapple_state = "hit"
                    rg.grapple_hit_stun_timer = rg.grapple_hit_stun_duration
                    _locked.grappled = True
                    self.floating_texts.append(FloatingText(
                        _locked.x, _locked.y - 30, "锁定直飞!", color=(200, 120, 255), lifetime=1.0
                    ))
                else:
                    # v2.2.7 锁定特殊道具：与僵尸拉回一致（钩爪线拉回，非磁吸）
                    rg.set_grapple_target(_locked)
                    rg.grapple_state = "pulling"
                    rg._pulling_timer = 0.0
                    self.floating_texts.append(FloatingText(
                        _locked.x, _locked.y - 30, "勾取道具!", color=(120, 230, 140), lifetime=1.0
                    ))
                return

        # 检测钩爪头与敌人的碰撞
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = math.hypot(enemy.x - head_pos[0], enemy.y - head_pos[1])
            if dist < enemy.size + 12:
                # 钩爪伤害
                base_dmg = 15 + grapple_lvl * 10
                enemy.take_damage(base_dmg)
                rg._grapple_impact_damage = base_dmg
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

        # 检测世界道具 - v2.2.7 与僵尸拉回一致（钩爪线拉回，非磁吸）
        for item in self.world.items:
            if not item.alive:
                continue
            dist = math.hypot(item.x - head_pos[0], item.y - head_pos[1])
            if dist < item.size + 12:
                rg.set_grapple_target(item)
                rg.grapple_state = "pulling"
                rg._pulling_timer = 0.0
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
