# -*- coding: utf-8 -*-
"""v2.8.8 单开的信息展示页：武器 / 地图 / 角色

统一结构：
    ┌─────────────────────────┐
    │ 标题                     │
    ├──────────┬──────────────┤
    │ 左侧列表  │ 右侧详情区     │
    │          │ 数值 / 机制    │
    │          │ 背景故事       │
    │          │ 升级对比       │
    ├──────────┴──────────────┤
    │ [确认]  [返回]           │
    └─────────────────────────┘

支持触控滑动滚动（与图鉴一致的手感）。
"""
import pygame

from . import Scene

try:
    from config import WHITE, LIGHT_GRAY, GRAY, DARK_GRAY, BLACK, GOLD, CYAN, GREEN, ORANGE, RED
except Exception:                                    # pragma: no cover
    WHITE = (255, 255, 255)
    LIGHT_GRAY = (200, 200, 200)
    GRAY = (128, 128, 128)
    DARK_GRAY = (60, 60, 60)
    BLACK = (0, 0, 0)
    GOLD = (255, 215, 0)
    CYAN = (0, 220, 220)
    GREEN = (60, 200, 90)
    ORANGE = (255, 160, 60)
    RED = (220, 60, 60)

BASE_W, BASE_H = 1280, 720
LIST_W = 300


class InfoPage(Scene):
    """信息展示页基类：左列表 + 右详情 + 底部按钮"""

    ITEM_H = 46

    def __init__(self, game, key=None, title="", back_to=None, items=None):
        Scene.__init__(self, game, key=key, title=title, back_to=back_to)
        self.items = list(items or [])
        self.index = 0
        self.list_scroll = 0
        self.detail_scroll = 0

    # ---------------- 数据 ----------------
    def set_items(self, items):
        self.items = list(items or [])
        self.index = 0
        self.list_scroll = 0
        self.detail_scroll = 0

    @property
    def current_item(self):
        if not self.items:
            return None
        if 0 <= self.index < len(self.items):
            return self.items[self.index]
        return None

    def sections(self, item):
        """详情分区：返回 [(标题, [(键, 值), ...]), ...]

        子类重写以填充数值 / 机制 / 背景故事 / 升级对比。
        """
        return []

    # ---------------- 交互 ----------------
    def handle_event(self, event):
        try:
            if event.type == pygame.MOUSEWHEEL:
                self.detail_scroll = max(0, self.detail_scroll - int(event.y * 24))
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                _g = self.game
                _s = getattr(_g, 'scale', 1.0) or 1.0
                _mx, _my = event.pos
                # 左侧列表点击选择
                _lw = int(LIST_W * _s)
                if _mx <= _lw:
                    _top = int(120 * _s) - self.list_scroll
                    for _i in range(len(self.items)):
                        _y0 = _top + _i * int(self.ITEM_H * _s)
                        _y1 = _y0 + int(self.ITEM_H * _s)
                        if _y0 <= _my <= _y1:
                            self.index = _i
                            self.detail_scroll = 0
                            return True
                return True
            if event.type == pygame.FINGERMOTION:
                _dy = getattr(event, 'dy', 0) or 0
                if _dy:
                    _g = self.game
                    _lw = int(LIST_W * (getattr(_g, 'scale', 1.0) or 1.0))
                    if getattr(event, 'x', 0) <= _lw:
                        self.list_scroll = max(0, self.list_scroll - int(_dy * 1.4))
                    else:
                        self.detail_scroll = max(0, self.detail_scroll - int(_dy * 1.4))
                return True
        except Exception:
            pass
        return False

    # ---------------- 绘制 ----------------
    def draw(self, renderer):
        screen = renderer.screen
        g = self.game
        s = getattr(g, 'scale', 1.0) or 1.0
        sw, sh = screen.get_size()
        screen.fill((18, 18, 24))

        # 标题
        try:
            _t = g.font_large.render(self.title, True, GOLD)
            screen.blit(_t, (int(24 * s), int(24 * s)))
        except Exception:
            pass

        # ---- 左侧列表 ----
        _lw = int(LIST_W * s)
        pygame.draw.rect(screen, (28, 28, 36), (0, int(100 * s), _lw, sh - int(100 * s)))
        _top = int(110 * s)
        for _i, _it in enumerate(self.items):
            _y = _top + _i * int(self.ITEM_H * s) - self.list_scroll
            if _y < int(100 * s) or _y > sh:
                continue
            _sel = (_i == self.index)
            _col = (52, 62, 82) if _sel else (34, 34, 44)
            pygame.draw.rect(screen, _col, (int(8 * s), _y, _lw - int(16 * s),
                                            int(self.ITEM_H * s) - int(4 * s)),
                             border_radius=int(6 * s))
            if _sel:
                pygame.draw.rect(screen, GOLD, (int(8 * s), _y, _lw - int(16 * s),
                                                int(self.ITEM_H * s) - int(4 * s)),
                                 max(1, int(2 * s)), border_radius=int(6 * s))
            try:
                _nm = str(self.item_name(_it))[:10]
                _fs = (g.font if _sel else g.font_small)
                _ls = _fs.render(_nm, True, WHITE if _sel else LIGHT_GRAY)
                screen.blit(_ls, (int(20 * s), _y + int(10 * s)))
            except Exception:
                pass
        pygame.draw.line(screen, GRAY, (_lw, int(100 * s)), (_lw, sh), max(1, int(s)))

        # ---- 右侧详情 ----
        _it = self.current_item
        _x = _lw + int(24 * s)
        _y = int(110 * s) - self.detail_scroll
        if _it is None:
            try:
                _et = g.font.render("暂无内容", True, GRAY)
                screen.blit(_et, (_x, _y))
            except Exception:
                pass
            self._draw_footer(renderer, s, sw, sh)
            return

        # 名称 + 稀有度
        try:
            _nt = g.font_large.render(str(self.item_name(_it)), True, WHITE)
            screen.blit(_nt, (_x, _y))
            _y += int(46 * s)
        except Exception:
            pass

        for _sec_title, _rows in self.sections(_it):
            try:
                _st = g.font.render(str(_sec_title), True, CYAN)
                screen.blit(_st, (_x, _y))
                _y += int(32 * s)
                pygame.draw.line(screen, DARK_GRAY, (_x, _y),
                                 (sw - int(24 * s), _y), max(1, int(s)))
                _y += int(8 * s)
            except Exception:
                pass
            for _k, _v in _rows:
                if _y > sh - int(90 * s):
                    break
                try:
                    _line = f"{_k}：{_v}"
                    # 长文本（背景故事）自动换行
                    _maxw = sw - _x - int(40 * s)
                    _words = str(_line)
                    _buf = ""
                    _lines = []
                    for _ch in _words:
                        _test = _buf + _ch
                        if g.font_small.size(_test)[0] > _maxw:
                            _lines.append(_buf)
                            _buf = _ch
                        else:
                            _buf = _test
                    if _buf:
                        _lines.append(_buf)
                    for _ln in _lines:
                        _ls = g.font_small.render(_ln, True, LIGHT_GRAY)
                        screen.blit(_ls, (_x + int(12 * s), _y))
                        _y += int(24 * s)
                except Exception:
                    break
            _y += int(14 * s)

        self._draw_footer(renderer, s, sw, sh)

    def item_name(self, item):
        if isinstance(item, dict):
            return item.get("name", "?")
        return str(getattr(item, "name", item))

    def _draw_footer(self, renderer, s, sw, sh):
        """底部按钮区（确认 / 返回）"""
        g = self.game
        try:
            _hint = g.font_small.render("滚轮或手指滑动可滚动内容", True, DARK_GRAY)
            screen = renderer.screen
            screen.blit(_hint, (sw - _hint.get_width() - int(24 * s), sh - int(36 * s)))
        except Exception:
            pass
        self.draw_buttons(renderer.screen, getattr(g, 'font', None),
                          getattr(g, 'scale', 1.0))


