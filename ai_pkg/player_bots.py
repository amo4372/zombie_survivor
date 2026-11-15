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

# v2.9.19：AI 玩家实体。**不复制玩法**，直接继承多人玩家同一个 Player 类，
# 因此伤害 / 状态 / 升级 / 回放 / 图鉴 / 技能树 / 抗性等全部接口天然一致；
# 这里只多挂两个标记字段供上层识别"这是 AI 而非人类视口"。
try:
    from entities_pkg.player import Player as _PlayerBase
except Exception:                                    # pragma: no cover
    from entities import Player as _PlayerBase


class AIPlayer(_PlayerBase):
    """多人模式 AI 玩家实体（与人类玩家共用全部接口）。

    * is_bot         → 视口/HUD/输入分派据此排除，不再为 AI 开视口
    * bot_profile    → 阵营/难度/策略配置，供伤害与胜负判定读取
    * ai_controller  → 反向引用 PlayerBot（可选，方便调试）
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_bot = True
        self.bot_profile = None
        self.ai_controller = None



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
            # v2.9.20：误差改为「每发抖动」而非固定角偏置，且整体下调。
            # 旧版 0.26rad≈15° 的固定偏差让简单 AI 几乎永远打不中。
            "简单":   (0.45, 0.11, 0.2, 0.18, False, False, False),
            "普通":   (0.30, 0.055, 0.6, 0.35, False, False, False),
            "困难":   (0.18, 0.025, 1.0, 0.55, False, False, True),
            "地狱":   (0.10, 0.008, 1.2, 0.75, True,  False, True),
            "超难":   (0.05, 0.0,  1.4, 0.95, True,  True,  True),
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
        self._target_kind = "idle"
        self._target_hold = 0.0        # v2.9.20 目标保持时间（防抖动）
        self._last_tpos = None         # 上一帧目标位置（做速度差分）
        self._tvel = (0.0, 0.0)        # 目标速度，像素/秒
        self._aim_angle = 0.0          # 每帧重算的瞄准角
        self._aim_point = None         # 预测命中点（供强锁使用）
        self._strafe = random.choice((-1, 1))

    # ------------------------------------------------------------ 感知
    def _candidates(self):
        g = self.game
        _out = []
        for e in (getattr(g, 'enemies', []) or []):
            if getattr(e, 'alive', False) and self.perception.visible(e):
                _out.append(e)
        return _out

    def _other_players(self, include_downed=False):
        """v2.9.20：默认只返回活着且可见的玩家；救援时把倒地队友也算进来。

        旧版一律过滤 `alive=True`，而倒地玩家 alive=False —— 于是 AI
        永远"看不到"倒地队友，救援目标从来选不中，这就是「不怎么会救队友」。
        """
        g = self.game
        try:
            _all = list(g.registered_players())
        except Exception:
            _all = []
        out = []
        for p in _all:
            if p is self.player:
                continue
            _down = bool(getattr(p, 'downed', False))
            if not _down and not getattr(p, 'alive', True):
                continue
            if _down and not include_downed:
                continue
            if getattr(p, 'permanently_dead', False):
                continue
            if self.perception.visible(p):
                out.append(p)
        return out

    def _team_of(self, p):
        # v2.9.19：优先 team_id（现有 PvP/救援/伤害链路都读它）
        return int(getattr(p, 'team_id', getattr(p, 'team', 0)) or 0)

    def _is_foe_player(self, p):
        """v2.9.19：敌方 AI 必须能打人类玩家、也必须与友方 AI 区分。

        旧版只有 config.pvp_enabled=True 才算敌对，而加 AI 时没人去开这个
        开关 → 敌方 AI 永远把人类当队友，既不攻击也不结算。现在按队伍判定。
        """
        _me = self.player
        if getattr(p, 'bot_hostile', None) is not None or getattr(_me, 'bot_hostile', None) is not None:
            _ph = bool(getattr(p, 'bot_hostile', False))
            _mh = bool(getattr(_me, 'bot_hostile', False))
            # 人类视为友方阵营；只要两边 hostile 不同就是敌人
            if _ph != _mh:
                return True
        _a, _b = self._team_of(_me), self._team_of(p)
        if _a == _b:
            return False
        return bool(getattr(getattr(self.game, 'config', None), 'pvp_enabled', False)) \
            or bool(getattr(p, 'bot_hostile', False)) or bool(getattr(_me, 'bot_hostile', False))

    # ------------------------------------------------------------ 决策
    # ------------------------------------------------------------ 目标
    def _target_alive(self, t):
        if t is None:
            return False
        if getattr(t, 'downed', False):          # 救援目标：倒地即有效
            return not getattr(t, 'permanently_dead', False)
        return bool(getattr(t, 'alive', True))

    def _target_score(self, t, kind):
        """v2.9.20：评分越小越优先，取代「永远选最近的」造成的来回抖动。"""
        _p = self.player
        d = math.hypot(t.x - _p.x, t.y - _p.y)
        w = {
            'rescue': -900.0,     # 队友倒地绝对优先
            'foe_player': -420.0,  # 敌方玩家优先于僵尸
            'enemy': 0.0,
            'pickup': 260.0,      # 没威胁才去捡东西
        }.get(kind, 0.0)
        # 低血目标 / 近目标加权；敌方玩家额外按血量压制
        if kind == 'foe_player':
            try:
                w -= (1.0 - float(t.hp) / max(1.0, float(t.max_hp))) * 260.0
            except Exception:
                pass
        elif kind == 'enemy':
            try:
                w -= (1.0 - float(t.hp) / max(1.0, float(getattr(t, 'max_hp', 100)))) * 90.0
            except Exception:
                pass
        return d + w

    def _pick_target(self):
        """v2.9.20：明确的目标优先级 + 目标粘性。

        优先级：倒地队友(救援) > 敌方玩家 > 僵尸 > 经验球/道具。
        旧版每次反应都重新选「最近的」，两个目标交替靠近时 AI 会来回
        横跳，看起来就是「没有明确目标」。现在目标一旦锁定至少保持
        0.8s（或直到死亡/跑出感知），且切换需要新目标明显更优。
        """
        g = self.game
        _p = self.player
        _old = self._target
        _old_kind = getattr(self, '_target_kind', 'idle')

        # 候选池
        _all_players = self._other_players(include_downed=True)
        _down = [p for p in _all_players
                 if getattr(p, 'downed', False) and not self._is_foe_player(p)]
        _foes = [p for p in _all_players
                 if not getattr(p, 'downed', False) and self._is_foe_player(p)]
        _z = self._candidates()

        _cands = []
        # 1) 救援：友方 AI 看到倒地队友立即前往（不再被 alive=False 过滤）
        if not getattr(_p, 'bot_hostile', False):
            _cands += [(p, 'rescue') for p in _down]
        # 2) 敌方玩家 / 僵尸
        _cands += [(p, 'foe_player') for p in _foes]
        _cands += [(e, 'enemy') for e in _z]
        # 3) 只有完全没有威胁时才捡经验 / 道具
        if not _cands:
            _orbs = [o for o in (getattr(g, 'exp_orbs', []) or [])
                     if getattr(o, 'alive', True) and self.perception.visible(o, 900.0)]
            _items = [o for o in (getattr(getattr(g, 'world', None), 'items', []) or [])
                      if getattr(o, 'alive', True) and self.perception.visible(o, 700.0)]
            _cands += [(o, 'pickup') for o in (_orbs + _items)]

        # 超难透视由 BotPerception.visible() 在候选收集阶段处理（不限制距离）
        if not _cands:
            self._target_kind = 'idle'
            self._target_hold = 0.0
            self._last_tpos = None
            return None

        # 策略修正：求生低血时不追敌方玩家，激进则更贴脸
        _hp_ratio = float(getattr(_p, 'hp', 1)) / max(1.0, float(getattr(_p, 'max_hp', 100)))
        if self.tactic is BotTactic.SURVIVAL and _hp_ratio < 0.35:
            _cands = [(t, k) for t, k in _cands if k != 'foe_player'] or _cands

        # 目标粘性：旧目标仍有效且保持时间未到 → 不换
        if _old is not None and self._target_hold > 0 and self._target_alive(_old):
            _still = any(t is _old for t, _k in _cands)
            if _still:
                return _old
        _best, _best_kind = min(_cands, key=lambda tk: self._target_score(tk[0], tk[1]))
        self._target_kind = _best_kind
        self._target_hold = 0.85 if _best_kind != 'rescue' else 1.4
        if _best is not _old:
            self._last_tpos = None
            self._tvel = (0.0, 0.0)
        return _best

    def _track_target_velocity(self, t, dt):
        """用位置差分估算目标速度（实体普遍没有 vx/vy 字段）。"""
        if t is None or dt <= 0:
            return
        _now = (float(t.x), float(t.y))
        _prev = getattr(self, '_last_tpos', None)
        if _prev is not None:
            _vx = (_now[0] - _prev[0]) / dt
            _vy = (_now[1] - _prev[1]) / dt
            # 平滑，避免单帧噪声
            _ovx, _ovy = getattr(self, '_tvel', (0.0, 0.0))
            self._tvel = (_ovx * 0.65 + _vx * 0.35,
                          _ovy * 0.65 + _vy * 0.35)
            # 明显不合理的速度（传送/重置）直接丢弃
            if math.hypot(*self._tvel) > 900.0:
                self._tvel = (0.0, 0.0)
        self._last_tpos = _now

    def _aim_accuracy(self):
        """v2.9.20：AI 的瞄准精度决定它能抵消多少武器基础散布。

        **打不准的真根因**：`Weapon.fire` 在 `_fire_spread is None` 时会用
        `max(spread, charge_spread_max*0.45)` 的大散布（AWM 平射可达 0.44rad
        ≈25°）。AI 不会像玩家那样长按蓄力收敛，开火时又把 `_fire_spread`
        置成 None，于是每发都吃满大散布 —— 比远程投掷僵尸还瞎。
        现在按难度把散布收敛掉，超难/强锁完全归零。
        """
        return {
            "简单": 0.30, "普通": 0.55, "困难": 0.80,
            "地狱": 0.92, "超难": 1.0,
        }.get(getattr(self.diff, 'value', ''), 0.55)

    def _aim_now(self):
        """v2.9.20：每帧重算瞄准角，含**弹速飞行时间**提前量。

        旧版只在 reaction 间隔（0.06~0.55s）更新一次角度，目标一动就
        整段打空；而且提前量读 `vx/vy`，绝大多数实体根本没有这两个
        字段，等于没有提前量 —— 所以「还没远程投掷僵尸打得准」。
        """
        _p = self.player
        _t = self._target
        if _t is None:
            self._aim_angle = getattr(self, '_angle', 0.0)
            self._aim_point = None
            return
        _react, _err, _lead, _skill, _xray, _lock, _allmech = self.diff.params
        try:
            _w = _p.get_current_weapon()
            _bspeed = max(2.0, float(getattr(_w, 'speed', 14) or 14))
        except Exception:
            _bspeed = 14.0
        _dx = float(_t.x) - float(_p.x)
        _dy = float(_t.y) - float(_p.y)
        _dist = math.hypot(_dx, _dy)
        # speed 是「像素/帧」，60fps → 飞行秒数
        _flight = min(1.2, _dist / max(1.0, _bspeed) / 60.0)
        _vx, _vy = getattr(self, '_tvel', (0.0, 0.0))
        _tx = float(_t.x) + _vx * _flight * _lead
        _ty = float(_t.y) + _vy * _flight * _lead
        self._aim_point = (_tx, _ty)
        _ang = math.degrees(math.atan2(_ty - _p.y, _tx - _p.x))
        # 误差改成「每发独立抖动」，不是固定偏置
        if _err:
            _ang += random.uniform(-_err, _err) * 57.2958
        self._aim_angle = _ang
        self._angle = _ang

    def _decide_move(self, target, dt):
        _p = self.player
        _hp_ratio = float(getattr(_p, 'hp', 1)) / max(1.0, float(getattr(_p, 'max_hp', 100)))
        if target is None:
            # v2.9.19：无目标走直线巡逻（旧版用不断变化的 _angle 算出旋转轨迹 → 一直转圈）
            self._patrol_t = getattr(self, '_patrol_t', 0.0) + 0.016
            if self._patrol_t > 3.2:
                self._patrol_t = 0.0
                self._patrol_angle = getattr(self, '_patrol_angle', random.uniform(0, 6.28)) \
                    + random.uniform(-1.2, 1.2)
            _pa = getattr(self, '_patrol_angle', 0.0)
            self._move_x = math.cos(_pa) * 0.65
            self._move_y = math.sin(_pa) * 0.65
            self._angle = math.degrees(_pa)
            return
        dx, dy = target.x - _p.x, target.y - _p.y
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        _want = 0.0
        if getattr(self, '_target_kind', 'foe') in ('rescue', 'pickup'):
            _want = 26.0
        elif self.tactic is BotTactic.SNIPER:
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
        # v2.9.20：朝向不再在这里算（旧版每 reaction 才更新一次且读不到
        # vx/vy）。统一由 update() 每帧调用 _aim_now() 处理。

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
        """v2.9.19：AI 会放技能。技能来源 = 自己 skill_tree 里已点出的主动技。

        旧版读 `active_skills`（其实是**冷却字典**），几乎永远为空或不合法，
        所以"AI 放不出技能"。
        """
        _p = self.player
        _rate = self.diff.params[3]
        self._skill_t -= dt
        if self._skill_t > 0 or random.random() > _rate * dt * 2.2:
            return
        self._skill_t = 1.0 + random.random() * 1.4
        try:
            _tree = getattr(_p, 'skill_tree', None)
            # v2.9.19：SkillTree.skills 是 **list[Skill]**，旧版按 dict.items()
            # 遍历，结果永远空 → "AI 放不出技能"。
            _skills = getattr(_tree, 'skills', None) or []
            if isinstance(_skills, dict):
                _iter = [(_k, _v) for _k, _v in _skills.items()]
            else:
                _iter = [(getattr(_sk, 'skill_type', None), _sk) for _sk in _skills]
            _cds = getattr(_p, 'active_skills', {}) or {}
            _usable = []
            for _st, _sk in _iter:
                if _st is None or _st in _cds:
                    continue
                if float(getattr(_sk, 'current_level', 0) or 0) <= 0:
                    continue
                if not getattr(_sk, 'is_active', False):
                    continue
                _usable.append(_st)
            if not _usable:
                return
            _st = random.choice(_usable)
            self.game._bot_use_skill(_p, _st, self._angle)
        except Exception:
            pass

    def _try_rescue(self):
        """v2.9.20：救援时停在 70~100 距离带内，不再冲过队友导致
        `rescue_progress` 反复清零；同时把朝向对准队友，符合直觉。"""
        if getattr(self, '_target_kind', '') != 'rescue':
            return
        _mate = self._target
        if _mate is None:
            return
        _d = math.hypot(_mate.x - self.player.x, _mate.y - self.player.y)
        if _d < 95:
            self._move_x *= 0.08
            self._move_y *= 0.08
        elif _d < 150:
            self._move_x *= 0.4
            self._move_y *= 0.4
        self._angle = math.degrees(math.atan2(_mate.y - self.player.y,
                                              _mate.x - self.player.x))

    def update(self, dt):
        """v2.9.20：决策低频、**瞄准与开火每帧**，这是命中率的关键。"""
        _p = self.player
        if not getattr(_p, 'alive', True) or getattr(_p, 'downed', False):
            return
        _react, _err, _lead, _skill, _xray, _lock, _allmech = self.diff.params
        self._react_t -= dt
        self._target_hold = max(0.0, float(getattr(self, '_target_hold', 0.0)) - dt)
        if self._react_t <= 0:
            self._react_t = _react
            self._target = self._pick_target()
            self._decide_move(self._target, dt)
            if random.random() < 0.25:
                self._strafe *= -1
        # 移动 / 朝向：走 Player 原生 update，与其它玩家完全一致
        self._track_target_velocity(self._target, dt)
        self._aim_now()
        try:
            # v2.9.20 **单位修正**：Player.update 的 mouse_angle 期望**弧度**
            # （内部 `facing_angle = math.degrees(mouse_angle)`），而 AI 全程
            # 用度数。旧版直接传度数 → facing_angle 被二次 degrees() 放大
            # 57 倍，AI 的朝向/绘制完全乱转，这也是"一直转"的根因之一。
            _p.update(dt, self._move_x, self._move_y, math.radians(self._aim_angle),
                      getattr(self.game, 'world', None), sprinting=False)
        except Exception:
            pass
        # 开火：拾取物 / 倒地队友不是射击目标；把预测点交给强锁
        _kind = getattr(self, '_target_kind', 'idle')
        if self._target is not None and _kind in ('foe_player', 'enemy'):
            try:
                _p._bot_aim_point = self._aim_point
                self.game._bot_fire(_p, self._aim_angle, locked=bool(_lock),
                                    accuracy=self._aim_accuracy())
            except Exception:
                pass
            finally:
                _p._bot_aim_point = None
        self._try_rescue()
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
        _PlayerCls = AIPlayer
        _slot = max(1, int(human_count)) + 1
        # v2.9.19：只要存在敌方 AI，就开启 PvP 结算链路并给人类分队，
        # 否则敌方 AI 的攻击/胜负判定会被"合作模式同阵营"整个吞掉。
        _has_hostile = any(p.hostile for p in self.enabled_profiles())
        # v2.9.20：允许把 AI 分配到 2~4 个阵营（不再只有"敌/友"两队）。
        # 阵营数取配置值与实际 AI 里最大 team+1 的较大者。
        _max_team = max([0] + [max(0, int(p.team or 0)) for p in self.enabled_profiles()])
        _nteams = max(2, int(getattr(g.config, 'pvp_teams', 2) or 2), _max_team + 1)
        _nteams = min(6, _nteams)
        if _has_hostile or _max_team > 0:
            try:
                g.config.pvp_enabled = True
                g.config.pvp_teams = _nteams
            except Exception:
                pass
            try:
                if getattr(g, 'player', None) is not None:
                    g.player.team_id = 0
            except Exception:
                pass
        for prof in self.enabled_profiles():
            if _slot > 10:
                break
            try:
                _base = getattr(g, 'player', None)
                _x = (_base.x if _base else 0) + random.randint(-260, 260)
                _y = (_base.y if _base else 0) + random.randint(-260, 260)
                # v2.9.19：夹到地图边界内，否则 AI 出生在界外会被 world
                # 碰撞逻辑钉死，表现就是"一直站着不动 / 一直转"
                try:
                    _bd = getattr(getattr(g, 'world', None), 'bounds', None)
                    if _bd and len(_bd) == 2:
                        _lo, _hi = float(_bd[0]) + 40.0, float(_bd[1]) - 40.0
                        if _hi > _lo:
                            _x = max(_lo, min(_hi, _x))
                            _y = max(_lo, min(_hi, _y))
                except Exception:
                    pass
                _w = prof.weapon or getattr(g, 'selected_weapon', None)
                _pl = _PlayerCls(_x, _y, start_weapon=_w)
                _pl.is_bot = True
                _pl.bot_profile = prof
                _pl.bot_hostile = bool(prof.hostile)
                # v2.9.20：按配置分配到 0..N-1 阵营；hostile 只表示"与人类敌对"。
                # team_id 才是现有伤害/救援/胜负链路读的字段。
                # v2.9.20：只勾「敌方」而没手动选阵营时，自动进敌方阵营 1，
                # 避免敌对 AI 与人类同 team_id 让伤害/胜负链路判成队友。
                # 显式设了 team>=2 的多阵营配置则原样保留。
                if prof.hostile and int(getattr(prof, 'team', 0) or 0) == 0:
                    prof.team = 1
                _tid = max(0, min(_nteams - 1, int(getattr(prof, 'team', 0) or 0)))
                _pl.team = _tid
                _pl.team_id = _tid
                prof.team = _tid
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
                _bot = PlayerBot(g, _pl, prof)
                _pl.ai_controller = _bot
                self.bots.append(_bot)
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
