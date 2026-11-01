# -*- coding: utf-8 -*-
"""ShopMixin - 由 game.py 自动拆分，逻辑等价"""

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

class ShopMixin:
    # ==================================================================
    # v2.8.9 军械库补给（武器抽取）—— 武器唯一获取途径
    # ==================================================================
    def gacha_init(self):
        """初始化抽取系统（v2.8.9 米哈游式：保底 + UP + 重复叠等级）"""
        try:
            from gacha import GachaBanner, SlotMachine
            from weapon_pool import build_pool
            _pool = build_pool()
            # 以 records.is_weapon_owned 为准遍历全部武器类型
            # （此前直接读 data["weapons"] 取不到真实结构，导致已解锁的
            #   武器仍留在奖池里，能重复抽到同一把）
            from config import WeaponType
            _unlocked = set()
            for _wt in WeaponType:
                try:
                    if self.records.is_weapon_owned(getattr(_wt, "name", str(_wt))):
                        _unlocked.add(getattr(_wt, "name", str(_wt)))
                except Exception:
                    pass
            _save = None
            try:
                _save = self.records.data.get("gacha_state")
            except Exception:
                pass
            # v2.9.0 UP 池轮换（优先读数据库 gacha_banners，否则自动轮换）
            _up = []
            try:
                from gacha import (banner_index, load_up_keys_from_db,
                                   build_up_keys)
                _idx = banner_index()
                try:
                    from gamedata import db as _gdb
                    _db = _gdb.GameDatabase() if hasattr(_gdb, "GameDatabase") else None
                    _up = load_up_keys_from_db(_db, _pool, _idx) if _db else []
                except Exception:
                    _up = []
                if not _up:
                    _up = build_up_keys(_pool, _idx)
                self.gacha_banner_index = _idx
            except Exception:
                _up = []
            self.gacha = GachaBanner(_pool, up_keys=_up, unlocked=_unlocked)
            if _save:
                self.gacha.from_save(_save)
            self.slot_machine = SlotMachine()
            # v2.9.0：出货演出（GachaFx）实例化
            try:
                from gacha import GachaFx
                self.gacha_fx = GachaFx()
            except Exception:
                self.gacha_fx = None
            self.gacha_result = []
            self.gacha_tip = ""
            self.slot_bet = 50
            self.slot_result = None
        except Exception:
            self.gacha = None
            self.slot_machine = None
            self.gacha_fx = None
            self.gacha_result = []
            self.gacha_tip = "补给系统初始化失败"

    def _gacha_save(self):
        """把保底计数写回存档（保底必须跨会话保留）"""
        try:
            if getattr(self, "gacha", None) is None:
                return
            self.records.data["gacha_state"] = self.gacha.to_save()
            if hasattr(self.records, "save"):
                self.records.save()
        except Exception:
            pass

    # ==================================================================
    # v2.9.0 多人分阶段开局流程
    # 同屏双人：地图 → P1武器 → P1角色 → P2武器 → P2角色 → 开始
    # 单人：地图 → 武器 → 角色 → 开始
    # ==================================================================
    SETUP_STEPS_SINGLE = ["map", "weapon_p1", "char_p1"]
    SETUP_STEPS_DUO = ["map", "weapon_p1", "char_p1", "weapon_p2", "char_p2"]

    def begin_setup_flow(self):
        """v2.9.2：从"开始游戏"进入分阶段流程（全模式通用）

        此前 setup_flow_init 写好了却没人调用 —— 玩家点开始游戏仍是
        直接跳到 EQUIP_SELECT 单页，新流程从未生效。
        """
        try:
            self.setup_flow_init()
            from config import GameState as _GS
            _st = self.setup_state_for(self.setup_current_step)
            if _st is not None:
                self.state = _st
                return True
        except Exception:
            pass
        return False

    def setup_flow_init(self):
        """开始一局前的准备流程初始化"""
        try:
            _duo = (getattr(self, "multiplayer_mode", None) == "same_screen")
        except Exception:
            _duo = False
        self.setup_steps = list(self.SETUP_STEPS_DUO if _duo
                                else self.SETUP_STEPS_SINGLE)
        self.setup_index = 0
        self.setup_done = False

    @property
    def setup_current_step(self):
        _i = int(getattr(self, "setup_index", 0) or 0)
        _s = getattr(self, "setup_steps", None) or self.SETUP_STEPS_SINGLE
        return _s[_i] if _i < len(_s) else None

    def setup_next(self):
        """确认当前步骤并进入下一步；返回下一步名或 None（流程结束）"""
        _s = getattr(self, "setup_steps", None) or self.SETUP_STEPS_SINGLE
        self.setup_index = int(getattr(self, "setup_index", 0) or 0) + 1
        if self.setup_index >= len(_s):
            self.setup_done = True
            return None
        return _s[self.setup_index]

    def setup_back(self):
        """返回上一步"""
        self.setup_index = max(0, int(getattr(self, "setup_index", 0) or 0) - 1)
        self.setup_done = False
        return self.setup_current_step

    def setup_state_for(self, step):
        """步骤 → GameState"""
        from config import GameState as _GS
        return {
            "map": _GS.MAP_SELECT,
            "weapon_p1": _GS.WEAPON_SELECT_P1,
            "char_p1": _GS.CHARACTER_SELECT_P1,
            "weapon_p2": _GS.WEAPON_SELECT_P2,
            "char_p2": _GS.CHARACTER_SELECT_P2,
        }.get(step)

    def update_gacha_fx(self, dt):
        """v2.9.0：每帧推进抽卡演出（由主循环调用）"""
        try:
            _fx = getattr(self, "gacha_fx", None)
            if _fx is not None and getattr(_fx, "active", False):
                _fx.update(dt)
                return True
        except Exception:
            pass
        return False

    def skip_gacha_fx(self):
        """跳过演出"""
        try:
            _fx = getattr(self, "gacha_fx", None)
            if _fx is not None:
                _fx.skip()
                return True
        except Exception:
            pass
        return False

    def do_gacha(self, n=1):
        """执行抽取（n=1 单抽 / n=10 十连），解锁武器并扣金币"""
        _ga = getattr(self, "gacha", None)
        if _ga is None:
            self.gacha_init()
            _ga = getattr(self, "gacha", None)
        if _ga is None:
            self.gacha_tip = "补给系统不可用"
            return []
        if _ga.pool_empty():
            self.gacha_tip = "全部武器已收集，奖池为空"
            self.gacha_result = []
            return []
        _n = 10 if int(n) >= 10 else 1
        _cost = _ga.price(_n)
        if self.records.get_coins() < _cost:
            self.gacha_tip = f"金币不足（需要 {_cost}）"
            return []
        self.records.spend_coins(_cost)
        # 注意：不能写成 `[_ga.draw_one()] if _ga.draw_one() else []`
        # —— 那会把 draw_one 调用两次（消耗两抽、返回第二抽结果）。
        if _n > 1:
            _res = _ga.draw_many(_n)
        else:
            _one = _ga.draw_one()
            _res = [_one] if _one else []
        _res = [_r for _r in _res if _r]
        # 真正解锁到存档（v2.8.9：重复抽取改为叠加等级）
        for _r in _res:
            try:
                _w = _r.get("weapon") or _r
                _k = str(_w.get("key") or _r.get("key"))
                _lv = int(_r.get("level", 1) or 1)
                self.records.unlock_weapon_purchase(_k)
                if _lv > 1 and hasattr(self.records, "upgrade_weapon_purchase"):
                    self.records.upgrade_weapon_purchase(_k, _lv)
            except Exception:
                pass
        self.gacha_result = _res
        # v2.9.0：触发出货演出
        try:
            if getattr(self, "gacha_fx", None) is not None:
                self.gacha_fx.play(_res)
        except Exception:
            pass
        # 提示：出紫/金时高亮
        _best = max((int(_r.get("star", 1)) for _r in _res), default=0)
        if _best >= 5:
            self.gacha_tip = "传说武器到手！"
        elif _best >= 4:
            self.gacha_tip = "史诗武器到手！"
        else:
            self.gacha_tip = f"已获得 {len(_res)} 把武器"
        self._gacha_save()
        return _res

    def do_slot(self, bet=None):
        """玩老虎机（v2.9.6：转子先转动，逐个停下后才结算）

        原实现是"点一下立刻出结果"，转子从不转动，完全没有赌博的紧张感。
        现在：扣注 → 算好结果（先不派彩）→ 启动转子动画 →
        动画跑完由 finish_slot_spin() 派彩并展示。
        """
        _sm = getattr(self, "slot_machine", None)
        if _sm is None:
            self.gacha_init()
            _sm = getattr(self, "slot_machine", None)
        if _sm is None:
            return None
        # 正在转动时忽略重复点击
        _anim = getattr(self, "slot_anim", None)
        if _anim is not None and getattr(_anim, "active", False):
            return None
        _bet = int(bet if bet is not None else getattr(self, "slot_bet", 50))
        _bet = _sm.clamp_bet(_bet)
        if self.records.get_coins() < _bet:
            self.gacha_tip = "金币不足"
            return None
        self.records.spend_coins(_bet)
        _r = _sm.spin(_bet)
        # 结果先压住，等转子停下再揭晓
        self.slot_pending = _r
        self.slot_result = None
        self.slot_paid = False
        try:
            from gacha import SlotSpinAnim
            if not isinstance(_anim, SlotSpinAnim):
                _anim = SlotSpinAnim()
                self.slot_anim = _anim
            _anim.payout = int(_r.get("payout", 0) or 0)
            _anim.kind = str(_r.get("kind", "none") or "none")
            _anim.start(_r.get("reels") or [])
        except Exception:
            # 动画不可用时退回即时结算
            self.finish_slot_spin()
        return _r

    def slot_add_reel(self):
        """v2.9.7：消耗金币追加一个倍率转子（最多 +3，即总共 6 轴）

        原实现有 unlock_cost / can_unlock 接口但**没有任何 UI 入口**，
        玩家根本没法加轴 —— 6 轴玩法形同虚设。
        """
        _sm = getattr(self, "slot_machine", None)
        if _sm is None:
            self.gacha_init()
            _sm = getattr(self, "slot_machine", None)
        if _sm is None:
            return False
        _cur = int(getattr(_sm, "reels", 3) or 3)
        _mx = int(getattr(_sm, "MAX_REELS", 6) or 6)
        if _cur >= _mx:
            self.gacha_tip = f"已达上限 {_mx} 轴"
            return False
        _cost = int(_sm.unlock_cost())
        if _cost <= 0:
            self.gacha_tip = "无法继续添加"
            return False
        if self.records.get_coins() < _cost:
            self.gacha_tip = f"金币不足（需要 {_cost}）"
            return False
        self.records.spend_coins(_cost)
        try:
            _ok, _spent = _sm.unlock_reel(self.records.get_coins())
            if not _ok:
                _sm.reels = _cur + 1
        except Exception:
            _sm.reels = _cur + 1
        self.gacha_tip = f"已添加第 {_cur + 1} 个转子！倍率上限提升"
        try:
            self._gacha_save()
        except Exception:
            pass
        return True

    def finish_slot_spin(self):
        """转子全部停下：揭晓结果并派彩"""
        _r = getattr(self, "slot_pending", None)
        if _r is None or getattr(self, "slot_paid", False):
            return
        self.slot_paid = True
        self.slot_result = _r
        _pay = int(_r.get("payout", 0) or 0)
        if _pay > 0:
            self.records.add_coins(_pay)
            # 中奖闪光
            try:
                self.slot_win_flash = 1.0
            except Exception:
                pass
            self.gacha_tip = (f"头奖！+{_pay}" if _r.get("kind") == "jackpot"
                              else f"中奖 +{_pay}")
        else:
            self.gacha_tip = "未中奖 —— 再试一次？"
        if _r.get("kind") == "jackpot":
            self._unlock_achievement_safe("slot_jackpot")
        try:
            self._gacha_save()
        except Exception:
            pass

    def _gacha_click(self, pos):
        """军械库补给页点击处理"""
        try:
            _btns = getattr(self, "gacha_buttons", {}) or {}
            for _k, _r in _btns.items():
                if hasattr(_r, "collidepoint") and _r.collidepoint(pos):
                    from config import GameState
                    if _k == "one":
                        self.do_gacha(1)
                    elif _k == "ten":
                        self.do_gacha(10)
                    elif _k == "slot":
                        self.state = GameState.SLOT_MACHINE
                    elif _k == "back":
                        self._gacha_save()
                        self.state = GameState.EQUIP_SELECT
                    return True
        except Exception:
            pass
        return False

    def _slot_click(self, pos):
        """老虎机页点击处理"""
        try:
            from config import GameState
            from gacha import SLOT_BET_MIN, SLOT_BET_MAX
            _btns = getattr(self, "slot_buttons", {}) or {}
            _bet = int(getattr(self, "slot_bet", SLOT_BET_MIN) or SLOT_BET_MIN)
            for _k, _r in _btns.items():
                if hasattr(_r, "collidepoint") and _r.collidepoint(pos):
                    if _k == "minus":
                        self.slot_bet = max(SLOT_BET_MIN, _bet - 50)
                    elif _k == "plus":
                        self.slot_bet = min(SLOT_BET_MAX, _bet + 50)
                    elif _k == "spin":
                        self.do_slot(_bet)
                    elif _k == "back":
                        self.state = GameState.GACHA
                    return True
        except Exception:
            pass
        return False

    #: v2.9.7：手雷 / 燃烧瓶 / 烟雾弹 归类为**投掷道具**而非武器，
    #: 从武器列表、武器图鉴、补给奖池中一并移除。
    EXCLUDED_WEAPON_NAMES = {"GRENADE", "MOLOTOV", "SMOKE_GRENADE"}

    def _get_shop_weapons(self):
        """局外可选武器列表（v2.9.7：移除三件投掷道具）"""
        try:
            return [wt for wt in WeaponType
                    if getattr(wt, "name", "") not in self.EXCLUDED_WEAPON_NAMES]
        except Exception:
            return list(WeaponType)

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
        """v2.8.9：武器**不再能直接购买**，只能通过「军械库补给」抽取获得。

        保留此入口仅为兼容旧调用点，一律返回 gacha_only。
        """
        if self.records.is_weapon_owned(wt.name):
            return "owned"
        return "gacha_only"

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
        """v2.9.2：武器不再能直接升级，只能靠重复抽取叠加等级（上限 5 级）。

        保留入口兼容旧调用点，一律返回 gacha_only（不扣金币、不升等级）。
        """
        return "gacha_only"

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
