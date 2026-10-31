# -*- coding: utf-8 -*-
"""v2.8.2 渲染：打击反馈 / 死亡反应 / 死亡详情页 / 玩家向回放画面

设计取向（v2.8.2 修订）
----------------------
回放画面此前是"开发者调试视图"：圆点 + 网格 + 满屏数据。
现在改为**玩家向的真实战况重现**：
  - 敌人按类型着色并带幽光/体型差异，玩家带朝向与血条
  - 地面、暗角、电影黑边，观感接近实际游戏
  - 数据面板默认**隐藏**，按 D 或点「数据」按钮才显示

死亡详情从"结算页浮层"改为**独立页面**，带明确退出按钮，触控可滚动。
"""

import math

import pygame


# 敌人类型 → (主体色, 描边色, 幽光色或None, 体型倍率)
def _enemy_style(type_name):
    _n = str(type_name or "").upper()
    if "BOSS" in _n:
        if "TITAN" in _n:
            return (150, 40, 60), (60, 12, 20), (255, 90, 70), 2.6
        if "QUEEN" in _n:
            return (140, 50, 110), (50, 15, 40), (230, 120, 240), 2.2
        if "MUTANT" in _n:
            return (120, 90, 40), (45, 35, 12), (240, 200, 80), 2.2
        if "WANG" in _n:
            return (90, 70, 130), (30, 22, 48), (170, 140, 255), 2.3
        return (170, 50, 45), (60, 15, 12), (255, 100, 70), 2.2
    if "RUNNER" in _n or "SPRINT" in _n:
        return (200, 110, 40), (70, 38, 10), None, 0.9
    if "EXPLOD" in _n:
        return (190, 80, 35), (66, 26, 10), (255, 110, 40), 1.1
    if "HEAL" in _n:
        return (60, 150, 80), (18, 55, 30), (90, 255, 140), 1.0
    if "PHANTOM" in _n:
        return (120, 80, 160), (40, 26, 58), (180, 110, 255), 1.0
    if "SHIELD" in _n:
        return (90, 110, 130), (30, 38, 46), None, 1.15
    if "CRAWL" in _n:
        return (110, 120, 60), (36, 40, 20), None, 0.85
    if "SPLIT" in _n:
        return (130, 130, 55), (44, 44, 18), None, 1.0
    if "POISON" in _n or "TOXIC" in _n:
        return (95, 140, 55), (32, 48, 18), (140, 220, 90), 1.0
    if "ELECT" in _n or "SHOCK" in _n:
        return (70, 120, 160), (22, 42, 58), (120, 220, 255), 1.0
    if "FAT" in _n or "TANK" in _n:
        return (140, 95, 70), (48, 32, 24), None, 1.5
    return (95, 105, 75), (32, 36, 26), None, 1.0


