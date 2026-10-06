#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
丧尸幸存者 - 黑暗绝望管弦乐 MIDI 生成器 v3（全配乐重制）
11 首标准 MIDI Type1 + GM 音色，手机端「音乐制作工坊」类 App（FL Studio Mobile / BandLab / GarageBand 等）可直接导入。
风格：悲哀绝望 + 史诗感管弦乐（弦乐群 / 铜管 / 低音提琴 / 定音鼓 / 打击乐 / 竖琴 / 人声合唱）
"""

import os
import random
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'music')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========== 音乐理论 ==========
_N = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5,
      'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}


def nn(name):
    """'C4' -> 60"""
    return _N[name[:-1]] + (int(name[-1]) + 1) * 12


def chord(root, kind='m', octave=3):
    """和弦音名列表，octave 为根音八度。root 可为 'Am'、'F'、'Dm7' 等带类型名"""
    import re
    m = re.match(r'^([A-G][#b]?)(.*)$', root)
    root_name = m.group(1)
    suffix = m.group(2)
    if suffix:
        if suffix == 'm': kind = 'm'
        elif suffix == 'm7': kind = 'm7'
        elif suffix == '7': kind = '7'
        elif suffix == 'sus4': kind = 'sus4'
        elif suffix == 'dim': kind = 'dim'
        elif suffix == 'M7': kind = 'M7'
        elif suffix == 'm6': kind = 'm6'
    r = nn(root_name + str(octave))
    if kind == 'm':    return [r, r + 3, r + 7]
    if kind == 'M':    return [r, r + 4, r + 7]
    if kind == 'dim':  return [r, r + 3, r + 6]
    if kind == 'm7':   return [r, r + 3, r + 7, r + 10]
    if kind == 'M7':   return [r, r + 4, r + 7, r + 11]
    if kind == 'sus4': return [r, r + 5, r + 7]
    if kind == '7':    return [r, r + 4, r + 7, r + 10]
    if kind == 'm6':   return [r, r + 3, r + 7, r + 9]
    return [r, r + 3, r + 7]


MINOR_KEYS = ['A', 'E', 'D', 'C', 'G', 'F', 'B']


# ========== MIDI 工具 ==========
class Trk:
    """多轨封装：标准 GM 音色。
    内部按【绝对 tick】收集事件，end() 时排序后统一转 delta time 输出——
    天然解决同轨同刻/重叠事件的时间线错位问题。
    """

    def __init__(self, mid, program=None, channel=0, name=''):
        self.track = MidiTrack()
        self.track.append(MetaMessage('track_name', name=name, time=0))
        mid.tracks.append(self.track)
        self.c = channel
        self.evs = []  # (abs_tick, kind, note, vel)
        if program is not None:
            self.track.append(Message('program_change', program=program, channel=channel, time=0))

    def note(self, pitch, vel, dur, start=None):
        """单音：start 为绝对 tick（可省略=沿用上一条末尾）"""
        if start is None:
            start = max([e[0] for e in self.evs] or [0])
        self.evs.append((start, 'note_on', pitch, vel))
        self.evs.append((start + dur, 'note_off', pitch, 0))

    def chord_n(self, notes, vel, dur, start=None):
        """和弦：全部同时发声，同时收尾"""
        if start is None:
            start = max([e[0] for e in self.evs] or [0])
        for p in notes:
            self.evs.append((start, 'note_on', p, vel))
        for p in notes:
            self.evs.append((start + dur, 'note_off', p, 0))

    def cc(self, num, val, t=0):
        self.evs.append((t, 'cc', num, val))

    def end(self, final=0):
        """排序并按 delta 输出；未覆盖到 final 的补 end_of_track 时间"""
        self.evs.sort(key=lambda e: e[0])
        last = 0
        for abs_t, kind, a, b in self.evs:
            d = max(abs_t - last, 0)
            if kind == 'note_on':
                self.track.append(Message('note_on', note=a, velocity=b, channel=self.c, time=d))
            elif kind == 'note_off':
                self.track.append(Message('note_off', note=a, velocity=0, channel=self.c, time=d))
            else:  # cc
                self.track.append(Message('control_change', control=a, value=b, channel=self.c, time=d))
            last = abs_t
        self.track.append(MetaMessage('end_of_track', time=max(final - last, 0)))


def make_midi(bpm, tpb=480):
    mid = MidiFile(ticks_per_beat=tpb)
    meta = MidiTrack()
    meta.append(MetaMessage('set_tempo', tempo=bpm2tempo(bpm), time=0))
    meta.append(MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    mid.tracks.append(meta)
    return mid


def _seg(note_on_msgs, n=8, bar_beats=4, bpm=120, beats=4):
    """占位（未用）"""
    pass


# 曲目规格：bpm, 调(根音), 和弦进行(小节单位), 时长(小节)
SONGS = {
    'menu':      dict(bpm=62,  key='A',  prog=['Am', 'F', 'C', 'G', 'Am', 'F', 'Dm7', 'Esus4'], bars=28, tempo_text='阴森空灵 · 主菜单'),
    'school':    dict(bpm=66,  key='E',  prog=['Em', 'C', 'G', 'D', 'Em', 'C', 'Am7', 'B7'],   bars=28, tempo_text='空旷压抑 · 校园'),
    'street':    dict(bpm=74,  key='D',  prog=['Dm', 'Bb', 'F', 'C', 'Dm', 'Bb', 'Gm7', 'Asus4'], bars=32, tempo_text='紧张疏离 · 街道'),
    'downtown':  dict(bpm=78,  key='C',  prog=['Cm', 'Ab', 'Eb', 'Bb', 'Cm', 'Ab', 'Fm7', 'G7'], bars=32, tempo_text='压迫 · 市中心'),
    'suburb':    dict(bpm=70,  key='G',  prog=['Gm', 'Eb', 'Bb', 'F', 'Gm', 'Eb', 'Cm7', 'D7'],  bars=32, tempo_text='不安潜伏 · 郊区'),
    'nuclear':   dict(bpm=84,  key='F',  prog=['Fm', 'Db', 'Ab', 'Eb', 'Fm', 'Db', 'Bbm7', 'C7'], bars=36, tempo_text='工业警报 · 核电站'),
    'tension':   dict(bpm=100, key='D',  prog=['Dm', 'Dm', 'Bb', 'Bb', 'Dm', 'Dm', 'A7', 'A7'],  bars=24, tempo_text='高紧张 · 潜伏'),
    'horde':     dict(bpm=122, key='D',  prog=['Dm', 'Bb', 'F', 'C', 'Dm', 'Bb', 'Gm7', 'A7'],  bars=48, tempo_text='激昂尸潮 · 战斗'),
    'boss':      dict(bpm=96,  key='C#', prog=['C#m', 'A', 'E', 'B', 'C#m', 'A', 'F#m7', 'G#7'], bars=56, tempo_text='史诗绝望 · BOSS战'),
    'victory':   dict(bpm=116, key='C',  prog=['C', 'F', 'G', 'C', 'Am', 'F', 'G7', 'C'],       bars=12, tempo_text='胜利号角'),
    'gameover':  dict(bpm=50,  key='A',  prog=['Am', 'F', 'Am', 'E', 'Am', 'F', 'Dm7', 'E7'],   bars=20, tempo_text='悲哀绝望 · 死亡'),
}

# GM 音色
P_STRINGS   = 48   # String Ensemble 1（弦乐群）
P_STR2      = 49   # String Ensemble 2
P_VIOLIN    = 40   # Violin
P_CELLO     = 42   # Cello
P_BASS      = 43   # Contrabass
P_FHORN     = 60   # French Horn（铜管圆号，史诗感）
P_TRUMPET   = 56   # Trumpet
P_TROMBONE  = 57   # Trombone
P_CHOIR     = 52   # Choir Aahs（人声合唱）
P_HARP      = 46   # Orchestral Harp
P_TIMPANI   = 47   # Timpani（定音鼓）
P_FLUTE     = 73   # Flute
P_CLARINET  = 71   # Clarinet
P_BASSOON   = 70   # Bassoon
P_PIANO     = 0    # Acoustic Grand Piano
P_OBOE      = 68   # Oboe

# GM 鼓组 (channel 9)
KICK = 36; SNARE = 38; SNARE2 = 40; CRASH = 49; RIDE = 51; HH_CL = 42; HH_OP = 46; TOM_L = 45; TOM_H = 50


def _root_from_key(k):
    return k if k != 'C#' else 'C#'


def generate(song_name):
    spec = SONGS[song_name]
    bpm = spec['bpm']
    root = spec['key']
    prog = spec['prog']
    bars = spec['bars']
    tpb = 480
    beat = tpb  # 1 拍 = 480 ticks
    mid = make_midi(bpm, tpb)

    # 通道规划（标准 GM，channel 0-15，9 为鼓）
    strings = Trk(mid, P_STRINGS, 0, 'Strings')
    cello = Trk(mid, P_CELLO, 1, 'Cello')
    bass = Trk(mid, P_BASS, 2, 'Contrabass')
    brass = Trk(mid, P_FHORN, 3, 'Brass')
    wood = Trk(mid, P_FLUTE if song_name != 'gameover' else P_CLARINET, 4, 'Woodwind')
    choir = Trk(mid, P_CHOIR, 5, 'Choir') if song_name in ('boss', 'menu', 'gameover') else None
    harp = Trk(mid, P_HARP, 6, 'Harp') if song_name in ('menu', 'suburb', 'victory') else None
    timp = Trk(mid, P_TIMPANI, 7, 'Timpani') if song_name in ('horde', 'boss', 'downtown', 'nuclear') else None
    drums = Trk(mid, None, 9, 'Drums')
    piano = Trk(mid, P_PIANO, 8, 'Piano') if song_name in ('menu', 'gameover', 'school') else None

    rng = random.Random(song_name)  # 固定种子，可复现

    # ---- 乐段 ----
    total_tick = bars * 4 * beat
    for bar in range(bars):
        t0 = bar * 4 * beat
        ch = prog[bar % len(prog)]
        notes = chord(ch, octave=3)
        root_note = notes[0]
        # 和弦根音八度归一（低音区）
        bass_pitch = root_note - 12 if root_note >= 48 else root_note
        # ---- 低音提琴：根音长音（每小节）----
        if bar % 2 == 0:
            bass.note(bass_pitch, 74, 4 * beat, start=t0)
        else:
            bass.note(bass_pitch, 70, 3 * beat, start=t0)
            bass.note(bass_pitch - 12 if bass_pitch >= 36 else bass_pitch, 68, beat, start=t0 + 3 * beat)
        # ---- 弦乐群：和声 pad（每 2 小节换，长音）----
        if bar % 2 == 0:
            vel = 62 + (bar % 8)
            strings.chord_n([n + 12 for n in notes], vel, 8 * beat, start=t0)
            # 内声部低八度
            strings.chord_n([n + 12 - 12 for n in notes[:2]], vel - 8, 8 * beat, start=t0)
        # ---- 大提琴：对位低音（第二拍起）----
        cello.note(bass_pitch + 7, 60, 2 * beat, start=t0 + 2 * beat)
        cello.note(bass_pitch + 3 if (bar + 1) % 2 else bass_pitch + 10, 58, 2 * beat, start=t0 + 2 * beat)
        # ---- 铜管：主题/应答（每 4 小节进一句）----
        if song_name in ('horde', 'boss', 'downtown', 'nuclear', 'tension'):
            if bar % 4 == 0:
                mels = [notes[0] + 24, notes[2] + 24, notes[1] + 24, notes[0] + 24]
                for i, mp in enumerate(mels):
                    brass.note(mp, 84 + (bar % 12), beat * 2, start=t0 + i * beat)
            elif bar % 4 == 2:
                brass.note(notes[2] + 24, 76, 4 * beat, start=t0)
        else:
            if bar % 4 == 0:
                brass.note(notes[0] + 24, 72, 2 * beat, start=t0)
                brass.note(notes[2] + 24, 70, 2 * beat, start=t0 + 2 * beat)
        # ---- 木管：点缀旋律（高八度）----
        if bar % 4 == 2 and song_name not in ('tension', 'horde'):
            wood.note(notes[0] + 36 if song_name != 'boss' else notes[1] + 36, 66, beat * 2, start=t0)
            wood.note(notes[1] + 36, 64, beat * 2, start=t0 + 2 * beat)
        # ---- 合唱：长音（boss/menu/gameover）----
        if choir is not None and bar % 2 == 0:
            choir.chord_n([n + 24 for n in notes[:3]], 58 + (bar % 6), 8 * beat, start=t0)
        # ---- 竖琴：琶音（menu/suburb/victory）----
        if harp is not None and bar % 2 == 0:
            for i, hp in enumerate([n + 24 for n in notes] + [n + 24 + 12 for n in notes[:1]]):
                harp.note(hp, 70, beat, start=t0 + i * (beat // 2))
        # ---- 定音鼓：强拍重击（horde/boss/downtown/nuclear）----
        if timp is not None:
            timp.note(bass_pitch + 12 if bass_pitch + 12 < 60 else bass_pitch, 92 if song_name in ('horde', 'boss') else 84,
                      3 * beat, start=t0)
            if bar % 2 == 1:
                timp.note(bass_pitch, 78, 2 * beat, start=t0 + 2 * beat)
        # ---- 钢琴（menu/gameover/school）：稀疏高音点缀 ----
        if piano is not None and bar % 2 == 0:
            piano.note(notes[0] + 36, 58, beat * 3, start=t0 + beat)
        # ---- 鼓组 ----
        dense = song_name in ('horde', 'boss', 'tension')
        kick_pat = [0, 2, 3] if dense else [0]
        snare_pat = [2] if song_name not in ('menu', 'school', 'gameover', 'suburb', 'victory') else []
        for b in range(4):
            bt = t0 + b * beat
            if b in kick_pat:
                drums.note(KICK, 100 if dense else 88, beat // 2, start=bt)
            if b == 0 and song_name in ('horde', 'boss', 'downtown', 'tension'):
                drums.note(CRASH, 90, beat * 2, start=bt)
            if b == 2 and 2 in snare_pat:
                drums.note(SNARE, 86 if song_name != 'tension' else 92, beat // 2, start=bt)
            if b == 3 and dense:
                drums.note(HH_OP, 70, beat // 4, start=bt)
            if song_name in ('boss', 'horde') and b == 3:
                drums.note(TOM_H, 78, beat // 2, start=bt)
    # 收尾：全部轨道 end_of_track
    for tr in (strings, cello, bass, brass, wood):
        tr.end(total_tick)
    for tr in (choir, harp, timp, piano):
        if tr is not None:
            tr.end(total_tick)
    drums.end(total_tick)
    path = os.path.join(OUTPUT_DIR, song_name + '.mid')
    mid.save(path)
    return path, bars, bpm


def main():
    made = []
    for name in SONGS:
        path, bars, bpm = generate(name)
        made.append((name, bars, bpm))
    print('=== MIDI 生成完成（标准 Type1 + GM）===')
    for name, bars, bpm in made:
        print(f'  {name}.mid  bpm={bpm}  时长≈{bars*4/60*bpm/ (bpm/60):.0f}s')


if __name__ == '__main__':
    main()
