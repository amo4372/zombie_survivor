# -*- coding: utf-8 -*-
"""NetLobbyMixin — v2.9.21 网络联机大厅 / 各自装备选择 / 阶段同步。

设计要点（对应本轮反馈）：
  * 创建房间与加入房间是**两个独立页面**，不再是拥挤的双栏页；
  * 房主与每个客户端都在自己的 NET_SETUP 页里**各自**选武器 / 角色 / 昵称，
    不再复用同屏双人的「P1 选完 → P2 选」顺序流程；
  * 房主权威：客户端只上报 loadout（武器/角色/名字）+ ready，房主汇总后
    统一 start_game() 并按每人配置为 P2/P3/P4 建实体；
  * phase = wait / setup / playing / over 通过快照广播，客户端任何状态下
    都能被推进，彻底修掉「只有 P1 能动，B 客户端没画面」。
"""
from config import GameState


class NetLobbyMixin:

    # ---------- 页面导航 ----------
    def _net_lobby_create(self):
        self.net_role = None
        self.net_last_error = None
        self.net_room_focused = False
        self.net_nick_focused = False
        self.net_ip_focused = False
        self.net_port_focused = False
        self.state = GameState.NET_HOST_SETUP

    def _net_lobby_join(self):
        self.net_role = None
        self.net_last_error = None
        self.net_ip_focused = False
        self.net_port_focused = False
        self.net_nick_focused = False
        self.state = GameState.NET_JOIN_SETUP
        try:
            self._net_start_discovery()
        except Exception:
            pass

    def _net_lobby_back(self):
        try:
            self._net_stop_discovery()
        except Exception:
            pass
        self.state = GameState.NET_LOBBY

    # ---------- 阶段 ----------
    def _net_current_phase(self):
        """房主按自身状态推导阶段；客户端以快照里的 phase 为准。"""
        _s = self.state
        if _s in (GameState.GAME_OVER, GameState.VICTORY, GameState.ENDING,
                  GameState.DEATH_DETAIL, GameState.DYING):
            return "over"
        if _s == GameState.NET_SETUP:
            return "setup"
        if _s in (GameState.PLAYING, GameState.PAUSED, GameState.DIALOGUE,
                  GameState.SKILL_SELECT):
            return "playing"
        return "wait"

    def _net_result_data(self):
        try:
            return {
                "victory": self.state in (GameState.VICTORY, GameState.ENDING),
                "wave": int(getattr(self, 'wave_count', 0) or 0),
                "kills": int(getattr(getattr(self, 'session', None), 'kills', 0) or 0),
                "time": round(float(getattr(self, 'survival_time', 0) or 0), 1),
                "room": getattr(getattr(self, 'net_host', None), 'room_name', '') or '',
            }
        except Exception:
            return {"victory": False, "wave": 0, "kills": 0, "time": 0.0, "room": ''}

    def _net_send_snapshot_now(self):
        """阶段切换时绕过 20Hz 节流立刻发一帧，避免客户端晚 50ms~无穷。"""
        try:
            self.net_snap_timer = 0.0
            self._net_send_snapshot()
        except Exception:
            pass

    # ---------- 各自装备选择 ----------
    def _net_init_my_loadout(self):
        """初始化本地（P1=房主 / Pn=客户端）的装备选择，不碰对方。"""
        try:
            from config import WeaponType, CHARACTERS
            _throw = {WeaponType.GRENADE, WeaponType.MOLOTOV, WeaponType.SMOKE_GRENADE}
            self.net_weapon_list = [w for w in WeaponType if w not in _throw]
            self.net_char_list = list(CHARACTERS.keys())
        except Exception:
            self.net_weapon_list, self.net_char_list = [], []
        if not getattr(self, 'net_my_weapon', None):
            self.net_my_weapon = (self.net_weapon_list[0]
                                  if self.net_weapon_list else None)
        if not getattr(self, 'net_my_char', None):
            self.net_my_char = (self.net_char_list[0]
                                if self.net_char_list else '幸存者')
        if not getattr(self, 'net_my_name', None):
            self.net_my_name = (getattr(self, 'net_nickname', '')
                                or ('房主' if getattr(self, 'net_role', None) == 'host' else '玩家'))
        self.net_my_ready = False
        self.net_setup_scroll = 0

    def _net_setup_pick_weapon(self, idx):
        _l = getattr(self, 'net_weapon_list', None) or []
        if 0 <= idx < len(_l):
            self.net_my_weapon = _l[idx]
            self.net_my_ready = False

    def _net_setup_pick_char(self, idx):
        _l = getattr(self, 'net_char_list', None) or []
        if 0 <= idx < len(_l):
            self.net_my_char = _l[idx]
            self.net_my_ready = False

    def _net_setup_confirm(self):
        """各自确认。客户端只上报 loadout，房主记录自己的。"""
        self.net_my_ready = not bool(getattr(self, 'net_my_ready', False))
        _w = getattr(self, 'net_my_weapon', None)
        _ws = _w.name if hasattr(_w, 'name') else str(_w or '')
        if getattr(self, 'net_role', None) == 'client' and getattr(self, 'net_client', None):
            self.net_client.send_loadout(
                _ws, str(getattr(self, 'net_my_char', '') or ''),
                str(getattr(self, 'net_my_name', '') or ''),
                ready=bool(self.net_my_ready))
        else:
            # 房主把自己的 loadout 存在 index 0
            self.net_host_loadout = {
                "weapon": _ws, "char": str(getattr(self, 'net_my_char', '') or ''),
                "name": str(getattr(self, 'net_my_name', '') or '')}
        try:
            self._net_send_snapshot_now()
        except Exception:
            pass

    def _net_ready_map(self):
        """给房主页面显示：{P1: 我, P2..: 客户端} 的准备状态。"""
        out = {"P1": bool(getattr(self, 'net_my_ready', False))}
        _h = getattr(self, 'net_host', None)
        if _h is not None:
            try:
                for _i in sorted(_h.clients.keys()):
                    out["P%d" % (_i + 1)] = bool(_h.ready.get(_i, False))
            except Exception:
                pass
        return out

    def _net_host_launch(self):
        """房主点开始游戏：等所有人 ready → 按各自 loadout 建实体 → 广播 playing。"""
        _h = getattr(self, 'net_host', None)
        if _h is None:
            return False
        if _h.connected and not _h.all_ready():
            self.net_last_error = "还有玩家没点「准备」，等大家都准备好再开始"
            return False
        if not bool(getattr(self, 'net_my_ready', False)):
            self.net_last_error = "房主自己也要先点「准备」"
            return False
        try:
            from config import WeaponType
            _los = {0: getattr(self, 'net_host_loadout', None) or {
                "weapon": (self.net_my_weapon.name if hasattr(self.net_my_weapon, 'name')
                           else str(self.net_my_weapon or '')),
                "char": str(getattr(self, 'net_my_char', '') or ''),
                "name": str(getattr(self, 'net_my_name', '') or '')}}
            try:
                _los.update({int(k): v for k, v in _h.get_loadouts().items()})
            except Exception:
                pass

            def _wt(v):
                _s = str(v or '')
                try:
                    return WeaponType[_s] if _s in WeaponType.__members__ else None
                except Exception:
                    return None

            self.selected_weapon = _wt((_los.get(0) or {}).get('weapon'))
            self.selected_character = (_los.get(0) or {}).get('char') or None
            for _i in (2, 3, 4):
                _lo = _los.get(_i - 1) or {}
                setattr(self, 'selected_weapon_p%d' % _i, _wt(_lo.get('weapon')))
                setattr(self, 'selected_char_p%d' % _i, _lo.get('char') or None)
            self.equip_p2_phase = False
            self.multiplayer_mode = "network"
            self.net_started = True
            self.net_phase = "playing"
            _h.phase = "playing"
            self.start_game()
            # v2.9.21：start_game() 会按单机流程把 state 切进开场 DIALOGUE，
            # 网络联机不该走单机剧情对话，否则房主开局即卡在对话页。
            self.state = GameState.PLAYING
            try:
                self.dialogue = None
            except Exception:
                pass
            self._net_send_snapshot_now()
            self.net_last_error = None
            return True
        except Exception as _e:
            self.net_last_error = "开局失败：%s" % _e
            return False

    # ---------- 客户端阶段同步 ----------
    def _net_client_sync_phase(self):
        """客户端每帧检查房主阶段，切到装备选择 / 游玩 / 结算。"""
        _nc = getattr(self, 'net_client', None)
        if _nc is None:
            return
        try:
            snap = _nc.get_snapshot() or {}
        except Exception:
            return
        _ph = snap.get("phase") or ("playing" if snap.get("started") else "wait")
        if _ph == getattr(self, 'net_phase', None):
            return
        self.net_phase = _ph
        if _ph == "setup":
            self._net_init_my_loadout()
            self.state = GameState.NET_SETUP
        elif _ph == "playing":
            try:
                self._setup_client_controls()
            except Exception:
                pass
            self.state = GameState.NET_CLIENT_PLAY
        elif _ph == "over":
            self.net_result = snap.get("result") or {}
            self.state = GameState.NET_RESULT
        elif _ph == "wait":
            self.state = GameState.NET_WAIT

    # ---------- 断开回到入口 ----------
    def _net_leave(self):
        try:
            self._net_stop()
        except Exception:
            pass
        self.state = GameState.NET_LOBBY
