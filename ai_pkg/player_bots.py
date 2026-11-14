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
    def _pick_target(self):
        """v2.9.19：目标优先级 敌方玩家 > 倒地队友(救援) > 僵尸 > 经验球。

        旧版没有经验球，无敌人时 _decide_move 用 `cos(_angle*0.7)` 原地
        绕圈（"一直转，也不吃经验"），而且 `_angle` 在无目标时从不更新。
        """
        g = self.game
        _p = self.player
        self._target_kind = "foe"
        _foes = [p for p in self._other_players() if self._is_foe_player(p)]
        _z = self._candidates()
        _hp_ratio = float(getattr(_p, 'hp', 1)) / max(1.0, float(getattr(_p, 'max_hp', 100)))

        # 友方 AI（含非激进策略）看到倒地队友 → 过去救援
        if not getattr(_p, 'bot_hostile', False):
            _down = [p for p in self._other_players()
                     if getattr(p, 'downed', False) and not self._is_foe_player(p)]
            if _down:
                self._target_kind = "rescue"
                return min(_down, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        if self.tactic is BotTactic.AGGRESSIVE and _foes:
            return min(_foes, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        if self.tactic is BotTactic.SURVIVAL and _hp_ratio < 0.35 and _z:
            return min(_z, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        if _z:
            return min(_z, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        if _foes:
            return min(_foes, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        # 没有敌人：去捡最近的经验球 / 世界道具
        _orbs = [o for o in (getattr(g, 'exp_orbs', []) or [])
                 if getattr(o, 'alive', True) and self.perception.visible(o, 900.0)]
        if _orbs:
            self._target_kind = "pickup"
            return min(_orbs, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        _items = [o for o in (getattr(getattr(g, 'world', None), 'items', []) or [])
                  if getattr(o, 'alive', True) and self.perception.visible(o, 700.0)]
        if _items:
            self._target_kind = "pickup"
            return min(_items, key=lambda o: (o.x - _p.x) ** 2 + (o.y - _p.y) ** 2)
        self._target_kind = "idle"
        return None

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
        """v2.9.19：靠近倒地队友即由通用救援系统累计进度；这里只负责
        把 AI 停在救援半径内并保持朝向，避免出现"跑过头"导致进度反复清零。"""
        if getattr(self, '_target_kind', '') != 'rescue':
            return
        _mate = self._target
        if _mate is None:
            return
        _d = math.hypot(_mate.x - self.player.x, _mate.y - self.player.y)
        if _d < 100:
            self._move_x *= 0.25
            self._move_y *= 0.25

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
        # 开火（超难强锁：命中率 100%）；拾取物 / 倒地队友不是射击目标
        if self._target is not None and getattr(self, '_target_kind', 'foe') == 'foe':
            try:
                self.game._bot_fire(_p, self._angle,
                                    locked=bool(self.diff.params[5]))
            except Exception:
                pass
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
        if _has_hostile:
            try:
                g.config.pvp_enabled = True
                g.config.pvp_teams = max(2, int(getattr(g.config, 'pvp_teams', 2) or 2))
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
                # v2.9.19：team_id 才是现有伤害/救援/胜负链路读的字段（旧版只写 .team）
                _pl.team = 1 if prof.hostile else 0
                _pl.team_id = 1 if prof.hostile else 0
                prof.team = _pl.team_id
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
