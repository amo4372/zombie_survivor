# -*- coding: utf-8 -*-
"""v2.8.9 双子 Boss（郑某 / 惠某）接入层

把 twin_boss.py 的逻辑真正挂进游戏：生成、每帧更新、效果结算、渲染、成就。
此前 twin_boss.py 只是独立模块，没有任何地方 import，游戏里根本遇不到。
"""
import math
import random
import time

from twin_boss import (TwinBossPair, BossZheng, BossHui, SpaceZone,
                       ZONE_DAMAGE, ZONE_SAFE, ZONE_HEAL, CASTLE_VARIANT)


class TwinBossMixin:
    """双子 Boss 混入类"""

    #: 双子出现的起始波次
    TWIN_MIN_WAVE = 5
    #: 每波出现概率（达到起始波次后）
    TWIN_CHANCE = 0.35
    #: 已有双子在场时不重复生成
    TWIN_BOSS_HP = 6000.0

    # ---------------- 生命周期 ----------------
    def twin_boss_init(self):
        self.twin_boss = None
        self.twin_boss_seen = False
        self._twin_now = 0.0

    @property
    def twin_boss_alive(self):
        return bool(getattr(self, "twin_boss", None) and self.twin_boss.alive)

    def spawn_twin_boss(self, x=None, y=None):
        """生成双子 Boss（成对）。返回是否成功"""
        try:
            if self.twin_boss_alive:
                return False
            # 出生点：以随机活跃玩家为中心外圈
            _sc = self._random_spawn_center() if hasattr(self, "_random_spawn_center") else None
            _cx = getattr(_sc, "x", 0.0) if _sc is not None else 0.0
            _cy = getattr(_sc, "y", 0.0) if _sc is not None else 0.0
            if x is not None:
                _cx, _cy = float(x), float(y or 0)
            _a = random.uniform(0, math.tau)
            _zx = _cx + math.cos(_a) * 320
            _zy = _cy + math.sin(_a) * 320
            _hx = _cx + math.cos(_a + math.pi) * 320
            _hy = _cy + math.sin(_a + math.pi) * 320
            _hp = self.TWIN_BOSS_HP * float(
                getattr(self.config, "difficulty", None) and
                getattr(self.config.difficulty, "value", 1) or 1)
            self.twin_boss = TwinBossPair(
                zheng=BossZheng(_zx, _zy, hp=_hp),
                hui=BossHui(_hx, _hy, hp=_hp),
                rng=random.Random(),
            )
            # 图鉴 / 成就：初见双子
            try:
                from codex import codex_unlock_manager as _cum
                for _n in ("郑某", "惠某"):
                    _u = _cum.unlock_boss(_n) if hasattr(_cum, "unlock_boss") else None
                    if _u:
                        self._codex_unlock_toast(_u, _n)
            except Exception:
                pass
            self._unlock_achievement_safe("twin_boss_meet")
            try:
                self.floating_texts.append(type(self)._FT(
                    _cx, _cy - 60, "郑某 · 惠某 出现了！",
                    color=(255, 120, 200), lifetime=3.0))
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _maybe_spawn_twin(self):
        """Boss 刷新时按概率改刷双子"""
        try:
            _wave = getattr(getattr(self, "horde_manager", None), "wave_count", 0) or 0
            if _wave < self.TWIN_MIN_WAVE:
                return False
            if self.twin_boss_alive:
                return False
            if random.random() > self.TWIN_CHANCE:
                return False
            return self.spawn_twin_boss()
        except Exception:
            return False

    # ---------------- 每帧 ----------------
    def update_twin_boss(self, dt):
        """每帧更新双子：能力、范围圈结算、时停、成就"""
        if not self.twin_boss_alive:
            return
        _tb = self.twin_boss
        self._twin_now = getattr(self, "_twin_now", 0.0) + dt
        _now = time.time()
        _players = [p for p in self.registered_players()
                    if getattr(p, "alive", False)]

        # 玩家子弹（供惠某时间回溯收回）
        _bullets = getattr(self, "projectiles", None)

        _evt = _tb.update(dt, _players, _now, _bullets)

        # 范围圈效果结算
        try:
            for _p, _dmg, _heal in _tb.apply_zone_effects(_players, dt):
                if _dmg > 0:
                    try:
                        _p.take_damage(_dmg, source="郑某·空间圈")
                    except Exception:
                        pass
                if _heal > 0:
                    try:
                        _p.heal(_heal)
                    except Exception:
                        pass
        except Exception:
            pass

        # 郑某弹幕命中玩家
        try:
            for _b in list(_tb.zheng.bullets):
                for _p in _players:
                    if math.hypot(_p.x - _b["x"], _p.y - _b["y"]) < 26:
                        try:
                            _p.take_damage(_b["damage"], source="郑某·弹幕")
                        except Exception:
                            pass
                        _b["life"] = 0
                        break
        except Exception:
            pass

        # 区域时停：冻结范围内的敌人
        try:
            if _tb.hui.freeze_active > 0:
                for _e in getattr(self, "enemies", []) or []:
                    if _tb.frozen_at(getattr(_e, "x", 0), getattr(_e, "y", 0)):
                        _e._hui_frozen = True
                    else:
                        _e._hui_frozen = False
            else:
                for _e in getattr(self, "enemies", []) or []:
                    if getattr(_e, "_hui_frozen", False):
                        _e._hui_frozen = False
        except Exception:
            pass

        # 事件提示
        if _evt:
            try:
                _kind = _evt[0]
                _txt = _evt[1] if len(_evt) > 1 else ""
                if _kind == "windup":
                    self._subtitle_safe("王车易位 · 前摇中……", 2.0)
                elif _kind == "castle":
                    self._subtitle_safe(str(_txt), 3.5)
                    self._unlock_achievement_safe("castle_survived")
                elif _kind == "rewind":
                    self._subtitle_safe("时间回溯 —— 你回到了从前", 2.5)
                elif _kind == "fast_forward":
                    self._subtitle_safe("时间快进！", 2.0)
                elif _kind == "freeze":
                    self._subtitle_safe("区域时停！", 2.0)
            except Exception:
                pass

        # 击杀判定
        if not _tb.alive and not getattr(self, "_twin_slain_done", False):
            self._twin_slain_done = True
            self._unlock_achievement_safe("twin_boss_slain")
            try:
                self.floating_texts.append(type(self)._FT(
                    _tb.zheng.x, _tb.zheng.y - 60, "双子已终结",
                    color=(255, 220, 120), lifetime=3.0))
            except Exception:
                pass

    # ---------------- 伤害入口 ----------------
    def damage_twin_boss(self, amount, x=None, y=None):
        """对双子造成伤害（按位置就近命中一位）"""
        if not self.twin_boss_alive:
            return False
        _tb = self.twin_boss
        try:
            if x is None:
                _tb.take_damage(amount)
                return True
            _dz = math.hypot(x - _tb.zheng.x, y - _tb.zheng.y)
            _dh = math.hypot(x - _tb.hui.x, y - _tb.hui.y)
            _tb.take_damage(amount, "zheng" if _dz <= _dh else "hui")
            return True
        except Exception:
            return False

    # ---------------- 渲染 ----------------
    def draw_twin_boss(self, screen, cam_x, cam_y, scale, font=None, offset_x=0):
        """绘制双子 Boss 本体与范围圈"""
        if not self.twin_boss_alive:
            return
        _tb = self.twin_boss
        import pygame
        try:
            # ---- 范围圈（郑某）----
            for _z in list(_tb.zheng.zones):
                _meta_c = {"damage": (230, 70, 60),
                           "safe": (90, 200, 255),
                           "heal": (110, 240, 140)}.get(_z.kind, (200, 200, 200))
                _pts = []
                for _wx, _wy in _z.polygon(28):
                    _pts.append(((_wx - cam_x) * scale + offset_x,
                                 (_wy - cam_y) * scale))
                if len(_pts) < 3:
                    continue
                _surf = pygame.Surface((screen.get_width(), screen.get_height()),
                                       pygame.SRCALPHA)
                _a = int(70 * min(1.0, _z.life / max(0.01, _z.max_life)))
                pygame.draw.polygon(_surf, (*_meta_c, _a), _pts)
                pygame.draw.polygon(_surf, (*_meta_c, 190), _pts, max(1, int(2 * scale)))
                screen.blit(_surf, (0, 0))
                # 圈类型标签
                if font is not None:
                    _lab = {"damage": "伤害", "safe": "安全",
                            "heal": "恢复"}.get(_z.kind, "")
                    _t = font.render(_lab, True, _meta_c)
                    _cx = sum(p[0] for p in _pts) / len(_pts)
                    _cy = sum(p[1] for p in _pts) / len(_pts)
                    screen.blit(_t, (_cx - _t.get_width() // 2,
                                     _cy - _t.get_height() // 2))
            # ---- 弹幕 ----
            for _b in list(_tb.zheng.bullets):
                _sx = (_b["x"] - cam_x) * scale + offset_x
                _sy = (_b["y"] - cam_y) * scale
                pygame.draw.circle(screen, (255, 200, 90),
                                   (int(_sx), int(_sy)), max(2, int(4 * scale)))
            # ---- 时停区域（惠某）----
            if _tb.hui.freeze_active > 0 and _tb.hui.freeze_center:
                _fx = (_tb.hui.freeze_center[0] - cam_x) * scale + offset_x
                _fy = (_tb.hui.freeze_center[1] - cam_y) * scale
                _r = int(_tb.hui.freeze_radius * scale)
                _s2 = pygame.Surface((screen.get_width(), screen.get_height()),
                                     pygame.SRCALPHA)
                pygame.draw.circle(_s2, (140, 120, 255, 60), (int(_fx), int(_fy)), _r)
                pygame.draw.circle(_s2, (180, 160, 255, 200), (int(_fx), int(_fy)),
                                   _r, max(1, int(2 * scale)))
                screen.blit(_s2, (0, 0))
            # ---- Boss 本体 ----
            for _b, _col in ((_tb.zheng, (120, 220, 255)),
                             (_tb.hui, (255, 150, 220))):
                if not _b.alive:
                    continue
                _bx = (_b.x - cam_x) * scale + offset_x
                _by = (_b.y - cam_y) * scale
                _rr = max(8, int(34 * scale))
                pygame.draw.circle(screen, _col, (int(_bx), int(_by)), _rr)
                pygame.draw.circle(screen, (255, 255, 255), (int(_bx), int(_by)),
                                   _rr, max(1, int(2 * scale)))
                # 血条
                _bw = int(90 * scale)
                _bh = max(3, int(7 * scale))
                _hpx = int(_bx - _bw // 2)
                _hpy = int(_by - _rr - int(14 * scale))
                _ratio = max(0.0, min(1.0, _b.hp / max(1.0, _b.max_hp)))
                pygame.draw.rect(screen, (60, 30, 40),
                                 (_hpx, _hpy, _bw, _bh))
                pygame.draw.rect(screen, _col,
                                 (_hpx, _hpy, int(_bw * _ratio), _bh))
                pygame.draw.rect(screen, (255, 255, 255),
                                 (_hpx, _hpy, _bw, _bh), 1)
                if font is not None:
                    _nt = font.render(f"{_b.name}", True, (255, 255, 255))
                    screen.blit(_nt, (int(_bx - _nt.get_width() // 2),
                                      _hpy - int(16 * scale)))
        except Exception:
            pass

    # ---------------- 辅助 ----------------
    def _subtitle_safe(self, text, dur=2.0):
        try:
            if hasattr(self, "show_subtitle"):
                self.show_subtitle(text, dur)
            elif hasattr(self, "_boss_subtitle"):
                self._boss_subtitle = (str(text), float(dur))
        except Exception:
            pass

    def _unlock_achievement_safe(self, key):
        try:
            if hasattr(self, "unlock_achievement"):
                self.unlock_achievement(key)
            elif getattr(self, "records", None) is not None:
                _r = self.records
                if hasattr(_r, "unlock"):
                    _r.unlock(key)
        except Exception:
            pass
