# -*- coding: utf-8 -*-
"""StoryMixin - 由 game.py 自动拆分，逻辑等价"""

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

class StoryMixin:
    def _start_intro_dialogue(self):
        # 故事模式：根据当前地图使用对应的开场对话
        if self.config.game_mode == GameMode.STORY and self.current_map in STORY_INTRO_DIALOGUE:
            dialogues = STORY_INTRO_DIALOGUE[self.current_map]
        else:
            dialogues = [
                {"speaker": "???", "text": "醒醒！快醒醒！"},
                {"speaker": "你", "text": "...这里是...学校？发生什么事了？"},
                {"speaker": "广播", "text": "紧急通知：学校出现不明病毒感染，所有人员立即撤离..."},
                {"speaker": "你", "text": "龙某？向某？你们在哪？"},
                {"speaker": "???", "text": "他们...他们已经...不，快逃！那些东西来了！"},
            ]
        def on_complete():
            self.state = GameState.PLAYING
            logger.info("开场对话结束，恢复游戏")
        self.dialogue.start_dialogue(dialogues, on_complete)
        self.state = GameState.DIALOGUE
        logger.info("开场对话开始")

    # ========== 故事模式相关方法 ==========
    def _update_story_mode(self, dt):
        """更新故事模式：时间、剧情收集物、特殊事件、地图切换"""
        self.map_time_elapsed += dt
        current_minute = self.map_time_elapsed / 60.0

        # 1. 剧情收集物刷新检查
        self._check_story_fragment_spawn(current_minute)

        # 2. 更新地图上的剧情收集物
        for item in self.story_fragment_items[:]:
            item["timer"] -= dt
            if item["timer"] <= 0:
                self.story_fragment_items.remove(item)
                continue
            # 磁吸移动（被钩爪勾中）
            if item.get("magnetized"):
                dx = self.player.x - item["x"]
                dy = self.player.y - item["y"]
                dist = math.hypot(dx, dy)
                if dist > 5:
                    item["x"] += (dx / dist) * 6 * dt * 60
                    item["y"] += (dy / dist) * 6 * dt * 60
            # 玩家拾取检测
            dist = math.hypot(self.player.x - item["x"], self.player.y - item["y"])
            if dist < self.player.size + 20:
                self._collect_story_fragment(item)
                self.story_fragment_items.remove(item)

        # 3. 特殊事件触发
        if not self.special_event_triggered:
            event_name = self.map_config.get("special_event", "")
            event_minutes = {
                "school_evacuation": 14,
                "street_blackout": 12,
                "downtown_airstrike": 10,
                "suburb_mutation": 8,
                "nuclear_meltdown": 6,
            }
            trigger_min = event_minutes.get(event_name, 999)
            if current_minute >= trigger_min:
                self._trigger_special_event(event_name)

        # 3.5 幸存者 NPC（v2.0.11 选项对话）
        self._update_survivor_npc(current_minute)

        # 4. 地图时间到了，切换到下一张地图
        time_limit = self.map_config.get("time_limit", 1200)
        if self.map_time_elapsed >= time_limit:
            self._advance_to_next_map()

    def _check_story_fragment_spawn(self, current_minute):
        """检查是否有剧情片段需要刷新到地图上"""
        fragments = STORY_FRAGMENTS.get(self.current_map, [])
        for frag in fragments:
            frag_id = frag["id"]
            if frag_id in self.story_collected_fragments:
                continue
            # 检查是否已经在地图上
            if any(item["id"] == frag_id for item in self.story_fragment_items):
                continue
            # 到了刷新时间
            if current_minute >= frag["spawn_minute"]:
                # 在玩家附近随机位置刷新
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(150, 350)
                x = self.player.x + math.cos(angle) * dist
                y = self.player.y + math.sin(angle) * dist
                self.story_fragment_items.append({
                    "id": frag_id,
                    "x": x,
                    "y": y,
                    "title": frag["title"],
                    "content": frag["content"],
                    "timer": 180.0,  # 存在3分钟
                    "pulse": 0.0,
                })
                self.floating_texts.append(FloatingText(
                    x, y - 30, "发现资料!", color=GOLD, lifetime=2.0
                ))
                logger.info(f"剧情片段刷新: {frag_id}")

    def _collect_story_fragment(self, item):
        """收集剧情片段"""
        self.story_collected_fragments.add(item["id"])
        self.records.add_collected_story(item["id"])
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40,
            f"收集: {item['title']}", color=GOLD, lifetime=2.5
        ))
        self.assets.play_sound("pickup")
        # 显示剧情内容对话
        dialogues = [
            {"speaker": "资料", "text": f"【{item['title']}】"},
            {"speaker": "资料", "text": item["content"]},
        ]
        def on_close():
            self.state = GameState.PLAYING
        self.dialogue.start_dialogue(dialogues, on_close)
        self.state = GameState.DIALOGUE
        logger.info(f"收集剧情片段: {item['id']}")

    def _trigger_special_event(self, event_name):
        """触发特殊事件"""
        self.special_event_triggered = True
        self.special_event_active = True
        logger.info(f"特殊事件触发: {event_name}")

        event_messages = {
            "school_evacuation": "警报！教学楼已失守，撤离至室外操场！难度大幅提升！",
            "street_blackout": "全城停电！视野受限，小心暗处的敌人！",
            "downtown_airstrike": "军方空袭开始！注意躲避随机轰炸！",
            "suburb_mutation": "警告！检测到大量变异体信号！敌人变得更强了！",
            "nuclear_meltdown": "反应堆熔毁！辐射区域正在扩散，注意躲避！",
        }
        msg = event_messages.get(event_name, "特殊事件触发！")
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 60, msg, color=RED, lifetime=4.0
        ))
        self.camera.shake(15, 1.0)
        self.assets.play_sound("boss_appear")

    # ========== v2.0.11 幸存者 NPC 选项对话（1/2/3） ==========
    def _spawn_survivor_npc(self):
        """在玩家附近刷新一名幸存者 NPC"""
        angle = random.uniform(0, math.pi * 2)
        dist = random.uniform(250, 420)
        self.survivor_npc = {
            "x": self.player.x + math.cos(angle) * dist,
            "y": self.player.y + math.sin(angle) * dist,
            "name": "幸存者",
            "active": True,
        }
        self.floating_texts.append(FloatingText(
            self.survivor_npc["x"], self.survivor_npc["y"] - 40,
            "幸存者！", color=(120, 220, 255), lifetime=3.0))

    def _update_survivor_npc(self, current_minute):
        """更新幸存者 NPC：生成 + 靠近触发对话"""
        if not hasattr(self, 'survivor_npc') or self.survivor_npc is None:
            if current_minute >= 0.8:
                self._spawn_survivor_npc()
            return
        npc = self.survivor_npc
        if not npc.get("active"):
            return
        dist = math.hypot(self.player.x - npc["x"], self.player.y - npc["y"])
        if dist < 70:
            self._start_survivor_dialogue()

    def _start_survivor_dialogue(self):
        """幸存者选项对话：1 补给 / 2 情报 / 3 结伴"""
        npc = self.survivor_npc
        if not npc or not npc.get("active"):
            return
        npc["active"] = False
        map_lines = {
            MapType.SCHOOL: "我从教学楼二楼逃出来的，那边已经全是...它们了。",
            MapType.STREET: "街上的便利店还有吃的，但晚上会有大群游荡。",
            MapType.DOWNTOWN: "市中心那帮当兵的，听说撤走前炸了桥。",
            MapType.SUBURB: "郊外那些大个子的变异体，别跟它们硬碰硬。",
            MapType.NUCLEAR_PLANT: "核电站方向一直有奇怪的绿光...别靠近那里。",
        }
        tip = map_lines.get(self.current_map, "这世道，活着就是胜利。")
        dialogues = [
            {"speaker": npc.get("name", "幸存者"), "text": "嘘！小声点！你也是活下来的？"},
            {"speaker": npc.get("name", "幸存者"), "text": tip},
            {"speaker": npc.get("name", "幸存者"), "text": "你想怎么办？", "choices": [
                {"text": "给我点吃的（回复生命+40）", "effect": {"type": "heal", "value": 40}},
                {"text": "打听附近的情报", "effect": {"type": "info", "value": "往北的便利店有个广播站，那边可能还有人。"}},
                {"text": "一起走（获得30金币）", "effect": {"type": "coin", "value": 30}},
            ]},
            {"speaker": npc.get("name", "幸存者"), "text": "（点头）活下去，比什么都强。保重。"},
        ]
        self.dialogue.start_dialogue(dialogues, None)
        self.state = GameState.DIALOGUE
        self.assets.play_sound("pickup")
        logger.info("幸存者选项对话开始")

    def _advance_to_next_map(self):
        """切换到下一张地图（通关当前地图，解锁下一张）"""
        # 通关当前地图，解锁下一张（供局外直接选图）
        try:
            self.records.clear_map(self.current_map.name)
            if self.current_map_index < len(STORY_MAP_ORDER) - 1:
                self.records.unlock_map(STORY_MAP_ORDER[self.current_map_index + 1].name)
        except Exception:
            pass
        if self.current_map_index >= len(STORY_MAP_ORDER) - 1:
            # 最后一张地图完成，通关
            self._story_victory()
            return

        self.current_map_index += 1
        self.current_map = STORY_MAP_ORDER[self.current_map_index]
        self.map_config = MAP_CONFIGS[self.current_map]
        self.map_time_elapsed = 0.0
        self.special_event_triggered = False
        self.special_event_active = False
        self.story_fragment_items = []

        # 重新生成世界
        self.world = GameWorld(map_type=self.current_map)
        # 重置敌人和投射物
        self.enemies = []
        self.projectiles = []
        self.special_items = []  # 场景道具（武器箱/宝箱/生命/弹药等）
        self.text_items = []  # 可拾取文本资料
        self.current_viewing_text = None
        self.rune_buffs = {}  # 符文永久buff（局内）
        self.enemy_projectiles = []
        self.smoke_zones = []
        self.grenades = []
        # 近战攻击状态
        self.melee_attack_active = False
        self.melee_attack_timer = 0
        self.melee_attack_duration = 0.25
        self.melee_attack_angle = 0
        self.melee_attack_range = 60
        self.melee_attack_damage = 0
        self.melee_attack_weapon = None
        self.melee_hit_enemies = set()
        # 重置尸潮管理器
        self.horde_manager = HordeManager(GameMode.STORY, self.config.difficulty)
        # 玩家位置重置
        # 故事模式进入新地图：重置全部局内状态（技能/符文/经验/生命），保留初始武器与角色
        self.player = Player(0, 0, start_weapon=self.selected_weapon, start_weapon_level=self.selected_weapon_level)
        self.rune_buffs = {}  # 符文局内buff 重置
        self.rune_manager = RuneManager()  # 符文局内层数重置（不跨局、不跨地图）
        try:
            self._apply_rune_bonuses()  # 无符文，恢复基础属性
            self._apply_character_bonuses()  # 重新应用局外角色加成（保留角色）
        except Exception:
            pass

        logger.info(f"切换到地图: {self.map_config['name']}")

        # 显示地图切换过场对话
        dialogues = [
            {"speaker": "系统", "text": f"---- {self.map_config['chapter']} ----"},
            {"speaker": "系统", "text": self.map_config['name']},
            {"speaker": "系统", "text": self.map_config['description']},
        ]
        def on_complete():
            self.state = GameState.PLAYING
            self._start_intro_dialogue()
        self.dialogue.start_dialogue(dialogues, on_complete)
        self.state = GameState.DIALOGUE

    def _story_victory(self):
        """故事模式通关"""
        logger.info("故事模式通关！")
        self.delete_saved_game()
        self.assets.play_music("victory")
        dialogues = STORY_ENDING_DIALOGUE
        def on_complete():
            self.state = GameState.VICTORY
            if self.session:
                self.session.end_session(victory=True)
                self.records.on_game_end(self.session)
        self.dialogue.start_dialogue(dialogues, on_complete)
        self.state = GameState.DIALOGUE

    def _boss_dialogue(self, boss_type):
        if boss_type == EnemyType.BOSS_LONG:
            dialogues = [
                {"speaker": "龙某", "text": "吼...吼..."},
                {"speaker": "你", "text": "龙某？是你吗？"},
                {"speaker": "龙某", "text": "杀...杀了我...不...快逃..."},
                {"speaker": "你", "text": "不，我会找到办法救你的！"},
            ]
        else:
            dialogues = [
                {"speaker": "向某", "text": "呃啊啊啊！"},
                {"speaker": "你", "text": "向某！坚持住！"},
                {"speaker": "向某", "text": "朋友...快走...我控制不住了..."},
                {"speaker": "你", "text": "我不会放弃你的！"},
            ]
        def on_complete():
            self.state = GameState.PLAYING
        self.dialogue.start_dialogue(dialogues, on_complete)
        self.state = GameState.DIALOGUE

    def _final_dialogue(self):
        choices = []
        if self.has_vaccine:
            choices = [
                {"text": "使用疫苗拯救两人", "effect": "save_both"},
                {"text": "只救龙某", "effect": "save_long"},
                {"text": "只救向某", "effect": "save_xiang"},
                {"text": "两人都不救", "effect": "save_none"},
            ]
        else:
            choices = [
                {"text": "杀死两人", "effect": "kill_both"},
                {"text": "放他们走", "effect": "let_go"},
            ]

        dialogues = [
            {"speaker": "龙某", "text": "终于...我们面对面了..."},
            {"speaker": "向某", "text": "你变强了...但我们已经无法回头了..."},
            {"speaker": "龙某", "text": "杀了我们吧...这是我们最后的请求..."},
            {"speaker": "向某", "text": "或者...如果你能找到疫苗..."},
            {"speaker": "你", "text": "...", "choices": choices},
        ]

        def on_complete():
            # 保存结局记录
            if self.session:
                if not self.session.data.get("ending"):
                    self.session.set_ending(self.ending_type or "kill_both")
                self.session.set_died(False)
                self.session.finalize()
                self.session = None
            # 播放结局音乐
            self.assets.play_music("ending")
            self.state = GameState.ENDING

        self.dialogue.start_dialogue(dialogues, on_complete)
        self.state = GameState.DIALOGUE

    def _advance_dialogue(self):
        if not self.dialogue.active:
            if self.state == GameState.DIALOGUE:
                self.state = GameState.PLAYING
                logger.info("对话已结束，恢复游戏状态")
            return
        if len(self.dialogue.displayed_text) < len(self.dialogue.text):
            self.dialogue.displayed_text = self.dialogue.text
            logger.debug("对话：快速显示全部文字")
            return
        if self.dialogue.choices:
            logger.debug("对话：等待玩家选择")
            return
        self.dialogue.advance()
        logger.debug(f"对话：推进到下一条，索引={self.dialogue.current_index}")
        if not self.dialogue.active:
            if self.state == GameState.DIALOGUE:
                self.state = GameState.PLAYING
            logger.info("对话结束，恢复")

    def _check_choice_click(self, pos):
        if not self.dialogue.choices or not self.dialogue.dialog_rect:
            return -1
        dialog_rect = self.dialogue.dialog_rect
        choice_y = dialog_rect.y + dialog_rect.height - 45
        for i, choice in enumerate(self.dialogue.choices):
            choice_x = dialog_rect.x + 20 + i * min(280, self.scaled_width // 4)
            choice_text = f"{i+1}. {choice['text']}"
            text_width = self.font.size(choice_text)[0]
            text_height = self.font.get_height()
            choice_rect = pygame.Rect(choice_x - 5, choice_y - 5, text_width + 10, text_height + 10)
            if choice_rect.collidepoint(pos):
                return i
        return -1

    def _apply_choice_effect(self, effect):
        """应用对话选项效果（v2.0.11：支持字符串结局 / dict 通用效果）"""
        if not effect:
            return
        # 旧式结局字符串（兼容）
        if isinstance(effect, str):
            ending_map = {
                "save_both": "perfect",
                "save_long": "save_long",
                "save_xiang": "save_xiang",
                "save_none": "tragic",
                "kill_both": "kill_both",
                "let_go": "let_go"
            }
            self.ending_type = ending_map.get(effect, "kill_both")
            if self.session:
                self.session.set_ending(self.ending_type)
            return
        # v2.0.11 通用效果字典
        if isinstance(effect, dict):
            et = effect.get("type", "")
            val = effect.get("value", 0)
            try:
                if et == "ending":
                    self.ending_type = str(val)
                    if self.session:
                        self.session.set_ending(self.ending_type)
                    logger.info(f"对话结局: {self.ending_type}")
                elif et == "heal" and self.player:
                    amt = int(val)
                    self.player.heal(amt)
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 50, f"+{amt} 生命", color=(80, 255, 120), lifetime=2.0))
                    self.assets.play_sound("pickup")
                elif et == "coin" and self.records:
                    amt = int(val)
                    self.records.add_coins(amt)
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 50,
                        f"+{amt} 金币" if amt >= 0 else f"{amt} 金币", color=GOLD, lifetime=2.0))
                    self.assets.play_sound("coin")
                elif et == "info":
                    msg = str(val)
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 60, msg, color=CYAN, lifetime=3.5))
                elif et == "buff" and self.player:
                    self.player.apply_buff(str(val), effect.get("duration", 10.0))
            except Exception as e:
                logger.warning(f"对话效果应用失败: {e}")

    # ========== 技能系统 ==========
    # 传说级武器 → 专属技能映射（持有对应武器自动解锁，等级随武器等级成长）
    LEGENDARY_WEAPON_SKILLS = {
        "SCYTHE": SkillType.SCYTHE_DANCE,
        "MINIGUN": SkillType.MINIGUN_OVERDRIVE,
        "RAILGUN": SkillType.RAILGUN_ANNIHILATION,
    }
