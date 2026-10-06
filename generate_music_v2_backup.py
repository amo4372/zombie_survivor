#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
丧尸幸存者 - 黑暗绝望管弦乐MIDI生成器 v2（修复版）
使用mido库生成11首约4分钟的管弦乐MIDI文件
关键修复：使用正确的相对时间（delta time），避免时间累积bug
"""

import os
import random
import math
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'music')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========== 音乐理论工具 ==========

MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]
HARMONIC_MINOR = [0, 2, 3, 5, 7, 8, 11]


def note_name_to_midi(name):
    notes = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
             'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
             'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
    pitch = name[:-1]
    octave = int(name[-1])
    return notes[pitch] + (octave + 1) * 12


def get_chord(root_note, chord_type='minor', octave=3):
    root = note_name_to_midi(root_note + str(octave))
    if chord_type == 'minor':
        return [root, root + 3, root + 7]
    elif chord_type == 'major':
        return [root, root + 4, root + 7]
    elif chord_type == 'diminished':
        return [root, root + 3, root + 6]
    elif chord_type == 'minor7':
        return [root, root + 3, root + 7, root + 10]
    return [root, root + 3, root + 7]


# ========== 安全轨道类（自动管理相对时间） ==========

class SafeTrack:
    """包装MidiTrack，自动将绝对时间转换为相对时间，避免时间累积bug"""
    def __init__(self, mid, program=None, channel=0):
        self.track = MidiTrack()
        mid.tracks.append(self.track)
        self.channel = channel
        self.last_tick = 0  # 上一个事件的绝对时间
        if program is not None:
            self._add(Message('program_change', program=program, channel=channel, time=0))

    def _add(self, msg):
        """添加消息，自动转换为相对时间"""
        abs_time = getattr(msg, 'time', 0)
        delta = max(0, abs_time - self.last_tick)
        msg.time = delta
        self.track.append(msg)
        self.last_tick = abs_time

    def note_on(self, note, velocity, tick):
        self._add(Message('note_on', note=note, velocity=velocity,
                          time=tick, channel=self.channel))

    def note_off(self, note, tick):
        self._add(Message('note_off', note=note, velocity=0,
                          time=tick, channel=self.channel))

    def add_note(self, note, velocity, start_tick, duration):
        """添加一个完整音符（note_on + note_off）"""
        self.note_on(note, velocity, start_tick)
        self.note_off(note, start_tick + duration)

    def add_chord(self, notes, velocity, start_tick, duration):
        """添加和弦（所有音符同时on和off）"""
        for n in notes:
            self.note_on(n, velocity, start_tick)
        for n in notes:
            self.note_off(n, start_tick + duration)

    def end(self, final_tick):
        """结束轨道"""
        self._add(MetaMessage('end_of_track', time=final_tick))


def create_midi(bpm, ticks_per_beat=480):
    """创建MIDI文件"""
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    meta = MidiTrack()
    mid.tracks.append(meta)
    meta.append(MetaMessage('set_tempo', tempo=bpm2tempo(bpm), time=0))
    meta.append(MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    meta.append(MetaMessage('end_of_track', time=0))
    return mid


# ========== 各首音乐生成函数 ==========

def generate_menu():
    """菜单：悲伤钢琴+弦乐，A小调，60BPM，约4分钟"""
    print("生成: 菜单音乐...")
    mid = create_midi(60)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 60  # 60小节 * 4秒 = 240秒 = 4分钟

    piano = SafeTrack(mid, 0, 0)
    strings = SafeTrack(mid, 48, 1)
    cello = SafeTrack(mid, 42, 2)
    flute = SafeTrack(mid, 73, 3)

    progression = [
        get_chord('A', 'minor', 3),
        get_chord('F', 'major', 3),
        get_chord('C', 'major', 3),
        get_chord('G', 'major', 3),
    ]
    melody_scale = [note_name_to_midi('A5'), note_name_to_midi('C6'),
                     note_name_to_midi('E6'), note_name_to_midi('D6')]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        # 钢琴分解和弦
        arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12]
        for i, n in enumerate(arp):
            piano.add_note(n, 45, t + i * beat // 2, beat // 2)
        # 弦乐持续
        strings.add_chord([n + 12 for n in chord], 35, t, measure)
        # 大提琴低音
        cello.add_note(chord[0] - 12, 50, t, measure)
        # 长笛稀疏旋律
        if m % 4 == 2:
            flute.add_note(random.choice(melody_scale), 40, t + beat, beat * 2)

    final = total_measures * measure
    for trk in [piano, strings, cello, flute]:
        trk.end(final)

    mid.save(os.path.join(OUTPUT_DIR, 'menu.mid'))
    print(f"  完成: menu.mid ({total_measures}小节, 约{total_measures*4}秒)")


def generate_school():
    """校园：黑暗钢琴+颤音弦乐，D小调，65BPM"""
    print("生成: 校园地图音乐...")
    mid = create_midi(65)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 65

    piano = SafeTrack(mid, 0, 0)
    tremolo = SafeTrack(mid, 44, 1)
    cello = SafeTrack(mid, 42, 2)
    harp = SafeTrack(mid, 46, 3)

    progression = [
        get_chord('D', 'minor', 3),
        get_chord('Bb', 'major', 3),
        get_chord('F', 'major', 3),
        get_chord('A', 'major', 3),
        get_chord('D', 'diminished', 3),
        get_chord('G', 'minor', 3),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 6]
        # 钢琴低沉单音
        if m % 2 == 0:
            piano.add_note(chord[0], 55, t, measure)
            piano.add_note(chord[0] + 7, 40, t + beat * 2, beat * 2)
        else:
            piano.add_note(chord[0], 60, t, measure // 2)
            piano.add_note(chord[0] + 1, 50, t + measure // 2, measure // 2)
        # 颤音弦乐
        trem_notes = [n + 12 for n in chord]
        if m % 3 == 0:
            trem_notes.append(chord[0] + 13)
        tremolo.add_chord(trem_notes, 30, t, measure)
        # 大提琴
        cello.add_note(chord[0] - 12, 45, t, measure)
        # 竖琴泛音
        if m % 4 == 1:
            harp.add_note(chord[2] + 24, 35, t + beat, beat * 3)

    final = total_measures * measure
    for trk in [piano, tremolo, cello, harp]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'school.mid'))
    print(f"  完成: school.mid")


def generate_street():
    """街区：低沉铜管+定音鼓，E小调，75BPM"""
    print("生成: 街区地图音乐...")
    mid = create_midi(75)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 75

    tuba = SafeTrack(mid, 58, 0)
    trombone = SafeTrack(mid, 57, 1)
    strings = SafeTrack(mid, 48, 2)
    timpani = SafeTrack(mid, 47, 9)  # 通道10打击乐
    bassoon = SafeTrack(mid, 70, 3)

    progression = [
        get_chord('E', 'minor', 2),
        get_chord('C', 'major', 2),
        get_chord('G', 'major', 2),
        get_chord('D', 'major', 2),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        tuba.add_note(chord[0] - 12, 55, t, measure)
        trombone.add_chord([n + 12 for n in chord[:2]], 40, t, measure)
        strings.add_chord([chord[2] + 24], 25, t, measure)
        # 定音鼓
        timpani.add_note(47, 70, t, beat)
        if m % 2 == 1:
            timpani.add_note(45, 50, t + beat * 2, beat)
        # 巴松管旋律
        if m % 2 == 0:
            bass_notes = [chord[0], chord[0] + 2, chord[0] + 3, chord[0] + 1]
            for i, bn in enumerate(bass_notes):
                bassoon.add_note(bn, 40, t + i * beat, beat)

    final = total_measures * measure
    for trk in [tuba, trombone, strings, timpani, bassoon]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'street.mid'))
    print(f"  完成: street.mid")


def generate_downtown():
    """市中心：激烈管弦+打击，C小调，120BPM"""
    print("生成: 市中心地图音乐...")
    mid = create_midi(120)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 120

    strings = SafeTrack(mid, 48, 0)
    brass = SafeTrack(mid, 61, 1)
    trumpet = SafeTrack(mid, 56, 2)
    perc = SafeTrack(mid, None, 9)
    piano = SafeTrack(mid, 0, 3)

    progression = [
        get_chord('C', 'minor', 3),
        get_chord('Ab', 'major', 3),
        get_chord('Eb', 'major', 3),
        get_chord('Bb', 'major', 3),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        intensity = 0.7 + 0.3 * math.sin(m * 0.3)
        # 弦乐快速重复
        scale_notes = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12]
        for i in range(8):
            sn = scale_notes[i % 4]
            strings.add_note(sn, int(40 * intensity), t + i * beat // 2, beat // 2)
        # 铜管
        if m % 2 == 0:
            brass.add_chord([n + 12 for n in chord], int(55 * intensity), t, measure)
        # 小号旋律
        if m % 4 == 0:
            mel = [chord[0] + 24, chord[2] + 24, chord[1] + 24, chord[0] + 24]
            for i, mn in enumerate(mel):
                trumpet.add_note(mn, int(60 * intensity), t + i * beat, beat)
        # 打击乐
        for b in range(4):
            perc.add_note(36, int(70 * intensity), t + b * beat, beat // 2)
            if b % 2 == 1:
                perc.add_note(38, int(60 * intensity), t + b * beat, beat // 2)
        if m % 4 == 3:
            perc.add_note(49, 80, t + measure - beat // 2, beat)
        # 钢琴低音
        piano.add_note(chord[0], int(50 * intensity), t, measure // 2)
        piano.add_note(chord[0] + 12, int(45 * intensity), t + measure // 2, measure // 2)

    final = total_measures * measure
    for trk in [strings, brass, trumpet, perc, piano]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'downtown.mid'))
    print(f"  完成: downtown.mid")


def generate_suburb():
    """郊区：诡异木管+弦乐泛音，F#小调，70BPM"""
    print("生成: 郊区地图音乐...")
    mid = create_midi(70)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 70

    oboe = SafeTrack(mid, 68, 0)
    clarinet = SafeTrack(mid, 71, 1)
    strings = SafeTrack(mid, 48, 2)
    harp = SafeTrack(mid, 46, 3)
    perc = SafeTrack(mid, None, 9)

    progression = [
        get_chord('Gb', 'minor', 3),
        get_chord('E', 'major', 3),
        get_chord('B', 'minor', 3),
        get_chord('Db', 'major', 3),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        # 双簧管诡异旋律
        if m % 2 == 0:
            mel = [chord[0] + 12, chord[0] + 13, chord[1] + 12, chord[0] + 11, chord[2] + 12]
            for i, mn in enumerate(mel):
                oboe.add_note(mn, 45, t + i * beat * 4 // 5, beat * 4 // 5)
        # 单簧管低音
        clarinet.add_note(chord[0], 35, t, measure)
        # 弦乐泛音
        strings.add_chord([n + 24 for n in chord], 20, t, measure)
        # 竖琴随机琶音
        if random.random() < 0.5:
            arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12]
            for i, an in enumerate(arp):
                harp.add_note(an, 30, t + i * beat, beat)
        # 稀疏打击
        if m % 4 == 0:
            perc.add_note(54, 40, t + beat, beat)
        if m % 6 == 3:
            perc.add_note(73, 35, t + beat * 2, beat * 2)

    final = total_measures * measure
    for trk in [oboe, clarinet, strings, harp, perc]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'suburb.mid'))
    print(f"  完成: suburb.mid")


