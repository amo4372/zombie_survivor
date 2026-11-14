#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.9.17 多人模式玩家 AI（PlayerBot）

设计目标
--------
* 与现有玩法完全兼容：AI 就是一个普通的 `Player` 对象，注册进
  `game.player2..player10`，走同一套伤害/状态/升级/回放/伤害日志管线。
* 人类玩家数决定渲染：1 人 → 单机全屏；2 人 → 同屏分屏；网络联机
  每台设备仍显示自己的单机视角，AI 只是世界里的实体。
* 最多 9 个 AI（总玩家数 ≤ 10），可逐个设置阵营（友方 / 敌方）、
  难度、武器、角色、策略偏好。
* 难度含「超难」：透视（全图精确状态）、精确提前量、强锁必中、
  运用格挡/闪避/钩爪/技能/道具等全部机制。

类结构
------
BotDifficulty  难度枚举
BotTactic      策略偏好
BotProfile     单个 AI 的可编辑配置（dataclass）
BotPerception  感知层（按难度决定是否透视/带噪声）
PlayerBot      控制器：绑定 Player + Game，每帧决策与执行
BotManager     管理器：创建/销毁/更新/自动升级
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum


class BotDifficulty(Enum):
    EASY = "简单"
    NORMAL = "普通"
    HARD = "困难"
    HELL = "地狱"
    NIGHTMARE = "超难"       # 透视 + 精确计算 + 强锁 + 全机制

    @classmethod
    def cycle(cls, cur):
        _l = list(cls)
        try:
            return _l[(_l.index(cur) + 1) % len(_l)]
        except (ValueError, TypeError):
            return _l[0]

    @property
    def params(self):
        # (反应间隔, 瞄准误差弧度, 提前量系数, 技能频率, 透视, 强锁, 全机制)
        return {
            "简单":   (0.55, 0.26, 0.0, 0.18, False, False, False),
            "普通":   (0.35, 0.14, 0.4, 0.35, False, False, False),
            "困难":   (0.22, 0.07, 0.8, 0.55, False, False, True),
            "地狱":   (0.13, 0.03, 1.0, 0.75, True,  False, True),
            "超难":   (0.06, 0.0,  1.2, 0.95, True,  True,  True),
        }[self.value]


class BotTactic(Enum):
    AGGRESSIVE = "激进"      # 针对玩家：优先冲脸、PvP 优先
    SURVIVAL = "求生"        # 自身状态：低血回撤、保命优先
    SUPPORT = "支援"         # 团队：救队友、治疗、拉怪
    SNIPER = "狙击"          # 环境：保持距离、找射界
    AMBUSHER = "游击"        # 侧翼绕行、偷袭

    @classmethod
    def cycle(cls, cur):
        _l = list(cls)
        try:
            return _l[(_l.index(cur) + 1) % len(_l)]
        except (ValueError, TypeError):
            return _l[0]


@dataclass
class BotProfile:
    slot: int                                  # 2..10
    enabled: bool = False
    hostile: bool = False                      # True=敌方AI / False=友方AI
    difficulty: BotDifficulty = BotDifficulty.NORMAL
    tactic: BotTactic = BotTactic.AGGRESSIVE
    weapon: object = None                      # WeaponType 或 None（跟随人类）
    character: str = ""                        # 角色 key 或 ""
    team: int = 0

    def label(self):
        return ("%s·%s·%s" % ("敌方" if self.hostile else "友方",
                              self.difficulty.value, self.tactic.value))


class BotPerception:
    """按难度给 AI 的观察结果加限制：低难度有噪声/视野限制，超难全图透视。"""

    def __init__(self, bot):
        self.bot = bot

    def visible(self, ent, max_dist=1400.0):
        p = self.bot.player
        d = math.hypot(getattr(ent, 'x', 0) - p.x, getattr(ent, 'y', 0) - p.y)
        _react, _err, _lead, _skill, _xray, _lock, _allmech = self.bot.diff.params
        if not _xray and d > max_dist:
            return False
        return True


