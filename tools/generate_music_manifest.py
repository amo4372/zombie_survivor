#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配乐 MIDI 轨道清单生成器（v2.5.7 新增）

用途：把 assets/music/*.mid 解析成"每个轨道该用什么乐器"的人话清单，
方便在手机「音乐制作工坊」里逐轨替换音色 / 导出最终 OGG。

用法：
    python3 generate_music_manifest.py                     # 处理争分夺秒配乐
    python3 generate_music_manifest.py assets/music/xxx.mid
输出：
    控制台表格 + <同名>.tracks.txt（UTF-8，附带 GM 音色对照）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from midi_lite import read_midi

# ============ General MIDI 音色表（0-127） ============
GM_PATCHES = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
    "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Bottle Blow", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)",
    "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto",
    "Kalimba", "Bagpipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot",
]

GM_DRUM_NAMES = {
    35: "Acoustic Bass Drum", 36: "Bass Drum 1", 37: "Side Stick", 38: "Acoustic Snare",
    39: "Hand Clap", 40: "Electric Snare", 41: "Low Floor Tom", 42: "Closed Hi-Hat",
    43: "High Floor Tom", 44: "Pedal Hi-Hat", 45: "Low Tom", 46: "Open Hi-Hat",
    47: "Low-Mid Tom", 48: "Hi-Mid Tom", 49: "Crash Cymbal 1", 50: "High Tom",
    51: "Ride Cymbal 1", 52: "Chinese Cymbal", 53: "Ride Bell", 54: "Tambourine",
    55: "Splash Cymbal", 56: "Cowbell", 57: "Crash Cymbal 2", 58: "Vibraslap",
    59: "Ride Cymbal 2", 60: "Hi Bongo", 61: "Low Bongo", 62: "Mute Hi Conga",
    63: "Open Hi Conga", 64: "Low Conga", 65: "High Timbale", 66: "Low Timbale",
    67: "High Agogo", 68: "Low Agogo", 69: "Cabasa", 70: "Maracas",
    71: "Short Whistle", 72: "Long Whistle", 73: "Short Guiro", 74: "Long Guiro",
    75: "Claves", 76: "Hi Wood Block", 77: "Low Wood Block", 78: "Mute Cuica",
    79: "Open Cuica", 80: "Mute Triangle", 81: "Open Triangle", 84: "Open Hi Conga",
}

# 轨道用途说明（按本项目各曲目的编写意图给出参考配色/角色）
ROLE_HINTS = {
    "Strings Staccato": "紧张同音反复的弦乐脉冲（主推动力）",
    "Brass Alarm": "铜管警报动机（每 4 小节半音上行，制造警报感）",
    "Bass Pulse": "八分音符脉冲贝斯（低音引擎，压迫感来源）",
    "Timpani": "定音鼓重击（心跳加重 / 段落落点）",
    "Synth Alarm": "合成器警报（防空警笛式的三连上行）",
    "Drums Stopwatch": "鼓组：秒表“嗒嗒”滴答 + 军鼓/踩镲推进",
}


def _fmt_time(sec):
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"


def analyze(midi_path):
    hdr, tracks = read_midi(midi_path)
    bpm = 120.0
    for tick, typ, d in tracks[0]:
        if typ == "set_tempo":
            bpm = 60000000.0 / float(d.get("tempo", 500000))
            break
    tpb = hdr.get("division", 480) or 480
    total_tick = 0
    for tr in tracks:
        if tr:
            total_tick = max(total_tick, tr[-1][0])
    dur = total_tick / float(tpb) * (60.0 / bpm)

    rows = []
    for idx, tr in enumerate(tracks):
        name = ""
        prog = None
        ch = None
        notes = 0
        pitches = set()
        for tick, typ, d in tr:
            if typ == "track_name":
                name = d.get("name", "") or ""
            elif typ == "program_change":
                prog = d.get("program")
                ch = d.get("channel")
            elif typ == "note_on" and d.get("velocity", 0) > 0:
                notes += 1
                pitches.add(d.get("note"))
                if ch is None:
                    ch = d.get("channel")
        rows.append({
            "idx": idx, "name": name, "program": prog, "channel": ch,
            "notes": notes, "pitches": pitches,
            "is_drum": (prog is None and notes > 0),
            "is_meta": notes == 0 and not name,
        })
    return hdr, bpm, tpb, dur, total_tick, rows


def render_text(midi_path, hdr, bpm, tpb, dur, total_tick, rows):
    lines = []
    lines.append("=" * 78)
    lines.append(f"配乐 MIDI 轨道清单: {os.path.basename(midi_path)}")
    lines.append("=" * 78)
    lines.append(f"文件类型      : Standard MIDI File Type {hdr.get('format')}（多轨，App 可逐轨编辑）")
    lines.append(f"轨道数        : {hdr.get('ntrks')}（含 1 条速度轨）")
    lines.append(f"时间分辨率    : {tpb} ticks / quarter")
    lines.append(f"速度          : {bpm:.1f} BPM · 4/4")
    lines.append(f"总时长        : {_fmt_time(dur)}（{dur:.1f} 秒 / {total_tick} ticks）")
    lines.append("")
    lines.append("-" * 78)
    lines.append("每轨乐器对照（GM 音色号 = 手机 App 里可选的标准 GM 音色编号）")
    lines.append("-" * 78)
    for r in rows:
        if r["is_meta"]:
            continue
        head = f"轨道 {r['idx']}"
        if r["is_drum"]:
            patch = "GM 鼓组（Drum Kit，App 里选「Standard Kit / 鼓组」）"
            pnum = "—"
            pnum1 = "—"
        else:
            pnum = str(r["program"])
            pnum1 = str(r["program"] + 1)   # GM 面板常见的是 1 基编号
            patch = GM_PATCHES[r["program"]] if 0 <= r["program"] < len(GM_PATCHES) else "?"
        lines.append("")
        lines.append(f"{head}  「{r['name']}」")
        lines.append(f"    MIDI 通道    : {r['channel'] + 1 if r['channel'] is not None else '—'}"
                     f"（0 基通道 {r['channel'] if r['channel'] is not None else '—'}）")
        lines.append(f"    音色号 GM    : {pnum} → {patch}")
        if pnum1 != "—":
            lines.append(f"    （面板 1 基编号: GM {pnum1}）")
        if r["is_drum"]:
            used = sorted(r["pitches"])
            lines.append("    使用的鼓件    : " + "、".join(
                f"{GM_DRUM_NAMES.get(p, 'Note' + str(p))}({p})" for p in used))
        else:
            if r["pitches"]:
                lo, hi = min(r["pitches"]), max(r["pitches"])
                lines.append(f"    音域         : MIDI {lo}~{hi}")
        lines.append(f"    音符数       : {r['notes']}")
        for k, v in ROLE_HINTS.items():
            if k.lower() in r["name"].lower():
                lines.append(f"    作用         : {v}")
                break
    lines.append("")
    lines.append("-" * 78)
    lines.append("导入 / 导出建议")
    lines.append("-" * 78)
    lines.append("1) 手机「音乐制作工坊」导入：选 MIDI 文件 → 6 条乐器轨会按顺序出现，")
    lines.append("   鼓组轨需在 App 里指定为 Standard Kit（GM 鼓组通道）。")
    lines.append("2) 保留 GM 音色号，导出时选 44.1kHz / 立体声 / OGG 或 WAV。")
    lines.append("3) 成品放回 assets/music/race_urgency.ogg（文件名必须一致），")
    lines.append("   游戏会自动加载；未放文件时会回退到地图原声，不会报错。")
    lines.append("4) 循环点：曲子是 8 小节循环 + 结尾 4 小节收束，直接循环播放即可。")
    lines.append("")
    lines.append("-" * 78)
    lines.append("手机端「音乐制作工坊」配置要点（据该 App 公开教程与 v2.0.6x 更新日志：支持导入 MIDI + SoundFont）")
    lines.append("-" * 78)
    lines.append("· 导入 MIDI：首页左上角菜单 → 下滑找到「导入MIDI文件」→ 选 race_urgency.mid")
    lines.append("· 音色：建议每条轨都用「采样乐器 / SoundFont 播放器」+ 同一个 GM SoundFont，")
    lines.append("  这样 program change 里的 GM 编号才能 1:1 对上（本 MIDI 只用 bank 0 的 128 音色号）")
    lines.append("· 鼓组轨（第 6 条）在 MIDI 里是第 10 通道，SF2 侧要挂 Standard Kit 预设")
    lines.append("· 复音数：弦乐/贝斯轨 8~16 够用，鼓组 4~8 即可（太高吃 CPU 会卡）")
    lines.append("· 导出：OGG（44.1kHz 立体声）→ 改名 race_urgency.ogg → 放 assets/music/")
    lines.append("")
    lines.append("· 常见坑：6 条轨全挂同一个 SF2，出来全是钢琴 ——")
    lines.append("  ① SF2 是「音色库」不是单乐器：一个文件里有几十~几百个预设(preset)，")
    lines.append("     加载文件 ≠ 选预设；不选就全是该 SF2 的默认预设（多半是钢琴）")
    lines.append("  ② 部分 App 导入 MIDI 时不套用 program change → 必须手动逐轨选预设")
    lines.append("  ③ 若 SF2 不是 GM 排列（patch 顺序不对应 GM 编号），按「名字」挑别按编号挑")
    lines.append("  ④ 鼓组轨：MIDI 第 10 通道对应 SF2 的 Standard Kit 预设（bank128/preset0）")
    lines.append("  → 30 秒自检：导入 assets/music/gm_timbre_check.mid，6 段接力听音色对不对")
    lines.append("")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    if args:
        path = args[0]
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "assets", "music", "race_urgency.mid")
    if not os.path.exists(path):
        print(f"[错误] 找不到 MIDI: {path}")
        return 1
    hdr, bpm, tpb, dur, total_tick, rows = analyze(path)
    text = render_text(path, hdr, bpm, tpb, dur, total_tick, rows)
    print(text)
    out = os.path.splitext(path)[0] + ".tracks.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"清单已写入: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
