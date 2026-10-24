#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GM 音色自检 MIDI（v2.5.7 新增）

用途：30 秒验证「音乐制作工坊」到底认不认 MIDI 里的 program change。
原理：6 条轨依次独奏（每轨 2 小节接力），每轨 2~4 个音 + 明确音区，
      听到的音色应该 = 轨名标注的 GM 乐器。

听感预期（0 基 GM 号 / 1 基 GM 号）：
  1-Strings   48 / 49  String Ensemble 1  弦乐群齐奏
  2-Brass     56 / 57  Trumpet            小号
  3-Bass      33 / 34  Electric Bass      电贝斯
  4-Timpani   47 / 48  Timpani            定音鼓
  5-Synth     83 / 84  Lead 4 (chiff)     合成拨弦
  6-Drums     通道10   GM 鼓组            底鼓/军鼓/踩镲

若 6 段听起来全是钢琴 → App 忽略了 program change（或者你挂的 SF2 不是 GM 排列），
需要在每条轨的「编辑乐器音色」里手动挑对应预设。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from midi_lite import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'music')
os.makedirs(OUT_DIR, exist_ok=True)

TPB = 480
BEAT = TPB
BAR = BEAT * 4
BPM = 120

# (轨名, 0基GM号, [(midi音高, 起始拍, 时长拍)], 是否鼓组)
SPEC = [
    ("1-Strings Staccato", 48, [(69, 0, 2), (72, 2, 2)], False),
    ("2-Brass Alarm", 56, [(74, 0, 2), (76, 2, 2)], False),
    ("3-Bass Pulse", 33, [(38, 0, 2), (36, 2, 2)], False),
    ("4-Timpani", 47, [(43, 0, 4)], False),
    ("5-Synth Alarm", 83, [(86, 0, 2), (90, 2, 2)], False),
    ("6-Drums Stopwatch", None, [(35, 0, 1), (38, 1, 1), (42, 2, 1), (35, 3, 1)], True),
]


def build():
    mid = MidiFile(ticks_per_beat=TPB)

    # ---- 速度轨 ----
    meta = MidiTrack()
    meta.append(MetaMessage('set_tempo', tempo=bpm2tempo(BPM), time=0))
    meta.append(MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    mid.tracks.append(meta)

    # ---- 6 条乐器轨（依次接力，每轨 2 小节）----
    for idx, (name, prog, notes, is_drum) in enumerate(SPEC):
        tr = MidiTrack()
        tr.append(MetaMessage('track_name', name=name, time=0))
        if prog is not None:
            tr.append(Message('program_change', program=prog, channel=idx, time=0))
        base = idx * 2 * BAR
        last = 0
        for pitch, start_beat, dur_beat in notes:
            t = base + int(start_beat * BEAT)
            tr.append(Message('note_on', note=pitch, velocity=96, channel=idx, time=t - last))
            last = t
            tr.append(Message('note_off', note=pitch, velocity=0, channel=idx,
                              time=int(dur_beat * BEAT) - 12))
            last = t + int(dur_beat * BEAT) - 12
        tr.append(MetaMessage('end_of_track', time=0))
        mid.tracks.append(tr)

    total = len(SPEC) * 2 * BAR
    meta.append(MetaMessage('end_of_track', time=total))
    return mid, total


def main():
    mid, total = build()
    path = os.path.join(OUT_DIR, 'gm_timbre_check.mid')
    mid.save(path)
    print(f'已生成: {path}')
    print(f'bpm={BPM}  6 轨接力  每轨 2 小节  总时长≈{len(SPEC) * 2 * 4 * 60 / BPM:.0f}s')
    return path


if __name__ == '__main__':
    main()
