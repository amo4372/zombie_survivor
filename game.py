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

class Game:
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
            base_path = os.path.dirname(os.path.abspath(__file__))
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

    def _setup_touch_controls(self):
        """触控按钮位置调整 - 重新布局避免重叠，三列两行"""
        # 移动摇杆 - 左下角
        self.joystick = VirtualJoystick(120, BASE_HEIGHT - 120, 70)
        # 攻击/瞄准摇杆 - 右下角
        self.aim_button = AimButton(BASE_WIDTH - 500, BASE_HEIGHT - 145, 62)

        # 触控按钮 - 三列两行布局，避免重叠
        self.touch_buttons = {
            "shoot": TouchButton(BASE_WIDTH - 500, BASE_HEIGHT - 145, 62, "射击", RED),
            "pause": TouchButton(60, 55, 38, "II", GRAY),
            "sprint": TouchButton(210, BASE_HEIGHT - 130, 40, "疾跑", AMBER),
        }
        # 技能切换按钮（右上列）
        self.skill_selector = SkillSelector(BASE_WIDTH - 220, BASE_HEIGHT - 320, 42)
        # 技能释放按钮（右下列）
        self.skill_caster = SkillCaster(BASE_WIDTH - 130, BASE_HEIGHT - 145, 52)
        # 投掷物切换按钮（中上列）
        self.throwable_switch_btn = TouchButton(BASE_WIDTH - 370, BASE_HEIGHT - 320, 42, "投掷", ORANGE)
        # 投掷物释放器（中下列，复用SkillCaster的瞄准逻辑）
        self.throwable_caster = SkillCaster(BASE_WIDTH - 310, BASE_HEIGHT - 145, 48)
        # 触控模式下显示按钮，键盘模式下隐藏
        self.throwable_caster.visible = (self.config.control_mode == ControlMode.TOUCH or getattr(self, 'is_android', False))
        # 投掷物选择系统
        self.throwable_types = ["incendiary", "smoke", "cluster", "emp"]
        self.throwable_names = {"incendiary": "燃烧弹", "smoke": "烟雾弹", "cluster": "集束炸弹", "emp": "EMP脉冲弹"}
        self.throwable_colors = {"incendiary": (255, 100, 0), "smoke": (160, 160, 160), "cluster": (255, 165, 0), "emp": (0, 200, 255)}
        self.selected_throwable = "incendiary"  # 当前选中的投掷物
        # Q键投掷物状态
        self.key_q_press_start = 0
        self.key_q_held = False
        self.q_aim_started = False
        self.key_q_long_threshold = 0.3  # 长按阈值，与G键一致
        self.throwable_max_dist = 450  # 投掷物最大距离
        self._apply_hud_layout()
        logger.info("触控控件初始化完成")

    def _apply_hud_layout(self):
        """应用用户自定义的HUD按钮布局（config.hud_layout: {name: [x, y]} 逻辑坐标）"""
        self._apply_layout_to(self.config.hud_layout or {})

    def _apply_layout_to(self, layout):
        """把布局字典应用到 P1 触控控件"""
        lay = layout or {}
        if not lay:
            return
        def _set(ctrl, key):
            if ctrl is not None and key in lay:
                try:
                    ctrl.base_x = int(lay[key][0])
                    ctrl.base_y = int(lay[key][1])
                except (TypeError, IndexError, ValueError):
                    pass
        _set(self.joystick, "joystick")
        _set(self.aim_button, "aim")
        _set(self.touch_buttons.get("shoot"), "shoot")
        _set(self.touch_buttons.get("pause"), "pause")
        _set(self.touch_buttons.get("sprint"), "sprint")
        _set(self.skill_selector, "skill_selector")
        _set(self.skill_caster, "skill_caster")
        _set(self.throwable_switch_btn, "throwable_switch")
        _set(self.throwable_caster, "throwable_caster")

    def _save_hud_layout(self, target="单机"):
        """保存触控布局（单机→hud_layout / P1→mp_p1_layout / P2→p2_hud_layout）"""
        layout = {}
        def _put(ctrl, key):
            if ctrl is not None:
                layout[key] = [int(ctrl.base_x), int(ctrl.base_y)]
        if target == "P2" and self.p2_controls:
            c2 = self.p2_controls
            _put(c2["joystick"], "joystick")
            _put(c2["aim"], "aim")
            _put(c2["shoot"], "shoot")
            _put(c2["pause"], "pause")
            _put(c2["sprint"], "sprint")
            _put(c2["skill_selector"], "skill_selector")
            _put(c2["skill_caster"], "skill_caster")
            _put(c2["throwable_switch"], "throwable_switch")
            _put(c2["throwable_caster"], "throwable_caster")
            self.config.p2_hud_layout = layout
        elif target == "P1":
            _put(self.joystick, "joystick")
            _put(self.aim_button, "aim")
            _put(self.touch_buttons.get("shoot"), "shoot")
            _put(self.touch_buttons.get("pause"), "pause")
            _put(self.touch_buttons.get("sprint"), "sprint")
            _put(self.skill_selector, "skill_selector")
            _put(self.skill_caster, "skill_caster")
            _put(self.throwable_switch_btn, "throwable_switch")
            _put(self.throwable_caster, "throwable_caster")
            self.config.mp_p1_layout = layout
        else:
            _put(self.joystick, "joystick")
            _put(self.aim_button, "aim")
            _put(self.touch_buttons.get("shoot"), "shoot")
            _put(self.touch_buttons.get("pause"), "pause")
            _put(self.touch_buttons.get("sprint"), "sprint")
            _put(self.skill_selector, "skill_selector")
            _put(self.skill_caster, "skill_caster")
            _put(self.throwable_switch_btn, "throwable_switch")
            _put(self.throwable_caster, "throwable_caster")
            self.config.hud_layout = layout
        self.config.save()
        logger.info(f"HUD布局已保存({target}): {len(layout)} 个控件")

    def _reset_hud_layout(self, target="单机"):
        """重置HUD布局为默认（单机→hud_layout / P1→mp_p1_layout / P2→p2_hud_layout）"""
        if target == "P2" and self.p2_controls:
            self.config.p2_hud_layout = {}
            self.config.save()
            self._setup_multiplayer_controls()
            logger.info("P2 HUD布局已重置为默认")
            return
        if target == "P1":
            self.config.mp_p1_layout = {}
            self.config.save()
            self._setup_multiplayer_controls()
            logger.info("P1 HUD布局已重置为默认")
            return
        self.config.hud_layout = {}
        self.config.save()
        self._setup_touch_controls()
        logger.info("HUD布局已重置为默认")

    # ===== 多人模式：P2 控件与玩家 =====
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

    def _update_net_client(self, dt):
        """网络客户端：采集本地输入发送给主机，检测断开"""
        if not self.net_client:
            self.state = GameState.NET_MULTIPLAYER
            return
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
            self.net_client.send_input({
                "mx": round(float(mx), 3), "my": round(float(my), 3),
                "shoot": bool(shoot), "skill": bool(skill),
                "throw": False, "sprint": False,
            })
        # 主机断开 → 返回联机界面
        if not self.net_client.connected:
            self.floating_texts.append(FloatingText(0, 0, "与主机断开连接", color=CRIMSON, lifetime=2.0))
            self._net_stop()
            self.state = GameState.NET_MULTIPLAYER

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
            snap = {
                "started": True,
                "time_left": getattr(self, 'time_left', 0),
                "wave": getattr(self, 'wave_count', 0) if hasattr(self, 'wave_count') else 0,
                "players": [
                    {"x": round(self.player.x, 1), "y": round(self.player.y, 1), "hp": int(self.player.hp),
                     "max_hp": int(self.player.max_hp), "alive": self.player.alive,
                     "downed": bool(getattr(self.player, 'downed', False)),
                     "weapon": self.player.get_current_weapon().name if self.player.get_current_weapon() else "PISTOL"},
                    {"x": round(self.player2.x, 1) if self.player2 else round(self.player.x, 1),
                     "y": round(self.player2.y, 1) if self.player2 else round(self.player.y, 1),
                     "hp": int(self.player2.hp) if self.player2 else 0,
                     "max_hp": int(self.player2.max_hp) if self.player2 else 1,
                     "alive": bool(self.player2 and self.player2.alive),
                     "downed": bool(self.player2 and getattr(self.player2, 'downed', False)),
                     "weapon": self.player2.get_current_weapon().name if (self.player2 and self.player2.get_current_weapon()) else "PISTOL"},
                ],
                "enemies": enems,
                "projectiles": projs,
                "effects": effects,
            }
            self.net_host.send_snapshot({"type": "snapshot", "data": snap})
        except Exception as e:
            logger.warning(f"快照发送失败: {e}")

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
        for dmg, dtype in getattr(p2, 'buff_damage_events', []):
            if dmg > 0:
                self.damage_numbers.append(DamageNumber(
                    p2.x + random.uniform(-15, 15), p2.y - 20, dmg, damage_type=dtype))

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

    def _spawn_grenade(self, x, y, angle_deg, player):
        """生成手雷（P2 用）"""
        ang = math.radians(angle_deg)
        proj = Projectile(x, y, math.cos(ang) * 12, math.sin(ang) * 12,
                          250 * player.damage_multiplier, 400, ORANGE, 6,
                          explosive=True, explosion_radius=180, gravity=0.1)
        self.projectiles.append(proj)

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

    def _start_auto_update_check(self):
        """启动时后台检查更新 + 资源完整性（不阻塞进入菜单）"""
        def _worker():
            try:
                # 1) 资源完整性校验（后台）
                try:
                    import updater as _up
                    missing, corrupted, status = _up.verify_assets()
                    if status == "ok" and (missing or corrupted):
                        self.asset_issues = (missing[:5], corrupted[:5])
                except Exception:
                    pass
                # 2) 自动检查新版本
                if not self.config.update_auto_check:
                    return
                if self.update_notice_dismissed:
                    return
                try:
                    import updater as _up
                    _up.clear_release_notes_cache()
                    result = _up.check_for_updates(timeout=8)
                    if result:
                        latest, url, changelog = result
                        if _up.is_newer_version(latest, self.current_version_str):
                            self.update_notice = (latest, changelog)
                except Exception:
                    pass
            except Exception:
                pass
        import threading
        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _dismiss_update_notice(self):
        """用户点『稍后』：本次运行不再弹窗"""
        self.update_notice_dismissed = True
        self.update_notice = None

    def _apply_update_now(self):
        """用户点『立即更新』：进入更新界面并自动开始下载应用"""
        self.update_notice = None
        self.state = GameState.UPDATE
        try:
            import updater as _up
            _up.perform_full_update(
                progress_cb=None,
                status_cb=lambda s: setattr(self, 'update_status_text', s),
            )
        except Exception:
            pass

    def _setup_menus(self):
        cx = BASE_WIDTH // 2 - 100
        self.menu_buttons = [
            Button(cx, 180, 200, 45, "继续游戏", color=CYAN),
            Button(cx, 235, 200, 45, "开始游戏", color=GREEN),
            Button(cx, 345, 200, 45, "剧情资料库", color=GOLD),
            Button(cx, 400, 200, 45, "图鉴", color=CYAN),
            Button(cx, 455, 200, 45, "记录", color=GOLD),
            Button(cx, 510, 200, 45, "成就", color=AMBER),
            Button(cx, 565, 200, 45, "Mod管理", color=PURPLE),
            Button(cx, 620, 200, 45, "检查更新", color=GREEN),
            Button(cx, 675, 200, 45, "设置", color=GRAY),
            Button(cx, 730, 200, 45, "教程", color=BLUE),
            Button(cx, 785, 200, 45, "退出", color=RED),
            Button(cx, 785, 200, 45, "更新说明", color=GRAY),
        ]
        # 模式选择按钮
        self.mode_select_buttons = [
            Button(cx, 250, 220, 55, "故事模式", color=GOLD),
            Button(cx, 330, 220, 55, "无尽模式", color=CRIMSON),
            Button(cx, 410, 220, 55, "限时模式", color=BLUE),
            Button(cx, 500, 200, 45, "返回", color=RED),
        ]
        # 开始游戏分流：单人 / 多人
        self.play_select_buttons = [
            Button(cx, 250, 220, 55, "单人游戏", color=GREEN),
            Button(cx, 330, 220, 55, "多人游戏", color=CYAN),
            Button(cx, 420, 200, 45, "返回", color=RED),
        ]
        # 多人游戏：同屏双人 / 网络联机
        self.multiplayer_select_buttons = [
            Button(cx, 240, 240, 55, "同屏双人", color=GOLD),
            Button(cx, 320, 240, 55, "网络联机", color=BLUE),
            Button(cx, 420, 200, 45, "返回", color=RED),
        ]
        # 网络联机：创建房间 / 加入房间
        self.net_mp_buttons = [
            Button(cx, 240, 240, 55, "创建房间(主机)", color=GREEN),
            Button(cx, 320, 240, 55, "加入房间(客户端)", color=GOLD),
            Button(cx, 420, 200, 45, "返回", color=RED),
        ]
        # 剧情资料库相关
        self.story_archive_scroll = 0
        self.story_archive_selected = None
        self.story_back_btn = Button(640 - 100, 720 - 60, 200, 45, "返回菜单", color=DARK_RED)
        # 图鉴相关
        self.codex_tab = "monster"  # monster / weapon
        self.codex_category = "全部"
        self.codex_scroll = 0
        self.codex_selected = None
        self.codex_back_btn = Button(640 - 100, 720 - 60, 200, 45, "返回菜单", color=DARK_RED)
        # Mod管理相关
        self.mod_manager_scroll = 0
        self.mod_selected = None
        self.mod_list_cache = []
        # 绑定 Mod API 到游戏实例
        if hasattr(mod_loader, 'mod_api'):
            mod_loader.mod_api._bind_game(self)
        self.codex_tab_buttons = [
            Button(120, 80, 120, 40, "怪物图鉴", color=CRIMSON),
            Button(260, 80, 120, 40, "武器图鉴", color=CYAN),
            Button(400, 80, 120, 40, "世界观", color=PURPLE),
        ]
        self.codex_world_selected = "origin"  # 当前选中的世界观条目
        # 难度选择按钮
        self.difficulty_select_buttons = [
            Button(cx, 200, 220, 55, "简单", color=GREEN),
            Button(cx, 275, 220, 55, "普通", color=GOLD),
            Button(cx, 350, 220, 55, "困难", color=ORANGE),
            Button(cx, 425, 220, 55, "地狱", color=CRIMSON),
            Button(cx, 520, 200, 45, "返回", color=RED),
        ]
        # 设置按钮（游戏功能设置，不含难度）
        self.settings_buttons = [
            Button(cx, 150, 200, 45, "音效音量: 70%", color=GRAY),
            Button(cx, 205, 200, 45, "音乐音量: 50%", color=GRAY),
            Button(cx, 260, 200, 45, "画质: 均衡", color=GRAY),
            Button(cx, 315, 200, 45, "外部图片: 开", color=GRAY),
            Button(cx, 370, 200, 45, "Buff特效: 开", color=GRAY),
            Button(cx, 425, 200, 45, "伤害数字: 开", color=GRAY),
            Button(cx, 480, 200, 45, "屏幕震动: 开", color=GRAY),
            Button(cx, 535, 200, 45, "控制: 键控", color=GRAY),
            Button(cx, 590, 200, 45, "日志记录: 开", color=GRAY),
            Button(cx, 640, 200, 50, "HUD布局", color=BLUE),
            Button(cx, 695, 200, 50, "返回", color=RED),
        ]
        self.pause_buttons = [
            Button(cx, 170, 200, 50, "继续", color=GREEN),
            Button(cx, 235, 200, 50, "符文", color=GOLD),
            Button(cx, 300, 200, 50, "技能树", color=BLUE),
            Button(cx, 365, 200, 50, "设置", color=GRAY),
            Button(cx, 430, 200, 50, "返回菜单", color=RED),
            Button(cx, 495, 200, 50, "开发者面板", color=(80, 180, 90)),
        ]
        self.settings_from_pause = False  # 标记设置是否从暂停菜单进入
        # 符文查看界面状态
        self.rune_view_scroll = 0
        self.rune_selected = None  # 选中的符文类型(RuneType)，用于查看详情
        # 更新界面相关
        self.update_status_text = ""
        self.update_progress = 0.0
        self.update_back_btn = Button(640 - 100, 720 - 60, 200, 45, "返回菜单", color=DARK_RED)
        self.update_check_btn = Button(640 - 100, 300, 200, 50, "检查更新", color=GREEN)
        self.update_download_btn = Button(640 - 100, 370, 200, 50, "下载并更新", color=CYAN)
        # 更新说明界面
        self.update_notes_scroll = 0
        self.update_notes_version = None
        self.update_notes_text = "正在加载更新说明..."
        self.current_version_str = updater.get_current_version()
        logger.info("菜单按钮初始化完成")
        # v2.0.8：启动时自动检查更新（后台线程，不阻塞菜单）
        try:
            self._start_auto_update_check()
        except Exception:
            pass

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
            with open("savegame.zss", "wb") as f:
                f.write(encrypted)
            # 删除旧的明文存档（如果存在）
            import os
            if os.path.exists("savegame.json"):
                try:
                    os.remove("savegame.json")
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
        return os.path.exists("savegame.zss") or os.path.exists("savegame.json")

    def load_game_state(self):
        """加载存档并开始游戏（从存档恢复）"""
        import json
        try:
            if not self.has_saved_game():
                return False
            import os
            # 优先加载加密存档，兼容明文旧存档
            if os.path.exists("savegame.zss"):
                with open("savegame.zss", "rb") as f:
                    encrypted = f.read()
                try:
                    decrypted = _save_decrypt(encrypted)
                    save_data = json.loads(decrypted.decode('utf-8'))
                    logger.info("加密存档解密成功")
                except Exception as e:
                    logger.log_exception(e)
                    logger.error("加密存档解密失败，尝试明文存档")
                    if os.path.exists("savegame.json"):
                        with open("savegame.json", "r", encoding="utf-8") as f:
                            save_data = json.load(f)
                    else:
                        return False
            else:
                # 明文旧存档
                with open("savegame.json", "r", encoding="utf-8") as f:
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
        for save_file in ["savegame.zss", "savegame.json"]:
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
                self.ach_toast_queue.append({"key": key, "desc": desc, "timer": 4.0})
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
        ending_map = {
            "save_both": "perfect",
            "save_long": "save_long",
            "save_xiang": "save_xiang",
            "save_none": "tragic",
            "kill_both": "kill_both",
            "let_go": "let_go"
        }
        self.ending_type = ending_map.get(effect, "kill_both")
        # 记录结局
        if self.session:
            self.session.set_ending(self.ending_type)

    # ========== 技能系统 ==========
    # 传说级武器 → 专属技能映射（持有对应武器自动解锁，等级随武器等级成长）
    LEGENDARY_WEAPON_SKILLS = {
        "SCYTHE": SkillType.SCYTHE_DANCE,
        "MINIGUN": SkillType.MINIGUN_OVERDRIVE,
        "RAILGUN": SkillType.RAILGUN_ANNIHILATION,
    }

    def _sync_legendary_skill_level(self):
        """传说专属技能等级与当前武器等级同步"""
        if not self.player:
            return None
        try:
            w = self.player.get_current_weapon()
            ls = self.LEGENDARY_WEAPON_SKILLS.get(w.weapon_type.name)
            if ls:
                sk = self.player.skill_tree.get_skill(ls)
                if sk:
                    sk.current_level = min(sk.max_level, max(1, int(getattr(w, 'level', 1))))
                    return ls
        except Exception:
            pass
        return None

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
        """获取某玩家的已解锁主动技能列表（基础手雷恒可用 + 技能树主动 + 传说武器专属）"""
        if not player:
            return [SkillType.GRENADE]
        skills = list(player.skill_tree.get_unlocked_active_skills())
        if SkillType.GRENADE not in skills:
            skills.insert(0, SkillType.GRENADE)
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
            SkillType.SHIELD_BASH: 120,
            SkillType.SHOCKWAVE: 150,
        }
        return distances.get(skill_type, 500)

    def _use_skill(self, skill_type):
        """使用指定技能"""
        try:
            trigger_hook(HOOK_SKILL_USE, skill_type, self.player)
        except Exception:
            pass
        if not self.player:
            return False
        if not self.player.can_act():
            return False
        self._sync_legendary_skill_level()  # 传说专属技能等级与武器同步

        skill = self.player.skill_tree.get_skill(skill_type)
        if not skill or (skill.current_level == 0 and skill_type != SkillType.GRENADE):
            # 基础手雷天生可用（0级=基础破片），其余技能需解锁
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

        # 检查并设置冷却
        cooldowns = {
            SkillType.DASH: 5.0, 
            SkillType.GRENADE: 8.0, 
            SkillType.TURRET: 15.0,
            SkillType.AIRSTRIKE: 20.0, 
            SkillType.SHIELD_BASH: 3.0,
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
            SkillType.SHOCKWAVE: 12.0,
            SkillType.WAR_CRY: 25.0,
            SkillType.PURIFY: 35.0,
            SkillType.SCYTHE_DANCE: 30.0,
            SkillType.MINIGUN_OVERDRIVE: 25.0,
            SkillType.RAILGUN_ANNIHILATION: 35.0,
        }
        cd = cooldowns.get(skill_type, 10.0) * self.player.cooldown_mult

        # 执行技能效果
        success = self._execute_skill(skill_type)

        if success:
            if skill_type != SkillType.RIOT_GEAR:
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

    def _use_skill_aimed(self, skill_type, angle, distance_ratio=1.0):
        """使用带瞄准方向和距离的技能 - distance_ratio: 0.1~1.0"""
        if not self.player:
            return False
        if not self.player.can_act():
            return False
        self._sync_legendary_skill_level()  # 传说专属技能等级与武器同步

        skill = self.player.skill_tree.get_skill(skill_type)
        if not skill or (skill.current_level == 0 and skill_type != SkillType.GRENADE):
            # 基础手雷天生可用（0级=基础破片），其余技能需解锁
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
            SkillType.SHIELD_BASH: 3.0,
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
            SkillType.SHOCKWAVE: 12.0,
        }
        cd = cooldowns.get(skill_type, 10.0) * self.player.cooldown_mult

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
        else:
            success = self._execute_skill(skill_type)

        if success:
            if skill_type != SkillType.RIOT_GEAR:
                self.player.active_skills[skill_type] = cd
            skill_name = skill.name if skill else "未知技能"
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                f"使用 {skill_name}!", color=GOLD, lifetime=1.5
            ))
        return success

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

    def _skill_shield_bash(self):
        """盾牌肘击技能"""
        if not self.player.riot_gear.equipped:
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                "需要先装备防爆套装!", color=RED, lifetime=1.5
            ))
            return False
        self._perform_bash()
        return True

    def _skill_grapple(self):
        """钩爪技能（独立技能，无需防爆套装）"""
        self._perform_grapple()
        return True

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
        """超载模式技能"""
        self.player.damage_boost_timer = 8.0
        self.player.damage_boost_mult = 2.5
        self.particles.spawn_explosion(self.player.x, self.player.y, RED, 40)
        self.camera.shake(12, 0.5)
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
        """狂暴技能"""
        self.player.berserk_active = True
        self.player.damage_boost_timer = 10.0
        self.player.damage_boost_mult = 2.0
        self.player.fire_rate_mult *= 2.0
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, "狂暴!", color=RED, lifetime=2.0
        ))
        self.particles.spawn_explosion(self.player.x, self.player.y, RED, 35)
        self.camera.shake(10, 0.4)
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

    def _skill_shockwave(self):
        """冲击波 - 伤害/半径随技能等级缩放，满级附加眩晕"""
        sw_skill = self.player.skill_tree.get_skill(SkillType.SHOCKWAVE) if self.player else None
        if sw_skill and sw_skill.current_level > 0:
            sw_radius = int(sw_skill.get_effective_radius())
            sw_damage = int(sw_skill.get_effective_damage())
            is_max = sw_skill.is_maxed()
        else:
            sw_radius = 150
            sw_damage = 60
            is_max = False
        for enemy in self.enemies:
            dist = math.hypot(enemy.x - self.player.x, enemy.y - self.player.y)
            if dist < sw_radius and dist > 0:
                push_force = 200 if is_max else 100
                push_x = (enemy.x - self.player.x) / dist * push_force
                push_y = (enemy.y - self.player.y) / dist * push_force
                enemy.x += push_x
                enemy.y += push_y
                enemy.take_damage(sw_damage)
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, sw_damage, color=ORANGE))
                if is_max:
                    enemy.apply_buff(BuffType.STUN, duration=1.0)
                if not enemy.alive:
                    self._on_enemy_death(enemy)
        self.particles.spawn_explosion(self.player.x, self.player.y, ORANGE, 40)
        self.camera.shake(15, 0.5)
        # 冲击波扩散光环（可视范围提示，更帅）
        self.slash_arcs.append(SlashArc(
            self.player.x, self.player.y, 0.0, sw_radius,
            (255, 150, 40), lifetime=0.5, kind="scythe",
            start_radius=sw_radius * 0.35, end_angle_offset=6.2))
        self.slash_arcs.append(SlashArc(
            self.player.x, self.player.y, math.pi / 3, sw_radius * 1.15,
            (255, 200, 80), lifetime=0.4, kind="scythe",
            start_radius=sw_radius * 0.5, end_angle_offset=6.2))
        label = "地震波!" if is_max else "冲击波!"
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, label, color=ORANGE, lifetime=1.5
        ))
        return True

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

    def _skill_railgun_annihilation(self):
        """轨道炮专属·湮灭射线：超粗贯穿激光 + 命中爆炸"""
        lv = self._legendary_skill_level(SkillType.RAILGUN_ANNIHILATION)
        width = {1: 40, 2: 40, 3: 55, 4: 70, 5: 85}[lv]
        dmg = 300
        dmg *= (self.player.damage_multiplier *
                self.player.buff_manager.get_damage_mult() *
                getattr(self.player, 'damage_mult', 1.0))
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

    def _reset_touch_controls(self):
        """重置所有触控控件状态（状态切换时调用，防止摇杆卡死）"""
        try:
            if hasattr(self, 'joystick') and self.joystick:
                self.joystick.active = False
                self.joystick.touch_id = None
                self.joystick.knob_x = self.joystick.base_x
                self.joystick.knob_y = self.joystick.base_y
                self.joystick.value_x = 0
                self.joystick.value_y = 0
        except Exception:
            pass
        try:
            if hasattr(self, 'aim_button') and self.aim_button:
                self.aim_button.pressed = False
                self.aim_button.touch_id = None
                self.aim_button.just_pressed = False
                self.aim_button.just_released = False
        except Exception:
            pass
        try:
            if hasattr(self, 'skill_selector') and self.skill_selector:
                self.skill_selector.pressed = False
                self.skill_selector.touch_id = None
        except Exception:
            pass
        try:
            if hasattr(self, 'throwable_caster') and self.throwable_caster:
                self.throwable_caster.is_aiming = False
        except Exception:
            pass
        try:
            if hasattr(self, 'skill_tree_renderer') and self.skill_tree_renderer:
                self.skill_tree_renderer._dragging = False
        except Exception:
            pass

    def handle_events(self):
        # ===== 统一事件收集（所有状态共享，避免重复消费导致事件丢失）=====
        all_events = pygame.event.get()
        self.touch_events = []
        # 预处理：将所有 FINGER 事件和鼠标事件统一转换为 touch_events（dict 格式）
        # Windows 触控一体机（班班通等）的触摸会被 SDL 同时合成 FINGER 与鼠标事件，
        # 先收集本帧 FINGER 事件位置用于去重，避免同一根手指被当成两个事件源反复抢绑控件。
        _finger_down_pos = set()
        _finger_up_pos = set()
        _has_finger_move = False
        for event in all_events:
            if event.type == pygame.FINGERDOWN:
                _finger_down_pos.add((event.x * self.scaled_width, event.y * self.scaled_height))
            elif event.type == pygame.FINGERUP:
                _finger_up_pos.add((event.x * self.scaled_width, event.y * self.scaled_height))
            elif event.type == pygame.FINGERMOTION:
                _has_finger_move = True
        _near_finger = lambda p, s: any(math.hypot(p[0] - q[0], p[1] - q[1]) <= 24 for q in s)
        for event in all_events:
            if event.type == pygame.FINGERDOWN:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self._active_touch_ids.add(event.finger_id)
                self._active_touch_pos[event.finger_id] = (x, y)
                self._active_touch_last[event.finger_id] = time.time()
                self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.FINGERUP:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self._active_touch_ids.discard(event.finger_id)
                self._active_touch_pos.pop(event.finger_id, None)
                self._active_touch_last.pop(event.finger_id, None)
                self.touch_events.append({"type": "up", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.FINGERMOTION:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                if event.finger_id in self._active_touch_ids:
                    self._active_touch_pos[event.finger_id] = (x, y)
                    self._active_touch_last[event.finger_id] = time.time()
                self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if _near_finger(event.pos, _finger_down_pos):
                    continue  # 同一手指的鼠标合成事件，去重
                self._active_touch_ids.add(-1)
                self._active_touch_pos[-1] = event.pos
                self._active_touch_last[-1] = time.time()
                self.touch_events.append({"type": "down", "pos": event.pos, "id": -1})
            elif event.type == pygame.MOUSEBUTTONUP:
                if _near_finger(event.pos, _finger_up_pos):
                    continue  # 同一手指的鼠标合成事件，去重
                self._active_touch_ids.discard(-1)
                self._active_touch_pos.pop(-1, None)
                self._active_touch_last.pop(-1, None)
                self.touch_events.append({"type": "up", "pos": event.pos, "id": -1})
            elif event.type == pygame.MOUSEMOTION:
                if _has_finger_move:
                    continue  # 手指移动时跳过鼠标合成移动
                if -1 in self._active_touch_ids:
                    self._active_touch_last[-1] = time.time()
                self.touch_events.append({"type": "move", "pos": event.pos, "id": -1})

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        # 开发者模式：密码输入 / 局内面板开关
        self._handle_dev_keys(all_events)

        # 技能卡选择界面
        if self.state == GameState.SKILL_SELECT:
            _up_pl = self.player2 if getattr(self, 'pending_upgrade_for', None) == "P2" and self.player2 else self.player
            for event in all_events:
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self.is_android:
                        self.screen = pygame.display.set_mode(
                            (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self._update_scale()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1 and len(_up_pl.skill_cards) > 0:
                        self._select_skill_card(0)
                    elif event.key == pygame.K_2 and len(_up_pl.skill_cards) > 1:
                        self._select_skill_card(1)
                    elif event.key == pygame.K_3 and len(_up_pl.skill_cards) > 2:
                        self._select_skill_card(2)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        selected = self.skill_card_selector.handle_input(
                            event.pos, (1, 0, 0), [], self.scale
                        )
                        if selected:
                            self._apply_skill_card(selected)
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    selected = self.skill_card_selector.handle_input(
                        (0, 0), (0, 0, 0), [{"type": "down", "pos": (x, y), "id": event.finger_id}], self.scale
                    )
                    if selected:
                        self._apply_skill_card(selected)
            return mouse_pos, mouse_pressed

        if self.state == GameState.DIALOGUE and self.dialogue.active:
            for event in all_events:
                if event.type == pygame.QUIT:
                    logger.info("收到退出事件")
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self.is_android:
                        self.screen = pygame.display.set_mode(
                            (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self._update_scale()
                        logger.info(f"窗口调整: {event.w}x{event.h}")
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        logger.debug("对话：空格/回车键推进")
                        self._advance_dialogue()
                    elif event.key == pygame.K_1 and self.dialogue.choices:
                        effect = self.dialogue.choices[0].get("effect")
                        self._apply_choice_effect(effect)
                        self.dialogue.select_choice(0)
                        logger.info("对话：选择选项1")
                    elif event.key == pygame.K_2 and len(self.dialogue.choices) > 1:
                        effect = self.dialogue.choices[1].get("effect")
                        self._apply_choice_effect(effect)
                        self.dialogue.select_choice(1)
                        logger.info("对话：选择选项2")
                    elif event.key == pygame.K_3 and len(self.dialogue.choices) > 2:
                        effect = self.dialogue.choices[2].get("effect")
                        self._apply_choice_effect(effect)
                        self.dialogue.select_choice(2)
                        logger.info("对话：选择选项3")
                    elif event.key == pygame.K_4 and len(self.dialogue.choices) > 3:
                        effect = self.dialogue.choices[3].get("effect")
                        self._apply_choice_effect(effect)
                        self.dialogue.select_choice(3)
                        logger.info("对话：选择选项4")
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mouse_pos = event.pos
                        if self.dialogue.choices and len(self.dialogue.displayed_text) >= len(self.dialogue.text):
                            choice_clicked = self._check_choice_click(mouse_pos)
                            if choice_clicked >= 0:
                                effect = self.dialogue.choices[choice_clicked].get("effect")
                                self._apply_choice_effect(effect)
                                self.dialogue.select_choice(choice_clicked)
                                logger.info(f"对话：鼠标选择选项 {choice_clicked + 1}")
                            else:
                                self._advance_dialogue()
                        else:
                            self._advance_dialogue()
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    touch_pos = (x, y)
                    if self.dialogue.choices and len(self.dialogue.displayed_text) >= len(self.dialogue.text):
                        choice_clicked = self._check_choice_click(touch_pos)
                        if choice_clicked >= 0:
                            effect = self.dialogue.choices[choice_clicked].get("effect")
                            self._apply_choice_effect(effect)
                            self.dialogue.select_choice(choice_clicked)
                            logger.info(f"对话：手指选择选项 {choice_clicked + 1}")
                        else:
                            self._advance_dialogue()
                    else:
                        self._advance_dialogue()
                elif event.type == pygame.FINGERMOTION:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
            return mouse_pos, mouse_pressed

        # 菜单/设置/教程/剧情资料库/难度选择的滚轮和触摸滚动
        if self.state in (GameState.MENU, GameState.SETTINGS, GameState.TUTORIAL, GameState.RECORDS, GameState.STORY_ARCHIVE, GameState.CODEX, GameState.MODE_SELECT, GameState.DIFFICULTY_SELECT, GameState.MOD_MANAGER, GameState.ACHIEVEMENTS, GameState.UPDATE, GameState.UPDATE_NOTES, GameState.EQUIP_SELECT):
            for event in all_events:
                if event.type == pygame.QUIT:
                    logger.info("收到退出事件")
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self.is_android:
                        self.screen = pygame.display.set_mode(
                            (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self._update_scale()
                        logger.info(f"窗口调整: {event.w}x{event.h}")
                elif event.type == pygame.MOUSEWHEEL:
                    if self.state == GameState.SKILL_TREE and hasattr(self, 'skill_tree_renderer'):
                        self.skill_tree_renderer.handle_wheel(event.y, getattr(event, 'x', 0))
                    elif self.state == GameState.MENU:
                        self.menu_scroll_offset = max(0, self.menu_scroll_offset - event.y * 40)
                    elif self.state == GameState.SETTINGS:
                        self.settings_scroll_offset = max(0, self.settings_scroll_offset - event.y * 40)
                    elif self.state == GameState.TUTORIAL:
                        self.tutorial_scroll_offset = max(0, self.tutorial_scroll_offset - event.y * 40)
                    elif self.state == GameState.RECORDS:
                        self.records_scroll_offset = max(0, getattr(self, 'records_scroll_offset', 0) - event.y * 40)
                    elif self.state == GameState.STORY_ARCHIVE:
                        self.story_archive_scroll = max(0, self.story_archive_scroll - event.y * 40)
                    elif self.state == GameState.CODEX:
                        self.codex_scroll = max(0, self.codex_scroll - event.y * 40)
                    elif self.state == GameState.MOD_MANAGER:
                        self.mod_manager_scroll = max(0, self.mod_manager_scroll - event.y * 40)
                    elif self.state == GameState.ACHIEVEMENTS:
                        self.ach_scroll_offset = max(0, self.ach_scroll_offset - event.y * 40)
                    elif self.state == GameState.UPDATE_NOTES:
                        if hasattr(self, '_update_notes_panel') and self._update_notes_panel:
                            self._update_notes_panel.handle_wheel(event.y)
                    elif self.state == GameState.EQUIP_SELECT:
                        try:
                            mx, _ = pygame.mouse.get_pos()
                            if mx < 640 * self.scale:
                                n = len(self.get_weapon_shop_rows())
                                visible = max(1, int((330 - 30) / (58 * self.scale)))
                                self.equip_weapon_scroll = max(0, min(max(0, n - visible), int(self.equip_weapon_scroll) - event.y))
                            else:
                                nc = len(self.get_character_shop_rows())
                                visiblec = max(1, int((330 - 30) / (78 * self.scale)))
                                self.equip_character_scroll = max(0, min(max(0, nc - visiblec), int(self.equip_character_scroll) - event.y))
                        except Exception:
                            pass
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
                    self.is_menu_dragging = True
                    self.menu_drag_start_y = y
                    if self.state == GameState.MENU:
                        self.menu_drag_start_offset = self.menu_scroll_offset
                    elif self.state == GameState.SETTINGS:
                        self.menu_drag_start_offset = self.settings_scroll_offset
                    elif self.state == GameState.TUTORIAL:
                        self.menu_drag_start_offset = self.tutorial_scroll_offset
                    elif self.state == GameState.RECORDS:
                        self.menu_drag_start_offset = getattr(self, 'records_scroll_offset', 0)
                    elif self.state == GameState.STORY_ARCHIVE:
                        self.menu_drag_start_offset = self.story_archive_scroll
                    elif self.state == GameState.CODEX:
                        self.menu_drag_start_offset = self.codex_scroll
                    elif self.state == GameState.MOD_MANAGER:
                        self.menu_drag_start_offset = self.mod_manager_scroll
                    elif self.state == GameState.ACHIEVEMENTS:
                        self.menu_drag_start_offset = self.ach_scroll_offset
                    elif self.state == GameState.EQUIP_SELECT:
                        # 拖动起点：按落点栏位存储对应滚动值
                        self.menu_drag_start_offset = self.equip_character_scroll if x >= 660 * self.scale else self.equip_weapon_scroll
                elif event.type == pygame.FINGERMOTION:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
                    if self.is_menu_dragging:
                        dy = self.menu_drag_start_y - y
                        new_offset = max(0, self.menu_drag_start_offset + dy)
                        if self.state == GameState.MENU:
                            self.menu_scroll_offset = new_offset
                        elif self.state == GameState.SETTINGS:
                            self.settings_scroll_offset = new_offset
                        elif self.state == GameState.TUTORIAL:
                            self.tutorial_scroll_offset = new_offset
                        elif self.state == GameState.RECORDS:
                            self.records_scroll_offset = new_offset
                        elif self.state == GameState.STORY_ARCHIVE:
                            self.story_archive_scroll = new_offset
                        elif self.state == GameState.CODEX:
                            self.codex_scroll = new_offset
                        elif self.state == GameState.MOD_MANAGER:
                            self.mod_manager_scroll = new_offset
                        elif self.state == GameState.ACHIEVEMENTS:
                            self.ach_scroll_offset = new_offset
                        elif self.state == GameState.EQUIP_SELECT:
                            try:
                                # 拖动像素换算为行数（合理速度：拖动约一行高才滚一行）
                                if x < 640 * self.scale:
                                    row_h = 58 * self.scale
                                    base = int(getattr(self, 'menu_drag_start_offset', self.equip_weapon_scroll))
                                    n = len(self.get_weapon_shop_rows())
                                    visible = max(1, int((330 - 30) / row_h))
                                    self.equip_weapon_scroll = max(0, min(max(0, n - visible), base + int(dy / row_h)))
                                else:
                                    row_h = 78 * self.scale
                                    base = int(getattr(self, 'menu_drag_start_offset', self.equip_character_scroll))
                                    nc = len(self.get_character_shop_rows())
                                    visiblec = max(1, int((330 - 30) / row_h))
                                    self.equip_character_scroll = max(0, min(max(0, nc - visiblec), base + int(dy / row_h)))
                            except Exception:
                                pass
                elif event.type == pygame.FINGERUP:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "up", "pos": (x, y), "id": event.finger_id})
                    self.is_menu_dragging = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.config.control_mode == ControlMode.TOUCH:
                        self.touch_events.append({"type": "down", "pos": mouse_pos, "id": 0})
                elif event.type == pygame.MOUSEBUTTONUP:
                    if self.config.control_mode == ControlMode.TOUCH:
                        self.touch_events.append({"type": "up", "pos": mouse_pos, "id": 0})
                elif event.type == pygame.MOUSEMOTION:
                    if self.config.control_mode == ControlMode.TOUCH:
                        self.touch_events.append({"type": "move", "pos": mouse_pos, "id": 0})
            return mouse_pos, mouse_pressed

        # PAUSED和GAME_OVER状态需要处理鼠标/触摸事件用于按钮点击
        is_paused_or_over = self.state in (GameState.PAUSED, GameState.GAME_OVER)

        if self.state == GameState.ACHIEVEMENTS:
            for event in all_events:
                if event.type == pygame.QUIT:
                    logger.info("收到退出事件")
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    if not self.is_android:
                        self.screen = pygame.display.set_mode(
                            (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self._update_scale()
                elif event.type == pygame.MOUSEWHEEL:
                    self.ach_scroll_offset -= event.y * 32
                    self.ach_scroll_offset = max(0, self.ach_scroll_offset)
                elif event.type == pygame.FINGERMOTION:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    # 触控拖动滚动
                    if hasattr(self, '_ach_touch_last_y') and self._ach_touch_last_y is not None:
                        delta = y - self._ach_touch_last_y
                        self.ach_scroll_offset -= delta
                        self.ach_scroll_offset = max(0, self.ach_scroll_offset)
                    self._ach_touch_last_y = y
                    self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self._ach_touch_last_y = y
                    self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
                elif event.type == pygame.FINGERUP:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self._ach_touch_last_y = None
                    self.touch_events.append({"type": "up", "pos": (x, y), "id": event.finger_id})
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = GameState.MENU
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button ==1:
                        self.touch_events.append({"type":"down","pos":event.pos,"id":0})
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button ==1:
                        self.touch_events.append({"type":"up","pos":event.pos,"id":0})
            return mouse_pos, mouse_pressed
        
        for event in all_events:
            if event.type == pygame.QUIT:
                logger.info("收到退出事件")
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                if not self.is_android:
                    self.screen = pygame.display.set_mode(
                        (event.w, event.h), pygame.RESIZABLE | pygame.DOUBLEBUF
                    )
                    self._update_scale()
                    logger.info(f"窗口调整: {event.w}x{event.h}")

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

            elif event.type == pygame.KEYUP:
                self._handle_keyup(event.key)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # 触摸事件已在预处理统一收集到 touch_events，这里只保留日志
                    if self.config.control_mode == ControlMode.TOUCH:
                        logger.debug(f"鼠标触控按下: {event.pos}")

            elif event.type == pygame.MOUSEWHEEL:
                # 剧情资料库滚动
                if self.state == GameState.STORY_ARCHIVE:
                    self.story_archive_scroll -= event.y * 40
                    self.story_archive_scroll = max(0, self.story_archive_scroll)

            elif event.type == pygame.FINGERDOWN:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self.last_touch_pos = (x, y)
                logger.debug(f"手指按下: ({x:.0f}, {y:.0f}), id={event.finger_id}")

            elif event.type == pygame.FINGERUP:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                logger.debug(f"手指抬起: ({x:.0f}, {y:.0f}), id={event.finger_id}")

        return mouse_pos, mouse_pressed

    # ================= 开发者测试模式 =================
    def _handle_net_ip_keyboard(self, events):
        """网络联机界面 IP 输入框：聚焦时接受系统输入法输入"""
        for ev in events:
            if ev.type == pygame.TEXTINPUT:
                if len(self.net_ip_input) < 30:
                    self.net_ip_input += ev.text
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    self.net_ip_focused = False
                    self.stop_text_input()
                    self._net_join()
                elif ev.key == pygame.K_BACKSPACE:
                    self.net_ip_input = self.net_ip_input[:-1]
                elif ev.key == pygame.K_ESCAPE:
                    self.net_ip_focused = False
                    self.stop_text_input()

    def _handle_dev_keys(self, events):
        """处理开发者密码输入与局内调试面板开关（键盘）"""
        # 网络联机 IP 输入框：聚焦时优先接受系统输入法输入
        if self.state == GameState.NET_MULTIPLAYER and self.net_ip_focused:
            self._handle_net_ip_keyboard(events)
            return
        if self.dev_input_active:
            for ev in events:
                # SDL_IME 系统输入法：TEXTINPUT 是最终合成字符事件（含中文候选），
                # 同一按键还会伴随 KEYDOWN，字符追加只走 TEXTINPUT，避免双重输入。
                # 只有输入框聚焦后才接受输入（点击输入框/回车/空格/Tab 聚焦）
                if ev.type == pygame.TEXTINPUT:
                    if self.dev_input_focused and len(self.dev_input_str) < 16:
                        self.dev_input_str += ev.text
                    continue
                if ev.type == pygame.KEYDOWN:
                    if not self.dev_input_focused:
                        # 未聚焦：回车/空格/Tab = 键盘"点击"输入框聚焦；ESC 关闭密码框
                        if ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_TAB):
                            self._focus_dev_input()
                        elif ev.key == pygame.K_ESCAPE:
                            self._blur_dev_input()
                            self.dev_input_active = False
                            self.dev_input_str = ""
                        continue
                    # ===== 聚焦态：接受系统输入法输入 =====
                    if ev.key == pygame.K_RETURN:
                        if self.dev_input_str == self._DEV_PASSWORD:
                            self.dev_mode = True
                            self.dev_input_active = False
                            self.dev_input_str = ""
                            self._blur_dev_input()
                            self.update_status_text = "开发者模式已开启！局内按 F9 键打开调试面板"
                        else:
                            self.dev_input_active = False
                            self.dev_input_str = ""
                            self._blur_dev_input()
                            self.update_status_text = "密码错误，请重试（连点版本号重新输入）"
                    elif ev.key == pygame.K_BACKSPACE:
                        self.dev_input_str = self.dev_input_str[:-1]
                    elif ev.key == pygame.K_ESCAPE:
                        self._blur_dev_input()
            return
        for ev in events:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F9:
                if self.state == GameState.PLAYING and self.dev_mode:
                    self.dev_panel_open = not self.dev_panel_open
                    self._rebuild_dev_buttons()

    def start_text_input(self):
        """唤起系统输入法（SDL_IME），供网络IP输入框/开发者密码框使用"""
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def stop_text_input(self):
        """收起系统输入法"""
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    def _focus_dev_input(self):
        """聚焦开发者密码输入框：激活系统输入法（SDL_IME），开始接受输入"""
        if not self.dev_input_active:
            return
        self.dev_input_focused = True
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def _blur_dev_input(self):
        """失焦：关闭系统输入法候选框，不再接受输入"""
        self.dev_input_focused = False
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    def _rebuild_dev_buttons(self):
        """重建局内调试面板按钮（依据当前 dev 状态）"""
        # Button 已在 game.py 顶部 from ui import 导入
        self.dev_buttons = [
            Button(0, 0, 150, 36, f"无敌:{'开' if self.dev_god else '关'}", color=(60, 60, 220)),
            Button(0, 0, 150, 36, f"倍率:x{self.dev_time_scale}", color=(40, 140, 80)),
            Button(0, 0, 150, 36, "生成Boss", color=(180, 60, 60)),
            Button(0, 0, 150, 36, "生成精英", color=(120, 80, 160)),
            Button(0, 0, 150, 36, "生成小怪", color=(90, 130, 80)),
            Button(0, 0, 150, 36, "清空敌人", color=(120, 120, 130)),
            Button(0, 0, 150, 36, "+5000金币", color=(200, 170, 60)),
            Button(0, 0, 150, 36, "+5000经验", color=(90, 160, 200)),
            Button(0, 0, 150, 36, "满血满弹", color=(60, 200, 120)),
            Button(0, 0, 150, 36, "关闭面板", color=(130, 60, 60)),
        ]

    def _update_dev_panel(self, mouse_pos, mouse_pressed, touch_events, scale):
        """局内调试面板：按钮点击检测与功能执行"""
        if not (self.dev_mode and self.dev_panel_open):
            return
        from config import EnemyType
        bx, by = self.scaled_width - 190, 90
        for idx, btn in enumerate(self.dev_buttons):
            btn.base_x = bx
            btn.base_y = by + idx * 42
            # 注意：bx/by 已是屏幕像素坐标，Button 内部不再缩放（传 scale=1.0）
            if btn.update(mouse_pos, mouse_pressed, touch_events, 1.0):
                self._dev_action(idx)

    def _dev_action(self, idx):
        """执行调试面板按钮动作"""
        if idx == 0:
            self.dev_god = not self.dev_god
            if self.player:
                self.player.dev_god = self.dev_god
            self._rebuild_dev_buttons()
        elif idx == 1:
            self.dev_time_scale = {1.0: 2.0, 2.0: 4.0, 4.0: 0.5, 0.5: 1.0}.get(self.dev_time_scale, 1.0)
            self._rebuild_dev_buttons()
        elif idx == 2:
            from config import EnemyType as _ET
            bs = [_ET.BOSS_LONG, _ET.BOSS_XIANG, _ET.BOSS_MUTANT, _ET.BOSS_QUEEN, _ET.BOSS_TITAN, _ET.BOSS_WANG]
            import random as _r
            et = _r.choice(bs)
            e = Enemy(self.player.x + _r.randint(-100, 100), self.player.y + _r.randint(-100, 100), et, 1, self.config.difficulty)
            self.enemies.append(e)
            self.floating_texts.append(FloatingText(e.x, e.y, f"生成 {getattr(e,'name','')}", color=(255, 80, 80), lifetime=2.0))
        elif idx == 3:
            import random as _r
            from config import EnemyType as _ET
            ets = [_ET.ELITE_BRUTE, _ET.ELITE_ASSASSIN, _ET.ELITE_SORCERER, _ET.ELITE_GUARDIAN]
            for _ in range(5):
                e = Enemy(self.player.x + _r.randint(-150, 150), self.player.y + _r.randint(-150, 150), _r.choice(ets), 1, self.config.difficulty)
                self.enemies.append(e)
        elif idx == 4:
            import random as _r
            from config import EnemyType as _ET
            ets = [_ET.ZOMBIE_NORMAL, _ET.ZOMBIE_FAST, _ET.ZOMBIE_CRAWLER, _ET.ZOMBIE_RANGED]
            for _ in range(12):
                e = Enemy(self.player.x + _r.randint(-200, 200), self.player.y + _r.randint(-200, 200), _r.choice(ets), 1, self.config.difficulty)
                self.enemies.append(e)
        elif idx == 5:
            self.enemies.clear()
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "已清空敌人", color=(200, 200, 210), lifetime=1.5))
        elif idx == 6:
            try:
                self.records.add_coins(5000)
            except Exception:
                pass
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "+5000金币", color=(255, 215, 0), lifetime=1.5))
        elif idx == 7:
            self.player.gain_exp(5000)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "+5000经验", color=(90, 200, 240), lifetime=1.5))
        elif idx == 8:
            self.player.hp = self.player.max_hp
            for w in self.player.weapons:
                if hasattr(w, 'current_ammo') and w.current_ammo != "Inf":
                    w.current_ammo = w.max_ammo
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "已回复满", color=(60, 220, 120), lifetime=1.5))
        elif idx == 9:
            self.dev_panel_open = False

    def _handle_keydown(self, key):
        import time
        # Mod 按键钩子：返回 True 则阻止默认处理
        try:
            results = trigger_hook(HOOK_KEYDOWN, key)
            if any(r is True for r in results):
                return
        except Exception:
            pass
        if self.state == GameState.PLAYING:
            # 单武器模式：删除武器切换键控（K1/K2/K3/R 不再切武器）
            if key == pygame.K_TAB:
                # Tab：短按切换下一个技能（非观战模式且玩家可操作时）
                if self.player.can_act():
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
            elif key == pygame.K_t:
                # T：打开技能树
                self.prev_state = self.state
                self.state = GameState.SKILL_TREE
                self.skill_tree_renderer.show()
            elif key == pygame.K_g:
                import time
                self.key_g_press_start = time.time()
                self.key_g_held = True
                self.g_aim_started = False
                self.skill_caster.is_aiming = False
                # 只记录按下，不释放技能
            elif key == pygame.K_q:
                # Q：投掷物（短按快投，长按瞄准）
                import time
                self.key_q_press_start = time.time()
                self.key_q_held = True
                self.q_aim_started = False
                self.throwable_caster.is_aiming = False
            elif key == pygame.K_e:
                # E：切换投掷物类型
                if self.player.can_act():
                    self._cycle_throwable()
            elif key == pygame.K_u:
                # U：P2 技能（短按快放，长按预瞄释放）
                if self.multiplayer_mode == "same_screen" and self.player2:
                    import time as _t
                    self.key_u_press_start = _t.time()
                    self.key_u_held = True
                    self.u_aim_started = False
                    if self.p2_controls:
                        self.p2_controls["skill_caster"].is_aiming = False
            elif key == pygame.K_f:
                    pass
            elif key == pygame.K_ESCAPE:
                self.state = GameState.PAUSED
        elif self.state == GameState.PAUSED:
            if key == pygame.K_ESCAPE:
                self.state = GameState.PLAYING
        elif self.state == GameState.RUNE_VIEW:
            if key == pygame.K_ESCAPE:
                self.state = GameState.PAUSED
                self.rune_selected = None
        elif self.state == GameState.HUD_EDIT:
            if key == pygame.K_ESCAPE:
                self.state = GameState.SETTINGS
        elif self.state == GameState.SETTINGS:
            if key == pygame.K_ESCAPE:
                self.config.save()
                if getattr(self, 'settings_from_pause', False):
                    self.settings_from_pause = False
                    self.state = GameState.PAUSED
                else:
                    self.state = GameState.MENU
        elif self.state == GameState.RECORDS:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
        elif self.state == GameState.CODEX:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
                self.codex_scroll = 0
                self.codex_selected = None
        elif self.state == GameState.SKILL_TREE:
            if key == pygame.K_ESCAPE or key == pygame.K_t:
                self.state = getattr(self, 'prev_state', GameState.PLAYING)
                self.skill_tree_renderer.hide()
            elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                if hasattr(self, 'skill_tree_renderer'):
                    self.skill_tree_renderer.handle_key(key)
        elif self.state == GameState.TEXT_VIEWER:
            if key == pygame.K_ESCAPE or key == pygame.K_e or key == pygame.K_RETURN or key == pygame.K_SPACE:
                self.state = getattr(self, 'prev_state', GameState.PLAYING)
                self.current_viewing_text = None
        elif self.state == GameState.STORY_ARCHIVE:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
                self.story_archive_scroll = 0
                self.story_archive_selected = None
        elif self.state == GameState.MOD_MANAGER:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
                self.mod_manager_scroll = 0
                self.mod_selected = None
        elif self.state == GameState.UPDATE:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU
        elif self.state == GameState.UPDATE_NOTES:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU

    def _handle_keyup(self, key):
        import time
        # 技能树方向键释放
        if self.state == GameState.SKILL_TREE and hasattr(self, 'skill_tree_renderer'):
            self.skill_tree_renderer.handle_key_up(key)
            return
        if self.state != GameState.PLAYING:
            return
        if key == pygame.K_g:
            hold_time = time.time() - self.key_g_press_start
            self.key_g_held = False
            self.skill_caster.is_aiming = False #松开关闭瞄准标记

            if not self.player.can_act():
                self.g_aim_started = False
                self.player.riot_gear.end_aim()
                return

            selected_skill = self.selected_skill
            if hold_time < self.key_g_long_threshold:
                # --------短按快放--------
                if selected_skill == SkillType.RIOT_GEAR:
                    riot_skill = self.player.skill_tree.get_skill(SkillType.RIOT_GEAR)
                    if riot_skill is not None and riot_skill.current_level > 0:
                        cd_mult = self.player.cooldown_mult
                        if self.player.riot_gear.equipped:
                            self.player.riot_gear.unequip(cd_reduction_mult=cd_mult)
                            self.floating_texts.append(FloatingText(self.player.x,self.player.y-50,"卸下防爆套装",ORANGE,1.2))
                        else:
                            ok = self.player.riot_gear.equip()
                            if ok:
                                self.floating_texts.append(FloatingText(self.player.x,self.player.y-50,"装备防爆套装",GREEN,1.2))
                            else:
                                self.floating_texts.append(FloatingText(self.player.x,self.player.y-50,"防爆套装冷却中！",RED,1.2))
                else:
                    self._use_skill(selected_skill)
            else:
                # --------长按瞄准释放，复用原有 _use_skill_aimed 接口--------
                angle = self.skill_caster.angle
                ratio = self.skill_caster.distance_ratio
                self._use_skill_aimed(selected_skill, angle, ratio)

            self.g_aim_started = False
            self.player.riot_gear.end_aim()

        elif key == pygame.K_q:
            # Q键释放：短按快投，长按瞄准投掷
            import time
            hold_time = time.time() - self.key_q_press_start
            self.key_q_held = False
            self.throwable_caster.is_aiming = False

            if not self.player.can_act():
                self.q_aim_started = False
                return

            if hold_time < self.key_q_long_threshold:
                # 短按：朝鼠标方向快速投掷
                self._throw_grenade()
            else:
                # 长按：按瞄准方向和距离投掷
                angle = self.throwable_caster.angle
                ratio = self.throwable_caster.distance_ratio
                self._throw_grenade_aimed(angle, ratio)

            self.q_aim_started = False

        elif key == pygame.K_u:
            # U键释放：P2 技能（短按快放，长按预瞄释放）
            if self.multiplayer_mode != "same_screen" or not self.player2:
                return
            import time as _t
            hold_time = _t.time() - self.key_u_press_start
            self.key_u_held = False
            if self.p2_controls:
                self.p2_controls["skill_caster"].is_aiming = False
            if not self.player2.can_act():
                self.u_aim_started = False
                return
            st = self.p2_selected_skill
            if st is None:
                sts = self._get_unlocked_skills_for(self.player2)
                if sts:
                    st = sts[0]
            if not st:
                self.u_aim_started = False
                return
            if hold_time < self.key_u_long_threshold:
                # 短按快放（当前朝向）
                self._use_skill_p2(st)
            else:
                # 长按：按预瞄方向+距离释放
                c2 = self.p2_controls
                if self.u_aim_started:
                    self._use_skill_p2_aimed(st, c2["skill_caster"].angle, c2["skill_caster"].distance_ratio)
                else:
                    self._use_skill_p2_aimed(st, math.radians(self.player2.facing_angle), 1.0)
            self.u_aim_started = False

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

    def _perform_bash(self, direction_angle=None):
        """盾牌冲撞：启动冲撞，移动和伤害由_update_charge处理"""
        if self.session:
            self.session.add_bash()
        self.assets.play_sound("bash")
        success = self.player.riot_gear.bash(direction_angle)
        if success:
            # 肘击消耗已扣 riot_gear.stamina，同步回玩家共享体力池。
            # 若不回流，Player.update 每帧会把 self.stamina 单向覆盖回 riot_gear.stamina，
            # 导致肘击体力消耗被抹掉 -> 体力与玩家不共享、恒接近满（接近无限）
            self.player.stamina = self.player.riot_gear.stamina
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, "盾牌冲撞!", color=CYAN, lifetime=1.0
            ))
            self.camera.shake(5, 0.2)

    def _update_charge(self, dt):
        """更新盾牌冲撞：移动玩家，检测沿途敌人碰撞"""
        rg = self.player.riot_gear
        if not rg.charge_active:
            return
        rg.charge_timer -= dt
        angle_rad = math.radians(rg.charge_direction)
        move_x = math.cos(angle_rad) * rg.charge_speed * dt
        move_y = math.sin(angle_rad) * rg.charge_speed * dt
        # 尝试移动（受世界边界限制）
        new_x = self.player.x + move_x
        new_y = self.player.y + move_y
        clamped_x, clamped_y = self.world.clamp_position(new_x, new_y, self.player.size)
        # 如果被墙挡住，提前结束冲撞
        if abs(clamped_x - new_x) > 1 or abs(clamped_y - new_y) > 1:
            rg.charge_timer = 0
        self.player.x, self.player.y = clamped_x, clamped_y
        # 检测沿途敌人碰撞
        hit_any = False
        for enemy in self.enemies:
            if id(enemy) in rg.charge_hit_ids:
                continue
            dist = math.hypot(enemy.x - self.player.x, enemy.y - self.player.y)
            hit_radius = self.player.size + enemy.size + 10
            if dist < hit_radius:
                rg.charge_hit_ids.add(id(enemy))
                is_crit = random.random() < self.player.crit_chance
                actual_damage = rg.charge_damage * self.player.damage_mult * self.player.buff_manager.get_damage_mult() * (self.player.crit_damage if is_crit else 1)
                enemy.take_damage(actual_damage)
                self._vampire_heal(actual_damage)
                # 强控制：眩晕（对 boss 控制效果减半）
                _is_boss = getattr(enemy, "is_boss", False)
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
        if hit_any:
            self.camera.shake(8, 0.3)
        # 冲撞拖尾粒子
        self.particles.spawn(self.player.x, self.player.y, CYAN, 2, (4, 10), (-3, 3), (0.15, 0.35))
        # 冲撞结束
        if rg.charge_timer <= 0:
            rg.charge_active = False
            rg.charge_hit_ids = set()
            # 结束冲击波
            self.particles.spawn_explosion(self.player.x, self.player.y, CYAN, 20)
            self.camera.shake(6, 0.25)

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

    def _perform_grapple_at(self, target_x, target_y):
        """在指定位置执行钩爪核心逻辑 - 新逻辑（独立技能）"""
        # 寻找钩爪路径上的目标
        dx = target_x - self.player.x
        dy = target_y - self.player.y
        dist = math.hypot(dx, dy)
        if dist > self.player.riot_gear.grapple_max_range:
            ratio = self.player.riot_gear.grapple_max_range / dist
            dx *= ratio
            dy *= ratio
            target_x = self.player.x + dx
            target_y = self.player.y + dy
            dist = self.player.riot_gear.grapple_max_range

        dir_x = dx / dist if dist > 0 else 1
        dir_y = dy / dist if dist > 0 else 0

        # 搜索路径上的敌人
        target = None
        target_dist = dist
        search_radius = 30  # 搜索半径

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            # 计算敌人到钩爪路径的距离
            ex = enemy.x - self.player.x
            ey = enemy.y - self.player.y
            # 投影到方向向量
            proj = ex * dir_x + ey * dir_y
            if proj < 0 or proj > dist:
                continue
            # 垂直距离
            perp_x = ex - proj * dir_x
            perp_y = ey - proj * dir_y
            perp_dist = math.hypot(perp_x, perp_y)
            if perp_dist < search_radius + enemy.size and proj < target_dist:
                target = enemy
                target_dist = proj

        # 搜索经验球
        for orb in self.exp_orbs:
            if not orb.alive:
                continue
            ex = orb.x - self.player.x
            ey = orb.y - self.player.y
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
            ex = item.x - self.player.x
            ey = item.y - self.player.y
            proj = ex * dir_x + ey * dir_y
            if proj < 0 or proj > dist:
                continue
            perp_x = ex - proj * dir_x
            perp_y = ey - proj * dir_y
            perp_dist = math.hypot(perp_x, perp_y)
            if perp_dist < search_radius + item.size and proj < target_dist:
                target_dist = proj

        # 使用钩爪
        if target:
            success = self.player.riot_gear.use_grapple(
                target.x, target.y, self.player.x, self.player.y, target
            )
        else:
            success = self.player.riot_gear.use_grapple(
                target_x, target_y, self.player.x, self.player.y, None
            )

        if success:
            # 记录钩爪使用
            if self.session:
                self.session.add_grapple()
            # 播放音效
            self.assets.play_sound("grapple")
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, "钩爪发射!", color=GREEN, lifetime=1.0
            ))
        return success

    def _throw_grenade(self):
        if self.config.control_mode == ControlMode.KEYBOARD:
            mouse_pos = pygame.mouse.get_pos()
            target_x = mouse_pos[0] / self.scale + self.camera.x
            target_y = mouse_pos[1] / self.scale + self.camera.y
        else:
            angle_rad = math.radians(self.player.facing_angle)
            target_x = self.player.x + math.cos(angle_rad) * 400
            target_y = self.player.y + math.sin(angle_rad) * 400
        self._throw_grenade_at(target_x, target_y)

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

    def _select_skill_card(self, index):
        """选择技能卡（双人：作用于当前升级的玩家）"""
        player = self.player2 if getattr(self, 'pending_upgrade_for', None) == "P2" and self.player2 else self.player
        if 0 <= index < len(player.skill_cards):
            skill = player.skill_cards[index]
            self._apply_skill_card(skill)

    def _apply_skill_card(self, skill):
        """应用选中的技能卡（双人：作用于当前升级的玩家）"""
        player = self.player2 if getattr(self, 'pending_upgrade_for', None) == "P2" and self.player2 else self.player
        tag = getattr(self, 'pending_upgrade_for', "P1") or "P1"
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
        player.pending_level_up = False
        player.skill_cards = []
        self.pending_upgrade_for = None
        self.skill_card_selector.hide()
        self.state = GameState.PLAYING

    def _synthesize_touch_ups(self):
        """状态切换时，为仍按住的触摸手指合成 up 事件，防止控件被留在按下态。"""
        for fid in list(self._active_touch_ids):
            pos = self._active_touch_pos.get(fid, (0, 0))
            self.touch_events.append({"type": "up", "pos": pos, "id": fid})
        self._active_touch_ids.clear()
        self._active_touch_pos.clear()
        self._active_touch_last.clear()

    def _reset_touch_state(self):
        """强制重置所有触控控件状态，防止游戏状态切换后摇杆/攻击/按钮卡死。

        关键：多指操控时（如一只手移动、一只手攻击）按下菜单键返回暂停，
        仍按住的攻击/摇杆手指的 up 事件在状态切换后不再被 _update_playing 消费，
        因此必须完整清掉所有控件的按下/射击/绑定状态，否则回到游戏后
        攻击摇杆会持续处于 is_shooting 状态（射击按钮卡死）。
        """
        # 虚拟摇杆
        if hasattr(self, 'joystick') and self.joystick:
            if hasattr(self.joystick, 'reset'):
                self.joystick.reset()
            else:
                self.joystick.active = False
                self.joystick.touch_id = None
                self.joystick.knob_x = self.joystick.base_x
                self.joystick.knob_y = self.joystick.base_y
                self.joystick.value_x = 0
                self.joystick.value_y = 0
        # 重置所有触控按钮的 pressed / 绑定手指 / 长按状态
        if hasattr(self, 'touch_buttons'):
            for btn in self.touch_buttons.values():
                for _a in ('pressed', 'was_pressed', 'just_released', 'just_pressed', 'is_long_press'):
                    if hasattr(btn, _a):
                        setattr(btn, _a, False)
                if hasattr(btn, 'touch_id'):
                    btn.touch_id = None
        # 重置攻击摇杆 / 技能施法器 / 投掷物施法器 / 技能选择器
        # 必须清掉 active / is_shooting / is_aiming / touch_id / knob 偏移，才能彻底解除卡死
        for attr in ['aim_button', 'skill_caster', 'throwable_caster', 'skill_selector']:
            obj = getattr(self, attr, None)
            if not obj:
                continue
            for _a in ('active', 'pressed', 'is_shooting', 'is_aiming', 'was_pressed',
                       'just_released', 'just_pressed', 'wheel_active', 'is_long_press',
                       'should_open_wheel'):
                if hasattr(obj, _a):
                    setattr(obj, _a, False)
            if hasattr(obj, 'touch_id'):
                obj.touch_id = None
            if hasattr(obj, 'knob_offset_x'):
                obj.knob_offset_x = 0
            if hasattr(obj, 'knob_offset_y'):
                obj.knob_offset_y = 0
        # 技能轮盘 / 武器轮盘：关闭活动状态
        for _w in (getattr(self, 'skill_wheel', None), getattr(self, 'weapon_wheel', None)):
            if _w and hasattr(_w, 'active'):
                _w.active = False
        # 注意：这里不清空 touch_events，状态切换时合成的 up 交由各控件消费；
        # 由于上面已把 touch_id 全部置空，残留的合成 up 会被控件安全忽略。

    def _open_update_notes(self):
        """打开“更新说明”界面：先用本地内置说明，再后台拉取 GitHub 最新发布说明"""
        self.update_notes_scroll = 0
        self.update_notes_text = (
            f"当前版本: v{self.current_version_str}\n\n"
            "丧尸幸存者 Zombie Survivor - 俯视角僵尸生存射击游戏\n"
            "由 AI 开发维护。\n\n"
            "## 功能特色\n"
            "- 无尽生存：升级、选择技能、切换武器\n"
            "- 多模式：故事 / 无尽 / 限时；多难度：简单/普通/困难/地狱\n"
            "- 武器、技能、精英怪与 Boss、符文、Buff 系统\n"
            "- 触控与键鼠双支持，适配班班通等触控一体机\n"
            "- 内置 GitHub Release 热更新（检查/下载/应用/自动重启）\n\n"
            "## v1.0.4 更新内容\n"
            "- 新增：触控端疾跑按钮（按住疾跑，键鼠下仍为 Ctrl）\n"
            "- 平衡：削弱防爆套装（冲撞伤害、控制时长降低；肘击/冲刺体力消耗增加；对 Boss 控制效果减半）\n"
            "- 钩爪：Boss 现在只能被钩中产生僵直，无法拉回；修复拉力过强导致被勾物乱飞\n"
            "- 钩爪：拉回后目标进入长僵直，短时间内无法移动或攻击玩家\n"
            "- 修复：Buff 持续伤害与钩爪伤害击杀敌人后不触发死亡结算/不掉落/尸体残留的问题\n"
            "- 修复：击退尸潮后找不到奖励（奖励改走正常掉落管线，可拾取）\n"
            "- 启用：符文系统（此前初始化缺失导致掉落加成、再生等完全不生效）\n"
            "- 修复：武器图鉴缺失武器（补齐 机枪 / 榴弹发射器 / 等离子步枪 / 连狙，共 32 把）\n"
            "\n"
            "- 修复：检查更新成功后渲染 GitHub 更新日志时空行导致的崩溃（Text has zero width）\n"
            "- 修复：装备防爆套装后体力不共享、接近无限的问题（肘击消耗不再被抹掉）\n"
            "- 删除：触控端的聊天按钮\n"
            "- 优化：触控按钮单字扩充为清晰表达（射击/换武器/投掷）\n"
            "\n"
            "## v1.0.2 更新内容\n"
            "- 修复：手机端检查更新页面按钮布局（下载/返回按钮被挤出屏幕外）\n"
            "- 修复：更新说明界面文字无法手动滚动、自动滚走消失的问题\n"
            "- 统一：所有滚动文字界面采用图鉴 ScrollablePanel 实现（触控+鼠标+滚轮+边界+滚动条）\n"
            "- 修复：图鉴世界观分类按钮触控需点好几下才响应的问题\n"
            "- 排查：技能选择/轮盘/对话等弹出界面切换时的触控状态重置，防止按键卡死\n"
            "\n"
            "## v1.0.1 更新内容\n"
            "- 修复多指操控时按菜单返回后射击按钮卡死的问题\n"
            "- 修复菜单/开头音乐在新旧版本间反复切换的异常\n"
            "- 新增：设置中可开关游戏日志记录（写入日志文件）\n"
            "- 新增：游戏内“更新说明”界面\n"
            "- 扩展热更新支持资源文件更新\n"
            "- 新增更多 Mod 钩子\n"
            "- 补全缺失图像资源（程序化生成）\n"
            "\n"
            "（正在后台获取 GitHub 最新发布说明...）"
        )
        self.update_notes_version = None
        try:
            import threading
            def _load():
                ver, body = updater.fetch_release_notes()
                if ver and body:
                    self.update_notes_version = ver
                    self.update_notes_text = f"最新版本: v{ver}\n\n{body}"
                else:
                    self.update_notes_text = self.update_notes_text.replace(
                        "（正在后台获取 GitHub 最新发布说明...）",
                        "（未能联网获取最新发布说明，显示本地内置版本）")
            threading.Thread(target=_load, daemon=True).start()
        except Exception:
            pass

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
        self.player.update(dt, move_x, move_y, mouse_angle, self.world, sprinting=sprinting)
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

    def _get_shop_weapons(self):
        """局外可选武器列表（排除投掷物类）"""
        throwable_set = {WeaponType.GRENADE, WeaponType.MOLOTOV, WeaponType.SMOKE_GRENADE}
        return [wt for wt in WeaponType if wt not in throwable_set]

    def get_weapon_shop_rows(self):
        """返回武器商店行数据：[(wt, name, price, owned, level, locked_reason, desc)]"""
        rows = []
        for wt in self._get_shop_weapons():
            name = Weapon(wt).name
            price = WEAPON_PRICES.get(wt.name, 0)
            owned = self.records.is_weapon_owned(wt.name)
            level = self.records.get_weapon_level(wt.name) if owned else 1
            locked_reason = ""
            if wt == WeaponType.SCYTHE and not self.records.has_defeated_wang():
                locked_reason = "需击败王某"
            rows.append((wt, name, price, owned, level, locked_reason, Weapon(wt).desc))
        return rows

    def equip_select_weapon(self, wt):
        """选择（已拥有的）武器"""
        if not self.records.is_weapon_owned(wt.name):
            return False
        self.selected_weapon = wt
        self.selected_weapon_level = self.records.get_weapon_level(wt.name)
        return True

    def equip_buy_weapon(self, wt):
        """购买武器。返回状态字符串"""
        if self.records.is_weapon_owned(wt.name):
            return "owned"
        if wt == WeaponType.SCYTHE and not self.records.has_defeated_wang():
            return "locked_wang"
        price = WEAPON_PRICES.get(wt.name, 0)
        if price <= 0:
            self.records.unlock_weapon_purchase(wt.name)
            self.selected_weapon = wt
            self.selected_weapon_level = 1
            return "ok"
        if self.records.get_coins() < price:
            return "no_coin"
        self.records.spend_coins(price)
        self.records.unlock_weapon_purchase(wt.name)
        self.selected_weapon = wt
        self.selected_weapon_level = 1
        return "ok"

    def get_weapon_upgrade_price(self, wt):
        """当前武器升至下一级的费用（满级返回0）"""
        try:
            cur = self.records.get_weapon_level(wt.name)
            if cur >= 5:
                return 0
            return max(0, int(WEAPON_PRICES.get(wt.name, 0) * 0.6 * (cur + 1)))
        except Exception:
            return 0

    def get_character_upgrade_price(self, name):
        """当前角色升至下一级的费用（满级返回0）"""
        try:
            cur = self.records.get_character_level(name)
            if cur >= 5:
                return 0
            return max(0, int(CHARACTERS.get(name, {}).get("price", 0) * 0.6 * (cur + 1)))
        except Exception:
            return 0

    def upgrade_weapon_shop(self, wt):
        """局外升级武器（花费金币提升等级，最高5级）"""
        cur = self.records.get_weapon_level(wt.name)
        if cur >= 5:
            return "max"
        next_lvl = cur + 1
        price = int(WEAPON_PRICES.get(wt.name, 0) * 0.6 * next_lvl)
        if price <= 0:
            return "ok"
        if self.records.get_coins() < price:
            return "no_coin"
        self.records.spend_coins(price)
        self.records.upgrade_weapon_purchase(wt.name, next_lvl)
        if self.selected_weapon == wt:
            self.selected_weapon_level = next_lvl
        return "ok"

    def get_character_shop_rows(self):
        """返回角色商店行数据：[(name, price, owned, level, desc, ability, locked_reason)]"""
        rows = []
        for name, cfg in CHARACTERS.items():
            if cfg.get("requires_scythe") and not self.records.has_defeated_wang():
                locked_reason = "需击败王某"
            else:
                locked_reason = ""
            owned = self.records.is_character_owned(name)
            level = self.records.get_character_level(name) if owned else 1
            rows.append((name, cfg["price"], owned, level, cfg["desc"], cfg["ability"], locked_reason))
        return rows

    def equip_select_character(self, name):
        if not self.records.is_character_owned(name):
            return False
        self.selected_character = name
        return True

    def equip_buy_character(self, name):
        cfg = CHARACTERS.get(name)
        if not cfg:
            return "err"
        if cfg.get("requires_scythe") and not self.records.has_defeated_wang():
            return "locked_wang"
        if self.records.is_character_owned(name):
            return "owned"
        price = cfg["price"]
        if price <= 0:
            self.records.unlock_character_purchase(name)
            self.selected_character = name
            return "ok"
        if self.records.get_coins() < price:
            return "no_coin"
        self.records.spend_coins(price)
        self.records.unlock_character_purchase(name)
        self.selected_character = name
        return "ok"

    def upgrade_character_shop(self, name):
        cur = self.records.get_character_level(name)
        if cur >= 5:
            return "max"
        next_lvl = cur + 1
        price = int(CHARACTERS.get(name, {}).get("price", 0) * 0.6 * next_lvl)
        if price <= 0:
            return "ok"
        if self.records.get_coins() < price:
            return "no_coin"
        self.records.spend_coins(price)
        self.records.upgrade_character_purchase(name, next_lvl)
        return "ok"

    def equip_confirm(self):
        """确认装备选择，开始游戏（选中项必须已解锁）"""
        if self.selected_weapon and not self.records.is_weapon_owned(self.selected_weapon.name):
            self.equip_hover = "请先解锁所选武器"
            return
        if self.selected_character and not self.records.is_character_owned(self.selected_character):
            self.equip_hover = "请先解锁所选角色"
            return
        # ===== 多人模式：P1/P2 两轮选择 =====
        if self.multiplayer_mode in ("same_screen", "network"):
            if not self.equip_p2_phase:
                self.selected_weapon_p1 = self.selected_weapon
                self.selected_char_p1 = self.selected_character
                self.selected_weapon_p1_level = self.selected_weapon_level
                self.equip_p2_phase = True
                self.selected_weapon = None
                self.selected_character = None
                self.selected_weapon_level = 1
                self.equip_hover = "轮到玩家2选择装备"
                self.equip_tab_weapon = True
                return
            self.selected_weapon_p2 = self.selected_weapon
            self.selected_char_p2 = self.selected_character
            self.selected_weapon_p2_level = self.selected_weapon_level
            self.equip_p2_phase = False
        self.start_game()

    # ===== 网络联机 =====
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
        self.net_host = NetHost(self.net_port)
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

    def _apply_character_bonuses(self):
        """应用局外角色特殊能力加成（按角色等级缩放）"""
        if not self.selected_character:
            return
        cfg = CHARACTERS.get(self.selected_character)
        if not cfg:
            return
        lvl = self.records.get_character_level(self.selected_character)
        scale_lvl = 1 + (lvl - 1) * 0.2
        p = self.player
        hb = int(cfg.get("hp_bonus", 0) * scale_lvl)
        if hb:
            p.max_hp += hb
            p.hp = min(p.hp + hb, p.max_hp)
        p.base_speed += cfg.get("speed_bonus", 0) * scale_lvl
        p.speed = p.base_speed
        p.damage_multiplier *= (1 + cfg.get("damage_bonus", 0))
        p.crit_bonus_add += cfg.get("crit_bonus", 0)
        p.crit_chance += p.crit_bonus_add
        p.health_regen += cfg.get("regen", 0) * scale_lvl
        p.dmg_reduce += cfg.get("dmg_reduce", 0)

    def _first_available_story_map(self):
        """故事模式第一遍流程：从第一张未通关地图开始；全通关后回到第一张"""
        for m in STORY_MAP_ORDER:
            if not self.records.is_map_cleared(m.name):
                return m
        return STORY_MAP_ORDER[0]

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

    def _codex_unlock_toast(self, unlocked, label):
        """图鉴新解锁时实时弹出提示"""
        if unlocked:
            self.ach_toast_queue.append({"key": "codex", "desc": f"图鉴解锁: {label}", "timer": 3.0})

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

if __name__ == "__main__":
    try:
        game = Game()
        game.run()
    except Exception as e:
        logger.log_exception(e)
        raise
