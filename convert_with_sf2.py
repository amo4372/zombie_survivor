#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIDI -> OGG 批量转换（FluidSynth + Timbres of Heaven）
"""

import os
import subprocess
import sys

# 配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MIDI_DIR = os.path.join(BASE_DIR, 'assets', 'music')
FLUIDSYNTH_DIR = os.path.join(BASE_DIR, 'fluidsynth_portable', 'bin')
SOUNDFONT = r"F:\Timbres of Heaven (XGM) 4.00(G).sf2"
SAMPLE_RATE = 44100
OGG_QUALITY = 6  # 0-10

MIDI_FILES = [
    'menu.mid', 'school.mid', 'street.mid', 'downtown.mid', 'suburb.mid',
    'nuclear.mid', 'boss.mid', 'horde.mid', 'tension.mid', 'gameover.mid',
    'victory.mid',
]


def midi_to_wav(midi_path, wav_path):
    """FluidSynth渲染MIDI为WAV"""
    cmd = [
        os.path.join(FLUIDSYNTH_DIR, 'fluidsynth.exe'),
        '-ni',                    # 无交互模式
        '-F', wav_path,           # 输出WAV
        '-r', str(SAMPLE_RATE),  # 采样率
        SOUNDFONT,
        midi_path,
    ]
    # 添加dll目录到PATH
    env = os.environ.copy()
    env['PATH'] = FLUIDSYNTH_DIR + ';' + env.get('PATH', '')

    print(f"  FluidSynth渲染中...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    if result.returncode != 0:
        print(f"  [错误] FluidSynth: {result.stderr[-500:]}")
        return False
    if not os.path.exists(wav_path):
        print(f"  [错误] WAV未生成")
        return False
    size_mb = os.path.getsize(wav_path) / 1024 / 1024
    print(f"  WAV: {size_mb:.1f}MB")
    return True


def wav_to_ogg(wav_path, ogg_path):
    """ffmpeg压缩WAV为OGG"""
    cmd = [
        'ffmpeg', '-y',
        '-i', wav_path,
        '-c:a', 'libvorbis',
        '-q:a', str(OGG_QUALITY),
        ogg_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  [错误] ffmpeg: {result.stderr[-300:]}")
        return False
    size_kb = os.path.getsize(ogg_path) / 1024
    print(f"  OGG: {size_kb:.0f}KB")
    return True


def main():
    print("=" * 60)
    print("MIDI -> OGG 转换（FluidSynth + Timbres of Heaven）")
    print("=" * 60)
    print()

    # 检查
    if not os.path.exists(SOUNDFONT):
        print(f"[错误] SoundFont不存在: {SOUNDFONT}")
        return
    sf_size = os.path.getsize(SOUNDFONT) / 1024 / 1024
    print(f"SoundFont: {os.path.basename(SOUNDFONT)} ({sf_size:.0f}MB)")
    print(f"采样率: {SAMPLE_RATE}Hz, OGG质量: {OGG_QUALITY}")
    print()

    success = 0
    failed = 0

    for i, midi_name in enumerate(MIDI_FILES):
        midi_path = os.path.join(MIDI_DIR, midi_name)
        if not os.path.exists(midi_path):
            print(f"[{i+1}/{len(MIDI_FILES)}] {midi_name} - 跳过")
            continue

        ogg_name = midi_name.replace('.mid', '.ogg')
        ogg_path = os.path.join(MIDI_DIR, ogg_name)
        wav_path = os.path.join(MIDI_DIR, midi_name.replace('.mid', '.wav'))

        if os.path.exists(ogg_path):
            print(f"[{i+1}/{len(MIDI_FILES)}] {midi_name} - 已存在，跳过")
            continue

        print(f"[{i+1}/{len(MIDI_FILES)}] {midi_name}")

        if not midi_to_wav(midi_path, wav_path):
            failed += 1
            print()
            continue

        if not wav_to_ogg(wav_path, ogg_path):
            failed += 1
            if os.path.exists(wav_path):
                os.remove(wav_path)
            print()
            continue

        if os.path.exists(wav_path):
            os.remove(wav_path)

        success += 1
        print(f"  [完成] {ogg_name}")
        print()

    print("=" * 60)
    print(f"完成: 成功{success}, 失败{failed}")
    print("=" * 60)
    print()
    print("输出文件:")
    for f in sorted(os.listdir(MIDI_DIR)):
        if f.endswith('.ogg'):
            size = os.path.getsize(os.path.join(MIDI_DIR, f)) / 1024
            print(f"  {f:20s} {size:>8.0f}KB")


if __name__ == '__main__':
    main()
