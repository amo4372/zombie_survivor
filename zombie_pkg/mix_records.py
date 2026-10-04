# -*- coding: utf-8 -*-
"""RecordsMixin - 由 game.py 自动拆分，逻辑等价"""

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

class RecordsMixin:
    def save_game_state(self):
        """保存当前对局状态到文件（退出时自动调用）"""
        import json
        try:
            if self.state != GameState.PLAYING or self.player is None:
                return False
            save_data = {
                "game_mode": self.config.game_mode.name if hasattr(self.config.game_mode, 'name') else str(self.config.game_mode),
                "difficulty": self.config.difficulty,
                "player_x": self.player.x,
                "player_y": self.player.y,
                "player_hp": self.player.hp,
                "player_max_hp": self.player.max_hp,
                "player_level": self.player.level,
                "player_exp": self.player.exp,
                "player_score": getattr(self.player, 'score', 0),
                "has_vaccine": self.has_vaccine,
                "total_time": self.horde_manager.total_time if self.horde_manager else 0,
                "horde_count": self.horde_manager.horde_count if self.horde_manager else 0,
                "horde_active": self.horde_manager.horde_active if self.horde_manager else False,
                "horde_timer": self.horde_manager.timer if self.horde_manager else 0,
                "horde_scale": self.horde_manager.current_scale if self.horde_manager else 1,
                "boss_guaranteed": self.horde_manager.boss_guaranteed if self.horde_manager else False,
                "boss_spawned_this_horde": self.horde_manager.boss_spawned_this_horde if self.horde_manager else False,
                "vaccine_boss_spawned": self.horde_manager.vaccine_boss_spawned if self.horde_manager else False,
                "boss_queue_remaining": [b.name for b in self.horde_manager.boss_queue] if (self.horde_manager and getattr(self.horde_manager, 'boss_queue', None)) else [],
                "endless_glitch_shown": self.horde_manager.endless_glitch_shown if self.horde_manager else False,
                "endless_countdown_left": self.horde_manager.endless_countdown_left if self.horde_manager else 90,
                "map_time_elapsed": getattr(self, 'map_time_elapsed', 0),
                "special_event_triggered": getattr(self, 'special_event_triggered', False),
                "story_collected": list(getattr(self, 'story_collected_fragments', [])),
                "current_map_index": getattr(self, 'current_map_index', 0),
                "weapons": [w.weapon_type.name if hasattr(w.weapon_type, 'name') else str(w.weapon_type) 
                           for w in self.player.weapons],
                "current_weapon_idx": getattr(self.player, "current_weapon_idx", 0),
                "weapon_ammo": {w.weapon_type.name if hasattr(w.weapon_type, 'name') else str(w.weapon_type): 
                               getattr(w, 'current_ammo', None) for w in self.player.weapons},
                "skill_tree": self._serialize_skill_tree(),
                "skill_slot_count": getattr(self.player, 'skill_slot_count', 3),
                "throwables": getattr(self.player, 'throwables', {}),
                "selected_throwable": getattr(self, 'selected_throwable', 'incendiary'),
                "riot_gear": {
                    "equipped": self.player.riot_gear.equipped,
                    "stamina": self.player.riot_gear.stamina,
                    "viewing_window_hp": self.player.riot_gear.viewing_window_hp,
                    "shield_broken": self.player.riot_gear.shield_broken,
                    "equip_cooldown": getattr(self.player, 'riot_gear_cooldown', 0),
                    "adrenaline_level": self.player.riot_gear.adrenaline_level,
                },
                "active_buffs": self._serialize_active_buffs(),
                "enemies": self._serialize_enemies(),
                "save_time": __import__('datetime').datetime.now().isoformat(),
            }
            # 加密保存（多层加密）
            json_bytes = json.dumps(save_data, ensure_ascii=False, indent=2).encode('utf-8')
            encrypted = _save_encrypt(json_bytes)
            with open(self.savegame_path, "wb") as f:
                f.write(encrypted)
            # 删除旧的明文存档（如果存在）
            import os
            if os.path.exists(self.savegame_json_path):
                try:
                    os.remove(self.savegame_json_path)
                except:
                    pass
            logger.info(f"对局状态已加密保存 ({len(json_bytes)}B -> {len(encrypted)}B)")
            return True
        except Exception as e:
            logger.log_exception(e)
            return False

    def _serialize_skill_tree(self):
        """序列化技能树（技能等级+技能点）"""
        try:
            skills = {}
            st = self.player.skill_tree
            for skill in st.skills:
                skills[skill.skill_type.name if hasattr(skill.skill_type, 'name') else str(skill.skill_type)] = skill.current_level
            return {
                "levels": skills,
                "skill_points": st.skill_points,
                "pending_level_up": getattr(self.player, 'pending_level_up', False),
            }
        except Exception as e:
            logger.log_exception(e)
            return {"levels": {}, "skill_points": 0, "pending_level_up": False}

    def _serialize_active_buffs(self):
        """序列化玩家当前激活的buff"""
        try:
            buffs = []
            bm = self.player.buff_manager
            active = getattr(bm, 'active_buffs', getattr(bm, 'buffs', {}))
            if isinstance(active, dict):
                for btype, buff in active.items():
                    buffs.append({
                        "type": btype.name if hasattr(btype, 'name') else str(btype),
                        "duration": getattr(buff, 'duration', 0),
                        "stacks": getattr(buff, 'stacks', 1),
                        "value": getattr(buff, 'value', None),
                    })
            elif isinstance(active, list):
                for buff in active:
                    btype = getattr(buff, 'buff_type', getattr(buff, 'type', None))
                    buffs.append({
                        "type": btype.name if hasattr(btype, 'name') else str(btype) if btype else "unknown",
                        "duration": getattr(buff, 'duration', 0),
                        "stacks": getattr(buff, 'stacks', 1),
                        "value": getattr(buff, 'value', None),
                    })
            return buffs
        except:
            return []

    def _serialize_enemies(self):
        """序列化当前场上的敌人（僵尸+Boss）"""
        try:
            enemies_data = []
            for enemy in getattr(self, 'enemies', []):
                if not getattr(enemy, 'alive', True):
                    continue
                etype = enemy.enemy_type
                enemies_data.append({
                    "type": etype.name if hasattr(etype, 'name') else str(etype),
                    "x": enemy.x,
                    "y": enemy.y,
                    "hp": enemy.hp,
                    "wave": getattr(enemy, 'wave', 1),
                    "difficulty": getattr(enemy, 'difficulty', 'normal'),
                    "split_count": getattr(enemy, 'split_count', 0),
                    "is_boss": getattr(enemy, 'is_boss', False),
                    "is_elite": getattr(enemy, 'is_elite', False),
                    "special_windup_timer": getattr(enemy, 'special_windup_timer', 0),
                    "special_windup_type": getattr(enemy, 'special_windup_type', None),
                    "special_windup_radius": getattr(enemy, 'special_windup_radius', 0),
                })
            return enemies_data
        except Exception as e:
            logger.log_exception(e)
            return []

    def has_saved_game(self):
        """检查是否存在存档（优先加密存档，兼容明文旧存档）"""
        import os
        return os.path.exists(self.savegame_path) or os.path.exists(self.savegame_json_path)

    def load_game_state(self):
        """加载存档并开始游戏（从存档恢复）"""
        import json
        try:
            if not self.has_saved_game():
                return False
            import os
            # 优先加载加密存档，兼容明文旧存档
            if os.path.exists(self.savegame_path):
                with open(self.savegame_path, "rb") as f:
                    encrypted = f.read()
                try:
                    decrypted = _save_decrypt(encrypted)
                    save_data = json.loads(decrypted.decode('utf-8'))
                    logger.info("加密存档解密成功")
                except Exception as e:
                    logger.log_exception(e)
                    logger.error("加密存档解密失败，尝试明文存档")
                    if os.path.exists(self.savegame_json_path):
                        with open(self.savegame_json_path, "r", encoding="utf-8") as f:
                            save_data = json.load(f)
                    else:
                        return False
            else:
                # 明文旧存档
                with open(self.savegame_json_path, "r", encoding="utf-8") as f:
                    save_data = json.load(f)
                logger.info("加载明文旧存档")
            
            # 恢复模式和难度
            mode_name = save_data.get("game_mode", "ENDLESS")
            from config import GameMode, SkillType, WeaponType
            self.config.game_mode = getattr(GameMode, mode_name, GameMode.ENDLESS)
            self.config.difficulty = save_data.get("difficulty", "普通")
            
            # 开始游戏
            self.start_game()
            
            # 恢复玩家状态
            self.player.x = save_data.get("player_x", 0)
            self.player.y = save_data.get("player_y", 0)
            self.player.hp = save_data.get("player_hp", self.player.max_hp)
            self.player.max_hp = save_data.get("player_max_hp", self.player.max_hp)
            self.player.level = save_data.get("player_level", 1)
            self.player.exp = save_data.get("player_exp", 0)
            self.player.score = save_data.get("player_score", 0)
            self.has_vaccine = save_data.get("has_vaccine", False)

            # 恢复技能槽数量
            self.player.skill_slot_count = save_data.get("skill_slot_count", 3)

            # 恢复投掷物
            self.player.throwables = save_data.get("throwables", {})
            self.selected_throwable = save_data.get("selected_throwable", "incendiary")

            # 恢复时间和尸潮状态
            if self.horde_manager:
                self.horde_manager.total_time = save_data.get("total_time", 0)
                self.horde_manager.horde_count = save_data.get("horde_count", 0)
                self.horde_manager.horde_active = save_data.get("horde_active", False)
                self.horde_manager.timer = save_data.get("horde_timer", 0)
                self.horde_manager.current_scale = save_data.get("horde_scale", 1)
                self.horde_manager.boss_guaranteed = save_data.get("boss_guaranteed", False)
                self.horde_manager.boss_spawned_this_horde = save_data.get("boss_spawned_this_horde", False)
                self.horde_manager.vaccine_boss_spawned = save_data.get("vaccine_boss_spawned", False)
                # 恢复 boss 队列（保证每个Boss全局只出现一次，重启不重复）
                q_names = save_data.get("boss_queue_remaining", [])
                if q_names:
                    from config import EnemyType
                    _by_name = {e.name: e for e in EnemyType}
                    self.horde_manager.boss_queue = [_by_name.get(n) for n in q_names if _by_name.get(n) is not None]
                self.horde_manager.endless_glitch_shown = save_data.get("endless_glitch_shown", False)
                self.horde_manager.endless_countdown_left = save_data.get("endless_countdown_left", 90)
            # 恢复故事模式地图时间和事件状态
            self.map_time_elapsed = save_data.get("map_time_elapsed", 0)
            self.special_event_triggered = save_data.get("special_event_triggered", False)
            self.special_event_active = False
            collected = save_data.get("story_collected", [])
            if collected:
                self.story_collected_fragments = set(collected)

            # 恢复故事模式地图
            if self.config.game_mode == GameMode.STORY:
                map_idx = save_data.get("current_map_index", 0)
                self.current_map_index = map_idx
                from config import STORY_MAP_ORDER, MAP_CONFIGS
                if map_idx < len(STORY_MAP_ORDER):
                    self.current_map = STORY_MAP_ORDER[map_idx]
                    self.map_config = MAP_CONFIGS[self.current_map]
                    self.world = GameWorld(map_type=self.current_map)

            # 恢复武器
            weapon_names = save_data.get("weapons", [])
            if weapon_names:
                self.player.weapons = []
                for wname in weapon_names:
                    wtype = getattr(WeaponType, wname, WeaponType.PISTOL)
                    self.player.add_weapon(wtype)
                self.player.current_weapon_idx = save_data.get("current_weapon_idx", 0)
            # 恢复武器弹药
            weapon_ammo = save_data.get("weapon_ammo", {})
            for w in self.player.weapons:
                wname = w.weapon_type.name if hasattr(w.weapon_type, 'name') else str(w.weapon_type)
                if wname in weapon_ammo and weapon_ammo[wname] is not None:
                    w.current_ammo = weapon_ammo[wname]

            # 恢复技能等级、技能点、待升级状态
            skill_data = save_data.get("skill_tree", {})
            # 兼容旧格式：直接是等级字典
            if isinstance(skill_data, dict) and "levels" in skill_data:
                skill_levels = skill_data.get("levels", {})
                self.player.skill_tree.skill_points = skill_data.get("skill_points", 0)
                self.player.pending_level_up = skill_data.get("pending_level_up", False)
            else:
                skill_levels = skill_data
            for sname, level in skill_levels.items():
                try:
                    stype = getattr(SkillType, sname)
                    skill = self.player.skill_tree.get_skill(stype)
                    if skill:
                        skill.current_level = level
                except:
                    pass
            # 如果有待升级，重新生成技能卡
            if getattr(self.player, 'pending_level_up', False):
                try:
                    self.player.skill_cards = self.player.skill_tree.get_random_skill_cards(
                        getattr(self.player, 'skill_slot_count', 3),
                        current_weapon=self.player.get_current_weapon())
                    # 解锁全局技能树（三选一出现过就算）
                    for sc in self.player.skill_cards:
                        if hasattr(sc, 'skill_type'):
                            skill_tree_unlock_manager.unlock_skill(sc.skill_type)
                        elif hasattr(sc, 'type'):
                            skill_tree_unlock_manager.unlock_skill(sc.type)
                except:
                    self.player.pending_level_up = False
            # 应用肾上腺素被动效果
            ad_skill = self.player.skill_tree.get_skill(SkillType.ADRENALINE)
            if ad_skill:
                self.player.riot_gear.adrenaline_level = ad_skill.current_level
            # 检查组合技（加载存档后）
            self._check_combos()

            # 恢复防爆套装状态
            rg_data = save_data.get("riot_gear", {})
            if rg_data:
                self.player.riot_gear.adrenaline_level = rg_data.get("adrenaline_level", 0)
                if rg_data.get("equipped", False):
                    self.player.riot_gear.equip()
                self.player.riot_gear.stamina = rg_data.get("stamina", self.player.riot_gear.max_stamina)
                self.player.riot_gear.viewing_window_hp = rg_data.get("viewing_window_hp", self.player.riot_gear.max_viewing_window_hp)
                self.player.riot_gear.shield_broken = rg_data.get("shield_broken", False)
                self.player.riot_gear_cooldown = rg_data.get("equip_cooldown", 0)

            # 恢复激活的buff
            active_buffs = save_data.get("active_buffs", [])
            for bd in active_buffs:
                try:
                    btype = getattr(BuffType, bd["type"], None)
                    if btype:
                        self.player.buff_manager.add_buff(btype, duration=bd.get("duration", 5), stacks=bd.get("stacks", 1))
                        if bd.get("value") is not None:
                            buff = self.player.buff_manager.get_buff(btype)
                            if buff:
                                buff.value = bd["value"]
                except:
                    pass
            
            # 恢复敌人（僵尸+Boss）
            enemies_data = save_data.get("enemies", [])
            if enemies_data:
                from entities import Enemy
                from config import EnemyType
                self.enemies = []
                for ed in enemies_data:
                    try:
                        etype = getattr(EnemyType, ed["type"], None)
                        if etype is None:
                            continue
                        enemy = Enemy(
                            ed["x"], ed["y"], etype,
                            ed.get("wave", 1),
                            ed.get("difficulty", self.config.difficulty)
                        )
                        enemy.hp = ed.get("hp", enemy.max_hp)
                        enemy.split_count = ed.get("split_count", 0)
                        enemy.special_windup_timer = ed.get("special_windup_timer", 0)
                        enemy.special_windup_type = ed.get("special_windup_type", None)
                        enemy.special_windup_radius = ed.get("special_windup_radius", 0)
                        self.enemies.append(enemy)
                        try:
                            _cu = codex_unlock_manager.unlock_monster(enemy.enemy_type.name if hasattr(enemy, "enemy_type") else enemy.type.name)
                            if _cu:
                                self._codex_unlock_toast(_cu, enemy.enemy_type.name if hasattr(enemy, "enemy_type") else enemy.type.name)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.log_exception(e)
                        continue
                logger.info(f"已恢复 {len(self.enemies)} 个敌人")

            logger.info(f"存档已加载，模式: {mode_name}, 时间: {save_data.get('total_time', 0):.0f}s")
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 60, 
                "对局已恢复！", color=GREEN, lifetime=3.0))
            return True
        except Exception as e:
            logger.log_exception(e)
            return False

    def delete_saved_game(self):
        """删除存档（游戏结束时调用）- 同时删除加密和明文存档"""
        import os
        for save_file in [self.savegame_path, self.savegame_json_path]:
            try:
                if os.path.exists(save_file):
                    os.remove(save_file)
            except:
                pass

    def _unlock_achievement(self, key):
        """即时解锁成就并显示提示（实时弹窗toast + 浮字）"""
        if self.records and self.records.unlock_achievement(key):
            ach = self.records.get_achievements().get(key, {})
            desc = ach.get("desc", key)
            # 实时弹出成就toast（右上角弹窗）
            try:
                self.ach_toast_queue.append({"key": key, "name": desc, "desc": desc,
                                            "timer": 4.0, "kind": "ach", "born": time.time()})
            except Exception:
                pass
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 60,
                f"成就解锁: {desc}", color=GOLD, lifetime=4.0))
            logger.info(f"成就解锁: {key} - {desc}")

    def _check_achievements_realtime(self):
        """游戏中实时结算成就（不等到游戏结束），达标即解锁+实时弹出"""
        if not hasattr(self, 'records') or self.records is None:
            return
        try:
            rd = self.records.data
            ach = rd.get("achievements", {})
            d = self.session.data if (self.session is not None) else {}
            game_coef = self.records.calculate_achievement_coefficient(d)
            # 本局存活时间
            try:
                from datetime import datetime as _dt
                time_survived = int((_dt.now() - self.session.start_time).total_seconds()) if self.session is not None else 0
            except Exception:
                time_survived = int(getattr(self, 'map_time_elapsed', 0) or 0)
            tk = rd.get("total_kills", 0)
            td = rd.get("total_deaths", 0)
            kb = rd.get("kills_by_type", {})
            boss_total = kb.get("boss_long", 0) + kb.get("boss_xiang", 0)
            su = rd.get("skill_usage", {})
            dkills = sum(d.get("kills_by_type", {}).values())

            def cond(key, ok):
                try:
                    item = ach.get(key, {})
                    if not ok or item.get("unlocked", False):
                        return
                    thr = item.get("coef_threshold", 0)
                    if thr > 0 and game_coef < thr:
                        return
                    self._unlock_achievement(key)
                except Exception:
                    pass

            # 击杀
            cond("first_blood", tk >= 1)
            cond("zombie_slayer", tk >= 100)
            cond("zombie_hunter", tk >= 1000)
            cond("zombie_destroyer", tk >= 10000)
            # 存活
            cond("survivor", time_survived >= 300)
            cond("veteran", time_survived >= 900)
            cond("legend", time_survived >= 1800)
            # 死亡
            cond("die_1", td >= 1); cond("die_10", td >= 10)
            cond("die_100", td >= 100); cond("die_1000", td >= 1000); cond("die_10000", td >= 10000)
            # 技能/武器
            cond("skill_master", d.get("skills_upgraded", 0) >= 20)
            cond("weapon_collector", d.get("weapons_collected", 0) >= 13)
            # Boss
            cond("boss_slayer", boss_total >= 10)
            cond("dragon_hunter", kb.get("boss_long", 0) >= 5)
            cond("xiang_hunter", kb.get("boss_xiang", 0) >= 5)
            # 战斗/累计
            cond("shield_master", rd.get("total_shield_blocks", 0) >= 100)
            cond("grapple_master", rd.get("total_grapples", 0) >= 50)
            cond("berserker", su.get("berserk", 0) >= 10)
            cond("centurion", dkills >= 100)
            cond("crit_master", rd.get("total_critical_hits", 0) >= 500)
            cond("damage_deal_500k", rd.get("total_damage_dealt", 0) >= 500000)
            cond("gunner", rd.get("total_shots_fired", 0) >= 10000)
            cond("tough_guy", rd.get("total_damage_taken", 0) >= 200000)
            # 尸潮
            cond("horde_survivor_5", rd.get("total_horde_survived", 0) >= 5)
            cond("horde_survivor_20", rd.get("total_horde_survived", 0) >= 20)
            # 本局
            cond("turret_master", d.get("turrets_deployed", 0) >= 10)
            cond("chest_opener", d.get("chests_opened", 0) >= 5)
            cond("ice_sculptor", d.get("enemies_frozen", 0) >= 30)
            cond("poison_master", d.get("poison_kills", 0) >= 30)
            cond("purifier", su.get("purify", 0) >= 10)
            cond("war_crier", d.get("war_cry_kills", 0) >= 50)
            # 元素/隐藏
            cond("elemental_master", d.get("has_flame_enchant", False) and d.get("has_frost_enchant", False) and d.get("has_poison_enchant", False))
            cond("fire_and_ice", d.get("has_flame_enchant", False) and d.get("has_frost_enchant", False))
            cond("debuff_collector", d.get("max_debuffs_at_once", 0) >= 5)
            cond("burning_survivor", d.get("burning_survive_time", 0) >= 60)
            cond("bleeding_warrior", d.get("bleeding_kills", 0) >= 20)
            # 地狱铁人
            cond("iron_will", d.get("difficulty") == "地狱" and time_survived >= 480)
        except Exception as e:
            logger.log_exception(e)

    def _save_collected_texts(self):
        """保存已收集的文本资料到文件"""
        import json
        try:
            save_path = "collected_texts.json"
            data = {"collected": list(self.collected_texts)}
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_collected_texts(self):
        """从文件加载已收集的文本资料"""
        import json
        try:
            save_path = "collected_texts.json"
            with open(save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.collected_texts = set(data.get("collected", []))
        except Exception:
            self.collected_texts = set()

    def _apply_item_effect(self, item_type):
        """应用特殊道具效果"""
        # 记录道具收集
        if self.session:
            self.session.add_item_collected()
        # 播放拾取音效
        self.assets.play_sound("pickup_item")
        # 兼容int类型（客户端同步过来的）
        if isinstance(item_type, int):
            try:
                item_type = ItemType(item_type)
            except:
                pass
        if item_type == ItemType.VACCINE:
            self.has_vaccine = True
            if self.session:
                self.session.set_got_vaccine(True)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "获得疫苗！", color=GREEN, lifetime=3.0))
        elif item_type == ItemType.HEALTH_PACK:
            self.player.heal(50)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "+50 HP", color=RED, lifetime=1.5))
        elif item_type == ItemType.AMMO_BOX:
            # 补充所有武器弹药
            for weapon in self.player.weapons:
                if hasattr(weapon, 'current_ammo') and weapon.current_ammo != "Inf":
                    weapon.current_ammo = weapon.max_ammo
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "弹药补给", color=YELLOW, lifetime=1.5))
        elif item_type == ItemType.SPEED_BOOST:
            self.player.buff_manager.add_buff(BuffType.SPEED_BOOST, duration=10.0)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "速度提升！", color=BLUE, lifetime=2.0))
        elif item_type == ItemType.DAMAGE_BOOST:
            self.player.buff_manager.add_buff(BuffType.DAMAGE_BOOST, duration=10.0)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "伤害提升！", color=ORANGE, lifetime=2.0))
        elif item_type == ItemType.SHIELD_REPAIR:
            if self.player.riot_gear.equipped:
                self.player.riot_gear.viewing_window_hp = min(
                    self.player.riot_gear.max_viewing_window_hp,
                    self.player.riot_gear.viewing_window_hp + 50
                )
                self.player.riot_gear.shield_broken = False
                self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "盾牌修复！", color=BLUE, lifetime=2.0))
        elif item_type == ItemType.WEAPON_BOX:
            # 武器箱：不再掉落武器，改为金币+经验奖励（武器由局外商店购买解锁）
            coin = random.randint(30, 60)
            try:
                self.records.add_coins(coin)
                self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, f"武器箱: +{coin}金币!", color=(200, 160, 80), lifetime=3.0))
            except Exception:
                pass
            self.player.gain_exp(50)
            self.assets.play_sound("pickup_weapon_box")
            self.particles.spawn_explosion(self.player.x, self.player.y, (200, 160, 80), 15)

            # 概率掉落可拾取文本资料
            try:
                from codex import PICKABLE_TEXTS
                uncollected = [tid for tid in PICKABLE_TEXTS if tid not in self.collected_texts]
                if uncollected and random.random() < 0.35:
                    text_id = random.choice(uncollected)
                    tx = self.player.x + random.randint(-50, 50)
                    ty = self.player.y + random.randint(-50, 50)
                    self.text_items.append(TextItem(tx, ty, text_id))
            except Exception:
                pass
        elif item_type == ItemType.TREASURE_CHEST:
            # 宝箱：多重奖励
            if self.session:
                self.session.add_chest_opened()
            rewards = []
            # 1. 金币（不再掉落武器，武器由局外商店购买解锁）
            coin = random.randint(40, 80)
            try:
                self.records.add_coins(coin)
            except Exception:
                pass
            rewards.append(f"+{coin}金币")
            # 2. 大量经验
            self.player.gain_exp(100)
            rewards.append("+100经验")
            # 3. 治疗
            self.player.heal(30)
            rewards.append("+30HP")
            # 4. 随机符文（局内永久buff，使用新符文系统）
            luck = self.rune_manager.get_bonus("drop_rate_mult") if hasattr(self, 'rune_manager') else 0
            rune_type = random_rune(luck_bonus=luck)
            if hasattr(self, 'rune_manager') and self._gain_rune(rune_type):
                cfg = RUNE_CONFIG[rune_type]
                rewards.append(f"符文: {cfg['name']}")
                self._apply_rune_bonuses()
            else:
                rewards.append("符文(已满)")
            # 5. 弹药补给
            for weapon in self.player.weapons:
                if hasattr(weapon, 'current_ammo') and weapon.current_ammo != "Inf":
                    weapon.current_ammo = weapon.max_ammo
            if self.session:
                self.session.add_weapon_collected()
                self.session.add_score(500)
            self.player.score += 500
            self.assets.play_sound("pickup_treasure")
            self.particles.spawn_explosion(self.player.x, self.player.y, (255, 215, 0), 30)
            self.particles.spawn(self.player.x, self.player.y, (255, 255, 200), 20)
            reward_text = "宝箱: " + ", ".join(rewards[:3])

            # 6. 概率掉落可拾取文本资料
            try:
                from codex import PICKABLE_TEXTS
                uncollected = [tid for tid in PICKABLE_TEXTS if tid not in self.collected_texts]
                if uncollected and random.random() < 0.6:
                    text_id = random.choice(uncollected)
                    tx = self.player.x + random.randint(-60, 60)
                    ty = self.player.y + random.randint(-60, 60)
                    self.text_items.append(TextItem(tx, ty, text_id))
            except Exception:
                pass
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 50, reward_text, color=(255, 215, 0), lifetime=4.0))

        elif item_type == ItemType.SKILL_SLOT:
            # 技能槽扩展：升级时多一个技能选项
            if not hasattr(self.player, 'skill_slot_count'):
                self.player.skill_slot_count = 3
            self.player.skill_slot_count += 1
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                f"技能槽+1！(当前{self.player.skill_slot_count}选1)", color=GOLD, lifetime=3.0))
            self.assets.play_sound("pickup_skill_slot")
            self.particles.spawn_explosion(self.player.x, self.player.y, GOLD, 25)

        elif item_type == ItemType.BUFF_CHARM:
            # 护符：随机获得一个强力正面buff
            buff_choices = [BuffType.EMPOWER, BuffType.GHOST, BuffType.THORNS,
                           BuffType.BLOOD_FRENZY, BuffType.INVINCIBLE, BuffType.BERSERK]
            chosen = random.choice(buff_choices)
            self.player.buff_manager.add_buff(chosen, duration=20.0)
            from buff import BUFF_CONFIGS
            buff_name = BUFF_CONFIGS[chosen]["name"]
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                f"护符: {buff_name}!", color=CYAN, lifetime=3.0))
            self.assets.play_sound("pickup_buff_charm")
            self.particles.spawn_explosion(self.player.x, self.player.y, CYAN, 20)

        elif item_type == ItemType.INCENDIARY:
            # 燃烧弹：添加到投掷物库存
            if not hasattr(self.player, 'throwables'):
                self.player.throwables = {}
            self.player.throwables["incendiary"] = self.player.throwables.get("incendiary", 0) + 2
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                "燃烧弹 x2！(按Q投掷)", color=FIRE_ORANGE, lifetime=3.0))
            self.assets.play_sound("pickup_grenade")
            self.particles.spawn_explosion(self.player.x, self.player.y, FIRE_ORANGE, 15)

        elif item_type == ItemType.SMOKE_GRENADE:
            # 烟雾弹
            if not hasattr(self.player, 'throwables'):
                self.player.throwables = {}
            self.player.throwables["smoke"] = self.player.throwables.get("smoke", 0) + 2
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                "烟雾弹 x2！(按Q投掷)", color=SMOKE_GRAY, lifetime=3.0))
            self.assets.play_sound("pickup_grenade")
            self.particles.spawn_explosion(self.player.x, self.player.y, SMOKE_GRAY, 15)

        elif item_type == ItemType.CLUSTER_BOMB:
            # 集束炸弹
            if not hasattr(self.player, 'throwables'):
                self.player.throwables = {}
            self.player.throwables["cluster"] = self.player.throwables.get("cluster", 0) + 1
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                "集束炸弹 x1！(按Q投掷)", color=ORANGE, lifetime=3.0))
            self.assets.play_sound("pickup_grenade")
            self.particles.spawn_explosion(self.player.x, self.player.y, ORANGE, 20)

        elif item_type == ItemType.EMP_GRENADE:
            # EMP脉冲弹
            if not hasattr(self.player, 'throwables'):
                self.player.throwables = {}
            self.player.throwables["emp"] = self.player.throwables.get("emp", 0) + 2
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                "EMP脉冲弹 x2！(按Q投掷)", color=CYAN, lifetime=3.0))
            self.assets.play_sound("pickup_grenade")
            self.particles.spawn_explosion(self.player.x, self.player.y, CYAN, 15)

        elif item_type == ItemType.RUNE:
            # 符文：局内永久buff
            luck = self.rune_manager.get_bonus("drop_rate_mult") if hasattr(self, 'rune_manager') else 0
            rune_type = random_rune(luck_bonus=luck)
            if hasattr(self, 'rune_manager') and self._gain_rune(rune_type):
                cfg = RUNE_CONFIG[rune_type]
                self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                    f"获得符文: {cfg['name']}!", color=cfg['color'], lifetime=3.5))
                self.assets.play_sound("level_up")
                self.particles.spawn_explosion(self.player.x, self.player.y, cfg['color'], 20)
                # 立即应用属性加成
                self._apply_rune_bonuses()
            else:
                self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                    "符文已达上限！", color=GRAY, lifetime=2.0))

        elif item_type == ItemType.GOLDEN_CHEST:
            # 黄金宝箱：必出符文+大量资源
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                "黄金宝箱开启！", color=GOLD, lifetime=2.5))
            self.assets.play_sound("level_up")
            # 必出1-2枚符文
            luck = self.rune_manager.get_bonus("drop_rate_mult") if hasattr(self, 'rune_manager') else 0
            rune_count = 2 if random.random() < 0.3 + luck else 1
            for _ in range(rune_count):
                rune_type = random_rune(luck_bonus=luck + 0.5)  # 黄金宝箱提升稀有度
                if hasattr(self, 'rune_manager'):
                    self._gain_rune(rune_type)
                    cfg = RUNE_CONFIG[rune_type]
                    self.floating_texts.append(FloatingText(self.player.x, self.player.y - 70,
                        f"符文: {cfg['name']}!", color=cfg['color'], lifetime=3.0))
            # 大量资源
            self.player.hp = min(self.player.max_hp, self.player.hp + 50)
            if hasattr(self.player, 'ammo'):
                for w in self.player.weapons:
                    if hasattr(w, 'ammo') and w.ammo is not None:
                        w.ammo = getattr(w, 'max_ammo', w.ammo + 30)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 100,
                "生命+50, 弹药全满!", color=GREEN, lifetime=2.5))
            self.particles.spawn_explosion(self.player.x, self.player.y, GOLD, 30)
            if hasattr(self, '_apply_rune_bonuses'):
                self._apply_rune_bonuses()

        elif item_type == ItemType.MYSTERY_BOX:
            # 神秘盒：随机效果（可能好可能坏）
            self.assets.play_sound("pickup_grenade")
            effects = [
                ("good", "full_heal", "神秘盒: 生命全满!", GREEN),
                ("good", "max_hp_up", "神秘盒: 最大生命+20!", GREEN),
                ("good", "damage_up", "神秘盒: 伤害永久+10%!", ORANGE),
                ("good", "speed_up", "神秘盒: 移速永久+10%!", CYAN),
                ("good", "rune", "神秘盒: 获得符文!", GOLD),
                ("good", "ammo", "神秘盒: 弹药全满!", YELLOW),
                ("bad", "damage", "神秘盒: 受到20点伤害!", RED),
                ("bad", "slow", "神秘盒: 移速降低5秒!", BLUE),
                ("bad", "zombies", "神秘盒: 引来一群僵尸!", RED),
            ]
            effect = random.choice(effects)
            etype, ekind, emsg, ecolor = effect
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40,
                emsg, color=ecolor, lifetime=3.0))
            if etype == "good":
                if ekind == "full_heal":
                    self.player.hp = self.player.max_hp
                elif ekind == "max_hp_up":
                    self.player.max_hp += 20
                    self.player.hp += 20
                elif ekind == "damage_up":
                    self.player.damage_mult = getattr(self.player, 'damage_mult', 1.0) + 0.10
                elif ekind == "speed_up":
                    self.player.speed_mult = getattr(self.player, 'speed_mult', 1.0) + 0.10
                elif ekind == "rune":
                    if hasattr(self, 'rune_manager'):
                        rt = random_rune()
                        self._gain_rune(rt)
                        self._apply_rune_bonuses()
                elif ekind == "ammo":
                    for w in self.player.weapons:
                        if hasattr(w, 'ammo') and w.ammo is not None:
                            w.ammo = getattr(w, 'max_ammo', w.ammo + 30)
            else:
                if ekind == "damage":
                    self.player.hp -= 20
                elif ekind == "slow":
                    if hasattr(self, 'buff_manager'):
                        self.buff_manager.add_buff(BuffType.SLOW, 5.0)
                elif ekind == "zombies":
                    # 在玩家周围生成5只普通僵尸
                    for _ in range(5):
                        angle = random.uniform(0, math.pi * 2)
                        dist = random.uniform(150, 250)
                        zx = self.player.x + math.cos(angle) * dist
                        zy = self.player.y + math.sin(angle) * dist
                        from entities import Enemy, EnemyType
                        self.enemies.append(Enemy(zx, zy, EnemyType.ZOMBIE, 1, self.config.difficulty))
            self.particles.spawn_explosion(self.player.x, self.player.y, PURPLE, 15)

    def _load_permanent_runes(self):
        """符文不跨局永久保存：本局从0开始，不加载跨局存档（符文本局获得/升级/重置）"""
        if not hasattr(self, 'rune_manager'):
            return
        # 符文改为局内：不再从跨局存档加载永久符文
        self.rune_manager.load_permanent({})

    def _gain_rune(self, rune_type):
        """获得/升级一枚符文：仅升级本局层数（不跨局保存）"""
        if not hasattr(self, 'rune_manager'):
            return False
        if not self.rune_manager.upgrade_rune(rune_type):
            return False
        # 符文不跨局：移除跨局永久存档同步
        return True

    def _apply_rune_bonuses(self):
        """应用所有符文的属性加成到玩家"""
        if not hasattr(self, 'rune_manager') or not hasattr(self, 'player') or self.player is None:
            return
        rm = self.rune_manager
        # 保存基础值（只在第一次应用时保存）
        if not hasattr(self.player, '_rune_base_max_hp'):
            self.player._rune_base_max_hp = self.player.max_hp
            self.player._rune_base_damage_mult = getattr(self.player, 'damage_mult', 1.0)
            self.player._rune_base_speed_mult = getattr(self.player, 'speed_mult', 1.0)
            self.player._rune_base_crit_chance = getattr(self.player, 'crit_chance', 0.05)
            self.player._rune_base_crit_damage = getattr(self.player, 'crit_damage_mult', 1.5)
            self.player._rune_base_lifesteal = getattr(self.player, 'lifesteal', 0.0)
            self.player._rune_base_armor = getattr(self.player, 'armor', 0)
            self.player._rune_base_fire_rate = getattr(self.player, 'fire_rate_mult', 1.0)
            self.player._rune_base_crit_damage = getattr(self.player, 'crit_damage', 1.5)
            self.player._rune_base_regen = getattr(self.player, 'regen_rate', 0.0)
        # 应用加成
        self.player.max_hp = self.player._rune_base_max_hp + rm.get_bonus("max_hp")
        self.player.damage_mult = self.player._rune_base_damage_mult + rm.get_bonus("damage_mult")
        self.player.speed_mult = self.player._rune_base_speed_mult + rm.get_bonus("speed_mult")
        self.player.crit_chance = self.player._rune_base_crit_chance + rm.get_bonus("crit_chance")
        self.player.crit_damage_mult = self.player._rune_base_crit_damage + rm.get_bonus("crit_damage_mult")
        # 暗影符文：暴击伤害倍率实际生效（攻击命中用crit_damage计算暴击伤害）
        self.player.crit_damage = self.player._rune_base_crit_damage + rm.get_bonus("crit_damage_mult")
        self.player.lifesteal = self.player._rune_base_lifesteal + rm.get_bonus("lifesteal")
        self.player.armor = self.player._rune_base_armor + rm.get_bonus("armor")
        self.player.fire_rate_mult = self.player._rune_base_fire_rate + rm.get_bonus("fire_rate_mult")
        # 再生符文：每秒回血实际生效（player.update按regen_rate回血）
        self.player.regen_rate = self.player._rune_base_regen + rm.get_bonus("regen")
        # 泰坦符文：体型增大15%（渲染用，碰撞仍用原size）
        titan_stacks = rm.get_stacks(RuneType.TITAN)
        base_size = getattr(self.player, '_rune_base_size', self.player.size)
        if not hasattr(self.player, '_rune_base_size'):
            self.player._rune_base_size = self.player.size
        self.player.render_size = int(base_size * (1.0 + 0.15 * titan_stacks))

    def _apply_rune_elemental_on_hit(self, enemy, base_damage=1.0):
        """玩家攻击命中敌人时应用元素符文效果（火焰/冰霜/毒素/雷电）"""
        if not hasattr(self, 'rune_manager') or enemy is None or not getattr(enemy, 'alive', False):
            return
        try:
            rm = self.rune_manager
            if rm.has_elemental("fire"):
                enemy.apply_buff(BuffType.BURN, duration=3.0)
            if rm.has_elemental("frost"):
                enemy.apply_buff(BuffType.SLOW, duration=2.0)
            if rm.has_elemental("poison"):
                enemy.apply_buff(BuffType.POISON, duration=5.0)
            if rm.has_elemental("thunder"):
                self._rune_thunder_chain(enemy, base_damage)
        except Exception:
            pass

    def _rune_thunder_chain(self, enemy, base_damage):
        """雷电符文：攻击命中时触发连锁闪电，跳跃到附近敌人（最多3次）"""
        try:
            stacks = self.rune_manager.get_stacks(RuneType.THUNDER)
            hit = [enemy]
            src = enemy
            dmg = max(1.0, base_damage * (0.5 + 0.25 * stacks))
            jumps = min(3, 1 + stacks)
            for _ in range(jumps):
                candidates = [e for e in self.enemies
                              if e not in hit and getattr(e, 'alive', False)
                              and math.hypot(e.x - src.x, e.y - src.y) < 220]
                if not candidates:
                    break
                tgt = min(candidates, key=lambda e: math.hypot(e.x - src.x, e.y - src.y))
                tgt.take_damage(dmg)
                self.damage_numbers.append(DamageNumber(tgt.x, tgt.y, dmg, is_crit=False, damage_type="thunder"))
                self.particles.spawn(tgt.x, tgt.y, YELLOW, 8, (2, 5), (-3, 3), (0.2, 0.4))
                hit.append(tgt)
                src = tgt
                dmg *= 0.7
        except Exception:
            pass

    def _vampire_heal(self, amount):
        """吸血符文：造成伤害时按lifesteal回复生命值"""
        try:
            ls = getattr(self.player, 'lifesteal', 0.0)
            if ls > 0 and amount > 0:
                self.player.heal(int(amount * ls))
        except Exception:
            pass

    def _codex_unlock_toast(self, unlocked, label):
        """图鉴新解锁时实时弹出提示"""
        if unlocked:
            self.ach_toast_queue.append({"key": "codex", "name": label, "desc": "已收录进图鉴",
                                            "timer": 3.0, "kind": "codex", "born": time.time()})
