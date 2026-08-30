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

from config import *
from assets import AssetManager, SOUND_MAP, MUSIC_MAP, MAP_MUSIC_MAP
from records import GameRecords, GameSession
from codex import MONSTER_CODEX, WEAPON_CODEX, MONSTER_CATEGORIES, WEAPON_CATEGORIES, codex_unlock_manager
from skill_tree_view import SkillTreeRenderer, skill_tree_unlock_manager
from mod_loader import (load_all_mods, trigger_hook, HOOK_GAME_START, HOOK_GAME_TICK, HOOK_ENEMY_SPAWN, HOOK_ENEMY_DEATH, HOOK_PLAYER_DAMAGE, HOOK_KEYDOWN, HOOK_RENDER_HUD, HOOK_GAME_OVER, HOOK_WAVE_COMPLETE)
from logger import GameLogger
from ui import (FontManager, Button, VirtualJoystick, TouchButton, DamageNumber, 
                FloatingText, ParticleSystem, AimButton, SkillSelector, SkillCaster, 
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
        self.config_file = "config.json"
        self.load()

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
        FontManager.init(base_path)

        self.config = Config()
        logger.info(f"控制模式: {self.config.control_mode.name}")

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

        # 武器切换
        self.weapon_switch_cooldown = 0

        # 钩爪相关
        self.grapple_aiming = False
        self.grapple_aim_angle = 0
        self.grapple_press_time = 0

        self.touch_events = []
        self._setup_touch_controls()

        #键鼠相关【新版：Tab/R只有短按；G支持短按快放 / 长按瞄准】
        self.key_g_press_start = 0.0
        self.key_g_long_threshold = 0.4
        self.g_aim_started = False
        self.key_g_held = False
        self.mouse_angle = 0.0

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
        self.session = None

        #成就页面滚动
        self.ach_scroll_offset = 0
        self._ach_touch_last_y = None
        #成就解锁toast队列
        self.ach_toast_queue = []
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
            "shoot": TouchButton(BASE_WIDTH - 500, BASE_HEIGHT - 145, 62, "射", RED),
            "weapon_switch": WeaponSwitchButton(BASE_WIDTH - 520, BASE_HEIGHT - 320, 42, "换", PURPLE),
            "pause": TouchButton(60, 55, 38, "II", GRAY),
            "chat": TouchButton(60, BASE_HEIGHT - 200, 42, "聊", CYAN),
        }
        # 技能切换按钮（右上列）
        self.skill_selector = SkillSelector(BASE_WIDTH - 220, BASE_HEIGHT - 320, 42)
        # 技能释放按钮（右下列）
        self.skill_caster = SkillCaster(BASE_WIDTH - 130, BASE_HEIGHT - 145, 52)
        # 投掷物切换按钮（中上列）
        self.throwable_switch_btn = TouchButton(BASE_WIDTH - 370, BASE_HEIGHT - 320, 42, "弹", ORANGE)
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
        logger.info("触控控件初始化完成")

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
            Button(cx, 620, 200, 45, "设置", color=GRAY),
            Button(cx, 675, 200, 45, "教程", color=BLUE),
            Button(cx, 730, 200, 45, "退出", color=RED),
        ]
        # 模式选择按钮
        self.mode_select_buttons = [
            Button(cx, 250, 220, 55, "故事模式", color=GOLD),
            Button(cx, 330, 220, 55, "无尽模式", color=CRIMSON),
            Button(cx, 410, 220, 55, "限时模式", color=BLUE),
            Button(cx, 500, 200, 45, "返回", color=RED),
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
            Button(cx, 595, 200, 50, "返回", color=RED),
        ]
        self.pause_buttons = [
            Button(cx, 200, 200, 50, "继续", color=GREEN),
            Button(cx, 270, 200, 50, "技能树", color=GOLD),
            Button(cx, 340, 200, 50, "设置", color=BLUE),
            Button(cx, 410, 200, 50, "返回菜单", color=RED),
        ]
        self.settings_from_pause = False  # 标记设置是否从暂停菜单进入
        logger.info("菜单按钮初始化完成")

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
            with open("savegame.json", "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            logger.info("对局状态已保存")
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
        """检查是否存在存档"""
        import os
        return os.path.exists("savegame.json")

    def load_game_state(self):
        """加载存档并开始游戏（从存档恢复）"""
        import json
        try:
            if not self.has_saved_game():
                return False
            with open("savegame.json", "r", encoding="utf-8") as f:
                save_data = json.load(f)
            
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
                        getattr(self.player, 'skill_slot_count', 3))
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
                            codex_unlock_manager.unlock_monster(enemy.enemy_type.name if hasattr(enemy, "enemy_type") else enemy.type.name)
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
        """删除存档（游戏结束时调用）"""
        import os
        try:
            if os.path.exists("savegame.json"):
                os.remove("savegame.json")
        except:
            pass

    def _unlock_achievement(self, key):
        """即时解锁成就并显示提示"""
        if self.records and self.records.unlock_achievement(key):
            ach = self.records.get_achievements().get(key, {})
            desc = ach.get("desc", key)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 60,
                f"成就解锁: {desc}", color=GOLD, lifetime=4.0))
            logger.info(f"成就解锁: {key} - {desc}")

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
            # 故事模式：从第一张地图开始
            if self.config.game_mode == GameMode.STORY:
                self.current_map_index = 0
                self.current_map = STORY_MAP_ORDER[0]
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

            self.player = Player(0, 0)
            # Mod 游戏开始钩子
            try:
                trigger_hook(HOOK_GAME_START, self)
            except Exception:
                pass
            # 解锁初始武器图鉴
            try:
                codex_unlock_manager.unlock_weapon(WeaponType.FISTS.name)
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
        """切换到下一张地图"""
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
        self.player.x = 0
        self.player.y = 0
        # 恢复一些生命值
        self.player.hp = min(self.player.max_hp, self.player.hp + self.player.max_hp * 0.3)

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
    def _get_unlocked_skills(self):
        """获取已解锁的主动技能列表"""
        if not self.player:
            return [SkillType.GRENADE]
        return self.player.skill_tree.get_unlocked_active_skills()

    def _get_unlocked_skill_objects(self):
        """获取已解锁的主动技能对象列表（用于轮盘显示）"""
        if not self.player:
            return []
        skill_types = self.player.skill_tree.get_unlocked_active_skills()
        return [self.player.skill_tree.get_skill(st) for st in skill_types if self.player.skill_tree.get_skill(st)]

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
        if not self.player:
            return False
        if not self.player.can_act():
            return False

        skill = self.player.skill_tree.get_skill(skill_type)
        if not skill or skill.current_level == 0:
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

        skill = self.player.skill_tree.get_skill(skill_type)
        if not skill or skill.current_level == 0:
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
        """空袭技能 - 根据等级累加效果
        Lv1: 单点轰炸
        Lv2: 飞机掠过，沿线连投5弹
        Lv3: 飞机连投 + 燃烧区域
        Lv4: 双机双向持续轰炸 + 燃烧
        Lv5: 超级核爆：中心巨型爆炸 + 双机轰炸 + 燃烧 + EMP眩晕
        """
        if self.config.control_mode == ControlMode.KEYBOARD:
            mouse_pos = pygame.mouse.get_pos()
            target_x = mouse_pos[0] / self.scale + self.camera.x
            target_y = mouse_pos[1] / self.scale + self.camera.y
        else:
            angle_rad = math.radians(self.player.facing_angle)
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

        if skill_level == 1:
            # Lv1: 单点轰炸
            self.floating_texts.append(FloatingText(
                target_x, target_y - 50, "空袭来袭!", color=RED, lifetime=2.0
            ))
            self.airstrikes.append({"x": target_x, "y": target_y, "timer": 2.0, "warned": False, "effects": effects})
        elif skill_level >= 2:
            # Lv2+: 飞机掠过连投
            label = "超级核爆!" if skill_level >= 5 else ("燃烧空袭!" if skill_level >= 3 else "空袭来袭!")
            label_color = (255, 200, 0) if skill_level >= 5 else (FIRE_ORANGE if skill_level >= 3 else RED)
            self.floating_texts.append(FloatingText(
                target_x, target_y - 50, label, color=label_color, lifetime=2.5
            ))
            # 第一架飞机（随机角度）
            self._create_plane_run(target_x, target_y, effects, bomb_count=5 if skill_level < 5 else 7)
            # Lv4+: 第二架飞机（垂直角度，持续轰炸）
            if skill_level >= 4:
                self._create_plane_run(target_x, target_y, effects, bomb_count=5 if skill_level < 5 else 7, angle_offset=90)
            # Lv5: 中心超级核爆（延迟1.5秒后引爆）
            if skill_level >= 5:
                self.airstrikes.append({
                    "x": target_x, "y": target_y, "timer": 1.5, "warned": False,
                    "effects": ["nuke", "fire", "emp"], "is_nuke": True
                })
        return True

    def _create_plane_run(self, target_x, target_y, effects, bomb_count=5, angle_offset=0):
        """创建一个飞机连投空袭"""
        import random as _rnd
        # 飞机飞行角度（随机，可加偏移）
        base_angle = _rnd.uniform(0, 360) + angle_offset
        rad = math.radians(base_angle)
        # 飞机从远处飞来
        fly_dist = 800
        plane_x = target_x - math.cos(rad) * fly_dist
        plane_y = target_y - math.sin(rad) * fly_dist
        plane_speed = 600
        plane_vx = math.cos(rad) * plane_speed
        plane_vy = math.sin(rad) * plane_speed
        # 沿飞行方向排列炸弹
        bombs = []
        line_length = 300
        for i in range(bomb_count):
            t = (i / max(1, bomb_count - 1)) - 0.5  # -0.5 到 0.5
            bx = target_x + math.cos(rad) * t * line_length
            by = target_y + math.sin(rad) * t * line_length
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
            # 核爆蘑菇云
            for _ in range(60):
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(0, 80)
                self.particles.spawn(x + math.cos(angle)*dist, y + math.sin(angle)*dist - 30,
                    (255, 200, 100), 1, (30, 60), (-2, 2), (2.0, 4.0))
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
        if has_nuke and self.player:
            pdist = math.hypot(self.player.x - x, self.player.y - y)
            if pdist < explosion_radius * 0.5:
                self.player.take_damage(20)  # 轻微自伤


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
        for event in all_events:
            if event.type == pygame.FINGERDOWN:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.FINGERUP:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self.touch_events.append({"type": "up", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.FINGERMOTION:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.touch_events.append({"type": "down", "pos": event.pos, "id": -1})
            elif event.type == pygame.MOUSEBUTTONUP:
                self.touch_events.append({"type": "up", "pos": event.pos, "id": -1})
            elif event.type == pygame.MOUSEMOTION:
                self.touch_events.append({"type": "move", "pos": event.pos, "id": -1})

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        # 技能卡选择界面
        if self.state == GameState.SKILL_SELECT:
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
                    if event.key == pygame.K_1 and len(self.player.skill_cards) > 0:
                        self._select_skill_card(0)
                    elif event.key == pygame.K_2 and len(self.player.skill_cards) > 1:
                        self._select_skill_card(1)
                    elif event.key == pygame.K_3 and len(self.player.skill_cards) > 2:
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
        if self.state in (GameState.MENU, GameState.SETTINGS, GameState.TUTORIAL, GameState.RECORDS, GameState.STORY_ARCHIVE, GameState.CODEX, GameState.MODE_SELECT, GameState.DIFFICULTY_SELECT, GameState.MOD_MANAGER, GameState.ACHIEVEMENTS):
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
                    # 所有状态都记录鼠标按下，用于按钮点击
                    self.touch_events.append({"type": "down", "pos": event.pos, "id": 0})
                    if self.config.control_mode == ControlMode.TOUCH:
                        logger.debug(f"鼠标触控按下: {event.pos}")

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.touch_events.append({"type": "up", "pos": event.pos, "id": 0})
                if self.config.control_mode == ControlMode.TOUCH:
                    self.touch_events.append({"type": "up", "pos": mouse_pos, "id": 0})

            elif event.type == pygame.MOUSEMOTION:
                if self.config.control_mode == ControlMode.TOUCH:
                    self.touch_events.append({"type": "move", "pos": mouse_pos, "id": 0})

            elif event.type == pygame.MOUSEWHEEL:
                # 剧情资料库滚动
                if self.state == GameState.STORY_ARCHIVE:
                    self.story_archive_scroll -= event.y * 40
                    self.story_archive_scroll = max(0, self.story_archive_scroll)

            elif event.type == pygame.FINGERDOWN:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self.last_touch_pos = (x, y)
                self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
                logger.debug(f"手指按下: ({x:.0f}, {y:.0f}), id={event.finger_id}")

            elif event.type == pygame.FINGERUP:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self.touch_events.append({"type": "up", "pos": (x, y), "id": event.finger_id})
                logger.debug(f"手指抬起: ({x:.0f}, {y:.0f}), id={event.finger_id}")

            elif event.type == pygame.FINGERMOTION:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
                self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})

        return mouse_pos, mouse_pressed

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
            if key == pygame.K_1 and self.player.can_act():
                self.player.switch_weapon(0)
            elif key == pygame.K_2 and self.player.can_act():
                self.player.switch_weapon(1)
            elif key == pygame.K_3 and self.player.can_act():
                self.player.switch_weapon(2)
            elif key == pygame.K_TAB:
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
                            f"技能: {skill.name if skill else '?'}", color=GOLD, lifetime=1.5
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
            elif key == pygame.K_r:
                # R：短按切换下一把武器
                if self.player.can_act() and self.weapon_switch_cooldown <= 0:
                    self.player.next_weapon()
                    self.weapon_switch_cooldown = 0.3
                    weapon = self.player.get_current_weapon()
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 40,
                        f"切换: {weapon.name}", color=PURPLE, lifetime=1.0
                    ))
            elif key == pygame.K_f:
                    pass
            elif key == pygame.K_ESCAPE:
                self.state = GameState.PAUSED
        elif self.state == GameState.PAUSED:
            if key == pygame.K_ESCAPE:
                self.state = GameState.PLAYING
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
                # 强控制：眩晕
                enemy.apply_buff(BuffType.STUN, duration=rg.charge_stun_duration)
                enemy.knockdown(1.0)
                # 击退
                if dist > 0:
                    enemy.x += math.cos(angle_rad) * rg.charge_knockback
                    enemy.y += math.sin(angle_rad) * rg.charge_knockback
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
            # 武器箱：随机获得一把未拥有的武器
            owned = {w.weapon_type for w in self.player.weapons}
            all_weapons = [wt for wt in WeaponType if wt not in (WeaponType.PISTOL,)]
            new_candidates = [wt for wt in all_weapons if wt not in owned]
            if new_candidates:
                new_weapon = random.choice(new_candidates)
            else:
                new_weapon = random.choice(all_weapons)
            self.player.add_weapon(new_weapon)
            # 图鉴解锁：获得武器后解锁
            try:
                codex_unlock_manager.unlock_weapon(new_weapon.name)
            except Exception:
                pass
            if self.session:
                self.session.add_weapon_collected()
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
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, f"武器箱: {Weapon(new_weapon).name}!", color=(200, 160, 80), lifetime=3.0))
        elif item_type == ItemType.TREASURE_CHEST:
            # 宝箱：多重奖励
            if self.session:
                self.session.add_chest_opened()
            rewards = []
            # 1. 随机武器
            all_weapons = [wt for wt in WeaponType if wt not in (WeaponType.PISTOL,)]
            new_weapon = random.choice(all_weapons)
            self.player.add_weapon(new_weapon)
            # 图鉴解锁
            try:
                codex_unlock_manager.unlock_weapon(new_weapon.name)
            except Exception:
                pass
            rewards.append(Weapon(new_weapon).name)
            # 2. 大量经验
            self.player.gain_exp(100)
            rewards.append("+100经验")
            # 3. 治疗
            self.player.heal(30)
            rewards.append("+30HP")
            # 4. 随机符文（局内永久buff，使用新符文系统）
            luck = self.rune_manager.get_bonus("drop_rate_mult") if hasattr(self, 'rune_manager') else 0
            rune_type = random_rune(luck_bonus=luck)
            if hasattr(self, 'rune_manager') and self.rune_manager.add_rune(rune_type):
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
            if hasattr(self, 'rune_manager') and self.rune_manager.add_rune(rune_type):
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
                    self.rune_manager.add_rune(rune_type)
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
                        self.rune_manager.add_rune(rt)
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
        # 应用加成
        self.player.max_hp = self.player._rune_base_max_hp + rm.get_bonus("max_hp")
        self.player.damage_mult = self.player._rune_base_damage_mult + rm.get_bonus("damage_mult")
        self.player.speed_mult = self.player._rune_base_speed_mult + rm.get_bonus("speed_mult")
        self.player.crit_chance = self.player._rune_base_crit_chance + rm.get_bonus("crit_chance")
        self.player.crit_damage_mult = self.player._rune_base_crit_damage + rm.get_bonus("crit_damage_mult")
        self.player.lifesteal = self.player._rune_base_lifesteal + rm.get_bonus("lifesteal")
        self.player.armor = self.player._rune_base_armor + rm.get_bonus("armor")
        self.player.fire_rate_mult = self.player._rune_base_fire_rate + rm.get_bonus("fire_rate_mult")

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
        })
        self.assets.play_sound("grenade_throw")

    def _update_enemy_throwables(self, dt):
        """更新怪物投掷物"""
        if not hasattr(self, 'enemy_throwables'):
            self.enemy_throwables = []
        for g in self.enemy_throwables[:]:
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
            
            # 检测命中玩家
            player_dist = math.hypot(g["x"] - self.player.x, g["y"] - self.player.y)
            if player_dist < 25:
                self._detonate_enemy_throwable(g)
                self.enemy_throwables.remove(g)
                continue
            
            if g["timer"] <= 0:
                self._detonate_enemy_throwable(g)
                self.enemy_throwables.remove(g)

    def _detonate_enemy_throwable(self, g):
        """怪物投掷物爆炸效果"""
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
            # 直接伤害
            player_dist = math.hypot(x - self.player.x, y - self.player.y)
            if player_dist < 80:
                self.player.take_damage(int(damage * 0.5), damage_type="fire")
                self.player.buff_manager.add_buff(BuffType.BURN, duration=3.0)
                
        elif gtype == "acid":
            # 酸液瓶：腐蚀+持续伤害
            self.assets.play_sound("poison_splash")
            self.particles.spawn_explosion(x, y, POISON_GREEN, 50)
            player_dist = math.hypot(x - self.player.x, y - self.player.y)
            if player_dist < 70:
                self.player.take_damage(int(damage), damage_type="melee")
                self.player.buff_manager.add_buff(BuffType.CORROSION, duration=5.0)
                self.player.buff_manager.add_buff(BuffType.POISON, duration=4.0)
                
        elif gtype == "curse":
            # 诅咒瓶：多种debuff
            self.assets.play_sound("curse_cast")
            self.particles.spawn_explosion(x, y, PURPLE, 40)
            player_dist = math.hypot(x - self.player.x, y - self.player.y)
            if player_dist < 70:
                self.player.take_damage(int(damage * 0.7), damage_type="magic")
                self.player.buff_manager.add_buff(BuffType.CURSE, duration=6.0)
                self.player.buff_manager.add_buff(BuffType.WEAKEN, duration=5.0)
                
        else:  # rock
            # 石块：物理伤害+眩晕
            self.assets.play_sound("rock_impact")
            self.camera.shake(10, 0.6)
            self.particles.spawn_explosion(x, y, GRAY, 30)
            player_dist = math.hypot(x - self.player.x, y - self.player.y)
            if player_dist < 40:
                self.player.take_damage(int(damage), damage_type="melee")
                if random.random() < 0.4:
                    self.player.buff_manager.add_buff(BuffType.STUN, duration=1.0)

    def _spawn_horde_rewards(self):
        """尸潮过后根据规模刷新奖励"""
        scale = getattr(self.horde_manager, 'current_scale', 1)
        horde_count = getattr(self.horde_manager, 'horde_count', 0)
        
        # 奖励数量和类型根据规模、时间、难度综合计算
        base_count = {1: 1, 2: 2, 3: 3, 4: 4}.get(scale, 1)
        # 时间系数：每存活3分钟，奖励+1（上限+3）
        time_bonus = min(3, int(self.horde_manager.total_time / 180))
        # 难度系数：困难+1，地狱+2
        diff_bonus = {"困难": 1, "地狱": 2, "hard": 1, "hell": 2}.get(self.config.difficulty, 0)
        reward_count = base_count + time_bonus + diff_bonus
        
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
            chest_chance = 0.35 + min(0.25, self.horde_manager.total_time / 600) + diff_bonus * 0.08 + luck * 0.1
            golden_chance = 0.05 + min(0.1, self.horde_manager.total_time / 1200) + luck * 0.05
            rune_chance = 0.15 + luck * 0.1
            mystery_chance = 0.08
            
            roll = random.random()
            if scale >= 4 or (scale >= 3 and roll < golden_chance):
                item_type = ItemType.GOLDEN_CHEST  # 巨型尸潮必出黄金宝箱
            elif scale >= 3 or (scale >= 2 and roll < chest_chance):
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
            
            self.special_items.append(SpecialItem(rx, ry, item_type))
        
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
                # 玩家也会被烧
                pdist = math.hypot(self.player.x - zone["x"], self.player.y - zone["y"])
                if pdist < zone["radius"]:
                    self.player.take_damage(5, damage_type="fire")
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
        import random
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
        """选择技能卡"""
        if 0 <= index < len(self.player.skill_cards):
            skill = self.player.skill_cards[index]
            self._apply_skill_card(skill)

    def _apply_skill_card(self, skill):
        """应用选中的技能卡"""
        if self.player.skill_tree.upgrade_skill(skill.skill_type):
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                f"升级: {skill.name}!", color=GOLD, lifetime=2.0
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
                ad_skill = self.player.skill_tree.get_skill(SkillType.ADRENALINE)
                if ad_skill:
                    self.player.riot_gear.adrenaline_level = ad_skill.current_level
            # 播放音效
            self.assets.play_sound("skill_select")
        self.player.pending_level_up = False
        self.player.skill_cards = []
        self.skill_card_selector.hide()
        self.state = GameState.PLAYING

    def update(self, dt):
        # 时间减缓效果
        if hasattr(self, 'time_slow_active') and self.time_slow_active:
            self.time_slow_timer -= dt
            if self.time_slow_timer <= 0:
                self.time_slow_active = False
            else:
                dt *= 0.3

        if self.state == GameState.PLAYING:
            self._update_playing(dt)
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
        self._update_black_holes(dt)
        self._update_medic_pods(dt)

    def _update_playing(self, dt):
        # 衰减吸血屏幕效果
        # Mod 每帧钩子
        try:
            trigger_hook(HOOK_GAME_TICK, self, dt)
        except Exception:
            pass
        if self.lifesteal_flash > 0:
            self.lifesteal_flash = max(0, self.lifesteal_flash - dt * 1.5)

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
            _tev = self.touch_events
            self.joystick.handle_touch(_tev, self.scale)
            move_x, move_y = self.joystick.get_direction()

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
                            f"技能: {skill.name if skill else '?'}", color=GOLD, lifetime=1.5
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
                elif not self.weapon_wheel.active:
                    self.weapon_wheel_active = False
            
            if not self.weapon_wheel_active:
                ws_btn = self.touch_buttons["weapon_switch"]
                ws_btn.handle_touch(_tev, self.scale)
                if ws_btn.wheel_just_opened():
                    self.weapon_wheel.show(self.player.weapons, self.player.current_weapon_idx)
                    self.weapon_wheel_active = True
                elif ws_btn.just_released:
                    if self.weapon_switch_cooldown <= 0:
                        self.player.next_weapon()
                        self.weapon_switch_cooldown = 0.3
                        weapon = self.player.get_current_weapon()
                        self.floating_texts.append(FloatingText(
                            self.player.x, self.player.y - 40,
                            f"切换: {weapon.name}", color=PURPLE, lifetime=1.0
                        ))

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

        # 更新防爆套装动画
        self._update_riot_animation(dt)

        # 更新武器切换冷却
        if self.weapon_switch_cooldown > 0:
            self.weapon_switch_cooldown -= dt

        # 应用符文速度加成
        rune_speed_mult = 1.0 + getattr(self, 'rune_buffs', {}).get("speed", 0)
        orig_speed_mult = self.player.speed_mult
        self.player.speed_mult *= rune_speed_mult
        self.player.update(dt, move_x, move_y, mouse_angle, self.world, sprinting=sprinting)
        # 符文：再生效果
        if hasattr(self, 'rune_manager'):
            regen = self.rune_manager.get_bonus("regen")
            if regen > 0 and self.player.hp < self.player.max_hp:
                self.player.hp = min(self.player.max_hp, self.player.hp + regen * dt)
        self.player.speed_mult = orig_speed_mult
        # 盾牌冲撞更新（移动+碰撞伤害）
        self._update_charge(dt)
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

        # 检查升级选择
        if self.player.pending_level_up and self.state != GameState.SKILL_SELECT:
            if self.player.skill_cards:
                self.state = GameState.SKILL_SELECT
                self.skill_card_selector.show(self.player.skill_cards)
                # 记录升级
                if self.session:
                    self.session.add_level_up()
                # 播放升级音效
                self.assets.play_sound("level_up")
            else:
                self.player.pending_level_up = False

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
                # 符文伤害加成
                rune_dmg_mult = 1.0 + getattr(self, 'rune_buffs', {}).get("damage", 0)
                proj_list = weapon.fire(
                    self.player.x, self.player.y, mouse_angle,
                    self.player.damage_mult * self.player.damage_boost_mult * self.player.buff_manager.get_damage_mult() * rune_dmg_mult, self.player.speed_mult,
                    player=self.player
                )
                self.projectiles.extend(proj_list)
                
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

        # 防爆套装自动肘击
        if self.player.riot_gear.equipped and self.config.control_mode == ControlMode.TOUCH:
            if self.aim_button.is_shooting and self.player.riot_gear.can_bash():
                self._perform_bash(self.player.facing_angle)

        # 生成敌人 - 尸潮期间大量刷新，非尸潮期间少量刷新
        spawn_type = self.horde_manager.should_spawn()
        max_enemies = 80 if self.horde_manager.is_horde_active() else 25
        if not hasattr(self, 'time_slow_active') or not self.time_slow_active:
            pass
        else:
            max_enemies = int(max_enemies * 0.7)
        if spawn_type and len(self.enemies) < max_enemies:
            # 处理元组返回：(boss_type, drops_vaccine)
            drops_vaccine = False
            if isinstance(spawn_type, tuple):
                spawn_type, drops_vaccine = spawn_type
            # 故事模式：使用地图配置的怪物权重（Boss除外）
            boss_types = (EnemyType.BOSS_LONG, EnemyType.BOSS_XIANG, EnemyType.BOSS_MUTANT,
                         EnemyType.BOSS_QUEEN, EnemyType.BOSS_TITAN)
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
                codex_unlock_manager.unlock_monster(spawn_type.name)
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

        # 更新敌人
        for enemy in self.enemies[:]:
            # 选择最近的玩家作为目标
            target_x, target_y, target_obj = self.player.x, self.player.y, self.player
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
                # 对玩家造成伤害
                dist_to_player = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_to_player < getattr(enemy, "explode_radius", 100):
                    self.player.take_damage(getattr(enemy, "explode_damage", 80) * 0.5)
                self._on_enemy_death(enemy)
                continue

            # ========== Boss行为返回处理 ==========
            if result == "boss_aoe":
                # 龙某 AOE地面震荡攻击
                aoe_radius = 130
                aoe_damage = int(enemy.damage * 0.85)
                dist_to_player = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_to_player <= aoe_radius:
                    self.player.take_damage(aoe_damage, damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                self.camera.shake(int(6), 0.3)

            elif result == "boss_execution_slash":
                # --------龙某【处决重劈】--------
                exec_radius = 160
                exec_dmg = int(enemy.damage * 2.2)
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= exec_radius:
                    self.player.take_damage(exec_dmg, damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                self.camera.shake(int(14),0.7)
                self.particles.spawn_explosion(enemy.x, enemy.y, CRIMSON,60)

            elif result == "boss_execution_salvo":
                # --------向某【处决霰弹爆发】近距离多段伤害--------
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                pellet_count =8
                pellet_dmg = int(enemy.damage*0.45)
                for _ in range(pellet_count):
                    if dist_pl <180:
                        self.player.take_damage(pellet_dmg, damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.camera.shake(int(12),0.65)
                self.particles.spawn_explosion(enemy.x, enemy.y, ORANGE,55)

            elif result == "boss_execution_mutant":
                # --------变异体【毁灭连招终结】超高伤害AOE--------
                exec_radius = 180
                exec_dmg = int(enemy.damage * 3.0)
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= exec_radius:
                    self.player.take_damage(exec_dmg, damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                self.camera.shake(18, 0.8)
                self.particles.spawn_explosion(enemy.x, enemy.y, BLOOD_RED, 70)
                self.particles.spawn_explosion(enemy.x, enemy.y, CRIMSON, 40)

            elif result == "boss_execution_queen":
                # --------尸潮女王【虫群吞噬】召唤大量小怪+持续伤害--------
                for _ in range(6):
                    angle = random.uniform(0, math.pi * 2)
                    spawn_x = enemy.x + math.cos(angle) * 100
                    spawn_y = enemy.y + math.sin(angle) * 100
                    minion = Enemy(spawn_x, spawn_y, random.choice([EnemyType.ZOMBIE_FAST, EnemyType.ZOMBIE_CRAWLER, EnemyType.ZOMBIE_SPITTER]), 1, self.difficulty)
                    self.enemies.append(minion)
                    try:
                        codex_unlock_manager.unlock_monster(minion.enemy_type.name if hasattr(minion, "enemy_type") else minion.type.name)
                    except Exception:
                        pass
                self.player.buff_manager.add_buff(BuffType.POISON, 8.0)
                self.camera.shake(10, 0.5)
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 60)

            elif result == "boss_execution_titan":
                # --------泰坦【泰坦之怒】超大范围地震--------
                exec_radius = 250
                exec_dmg = int(enemy.damage * 2.0)
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= exec_radius:
                    self.player.take_damage(exec_dmg, damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                self.camera.shake(25, 1.0)
                self.particles.spawn_explosion(enemy.x, enemy.y, GRAY, 80)
                self.particles.spawn_explosion(enemy.x, enemy.y, CHARCOAL, 50)

            # === 新增Boss技能处理 ===
            elif result == "boss_ground_slam":
                # 龙某地震波：大范围环形AOE
                slam_radius = 220
                slam_dmg = int(enemy.damage * 1.2)
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= slam_radius:
                    self.player.take_damage(slam_dmg, damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                self.camera.shake(10, 0.5)
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
                # 龙某狂暴冲锋拖尾+碰撞伤害
                self.particles.spawn_particle(enemy.x, enemy.y, 0, 0, CRIMSON, 0.3, 12)
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl < enemy.size + self.player.size + 5:
                    self.player.take_damage(int(enemy.damage * 0.8), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)

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
                # 向某弹幕扫射：环形12发子弹
                for i in range(12):
                    angle = i * math.pi * 2 / 12
                    proj = Projectile(
                        enemy.x, enemy.y,
                        math.cos(angle) * 6, math.sin(angle) * 6,
                        int(enemy.damage * 0.5), 400, PURPLE, 4
                    )
                    self.enemy_projectiles.append(proj)
                self.camera.shake(4, 0.2)

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
                # 快速僵尸冲刺
                self.particles.spawn_particle(enemy.x, enemy.y, 0, 0, POISON_GREEN, 0.2, 8)

            elif result == "tank_slam":
                # 坦克重击AOE
                slam_r = 70
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= slam_r:
                    self.player.take_damage(int(enemy.damage * 1.3), damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
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

            elif result == "phantom_teleport":
                # 幻影瞬移特效
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 20)

            elif result == "shield_charge":
                # 盾兵冲锋碰撞伤害
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl < enemy.size + self.player.size + 10:
                    self.player.take_damage(int(enemy.damage * 1.5), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.particles.spawn_particle(enemy.x, enemy.y, 0, 0, CHARCOAL, 0.3, 10)

            # === 新普通僵尸技能 ===
            elif result == "leaper_strike":
                # 跳跃僵尸扑击
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl < enemy.size + self.player.size + 15:
                    self.player.take_damage(int(enemy.damage * getattr(enemy, "leap_damage_mult", 2.0)), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.assets.play_sound("zombie_leap")
                self.particles.spawn_explosion(enemy.x, enemy.y, ORANGE, 12)

            elif result == "wraith_fear":
                # 怨灵恐惧
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl < 120:
                    self.player.buff_manager.add_buff(BuffType.FEAR, 2.0)
                self.assets.play_sound("fear_scream")
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 15)

            # === 精英怪技能 ===
            elif result == "elite_heavy_slam":
                # 精英蛮兵重击
                slam_r = 80
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= slam_r:
                    self.player.take_damage(int(enemy.damage * getattr(enemy, "heavy_damage_mult", 2.5)), damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                self.camera.shake(6, 0.3)
                self.assets.play_sound("elite_heavy_attack")
                self.particles.spawn_explosion(enemy.x, enemy.y, DARK_RED, 20)

            elif result == "elite_assassin_dash":
                # 精英刺客冲刺
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl < enemy.size + self.player.size + 10:
                    self.player.take_damage(int(enemy.damage * getattr(enemy, "dash_damage_mult", 3.0)), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.assets.play_sound("elite_dash")
                self.particles.spawn_particle(enemy.x, enemy.y, 0, 0, CYAN, 0.3, 12)

            # === 新Boss技能 ===
            elif result == "mutant_combo_hit":
                # 变异体连招攻击
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl < enemy.size + self.player.size + 20:
                    self.player.take_damage(int(enemy.damage * 1.2), damage_type="melee", attack_x=enemy.x, attack_y=enemy.y)
                self.assets.play_sound("boss_mutant_combo")
                self.particles.spawn_explosion(enemy.x, enemy.y, BLOOD_RED, 15)
                self.camera.shake(4, 0.15)

            elif result == "mutant_combo_finisher":
                # 变异体连招终结AOE
                finisher_r = 120
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= finisher_r:
                    self.player.take_damage(int(enemy.damage * getattr(enemy, "combo_damage_mult", 2.5)), damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
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
                        codex_unlock_manager.unlock_monster(minion.enemy_type.name if hasattr(minion, "enemy_type") else minion.type.name)
                    except Exception:
                        pass
                self.assets.play_sound("boss_queen_summon")
                self.particles.spawn_explosion(enemy.x, enemy.y, PURPLE, 30)

            elif result == "queen_mind_control":
                # 女王精神控制（恐惧）
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl < 300:
                    self.player.buff_manager.add_buff(BuffType.FEAR, 3.0)
                self.assets.play_sound("boss_queen_tentacle")
                self.particles.spawn_explosion(self.player.x, self.player.y, PURPLE, 20)

            elif result == "queen_poison_cloud":
                # 女王毒雾
                self.player.buff_manager.add_buff(BuffType.POISON, 5.0)
                self.particles.spawn_explosion(self.player.x, self.player.y, POISON_GREEN, 25)

            elif result == "queen_tentacle":
                # 女王触手突袭
                tentacle_r = 60
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= tentacle_r:
                    self.player.take_damage(int(enemy.damage * 1.5), damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                self.assets.play_sound("boss_queen_tentacle")
                self.particles.spawn_explosion(self.player.x, self.player.y, PURPLE, 20)

            elif result == "titan_stomp":
                # 泰坦地震踩踏
                stomp_r = getattr(enemy, "stomp_radius", 150)
                dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
                if dist_pl <= stomp_r:
                    self.player.take_damage(getattr(enemy, "stomp_damage", 120), damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
                self.assets.play_sound("boss_titan_stomp")
                self.camera.shake(15, 0.5)
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

            # 怪物与玩家碰撞
            if enemy.get_rect().colliderect(self.player.get_rect()):
                dx = enemy.x - self.player.x
                dy = enemy.y - self.player.y
                dist = math.hypot(dx, dy)
                if dist > 0:
                    min_dist = enemy.size + self.player.size + 2
                    if dist < min_dist:
                        push_x = (dx / dist) * (min_dist - dist) * 0.5
                        push_y = (dy / dist) * (min_dist - dist) * 0.5
                        enemy.x += push_x
                        enemy.y += push_y
                        self.player.x -= push_x
                        self.player.y -= push_y

                if enemy.knockdown_timer <= 0:
                    angle_to_enemy = math.atan2(dy, dx)
                    facing_rad = math.radians(self.player.facing_angle)
                    angle_diff = abs(math.atan2(math.sin(angle_to_enemy - facing_rad),
                                               math.cos(angle_to_enemy - facing_rad)))
                    from_front = angle_diff < math.pi / 3

                    if self.player.riot_gear.equipped and from_front:
                        shield_rect = self.player.riot_gear.get_shield_rect(self.player.x, self.player.y)
                        if shield_rect and shield_rect.colliderect(enemy.get_rect()):
                            push_back = 15
                            enemy.x += math.cos(angle_to_enemy) * push_back
                            enemy.y += math.sin(angle_to_enemy) * push_back
                            self.player.take_damage(enemy.damage, "melee", True, enemy.x, enemy.y)
                        else:
                            self.player.take_damage(enemy.damage, "melee", from_front, enemy.x, enemy.y)
                    else:
                        self.player.take_damage(enemy.damage, "melee", from_front, enemy.x, enemy.y)

                    # 僵尸攻击施加debuff
                    etype = enemy.enemy_type
                    if etype == EnemyType.ZOMBIE_FAST and random.random() < 0.25:
                        self.player.buff_manager.add_buff(BuffType.BLEED, duration=4.0)
                    elif etype == EnemyType.ZOMBIE_TANK and random.random() < 0.3:
                        self.player.buff_manager.add_buff(BuffType.FRACTURE, duration=5.0)
                    elif etype == EnemyType.ZOMBIE_NORMAL and random.random() < 0.1:
                        self.player.buff_manager.add_buff(BuffType.BLEED, duration=3.0)

                    # 确保玩家被推动后不在障碍物内
                    self.player.ensure_safe_position(self.world)

                    if self.config.screen_shake:
                        self.camera.shake(6, 0.4)

            # 普通远程敌人攻击（选择最近玩家作为目标）
            if getattr(enemy, "attack_range", 0) > 0 and not getattr(enemy, "is_boss", False):
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
            if proj.get_rect().colliderect(self.player.get_rect()):
                # 检测是否被盾牌阻挡
                dx = proj.x - self.player.x
                dy = proj.y - self.player.y
                attack_angle = math.atan2(dy, dx)
                facing_rad = math.radians(self.player.facing_angle)
                angle_diff = abs(math.atan2(math.sin(attack_angle - facing_rad), 
                                           math.cos(attack_angle - facing_rad)))
                from_front = angle_diff < math.pi / 3

                if self.player.riot_gear.equipped and from_front and not self.player.riot_gear.shield_broken:
                    # 盾牌阻挡远程攻击
                    self.player.riot_gear.take_damage(proj.damage * 0.3, "ranged", True, proj.x, proj.y)
                    proj.alive = False
                    self.particles.spawn(proj.x, proj.y, CYAN, 5, (2, 4), (-2, 2), (0.2, 0.5))
                    self.floating_texts.append(FloatingText(proj.x, proj.y - 20, "格挡!", color=CYAN, lifetime=0.5))
                else:
                    self.player.take_damage(proj.damage, "ranged")
                    proj.alive = False
                    if self.config.screen_shake:
                        self.camera.shake(2, 0.15)

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
                    dist_pl = math.hypot(self.player.x - grenade["target_x"], self.player.y - grenade["target_y"])
                    if dist_pl < grenade["radius"]:
                        dmg = grenade["damage"] * (1 - dist_pl / grenade["radius"])
                        self.player.take_damage(int(dmg), damage_type="aoe", attack_x=grenade["target_x"], attack_y=grenade["target_y"])
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

        # 摄像机跟随
        self.camera.follow(self.player.x, self.player.y, dt)

        if self.player.hp <= 0:
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
        # 更新成就toast提示队列
        remove_list = []
        for toast in self.ach_toast_queue:
            toast["timer"] -= dt
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
        return targets

    def _damage_player_target(self, target, damage, damage_type="melee", attack_x=0, attack_y=0):
        """对玩家目标造成伤害（单人模式只有本地玩家）"""
        if target["is_local"]:
            self.player.take_damage(damage, damage_type=damage_type, attack_x=attack_x, attack_y=attack_y)

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

    def _on_enemy_death(self, enemy):
        # 记录击杀
        # Mod 敌人死亡钩子
        try:
            trigger_hook(HOOK_ENEMY_DEATH, enemy, self.player)
        except Exception:
            pass
        if self.session:
            self.session.add_kill(enemy.enemy_type)
        # 播放击杀音效
        if getattr(enemy, "is_boss", False):
            self.assets.play_sound("boss_death")
            self.last_boss_death_pos = (enemy.x, enemy.y)
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
            dist_pl = math.hypot(self.player.x - enemy.x, self.player.y - enemy.y)
            if dist_pl < splash_r:
                self.player.take_damage(int(15 * (1 - dist_pl / splash_r)), damage_type="aoe", attack_x=enemy.x, attack_y=enemy.y)
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
                    codex_unlock_manager.unlock_monster(small_enemy.enemy_type.name if hasattr(small_enemy, "enemy_type") else small_enemy.type.name)
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
