# -*- coding: utf-8 -*-
"""MapEditorUiMixin — v2.9.21 地图编辑器 GUI 绘制 + 主菜单入口。"""
import pygame
from config import *


class MapEditorUiMixin:

    def _me_ui_events(self):
        g = self.game
        _tes = getattr(g, 'touch_events', []) or []
        ups = [te['pos'] for te in _tes if te.get('type') == 'up' and te.get('pos')]
        moves = [te['pos'] for te in _tes if te.get('type') == 'move' and te.get('pos')]
        downs = [te['pos'] for te in _tes if te.get('type') == 'down' and te.get('pos')]
        _mp, _mpr = pygame.mouse.get_pos(), pygame.mouse.get_pressed()
        if not ups and _mpr[0]: ups = [_mp]
        if _mpr[0]: downs = downs or [_mp]
        if _mpr[2]: moves = [('erase', _mp)]
        return ups, downs, moves

    def _me_btn(self, r, text, fill, ups, font=None, selected=False):
        pygame.draw.rect(self.screen, fill, r, border_radius=8)
        pygame.draw.rect(self.screen, GOLD if selected else (80, 92, 110),
                         r, 2 if not selected else 3, border_radius=8)
        _t = (font or self.game.font_small).render(text, True, WHITE)
        self.screen.blit(_t, _t.get_rect(center=r.center))
        return any(r.collidepoint(p) for p in ups)

    def _draw_map_editor_entry(self):
        """主菜单右下角入口（不改动原菜单按钮索引）。"""
        g = self.game
        s = g.scale
        _r = pygame.Rect(int(g.scaled_width - 210 * s), int(g.scaled_height - 58 * s),
                         int(190 * s), int(44 * s))
        ups, _, _ = self._me_ui_events()
        if self._me_btn(_r, "地图编辑器 (F5)", (44, 62, 82), ups,
                        self.game.font_small):
            g._me_enter()

    def _draw_map_editor(self):
        g = self.game
        s = g.scale
        sw, sh = g.scaled_width, g.scaled_height
        self.screen.fill((16, 18, 24))
        ups, downs, moves = self._me_ui_events()
        if not hasattr(g, 'me_obstacles'):
            g._me_enter()
        _z = g.me_zoom
        _cx, _cy = g.me_cam_x, g.me_cam_y

        # 标题
        t = g.font_title.render("地图编辑器 · 障碍物与材质", True, WHITE)
        self.screen.blit(t, t.get_rect(center=(sw // 2, int(28 * s))))

        # 网格
        _step = int(g.me_grid * s * _z)
        _step = max(8, _step)
        _ox = int((-_cx * _z * s) % _step)
        _oy = int((-_cy * _z * s) % _step)
        for _x in range(_ox, sw - int(250 * s), _step):
            pygame.draw.line(self.screen, (34, 40, 52), (_x, int(56 * s)), (_x, sh))
        for _y in range(_oy, sh, _step):
            pygame.draw.line(self.screen, (34, 40, 52), (0, _y), (sw - int(250 * s), _y))
        # 障碍
        for _o in g.me_obstacles:
            _r = _o['rect']
            _sr = pygame.Rect(int((_r.x - _cx) * _z * s), int((_r.y - _cy) * _z * s),
                              int(_r.w * _z * s), int(_r.h * _z * s))
            if _sr.right < 0 or _sr.bottom < int(56 * s) or _sr.x > sw - int(250 * s):
                continue
            pygame.draw.rect(self.screen, _o.get('color', (110, 100, 95)), _sr, border_radius=3)
            pygame.draw.rect(self.screen, (20, 22, 28), _sr, 2, border_radius=3)
            # 材质标记（挡视线用斜纹）
            try:
                from world import GameWorld
                if GameWorld.blocks_sight(_o):
                    pygame.draw.line(self.screen, (255, 255, 255, 60),
                                     _sr.topleft, _sr.bottomright, 1)
            except Exception:
                pass

        # 绘制 / 擦除
        _canvas = pygame.Rect(0, int(56 * s), sw - int(250 * s), sh - int(56 * s))
        for _p in downs:
            if isinstance(_p, tuple) and len(_p) == 2 and _canvas.collidepoint(_p):
                g._me_place(_p[0], _p[1], erase=False)
        for _m in moves:
            if isinstance(_m, tuple) and len(_m) == 2 and _m[0] == 'erase':
                _p = _m[1]
                if _canvas.collidepoint(_p):
                    g._me_place(_p[0], _p[1], erase=True)
            elif isinstance(_m, tuple) and len(_m) == 2 and _canvas.collidepoint(_m):
                # 触控拖动连续放置
                g._me_place(_m[0], _m[1], erase=False)

        # 右侧工具栏
        _tx = sw - int(240 * s)
        pygame.draw.rect(self.screen, (22, 26, 36),
                         (_tx, int(56 * s), int(240 * s), sh - int(56 * s)))
        self.screen.blit(g.font.render("障碍物类型", True, GOLD),
                         (_tx + int(12 * s), int(64 * s)))
        _ty = int(96 * s)
        for _i, (_key, _name) in enumerate(g._me_types()):
            _r = pygame.Rect(_tx + int(10 * s), _ty + _i * int(34 * s),
                             int(220 * s), int(30 * s))
            _sel = g.me_type == _key
            if self._me_btn(_r, "%s · %s" % (_name, g._me_material(_key)),
                            (52, 82, 62) if _sel else (34, 40, 54), ups,
                            g.font_small, _sel):
                g.me_type = _key
        _ty2 = _ty + len(g._me_types()) * int(34 * s) + int(8 * s)
        # 当前规则说明
        for _i, _ln in enumerate(("当前：" + g.me_type,
                                 g._me_rule_text(g.me_type),
                                 "旋转 %d°" % g.me_rot)):
            _t = g.font_small.render(_ln[:34], True, (180, 200, 220))
            self.screen.blit(_t, (_tx + int(12 * s), _ty2 + _i * int(22 * s)))
        _ty3 = _ty2 + int(76 * s)
        _bw = int(105 * s)
        for _i, (_lab, _act) in enumerate((
            ("旋转", lambda: setattr(g, 'me_rot', (g.me_rot + 45) % 180)),
            ("清空", lambda: g._me_clear()),
            ("保存", lambda: g._me_save('custom')),
            ("载入", lambda: g._me_load('custom')),
            ("试玩", lambda: g._me_playtest()),
            ("视野", lambda: g._me_toggle_vision()))):
            _r = pygame.Rect(_tx + int(10 * s) + (_i % 2) * (_bw + int(10 * s)),
                             _ty3 + (_i // 2) * int(40 * s), _bw, int(34 * s))
            if self._me_btn(_r, _lab, (48, 70, 100), ups, g.font_small):
                _act()
        _br = pygame.Rect(_tx + int(10 * s), sh - int(52 * s),
                          int(220 * s), int(40 * s))
        if self._me_btn(_br, "返回主菜单", (90, 50, 50), ups, g.font_small):
            g.state = GameState.MENU
        if getattr(g, 'me_tip', ''):
            _t = g.font_small.render(str(g.me_tip)[:52], True, GOLD)
            self.screen.blit(_t, (int(12 * s), sh - int(30 * s)))
        self.screen.blit(g.font_small.render(
            "左键/触控拖动放置 · 右键擦除 · F5 退出 · 障碍共 %d 个" % len(g.me_obstacles),
            True, (140, 155, 175)), (int(12 * s), sh - int(54 * s)))
