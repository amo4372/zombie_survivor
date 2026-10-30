# -*- coding: utf-8 -*-
"""v2.8.0 渲染：打击反馈 / 死亡反应 / 死亡详情 / 全局回放

- 命中标记：敌人被命中处弹出十字/爆点，技能命中用醒目配色（技能也有打击感）
- 受伤红晕 + 来袭方向指示
- DYING：慢放定格画面 + 致命一击来源提示
- 死亡详情面板：最近伤害的来源/数值/类型/剩余血量
- 回放：自由摄像机重看战况 + 数据面板 + 时间轴 + 事件流水 + 运动轨迹
"""

import math

import pygame


class ReplayRenderMixin:
    """打击反馈 / 死亡 / 回放的绘制"""

    # ==================================================================
    # 命中标记（画在世界层，需在 _draw_playing_core 之后调用）
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
            _k = 1.0 - (_life / _maxl)          # 0→1 进度
            _a = int(255 * (1.0 - _k * 0.85))
            if _kind == "kill":
                _col, _r = (255, 90, 70), int(16 * (1 + _k * 0.6))
            elif _kind == "skill":
                _col, _r = (200, 130, 255), int(14 * (1 + _k * 0.5))
            elif _kind == "heavy":
                _col, _r = (255, 190, 80), int(12 * (1 + _k * 0.4))
            else:
                _col, _r = (245, 245, 245), 9
            # 四角发散的命中标记（收缩动画）
            _off = int((_r + 10) * (1.0 - _k * 0.35))
            _w = max(1, int(2 * _scale))
            for _dx, _dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                pygame.draw.line(self.screen, _col,
                                 (_sx + _dx * _off, _sy + _dy * _off),
                                 (_sx + _dx * int(_off * 0.45), _sy + _dy * int(_off * 0.45)),
                                 _w)
            if _kind in ("kill", "skill"):
                _gs = _r * 3
                _surf = pygame.Surface((_gs * 2, _gs * 2), pygame.SRCALPHA)
                pygame.draw.circle(_surf, (*_col[:3], int(70 * (1 - _k))),
                                   (_gs, _gs), int(_gs * (0.4 + _k * 0.5)))
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
        _a = int(min(120, _flash * 120))
        _ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        # 边缘红晕（中间透明，四周红）
        _ov.fill((190, 20, 20, int(_a * 0.35)))
        try:
            for _i in range(6):
                _inset = int(min(sw, sh) * 0.06 * _i)
                pygame.draw.rect(_ov, (190, 20, 20, max(0, int(_a * 0.16))),
                                 (_inset, _inset, sw - _inset * 2, sh - _inset * 2), 0)
        except Exception:
            pass
        self.screen.blit(_ov, (0, 0))
        # 来袭方向指示（屏幕边缘箭头）
        _hd = getattr(g, 'hurt_dir', None)
        if _hd is not None:
            _ang, _life = _hd
            _cx, _cy = sw / 2, sh / 2
            _rad = min(sw, sh) * 0.38
            _ax = _cx + math.cos(_ang) * _rad
            _ay = _cy + math.sin(_ang) * _rad
            _col = (255, 70, 60)
            _sz = int(22 * g.scale)
            _pts = [
                (_ax + math.cos(_ang) * _sz, _ay + math.sin(_ang) * _sz),
                (_ax + math.cos(_ang + 2.5) * _sz, _ay + math.sin(_ang + 2.5) * _sz),
                (_ax + math.cos(_ang - 2.5) * _sz, _ay + math.sin(_ang - 2.5) * _sz),
            ]
            pygame.draw.polygon(self.screen, _col, _pts)

    # ==================================================================
    # DYING：死亡反应时间
    # ==================================================================
    def _draw_dying(self):
        g = self.game
        sw, sh, _s = g.scaled_width, g.scaled_height, g.scale
        # 渐暗 + 红调
        _k = 1.0 - max(0.0, min(1.0, getattr(g, 'death_timer', 0.0) / 2.6))
        _ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        _ov.fill((40, 0, 0, int(150 * _k)))
        self.screen.blit(_ov, (0, 0))
        # 去饱和暗角
        try:
            _vg = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for _i in range(8):
                _inset = int(min(sw, sh) * 0.05 * _i)
                pygame.draw.rect(_vg, (0, 0, 0, int(16 * _k)),
                                 (_inset, _inset, sw - _inset * 2, sh - _inset * 2), 0)
            self.screen.blit(_vg, (0, 0))
        except Exception:
            pass
        # 文案
        _t = g.font_title.render("你被击倒了", True, (255, 90, 70))
        self.screen.blit(_t, _t.get_rect(center=(sw / 2, int(sh * 0.30))))
        _killer = getattr(g, 'death_killer', None)
        if _killer:
            _src = str(_killer.get("source", "") or "未知")
            _map = {"zombie": "僵尸", "player": "敌对玩家", "boss": "Boss",
                    "dot": "持续伤害", "explosion": "爆炸"}
            _src_cn = _map.get(_src, _src)
            _line = f"致命一击：{_src_cn} · {_killer.get('amount', 0):.0f} 点伤害"
            _st = g.font_large.render(_line, True, (255, 200, 160))
            self.screen.blit(_st, _st.get_rect(center=(sw / 2, int(sh * 0.30) + int(48 * _s))))
        _hint = g.font.render("空格 / 点击 跳过", True, (190, 190, 190))
        self.screen.blit(_hint, _hint.get_rect(center=(sw / 2, int(sh * 0.82))))

    # ==================================================================
    # 死亡详情面板
    # ==================================================================
    def _draw_death_detail(self):
        g = self.game
        if not getattr(g, 'show_death_detail', False):
            return
        sw, sh, _s = g.scaled_width, g.scaled_height, g.scale
        _w = int(min(sw * 0.86, 720 * _s))
        _h = int(min(sh * 0.78, 560 * _s))
        _px = (sw - _w) // 2
        _py = (sh - _h) // 2
        _panel = pygame.Surface((_w, _h), pygame.SRCALPHA)
        _panel.fill((16, 12, 18, 244))
        self.screen.blit(_panel, (_px, _py))
        pygame.draw.rect(self.screen, (200, 170, 90), (_px, _py, _w, _h), max(1, int(2 * _s)))

        _y = _py + int(14 * _s)
        _t = g.font_large.render("死亡详情", True, (255, 210, 120))
        self.screen.blit(_t, _t.get_rect(center=(sw / 2, _y + int(12 * _s))))
        _y += int(38 * _s)

        _sum = g.death_detail_summary() if hasattr(g, 'death_detail_summary') else {}
        _info = f"总承伤 {_sum.get('total', 0):.0f} · {_sum.get('hits', 0)} 次命中 · 最高单次 {_sum.get('max', 0):.0f}"
        _si = g.font.render(_info, True, (200, 200, 210))
        self.screen.blit(_si, _si.get_rect(center=(sw / 2, _y)))
        _y += int(26 * _s)
        _kk = _sum.get('killer')
        if _kk:
            _ki = g.font.render(f"致命来源：{_kk}", True, (255, 120, 100))
            self.screen.blit(_ki, _ki.get_rect(center=(sw / 2, _y)))
        _y += int(30 * _s)

        # 表头
        _cols = [("时间", 0.10), ("来源", 0.30), ("类型", 0.52), ("伤害", 0.74), ("剩余HP", 0.88)]
        for _name, _rx in _cols:
            _cx = _px + int(_w * _rx) + int(8 * _s)
            _hs = g.font_small.render(_name, True, (150, 190, 230))
            self.screen.blit(_hs, (_cx, _y))
        _y += int(20 * _s)
        pygame.draw.line(self.screen, (90, 80, 100),
                         (_px + int(10 * _s), _y), (_px + _w - int(10 * _s), _y), 1)
        _y += int(6 * _s)

        _rows = g.death_detail_rows() if hasattr(g, 'death_detail_rows') else []
        if not _rows:
            _e = g.font.render("（本局没有记录到伤害）", True, (150, 150, 150))
            self.screen.blit(_e, _e.get_rect(center=(sw / 2, _y + int(30 * _s))))
        _map = {"zombie": "僵尸", "player": "敌对玩家", "boss": "Boss", "dot": "持续伤害",
                "melee": "近战", "ranged": "远程", "explosion": "爆炸", "aoe": "范围",
                "magic": "法术", "fire": "燃烧", "fall": "坠落"}
        _maxr = int((_py + _h - _y - int(20 * _s)) / max(1, int(19 * _s)))
        for _r in _rows[:_maxr]:
            _ago = _r.get("ago", 0)
            _src = _map.get(str(_r.get("source", "")), str(_r.get("source", "")) or "—")
            _ty = _map.get(str(_r.get("type", "")), str(_r.get("type", "")) or "—")
            _amt = _r.get("amount", 0)
            _hp = _r.get("hp", 0)
            _col = (255, 150, 120) if _amt >= 25 else (225, 225, 225)
            _vals = [(f"-{_ago:.1f}s", 0.10, (180, 180, 180)),
                     (_src, 0.30, (255, 210, 130)),
                     (_ty, 0.52, (170, 200, 220)),
                     (f"{_amt:.0f}", 0.74, _col),
                     (f"{_hp:.0f}", 0.88, (150, 220, 160))]
            for _txt, _rx, _c in _vals:
                _cx = _px + int(_w * _rx) + int(8 * _s)
                _srf = g.font_small.render(_txt, True, _c)
                self.screen.blit(_srf, (_cx, _y))
            _y += int(19 * _s)

        _cls = g.font.render("点击面板外 / ESC 关闭", True, (140, 140, 150))
        self.screen.blit(_cls, _cls.get_rect(center=(sw / 2, _py + _h - int(14 * _s))))

    # ==================================================================
    # 回放
    # ==================================================================
    def _draw_replay(self):
        g = self.game
        _d = getattr(g, 'replay_data', None)
        sw, sh, _s = g.scaled_width, g.scaled_height, g.scale
        self.screen.fill((10, 9, 14))
        if _d is None or not _d.frames:
            _t = g.font_large.render("没有可播放的回放", True, (200, 200, 200))
            self.screen.blit(_t, _t.get_rect(center=(sw / 2, sh / 2)))
            return
        _cam = getattr(g, 'replay_cam', None)
        if _cam is None:
            return
        _z = _cam.zoom * _s

        def w2s(wx, wy):
            return (int((wx - _cam.x) * _z + sw / 2), int((wy - _cam.y) * _z + sh / 2))

        # --- 地面网格 ---
        _step = 200
        _x0 = int((_cam.x - sw / 2 / _z) / _step) * _step
        _x1 = int((_cam.x + sw / 2 / _z) / _step) * _step + _step
        _y0 = int((_cam.y - sh / 2 / _z) / _step) * _step
        _y1 = int((_cam.y + sh / 2 / _z) / _step) * _step + _step
        for _gx in range(_x0, _x1, _step):
            _a, _b = w2s(_gx, _y0)
            _c2, _d2 = w2s(_gx, _y1)
            pygame.draw.line(self.screen, (34, 32, 42), (_a, _b), (_c2, _d2), 1)
        for _gy in range(_y0, _y1, _step):
            _a, _b = w2s(_x0, _gy)
            _c2, _d2 = w2s(_x1, _gy)
            pygame.draw.line(self.screen, (34, 32, 42), (_a, _b), (_c2, _d2), 1)

        _f = _d.current
        # --- 运动轨迹（最近 40 帧） ---
        try:
            _i0 = max(0, _d.index - 40)
            for _pi, _col in ((0, (120, 220, 255)), (1, (255, 200, 120)),
                              (2, (180, 255, 180)), (3, (255, 160, 220))):
                _pts = []
                for _fi in range(_i0, _d.index + 1):
                    _fr = _d.frames[_fi]
                    if len(_fr.players) > _pi:
                        _pts.append(w2s(_fr.players[_pi][0], _fr.players[_pi][1]))
                if len(_pts) > 1:
                    pygame.draw.lines(self.screen, _col, False, _pts, max(1, int(2 * _s)))
        except Exception:
            pass

        # --- 敌人 ---
        for _e in _f.enemies:
            _eid, _ti, _ex, _ey, _ehp, _ea, _ef = _e
            _alive = bool(_ef & 1)
            _boss = bool(_ef & 2)
            if not _alive:
                continue
            _sx, _sy = w2s(_ex, _ey)
            if _sx < -50 or _sy < -50 or _sx > sw + 50 or _sy > sh + 50:
                continue
            _r = int((14 if _boss else 7) * _cam.zoom * _s / _s * _s)
            _r = max(3, int((14 if _boss else 7) * _cam.zoom * _s))
            _col = (255, 90, 70) if _boss else (200, 70, 60)
            pygame.draw.circle(self.screen, _col, (_sx, _sy), _r)
            pygame.draw.circle(self.screen, (90, 20, 20), (_sx, _sy), _r, 1)
            if _boss:
                _bt = g.font_small.render("BOSS", True, (255, 200, 120))
                self.screen.blit(_bt, (_sx - _bt.get_width() // 2, _sy - _r - int(14 * _s)))

        # --- 玩家 ---
        for _pi, _p in enumerate(_f.players):
            _px2, _py2, _php, _pa, _pf = _p
            _sx, _sy = w2s(_px2, _py2)
            _alive = bool(_pf & 1)
            _downed = bool(_pf & 2)
            _col = [(120, 230, 255), (255, 210, 120), (180, 255, 180), (255, 160, 220)][_pi % 4]
            if not _alive:
                _col = (110, 110, 115)
            _r = max(4, int(10 * _cam.zoom * _s))
            pygame.draw.circle(self.screen, _col, (_sx, _sy), _r)
            pygame.draw.circle(self.screen, (255, 255, 255), (_sx, _sy), _r, max(1, int(2 * _s)))
            # 朝向
            _ang = math.radians(_pa)
            pygame.draw.line(self.screen, _col, (_sx, _sy),
                             (_sx + math.cos(_ang) * _r * 1.9, _sy + math.sin(_ang) * _r * 1.9),
                             max(1, int(2 * _s)))
            _tag = f"P{_pi + 1}{' 倒地' if _downed else ''}"
            _ts = g.font_small.render(_tag, True, _col)
            self.screen.blit(_ts, (_sx - _ts.get_width() // 2, _sy - _r - int(15 * _s)))
            _hs = g.font_small.render(f"{_php:.0f}", True, (230, 230, 230))
            self.screen.blit(_hs, (_sx - _hs.get_width() // 2, _sy + _r + int(2 * _s)))

        # --- 数据面板 ---
        _st = g.replay_stats() if hasattr(g, 'replay_stats') else {}
        _pw = int(min(sw * 0.42, 340 * _s))
        _ph = int(150 * _s)
        _bx = sw - _pw - int(10 * _s)
        _by = int(10 * _s)
        _pn = pygame.Surface((_pw, _ph), pygame.SRCALPHA)
        _pn.fill((14, 12, 18, 226))
        self.screen.blit(_pn, (_bx, _by))
        pygame.draw.rect(self.screen, (120, 200, 240), (_bx, _by, _pw, _ph), 1)
        _ly = _by + int(8 * _s)
        _tt = g.font.render(f"回放：{getattr(_d, 'name', '')}", True, (140, 220, 255))
        self.screen.blit(_tt, (_bx + int(10 * _s), _ly)); _ly += int(20 * _s)
        _mode = str(_st.get("meta", {}).get("mode", ""))
        _lines = [
            f"时间 {_st.get('time', 0):.1f}s / {_st.get('duration', 0):.1f}s"
            f"（{_st.get('frame', 0)}/{_st.get('frames', 0)} 帧）",
            f"场上敌人 {_st.get('enemies_alive', 0)}（Boss {_st.get('boss', 0)}）  玩家 {_st.get('players', 0)}",
            f"模式 {_mode}   倍速 {_d.speed:g}x{'  ▶' if g.replay_playing else '  ‖'}",
        ]
        for _l in _lines:
            _srf = g.font_small.render(_l, True, (215, 215, 225))
            self.screen.blit(_srf, (_bx + int(10 * _s), _ly)); _ly += int(17 * _s)
        # 事件流水
        _evs = _st.get("events", [])[-4:]
        for _e in _evs:
            _txt = f"{_e.get('t', 0):.1f}s {_e.get('text', '')}"
            _srf = g.font_small.render(_txt, True, (180, 200, 180))
            self.screen.blit(_srf, (_bx + int(10 * _s), _ly)); _ly += int(15 * _s)

        # --- 时间轴 ---
        _th = int(26 * _s)
        _ty2 = sh - _th - int(10 * _s)
        _tw = sw - int(40 * _s)
        _tx = int(20 * _s)
        pygame.draw.rect(self.screen, (40, 38, 48), (_tx, _ty2, _tw, _th), border_radius=int(4 * _s))
        _ratio = _d.index / max(1, len(_d.frames) - 1)
        pygame.draw.rect(self.screen, (110, 200, 250),
                         (_tx, _ty2, int(_tw * _ratio), _th), border_radius=int(4 * _s))
        # 死亡事件标记
        try:
            for _e in _d.events:
                if _e.get("tag") == "death":
                    _er = min(1.0, _e.get("t", 0) / max(0.01, _d.duration))
                    _mx = _tx + int(_tw * _er)
                    pygame.draw.line(self.screen, (255, 80, 70),
                                     (_mx, _ty2 - int(4 * _s)), (_mx, _ty2 + _th + int(4 * _s)),
                                     max(1, int(2 * _s)))
        except Exception:
            pass

        # --- 操作提示 ---
        _hint = "WASD/拖动 移动视角 · 滚轮 缩放 · 空格 播放/暂停 · ←→ 逐帧 · 1-4 倍速 · F 跟随 · ESC 退出"
        _hs2 = g.font_small.render(_hint, True, (150, 155, 165))
        self.screen.blit(_hs2, (int(20 * _s), _ty2 - int(18 * _s)))
