# -*- coding: utf-8 -*-
"""统一「有伤害技能」的目标结算（v2.9.12）

修复「诸多有伤害技能对敌人玩家无效」：此前每个技能都只遍历
`self.enemies`，PvP 里敌方玩家完全不吃技能伤害。

本模块提供单一入口 `apply_area_damage()`，同时结算
**僵尸 / Boss / 敌方玩家**，并统一处理：
- 抗性系统（走各自 take_damage）
- 状态施加（流血/燃烧/冰冻/中毒，走结构化 EntityStatus）
- 伤害数字 / 击杀回调 / 眩晕
- 扇形方向过滤、距离衰减

技能函数只需调一次，不再各写各的敌人循环。
"""
import math


class TargetMixin:
    def pvp_targets(self, owner=None):
        """PvP 下可被 owner 伤害的玩家；合作模式返回空列表"""
        try:
            if not getattr(self.config, "pvp_enabled", False):
                return []
            owner = owner or getattr(self, "player", None)
            if owner is None:
                return []
            out = []
            for p in self._enemy_players_of(owner):
                if p is None or p is owner:
                    continue
                if not getattr(p, "alive", True) or getattr(p, "downed", False):
                    continue
                out.append(p)
            return out
        except Exception:
            return []

    def _in_arc(self, x, y, tx, ty, angle, half_arc):
        if angle is None or half_arc is None:
            return True
        try:
            a = math.degrees(math.atan2(ty - y, tx - x))
            return abs((a - angle + 180.0) % 360.0 - 180.0) <= float(half_arc)
        except Exception:
            return True

    def apply_area_damage(self, x, y, radius, damage, dtype="magic", owner=None,
                          angle=None, half_arc=None, scale_by_dist=False,
                          include_enemies=True, players_only=False,
                          status_kind=None, status_duration=None,
                          freeze=0.0, stun=0.0, damage_numbers=True):
        """圆形/扇形范围内统一结算。返回命中目标数。"""
        try:
            radius = float(radius)
            base = float(damage)
        except (TypeError, ValueError):
            return 0
        if radius <= 0:
            return 0
        base = max(0.0, base)   # 允许 0 伤害的纯控制技能（仍施加状态）
        owner = owner or getattr(self, "player", None)
        hits = 0
        try:
            from ui_pkg.fx import DamageNumber
        except Exception:
            try:
                from ui import DamageNumber
            except Exception:
                DamageNumber = None

        targets = []
        if include_enemies and not players_only:
            targets.extend(list(getattr(self, "enemies", []) or []))
        targets.extend(self.pvp_targets(owner))

        for t in targets:
            try:
                if t is None or not getattr(t, "alive", True):
                    continue
                if getattr(t, "downed", False):
                    continue
                dx = float(t.x) - float(x)
                dy = float(t.y) - float(y)
                dist = math.hypot(dx, dy)
                if dist > radius + float(getattr(t, "size", 16) or 16):
                    continue
                if not self._in_arc(x, y, t.x, t.y, angle, half_arc):
                    continue
                dmg = base * (1.0 - min(0.9, dist / radius)) if scale_by_dist else base
                is_player = hasattr(t, "take_damage") and hasattr(t, "skill_tree")
                if dmg > 0 and is_player:
                    # 玩家：带攻击来源坐标（供格挡方向判定）+ 不可闪避
                    t.take_damage(dmg, damage_type=dtype, from_front=False,
                                  attack_x=float(x), attack_y=float(y),
                                  bypass_dodge=True, source="player")
                elif dmg > 0:
                    t.take_damage(dmg, damage_type=dtype)
                # 结构化状态（两者都挂了 EntityStatus）
                st = getattr(t, "status", None)
                if st is not None and status_kind:
                    st.apply(status_kind, duration=status_duration)
                if freeze > 0:
                    if is_player:
                        if st is not None:
                            st.apply("freeze", duration=freeze)
                        try:
                            from buff import BuffType
                            t.buff_manager.add_buff(BuffType.FREEZE, duration=freeze)
                        except Exception:
                            pass
                    else:
                        t.frozen_timer = max(getattr(t, "frozen_timer", 0.0), freeze)
                if stun > 0:
                    try:
                        from buff import BuffType
                        if hasattr(t, "buff_manager"):
                            t.buff_manager.add_buff(BuffType.STUN, duration=stun)
                    except Exception:
                        pass
                if dmg > 0 and damage_numbers and DamageNumber is not None:
                    try:
                        self.damage_numbers.append(DamageNumber(t.x, t.y, int(dmg)))
                    except Exception:
                        pass
                if not is_player and not getattr(t, "alive", True):
                    try:
                        self._on_enemy_death(t)
                    except Exception:
                        pass
                hits += 1
            except Exception:
                continue
        return hits
