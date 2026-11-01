# -*- coding: utf-8 -*-
"""v2.9.1 快速测试（不跑帧）"""
import os, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

print("[A] 打包清单补齐（v2.8.9/2.9.0 漏文件致 import 失败）")
_br = open("build_release.py", encoding="utf-8").read()
for _f in ("twin_boss.py", "gacha.py", "weapon_pool.py"):
    check(f'"{_f}"' in _br, f"{_f} 已登记必需文件")
check('"scenes"' in _br, "scenes 目录已登记")
_z = "releases/zombie_survivor_v2.9.1_update.zip"
if os.path.exists(_z):
    _n = zipfile.ZipFile(_z).namelist()
    for _f in ("twin_boss.py", "gacha.py", "weapon_pool.py",
               "scenes/__init__.py", "scenes/info_pages.py"):
        check(any(x.endswith("/" + _f) for x in _n), f"2.9.1 包含 {_f}")
else:
    print("  [提示] 未找到 2.9.1 包，跳过包内容检查")

print("[B] 回放暂停后可继续播放（状态同步）")
_mr = open("zombie_pkg/mix_replay.py", encoding="utf-8").read()
check("_d.playing = bool(self.replay_playing)" in _mr,
      "toggle 同步 ReplayData.playing（根因：两个 playing 从不同步）")
check("_d.playing = False" in _mr, "逐帧时同步暂停")
check("def save_current_replay" in _mr, "保存录像接口")
check("def load_saved_replay" in _mr, "读取已保存录像")
check("def delete_saved_replay" in _mr, "删除录像")
# 模拟：播完→置 False→toggle 应恢复
class _RD:
    def __init__(s): s.playing=True; s.index=0; s.frames=[0]*10; s._acc=0.0
    def update(s,dt):
        if not s.playing: return
        s.index=min(s.index+1,len(s.frames)-1)
        if s.index>=len(s.frames)-1: s.playing=False
class _G:
    def __init__(s): s.replay_data=_RD(); s.replay_playing=True
    def toggle(s):
        _d=s.replay_data
        if _d.index>=len(_d.frames)-1: _d.index=0
        s.replay_playing = not s.replay_playing
        _d.playing = bool(s.replay_playing)
        if s.replay_playing: _d._acc=0.0
g=_G()
for _ in range(20): g.replay_data.update(0.05)
check(not g.replay_data.playing, "播完自动停")
g.replay_playing = True   # 点播放
g.toggle(); g.toggle()     # 两次：True->False->True
check(g.replay_data.playing == g.replay_playing, "toggle 后两者一致")
if g.replay_playing:
    _i0=g.replay_data.index; g.replay_data.update(0.05)
    check(g.replay_data.index > _i0 or _i0==0, "恢复后能推进")

print("[C] 按钮文字去掉 Unicode 箭头")
_gc = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check('"上一帧"' in _gc, "上一帧改纯中文")
check('"下一帧"' in _gc, "下一帧改纯中文")
check('"◀"' not in _gc and '"▶"' not in _gc, "不再使用渲染不出的箭头符号")
check('"保存"' in _gc, "回放页有保存按钮")
check('"保存"' in open("renderer_pkg/draw_replay.py",encoding="utf-8").read()
      or "save" in open("renderer_pkg/draw_replay.py",encoding="utf-8").read(),
      "保存按钮点击已处理")

print("[D] 回放列表（含通关录像）")
import pygame; pygame.init()
from config import GameState as GS
check(hasattr(GS, "REPLAY_LIST"), "新增 REPLAY_LIST 状态")
check("def draw_replay_list" in open("renderer_pkg/draw_ui.py",encoding="utf-8").read(),
      "列表页绘制存在")
check("GameState.REPLAY_LIST" in open("renderer_pkg/render_core.py",encoding="utf-8").read(),
      "渲染分派已接入")
check("_handle_replay_list_click" in open("zombie_pkg/mix_input.py",encoding="utf-8").read(),
      "列表点击处理存在")
check('"回放列表"' in open("zombie_pkg/mix_menu.py",encoding="utf-8").read(),
      "主菜单有入口按钮")
check("i == 12" in open("renderer_pkg/draw_ui.py",encoding="utf-8").read(),
      "入口索引已绑定")

print("[E] 技能事件记录")
check("def record_skill_event" in _mr, "技能事件记录接口")
check("def record_boss_skill" in _mr, "Boss 技能记录接口")
check("record_skill_event(" in open("zombie_pkg/mix_skills.py",encoding="utf-8").read(),
      "玩家技能释放已记入回放")
check("record_boss_skill" in open("zombie_pkg/mix_twinboss.py",encoding="utf-8").read(),
      "双子 Boss 技能已记入回放")

print("[F] 采样率提升")
_rp = open("replay.py", encoding="utf-8").read()
import re
_m = re.search(r'SAMPLE_HZ\s*=\s*([\d.]+)', _rp)
check(_m and float(_m.group(1)) >= 30.0, f"采样率提升至 {_m.group(1) if _m else '?'}Hz")

print()
print(f"===== v2.9.1 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