class WeaponSelectPage(InfoPage):
    """武器选择页：数值 + 机制 + 背景故事 + 升级对比"""

    key = "weapon_select"
    title = "选择武器"

    def sections(self, item):
        _d = item if isinstance(item, dict) else {}
        _out = []
        _stats = [
            ("基础伤害", _d.get("damage", "-")),
            ("对玩家伤害", _d.get("damage_vs_player", _d.get("damage", "-"))),
            ("射速", _d.get("fire_rate", "-")),
            ("射程", _d.get("range", "-")),
            ("弹速", _d.get("speed", "-")),
            ("散布", _d.get("spread", "-")),
            ("穿透", _d.get("pierce", "-")),
            ("弹匣", _d.get("ammo", "-")),
            ("换弹", _d.get("reload", "-")),
        ]
        _out.append(("数值", [(k, v) for k, v in _stats if v != "-"]))
        if _d.get("desc"):
            _out.append(("机制", [("说明", _d["desc"])]))
        if _d.get("story"):
            _out.append(("背景故事", [("", _d["story"])]))
        _up = _d.get("upgrade")
        if _up:
            _out.append(("升级对比", [(k, v) for k, v in _up]))
        return _out


class MapSelectPage(InfoPage):
    """地图选择页：每张地图的信息"""

    key = "map_select"
    title = "选择地图"

    def sections(self, item):
        _d = item if isinstance(item, dict) else {}
        _out = []
        _info = [
            ("章节", _d.get("chapter", "-")),
            ("难度系数", _d.get("difficulty_scale", "-")),
            ("推荐等级", _d.get("recommend", "-")),
        ]
        _out.append(("信息", [(k, v) for k, v in _info if v != "-"]))
        if _d.get("description"):
            _out.append(("背景", [("", _d["description"])]))
        if _d.get("features"):
            _out.append(("地图特性", [(str(i + 1), f) for i, f in enumerate(_d["features"])]))
        return _out


class CharacterSelectPage(InfoPage):
    """角色选择页：词条 + 背景 + 升级对比"""

    key = "character_select"
    title = "选择角色"

    def sections(self, item):
        _d = item if isinstance(item, dict) else {}
        _out = []
        _perks = _d.get("perks") or []
        if _perks:
            _out.append(("角色词条", [(p.get("name", "?"), p.get("desc", ""))
                                      for p in _perks]))
        _stats = [
            ("生命", _d.get("hp", "-")),
            ("移速", _d.get("speed", "-")),
            ("伤害", _d.get("damage", "-")),
        ]
        _out.append(("属性", [(k, v) for k, v in _stats if v != "-"]))
        if _d.get("story"):
            _out.append(("背景故事", [("", _d["story"])]))
        _up = _d.get("upgrade")
        if _up:
            _out.append(("升级对比", [(k, v) for k, v in _up]))
        return _out
