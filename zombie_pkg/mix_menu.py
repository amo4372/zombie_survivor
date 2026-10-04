# -*- coding: utf-8 -*-
"""MenuMixin - 由 game.py 自动拆分，逻辑等价"""

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

class MenuMixin:
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
