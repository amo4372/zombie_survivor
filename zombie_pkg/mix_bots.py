#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.9.17 玩家 AI 的游戏侧接入（BotMixin）

只提供 AI 需要的三个薄接口 + 生命周期，玩法逻辑全部复用现有实现：
  _bot_fire        → Weapon.fire + self.projectiles
  _bot_use_skill   → _use_skill / _use_skill_p2_aimed
  setup_bots       → BotManager.setup（start_game 末尾）
  update_bots      → BotManager.update（_update_playing 每帧）
"""
import math


class BotMixin:
    def _bots(self):
        m = getattr(self, 'bot_manager', None)
        if m is None:
            try:
                from ai_pkg.player_bots import BotManager
                m = BotManager(self)
                self.bot_manager = m
            except Exception:
                return None
        return m

    def setup_bots(self, human_count=None):
        _m = self._bots()
        if _m is None:
            return
        _hc = human_count if human_count is not None else \
            (2 if getattr(self, 'multiplayer_mode', None) == 'same_screen' else 1)
        self.human_player_count = max(1, int(_hc))
        # v2.9.20：先清掉上一局挂在各槽位的 AI 实体，再创建本局 AI
        _m.clear()
        _m.setup(self.human_player_count)

    def update_bots(self, dt):
        _m = getattr(self, 'bot_manager', None)
        if _m is not None:
            _m.update(dt)

    # ------------------------------------------------------------ 开火
    def _bot_fire(self, player, angle_deg, locked=False, accuracy=None):
        """AI 开火：完全复用 Weapon.fire，不改伤害管线。"""
        try:
            _w = player.get_current_weapon()
            if _w is None or not _w.can_fire():
                return False
            _ang = float(angle_deg)
            if locked:
                # v2.9.19：超难强锁只锁**敌对**目标。
                # 旧版把全部玩家（含同阵营友方 AI）都当候选，敌方 AI 会
                # 强锁到离自己最近的友方 AI 身上，人类玩家反而永远打不到。
                _tg = None
                _bd = 1e9
                _my_team = int(getattr(player, 'team_id', 0) or 0)
                for _o in list(getattr(self, 'enemies', []) or []):
                    if not getattr(_o, 'alive', True):
                        continue
                    _d = (_o.x - player.x) ** 2 + (_o.y - player.y) ** 2
                    if _d < _bd:
                        _bd, _tg = _d, _o
                for _o in self.registered_players():
                    if _o is player or not getattr(_o, 'alive', True) or getattr(_o, 'downed', False):
                        continue
                    _ot = int(getattr(_o, 'team_id', 0) or 0)
                    _hostile = bool(getattr(player, 'bot_hostile', False)) != \
                        bool(getattr(_o, 'bot_hostile', False))
                    if _ot == _my_team and not _hostile:
                        continue
                    _d = (_o.x - player.x) ** 2 + (_o.y - player.y) ** 2
                    if _d < _bd:
                        _bd, _tg = _d, _o
                # v2.9.20：AI 每帧算好的**预测命中点**优先（含弹速提前量）。
                # 旧版强锁重新选"最近目标"并直接朝当前位置开火，反而把
                # 提前量丢掉，超难 AI 打移动目标照样空枪。
                _pt = getattr(player, '_bot_aim_point', None)
                if _pt is not None:
                    _ang = math.degrees(math.atan2(_pt[1] - player.y,
                                                   _pt[0] - player.x))
                elif _tg is not None:
                    _ang = math.degrees(math.atan2(_tg.y - player.y, _tg.x - player.x))
            # v2.9.20：AI 不吃满武器大散布（详情见 PlayerBot._aim_accuracy）
            _base_spread = float(getattr(_w, 'spread', 0.0) or 0.0)
            _charge_max = float(getattr(_w, 'charge_spread_max', 0.0) or 0.0) * 0.45
            _eff = max(_base_spread, _charge_max)
            if locked:
                _ai_spread = 0.0
            else:
                _acc = max(0.0, min(1.0, float(accuracy if accuracy is not None else 0.55)))
                _ai_spread = max(0.0, _eff * (1.0 - _acc))
            try:
                player._fire_spread = _ai_spread
                # v2.9.20 **打不准的真正根因**：Weapon.fire 的 angle 是**弧度**
                # （项目所有正常开火点都写 math.radians(facing_angle)），而
                # `_bot_fire(player, angle_deg, ...)` 一直把**度数**直接传进去。
                # -90° 被当成 -90 弧度 → cos/sin 得到约 -115° 的方向，AI 每发
                # 都朝完全错误的地方飞，偶尔命中纯属随机散布碰巧。
                _projs = _w.fire(player.x, player.y, math.radians(_ang),
                                 float(getattr(player, 'damage_multiplier', 1.0) or 1.0),
                                 float(getattr(player, 'speed_mult', 1.0) or 1.0),
                                 player=player)
            finally:
                player._fire_spread = None
            for _p in _projs or []:
                try:
                    _p.owner = player
                except Exception:
                    pass
            # v2.9.19：列表为空时 `or []` 会创建**临时列表**，extend 完直接
            # 丢弃 —— AI 的第一枪（以及清空后每枪）永远消失。必须拿到真列表。
            _lst = getattr(self, 'projectiles', None)
            if _lst is None:
                _lst = []
                self.projectiles = _lst
            _lst.extend(_projs or [])
            return bool(_projs)
        except Exception:
            return False

    # ------------------------------------------------------------ 技能
    def _bot_use_skill(self, player, skill_type, angle_deg=0.0):
        """v2.9.19：任意槽位 AI 都能放技能。

        旧版只有 P1 走 _use_skill、其余固定走 _use_skill_p2_aimed，
        而后者内部硬编码 self.player2 —— P3~P10 的 AI 放出来的技能
        全落在 P2 身上甚至直接失败。这里临时把「当前施法者」挂到
        player2 再复用那套完整实现，结束一定恢复，不影响人类玩家。
        """
        try:
            if player is getattr(self, 'player', None):
                return bool(self._use_skill(skill_type))
            _orig = getattr(self, 'player2', None)
            try:
                self.player2 = player
                import math as _m
                _a = _m.radians(float(angle_deg if angle_deg else
                                      getattr(player, 'facing_angle', 0.0) or 0.0))
                return bool(self._use_skill_p2_aimed(skill_type, _a, 1.0))
            finally:
                self.player2 = _orig
        except Exception:
            return False
