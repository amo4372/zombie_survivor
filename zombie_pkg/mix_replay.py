# -*- coding: utf-8 -*-
"""v2.8.0 全局回放系统的游戏侧集成（ReplayMixin）

录制：开局即启动，按 20Hz 采样世界快照，环形缓冲保留最近 120 秒。
     任何时刻都能"把刚刚发生的事"存成 .zsr（尤其是死亡瞬间）。
播放：进入 GameState.REPLAY，用自由摄像机重新观察当时的战况，
     叠加显示时间轴与相关数据（血量/敌人数/击杀/事件流水）。
"""

import os
import time

from replay import ReplayRecorder, load_replay, ReplayData, FreeCamera

REPLAY_DIR = "replays"


class ReplayMixin:
    """回放录制 / 保存 / 播放"""

    # ==================================================================
    # 录制
    # ==================================================================
    def _replay_init(self):
        """初始化（在 start_game 里调用）"""
        self.replay_recorder = ReplayRecorder()
        self.replay_data = None
        self.replay_cam = None
        self.replay_playing = True
        self.replay_last_saved = None
        self.replay_ui_drag = None
        self.replay_zoom_step = 1.0

    def _replay_dir(self):
        _d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), REPLAY_DIR)
        try:
            os.makedirs(_d, exist_ok=True)
        except Exception:
            pass
        return _d

    def start_replay_recording(self):
        """开局启动录制"""
        try:
            _meta = {
                "mode": str(getattr(getattr(self, 'config', None), 'game_mode', '')),
                "map": str(getattr(self, 'current_map', '')),
                "difficulty": str(getattr(getattr(self, 'config', None), 'difficulty', '')),
                "multiplayer": bool(self.is_multiplayer_active()) if hasattr(self, 'is_multiplayer_active') else False,
            }
            self.replay_recorder.start(_meta)
        except Exception:
            pass

    def _replay_tick(self, dt):
        """每逻辑帧采样（由 _update_playing 调用）"""
        try:
            if getattr(self, 'replay_recorder', None) is None or not self.replay_recorder.recording:
                return
            self.replay_recorder.tick(dt, self.registered_players(), getattr(self, 'enemies', []))
        except Exception:
            pass

    def replay_event(self, kind, text="", x=0.0, y=0.0, value=0.0, tag=None):
        """记录一条回放事件（击杀/受伤/技能/Boss/升级）"""
        try:
            if getattr(self, 'replay_recorder', None) is not None:
                self.replay_recorder.add_event(kind, text, x, y, value, tag)
        except Exception:
            pass

    def save_replay(self, name=None, tag="manual"):
        """把当前环形缓冲存成 .zsr 文件，返回路径（失败返回 None）"""
        try:
            _r = getattr(self, 'replay_recorder', None)
            if _r is None or not _r.frames:
                return None
            if name is None:
                _stamp = time.strftime("%Y%m%d_%H%M%S")
                name = f"replay_{tag}_{_stamp}.zsr"
            if not name.endswith(".zsr"):
                name += ".zsr"
            _path = os.path.join(self._replay_dir(), name)
            _r.save(_path)
            self.replay_last_saved = _path
            return _path
        except Exception:
            return None

    def list_replays(self):
        """列出已保存的回放（最新在前）"""
        try:
            _d = self._replay_dir()
            _out = []
            for _fn in os.listdir(_d):
                if _fn.endswith(".zsr"):
                    _p = os.path.join(_d, _fn)
                    _out.append({"name": _fn, "path": _p,
                                 "size": os.path.getsize(_p),
                                 "mtime": os.path.getmtime(_p)})
            _out.sort(key=lambda r: r["mtime"], reverse=True)
            return _out
        except Exception:
            return []

    # ==================================================================
    # 播放
    # ==================================================================
    def enter_replay(self, path):
        """加载并进入回放"""
        try:
            _d = load_replay(path)
        except Exception:
            return False
        self.replay_data = _d
        self.replay_cam = FreeCamera(0.0, 0.0, 1.0)
        self.replay_playing = True
        self.replay_follow = True
        # v2.8.2 玩家向：默认隐藏数据面板（按 D/数据键可切换），
        # 默认从「致死时刻前 3 秒」开始播，直接看到自己是怎么死的
        self.replay_show_data = False
        try:
            _di = _d.death_index()
            _back = int(3.0 * float(_d.meta.get("sample_hz", 20)))
            _d.index = max(0, _di - _back)
        except Exception:
            _d.index = 0
        # 摄像机对准第一位玩家
        _f = _d.current
        if _f and _f.players:
            self.replay_cam.center_on(_f.players[0][0], _f.players[0][1])
        self.state = self._replay_state()
        return True

    def _replay_state(self):
        from config import GameState
        return GameState.REPLAY

    def exit_replay(self):
        """退出回放"""
        self.replay_data = None
        self.replay_cam = None
        from config import GameState
        self.state = GameState.MENU

    def _update_replay(self, dt):
        """回放播放推进 + 自由摄像机输入"""
        _d = getattr(self, 'replay_data', None)
        if _d is None:
            return
        # 播放推进
        if self.replay_playing:
            _d.update(dt)
        _cam = self.replay_cam
        if _cam is None:
            return
        if not hasattr(self, 'replay_follow'):
            self.replay_follow = True

        # --- 自由摄像机：WASD 平移 ---
        try:
            import pygame
            _keys = pygame.key.get_pressed()
            _sp = 900.0 * dt / max(0.25, _cam.zoom)
            _dx = _dy = 0.0
            if _keys[pygame.K_a]:
                _dx -= _sp
            if _keys[pygame.K_d]:
                _dx += _sp
            if _keys[pygame.K_w]:
                _dy -= _sp
            if _keys[pygame.K_s]:
                _dy += _sp
            if _dx or _dy:
                self.replay_follow = False
                _cam.move(_dx, _dy)
        except Exception:
            pass

        # --- 自由摄像机：鼠标/触摸拖动 ---
        try:
            import pygame
            if pygame.mouse.get_pressed()[0]:
                _rel = pygame.mouse.get_rel()
                if _rel[0] or _rel[1]:
                    self.replay_follow = False
                    _cam.move(-_rel[0], -_rel[1])
            else:
                pygame.mouse.get_rel()
        except Exception:
            pass

        # --- 跟随主玩家（未手动操作时） ---
        _f = _d.current
        if _f and _f.players and self.replay_follow:
            _cam.x += (_f.players[0][0] - _cam.x) * min(1.0, dt * 3.0)
            _cam.y += (_f.players[0][1] - _cam.y) * min(1.0, dt * 3.0)

    def replay_toggle_play(self):
        _d = getattr(self, 'replay_data', None)
        if _d is None:
            return
        if _d.index >= len(_d.frames) - 1:
            _d.index = 0          # 播完后再按 = 从头播
        self.replay_playing = not self.replay_playing

    def replay_seek(self, ratio):
        _d = getattr(self, 'replay_data', None)
        if _d is not None:
            _d.seek_ratio(ratio)

    def replay_step(self, delta):
        _d = getattr(self, 'replay_data', None)
        if _d is not None:
            self.replay_playing = False
            _d.step(delta)

    def replay_cycle_speed(self):
        _d = getattr(self, 'replay_data', None)
        if _d is None:
            return 1.0
        _steps = (0.25, 0.5, 1.0, 2.0, 4.0)
        _cur = _d.speed
        for _s in _steps:
            if _s > _cur + 1e-6:
                _d.speed = _s
                return _d.speed
        _d.speed = _steps[0]
        return _d.speed

    def replay_stats(self):
        """回放数据面板用的统计（当前帧）"""
        _d = getattr(self, 'replay_data', None)
        if _d is None:
            return {}
        _f = _d.current
        if _f is None:
            return {}
        _alive = sum(1 for e in _f.enemies if e[6] & 1)
        _boss = sum(1 for e in _f.enemies if e[6] & 2)
        return {
            "time": _f.t,
            "duration": _d.duration,
            "frame": _d.index + 1,
            "frames": len(_d.frames),
            "players": len(_f.players),
            "enemies": len(_f.enemies),
            "enemies_alive": _alive,
            "boss": _boss,
            "events": _d.events_until(_f.t, 8),
            "meta": _d.meta,
        }
