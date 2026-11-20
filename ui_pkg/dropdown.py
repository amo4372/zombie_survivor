# -*- coding: utf-8 -*-
"""DropdownGroup — 全项目统一的下拉选择控件（v2.9.21）。

这是同屏双人房间页 `_handle_dd` / `_dd_pending` 那套交互的**抽取版**：
  * 模态：一次只展开一个，选项统一在页面末尾绘制（永远在最上层）
  * 支持滚轮、触控拖动滚动、按下未移动=点击选中（拖动中不误选）
  * 精确 overlay：把「下拉行 + 选项列表」的矩形缓存回 game，页面按钮
    只排除落在这些区域的 up，既不误触也不会把下拉自己点死
  * 点击区域外自动收起

同屏双人房间页与网络创建页现在共用这一份实现，避免两套逻辑分叉导致的
「网络下滑栏点不动」「显示内容与实际值不符」。
"""
import pygame


class DropdownGroup:
    def __init__(self, screen, font, game, scale, sw, sh,
                 all_ups, ups, moves, downs,
                 state_key='room_dropdown', overlay_key='_dd_overlay_rects',
                 item_draw=None):
        self.screen = screen
        self.font = font
        self.game = game
        self.scale = float(scale or 1.0)
        self.sw = int(sw)
        self.sh = int(sh)
        self.all_ups = [te for te in (all_ups or []) if te.get('pos') is not None]
        self.ups = [te for te in (ups or []) if te.get('pos') is not None]
        self.moves = [te for te in (moves or []) if te.get('pos') is not None]
        self.downs = [te for te in (downs or []) if te.get('pos') is not None]
        self.state_key = state_key
        self.overlay_key = overlay_key
        self.item_draw = item_draw or self._default_item
        self.pending = []

    # ---------- 行 ----------
    def row(self, key, rect, options, setter, current=0):
        """画行由调用方负责；这里只处理点击与收集。返回 True 表示已展开。"""
        _open = getattr(self.game, self.state_key, None)
        if _open == key:
            self.pending.append((key, rect, list(options), setter, int(current or 0)))
            return True
        if any(rect.collidepoint(te['pos']) for te in self.all_ups):
            setattr(self.game, self.state_key, key)
            self.pending.append((key, rect, list(options), setter, int(current or 0)))
            return True
        return False

    def _default_item(self, rect, text, selected=False):
        _c = (60, 130, 90) if selected else (38, 44, 58)
        pygame.draw.rect(self.screen, _c, rect, border_radius=8)
        pygame.draw.rect(self.screen, (90, 120, 150) if selected else (55, 62, 80),
                         rect, 2, border_radius=8)
        _t = self.font.render(str(text), True, (245, 245, 245))
        self.screen.blit(_t, _t.get_rect(midleft=(rect.x + int(12 * self.scale), rect.centery)))

    # ---------- 末尾统一绘制展开的选项 ----------
    def finish(self):
        g = self.game
        s = self.scale
        _sc = getattr(g, 'dd_scroll', None)
        if _sc is None:
            _sc = {}
            g.dd_scroll = _sc
        _ih = int(42 * s)
        _gap_i = int(3 * s)
        _ov = []
        if self.pending:
            for _dkey, _drect, _dopts, _dset, _dcur in self.pending:
                _max_rows = max(1, int((self.sh - _drect.bottom - int(20 * s)) // (_ih + _gap_i)))
                _max_rows = min(_max_rows, len(_dopts)) or 1
                _sval = int(_sc.get(_dkey, 0) or 0)
                _smax = max(0, len(_dopts) - _max_rows)
                _sval = int(max(0, min(_smax, _sval)))
                _list_w = _drect.width
                _list_h = _max_rows * (_ih + _gap_i)
                _bar_w = int(9 * s)
                _bar_x = _drect.x + _list_w - _bar_w - int(3 * s)
                _list_rect = pygame.Rect(_drect.x, _drect.bottom, _list_w, _list_h)
                # 滚轮
                for _te in getattr(g, 'touch_events', []):
                    if _te.get('type') == 'wheel':
                        _sval = int(max(0, min(_smax, int(_sval) - int(_te.get('dy', 0)))))
                # 触控拖动
                _bar_h = max(int(22 * s), int(_list_h * _max_rows / max(1, len(_dopts)))) if _smax > 0 else 0
                if getattr(g, 'dd_drag', None) == _dkey:
                    _last = getattr(g, 'dd_drag_y', None)
                    _start = float(getattr(g, 'dd_drag_start', _last) or _last or 0)
                    _fy = float(self.moves[-1]['pos'][1]) if self.moves else float(_last or 0)
                    if _smax > 0 and abs(_fy - _start) >= max(4.0, 5.0 * s):
                        _ratio = (_fy - _drect.bottom) / float(_list_h)
                        _sval = int(max(0, min(_smax,
                            round(max(0.0, min(1.0, _ratio)) * _smax))))
                        g.dd_drag_moved = True
                    if self.moves:
                        g.dd_drag_y = int(self.moves[-1]['pos'][1])
                for _te in self.downs:
                    if _list_rect.collidepoint(_te['pos']):
                        g.dd_drag = _dkey
                        g.dd_drag_y = _te['pos'][1]
                        g.dd_drag_start = _te['pos'][1]
                        g.dd_drag_moved = False
                if getattr(g, 'dd_drag', None) == _dkey:
                    for _te in self.ups:
                        g.dd_drag = None
                        break
                # 选项（裁剪）
                _clip = pygame.Rect(_drect.x, _drect.bottom, _list_w, _list_h)
                _clip = _clip.clip(pygame.Rect(0, 0, self.sw, self.sh))
                _old = self.screen.get_clip()
                self.screen.set_clip(_clip)
                for _oi in range(_max_rows):
                    _gi = int(_sval) + _oi
                    if _gi >= len(_dopts):
                        break
                    _opt, _val = _dopts[_gi]
                    _or = pygame.Rect(_drect.x, _drect.bottom + _oi * (_ih + _gap_i),
                                      _list_w - _bar_w - int(4 * s), _ih)
                    self.item_draw(_or, _opt, _gi == _dcur)
                    if (not getattr(g, 'dd_drag_moved', False)
                            and any(_or.collidepoint(te['pos']) for te in self.all_ups)):
                        try:
                            _dset(_val)
                        except Exception:
                            pass
                        setattr(g, self.state_key, None)
                        g.dd_drag = None
                        g.dd_drag_moved = False
                self.screen.set_clip(_old)
                if _smax > 0:
                    _bar_y = _drect.bottom + int((_list_h - _bar_h) * (_sval / _smax))
                    pygame.draw.rect(self.screen, (70, 78, 96),
                                     (_bar_x, _drect.bottom, _bar_w, _list_h), border_radius=4)
                    pygame.draw.rect(self.screen, (150, 170, 200),
                                     (_bar_x, _bar_y, _bar_w, _bar_h), border_radius=4)
                _sc[_dkey] = int(_sval)
                # 缓存覆盖区（下一帧页面按钮据此精确排除）
                _ov.append(_drect)
                _ov.append(pygame.Rect(_drect.x, _drect.bottom, _drect.width, _list_h))
            # v2.9.21：只有本次确实有展开项（_ov 非空）才做「点外部收起」。
            # 否则残留的脏 state_key + 空 _ov 会把刚点开的下拉立刻清成 None。
            if self.all_ups and getattr(g, self.state_key, None) and _ov:
                if not any(_r.collidepoint(te['pos'])
                           for te in self.all_ups for _r in _ov):
                    setattr(g, self.state_key, None)
                    g.dd_drag = None
                    _ov = []
        setattr(g, self.overlay_key, _ov)
        return _ov
