# -*- coding: utf-8 -*-
"""v2.8.0 全局回放系统（Zombie Survivor Replay，.zsr）

设计目标
--------
1. **全局**：从开局到结束持续录制，环形缓冲保留最近 N 秒（默认 120s），
   任何时刻都能把"刚刚发生的事"存成文件（尤其是死亡瞬间）。
2. **只有游戏能解析**：自定义二进制格式（magic + 版本号 + zlib 压缩的定长帧），
   不是通用视频/JSON，脱离本游戏无法解读。
3. **可重新进入当时的情况**：回放不是录像画面，而是**世界状态快照序列**，
   玩家可以自由移动摄像机、缩放、逐帧查看，并从任意角度观察当时的战况。
4. **显示相关数据**：时间轴、击杀数、玩家血量/位置、场上敌人数、事件流水
   （击杀 / 受伤 / 技能 / Boss 登场 / 升级）都实时叠加显示。

文件格式（v1）
--------------
    b'ZSRP'                      magic（4B）
    uint8   version              （1B）
    uint32  meta_len             （4B）
    bytes   meta_json            utf-8  JSON：地图/模式/难度/时长/类型索引表/统计
    uint32  frames_len           （4B）
    bytes   frames_zlib          zlib 压缩的定长帧序列
    uint32  events_len           （4B）
    bytes   events_json          JSON 事件流水

帧布局（未压缩，每帧）
----------------------
    float32  t            时间戳（秒，相对开局）
    uint16   player_count
    uint16   enemy_count
    玩家 × N：float32 x, y, hp, angle + uint8 flags(bit0 alive, bit1 downed)
    敌人 × M：uint32 id, uint16 type_idx, float32 x, y, hp, angle + uint8 flags(bit0 alive, bit1 boss)
"""

import json
import os
import struct
import time
import zlib

MAGIC = b"ZSRP"
VERSION = 1

# 单帧结构（头部）
_FRAME_HEAD = struct.Struct("<fHH")          # t, player_count, enemy_count
_PLAYER_BIN = struct.Struct("<ffffB")        # x, y, hp, angle, flags
_ENEMY_BIN = struct.Struct("<IHffffB")       # id, type_idx, x, y, hp, angle, flags

# 采样与容量
SAMPLE_HZ = 20.0                 # 每秒采样帧数
DEFAULT_BUFFER_SECONDS = 120.0   # 环形缓冲保留秒数
MAX_ENEMIES_PER_FRAME = 220      # 单帧敌人上限（超出的按距离玩家最近的截断）


class ReplayFrame:
    """一帧世界快照（内存态）"""

    __slots__ = ("t", "players", "enemies")

    def __init__(self, t, players=None, enemies=None):
        self.t = t
        self.players = players or []   # [(x, y, hp, angle, flags)]
        self.enemies = enemies or []   # [(id, type_idx, x, y, hp, angle, flags)]

    def __repr__(self):
        return f"<ReplayFrame t={self.t:.2f} p={len(self.players)} e={len(self.enemies)}>"


