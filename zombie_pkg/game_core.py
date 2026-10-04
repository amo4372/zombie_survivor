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

class GameCore:

    def __init__(self):
        self.logger = logger
        try:
            pygame.init()
            pygame.mixer.init()
            logger.info("Pygame初始化成功")
        except Exception as e:
            logger.log_exception(e)

        self.is_android = "ANDROID_ROOT" in os.environ or hasattr(sys, "getandroidapilevel")
        logger.info(f"平台: {'Android' if self.is_android else 'PC/Desktop'}")

        info = pygame.display.Info()
        self.native_width = info.current_w
        self.native_height = info.current_h
        logger.info(f"屏幕分辨率: {self.native_width}x{self.native_height}")

        try:
            if self.is_android:
                self.screen = pygame.display.set_mode(
                    (self.native_width, self.native_height),
                    pygame.FULLSCREEN | pygame.DOUBLEBUF
                )
                logger.info("Android全屏模式")
            else:
                self.screen = pygame.display.set_mode(
                    (BASE_WIDTH, BASE_HEIGHT),
                    pygame.RESIZABLE | pygame.DOUBLEBUF
                )
                logger.info("PC窗口模式")
        except Exception as e:
            logger.log_exception(e)
            self.screen = pygame.display.set_mode((BASE_WIDTH, BASE_HEIGHT))

        pygame.display.set_caption("丧尸幸存者 - 黑暗尸潮")
        self.clock = pygame.time.Clock()
        self.running = True

        self.scale = 1.0
        self._update_scale()
        logger.info(f"初始缩放比例: {self.scale}")

        # 兼容 PyInstaller 打包：资源从 exe 同级目录加载（不内嵌资源模式）
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            # v2.0.9 包结构：game_core.py 位于 zombie_pkg/ 子包，上溯一级为仓库根
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # v2.0.8：启动时先应用上次更新被占用而延迟替换的文件（字体/音频等），
        # 必须在 FontManager 加载任何字体之前执行，避免 ttf 被旧文件占用导致热更新失败
        try:
            _pending = updater.apply_pending_updates(base_path)
            if _pending > 0:
                logger.info(f"已应用 {_pending} 个延迟替换文件（上次更新被占用）")
        except Exception as e:
            logger.warning(f"应用延迟替换失败: {e}")

        FontManager.init(base_path)

        self.config = Config()
        logger.info(f"控制模式: {self.config.control_mode.name}")
        # 应用日志开关：默认只写游戏日志文件，不打印终端
        logger.set_enabled(self.config.enable_logging)
        logger.set_console(False)

        self.font_small = FontManager.get(14)
        self.font = FontManager.get(18)
        self.font_medium = self.font  # 别名，兼容renderer
        self.font_large = FontManager.get(24)
        self.font_title = FontManager.get(40)

        self.state = GameState.MENU
        self.previous_state = None

        self.player = None
        # 观战模式
        self.world = None
        self.horde_manager = None
        self.camera = None
        self.particles = None
        self.dialogue = None

        self.rune_manager = RuneManager()  # 符文系统（修复：此前从未初始化导致不生效）
        self.enemies = []
        self.projectiles = []
        self.special_items = []  # 场景道具（武器箱/宝箱/生命/弹药等）
        self.text_items = []  # 可拾取文本资料
        self.collected_texts = set()  # 已收集的文本ID
        self.current_viewing_text = None  # 当前查看的文本
        self._load_collected_texts()
        self.rune_buffs = {}  # 符文永久buff（局内）
        self.exp_orbs = []
        self.damage_numbers = []
        self.floating_texts = []
        self.slash_arcs = []  # 刀光弧斩特效（死神镰刀横扫/处决/枪械曳光）
        self.sweep_rings = []  # 圆形横扫扩散环特效（死神镰刀换弹横扫）
        self.enemy_projectiles = []

        # 近战攻击状态
        self.melee_attack_active = False
        self.melee_attack_timer = 0
        self.melee_attack_duration = 0.25
        self.melee_attack_angle = 0
        self.melee_attack_range = 60
        self.melee_attack_damage = 0
        self.melee_attack_weapon = None
        self.melee_hit_enemies = set()

        # 技能相关
        self.selected_skill = SkillType.GRENADE
        self.skill_wheel = SkillWheel()
        self.weapon_wheel = WeaponWheel()
        self.skill_wheel_active = False
        self.weapon_wheel_active = False
        self.skill_selector = None
        self.skill_caster = None
        self.skill_card_selector = SkillCardSelector()
        self.pending_upgrade_for = None  # 同屏双人：当前升级的玩家 "P1"/"P2"
        self.hud_layout_feedback = None  # HUD布局保存/重置的屏幕反馈提示
        self.skill_tree_renderer = SkillTreeRenderer()
        # 加载 mod
        try:
            self.loaded_mods = load_all_mods()
        except Exception as e:
            print(f"[Mod] 加载失败: {e}")
            self.loaded_mods = []

        # 菜单滚动
        self.menu_scroll_offset = 0
        self.settings_scroll_offset = 0
        self.tutorial_scroll_offset = 0
        self.records_scroll_offset = 0
        self.story_archive_scroll = 0
        self.is_menu_dragging = False
        self.menu_drag_start_y = 0
        self.menu_drag_start_offset = 0

        # 防爆套装动画
        self.riot_anim_timer = 0
        self.riot_anim_duration = 0.5
        self.riot_anim_state = "idle"
        self.riot_long_press_timer = 0
        self.riot_long_press_threshold = 0.5

        # 武器切换（已改为单武器模式，保留旧变量兼容）
        self.weapon_switch_cooldown = 0

        # ==== 局外选择：武器 / 角色 / 地图 ====
        self.selected_weapon = WeaponType.PISTOL      # 局外选定的武器（局内唯一）
        self.selected_weapon_level = 1                # 局外武器等级
        self.selected_character = None                # 局外选定的角色（None=默认角色）
        self.selected_map_for_story = None            # 故事模式局外选定地图（None=流程）
        # 装备选择界面滚动与选中
        self.equip_weapon_scroll = 0
        self.equip_character_scroll = 0
        self.equip_hover = None

        # 钩爪相关
        self.grapple_aiming = False
        self.grapple_aim_angle = 0
        self.grapple_press_time = 0

        self.touch_events = []
        # 跨状态、跨帧持久的手指按下跟踪（防止界面切换后控件被留在按下态）
        self._active_touch_ids = set()   # 当前仍按住的手指 id（鼠标统一用 -1 表示）
        self._active_touch_pos = {}      # 每根手指最后一次已知位置，用于切换时合成 up
        self._active_touch_last = {}     # 每根手指最后一次出现任何事件的时间（用于空闲超时恢复）
        self.touch_stuck_timeout = 4.0   # 手指静默多少秒后强制释放（防事件彻底丢失卡死，可调）
        self._setup_touch_controls()

        # ===== 开发者测试模式（不公开，主菜单连点版本号+密码进入）=====
        self.dev_mode = False            # 是否已进入开发者模式
        self.dev_click_count = 0         # 主菜单版本号连点计数
        self.dev_click_timer = 0.0       # 连点窗口计时
        self.dev_input_active = False    # 密码输入框是否激活
        self.dev_input_focused = False   # 密码输入框是否聚焦（点击后接受系统输入法）
        self.dev_input_str = ""          # 已输入密码
        self.dev_panel_open = False      # 局内调试面板开关
        self.dev_god = False             # 无敌
        self.dev_time_scale = 1.0        # 时间倍率（局内已支持，见 run()）
        self.dev_buttons = []            # 局内调试面板按钮
        self._DEV_PASSWORD = "dev4372"   # 开发者密码
        self.update_status_text = ""     # 主菜单提示文本
        self.update_notice = None        # 自动检查发现的新版本弹窗 (latest_version, changelog)
        self.update_notice_dismissed = False  # 用户已点"稍后"
        self.asset_issues = None        # 资源完整性检查结果 (missing, corrupted) 或 None

        #键鼠相关【新版：Tab/R只有短按；G支持短按快放 / 长按瞄准】
        self.key_g_press_start = 0.0
        self.key_g_long_threshold = 0.4
        self.g_aim_started = False
        self.key_g_held = False
        self.mouse_angle = 0.0

        # ===== 多人模式（v2.0）=====
        self.multiplayer_mode = None      # None / "same_screen" / "network"
        self.player2 = None               # 双人模式的第二位玩家
        self.camera2 = None               # 双人模式第二摄像机
        self.equip_p2_phase = False       # 多人模式装备选择阶段（False=P1 / True=P2）
        self.selected_weapon_p1 = None
        self.selected_char_p1 = None
        self.selected_weapon_p1_level = 1
        self.selected_weapon_p2 = None
        self.selected_char_p2 = None
        self.selected_weapon_p2_level = 1
        self.net_role = None              # None / "host" / "client"
        self.net_host = None
        self.net_client = None
        self.net_port = 26000
        self.net_ip_input = "127.0.0.1"
        self.net_ip_focused = False
        self.net_started = False
        # 同屏双人 P2 键控输入状态
        self.p2_input = {"mx": 0.0, "my": 0.0, "shoot": False, "skill": False,
                         "throw": False, "sprint": False}
        self.p2_controls = None
        self._p2_finger_ids = set()
        self.hud_edit_target = "P1"  # HUD布局编辑对象（双人模式 P1/P2）

        self.menu_buttons = []
        self.settings_buttons = []
        self.pause_buttons = []
        self._setup_menus()

        # 额外的UI按钮（避免每帧创建导致状态丢失）
        from ui import Button
        self.tutorial_back_btn = Button(640 - 100, 720 - 80, 200, 50, "返回", color=DARK_RED)
        self.gameover_back_btn = Button(640 - 100, 720 - 150, 200, 50, "返回菜单", color=DARK_RED)

        self.story_progress = 0
        self.boss_kills = {"long": 0, "xiang": 0}
        self.ending_type = None
        self.has_vaccine = False

        self.tutorial_step = 0
        self.tutorial_texts = [
            "欢迎来到丧尸幸存者！",
            "WASD/左摇杆移动，鼠标/右摇杆瞄准，左键/射击按钮攻击",
            "击败敌人获得经验，升级选择技能",
            "防爆套装为主动技能，Tab切换选中，G释放",
            "盾牌有观察窗，受损过多会破碎",
            "钩爪为独立主动技能，升级后射程更远、可连射、命中爆炸",
            "尸潮会定期来袭，准备好面对无尽的黑暗...",
            "找到疫苗可以拯救你的朋友...",
            "祝你好运，幸存者！"
        ]

        # 资源管理器
        self.assets = AssetManager(base_path)
        self.assets.print_status()
        # 应用配置的音量
        self.assets.set_sound_volume(self.config.sound_volume)
        self.assets.set_music_volume(self.config.music_volume)

        # 全局记录系统
        self.records = GameRecords(base_path)
        # 首张故事地图默认解锁（供局外直接选图）
        try:
            if not self.records.is_map_unlocked(MapType.SCHOOL.name):
                self.records.unlock_map(MapType.SCHOOL.name)
        except Exception:
            pass
        self.session = None

        #成就页面滚动
        self.ach_scroll_offset = 0
        self._ach_touch_last_y = None
        #成就解锁toast队列
        self.ach_toast_queue = []
        # 实时成就检查节流计时器
        self._ach_check_timer = 0.0
        #成就返回按钮
        self.ach_back_btn = Button(640 -100, 720 -80, 200,50,"返回菜单",color=DARK_RED)

        self.renderer = Renderer(self.screen, self)
        logger.info("游戏初始化完成")

    def _update_scale(self):
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        self.scale = min(sw / BASE_WIDTH, sh / BASE_HEIGHT)
        self.scaled_width = sw
        self.scaled_height = sh
        logger.debug(f"缩放更新: scale={self.scale:.3f}, {sw}x{sh}")

    def _apply_character_bonuses2(self):
        """应用玩家2的局外角色加成"""
        cfg = CHARACTERS.get(getattr(self, 'selected_character2', None))
        if not cfg or not self.player2:
            return
        p = self.player2
        lvl = self.records.get_character_level(getattr(self, 'selected_character2'))
        scale_lvl = 1 + (lvl - 1) * 0.2
        hb = int(cfg.get("hp_bonus", 0) * scale_lvl)
        if hb:
            p.max_hp += hb
            p.hp = min(p.hp + hb, p.max_hp)
        p.base_speed += cfg.get("speed_bonus", 0) * scale_lvl
        p.speed = p.base_speed
        p.damage_multiplier *= (1 + cfg.get("damage_bonus", 0))
        p.crit_bonus_add += cfg.get("crit_bonus", 0)
        p.health_regen += cfg.get("regen", 0) * scale_lvl
        p.dmg_reduce += cfg.get("dmg_reduce", 0)
        p.char_name = getattr(self, 'selected_character2')

    def is_multiplayer_active(self):
        """是否处于双人/联机游玩中"""
        return bool(self.player2 is not None)

    def is_network_client_render(self):
        """是否为网络客户端游玩渲染（快照渲染，无本地世界）"""
        return self.multiplayer_mode == "network" and self.net_role == "client" and self.state == GameState.NET_CLIENT_PLAY

    def _setup_client_controls(self):
        """网络客户端输入控件（全屏布局，单人同款）"""
        from ui import VirtualJoystick, AimButton, TouchButton
        self.client_joystick = VirtualJoystick(120, BASE_HEIGHT - 120, 70)
        self.client_aim = AimButton(780, BASE_HEIGHT - 145, 62)
        self.client_shoot = TouchButton(780, BASE_HEIGHT - 145, 62, "射击", RED)
        self.client_skill = TouchButton(580, BASE_HEIGHT - 320, 42, "技能", BLUE)
        self._client_finger_ids = set()

    def _get_p2_local_input(self):
        """同屏双人：P2 键控输入（方向键+J/K/L）"""
        keys = pygame.key.get_pressed()
        mx = (1 if keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_LEFT] else 0)
        my = (1 if keys[pygame.K_DOWN] else 0) - (1 if keys[pygame.K_UP] else 0)
        shoot = bool(keys[pygame.K_j] or keys[pygame.K_k])
        skill = bool(keys[pygame.K_u])
        throw = bool(keys[pygame.K_o])
        sprint = bool(keys[pygame.K_LSHIFT])
        return mx, my, shoot, skill, throw, sprint

    def start_game(self):
        logger.info("开始新游戏")
        # 初始化游戏会话记录
        self.session = self.records.on_game_start(self.config.difficulty, self.config.game_mode)
        self.session.set_difficulty(self.config.difficulty)
        self.session.set_mode(self.config.game_mode)
        # 播放游戏音乐
        # 播放地图专属音乐
        map_name = self.world.map_type.name.lower() if hasattr(self.world, 'map_type') else 'school'
        map_music = MAP_MUSIC_MAP.get(map_name, 'school')
        self.assets.play_music(map_music)
        self._current_map_music = map_music
        self._music_context = 'explore'  # explore / boss / horde / tension
        try:
            # 故事模式：从局外选定地图开始；未指定则从第一张未通关地图开始
            if self.config.game_mode == GameMode.STORY:
                if self.selected_map_for_story is not None and self.records.is_map_unlocked(self.selected_map_for_story.name):
                    self.current_map = self.selected_map_for_story
                else:
                    self.current_map = self._first_available_story_map()
                self.current_map_index = STORY_MAP_ORDER.index(self.current_map) if self.current_map in STORY_MAP_ORDER else 0
                self.map_config = MAP_CONFIGS[self.current_map]
                self.story_collected_fragments = set(self.records.get_collected_story())
                self.story_pending_fragments = []  # 待刷新的剧情片段
                self.story_fragment_items = []  # 地图上的剧情收集物
                self.special_event_triggered = False
                self.special_event_active = False
                self.map_time_elapsed = 0.0
                self.map_transition_timer = 0.0
                logger.info(f"故事模式开始，当前地图: {self.map_config['name']}")
            else:
                self.current_map = MapType.SCHOOL
                self.map_config = MAP_CONFIGS[MapType.SCHOOL]

            self.world = GameWorld(map_type=self.current_map)
            logger.info(f"世界创建完成，地图: {self.map_config['name']}")

            self.player = Player(0, 0, start_weapon=self.selected_weapon, start_weapon_level=self.selected_weapon_level)
            # 双人模式：P1 实际武器/角色来自第一轮选择
            if self.multiplayer_mode in ("same_screen", "network"):
                if getattr(self, 'selected_weapon_p1', None):
                    self.player = Player(0, 0, start_weapon=self.selected_weapon_p1,
                                         start_weapon_level=self.selected_weapon_level)
                if getattr(self, 'selected_char_p1', None):
                    self.selected_character = self.selected_char_p1
            # 加载跨局永久符文(可升级)到本局符文管理器
            self._load_permanent_runes()
            # 应用符文属性加成（需在玩家初始化后）
            self._apply_rune_bonuses()
            # 应用局外角色特殊能力
            self._apply_character_bonuses()
            # Mod 游戏开始钩子
            try:
                trigger_hook(HOOK_GAME_START, self)
            except Exception:
                pass
            # 解锁所选武器图鉴
            try:
                _cu = codex_unlock_manager.unlock_weapon(self.selected_weapon.name)
                if _cu:
                    self._codex_unlock_toast(_cu, self.selected_weapon.name)
            except Exception:
                pass
                    # 问题3a: 应用难度配置到玩家初始资源
            try:
                from config import DIFFICULTY_CONFIG
                diff_cfg = DIFFICULTY_CONFIG.get(self.config.difficulty, {})
                if diff_cfg:
                    self.player.max_hp = int(100 * diff_cfg.get("player_hp_mult", 1.0))
                    self.player.hp = self.player.max_hp
                    self.player.damage_mult = diff_cfg.get("player_damage_mult", 1.0)
                    self.player.exp_mult = diff_cfg.get("exp_mult", 1.0)
                    self._difficulty_drop_mult = diff_cfg.get("drop_rate_mult", 1.0)
                    logger.info(f"难度应用: {self.config.difficulty}, HP={self.player.max_hp}, 伤害倍率={self.player.damage_mult}")
            except Exception as e:
                logger.warning(f"难度配置应用失败: {e}")
                self._difficulty_drop_mult = 1.0
            logger.info(f"玩家创建: ({self.player.x}, {self.player.y})")

            self.horde_manager = HordeManager(self.config.game_mode, self.config.difficulty)
            self._was_horde = False
            self.last_boss_death_pos = None
            self.camera = Camera(BASE_WIDTH, BASE_HEIGHT)
            self.camera.shake_enabled = self.config.screen_shake
            # ===== 多人模式：创建第二位玩家 + 第二摄像机 =====
            if self.multiplayer_mode in ("same_screen", "network"):
                # 同屏双人：每半屏视口宽 = 半屏，摄像机中心偏移应为半宽（否则玩家会贴在全屏中心）
                if self.multiplayer_mode == "same_screen":
                    self.camera = Camera(BASE_WIDTH // 2, BASE_HEIGHT)
                    self.camera.shake_enabled = self.config.screen_shake
                p1_w = getattr(self, 'selected_weapon_p1', None) or self.selected_weapon
                p2_w = getattr(self, 'selected_weapon_p2', None) or self.selected_weapon
                p2_char = getattr(self, 'selected_char_p2', None)
                try:
                    self.player2 = Player(self.player.x + 60, self.player.y, start_weapon=p2_w,
                                          start_weapon_level=getattr(self, 'selected_weapon_p2_level', 1))
                    if p2_char:
                        self.selected_character2 = p2_char
                        self._apply_character_bonuses2()
                except Exception as e:
                    logger.warning(f"创建玩家2失败: {e}")
                    self.player2 = None
                self.camera2 = Camera(BASE_WIDTH // 2, BASE_HEIGHT)  # 同屏半屏视口宽=半宽
                self.camera2.shake_enabled = self.config.screen_shake
                self._setup_multiplayer_controls()
            else:
                self.player2 = None
                self.camera2 = None
                self.p2_controls = None
                # 单机：刷新触控控件并应用最新 HUD 布局（保存布局后直接开局也能生效）
                self._setup_touch_controls()
                self._apply_hud_layout()
            self.particles = ParticleSystem()
            self.lifesteal_flash = 0.0  # 吸血屏幕效果强度(0-1)
            # 屏幕血渍系统（持久化，受伤时添加，随时间淡出流淌）
            self.screen_blood = []  # [(x, y, radius, alpha, drip_speed, drip_offset)]
            self.war_cry_timer = 0.0  # 战吼状态计时器
            self.last_touch_pos = None  # 最后触摸位置，用于buff详情
            self._trauma_cache = None  # 缓存边缘渐变
            self.dialogue = DialogueSystem()

            self.enemies = []
            self.projectiles = []
            self.exp_orbs = []
            self.damage_numbers = []
            self.floating_texts = []
            self.slash_arcs = []
            self.sweep_rings = []
            self.enemy_projectiles = []
            self.smoke_zones = []
            self.grenades = []

            self.story_progress = 0
            self.boss_kills = {"long": 0, "xiang": 0}
            self.ending_type = None
            self.has_vaccine = False

            # 重置技能系统
            self.selected_skill = SkillType.GRENADE
            self.skill_wheel_active = False

            # 重置防爆套装动画
            self.riot_anim_timer = 0
            self.riot_anim_state = "idle"
            self.riot_long_press_timer = 0

            # 重置武器切换
            self.weapon_switch_cooldown = 0

            # 重置钩爪
            self.grapple_aiming = False

            self.state = GameState.PLAYING
            self._start_intro_dialogue()
            logger.info("游戏状态切换到PLAYING")
        except Exception as e:
            logger.log_exception(e)

    def _execute_skill(self, skill_type):
        """执行具体技能效果"""
        if skill_type == SkillType.DASH:
            return self._skill_dash()
        elif skill_type == SkillType.GRENADE:
            return self._skill_grenade()
        elif skill_type == SkillType.TURRET:
            return self._skill_turret()
        elif skill_type == SkillType.AIRSTRIKE:
            return self._skill_airstrike()
        elif skill_type == SkillType.SHIELD_BASH:
            return self._skill_shield_bash()
        elif skill_type == SkillType.GRAPPLE_PULL:
            return self._skill_grapple()
        elif skill_type == SkillType.TIME_SLOW:
            return self._skill_time_slow()
        elif skill_type == SkillType.OVERLOAD:
            return self._skill_overload()
        elif skill_type == SkillType.RIOT_GEAR:
            return self._toggle_riot_gear_skill()
        elif skill_type == SkillType.ICE_NOVA:
            return self._skill_ice_nova()
        elif skill_type == SkillType.BERSERK:
            return self._skill_berserk()
        elif skill_type == SkillType.PHANTOM_STRIKE:
            return self._skill_phantom_strike()
        elif skill_type == SkillType.SHOCKWAVE:
            return self._skill_shockwave()
        elif skill_type == SkillType.WAR_CRY:
            return self._skill_war_cry()
        elif skill_type == SkillType.PURIFY:
            return self._skill_purify()
        elif skill_type == SkillType.SCYTHE_DANCE:
            return self._skill_scythe_dance()
        elif skill_type == SkillType.MINIGUN_OVERDRIVE:
            return self._skill_minigun_overdrive()
        elif skill_type == SkillType.RAILGUN_ANNIHILATION:
            return self._skill_railgun_annihilation()
        return False

    def _throw_skill_grenade(self, target_x, target_y):
        """技能手雷：抛物线投射物，根据技能等级解锁附魔"""
        if not hasattr(self, 'grenades_in_flight'):
            self.grenades_in_flight = []
        dx = target_x - self.player.x
        dy = target_y - self.player.y
        total_dist = math.hypot(dx, dy)
        speed = total_dist / 1.1 if total_dist > 0 else 300
        if total_dist > 0:
            vx = dx / total_dist * speed
            vy = dy / total_dist * speed
        else:
            vx, vy = 0, -300
        
        # 根据手雷技能等级累加附魔效果（高等级保留低等级效果）
        grenade_skill = self.player.skill_tree.get_skill(SkillType.GRENADE)
        skill_level = grenade_skill.current_level if grenade_skill else 1
        g_effects = ["frag"]  # 基础破片效果
        if skill_level >= 2:
            g_effects.append("fire")     # 燃烧区域+燃烧DOT
        if skill_level >= 3:
            g_effects.append("frost")    # 减速区域+减速Debuff
        if skill_level >= 4:
            g_effects.append("poison")   # 剧毒DOT
        if skill_level >= 5:
            g_effects.append("nuke")     # 核弹：范围+伤害大幅提升

        self.grenades_in_flight.append({
            "type": "frag",
            "effects": g_effects,
            "x": self.player.x, "y": self.player.y,
            "vx": vx, "vy": vy,
            "timer": 1.1,
            "target_x": target_x, "target_y": target_y,
        })
        self.assets.play_sound("grenade_throw")

    def _update_riot_animation(self, dt):
        """更新防爆套装装备/卸盾动画"""
        if self.riot_anim_state == "idle":
            return

        self.riot_anim_timer -= dt
        if self.riot_anim_timer <= 0:
            if self.riot_anim_state == "equipping":
                self.player.riot_gear.equip()
                self.player.riot_gear_cooldown = self.player.riot_gear_equip_cooldown
                self.floating_texts.append(FloatingText(
                    self.player.x, self.player.y - 40, 
                    "防爆套装已装备!", color=GREEN, lifetime=1.5
                ))
            elif self.riot_anim_state == "unequipping":
                self.player.riot_gear.unequip()
                self.floating_texts.append(FloatingText(
                    self.player.x, self.player.y - 40, 
                    "防爆套装已卸下", color=GRAY, lifetime=1.5
                ))
            self.riot_anim_state = "idle"
            self.riot_anim_timer = 0

    def update(self, dt):
        # 状态变化检测：切换状态时先合成 up（释放仍按住的控件），回到 PLAYING 再全量重置
        if not hasattr(self, '_last_state'):
            self._last_state = self.state
        state_changed = (self.state != self._last_state)
        if state_changed:
            self._synthesize_touch_ups()
            # 离开 PLAYING 也要全量重置触控（多指操控中按菜单返回时，
            # 仍按住的攻击/摇杆手指的 up 事件不会被 _update_playing 消费，
            # 必须清掉控件状态，否则攻击摇杆会持续 is_shooting 卡死）
            if self.state == GameState.PLAYING or self._last_state == GameState.PLAYING:
                self._reset_touch_state()
        self._last_state = self.state

        # 时间减缓效果
        if hasattr(self, 'time_slow_active') and self.time_slow_active:
            self.time_slow_timer -= dt
            if self.time_slow_timer <= 0:
                self.time_slow_active = False
            else:
                dt *= 0.3

        if self.state == GameState.PLAYING:
            self._update_playing(dt)
            # 主机广播世界快照给客户端
            if self.multiplayer_mode == "network" and self.net_role == "host" and self.net_started:
                self._net_send_snapshot()
            # 开发者调试面板
            if self.dev_mode and self.dev_panel_open:
                self._update_dev_panel(pygame.mouse.get_pos(), pygame.mouse.get_pressed(), self.touch_events, self.scale)
        elif self.state == GameState.NET_CLIENT_PLAY:
            self._update_net_client(dt)
        elif self.state == GameState.DIALOGUE:
            self.dialogue.update(dt)
        elif self.state == GameState.SKILL_SELECT:
            if self.particles:
                self.particles.update(dt)
        elif self.state == GameState.RECORDS:
            pass
        elif self.state == GameState.SKILL_TREE:
            if hasattr(self, 'skill_tree_renderer') and self.skill_tree_renderer:
                mouse_pos = pygame.mouse.get_pos()
                mouse_pressed = pygame.mouse.get_pressed()
                touch_events = getattr(self, 'touch_events', [])
                self.skill_tree_renderer.handle_input(mouse_pos, mouse_pressed, touch_events, self.scale)
                # 返回按钮：回到暂停菜单
                if self.skill_tree_renderer.back_requested:
                    self.skill_tree_renderer.back_requested = False
                    self.skill_tree_renderer.hide()
                    self.state = GameState.PAUSED
                    logger.info("技能树返回暂停菜单")

        # 更新轮盘动画
        if self.skill_wheel_active:
            self.skill_wheel.update(dt)
        if self.weapon_wheel_active:
            self.weapon_wheel.update(dt)

        # 更新炮塔、空袭、黑洞、医疗舱
        self._update_turrets(dt)
        self._update_airstrikes(dt)
        self._update_melee_attack(dt)
        self._update_grenades(dt)
        self._update_enemy_throwables(dt)
        self._update_fire_zones(dt)
        self._update_smoke_zones(dt)
        # 实时成就结算（节流0.5s，不等到游戏结束）
        self._ach_check_timer -= dt
        if self._ach_check_timer <= 0:
            self._check_achievements_realtime()
            self._ach_check_timer = 0.5
        self._update_black_holes(dt)
        self._update_medic_pods(dt)
        # 双人救援：每帧结算倒地/救援（全倒地时在此结束游戏）
        if self.is_multiplayer_active() and self._update_rescue(dt):
            self._trigger_multiplayer_game_over()

    def draw(self):
        self.renderer.render()

    def run(self):
        logger.info("游戏主循环开始")
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            dt = min(dt, 0.05)
            # 开发者模式：游戏速度倍率
            if hasattr(self, 'dev_time_scale') and self.dev_time_scale and self.dev_time_scale != 1.0:
                dt *= self.dev_time_scale

            try:
                self.handle_events()
                self.update(dt)
                self.draw()
            except Exception as e:
                logger.log_exception(e)
                self.screen.fill(BLACK)
                error_text = self.font.render(f"错误: {str(e)}", True, RED)
                self.screen.blit(error_text, (50, self.scaled_height // 2))
                pygame.display.flip()
                pygame.time.wait(3000)
                self.running = False

        logger.info("游戏退出")
        # 退出时自动保存对局
        if self.state == GameState.PLAYING:
            self.save_game_state()
        pygame.quit()
        try:
            sys.exit(0)
        except:
            pass