class ReplayRenderMixin:
    """打击反馈 / 死亡 / 死亡详情页 / 回放的绘制"""

    # ==================================================================
    # 命中标记（画在世界层）
    # ==================================================================
    def _draw_hit_markers(self, camera=None, viewport=None):
        """命中标记；camera/viewport 可选，用于分屏时按各自视口绘制"""
        g = self.game
        _ms = getattr(g, 'hit_markers', None)
        if not _ms:
            return
        _cam = camera if camera is not None else getattr(g, 'camera', None)
        if _cam is None:
            return
        _scale = g.scale
        _cx = getattr(_cam, 'x', 0.0)
        _cy = getattr(_cam, 'y', 0.0)
        _vw = getattr(_cam, 'width', g.scaled_width)
        _vh = getattr(_cam, 'height', g.scaled_height)
        _vpx = 0
        if viewport is not None:
            try:
                _vpx = int(viewport.x)
                _vw = int(viewport.width)
                _vh = int(viewport.height)
            except Exception:
                _vpx = 0
        for _m in _ms:
            _x, _y, _life, _maxl, _kind, _dmg = _m
            _sx = int((_x - _cx) * _scale + _vw / 2) + _vpx
            _sy = int((_y - _cy) * _scale + _vh / 2)
            if _sx < -40 or _sy < -40 or _sx > _vw + 40 or _sy > _vh + 40:
                continue
            _k = 1.0 - (_life / _maxl)     # 0→1 进度
            # v2.8.2：标记显著加大（此前太小，实战中根本注意不到）
            if _kind == "kill":
                _col = (255, 95, 70)
                _base = int(30 * _scale)
            elif _kind == "skill":
                _col = (205, 135, 255)
                _base = int(26 * _scale)
            elif _kind == "heavy":
                _col = (255, 195, 85)
                _base = int(22 * _scale)
            else:
                _col = (250, 250, 250)
                _base = int(15 * _scale)
            # 弹出动画：先大后小
            _pop = 1.0 + 0.55 * (1.0 - _k) ** 2
            _off = int(_base * _pop)
            _w = max(2, int(3 * _scale))
            for _dx, _dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                pygame.draw.line(self.screen, _col,
                                 (_sx + _dx * _off, _sy + _dy * _off),
                                 (_sx + _dx * int(_off * 0.42), _sy + _dy * int(_off * 0.42)),
                                 _w)
            # 中心点
            pygame.draw.circle(self.screen, _col, (_sx, _sy), max(1, int(2 * _scale)))
            # 击杀/技能：额外光环
            if _kind in ("kill", "skill", "heavy"):
                _gs = int(_base * 2.2 * _pop)
                _surf = pygame.Surface((_gs * 2, _gs * 2), pygame.SRCALPHA)
                _a = int(110 * (1 - _k))
                pygame.draw.circle(_surf, (*_col[:3], _a), (_gs, _gs), int(_gs * 0.75))
                self.screen.blit(_surf, (_sx - _gs, _sy - _gs))

    # ==================================================================
    # 受伤红晕 + 来袭方向
    # ==================================================================
    def _draw_damage_feedback(self):
        g = self.game
        _flash = getattr(g, 'damage_flash', 0.0)
        if _flash <= 0.01:
            return
        sw, sh = g.scaled_width, g.scaled_height
        _a = int(min(140, _flash * 140))
        _ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        _ov.fill((190, 20, 20, int(_a * 0.30)))
        try:
            for _i in range(7):
                _inset = int(min(sw, sh) * 0.055 * _i)
                pygame.draw.rect(_ov, (190, 20, 20, max(0, int(_a * 0.15))),
                                 (_inset, _inset, sw - _inset * 2, sh - _inset * 2), 0)
        except Exception:
            pass
        self.screen.blit(_ov, (0, 0))
        # 来袭方向箭头（加大加粗）
        _hd = getattr(g, 'hurt_dir', None)
        if _hd is not None:
            _ang, _life = _hd
            _cx, _cy = sw / 2, sh / 2
            _rad = min(sw, sh) * 0.36
            _ax = _cx + math.cos(_ang) * _rad
            _ay = _cy + math.sin(_ang) * _rad
            _sz = int(34 * g.scale)
            _col = (255, 70, 60)
            _pts = [
                (_ax + math.cos(_ang) * _sz, _ay + math.sin(_ang) * _sz),
                (_ax + math.cos(_ang + 2.45) * _sz, _ay + math.sin(_ang + 2.45) * _sz),
                (_ax + math.cos(_ang - 2.45) * _sz, _ay + math.sin(_ang - 2.45) * _sz),
            ]
            pygame.draw.polygon(self.screen, _col, _pts)
            pygame.draw.polygon(self.screen, (255, 190, 180), _pts, max(1, int(2 * g.scale)))

    # ==================================================================
    # DYING：死亡反应时间
    # ==================================================================
    def _draw_dying(self):
        g = self.game
        sw, sh, _s = g.scaled_width, g.scaled_height, g.scale
        _k = 1.0 - max(0.0, min(1.0, getattr(g, 'death_timer', 0.0) / 2.6))
        _ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        _ov.fill((40, 0, 0, int(150 * _k)))
        self.screen.blit(_ov, (0, 0))
        try:
            _vg = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for _i in range(8):
                _inset = int(min(sw, sh) * 0.05 * _i)
                pygame.draw.rect(_vg, (0, 0, 0, int(16 * _k)),
                                 (_inset, _inset, sw - _inset * 2, sh - _inset * 2), 0)
            self.screen.blit(_vg, (0, 0))
        except Exception:
            pass
        _t = g.font_title.render("你被击倒了", True, (255, 90, 70))
        self.screen.blit(_t, _t.get_rect(center=(sw / 2, int(sh * 0.30))))
        _killer = getattr(g, 'death_killer', None)
        if _killer:
            _src = str(_killer.get("source", "") or "未知")
            _map = {"zombie": "僵尸", "player": "敌对玩家", "boss": "Boss",
                    "dot": "持续伤害", "explosion": "爆炸"}
            _line = f"致命一击：{_map.get(_src, _src)} · {_killer.get('amount', 0):.0f} 点伤害"
            _st = g.font_large.render(_line, True, (255, 200, 160))
            self.screen.blit(_st, _st.get_rect(center=(sw / 2, int(sh * 0.30) + int(48 * _s))))
        _hint = g.font.render("轻触屏幕 / 空格 跳过", True, (190, 190, 190))
        self.screen.blit(_hint, _hint.get_rect(center=(sw / 2, int(sh * 0.82))))

    # ==================================================================
    # 死亡详情：独立页面（v2.8.2）
    # ==================================================================
    def _draw_death_detail_page(self):
        g = self.game
        sw, sh, _s = g.scaled_width, g.scaled_height, g.scale
        self.screen.fill((14, 10, 12))
        # 标题
        _t = g.font_title.render("死亡详情", True, (255, 200, 110))
        self.screen.blit(_t, _t.get_rect(center=(sw / 2, int(66 * _s))))

        _sum = g.death_detail_summary() if hasattr(g, 'death_detail_summary') else {}
        _y = int(120 * _s)
        _info = (f"总承伤 {_sum.get('total', 0):.0f}    命中 {_sum.get('hits', 0)} 次    "
                 f"最高单次 {_sum.get('max', 0):.0f}")
        _si = g.font_large.render(_info, True, (225, 225, 230))
        self.screen.blit(_si, _si.get_rect(center=(sw / 2, _y)))
        _y += int(34 * _s)
        _kk = _sum.get('killer')
        if _kk:
            _ki = g.font.render(f"致命来源：{_kk}", True, (255, 120, 100))
            self.screen.blit(_ki, _ki.get_rect(center=(sw / 2, _y)))
        _y += int(30 * _s)

        # 表头
        _px = int(sw * 0.06)
        _pw = sw - _px * 2
        _cols = [("时间", 0.02), ("来源", 0.20), ("类型", 0.44), ("伤害", 0.66), ("剩余HP", 0.83)]
        for _name, _rx in _cols:
            _cx = _px + int(_pw * _rx)
            self.screen.blit(g.font_small.render(_name, True, (150, 190, 230)), (_cx, _y))
        _y += int(20 * _s)
        pygame.draw.line(self.screen, (80, 70, 88), (_px, _y), (_px + _pw, _y), 1)
        _y += int(8 * _s)

        _rows = g.death_detail_rows() if hasattr(g, 'death_detail_rows') else []
        _map = {"zombie": "僵尸", "player": "敌对玩家", "boss": "Boss", "dot": "持续伤害",
                "melee": "近战", "ranged": "远程", "explosion": "爆炸", "aoe": "范围",
                "magic": "法术", "fire": "燃烧", "fall": "坠落"}
        _scroll = getattr(g, 'death_detail_scroll', 0)
        _rows = _rows[_scroll:]
        _bottom = sh - int(120 * _s)
        _row_h = int(24 * _s)
        if not _rows:
            _e = g.font.render("本局没有记录到伤害", True, (150, 150, 150))
            self.screen.blit(_e, _e.get_rect(center=(sw / 2, _y + int(40 * _s))))
        for _r in _rows:
            if _y + _row_h > _bottom:
                break
            _src = _map.get(str(_r.get("source", "")), str(_r.get("source", "")) or "—")
            _ty = _map.get(str(_r.get("type", "")), str(_r.get("type", "")) or "—")
            _amt = _r.get("amount", 0)
            _col = (255, 150, 120) if _amt >= 25 else (225, 225, 225)
            _vals = [(f"-{_r.get('ago', 0):.1f}s", 0.02, (175, 175, 180)),
                     (f"{_r.get('tag', '')} {_src}", 0.20, (255, 210, 130)),
                     (_ty, 0.44, (170, 200, 220)),
                     (f"{_amt:.0f}", 0.66, _col),
                     (f"{_r.get('hp', 0):.0f}", 0.83, (150, 220, 160))]
            for _txt, _rx, _c in _vals:
                self.screen.blit(g.font_small.render(_txt, True, _c), (_px + int(_pw * _rx), _y))
            _y += _row_h

        # 退出按钮（明确、大尺寸、触控友好）
        _btn = g.death_detail_exit_btn
        _btn.visible = True
        _mp = pygame.mouse.get_pos()
        _mpr = pygame.mouse.get_pressed()
        if _btn.update(_mp, _mpr, getattr(g, 'touch_events', []), _s):
            g.show_death_detail = False
            g.death_detail_scroll = 0
            from config import GameState
            g.state = GameState.GAME_OVER
        _btn.draw(self.screen, g.font_large, _s)
        _hint = g.font_small.render("上下滑动可滚动列表", True, (140, 140, 150))
        self.screen.blit(_hint, _hint.get_rect(center=(sw / 2, _bottom + int(18 * _s))))

    # ==================================================================
    # 回放：玩家向真实战况（v2.8.2）
    # ==================================================================
    def _draw_replay(self):
        g = self.game
        _d = getattr(g, 'replay_data', None)
        sw, sh, _s = g.scaled_width, g.scaled_height, g.scale
        if _d is None or not _d.frames:
            self.screen.fill((10, 9, 14))
            _t = g.font_large.render("没有可播放的回放", True, (200, 200, 200))
            self.screen.blit(_t, _t.get_rect(center=(sw / 2, sh / 2)))
            return
        _cam = getattr(g, 'replay_cam', None)
        if _cam is None:
            return
        _z = _cam.zoom * _s

        def w2s(wx, wy):
            return (int((wx - _cam.x) * _z + sw / 2), int((wy - _cam.y) * _z + sh / 2))

        # --- 地面（暗色地表，极淡网格：像游戏地面而非调试网格）---
        self.screen.fill((18, 17, 22))
        _step = 160
        _x0 = int((_cam.x - sw / 2 / _z) / _step) * _step
        _x1 = int((_cam.x + sw / 2 / _z) / _step) * _step + _step
        _y0 = int((_cam.y - sh / 2 / _z) / _step) * _step
        _y1 = int((_cam.y + sh / 2 / _z) / _step) * _step + _step
        for _gx in range(_x0, _x1, _step):
            _a, _b = w2s(_gx, _y0)
            _c2, _d2 = w2s(_gx, _y1)
            pygame.draw.line(self.screen, (26, 25, 32), (_a, _b), (_c2, _d2), 1)
        for _gy in range(_y0, _y1, _step):
            _a, _b = w2s(_x0, _gy)
            _c2, _d2 = w2s(_x1, _gy)
            pygame.draw.line(self.screen, (26, 25, 32), (_a, _b), (_c2, _d2), 1)

        _f = _d.current
        _types = _d.types

        # --- 敌人（按类型着色 + 幽光 + 体型）---
        for _e in _f.enemies:
            _eid, _ti, _ex, _ey, _ehp, _emax, _ea, _esize, _ef = _e
            if not (_ef & 1):
                continue
            _sx, _sy = w2s(_ex, _ey)
            if _sx < -80 or _sy < -80 or _sx > sw + 80 or _sy > sh + 80:
                continue
            _name = _types[_ti] if _ti < len(_types) else ""
            _body, _edge, _glow, _mult = _enemy_style(_name)
            _r = max(3, int((_esize if _esize > 0 else 12.0) * 0.55 * _mult * _cam.zoom * _s))
            # 幽光
            if _glow:
                _gs = _r * 3
                _surf = pygame.Surface((_gs * 2, _gs * 2), pygame.SRCALPHA)
                pygame.draw.circle(_surf, (*_glow[:3], 42), (_gs, _gs), _gs)
                self.screen.blit(_surf, (_sx - _gs, _sy - _gs))
            # 影子
            pygame.draw.ellipse(self.screen, (8, 8, 10),
                                (_sx - _r, _sy + int(_r * 0.55), _r * 2, max(2, int(_r * 0.5))))
            pygame.draw.circle(self.screen, _body, (_sx, _sy), _r)
            pygame.draw.circle(self.screen, _edge, (_sx, _sy), _r, max(1, int(2 * _s)))
            # 朝向
            _ang = math.radians(_ea)
            pygame.draw.line(self.screen, _edge, (_sx, _sy),
                             (_sx + math.cos(_ang) * _r * 1.5, _sy + math.sin(_ang) * _r * 1.5),
                             max(1, int(2 * _s)))
            # 血条（仅在受伤时显示，避免画面杂乱）
            if _emax > 0 and _ehp < _emax * 0.999:
                _bw = max(10, int(_r * 2.2))
                _bh = max(2, int(3 * _s))
                _bx = _sx - _bw // 2
                _by = _sy - _r - int(7 * _s)
                pygame.draw.rect(self.screen, (30, 12, 12), (_bx, _by, _bw, _bh))
                pygame.draw.rect(self.screen, (215, 60, 55),
                                 (_bx, _by, int(_bw * max(0.0, _ehp / _emax)), _bh))
            # Boss 名签
            if "BOSS" in str(_name).upper():
                _bt = g.font_small.render("BOSS", True, (255, 190, 110))
                self.screen.blit(_bt, (_sx - _bt.get_width() // 2, _sy - _r - int(22 * _s)))

        # --- 玩家（带朝向、血条、标签）---
        _pcols = [(110, 225, 255), (255, 205, 110), (175, 255, 175), (255, 155, 215)]
        for _pi, _p in enumerate(_f.players):
            _px2, _py2, _php, _pmax, _pa, _pf = _p
            _sx, _sy = w2s(_px2, _py2)
            _alive = bool(_pf & 1)
            _downed = bool(_pf & 2)
            _col = _pcols[_pi % 4] if _alive else (115, 115, 120)
            _r = max(5, int(13 * _cam.zoom * _s))
            pygame.draw.ellipse(self.screen, (8, 8, 10),
                                (_sx - _r, _sy + int(_r * 0.6), _r * 2, max(2, int(_r * 0.5))))
            pygame.draw.circle(self.screen, _col, (_sx, _sy), _r)
            pygame.draw.circle(self.screen, (255, 255, 255), (_sx, _sy), _r, max(1, int(2 * _s)))
            _ang = math.radians(_pa)
            pygame.draw.line(self.screen, (255, 255, 255), (_sx, _sy),
                             (_sx + math.cos(_ang) * _r * 1.9, _sy + math.sin(_ang) * _r * 1.9),
                             max(1, int(2 * _s)))
            _tag = f"P{_pi + 1}" + (" 倒地" if _downed else ("" if _alive else " 阵亡"))
            _ts = g.font_small.render(_tag, True, _col)
            self.screen.blit(_ts, (_sx - _ts.get_width() // 2, _sy - _r - int(16 * _s)))
            if _pmax > 0:
                _bw = max(14, int(_r * 2.4))
                _bh = max(2, int(4 * _s))
                _bx = _sx - _bw // 2
                _by = _sy + _r + int(4 * _s)
                pygame.draw.rect(self.screen, (26, 26, 30), (_bx, _by, _bw, _bh))
                _ratio = max(0.0, min(1.0, _php / _pmax))
                _hc = (90, 220, 120) if _ratio > 0.5 else ((240, 200, 70) if _ratio > 0.25 else (235, 70, 60))
                pygame.draw.rect(self.screen, _hc, (_bx, _by, int(_bw * _ratio), _bh))

        # --- 电影感：暗角 + 上下黑边 ---
        try:
            _vg = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for _i in range(9):
                _inset = int(min(sw, sh) * 0.045 * _i)
                pygame.draw.rect(_vg, (0, 0, 0, 13),
                                 (_inset, _inset, sw - _inset * 2, sh - _inset * 2), 0)
            self.screen.blit(_vg, (0, 0))
        except Exception:
            pass
        _bar = max(6, int(sh * 0.055))
        pygame.draw.rect(self.screen, (0, 0, 0), (0, 0, sw, _bar))
        pygame.draw.rect(self.screen, (0, 0, 0), (0, sh - _bar, sw, _bar))

        # --- 顶部标题（轻量，玩家向）---
        _ttl = g.font.render("死亡回放", True, (225, 205, 175))
        self.screen.blit(_ttl, _ttl.get_rect(center=(sw / 2, int(_bar + 16 * _s))))
        if not g.replay_playing:
            _pz = g.font_small.render("已暂停", True, (255, 210, 130))
            self.screen.blit(_pz, _pz.get_rect(center=(sw / 2, int(_bar + 42 * _s))))

        # --- 数据面板（默认隐藏，按 D 或「数据」按钮切换）---
        if getattr(g, 'replay_show_data', False):
            self._draw_replay_data_panel(_d, sw, sh, _s)

        # --- 底部时间轴 ---
        self._draw_replay_timeline(_d, sw, sh, _s)
        # --- 触控按钮 ---
        self._draw_replay_touch_buttons(_d, sw, sh, _s)

    def _draw_replay_data_panel(self, _d, sw, sh, _s):
        g = self.game
        _st = g.replay_stats() if hasattr(g, 'replay_stats') else {}
        _pw = int(min(sw * 0.42, 330 * _s))
        _ph = int(140 * _s)
        _bx = sw - _pw - int(12 * _s)
        _by = int(58 * _s)
        _pn = pygame.Surface((_pw, _ph), pygame.SRCALPHA)
        _pn.fill((12, 11, 15, 226))
        self.screen.blit(_pn, (_bx, _by))
        pygame.draw.rect(self.screen, (120, 200, 240), (_bx, _by, _pw, _ph), 1)
        _ly = _by + int(8 * _s)
        _lines = [
            f"时间 {_st.get('time', 0):.1f}s / {_st.get('duration', 0):.1f}s",
            f"敌人 {_st.get('enemies_alive', 0)}（Boss {_st.get('boss', 0)}）  玩家 {_st.get('players', 0)}",
            f"帧 {_st.get('frame', 0)}/{_st.get('frames', 0)}   倍速 {_d.speed:g}x",
        ]
        for _l in _lines:
            self.screen.blit(g.font_small.render(_l, True, (215, 215, 225)),
                             (_bx + int(10 * _s), _ly))
            _ly += int(17 * _s)
        for _e in _st.get("events", [])[-4:]:
            _txt = f"{_e.get('t', 0):.1f}s {_e.get('text', '')}"
            self.screen.blit(g.font_small.render(_txt, True, (175, 200, 175)),
                             (_bx + int(10 * _s), _ly))
            _ly += int(15 * _s)

    def _draw_replay_timeline(self, _d, sw, sh, _s):
        g = self.game
        _th = int(28 * _s)
        _ty = sh - int(150 * _s)
        _tw = sw - int(40 * _s)
        _tx = int(20 * _s)
        _mp = pygame.mouse.get_pos()
        _mpr = pygame.mouse.get_pressed()
        _rect = pygame.Rect(_tx, _ty, _tw, _th)
        pygame.draw.rect(self.screen, (40, 38, 48), _rect, border_radius=int(5 * _s))
        _ratio = _d.index / max(1, len(_d.frames) - 1)
        pygame.draw.rect(self.screen, (110, 200, 250),
                         (_tx, _ty, int(_tw * _ratio), _th), border_radius=int(5 * _s))
        # 阵亡标记
        try:
            for _e in _d.events:
                if _e.get("tag") == "death":
                    _er = min(1.0, _e.get("t", 0) / max(0.01, _d.duration))
                    _mx = _tx + int(_tw * _er)
                    pygame.draw.line(self.screen, (255, 80, 70),
                                     (_mx, _ty - int(5 * _s)), (_mx, _ty + _th + int(5 * _s)),
                                     max(1, int(3 * _s)))
        except Exception:
            pass
        # 点击/拖动跳转（鼠标 + 触控）
        try:
            _touch = getattr(g, 'touch_events', []) or []
            _hit = False
            if _mpr[0] and _rect.collidepoint(_mp):
                _hit = True
                _vx = _mp[0]
            else:
                for _ev in _touch:
                    _p = getattr(_ev, 'pos', None) or (_ev.x, _ev.y)
                    if _rect.collidepoint(_p[0], _p[1]):
                        _hit = True
                        _vx = _p[0]
                        break
            if _hit:
                g.replay_seek((_vx - _tx) / max(1.0, _tw))
        except Exception:
            pass
        _lb = g.font_small.render(f"{_d.time_now:.1f}s / {_d.duration:.1f}s", True, (200, 200, 210))
        self.screen.blit(_lb, (_tx + int(6 * _s), _ty - int(17 * _s)))

    def _draw_replay_touch_buttons(self, _d, sw, sh, _s):
        """回放页触控控件（手机端主要操作方式）"""
        g = self.game
        _btns = getattr(g, 'replay_touch_btns', None) or {}
        _mp = pygame.mouse.get_pos()
        _mpr = pygame.mouse.get_pressed()
        _touch = getattr(g, 'touch_events', []) or []
        for _k, _b in _btns.items():
            _b.visible = True
            if not _b.update(_mp, _mpr, _touch, _s):
                continue
            if _k == "play":
                g.replay_toggle_play()
            elif _k == "prev":
                g.replay_step(-1)
            elif _k == "next":
                g.replay_step(1)
            elif _k == "zoom_o":
                g.replay_cam.zoom_by(1.25)
            elif _k == "zoom_i":
                g.replay_cam.zoom_by(1 / 1.25)
            elif _k == "follow":
                g.replay_follow = not getattr(g, 'replay_follow', True)
            elif _k == "data":
                g.replay_show_data = not getattr(g, 'replay_show_data', False)
            elif _k == "exit":
                g.exit_replay()
                return
        for _b in _btns.values():
            _b.draw(self.screen, g.font_small, _s)