class PlayerBot:
    """一个 AI 玩家控制器。只负责『决策 + 调用现有游戏接口』，不复制玩法逻辑。"""

    def __init__(self, game, player, profile):
        self.game = game
        self.player = player
        self.profile = profile
        self.diff = profile.difficulty
        self.tactic = profile.tactic
        self.perception = BotPerception(self)
        self._react_t = 0.0
        self._skill_t = 0.0
        self._move_x = 0.0
        self._move_y = 0.0
        self._angle = 0.0
        self._target = None
        self._strafe = random.choice((-1, 1))

    # ------------------------------------------------------------ 感知
    def _candidates(self):
        g = self.game
        _out = []
        for e in (getattr(g, 'enemies', []) or []):
            if getattr(e, 'alive', False) and self.perception.visible(e):
                _out.append(e)
        return _out

    def _other_players(self):
        g = self.game
        return [p for p in (g.registered_players() if hasattr(g, 'registered_players') else [])
                if p is not self.player and getattr(p, 'alive', True)
                and self.perception.visible(p)]

    def _team_of(self, p):
        return int(getattr(p, 'team', 0) or 0)

    def _is_foe_player(self, p):
        g = self.game
        _pvp = bool(getattr(getattr(g, 'config', None), 'pvp_enabled', False))
        return _pvp and self._team_of(p) != self._team_of(self.player)

    # ------------------------------------------------------------ 决策
    def _pick_target(self):
        g = self.game
        _p = self.player
        _foes = [p for p in self._other_players() if self._is_foe_player(p)]
        _z = self._candidates()
        _hp_ratio = float(getattr(_p, 'hp', 1)) / max(1.0, float(getattr(_p, 'max_hp', 100)))
        if self.tactic is BotTactic.AGGRESSIVE and _foes:
            return min(_foes, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        if self.tactic is BotTactic.SUPPORT:
            # 优先救援倒地队友
            for p in self._other_players():
                if getattr(p, 'downed', False) and not self._is_foe_player(p):
                    return p
        if self.tactic is BotTactic.SURVIVAL and _hp_ratio < 0.35 and _z:
            # 低血：把最近僵尸当"要远离的对象"，由 _decide_move 处理
            return min(_z, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        if _z:
            return min(_z, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        return _foes[0] if _foes else None

    def _decide_move(self, target, dt):
        _p = self.player
        _hp_ratio = float(getattr(_p, 'hp', 1)) / max(1.0, float(getattr(_p, 'max_hp', 100)))
        if target is None:
            # 无目标：缓慢游走拾取
            self._move_x = math.cos(self._angle * 0.7 + self._strafe) * 0.35
            self._move_y = math.sin(self._angle * 0.7 + self._strafe) * 0.35
            return
        dx, dy = target.x - _p.x, target.y - _p.y
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        _want = 0.0
        if self.tactic is BotTactic.SNIPER:
            _want = 420.0
        elif self.tactic is BotTactic.AMBUSHER:
            _want = 190.0
        elif self.tactic is BotTactic.SUPPORT:
            _want = 150.0
        elif self.tactic is BotTactic.SURVIVAL:
            _want = 300.0 if _hp_ratio < 0.5 else 210.0
        else:
            _want = 120.0
        if self.tactic is BotTactic.SURVIVAL and _hp_ratio < 0.35:
            _k = -1.0                      # 回撤
        elif d > _want + 60:
            _k = 1.0
        elif d < _want - 60:
            _k = -0.7
        else:
            _k = 0.15 * self._strafe       # 保持距离 + 侧移
        _sx, _sy = -uy * 0.45 * self._strafe, ux * 0.45 * self._strafe
        self._move_x = max(-1.0, min(1.0, ux * _k + _sx))
        self._move_y = max(-1.0, min(1.0, uy * _k + _sy))
        # 朝向（含提前量）
        _react, _err, _lead, _skill, _xray, _lock, _allmech = self.diff.params
        _tx = float(getattr(target, 'x', 0)) + float(getattr(target, 'vx', 0) or 0) * _lead * 0.25
        _ty = float(getattr(target, 'y', 0)) + float(getattr(target, 'vy', 0) or 0) * _lead * 0.25
        self._angle = math.degrees(math.atan2(_ty - _p.y, _tx - _p.x)) + \
            (random.uniform(-_err, _err) if _err else 0.0)

    # ------------------------------------------------------------ 执行
    def _try_block(self):
        _all = self.diff.params[6]
        if not _all:
            return
        blk = getattr(self.player, 'block', None)
        if blk is None or blk.active or blk.on_cooldown:
            return
        # 超难：近处有前摇中的敌人就举起格挡
        for e in (getattr(self.game, 'enemies', []) or []):
            if getattr(e, 'special_windup_timer', 0) > 0 and \
                    math.hypot(e.x - self.player.x, e.y - self.player.y) < 140:
                try:
                    blk.press(math.degrees(math.atan2(e.y - self.player.y, e.x - self.player.x)))
                    blk.release()
                    return
                except Exception:
                    return

    def _try_skill(self, dt):
        _p = self.player
        _rate = self.diff.params[3]
        self._skill_t -= dt
        if self._skill_t > 0 or random.random() > _rate * dt * 2.2:
            return
        self._skill_t = 1.2 + random.random() * 1.6
        try:
            _skills = list(getattr(_p, 'active_skills', {}) or {})
            # 只挑已冷却好、且属于主动类的技能
            for st in _skills:
                if float(getattr(_p, 'active_skills', {}).get(st, 0) or 0) > 0:
                    continue
                _ok = self.game._bot_use_skill(_p, st)
                if _ok:
                    break
        except Exception:
            pass

    def update(self, dt):
        _p = self.player
        if not getattr(_p, 'alive', True) or getattr(_p, 'downed', False):
            return
        _react = self.diff.params[0]
        self._react_t -= dt
        if self._react_t <= 0:
            self._react_t = _react
            self._target = self._pick_target()
            self._decide_move(self._target, dt)
            if random.random() < 0.25:
                self._strafe *= -1
        # 移动 / 朝向：走 Player 原生 update，与其它玩家完全一致
        try:
            _p.update(dt, self._move_x, self._move_y, self._angle,
                      getattr(self.game, 'world', None), sprinting=False)
        except Exception:
            pass
        # 开火（超难强锁：命中率 100%）
        if self._target is not None:
            try:
                self.game._bot_fire(_p, self._angle,
                                    locked=bool(self.diff.params[5]))
            except Exception:
                pass
        self._try_block()
        self._try_skill(dt)


class BotManager:
    """创建 / 更新 / 自动升级全部 AI 玩家。"""

    MAX_BOTS = 9

    def __init__(self, game):
        self.game = game
        self.bots = []
        self.profiles = [BotProfile(slot=i) for i in range(2, 2 + self.MAX_BOTS)]

    def enabled_profiles(self):
        return [p for p in self.profiles if p.enabled]

    def setup(self, human_count=1):
        """在 start_game 末尾调用：把启用的 AI 创建成 Player 并注册到槽位。"""
        g = self.game
        self.bots = []
        try:
            from entities_pkg.player import Player
        except Exception:
            try:
                from entities import Player
            except Exception:
                return
        _slot = max(1, int(human_count)) + 1
        for prof in self.enabled_profiles():
            if _slot > 10:
                break
            try:
                _base = getattr(g, 'player', None)
                _x = (_base.x if _base else 0) + random.randint(-260, 260)
                _y = (_base.y if _base else 0) + random.randint(-260, 260)
                _w = prof.weapon or getattr(g, 'selected_weapon', None)
                _pl = Player(_x, _y, start_weapon=_w)
                _pl.is_bot = True
                _pl.bot_profile = prof
                _pl.team = int(prof.team)
                _pl.bot_hostile = bool(prof.hostile)
                try:
                    if prof.character:
                        from gamedata.models import CharacterData
                        _cd = CharacterData.by_key(prof.character)
                        if _cd is not None:
                            _cd.apply_to(_pl)
                except Exception:
                    pass
                _attr = g.PLAYER_ATTRS[_slot - 1]
                setattr(g, _attr, _pl)
                self.bots.append(PlayerBot(g, _pl, prof))
            except Exception:
                continue
            _slot += 1
        # 人类玩家数：决定单机全屏 / 同屏分屏
        g.human_player_count = max(1, int(human_count))

    def update(self, dt):
        for b in self.bots:
            try:
                b.update(dt)
            except Exception:
                pass
        self.auto_upgrade()

    def auto_upgrade(self):
        """AI 不弹选卡界面：检测到自己的升级会话就自动选一张。"""
        g = self.game
        try:
            _tags = list(g.active_upgrade_tags()) if hasattr(g, 'active_upgrade_tags') else []
            for _t in _tags:
                _p = g.player_for_tag(_t) if hasattr(g, 'player_for_tag') else None
                if _p is None or not getattr(_p, 'is_bot', False):
                    continue
                _sel = g.selector_for(_t)
                # AI 不看选卡界面：只要处于升级态就立刻处理，
                # 不依赖 selector.visible（P3+ 复用 P1 选择器，可能不可见）
                if _sel is not None:
                    _cards = (getattr(_sel, 'cards', None)
                              or getattr(_sel, 'current_cards', None)
                              or getattr(_sel, 'options', None) or [])
                    try:
                        if _cards:
                            g._apply_skill_card(_cards[0], player=_p, tag=_t)
                        else:
                            raise ValueError("no cards")
                    except Exception:
                        # 兜底：绝不把 AI 卡在选卡态（会阻塞整局）
                        try:
                            _p.upgrade_paused = False
                            _p.pending_level_up = False
                            _p.skill_cards = []
                            _sel.visible = False
                        except Exception:
                            pass
        except Exception:
            pass

    def clear(self):
        g = self.game
        for b in self.bots:
            try:
                _attr = g.PLAYER_ATTRS[b.profile.slot - 1]
                if getattr(g, _attr, None) is b.player:
                    setattr(g, _attr, None)
            except Exception:
                pass
        self.bots = []