def generate_nuclear():
    """核电站：工业打击+低沉长号，G小调，85BPM"""
    print("生成: 核电站地图音乐...")
    mid = create_midi(85)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 85

    trombone = SafeTrack(mid, 57, 0)
    tuba = SafeTrack(mid, 58, 1)
    strings = SafeTrack(mid, 48, 2)
    perc = SafeTrack(mid, None, 9)
    synth = SafeTrack(mid, 50, 3)

    progression = [
        get_chord('G', 'minor', 2),
        get_chord('Eb', 'major', 2),
        get_chord('Bb', 'major', 2),
        get_chord('F', 'major', 2),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        trombone.add_chord([n for n in chord[:2]], 50, t, measure)
        tuba.add_note(chord[0] - 12, 60, t, measure)
        strings.add_chord([chord[2] + 24, chord[0] + 25], 25, t, measure)
        synth.add_note(chord[0] - 12, 40, t, measure)
        # 工业打击
        for b in range(4):
            perc.add_note(36, 75, t + b * beat, beat // 2)
            if b == 2:
                perc.add_note(38, 65, t + b * beat, beat // 2)
        if m % 2 == 1:
            perc.add_note(52, 50, t + measure - beat, beat)

    final = total_measures * measure
    for trk in [trombone, tuba, strings, perc, synth]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'nuclear.mid'))
    print(f"  完成: nuclear.mid")


def generate_boss():
    """Boss战斗：全管弦激烈，D小调，140BPM"""
    print("生成: Boss战斗音乐...")
    mid = create_midi(140)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 140

    strings = SafeTrack(mid, 48, 0)
    brass = SafeTrack(mid, 61, 1)
    trumpet = SafeTrack(mid, 56, 2)
    perc = SafeTrack(mid, None, 9)
    piano = SafeTrack(mid, 0, 3)
    timpani = SafeTrack(mid, 47, 4)

    progression = [
        get_chord('D', 'minor', 3),
        get_chord('Bb', 'major', 3),
        get_chord('F', 'major', 3),
        get_chord('C', 'major', 3),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        phase = m % 16
        # 弦乐音阶
        scale = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12,
                 chord[0] + 12, chord[2] + 12, chord[1] + 12, chord[0] + 12]
        for i, sn in enumerate(scale):
            strings.add_note(sn, 50, t + i * beat // 2, beat // 2)
        # 铜管
        if phase < 8:
            brass.add_chord([n + 12 for n in chord], 65, t, measure)
        else:
            brass.add_chord([n + 12 for n in chord], 75, t, measure // 2)
            brass.add_chord([chord[1] + 12, chord[2] + 12, chord[0] + 24], 70,
                            t + measure // 2, measure // 2)
        # 小号
        if m % 4 == 0:
            mel = [chord[0] + 24, chord[2] + 24, chord[0] + 24, chord[2] + 24,
                   chord[1] + 24, chord[0] + 24, chord[2] + 24, chord[0] + 24]
            for i, mn in enumerate(mel):
                trumpet.add_note(mn, 70, t + i * beat // 2, beat // 2)
        # 打击乐
        for b in range(4):
            perc.add_note(36, 80, t + b * beat, beat // 2)
            perc.add_note(38, 70, t + b * beat + beat // 2, beat // 2)
        if m % 4 == 3:
            perc.add_note(49, 90, t + measure - beat // 2, beat)
        # 钢琴
        piano.add_note(chord[0], 60, t, measure // 4)
        piano.add_note(chord[0] + 12, 55, t + measure // 2, measure // 4)
        # 定音鼓
        timpani.add_note(47, 75, t, beat)
        if m % 2 == 1:
            timpani.add_note(45, 65, t + beat * 2, beat)

    final = total_measures * measure
    for trk in [strings, brass, trumpet, perc, piano, timpani]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'boss.mid'))
    print(f"  完成: boss.mid")


def generate_horde():
    """尸潮：急促打击+铜管，E小调，130BPM"""
    print("生成: 尸潮音乐...")
    mid = create_midi(130)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 130

    brass = SafeTrack(mid, 61, 0)
    strings = SafeTrack(mid, 48, 1)
    perc = SafeTrack(mid, None, 9)
    tuba = SafeTrack(mid, 58, 2)
    violin = SafeTrack(mid, 40, 3)

    progression = [
        get_chord('E', 'minor', 3),
        get_chord('C', 'major', 3),
        get_chord('G', 'major', 3),
        get_chord('D', 'major', 3),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        # 铜管短促
        for b in range(4):
            brass.add_chord([n + 12 for n in chord], 60, t + b * beat, beat * 3 // 4)
        # 弦乐快速重复
        for b in range(8):
            strings.add_note(chord[0] + 12, 45, t + b * beat // 2, beat // 2)
        # 打击乐
        for b in range(8):
            perc.add_note(36, 75, t + b * beat // 2, beat // 4)
            if b % 2 == 1:
                perc.add_note(38, 70, t + b * beat // 2, beat // 4)
        # 大号
        tuba.add_note(chord[0] - 12, 60, t, measure // 2)
        tuba.add_note(chord[0] - 12, 55, t + measure // 2, measure // 2)
        # 小提琴急促高音
        if m % 2 == 0:
            for i in range(8):
                violin.add_note(chord[2] + 24, 40, t + i * beat // 2, beat // 4)

    final = total_measures * measure
    for trk in [brass, strings, perc, tuba, violin]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'horde.mid'))
    print(f"  完成: horde.mid")


def generate_tension():
    """紧张氛围：悬疑弦乐颤音，A小调，55BPM"""
    print("生成: 紧张氛围音乐...")
    mid = create_midi(55)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 55

    tremolo = SafeTrack(mid, 44, 0)
    cello = SafeTrack(mid, 42, 1)
    piano = SafeTrack(mid, 0, 2)
    perc = SafeTrack(mid, None, 9)

    progression = [
        get_chord('A', 'minor', 3),
        get_chord('F', 'major', 3),
        get_chord('E', 'major', 3),
        get_chord('A', 'diminished', 3),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        # 颤音弦乐
        trem_notes = [n + 12 for n in chord]
        if m % 2 == 0:
            trem_notes.append(chord[0] + 13)
        tremolo.add_chord(trem_notes, 30, t, measure)
        # 大提琴
        cello.add_note(chord[0] - 12, 40, t, measure)
        # 钢琴随机单音
        if random.random() < 0.4:
            delay = random.randint(0, 3) * beat
            pnote = random.choice([chord[0] + 12, chord[2] + 12, chord[0] + 13])
            piano.add_note(pnote, 35, t + delay, beat * 2)
        # 稀疏打击
        if m % 8 == 3:
            perc.add_note(75, 30, t + beat * 2, beat)
        if m % 12 == 7:
            perc.add_note(46, 25, t + beat, beat * 2)

    final = total_measures * measure
    for trk in [tremolo, cello, piano, perc]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'tension.mid'))
    print(f"  完成: tension.mid")


def generate_gameover():
    """游戏结束：悲伤大提琴，D小调，50BPM"""
    print("生成: 游戏结束音乐...")
    mid = create_midi(50)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 50

    cello = SafeTrack(mid, 42, 0)
    piano = SafeTrack(mid, 0, 1)
    strings = SafeTrack(mid, 48, 2)

    progression = [
        get_chord('D', 'minor', 3),
        get_chord('Bb', 'major', 3),
        get_chord('F', 'major', 3),
        get_chord('C', 'major', 3),
    ]
    cello_melody = [
        [0, 2, 3, 5, 3, 2, 0, -2],
        [3, 5, 7, 5, 3, 2, 0, 0],
        [0, 3, 5, 7, 8, 7, 5, 3],
        [5, 3, 2, 0, -2, 0, 2, 3],
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        pattern = cello_melody[m % 4]
        # 大提琴旋律
        for i, interval in enumerate(pattern):
            note = chord[0] + interval
            vel = 50 + int(10 * math.sin(i * 0.8))
            cello.add_note(note, vel, t + i * beat // 2, beat // 2)
        # 钢琴分解
        arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12]
        for i, an in enumerate(arp):
            piano.add_note(an, 30, t + i * beat, beat)
        # 弦乐
        string_vel = 25 + int(10 * (m % 8) / 8)
        strings.add_chord([n + 12 for n in chord], string_vel, t, measure)

    final = total_measures * measure
    for trk in [cello, piano, strings]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'gameover.mid'))
    print(f"  完成: gameover.mid")


def generate_victory():
    """胜利：悲伤但有希望，C大调，70BPM"""
    print("生成: 胜利音乐...")
    mid = create_midi(70)
    tpb = mid.ticks_per_beat
    beat = tpb
    measure = beat * 4
    total_measures = 56

    strings = SafeTrack(mid, 48, 0)
    piano = SafeTrack(mid, 0, 1)
    trumpet = SafeTrack(mid, 56, 2)
    harp = SafeTrack(mid, 46, 3)

    progression = [
        get_chord('C', 'major', 3),
        get_chord('G', 'major', 3),
        get_chord('A', 'minor', 3),
        get_chord('F', 'major', 3),
    ]

    for m in range(total_measures):
        t = m * measure
        chord = progression[m % 4]
        strings.add_chord([n + 12 for n in chord], 40, t, measure)
        # 钢琴分解
        arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12,
               chord[0] + 12, chord[2] + 12, chord[1] + 12, chord[0] + 12]
        for i, an in enumerate(arp):
            piano.add_note(an, 35, t + i * beat // 2, beat // 2)
        # 小号
        if m % 4 == 0:
            mel = [chord[0] + 24, chord[2] + 24, chord[1] + 24, chord[0] + 24]
            for i, mn in enumerate(mel):
                trumpet.add_note(mn, 50, t + i * beat, beat)
        # 竖琴
        if m % 2 == 1:
            harp_arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[0] + 24]
            for i, hn in enumerate(harp_arp):
                harp.add_note(hn, 30, t + i * beat, beat)

    final = total_measures * measure
    for trk in [strings, piano, trumpet, harp]:
        trk.end(final)
    mid.save(os.path.join(OUTPUT_DIR, 'victory.mid'))
    print(f"  完成: victory.mid")


# ========== 主程序 ==========

if __name__ == '__main__':
    print("=" * 60)
    print("丧尸幸存者 - 黑暗绝望管弦乐MIDI生成器 v2（修复版）")
    print("=" * 60)
    print()

    # 删除旧文件
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith('.mid'):
            os.remove(os.path.join(OUTPUT_DIR, f))
    print("已清除旧MIDI文件")
    print()

    generate_menu()
    generate_school()
    generate_street()
    generate_downtown()
    generate_suburb()
    generate_nuclear()
    generate_boss()
    generate_horde()
    generate_tension()
    generate_gameover()
    generate_victory()

    print()
    print("=" * 60)
    print("全部生成完成！验证文件...")
    print("=" * 60)

    # 验证所有文件
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith('.mid'):
            path = os.path.join(OUTPUT_DIR, f)
            size = os.path.getsize(path)
            try:
                mid = MidiFile(path)
                # 计算总时长（秒）
                total_ticks = 0
                for track in mid.tracks:
                    track_ticks = sum(msg.time for msg in track)
                    total_ticks = max(total_ticks, track_ticks)
                seconds = total_ticks / mid.ticks_per_beat / (mid.tracks[0][0].tempo / 1000000) if mid.tracks[0][0].type == 'set_tempo' else total_ticks / mid.ticks_per_beat / 2
                print(f"  {f:20s} {size:>8.1f}KB  约{seconds:.0f}秒({seconds/60:.1f}分钟)  OK")
            except Exception as e:
                print(f"  {f:20s} {size:>8.1f}KB  损坏: {e}")
