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

from config import (BASE_WIDTH, BASE_HEIGHT, GameState, ControlMode, GameMode, 
                   EnemyType, WeaponType, SkillType, ItemType, WHITE, BLACK, RED, GREEN, 
                   BLUE, YELLOW, ORANGE, GRAY, DARK_GRAY, CYAN, PURPLE, GOLD, AMBER, CRIMSON,
                   CHARCOAL, VOID_BLACK, DARK_RED, LIME, TEAL, RUST, POISON_GREEN, BLOOD_RED,
                   SMOKE_GRAY, FIRE_ORANGE, FIRE_YELLOW, MUZZLE_FLASH)
from assets import AssetManager, SOUND_MAP, MUSIC_MAP
from records import GameRecords, GameSession
from logger import GameLogger
from ui import (FontManager, Button, VirtualJoystick, TouchButton, DamageNumber, 
                FloatingText, ParticleSystem, AimButton, SkillSelector, SkillCaster, 
                SkillCardSelector, WeaponSwitchButton, draw_dashed_line)
from skills import SkillTree
from weapons import Weapon, Projectile
from entities import Player, Enemy, ExpOrb, RiotGear
from world import GameWorld, HordeManager, SpecialItem
from dialogue import DialogueSystem
from skill_wheel import SkillWheel, WeaponWheel
from renderer import Camera, Renderer

