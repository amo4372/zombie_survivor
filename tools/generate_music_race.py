#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
丧尸幸存者 - 争分夺秒模式配乐 MIDI 生成器（v2.5.2 配套）
风格：紧迫感 · 倒计时秒表（嗒嗒声）+ 快节奏脉冲贝斯 + 紧张弦乐 staccato + 警报动机
标准 MIDI Type1 + GM 音色，可被 FL Studio Mobile / BandLab / GarageBand / 音乐工坊等手机 App 直接导入。
复用 generate_music.py 的 Trk 框架与音乐理论工具。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_music import Trk, make_midi, chord, nn, finish_meta

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'music')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# GM 音色
P_STRINGS  = 48   # String Ensemble（紧张同音反复）
P_TRUMPET  = 56   # Trumpet（警报动机）
P_BASS     = 33   # Electric Bass（八分脉冲）
P_TIMPANI  = 47   # Timpani
P_SYNTH    = 83   # Lead 4 (chiffer) 合成警报（更亮更刺耳，适合防空警笛）

# GM 鼓组（channel 9）
KICK = 35; SNARE = 38; HH_CL = 42; HH_OP = 46; RIDE = 51; CRASH = 49
HIQ = 76          # Hi Q：秒表"嗒"高音
CLICK = 81        # 秒表感点击音（Open Hi-Hat 2 / 金属滴答）

# 进行（8 小节循环，D 小调，紧迫）
PROG = ['Dm', 'Bb', 'F', 'A7', 'Dm', 'Bb', 'Gm7', 'A7']
BPM = 165
BARS = 64          # ≈ 64 * 4 * 60/165 ≈ 93 秒循环


def generate_race():
    tpb = 480
    beat = tpb
    e = beat // 2   # 8 分音符 = 240 ticks
    mid = make_midi(BPM, tpb)

    # 轨道名带序号：手机音乐工坊导入后按轨序排列，一眼看清谁是谁
    strings = Trk(mid, P_STRINGS, 0, '1-Strings Staccato')
    brass = Trk(mid, P_TRUMPET, 1, '2-Brass Alarm')
    bass = Trk(mid, P_BASS, 2, '3-Bass Pulse')
    timp = Trk(mid, P_TIMPANI, 3, '4-Timpani')
    synth = Trk(mid, P_SYNTH, 4, '5-Synth Alarm')
    drums = Trk(mid, None, 9, '6-Drums Stopwatch')

    total = BARS * 4 * beat

    for bar in range(BARS):
        t0 = bar * 4 * beat
        ch = PROG[bar % len(PROG)]
        notes = chord(ch, octave=3)
        root = notes[0]
        bass_pitch = root - 12 if root >= 48 else root

        # ---- 秒表嗒嗒：每 8 分音符 tick，反拍 HiQ 高"嗒"，强拍轻 Kick ----
        for i8 in range(8):
            tt = t0 + i8 * e
            if i8 % 2 == 0:
                # 正拍：金属滴答（轻）
                drums.note(CLICK, 58, e // 2, start=tt)
            else:
                # 反拍：Hi Q 高音"嗒"（秒表主声）
                drums.note(HIQ, 72, e // 2, start=tt)
        drums.note(KICK, 84, e // 2, start=t0)          # 每小节强拍轻击（倒计时心跳）
        if bar % 2 == 1:
            drums.note(SNARE, 66, e // 2, start=t0 + 2 * beat)  # 弱拍军鼓（推进）
        if bar % 8 == 7:                                 # 循环末尾 Crash 提神
            drums.note(CRASH, 82, 2 * e, start=t0)

        # ---- 脉冲贝斯：8 分音符根音（紧迫低音引擎）----
        vel_b = 80 + (bar % 4) * 3
        for i8 in range(8):
            bp = bass_pitch - 12 if bass_pitch >= 40 else bass_pitch
            if i8 % 2 == 0:
                bass.note(bp, vel_b, e - 6, start=t0 + i8 * e)
            else:
                bass.note(bp - 12 if bp >= 36 else bp, vel_b - 8, e - 6, start=t0 + i8 * e)

        # ---- 弦乐 staccato：8 分音符同音反复（高音脉搏，紧压感）----
        top = notes[2] + 24          # 和弦五音高八度
        for i8 in range(8):
            strings.note(top, 58 + (i8 % 4) * 4, e - 8, start=t0 + i8 * e)
        if bar % 2 == 0:
            strings.note(top + 2, 62, e - 8, start=t0 + 6 * e)  # 偶发半音摩擦（紧张）

        # ---- 铜管警报动机：每 4 小节上升半音 2 音符短句 ----
        if bar % 4 == 0:
            m1 = notes[0] + 24
            brass.note(m1, 86, e, start=t0)
            brass.note(m1 + 1, 86, e, start=t0 + e)       # 半音上行（警报）
            brass.note(m1, 80, e * 2, start=t0 + 2 * e)
        elif bar % 4 == 2:
            brass.note(notes[1] + 24, 78, e, start=t0)
            brass.note(notes[1] + 24 + 1, 78, e, start=t0 + e)

        # ---- 合成警报：每 8 小节 16 分音符三连上行（防空警报）----
        if bar % 8 == 4:
            s0 = notes[0] + 36
            for j in range(6):
                synth.note(s0 + j * 2, 74, e // 2 - 4, start=t0 + j * (e // 2))
            synth.note(s0 + 13, 84, 2 * e, start=t0 + 6 * (e // 2))

        # ---- 定音鼓：每 2 小节一次重击（心跳加重）----
        if bar % 2 == 0:
            timp.note(bass_pitch, 88, 2 * e, start=t0)

    # ---- 结尾 4 小节：渐弱 + 倒计时归零大"嗒" ----
    tail0 = (BARS - 4) * 4 * beat
    for bar in range(BARS - 4, BARS):
        t0 = bar * 4 * beat
        fade = 1.0 - (bar - (BARS - 4)) * 0.25
        ch = PROG[bar % len(PROG)]
        notes = chord(ch, octave=3)
        root = notes[0]
        bass_pitch = root - 12 if root >= 48 else root
        for i8 in range(8):
            tt = t0 + i8 * e
            v = int(58 * fade)
            if i8 % 2 == 0:
                drums.note(CLICK, int(56 * fade), e // 2, start=tt)
            else:
                drums.note(HIQ, int(70 * fade), e // 2, start=tt)
            bass.note(bass_pitch - 12 if bass_pitch >= 40 else bass_pitch,
                      int(78 * fade), e - 6, start=tt)
            strings.note(notes[2] + 24, int(54 * fade), e - 8, start=tt)
    # 最后一声：大"嗒" + 低音停（倒计时归零）
    drums.note(HIQ, 108, 2 * e, start=tail0)
    drums.note(KICK, 96, e, start=tail0)
    bass.note(nn('D2'), 70, 4 * e, start=tail0)
    strings.note(nn('A4'), 60, 4 * e, start=tail0)

    for tr in (strings, brass, bass, timp, synth, drums):
        tr.end(total)
    # v2.5.7：速度轨收尾（否则部分手机 App 会提示文件不完整）
    finish_meta(mid, total)

    path = os.path.join(OUTPUT_DIR, 'race_urgency.mid')
    mid.save(path)
    return path, BARS, BPM


if __name__ == '__main__':
    path, bars, bpm = generate_race()
    dur = bars * 4 * 60 / bpm
    print(f'已生成: {path}')
    print(f'bpm={bpm}  小节={bars}  时长≈{dur:.1f}s  （Type1 + GM，手机音乐工坊可直接导入）')
