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
        _m.setup(self.human_player_count)

    def update_bots(self, dt):
        _m = getattr(self, 'bot_manager', None)
        if _m is not None:
            _m.update(dt)

    # ------------------------------------------------------------ 开火
    def _bot_fire(self, player, angle_deg, locked=False):
        """AI 开火：完全复用 Weapon.fire，不改伤害管线。"""
        try:
            _w = player.get_current_weapon()
            if _w is None or not _w.can_fire():
                return False
            _ang = float(angle_deg)
            if locked:
                # 超难强锁：直接把角度对准最近目标（无视散布）
                _tg = None
                _bd = 1e9
                for _o in list(getattr(self, 'enemies', []) or []) + \
                        [p for p in self.registered_players() if p is not player]:
                    if not getattr(_o, 'alive', True):
                        continue
                    _d = (_o.x - player.x) ** 2 + (_o.y - player.y) ** 2
                    if _d < _bd:
                        _bd, _tg = _d, _o
                if _tg is not None:
                    _ang = math.degrees(math.atan2(_tg.y - player.y, _tg.x - player.x))
            try:
                player._fire_spread = 0.0 if locked else None
                _projs = _w.fire(player.x, player.y, _ang,
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
            (getattr(self, 'projectiles', None) or []).extend(_projs or [])
            return bool(_projs)
        except Exception:
            return False

    # ------------------------------------------------------------ 技能
    def _bot_use_skill(self, player, skill_type):
        """AI 放技能：P1 走 _use_skill，其余走 P2 的通用实现。"""
        try:
            if player is getattr(self, 'player', None):
                return bool(self._use_skill(skill_type))
            import math as _m
            _a = _m.radians(float(getattr(player, 'facing_angle', 0.0) or 0.0))
            return bool(self._use_skill_p2_aimed(skill_type, _a, 1.0))
        except Exception:
            return False