class Config:
    def __init__(self):
        self.control_mode = ControlMode.KEYBOARD
        self.game_mode = GameMode.TIMED
        self.sound_volume = 0.7
        self.music_volume = 0.5
        self.difficulty = "普通"
        self.show_damage_numbers = True
        self.screen_shake = True
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
        except Exception as e:
            logger.error(f"配置加载失败: {e}")

    def save(self):
        data = {
            "control_mode": self.control_mode.name,
            "game_mode": self.game_mode.name,
            "sound_volume": self.sound_volume,
            "music_volume": self.music_volume,
            "difficulty": self.difficulty
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

        base_path = os.path.dirname(os.path.abspath(__file__))
        FontManager.init(base_path)

        self.config = Config()
        logger.info(f"控制模式: {self.config.control_mode.name}")

        self.font_small = FontManager.get(14)
        self.font = FontManager.get(18)
        self.font_large = FontManager.get(24)
        self.font_title = FontManager.get(40)

        self.state = GameState.MENU
        self.previous_state = None

        self.player = None
        self.world = None
        self.horde_manager = None
        self.camera = None
        self.particles = None
        self.dialogue = None

        self.enemies = []
        self.projectiles = []
        self.exp_orbs = []
        self.damage_numbers = []
        self.floating_texts = []
        self.enemy_projectiles = []

        # 技能相关
        self.selected_skill = SkillType.GRENADE
        self.skill_wheel = SkillWheel()
        self.weapon_wheel = WeaponWheel()
        self.skill_wheel_active = False
        self.weapon_wheel_active = False
        self.skill_selector = None
        self.skill_caster = None
        self.skill_card_selector = SkillCardSelector()

        # 菜单滚动
        self.menu_scroll_offset = 0
        self.settings_scroll_offset = 0
        self.tutorial_scroll_offset = 0
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
            "钩爪集成在防爆套装技能，装备后即可使用",
            "尸潮会定期来袭，准备好面对无尽的黑暗...",
            "找到疫苗可以拯救你的朋友...",
            "祝你好运，幸存者！"
        ]

        # 资源管理器
        self.assets = AssetManager(base_path)
        self.assets.print_status()

        # 全局记录系统
        self.records = GameRecords(base_path)
        self.session = None

        #成就页面滚动
        self.ach_scroll_offset = 0
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
        """触控按钮位置调整 - II键移到右半屏上方中央"""
        # 移动摇杆 - 左下角
        self.joystick = VirtualJoystick(120, BASE_HEIGHT - 120, 70)
        # 攻击/瞄准摇杆 - 右下角
        self.aim_button = AimButton(BASE_WIDTH - 200, BASE_HEIGHT - 150, 70)

        # 触控按钮 - 调整位置
        self.touch_buttons = {
            "shoot": TouchButton(BASE_WIDTH - 200, BASE_HEIGHT - 150, 70, "射", RED),
            "weapon_switch": WeaponSwitchButton(BASE_WIDTH - 340, BASE_HEIGHT - 280, 55, "换", PURPLE),
            "pause": TouchButton(BASE_WIDTH - 60, 60, 45, "II", GRAY),  # 右半屏上方中央
        }
        # 技能切换按钮
        self.skill_selector = SkillSelector(BASE_WIDTH - 80, BASE_HEIGHT - 280, 55)
        # 技能释放按钮
        self.skill_caster = SkillCaster(BASE_WIDTH - 80, BASE_HEIGHT - 150, 60)
        logger.info("触控控件初始化完成")

    def _setup_menus(self):
        cx = BASE_WIDTH // 2 - 100
        self.menu_buttons = [
            Button(cx, 240, 200, 50, "开始游戏", color=GREEN),
            Button(cx, 300, 200, 50, "记录", color=GOLD),
            Button(cx, 360, 200, 50, "成就", color=AMBER),
            Button(cx, 420, 200, 50, "设置", color=GRAY),
            Button(cx, 480, 200, 50, "教程", color=BLUE),
            Button(cx, 540, 200, 50, "退出", color=RED),
        ]
        self.settings_buttons = [
            Button(cx, 180, 200, 45, "控制: 键控", color=GRAY),
            Button(cx, 245, 200, 45, "模式: 限时", color=GRAY),
            Button(cx, 310, 200, 45, "难度: 普通", color=GRAY),
            Button(cx, 420, 200, 50, "返回", color=RED),
        ]
        self.pause_buttons = [
            Button(cx, 240, 200, 50, "继续", color=GREEN),
            Button(cx, 310, 200, 50, "返回菜单", color=RED),
        ]
        logger.info("菜单按钮初始化完成")

    def start_game(self):
        logger.info("开始新游戏")
        # 初始化游戏会话记录
        self.session = self.records.on_game_start(self.config.difficulty, self.config.game_mode)
        self.session.set_difficulty(self.config.difficulty)
        self.session.set_mode(self.config.game_mode)
        # 播放游戏音乐
        self.assets.play_music("gameplay")
        try:
            self.world = GameWorld()
            logger.info(f"无限世界创建完成")

            self.player = Player(0, 0)
            logger.info(f"玩家创建: ({self.player.x}, {self.player.y})")

            self.horde_manager = HordeManager(self.config.game_mode, self.config.difficulty)
            self.camera = Camera(BASE_WIDTH, BASE_HEIGHT)
            self.particles = ParticleSystem()
            self.dialogue = DialogueSystem()

            self.enemies = []
            self.projectiles = []
            self.exp_orbs = []
            self.damage_numbers = []
            self.floating_texts = []
            self.enemy_projectiles = []

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
            SkillType.GRAPPLE_PULL: 6.0, 
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
            SkillType.GRAPPLE_PULL: 6.0, 
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
            self._throw_grenade_at(target_x, target_y)
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
        """手雷技能"""
        self._throw_grenade()
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

    def _create_turret_effect(self, tx, ty):
        if not hasattr(self, 'turrets'):
            self.turrets = []
        self.turrets.append({"x": tx, "y": ty, "timer": 10.0, "fire_timer": 0})

    def _update_turrets(self, dt):
        if not hasattr(self, 'turrets'):
            self.turrets = []

        for turret in self.turrets[:]:
            turret["timer"] -= dt
            turret["fire_timer"] -= dt

            if turret["fire_timer"] <= 0:
                turret["fire_timer"] = 0.5
                closest = None
                closest_dist = 250
                for enemy in self.enemies:
                    dist = math.hypot(enemy.x - turret["x"], enemy.y - turret["y"])
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = enemy

                if closest:
                    dx = closest.x - turret["x"]
                    dy = closest.y - turret["y"]
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        proj = Projectile(
                            turret["x"], turret["y"],
                            dx / dist * 12, dy / dist * 12,
                            30, 300, YELLOW, 4, pierce=2
                        )
                        self.projectiles.append(proj)
                        self.particles.spawn(turret["x"], turret["y"], YELLOW, 3)

            if turret["timer"] <= 0:
                self.particles.spawn_explosion(turret["x"], turret["y"], GRAY, 10)
                self.turrets.remove(turret)

    def _skill_airstrike(self):
        """空袭技能"""
        if self.config.control_mode == ControlMode.KEYBOARD:
            mouse_pos = pygame.mouse.get_pos()
            target_x = mouse_pos[0] / self.scale + self.camera.x
            target_y = mouse_pos[1] / self.scale + self.camera.y
        else:
            angle_rad = math.radians(self.player.facing_angle)
            target_x = self.player.x + math.cos(angle_rad) * 500
            target_y = self.player.y + math.sin(angle_rad) * 500

        self.floating_texts.append(FloatingText(
            target_x, target_y - 50, "空袭来袭!", color=RED, lifetime=2.0
        ))
        if not hasattr(self, 'airstrikes'):
            self.airstrikes = []
        self.airstrikes.append({"x": target_x, "y": target_y, "timer": 2.0, "warned": False})
        return True

    def _update_airstrikes(self, dt):
        """更新空袭效果 - 超增强"""
        if not hasattr(self, 'airstrikes'):
            self.airstrikes = []

        for strike in self.airstrikes[:]:
            strike["timer"] -= dt

            if strike["timer"] <= 0:
                self.particles.spawn_explosion(strike["x"], strike["y"], ORANGE, 150)
                self.particles.spawn_explosion(strike["x"], strike["y"], RED, 100)
                self.particles.spawn_explosion(strike["x"], strike["y"], FIRE_YELLOW, 80)
                self.particles.spawn_explosion(strike["x"], strike["y"], WHITE, 50)
                self.camera.shake(40, 1.5)

                # 多层冲击波
                for i in range(12):
                    radius = 30 + i * 30
                    alpha = int(200 - i * 15)
                    shock_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                    pygame.draw.circle(shock_surf, (255, 255, 255, alpha), (radius, radius), radius, max(2, int(5 - i * 0.3)))
                    self.screen.blit(shock_surf, (int((strike["x"] - self.camera.x) * self.scale) - radius,
                                                 int((strike["y"] - self.camera.y) * self.scale) - radius))

                # 烟雾
                for _ in range(50):
                    angle = random.uniform(0, math.pi * 2)
                    dist = random.uniform(20, 200)
                    sx = strike["x"] + math.cos(angle) * dist
                    sy = strike["y"] + math.sin(angle) * dist
                    self.particles.spawn(sx, sy, SMOKE_GRAY, 1, (25, 50), (-3, 3), (2.0, 4.0))

                # 火焰
                for _ in range(40):
                    angle = random.uniform(0, math.pi * 2)
                    dist = random.uniform(10, 120)
                    fx = strike["x"] + math.cos(angle) * dist
                    fy = strike["y"] + math.sin(angle) * dist
                    self.particles.spawn(fx, fy, FIRE_ORANGE, 1, (12, 30), (-4, 4), (1.0, 2.5))
                    self.particles.spawn(fx, fy, FIRE_YELLOW, 1, (6, 18), (-3, 3), (0.5, 1.8))

                # 火花
                for _ in range(50):
                    angle = random.uniform(0, math.pi * 2)
                    speed = random.uniform(8, 30)
                    sx = strike["x"] + math.cos(angle) * random.uniform(0, 50)
                    sy = strike["y"] + math.sin(angle) * random.uniform(0, 50)
                    self.particles.spawn(sx, sy, (255, 255, 200), 1, (4, 10), (-speed, speed), (0.3, 1.5))

                self.particles.spawn(strike["x"], strike["y"], CRIMSON, 60, (12, 30), (-18, 18), (0.5, 1.8))
                self.particles.spawn(strike["x"], strike["y"], YELLOW, 40, (8, 20), (-12, 12), (0.3, 1.2))
                self.particles.spawn(strike["x"], strike["y"], WHITE, 25, (5, 15), (-10, 10), (0.2, 0.8))

                for enemy in self.enemies:
                    dist = math.hypot(enemy.x - strike["x"], enemy.y - strike["y"])
                    if dist < 300:
                        damage = 600 * (1 - dist / 300)
                        if dist > 0:
                            push_x = (enemy.x - strike["x"]) / dist * 150
                            push_y = (enemy.y - strike["y"]) / dist * 150
                            enemy.x += push_x
                            enemy.y += push_y
                            enemy.knockdown(1.0)
                        enemy.take_damage(damage)
                        self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, damage, is_crit=True))
                        if not enemy.alive:
                            self._on_enemy_death(enemy)

                self.airstrikes.remove(strike)
            elif strike["timer"] <= 1.0 and not strike.get("warned", False):
                strike["warned"] = True
                self.particles.spawn(strike["x"], strike["y"], RED, 30, size_range=(8, 15), 
                                   velocity_range=(-2, 2), lifetime_range=(0.5, 1.0))

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
        """钩爪技能"""
        if not self.player.riot_gear.equipped:
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                "需要先装备防爆套装!", color=RED, lifetime=1.5
            ))
            return False
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
        """冰霜新星"""
        for enemy in self.enemies:
            dist = math.hypot(enemy.x - self.player.x, enemy.y - self.player.y)
            if dist < 200:
                enemy.frozen_timer = 2.0
        self.particles.spawn_explosion(self.player.x, self.player.y, BLUE, 60)
        self.camera.shake(8, 0.3)
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, "冰霜新星!", color=BLUE, lifetime=1.5
        ))
        return True

    def _skill_black_hole(self, x, y):
        """黑洞技能"""
        if not hasattr(self, 'black_holes'):
            self.black_holes = []
        self.black_holes.append({"x": x, "y": y, "timer": 5.0, "radius": 150})
        self.floating_texts.append(FloatingText(
            x, y - 30, "黑洞生成!", color=PURPLE, lifetime=1.5
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
                    enemy.take_damage(50 * dt)
                    if not enemy.alive:
                        self._on_enemy_death(enemy)
            # 视觉效果
            self.particles.spawn(bh["x"], bh["y"], PURPLE, 5, (2, 5), (-2, 2), (0.3, 0.6))
            if bh["timer"] <= 0:
                self.particles.spawn_explosion(bh["x"], bh["y"], PURPLE, 30)
                self.black_holes.remove(bh)

    def _skill_chain_lightning(self, angle):
        """连锁闪电"""
        start_x = self.player.x
        start_y = self.player.y
        target_x = start_x + math.cos(angle) * 350
        target_y = start_y + math.sin(angle) * 350

        # 寻找最近的敌人作为起点
        closest = None
        closest_dist = 350
        for enemy in self.enemies:
            dist = math.hypot(enemy.x - target_x, enemy.y - target_y)
            if dist < closest_dist:
                closest_dist = dist
                closest = enemy

        if closest:
            # 连锁伤害
            hit_enemies = [closest]
            current_target = closest
            for _ in range(4):  # 最多连锁4次
                next_target = None
                next_dist = 200
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
                damage = 80 * (0.7 ** i)  # 递减伤害
                enemy.take_damage(damage)
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, damage, color=YELLOW))
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
        """医疗舱"""
        if not hasattr(self, 'medic_pods'):
            self.medic_pods = []
        self.medic_pods.append({"x": x, "y": y, "timer": 8.0, "heal_timer": 0})
        self.floating_texts.append(FloatingText(
            x, y - 30, "医疗舱部署!", color=GREEN, lifetime=1.5
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
                if dist < 100:
                    self.player.heal(10)
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 40, "+10", color=GREEN, lifetime=0.5
                    ))
            self.particles.spawn(pod["x"], pod["y"], GREEN, 3, (2, 4), (-1, 1), (0.5, 1.0))
            if pod["timer"] <= 0:
                self.medic_pods.remove(pod)

    def _skill_shockwave(self):
        """冲击波"""
        for enemy in self.enemies:
            dist = math.hypot(enemy.x - self.player.x, enemy.y - self.player.y)
            if dist < 150 and dist > 0:
                push_x = (enemy.x - self.player.x) / dist * 100
                push_y = (enemy.y - self.player.y) / dist * 100
                enemy.x += push_x
                enemy.y += push_y
                enemy.take_damage(50)
                self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, 50, color=ORANGE))
                if not enemy.alive:
                    self._on_enemy_death(enemy)
        self.particles.spawn_explosion(self.player.x, self.player.y, ORANGE, 40)
        self.camera.shake(15, 0.5)
        self.floating_texts.append(FloatingText(
            self.player.x, self.player.y - 40, "冲击波!", color=ORANGE, lifetime=1.5
        ))
        return True

    def handle_events(self):
        self.touch_events = []
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        # 技能卡选择界面
        if self.state == GameState.SKILL_SELECT:
            for event in pygame.event.get():
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
            for event in pygame.event.get():
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

        # 菜单/设置/教程的滚轮和触摸滚动
        if self.state in (GameState.MENU, GameState.SETTINGS, GameState.TUTORIAL, GameState.RECORDS):
            for event in pygame.event.get():
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
                    if self.state == GameState.MENU:
                        self.menu_scroll_offset = max(0, self.menu_scroll_offset - event.y * 40)
                    elif self.state == GameState.SETTINGS:
                        self.settings_scroll_offset = max(0, self.settings_scroll_offset - event.y * 40)
                    elif self.state == GameState.TUTORIAL:
                        self.tutorial_scroll_offset = max(0, self.tutorial_scroll_offset - event.y * 40)
                    elif self.state == GameState.RECORDS:
                        self.records_scroll_offset = max(0, getattr(self, 'records_scroll_offset', 0) - event.y * 40)
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
            for event in pygame.event.get():
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
                    self.touch_events.append({"type": "move", "pos": (x, y), "id": event.finger_id})
                elif event.type == pygame.FINGERDOWN:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
                    self.touch_events.append({"type": "down", "pos": (x, y), "id": event.finger_id})
                elif event.type == pygame.FINGERUP:
                    x = event.x * self.scaled_width
                    y = event.y * self.scaled_height
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
        
        for event in pygame.event.get():
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

            elif event.type == pygame.FINGERDOWN:
                x = event.x * self.scaled_width
                y = event.y * self.scaled_height
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
        if self.state == GameState.PLAYING:
            if key == pygame.K_1:
                self.player.switch_weapon(0)
            elif key == pygame.K_2:
                self.player.switch_weapon(1)
            elif key == pygame.K_3:
                self.player.switch_weapon(2)
            elif key == pygame.K_TAB:
                # Tab：短按切换下一个技能
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
            elif key == pygame.K_g:
                import time
                self.key_g_press_start = time.time()
                self.key_g_held = True
                self.g_aim_started = False
                self.skill_caster.is_aiming = False
                # 只记录按下，不释放技能
            elif key == pygame.K_r:
                # R：短按切换下一把武器
                if self.weapon_switch_cooldown <= 0:
                    self.player.next_weapon()
                    self.weapon_switch_cooldown = 0.3
                    weapon = self.player.get_current_weapon()
                    self.floating_texts.append(FloatingText(
                        self.player.x, self.player.y - 40,
                        f"切换: {weapon.name}", color=PURPLE, lifetime=1.0
                    ))
            elif key == pygame.K_ESCAPE:
                self.state = GameState.PAUSED
        elif self.state == GameState.PAUSED:
            if key == pygame.K_ESCAPE:
                self.state = GameState.PLAYING
        elif self.state == GameState.RECORDS:
            if key == pygame.K_ESCAPE:
                self.state = GameState.MENU

    def _handle_keyup(self, key):
        import time
        if self.state != GameState.PLAYING:
            return
        if key == pygame.K_g:
            hold_time = time.time() - self.key_g_press_start
            self.key_g_held = False
            self.skill_caster.is_aiming = False #松开关闭瞄准标记

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
        """肘击"""
        # 记录肘击
        if self.session:
            self.session.add_bash()
        # 播放音效
        self.assets.play_sound("bash")
        damage, knockdown, bash_range = self.player.riot_gear.bash(direction_angle)
        if damage > 0:
            angle_rad = math.radians(self.player.riot_gear.bash_direction)
            bash_x = self.player.x + math.cos(angle_rad) * bash_range * 0.5
            bash_y = self.player.y + math.sin(angle_rad) * bash_range * 0.5

            hit_any = False
            for enemy in self.enemies:
                dist = math.hypot(enemy.x - bash_x, enemy.y - bash_y)
                if dist < bash_range:
                    is_crit = random.random() < self.player.crit_chance
                    actual_damage = damage * self.player.damage_mult * (self.player.crit_damage if is_crit else 1)
                    enemy.take_damage(actual_damage)
                    if knockdown:
                        enemy.knockdown(2.0)
                    push_dist = 100
                    enemy.x += math.cos(angle_rad) * push_dist
                    enemy.y += math.sin(angle_rad) * push_dist
                    self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, actual_damage, is_crit=is_crit))
                    self.particles.spawn_blood(enemy.x, enemy.y, 10)
                    self.particles.spawn_explosion(enemy.x, enemy.y, CYAN, 20)
                    hit_any = True
                    if not enemy.alive:
                        self._on_enemy_death(enemy)

            if hit_any:
                self.particles.spawn(bash_x, bash_y, WHITE, 25, (5, 25), (-12, 12), (0.2, 0.5))
                self.camera.shake(10, 0.4)
                self.floating_texts.append(FloatingText(bash_x, bash_y - 30, "肘击！", color=CYAN, lifetime=1.0))
            else:
                self.particles.spawn(bash_x, bash_y, CYAN, 12, (3, 12), (-6, 6), (0.1, 0.3))

    def _perform_grapple_aimed(self, angle, max_dist=800):
        """带瞄准方向和距离的钩爪"""
        if not self.player.riot_gear.equipped:
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                "需要先装备防爆套装!", color=RED, lifetime=1.5
            ))
            return False
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
        """在指定位置执行钩爪核心逻辑 - 新逻辑"""
        if not self.player.riot_gear.equipped:
            self.floating_texts.append(FloatingText(
                self.player.x, self.player.y - 40, 
                "需要先装备防爆套装!", color=RED, lifetime=1.5
            ))
            return False

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

    def _apply_item_effect(self, item_type):
        """应用特殊道具效果"""
        # 记录道具收集
        if self.session:
            self.session.add_item_collected()
        # 播放拾取音效
        self.assets.play_sound("pickup_item")
        if item_type == ItemType.VACCINE:
            self.has_vaccine = True
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "获得疫苗！", color=GREEN, lifetime=3.0))
        elif item_type == ItemType.HEALTH_PACK:
            self.player.heal(50)
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "+50 HP", color=RED, lifetime=1.5))
        elif item_type == ItemType.AMMO_BOX:
            # 补充所有武器弹药
            for weapon in self.player.weapons:
                if hasattr(weapon, 'current_ammo') and weapon.current_ammo != "∞":
                    weapon.current_ammo = weapon.max_ammo
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "弹药补给", color=YELLOW, lifetime=1.5))
        elif item_type == ItemType.SPEED_BOOST:
            self.player.speed_boost_timer = 10.0
            self.player.speed_boost_mult = 1.5
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "速度提升！", color=BLUE, lifetime=2.0))
        elif item_type == ItemType.DAMAGE_BOOST:
            self.player.damage_boost_timer = 10.0
            self.player.damage_boost_mult = 2.0
            self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "伤害提升！", color=ORANGE, lifetime=2.0))
        elif item_type == ItemType.SHIELD_REPAIR:
            if self.player.riot_gear.equipped:
                self.player.riot_gear.viewing_window_hp = min(
                    self.player.riot_gear.max_viewing_window_hp,
                    self.player.riot_gear.viewing_window_hp + 50
                )
                self.player.riot_gear.shield_broken = False
                self.floating_texts.append(FloatingText(self.player.x, self.player.y - 40, "盾牌修复！", color=BLUE, lifetime=2.0))

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

        # 更新轮盘动画
        if self.skill_wheel_active:
            self.skill_wheel.update(dt)
        if self.weapon_wheel_active:
            self.weapon_wheel.update(dt)

        # 更新炮塔、空袭、黑洞、医疗舱
        self._update_turrets(dt)
        self._update_airstrikes(dt)
        self._update_black_holes(dt)
        self._update_medic_pods(dt)

    def _update_playing(self, dt):
        keys = pygame.key.get_pressed()
        move_x, move_y = 0, 0
        mouse_angle = 0.0

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
        else:
            # 触控模式
            self.joystick.handle_touch(self.touch_events, self.scale)
            move_x, move_y = self.joystick.get_direction()

            # 攻击/瞄准摇杆
            self.aim_button.handle_touch(self.touch_events, self.scale)
            mouse_angle = self.aim_button.get_angle()
            self.player.facing_angle = math.degrees(mouse_angle)

            # === 技能轮盘处理 ===
            if self.skill_wheel_active:
                selected_skill = self.skill_wheel.handle_touch(self.touch_events, self.scale)
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
                self.skill_selector.handle_touch(self.touch_events, self.scale)
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
                selected_idx = self.weapon_wheel.handle_touch(self.touch_events, self.scale)
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
                ws_btn.handle_touch(self.touch_events, self.scale)
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
            was_aiming = self.skill_caster.is_aiming
            saved_angle = self.skill_caster.angle
            saved_dist_ratio = self.skill_caster.distance_ratio
            cast_result = self.skill_caster.handle_touch(self.touch_events, self.scale)
            if cast_result:
                if was_aiming:
                    self._use_skill_aimed(self.selected_skill, saved_angle, saved_dist_ratio)
                else:
                    self._use_skill(self.selected_skill)

            # 其他按钮
            for name, btn in self.touch_buttons.items():
                if name == "weapon_switch":
                    continue  # 已在上面处理
                btn.handle_touch(self.touch_events, self.scale)
                if name == "shoot" and btn.just_released:
                    if self.player.riot_gear.equipped:
                        self._perform_bash(self.player.facing_angle)
                elif name == "pause" and btn.just_released:
                    self.state = GameState.PAUSED

        move_len = math.hypot(move_x, move_y)
        if move_len > 1:
            move_x /= move_len
            move_y /= move_len

        # 更新防爆套装动画
        self._update_riot_animation(dt)

        # 更新武器切换冷却
        if self.weapon_switch_cooldown > 0:
            self.weapon_switch_cooldown -= dt

        self.player.update(dt, move_x, move_y, mouse_angle, self.world)
        self.player.x, self.player.y = self.world.clamp_position(
            self.player.x, self.player.y, self.player.size)

        # 更新世界
        self.world.update(dt, self.player.x, self.player.y)

        # 更新尸潮管理器
        self.horde_manager.update(dt)

        # 尸潮音乐切换
        if self.horde_manager.is_horde_active():
            self.assets.play_music("horde")
        elif hasattr(self, '_was_horde') and self._was_horde and not self.horde_manager.is_horde_active():
            # 尸潮结束，记录存活
            if self.session:
                self.session.add_horde_survived()
            self.assets.play_music("gameplay")
        self._was_horde = self.horde_manager.is_horde_active()

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
            if mouse_left:
                if self.player.riot_gear.equipped and self.riot_anim_state == "idle":
                    self._perform_bash(math.degrees(mouse_angle))
                else:
                    auto_shoot = True
        else:
            auto_shoot = self.aim_button.is_shooting

        if auto_shoot and not self.player.riot_gear.equipped and self.riot_anim_state != "equipping":
            weapon = self.player.get_current_weapon()
            if weapon.can_fire():
                proj_list = weapon.fire(
                    self.player.x, self.player.y, mouse_angle,
                    self.player.damage_mult * self.player.damage_boost_mult, self.player.speed_mult,
                    player=self.player
                )
                self.projectiles.extend(proj_list)
                # 记录射击
                if self.session:
                    self.session.add_shot_fired()
                # 播放射击音效
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
            angle = random.uniform(0, math.pi * 2)
            dist = random.randint(400, 700)
            spawn_x = self.player.x + math.cos(angle) * dist
            spawn_y = self.player.y + math.sin(angle) * dist
            spawn_x, spawn_y = self.world.clamp_position(spawn_x, spawn_y, 20)
            enemy = Enemy(spawn_x, spawn_y, spawn_type, 1, self.config.difficulty)
            self.enemies.append(enemy)
            if getattr(enemy, "is_boss", False):
                self._boss_dialogue(spawn_type)

                # 更新敌人
        for enemy in self.enemies[:]:
            result = enemy.update(dt, self.player.x, self.player.y, self.player)

            # 爆炸僵尸自爆
            if result == "explode":
                self.particles.spawn_explosion(enemy.x, enemy.y, RUST, 40)
                self.camera.shake(10, 0.5)
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

                    # 确保玩家被推动后不在障碍物内
                    self.player.ensure_safe_position(self.world)

                    if self.config.screen_shake:
                        self.camera.shake(6, 0.4)

            # 普通远程敌人攻击（普通远程僵尸，Boss的射击已经在result dict处理）
            if getattr(enemy, "attack_range", 0) > 0 and not getattr(enemy, "is_boss", False):
                dist_e_p = math.hypot(enemy.x - self.player.x, enemy.y - self.player.y)
                r_result = enemy._ranged_attack(dt, self.player.x, self.player.y, dist_e_p)
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
                        self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, actual_damage, is_crit=is_crit))
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
                                    self.damage_numbers.append(DamageNumber(e.x, e.y, actual_damage, is_crit=is_crit))
                                    if not e.alive:
                                        self._on_enemy_death(e)
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
                    self.damage_numbers.append(DamageNumber(enemy.x, enemy.y, actual_damage, is_crit=is_crit))
                    self.particles.spawn_blood(enemy.x, enemy.y, 5)

                    if self.player.life_steal > 0:
                        self.player.heal(actual_damage * self.player.life_steal)

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

        self.particles.update(dt)
        for dn in self.damage_numbers[:]:
            dn.update(dt)
            if not dn.is_alive():
                self.damage_numbers.remove(dn)
        for ft in self.floating_texts[:]:
            ft.update(dt)
            if not ft.is_alive():
                self.floating_texts.remove(ft)

        self.camera.follow(self.player.x, self.player.y, dt)

        if self.player.hp <= 0:
            # 保存游戏记录
            if self.session:
                self.session.set_died(True)
                new_unlock_keys = self.session.finalize()
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

    def _update_grapple_collision(self):
        """更新钩爪碰撞检测 - 检测钩爪头是否碰到敌人"""
        if not self.player.riot_gear.grapple_active:
            return
        if self.player.riot_gear.grapple_state != "shooting":
            return

        head_pos = self.player.riot_gear.grapple_head_pos
        if not head_pos:
            return

        # 检测钩爪头与敌人的碰撞
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = math.hypot(enemy.x - head_pos[0], enemy.y - head_pos[1])
            if dist < enemy.size + 10:
                # 勾中敌人！
                self.player.riot_gear.set_grapple_target(enemy)
                self.player.riot_gear.grapple_state = "hit"
                self.player.riot_gear.grapple_hit_stun_timer = self.player.riot_gear.grapple_hit_stun_duration
                enemy.grappled = True
                self.floating_texts.append(FloatingText(
                    enemy.x, enemy.y - 30, "勾中!", color=GREEN, lifetime=1.0
                ))
                return

        # 检测钩爪头与经验球的碰撞
        for orb in self.exp_orbs:
            if not orb.alive:
                continue
            dist = math.hypot(orb.x - head_pos[0], orb.y - head_pos[1])
            if dist < orb.size + 10:
                # 直接拉取经验球
                orb.magnetized = True
                self.player.riot_gear._reset_grapple()
                return

        # 检测钩爪头与道具的碰撞
        for item in self.world.items:
            if not item.alive:
                continue
            dist = math.hypot(item.x - head_pos[0], item.y - head_pos[1])
            if dist < item.size + 10:
                # 直接拉取道具
                self._apply_item_effect(item.item_type)
                item.alive = False
                self.player.riot_gear._reset_grapple()
                return

    def _on_enemy_death(self, enemy):
        # 记录击杀
        if self.session:
            self.session.add_kill(enemy.enemy_type)
        # 播放击杀音效
        if getattr(enemy, "is_boss", False):
            self.assets.play_sound("boss_death")
        else:
            self.assets.play_sound_random(["zombie_death", "zombie_groan"])
        self.particles.spawn_blood(enemy.x, enemy.y, 15)
        self.particles.spawn_explosion(enemy.x, enemy.y, enemy.color, 10)
        self.particles.spawn_death_aura(enemy.x, enemy.y, enemy.color)

        # 分裂者分裂
        if getattr(enemy, "is_splitter", False) and enemy.split_count < 1:
            enemy.split_count += 1
            for _ in range(2):
                offset_x = random.uniform(-20, 20)
                offset_y = random.uniform(-20, 20)
                small_enemy = Enemy(enemy.x + offset_x, enemy.y + offset_y, 
                                   EnemyType.ZOMBIE_FAST, 1, self.config.difficulty)
                small_enemy.size = 8
                small_enemy.max_hp = small_enemy.hp = 15
                small_enemy.damage = 5
                self.enemies.append(small_enemy)
            self.floating_texts.append(FloatingText(
                enemy.x, enemy.y - 30, "分裂!", color=BLOOD_RED, lifetime=1.5
            ))

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

        # 武器掉落
        if random.random() < 0.02:
            weapon_types = [WeaponType.RIFLE, WeaponType.SHOTGUN, WeaponType.SNIPER,
                          WeaponType.MACHINE_GUN, WeaponType.ROCKET_LAUNCHER, WeaponType.FLAMETHROWER,
                          WeaponType.CROSSBOW, WeaponType.GRENADE_LAUNCHER, WeaponType.PLASMA_RIFLE,
                          WeaponType.RAILGUN, WeaponType.MINIGUN, WeaponType.DOUBLE_BARREL]
            new_weapon = random.choice(weapon_types)
            self.player.add_weapon(new_weapon)
            # 记录武器收集
            if self.session:
                self.session.add_weapon_collected()
            # 播放音效
            self.assets.play_sound("weapon_switch")
            self.floating_texts.append(FloatingText(enemy.x, enemy.y, f"获得{Weapon(new_weapon).name}!"))

        # Boss掉落疫苗
        if getattr(enemy, "is_boss", False) and random.random() < 0.15 and not self.has_vaccine:
            self.has_vaccine = True
            self.floating_texts.append(FloatingText(enemy.x, enemy.y, "获得疫苗！", color=GREEN, lifetime=3.0))

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