class ReplayRecorder:
    """全局录制器：持续采样，环形缓冲"""

    def __init__(self, buffer_seconds=DEFAULT_BUFFER_SECONDS, sample_hz=SAMPLE_HZ):
        self.sample_hz = float(sample_hz)
        self._interval = 1.0 / self.sample_hz
        self.max_frames = max(30, int(buffer_seconds * self.sample_hz))
        self.frames = []            # 环形缓冲（超出后丢弃最旧的）
        self.events = []            # 事件流水（不裁剪，量小）
        self.type_table = []        # 敌人类型名 → 索引
        self._type_index = {}
        self._acc = 0.0
        self.elapsed = 0.0
        self.recording = False
        self.meta = {}
        self._event_seq = 0

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self, meta=None):
        self.frames = []
        self.events = []
        self.type_table = []
        self._type_index = {}
        self._acc = 0.0
        self.elapsed = 0.0
        self._event_seq = 0
        self.meta = dict(meta or {})
        self.recording = True

    def stop(self):
        self.recording = False

    # ------------------------------------------------------------------
    # 采样
    # ------------------------------------------------------------------
    def tick(self, dt, players, enemies):
        """每逻辑帧调用；内部按采样率决定是否落一帧"""
        if not self.recording:
            return
        self.elapsed += dt
        self._acc += dt
        if self._acc < self._interval:
            return
        self._acc = 0.0
        self._capture(players, enemies)

    def force_capture(self, players, enemies):
        """立即落一帧（死亡瞬间等关键节点）"""
        if not self.recording:
            return
        self._capture(players, enemies)

    def _type_idx(self, name):
        _i = self._type_index.get(name)
        if _i is None:
            _i = len(self.type_table)
            self.type_table.append(name)
            self._type_index[name] = _i
        return _i

    def _capture(self, players, enemies):
        _ps = []
        for _p in players or []:
            if _p is None:
                continue
            _flags = (1 if getattr(_p, "alive", True) else 0) | \
                     (2 if getattr(_p, "downed", False) else 0)
            _ps.append((float(getattr(_p, "x", 0.0)), float(getattr(_p, "y", 0.0)),
                        float(getattr(_p, "hp", 0.0)),
                        float(getattr(_p, "facing_angle", 0.0)), _flags))
        _es = []
        for _e in enemies or []:
            _ename = _e.get("type") if isinstance(_e, dict) else getattr(_e, "enemy_type", None)
            _ename = getattr(_ename, "name", str(_ename))
            _flags = 0
            _eid = 0
            _ex = _ey = _ehp = _eang = 0.0
            _alive = True
            _boss = False
            if isinstance(_e, dict):
                _eid = int(_e.get("id", 0))
                _ex = float(_e.get("x", 0.0)); _ey = float(_e.get("y", 0.0))
                _ehp = float(_e.get("hp", 0.0)); _eang = float(_e.get("angle", 0.0))
                _alive = bool(_e.get("alive", True)); _boss = bool(_e.get("boss", False))
            else:
                _eid = int(getattr(_e, "enemy_id", id(_e)) & 0xFFFFFFFF)
                _ex = float(getattr(_e, "x", 0.0)); _ey = float(getattr(_e, "y", 0.0))
                _ehp = float(getattr(_e, "hp", 0.0))
                _eang = float(getattr(_e, "facing_angle", 0.0))
                _alive = bool(getattr(_e, "alive", True))
                _boss = bool(getattr(_e, "is_boss", False))
            _flags = (1 if _alive else 0) | (2 if _boss else 0)
            _es.append((_eid, self._type_idx(_ename), _ex, _ey, _ehp, _eang, _flags))

        # 敌人过多时截断（按 hp 非零优先保留，避免回放文件爆炸）
        if len(_es) > MAX_ENEMIES_PER_FRAME:
            _es.sort(key=lambda r: (not (r[6] & 1),))
            _es = _es[:MAX_ENEMIES_PER_FRAME]

        self.frames.append(ReplayFrame(self.elapsed, _ps, _es))
        if len(self.frames) > self.max_frames:
            del self.frames[:len(self.frames) - self.max_frames]

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def add_event(self, kind, text="", x=0.0, y=0.0, value=0.0, tag=None):
        """记录一条事件（击杀/受伤/技能/Boss/升级……）"""
        if not self.recording:
            return
        self._event_seq += 1
        self.events.append({
            "i": self._event_seq,
            "t": round(self.elapsed, 3),
            "kind": kind,
            "text": text,
            "x": round(float(x), 1), "y": round(float(y), 1),
            "v": round(float(value), 2),
            "tag": tag,
        })
        # 事件量保护
        if len(self.events) > 4000:
            del self.events[:len(self.events) - 4000]

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_bytes(self):
        """序列化为 .zsr 字节流（只有本游戏能解析）"""
        _meta = dict(self.meta)
        _meta["types"] = self.type_table
        _meta["frames"] = len(self.frames)
        _meta["duration"] = round(self.elapsed, 3)
        _meta["sample_hz"] = self.sample_hz
        _meta["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _meta_bytes = json.dumps(_meta, ensure_ascii=False).encode("utf-8")

        _buf = bytearray()
        for _f in self.frames:
            _buf += _FRAME_HEAD.pack(_f.t, len(_f.players), len(_f.enemies))
            for _p in _f.players:
                _buf += _PLAYER_BIN.pack(*_p)
            for _e in _f.enemies:
                _buf += _ENEMY_BIN.pack(*_e)
        _frames_z = zlib.compress(bytes(_buf), 6)
        _events_bytes = json.dumps(self.events, ensure_ascii=False).encode("utf-8")

        _out = bytearray()
        _out += MAGIC
        _out += struct.pack("<B", VERSION)
        _out += struct.pack("<I", len(_meta_bytes)) + _meta_bytes
        _out += struct.pack("<I", len(_frames_z)) + _frames_z
        _out += struct.pack("<I", len(_events_bytes)) + _events_bytes
        return bytes(_out)

    def save(self, path):
        _dir = os.path.dirname(os.path.abspath(path))
        if _dir:
            os.makedirs(_dir, exist_ok=True)
        with open(path, "wb") as _f:
            _f.write(self.to_bytes())
        return path


def load_replay(path):
    """解析 .zsr 文件 → ReplayData。格式不符会抛 ValueError。"""
    with open(path, "rb") as _f:
        _raw = _f.read()
    if len(_raw) < 13 or _raw[:4] != MAGIC:
        raise ValueError("不是有效的回放文件（magic 不匹配）")
    _off = 4
    _ver = _raw[_off]; _off += 1
    if _ver != VERSION:
        raise ValueError(f"回放版本不支持: {_ver}")
    _meta_len = struct.unpack_from("<I", _raw, _off)[0]; _off += 4
    _meta = json.loads(_raw[_off:_off + _meta_len].decode("utf-8")); _off += _meta_len
    _frames_len = struct.unpack_from("<I", _raw, _off)[0]; _off += 4
    _frames_raw = zlib.decompress(_raw[_off:_off + _frames_len]); _off += _frames_len
    _events_len = struct.unpack_from("<I", _raw, _off)[0]; _off += 4
    _events = json.loads(_raw[_off:_off + _events_len].decode("utf-8"))

    _frames = []
    _p = 0
    _hp, _pp, _pe = _FRAME_HEAD.size, _PLAYER_BIN.size, _ENEMY_BIN.size
    _n = len(_frames_raw)
    while _p + _hp <= _n:
        _t, _pc, _ec = _FRAME_HEAD.unpack_from(_frames_raw, _p)
        _p += _hp
        _pl = []
        for _ in range(_pc):
            if _p + _pp > _n:
                break
            _pl.append(_PLAYER_BIN.unpack_from(_frames_raw, _p))
            _p += _pp
        _el = []
        for _ in range(_ec):
            if _p + _pe > _n:
                break
            _el.append(_ENEMY_BIN.unpack_from(_frames_raw, _p))
            _p += _pe
        _frames.append(ReplayFrame(_t, _pl, _el))
    return ReplayData(_meta, _frames, _events, os.path.basename(path))


class ReplayData:
    """已加载的回放数据 + 播放控制（自由摄像机在 FreeCamera 里）"""

    def __init__(self, meta, frames, events, name=""):
        self.meta = meta or {}
        self.frames = frames or []
        self.events = events or []
        self.name = name
        self.types = self.meta.get("types", [])
        self.index = 0            # 当前帧下标
        self.playing = True
        self.speed = 1.0
        self._acc = 0.0

    @property
    def duration(self):
        return self.frames[-1].t if self.frames else 0.0

    @property
    def current(self):
        if not self.frames:
            return None
        return self.frames[min(self.index, len(self.frames) - 1)]

    @property
    def time_now(self):
        _f = self.current
        return _f.t if _f else 0.0

    def update(self, dt):
        if not self.playing or not self.frames:
            return
        self._acc += dt * self.speed
        _step = 1.0 / float(self.meta.get("sample_hz", SAMPLE_HZ))
        while self._acc >= _step:
            self._acc -= _step
            if self.index < len(self.frames) - 1:
                self.index += 1
            else:
                self.playing = False   # 播完停在最后一帧
                self._acc = 0.0
                break

    def seek_ratio(self, ratio):
        if not self.frames:
            return
        _r = max(0.0, min(1.0, ratio))
        self.index = int(_r * (len(self.frames) - 1))

    def step(self, delta):
        if not self.frames:
            return
        self.index = max(0, min(len(self.frames) - 1, self.index + delta))

    def events_until(self, t, limit=8):
        """取当前时刻之前最近的 limit 条事件（用于数据面板流水）"""
        _out = [e for e in self.events if e.get("t", 0) <= t]
        return _out[-limit:]


class FreeCamera:
    """回放用自由摄像机：可平移、缩放，不受玩家/边界约束"""

    def __init__(self, x=0.0, y=0.0, zoom=1.0):
        self.x = x
        self.y = y
        self.zoom = max(0.25, min(4.0, zoom))

    def move(self, dx, dy):
        self.x += dx / self.zoom
        self.y += dy / self.zoom

    def zoom_by(self, factor):
        self.zoom = max(0.25, min(4.0, self.zoom * factor))

    def center_on(self, x, y):
        self.x = float(x)
        self.y = float(y)
