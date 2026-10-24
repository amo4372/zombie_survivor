#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
midi_lite —— 零依赖的标准 MIDI (SMF) 读写最小实现（v2.5.7 新增）

为什么需要它：
  仓库里的 generate_music.py / generate_music_race.py 依赖 `mido`，
  但 mido 不是 Python 标准库，PyDroid3 / 离线环境 / CI 里常常装不上，
  导致"生成配乐 MIDI"这一步在手机上根本跑不了。
  本模块提供与 mido **同名 API 子集**（MidiFile / MidiTrack / Message /
  MetaMessage / bpm2tempo），因此生成脚本无需改动即可直接跑。

输出标准：
  - Standard MIDI File Type 1（多轨 + 独立速度轨），手机「音乐制作工坊」类
    App（FL Studio Mobile / BandLab / GarageBand / 音乐工坊）可直接导入；
  - 480 ticks/quarter，GM 音色（program_change），4/4 拍；
  - 每轨带 track_name（方便在 App 里认轨），结尾补 end_of_track。
"""

import struct

__all__ = ["MidiFile", "MidiTrack", "Message", "MetaMessage", "bpm2tempo",
           "MidiError"]


class MidiError(Exception):
    pass


# ==================== 变长量（delta time） ====================
def _vlq(n):
    """把整数编码成 MIDI 变长量（VLQ）字节串"""
    if n < 0:
        n = 0
    buf = bytearray()
    buf.append(n & 0x7F)
    n >>= 7
    while n:
        buf.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(buf))


# ==================== 事件对象 ====================
class _BaseMsg(object):
    __slots__ = ("type", "time")

    def __init__(self, type_, time=0):
        self.type = type_
        self.time = time


class Message(_BaseMsg):
    """通道事件（note_on / note_off / program_change / control_change）"""

    __slots__ = ("channel", "note", "velocity", "control", "value", "program")

    def __init__(self, type_, time=0, channel=0, note=0, velocity=0,
                 control=0, value=0, program=0):
        _BaseMsg.__init__(self, type_, time)
        self.channel = int(channel) & 0x0F
        self.note = int(note)
        self.velocity = int(velocity)
        self.control = int(control)
        self.value = int(value)
        self.program = int(program)

    # -- 编码 --
    def _status(self):
        if self.type == "note_on":
            return 0x90 | self.channel
        if self.type == "note_off":
            return 0x80 | self.channel
        if self.type == "program_change":
            return 0xC0 | self.channel
        if self.type == "control_change":
            return 0xB0 | self.channel
        if self.type == "pitchwheel":
            return 0xE0 | self.channel
        raise MidiError("midi_lite 不支持的事件类型: %s" % self.type)

    def raw(self):
        st = self._status()
        if self.type in ("note_on", "note_off"):
            return bytes([st, self.note & 0x7F, self.velocity & 0x7F])
        if self.type == "program_change":
            return bytes([st, self.program & 0x7F])
        if self.type == "control_change":
            return bytes([st, self.control & 0x7F, self.value & 0x7F])
        if self.type == "pitchwheel":
            v = max(0, min(0x3FFF, self.value))
            return bytes([st, v & 0x7F, (v >> 7) & 0x7F])
        raise MidiError("midi_lite 不支持的事件类型: %s" % self.type)

    def __repr__(self):
        return "Message(%r, channel=%r, note=%r, velocity=%r)" % (
            self.type, self.channel, self.note, self.velocity)


class MetaMessage(_BaseMsg):
    """元事件（track_name / set_tempo / time_signature / end_of_track ...）"""

    __slots__ = ("data",)

    def __init__(self, type_, time=0, **kwargs):
        _BaseMsg.__init__(self, type_, time)
        self.data = dict(kwargs)

    def raw(self):
        t = self.type
        if t == "track_name":
            payload = str(self.data.get("name", "")).encode("utf-8")
            return b"\xFF\x03" + _vlq(len(payload)) + payload
        if t == "set_tempo":
            tempo = int(self.data.get("tempo", 500000))
            return b"\xFF\x51\x03" + struct.pack(">I", tempo)[1:]
        if t == "time_signature":
            num = int(self.data.get("numerator", 4))
            den = int(self.data.get("denominator", 4))
            dd = 0
            d = den
            while d > 1 and d % 2 == 0:
                d //= 2
                dd += 1
            cc = int(self.data.get("clocks_per_click", 24))
            nq = int(self.data.get("notes_per_quarter", 8))
            return b"\xFF\x58\x04" + bytes([num, dd, cc, nq])
        if t == "end_of_track":
            return b"\xFF\x2F\x00"
        if t == "marker":
            payload = str(self.data.get("text", "")).encode("utf-8")
            return b"\xFF\x06" + _vlq(len(payload)) + payload
        if t == "copyright":
            payload = str(self.data.get("text", "")).encode("utf-8")
            return b"\xFF\x02" + _vlq(len(payload)) + payload
        raise MidiError("midi_lite 不支持的元事件: %s" % t)

    def __repr__(self):
        return "MetaMessage(%r, %r)" % (self.type, self.data)


class MidiTrack(object):
    """单轨：按追加顺序保存事件，save 时统一算 delta time"""

    def __init__(self, name=None):
        self.events = []
        self.name = name

    def append(self, msg):
        self.events.append(msg)
        return msg

    def __len__(self):
        return len(self.events)

    def __iter__(self):
        return iter(self.events)

    # -- 编码 --
    def _encode(self):
        out = bytearray()
        last = 0
        for msg in self.events:
            delta = int(getattr(msg, "time", 0) or 0)
            if delta < 0:
                delta = 0
            out += _vlq(delta)
            out += msg.raw()
            last += delta
        return bytes(out)

    def to_bytes(self):
        body = self._encode()
        return b"MTrk" + struct.pack(">I", len(body)) + body


class MidiFile(object):
    """标准 MIDI 文件（Type 1）"""

    def __init__(self, ticks_per_beat=480, file_format=1):
        self.ticks_per_beat = int(ticks_per_beat)
        self.file_format = int(file_format)
        self.tracks = []

    def save(self, path):
        head = b"MThd" + struct.pack(">IHHH", 6, self.file_format,
                                     len(self.tracks), self.ticks_per_beat)
        with open(path, "wb") as f:
            f.write(head)
            for tr in self.tracks:
                f.write(tr.to_bytes())
        return path

    def __repr__(self):
        return "MidiFile(tracks=%d, tpb=%d)" % (len(self.tracks), self.ticks_per_beat)


def bpm2tempo(bpm, ticks_per_beat=480):
    """BPM → 每四分音符微秒数"""
    return int(round(60000000.0 / float(bpm)))


# ==================== 迷你读取器（用于自检/测试） ====================
def read_midi(path):
    """读取 MIDI → (header_info, [track_events])

    track_events: list of list of (abs_tick, 类型, 参数字典)
    """
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"MThd":
        raise MidiError("不是标准 MIDI 文件")
    hlen = struct.unpack(">I", data[4:8])[0]
    fmt, ntrk, div = struct.unpack(">HHH", data[8:8 + 6])
    pos = 8 + hlen
    tracks = []
    for _ in range(ntrk):
        if data[pos:pos + 4] != b"MTrk":
            break
        tlen = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + tlen]
        pos += 8 + tlen
        tracks.append(_parse_track(body))
    return {"format": fmt, "ntrks": ntrk, "division": div}, tracks


def _parse_track(body):
    events = []
    i = 0
    tick = 0
    status = 0
    while i < len(body):
        # delta
        delta = 0
        while True:
            if i >= len(body):
                return events
            b = body[i]
            i += 1
            delta = (delta << 7) | (b & 0x7F)
            if not (b & 0x80):
                break
        tick += delta
        if i >= len(body):
            break
        b = body[i]
        if b == 0xFF:  # meta
            i += 1
            mtype = body[i]
            i += 1
            ln = 0
            while True:
                bb = body[i]
                i += 1
                ln = (ln << 7) | (bb & 0x7F)
                if not (bb & 0x80):
                    break
            payload = body[i:i + ln]
            i += ln
            if mtype == 0x2F:
                events.append((tick, "end_of_track", {}))
            elif mtype == 0x03:
                events.append((tick, "track_name", {"name": payload.decode("utf-8", "replace")}))
            elif mtype == 0x51:
                tempo = struct.unpack(">I", b"\x00" + payload)[0]
                events.append((tick, "set_tempo", {"tempo": tempo}))
            elif mtype == 0x58:
                events.append((tick, "time_signature", {
                    "numerator": payload[0], "denominator": 2 ** payload[1]}))
            else:
                events.append((tick, "meta_%02X" % mtype, {}))
        elif b in (0xF0, 0xF7):  # sysex
            i += 1
            ln = 0
            while True:
                bb = body[i]
                i += 1
                ln = (ln << 7) | (bb & 0x7F)
                if not (bb & 0x80):
                    break
            i += ln
        else:
            if b & 0x80:
                status = b
                i += 1
            st = status & 0xF0
            ch = status & 0x0F
            if st in (0xC0, 0xD0):
                d1 = body[i]
                i += 1
                events.append((tick, "program_change" if st == 0xC0 else "aftertouch",
                               {"channel": ch, "program": d1}))
            else:
                d1 = body[i]
                d2 = body[i + 1]
                i += 2
                if st == 0x90:
                    events.append((tick, "note_on", {"channel": ch, "note": d1, "velocity": d2}))
                elif st == 0x80:
                    events.append((tick, "note_off", {"channel": ch, "note": d1, "velocity": d2}))
                elif st == 0xB0:
                    events.append((tick, "control_change", {"channel": ch, "control": d1, "value": d2}))
                elif st == 0xE0:
                    events.append((tick, "pitchwheel", {"channel": ch, "value": (d2 << 7) | d1}))
                else:
                    events.append((tick, "other", {"channel": ch}))
    return events
