# -*- coding: utf-8 -*-
"""NetLobbyUiMixin — v2.9.21 网络联机五个独立页面。

  NET_LOBBY       入口：创建房间 / 加入房间（不再双栏挤在一页）
  NET_HOST_SETUP  创建页：配置 + 全部网卡地址 + 一键复制
  NET_JOIN_SETUP  加入页：IP:端口 + 房间列表 + 陶瓦/异地 P2P 指引
  NET_SETUP       各自装备页：每人独立选武器/角色/昵称 + 准备
  NET_RESULT      结算页

所有页面统一「自绘 + 自消费全量 up 事件」，下拉复用 ui_pkg.DropdownGroup
（与同屏双人房间页同一套逻辑），不依赖 handle_events 的状态白名单。
"""
import pygame
from config import *
from ui_pkg.dropdown import DropdownGroup
from .draw_ui import _zs_copy_text, _zs_host_addr


class NetLobbyUiMixin:

    # ---------------- 通用小工具 ----------------
    def _nl_events(self, exclude_overlay=True):
        g = self.game
        _tes = getattr(g, 'touch_events', []) or []
        ups = [te for te in _tes if te.get('type') == 'up' and te.get('pos') is not None]
        moves = [te for te in _tes if te.get('type') == 'move' and te.get('pos') is not None]
        downs = [te for te in _tes if te.get('type') == 'down' and te.get('pos') is not None]
        _mp = pygame.mouse.get_pos()
        _mpr = pygame.mouse.get_pressed()
        if not ups and _mpr[0]:
            ups = [{'type': 'up', 'pos': _mp, 'id': -1}]
        if exclude_overlay:
            _ov = [r for r in getattr(g, '_dd_overlay_rects', []) or []
                   if hasattr(r, 'collidepoint')]
            ups = [te for te in ups
                   if not any(r.collidepoint(te['pos']) for r in _ov)]
        return ups, moves, downs

    def _nl_txt(self, t, x, y, font=None, color=None, center=False, s=None):
        s = s or self.game.scale
        _f = font or self.game.font_small
        _t = _f.render(str(t), True, color or LIGHT_GRAY)
        _r = (_t.get_rect(center=(int(x * s), int(y * s))) if center
              else _t.get_rect(topleft=(int(x * s), int(y * s))))
        self.screen.blit(_t, _r)
        return _t

    def _nl_rect(self, x, y, w, h, s=None):
        s = s or self.game.scale
        return pygame.Rect(int(x * s), int(y * s), int(w * s), int(h * s))

    def _nl_box(self, r, text, focused=False, color=None):
        pygame.draw.rect(self.screen, (30, 60, 50) if focused else (24, 28, 40),
                         r, border_radius=8)
        pygame.draw.rect(self.screen, (120, 220, 120) if focused else (70, 82, 102),
                         r, 2, border_radius=8)
        if text:
            _t = self.game.font.render(str(text), True, color or (232, 236, 245))
            self.screen.blit(_t, _t.get_rect(midleft=(r.x + int(12 * self.game.scale), r.centery)))

    def _nl_btn(self, r, text, fill, edge=None, font=None, ups=None, enabled=True):
        pygame.draw.rect(self.screen, fill if enabled else (48, 50, 58), r, border_radius=9)
        pygame.draw.rect(self.screen, (edge or GRAY) if enabled else (60, 62, 70),
                         r, 2, border_radius=9)
        _t = (font or self.game.font).render(text, True,
                                             WHITE if enabled else (120, 124, 136))
        self.screen.blit(_t, _t.get_rect(center=r.center))
        if not enabled:
            return False
        return any(r.collidepoint(te['pos']) for te in (ups or []))

    def _nl_hit(self, r, ups):
        return any(r.collidepoint(te['pos']) for te in ups)

    def _nl_blur_all(self, except_key=None):
        g = self.game
        for _k in ('net_room_focused', 'net_nick_focused', 'net_ip_focused',
                   'net_port_focused', 'net_setup_name_focused'):
            if _k != except_key and getattr(g, _k, False):
                setattr(g, _k, False)
                try: pygame.key.stop_text_input()
                except Exception: pass

    def _nl_focus(self, r, ups, key, all_ups=None):
        """点输入框聚焦；点其它区域失焦（用户明确要求的机制）。"""
        g = self.game
        _all = all_ups if all_ups is not None else ups
        if self._nl_hit(r, _all):
            self._nl_blur_all(except_key=key)
            setattr(g, key, True)
            try: pygame.key.start_text_input()
            except Exception: pass
            return True
        return False

    def _nl_header(self, title, sub):
        g = self.game
        s = g.scale
        self.screen.fill(VOID_BLACK)
        self._nl_txt(title, 640, 36, g.font_title, WHITE, center=True)
        self._nl_txt(sub, 640, 74, g.font_small, (150, 165, 185), center=True)

    # ---------------- ① 入口页 ----------------
    def _draw_net_lobby(self):
        g = self.game
        s = g.scale
        ups, _, _ = self._nl_events()
        self._nl_header("网络联机", "同一 WiFi 直接连；异地用陶瓦联机(EasyTier P2P)建虚拟局域网")
        # 两张大卡片
        cr = self._nl_rect(120, 140, 470, 330)
        jr = self._nl_rect(690, 140, 470, 330)
        for _r, _c, _t, _d in (
            (cr, (36, 72, 52), "创建房间", "本机作房主 · 房主权威\n把 IP:端口 发给队友"),
            (jr, (30, 58, 82), "加入房间", "填房主地址或点房间列表\n各自选自己的武器与角色")):
            pygame.draw.rect(self.screen, _c, _r, border_radius=16)
            pygame.draw.rect(self.screen, (95, 170, 130) if _r is cr else (90, 150, 210),
                             _r, 3, border_radius=16)
            self._nl_txt(_t, _r.centerx / s, 210, g.font_large, WHITE, center=True)
            for _i, _ln in enumerate(_d.split('\n')):
                self._nl_txt(_ln, _r.centerx / s, 285 + _i * 30,
                             g.font_small, (200, 215, 230), center=True)
        if self._nl_hit(cr, ups):
            g._net_lobby_create()
            return
        if self._nl_hit(jr, ups):
            g._net_lobby_join()
            return
        # 陶瓦联机指引
        self._nl_txt("跨局域网 / 异地联机（陶瓦联机 · Terracotta / EasyTier，房主权威 P2P）",
                     640, 510, g.font, GOLD, center=True)
        for _i, _ln in enumerate((
            "1. 双方安装 FCL 联机工具 / 方块盒子 / HMCL 的「陶瓦联机」，用邀请码进同一房间（Android 需允许 VPN 授权）",
            "2. 房主在下方「创建房间」页复制自己的虚拟网卡地址（10.x / 100.64.x / fd00:: 开头）",
            "3. 队友在「加入房间」页把「虚拟IP:端口」整串粘进地址框即可，无需公网 IP、无需端口映射")):
            self._nl_txt(_ln, 640, 548 + _i * 28, g.font_small, (175, 190, 210), center=True)
        br = self._nl_rect(490, 650, 300, 48)
        if self._nl_btn(br, "返回主菜单", (80, 50, 50), GRAY, ups=ups):
            try: g._net_stop_discovery()
            except Exception: pass
            g.state = GameState.MENU

    # ---------------- ② 创建房间页 ----------------
    def _draw_net_host_setup(self):
        g = self.game
        s = g.scale
        ups_all, moves, downs = self._nl_events(exclude_overlay=False)
        ups, _, _ = self._nl_events()
        self._nl_header("创建房间 · 房主", "监听全部网卡（含陶瓦虚拟网卡），把地址发给队友")
        try:
            from net import local_addresses
            _addrs = local_addresses()
        except Exception:
            _addrs = [g._get_local_ip()]
        _port = str(getattr(g, 'net_port_input', '') or '26000')
        _addr_main = "%s:%s" % (_addrs[0] if _addrs else g._get_local_ip(), _port)

        # 输入框
        r_room = self._nl_rect(40, 100, 560, 44)
        r_port = self._nl_rect(620, 100, 200, 44)
        r_nick = self._nl_rect(840, 100, 400, 44)
        self._nl_box(r_room, "房间名：" + str(getattr(g, 'net_room_name', '') or '幸存者房间'),
                     bool(getattr(g, 'net_room_focused', False)))
        self._nl_box(r_port, "端口：" + _port, bool(getattr(g, 'net_port_focused', False)))
        self._nl_box(r_nick, "你的昵称：" + str(getattr(g, 'net_nickname', '') or '房主'),
                     bool(getattr(g, 'net_nick_focused', False)))
        for _r, _k in ((r_room, 'net_room_focused'), (r_port, 'net_port_focused'),
                       (r_nick, 'net_nick_focused')):
            self._nl_focus(_r, ups, _k, all_ups=ups_all)
        if ups_all and not any(_r.collidepoint(te['pos'])
                               for te in ups_all for _r in (r_room, r_port, r_nick)):
            self._nl_blur_all()

        # 下拉配置（与同屏双人共用 DropdownGroup）
        try:
            from config import GameMode
            _modes = [GameMode.ENDLESS, GameMode.STORY, GameMode.TIMED]
            _mi = _modes.index(g.config.game_mode) if g.config.game_mode in _modes else 0
        except Exception:
            _modes, _mi = [], 0
        _mode_names = ["无尽生存", "故事模式", "争分夺秒"]
        _maps = ["沦陷的校园", "末日街区", "市中心", "郊区小镇", "核电站"]
        _mapi = int(getattr(g, 'room_map_idx', 0) or 0) % len(_maps)
        _diff_names = ["简单", "普通", "困难", "地狱"]   # 与 difficulty 表中文 key 一致
        _cur_diff = str(getattr(g.config, 'difficulty', '普通') or '普通')
        _di = _diff_names.index(_cur_diff) if _cur_diff in _diff_names else 1
        _ccn = max(2, min(4, int(getattr(g, 'coop_player_count', 2) or 2)))
        _pv = bool(getattr(g.config, 'pvp_enabled', False))
        _nt = int(getattr(g.config, 'pvp_teams', 2) or 2)

        ddg = DropdownGroup(self.screen, g.font, g, s,
                            g.scaled_width, g.scaled_height,
                            all_ups=ups_all, ups=ups_all, moves=moves, downs=downs,
                            state_key='net_dd_key')
        rows = [
            ("net_cnt", self._nl_rect(40, 168, 580, 42), "最大人数：%d 人" % _ccn,
             [("%d 人" % n, n) for n in (2, 3, 4)],
             lambda v: setattr(g, 'coop_player_count', v), _ccn - 2),
            ("net_pvp", self._nl_rect(40, 218, 580, 42),
             "玩法：" + ("合作 nPvE" if not _pv else "对战 PvPvE（%d 阵营）" % _nt),
             [("合作 nPvE", ("coop", 0))] +
             [("对战 PvPvE（%d 阵营）" % n, ("pvp", n)) for n in (2, 3, 4)],
             lambda v: (setattr(g.config, 'pvp_enabled', v[0] != 'coop'),
                        setattr(g.config, 'pvp_teams', v[1] or 2)), 0),
            ("net_mode", self._nl_rect(40, 268, 580, 42), "模式：" + _mode_names[_mi],
             [(n, i) for i, n in enumerate(_mode_names)],
             lambda v: setattr(g.config, 'game_mode', _modes[v]), _mi),
            ("net_map", self._nl_rect(40, 318, 580, 42), "地图：" + _maps[_mapi],
             [(m, i) for i, m in enumerate(_maps)],
             lambda v: setattr(g, 'room_map_idx', v), _mapi),
            ("net_diff", self._nl_rect(40, 368, 580, 42), "难度：" + _diff_names[_di],
             [(n, n) for n in _diff_names],
             lambda v: setattr(g.config, 'difficulty', v), _di),
        ]
        for _k, _r, _lab, _op, _set, _cur in rows:
            self._nl_box(_r, _lab, color=(225, 232, 245))
            ddg.row(_k, _r, _op, _set, _cur)

        # 右栏：全部网卡地址 + 一键复制
        self._nl_txt("本机地址（发给队友）", 700, 168, g.font, GOLD)
        _y = 200
        for _i, _ip in enumerate(_addrs[:5]):
            _tag = "  ← 虚拟网卡(陶瓦)" if (_ip.startswith('100.') or
                    _ip.startswith('10.126.') or _ip.startswith('fd') or
                    _ip.startswith('fc') or ':' in _ip) else ""
            _ar = self._nl_rect(660, _y, 560, 38)
            self._nl_box(_ar, "%s:%s%s" % (_ip, _port, _tag),
                         color=(170, 240, 190) if _tag else None)
            _cp = self._nl_rect(1150, _y + 2, 90, 34)
            if self._nl_btn(_cp, "复制", (40, 90, 65), (90, 170, 120),
                            g.font_small, ups):
                _zs_copy_text("%s:%s" % (_ip, _port))
                g.net_copy_hint = 2.5
            _y += 44
        self._nl_txt("陶瓦/异地：复制标「虚拟网卡」那一行；同 WiFi：复制 192.168.x 那一行",
                     640, 452, g.font_small, (165, 185, 210), center=True)
        _vl = "检测到虚拟网卡，可直接跨网联机" if any(
            (x.startswith('100.') or x.startswith('10.126.') or x.startswith('fd'))
            for x in _addrs) else "未检测到虚拟网卡（异地请先开陶瓦联机工具）"
        self._nl_txt(_vl, 640, 480, g.font_small,
                     (140, 220, 160) if '检测到' in _vl else (220, 180, 120), center=True)

        b_create = self._nl_rect(390, 560, 300, 56)
        b_back = self._nl_rect(730, 560, 180, 56)
        if self._nl_btn(b_create, "创建房间", (40, 130, 70), (90, 200, 130),
                        g.font, ups):
            self._nl_blur_all()
            try: g._net_start_host()
            except Exception as e: g.net_last_error = str(e)
        if self._nl_btn(b_back, "返回", (80, 50, 50), GRAY, ups=ups):
            g._net_lobby_back()
        if getattr(g, 'net_last_error', None):
            self._nl_txt(str(g.net_last_error)[:70], 640, 632,
                         g.font_small, CRIMSON, center=True)
        if getattr(g, 'net_copy_hint', 0) > 0:
            g.net_copy_hint = max(0.0, float(g.net_copy_hint) - 1 / 60)
            self._nl_txt("已复制地址，发给队友即可", 640, 660,
                         g.font_small, GOLD, center=True)
        ddg.finish()   # 选项永远画在最上层

    # ---------------- ③ 加入房间页 ----------------
    def _draw_net_join_setup(self):
        g = self.game
        s = g.scale
        ups, _, _ = self._nl_events()
        self._nl_header("加入房间", "填房主 IP:端口，或点下方自动发现的房间")
        r_nick = self._nl_rect(40, 108, 360, 44)
        r_ip = self._nl_rect(420, 108, 700, 44)
        r_port = self._nl_rect(1140, 108, 100, 44)
        self._nl_box(r_nick, "昵称：" + str(getattr(g, 'net_nickname', '') or '玩家'),
                     bool(getattr(g, 'net_nick_focused', False)))
        self._nl_box(r_ip, "房主地址：" + str(getattr(g, 'net_ip_input', '') or '例如 192.168.1.5:26000 / 10.126.0.7:26000'),
                     bool(getattr(g, 'net_ip_focused', False)))
        self._nl_box(r_port, str(getattr(g, 'net_port_input', '26000') or '26000'),
                     bool(getattr(g, 'net_port_focused', False)))
        for _r, _k in ((r_nick, 'net_nick_focused'), (r_ip, 'net_ip_focused'),
                       (r_port, 'net_port_focused')):
            self._nl_focus(_r, ups, _k)
        if ups and not any(_r.collidepoint(te['pos'])
                           for te in ups for _r in (r_nick, r_ip, r_port)):
            self._nl_blur_all()

        # 局域网房间列表
        try: g._net_start_discovery()
        except Exception: pass
        self._nl_txt("同一 WiFi 自动发现的房间（点一下直接加入）", 40, 180, g.font, GOLD)
        _rooms = []
        try: _rooms = g._net_room_list() or []
        except Exception: pass
        _ly = 212
        if not _rooms:
            self._nl_txt("暂未发现房间；可直接填上方地址，或让房主先创建房间",
                         40, _ly, g.font_small, (150, 165, 185))
        for _i, _rm in enumerate(_rooms[:5]):
            _rr = self._nl_rect(40, _ly + _i * 48, 1180, 42)
            _lab = "%s  ·  %s:%s  ·  房主 %s" % (
                _rm.get('room', '房间'), _rm.get('host_ip') or _rm.get('ip', ''),
                _rm.get('port', 26000), _rm.get('host', ''))
            self._nl_box(_rr, _lab)
            if self._nl_hit(_rr, ups):
                try: g._net_join_room(_rm)
                except Exception: pass
                return

        # 陶瓦 / 异地指引
        self._nl_txt("异地 / 跨局域网（陶瓦联机 · EasyTier P2P，无需公网 IP）",
                     640, 476, g.font, GOLD, center=True)
        for _i, _ln in enumerate((
            "双方用 FCL 联机工具 / 方块盒子 / HMCL 陶瓦联机进同一房间（Android 允许 VPN 授权）",
            "把房主创建页里标「虚拟网卡」的地址（10.x / 100.64.x / fd00::）整串粘进上方地址框",
            "支持 192.168.x.x、10.126.x.x:26000、[fd00::1]:26000 与主机名；UDP 广播在虚拟网卡上不保证可用")):
            self._nl_txt(_ln, 640, 508 + _i * 26, g.font_small,
                         (175, 190, 210), center=True)
        b_join = self._nl_rect(390, 596, 300, 54)
        b_back = self._nl_rect(730, 596, 180, 54)
        if self._nl_btn(b_join, "加入房间", (40, 100, 150), (90, 170, 230),
                        g.font, ups):
            self._nl_blur_all()
            try: g._net_join()
            except Exception as e: g.net_last_error = str(e)
        if self._nl_btn(b_back, "返回", (80, 50, 50), GRAY, ups=ups):
            g._net_lobby_back()
        if getattr(g, 'net_last_error', None):
            self._nl_txt(str(g.net_last_error)[:76], 640, 668,
                         g.font_small, CRIMSON, center=True)

    # ---------------- ④ 各自装备选择 ----------------
    def _draw_net_setup(self):
        g = self.game
        s = g.scale
        ups, moves, downs = self._nl_events()
        try:
            _idx = int(getattr(g.net_client, 'player_index', 0) or 0) if getattr(
                g, 'net_role', None) == 'client' else 0
        except Exception:
            _idx = 0
        _is_host = getattr(g, 'net_role', None) != 'client'
        self._nl_header("P%d · 选择你的装备" % (_idx + 1),
                        "两人各自独立选择，互不复用同屏双人的 P1→P2 顺序流程")
        if not getattr(g, 'net_weapon_list', None):
            try: g._net_init_my_loadout()
            except Exception: pass
        _wl = list(getattr(g, 'net_weapon_list', None) or [])
        _cl = list(getattr(g, 'net_char_list', None) or [])
        _mw = getattr(g, 'net_my_weapon', None)
        _mc = getattr(g, 'net_my_char', None)
        try:
            _widx = _wl.index(_mw) if _mw in _wl else 0
        except Exception:
            _widx = 0

        # 昵称
        r_name = self._nl_rect(40, 100, 560, 44)
        self._nl_box(r_name, "昵称：" + str(getattr(g, 'net_my_name', '') or ''),
                     bool(getattr(g, 'net_setup_name_focused', False)))
        self._nl_focus(r_name, ups, 'net_setup_name_focused')
        if ups and not r_name.collidepoint(ups[0]['pos']):
            pass   # 列表/按钮点击不强制失焦，避免手指移动误关输入法

        # 武器列表（左，可点击 + 简单滚动）
        self._nl_txt("武器", 40, 166, g.font, GOLD)
        _scroll = int(getattr(g, 'net_setup_scroll', 0) or 0)
        _vis = 12
        _wrects = []
        for _i in range(_vis):
            _gi = _scroll + _i
            if _gi >= len(_wl): break
            _r = self._nl_rect(40, 190 + _i * 34, 560, 30)
            _wrects.append((_r, _gi))
            _sel = _gi == _widx
            pygame.draw.rect(self.screen, (60, 130, 90) if _sel else (30, 34, 46),
                             _r, border_radius=6)
            try:
                from weapons import Weapon
                _nm = Weapon(_wl[_gi]).name
            except Exception:
                _nm = _wl[_gi].name if hasattr(_wl[_gi], 'name') else str(_wl[_gi])
            self._nl_txt(("● " if _sel else "  ") + _nm, 52, 194 + _i * 34,
                         g.font_small, WHITE if _sel else (195, 202, 216))
        for _r, _gi in _wrects:
            if self._nl_hit(_r, ups):
                g._net_setup_pick_weapon(_gi)
        # 滚轮
        for _te in getattr(g, 'touch_events', []) or []:
            if _te.get('type') == 'wheel':
                g.net_setup_scroll = max(0, min(max(0, len(_wl) - _vis),
                    _scroll - int(_te.get('dy', 0))))

        # 角色列表（右）
        self._nl_txt("角色", 660, 166, g.font, GOLD)
        for _i, _cn in enumerate(_cl[:12]):
            _r = self._nl_rect(660, 190 + _i * 34, 560, 30)
            _sel = _cn == _mc
            pygame.draw.rect(self.screen, (60, 110, 150) if _sel else (30, 34, 46),
                             _r, border_radius=6)
            self._nl_txt(("● " if _sel else "  ") + _cn, 672, 194 + _i * 34,
                         g.font_small, WHITE if _sel else (195, 202, 216))
            if self._nl_hit(_r, ups):
                g._net_setup_pick_char(_i)

        # 准备状态
        _ready = bool(getattr(g, 'net_my_ready', False))
        self._nl_txt("状态：" + ("已准备 ✓" if _ready else "未准备"),
                     40, 620, g.font, GREEN if _ready else (220, 180, 120))
        b_ready = self._nl_rect(240, 604, 220, 50)
        if self._nl_btn(b_ready, "取消准备" if _ready else "准 备",
                        (40, 130, 70) if not _ready else (110, 85, 40),
                        (90, 200, 130), g.font, ups):
            g._net_setup_confirm()
        if _is_host:
            try:
                _rmap = g._net_ready_map()
                self._nl_txt("   ".join("%s:%s" % (k, "✓" if v else "…")
                                        for k, v in sorted(_rmap.items())),
                             660, 620, g.font_small, CYAN)
            except Exception: pass
            b_go = self._nl_rect(930, 604, 290, 50)
            if self._nl_btn(b_go, "开始游戏", (40, 110, 60), (90, 200, 130),
                            g.font, ups):
                g._net_host_launch()
        b_leave = self._nl_rect(40, 664, 200, 42)
        if self._nl_btn(b_leave, "退出房间", (90, 45, 45), GRAY,
                        g.font_small, ups):
            g._net_leave()
        if getattr(g, 'net_last_error', None):
            self._nl_txt(str(g.net_last_error)[:72], 640, 672,
                         g.font_small, CRIMSON, center=True)

    # ---------------- ⑤ 结算页 ----------------
    def _draw_net_result(self):
        g = self.game
        ups, _, _ = self._nl_events()
        self._nl_header("对局结束", "房主权威结算")
        _r = getattr(g, 'net_result', None) or {}
        if getattr(g, 'net_role', None) == 'client':
            try: _r = (g.net_client.get_snapshot() or {}).get('result') or _r
            except Exception: pass
        _win = bool(_r.get('victory'))
        self._nl_txt("胜利" if _win else "全员阵亡", 640, 200,
                     g.font_title, GOLD if _win else CRIMSON, center=True)
        for _i, (_k, _v) in enumerate((
            ("波数", _r.get('wave', 0)), ("击杀", _r.get('kills', 0)),
            ("存活时间", "%.1fs" % float(_r.get('time', 0) or 0)),
            ("房间", _r.get('room', '')))):
            self._nl_txt("%s：%s" % (_k, _v), 640, 290 + _i * 42,
                         g.font, LIGHT_GRAY, center=True)
        b = self._nl_rect(490, 540, 300, 54)
        if self._nl_btn(b, "返回主菜单", (50, 90, 130), (100, 170, 220),
                        g.font, ups):
            g._net_leave()
            g.state = GameState.MENU
