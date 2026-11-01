# -*- coding: utf-8 -*-
"""v2.9.3 快速测试（含跑帧）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

print("[A] 静态检查")
_ui = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
_mi = open("zombie_pkg/mix_input.py", encoding="utf-8").read()
_gc = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check("setup_page_btns" in _gc, "流程页按钮为持久化 Button（主菜单同款）")
check("replay_list_btns" in _gc, "回放列表按钮为持久化 Button")
check("setup_page_btns" in _ui, "渲染层使用 Button")
check("_handle_dd(\"pweapon\"" not in _ui, "多人武器下拉栏已删除")
check("（流程内选择）" in _ui, "武器改为流程内选择")
_mp = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("_fire_spread" in _mp, "开火前固化散布")
check("_fire_spread" in open("weapons.py", encoding="utf-8").read(),
      "fire 读取固化散布")
check("_charge_zoom_active" in open("zombie_pkg/mix_players.py", encoding="utf-8").read(),
      "蓄力拉远时通用 zoom 让行（不再互相覆盖）")
check("if False and getattr(enemy, \"is_boss\"" in _mp, "双子生成已禁用")
check("# from .mix_twinboss import" in open("zombie_pkg/__init__.py", encoding="utf-8").read(),
      "TwinBossMixin 已摘除")
check("draw_twin_boss" not in open("renderer_pkg/draw_play.py", encoding="utf-8").read(),
      "双子渲染已移除")
check("def _open_info_page" in _ui, "武器/角色详情页入口")
check("武器详情" in _ui and "角色详情" in _ui, "装备页有详情按钮")

print("[B] 跑帧：新页面按钮可点")
import pygame
pygame.init()
_screen = pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState as GS
g = Game()
g.begin_setup_flow()
_s0 = g.state
check(_s0 == GS.MAP_SELECT, f"流程起点为地图页（{_s0}）")
for _ in range(3):
    g.draw()
# 注入点击「下一步」(base 520,640,200x56 → 中心 620,668)
def tap(x, y):
    import time as _t
    _t.sleep(0.25)   # 跨过 Button 的 180ms 去抖（防"点一次算两次"）
    g.touch_events = [{"type": "down", "pos": (x, y), "id": 0}]
    g.draw()
    g.touch_events = [{"type": "up", "pos": (x, y), "id": 0}]
    g.draw()
    g.touch_events = []
tap(620, 668)
check(g.state == GS.WEAPON_SELECT_P1, f"点下一步→P1武器页（{g.state}）")
tap(620, 668)
check(g.state == GS.CHARACTER_SELECT_P1, f"再点→P1角色页（{g.state}）")
tap(120, 668)   # 上一步
check(g.state == GS.WEAPON_SELECT_P1, f"点上一步→回武器页（{g.state}）")

print("[C] 跑帧：回放列表按钮")
g2 = Game()
g2.state = GS.REPLAY_LIST
try:
    g2.records.data["saved_replays"] = [
        {"name": "t1.zsr", "path": "replays/saved/t1.zsr",
         "kind": "death", "duration": 12.0, "time": "2026-11-01 10:00"}]
except Exception:
    pass
for _ in range(2):
    g2.draw()
check(len(getattr(g2, "replay_list_btns", {})) >= 2, "列表按钮已创建（播放/删除）")
# 点返回 (base 28,640,180x56 → 118,668)
import time as _t2
_t2.sleep(0.25)
g2.touch_events = [{"type": "down", "pos": (118, 668), "id": 0}]
g2.draw()
g2.touch_events = [{"type": "up", "pos": (118, 668), "id": 0}]
g2.draw()
g2.touch_events = []
check(g2.state == GS.MENU, f"点返回→主菜单（{g2.state}）")

print("[D] 跑帧：双子已移除且不开局报错")
g3 = Game()
check(not hasattr(g3, "spawn_twin_boss"), "Game 无双子生成方法")
check(not hasattr(g3, "draw_twin_boss"), "Game 无双子绘制方法")
try:
    g3.begin_setup_flow()
    g3.state = GS.PLAYING
    g3.start_game()
    for _ in range(60):
        g3.update(0.05)
        g3.draw()
    check(True, "开局跑 60 帧无异常（双子已摘）")
except Exception as _e:
    check(False, f"开局跑帧异常: {_e!r}")

print("[E] 跑帧：详情页可打开并返回")
g4 = Game()
try:
    g4.state = GS.EQUIP_SELECT
    g4.draw()
    g4.renderer._open_info_page("weapon", "P1")
    check(g4.state == GS.WEAPON_SELECT_P1, f"详情页已打开（{g4.state}）")
    for _ in range(2):
        g4.draw()
    import time as _t3
    _t3.sleep(0.25)
    g4.touch_events = [{"type": "down", "pos": (620, 668), "id": 0}]
    g4.draw()
    g4.touch_events = [{"type": "up", "pos": (620, 668), "id": 0}]
    g4.draw()
    g4.touch_events = []
    check(g4.state == GS.EQUIP_SELECT, f"点返回→回装备页（{g4.state}）")
except Exception as _e:
    check(False, f"详情页异常: {_e!r}")

print()
print(f"===== v2.9.3 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
