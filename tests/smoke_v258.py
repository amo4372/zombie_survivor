#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.5.8 冒烟测试：真实跑帧验证开发者模式多人化 + 镜像容错

在 dummy 视频驱动下真实启动游戏，逐条压测新代码路径不崩溃/行为正确：
1. 每玩家独立开发者面板（P1/P2 状态、按钮、视口互不干扰）
2. 免疫僵尸伤害但不免疫玩家伤害（抗尸）
3. TP 到某个玩家（多人 + PvP）
4. PvP 秒杀敌对玩家 / 面板按阵营
5. F9/F10 面板开关 + 暂停菜单 P2 面板按钮
6. 更新器镜像代理候选节点（多节点 + 失败换节点）
"""
import os
import sys
import math

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, _ROOT)

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game import Game, GameState
from config import GameMode, ControlMode
from entities_pkg.player import Player

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


def frames(g, n, draw=True):
    for _ in range(n):
        g.update(1 / 60)
        if draw:
            g.renderer.render()


g = Game()
g.start_game()
g.state = GameState.PLAYING
g.dev_mode = True
g.multiplayer_mode = "same_screen"
if g.player2 is None:
    g.player2 = Player(g.player.x + 300, g.player.y)
    g.camera2 = type(g.camera)(640, 720)

# ======================================================================
print("[1] 每玩家独立开发者状态")
st1, st2 = g._dev_state(1), g._dev_state(2)
check(st1 is not st2, "P1/P2 状态对象独立")
check(g._dev_player_indices() == [1, 2], "识别到 P1/P2 两个玩家")
g._dev_action(1, "god")
check(st1.god and not st2.god, "P1 无敌不影响 P2")
g._dev_action(2, "zombie_immune")
check(st2.zombie_immune and not st1.zombie_immune, "P2 抗尸不影响 P1")
check(g.player2.dev_zombie_immune and not g.player.dev_zombie_immune, "状态已同步到各自实体")
g._dev_action(1, "god")
g._dev_action(2, "zombie_immune")

# ======================================================================
print("[2] 免疫僵尸伤害但不免疫玩家伤害")
g._dev_action(1, "zombie_immune")
g.player.hp = g.player.max_hp
g.player.invincible_timer = 0
_hp0 = g.player.hp
g.player.take_damage(25, damage_type="melee", source="zombie")
check(g.player.hp == _hp0, f"僵尸伤害被挡住（hp={g.player.hp:.0f}）")
g.player.take_damage(25, damage_type="ranged", source="player", bypass_dodge=True)
check(g.player.hp < _hp0, f"玩家伤害照吃（hp={g.player.hp:.0f}）")
g._dev_action(1, "zombie_immune")

# ======================================================================
print("[3] TP 到某个玩家")
g.player.x, g.player.y = 300.0, 300.0
g.player2.x, g.player2.y = 2400.0, 2400.0
g._dev_action(1, "tp_target")
check(st1.tp_target == 2, f"TP 目标循环到 P2（tp={st1.tp_target}）")
_ok, _msg = g._dev_teleport_to(1, st1.tp_target)
check(_ok, f"传送执行成功（{_msg}）")
check(math.hypot(g.player.x - g.player2.x, g.player.y - g.player2.y) < 200,
      "P1 已落在 P2 身边")
# 切到 P2 的面板传送 P2 → P1
g._dev_action(2, "tp_target")
_ok2, _msg2 = g._dev_teleport_to(2, st2.tp_target)
check(_ok2, f"P2 面板也能传送（{_msg2}）")
check(math.hypot(g.player2.x - g.player.x, g.player2.y - g.player.y) < 200,
      "P2 已落在 P1 身边")

# ======================================================================
print("[4] 面板布局与互不干扰")
st1.panel_open = True
st2.panel_open = True
g._rebuild_dev_buttons(1)
g._rebuild_dev_buttons(2)
check(g.dev_states[1].buttons is not g.dev_states[2].buttons, "P1/P2 按钮列表独立")
_p1 = g._dev_panel_positions(1)
_p2 = g._dev_panel_positions(2)
check(all(x < 640 for x, _ in _p1), "P1 面板按钮都在左半屏")
check(all(x >= 640 for x, _ in _p2), "P2 面板按钮都在右半屏")
check(len(_p1) == len(_p2) == len(g.dev_states[1].buttons), "按钮数量与面板一致")
# 面板太矮时自动压缩/双列
_gc = g
_saved_rect = _gc._dev_viewport_rect
_gc._dev_viewport_rect = lambda i=1: pygame.Rect(0, 0, 320, 300)
_p1s = _gc._dev_panel_positions(1)
check(all(0 <= x < 320 for x, _ in _p1s), "窄视口下按钮仍不越界")
_gc._dev_viewport_rect = _saved_rect

# ======================================================================
print("[5] PvP 开发者能力")
g.config.pvp_enabled = True
g.config.pvp_teams = 2
g.player.team_id = 0
g.player2.team_id = 1
g._rebuild_dev_buttons(1)
_txts = [b.text for b in g.dev_states[1].buttons]
check("秒杀敌对" in _txts, f"PvP 面板出现「秒杀敌对」（{len(_txts)} 个按钮）")
g.player2.alive = True
g.player2.hp = 100
_n = g._dev_kill_hostile_players(1)
check(_n >= 1 and not g.player2.alive, f"敌对玩家被秒杀（{_n} 个）")
# 同阵营不杀
g.player2.alive = True
g.player2.team_id = 0
_n2 = g._dev_kill_hostile_players(1)
check(_n2 == 0 and g.player2.alive, "同阵营玩家不会被误杀")

# ======================================================================
print("[6] 键盘/暂停菜单开关")
g._dev_state(1).panel_open = False
g._dev_state(2).panel_open = False
_ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F9)
g._handle_dev_keys([_ev])
check(g._dev_state(1).panel_open, "F9 打开 P1 面板")
g._handle_dev_keys([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F9)])
check(not g._dev_state(1).panel_open, "F9 再按关闭 P1 面板")
g._handle_dev_keys([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F10)])
check(g._dev_state(2).panel_open, "F10 打开 P2 面板")
_pause_txts = [b.text for b in g.pause_buttons]
check("P2开发者面板" in _pause_txts, "暂停菜单有 P2 开发者面板按钮")

# ======================================================================
print("[7] 更新器镜像代理")
import updater
_url = "https://github.com/amo4372/zombie_survivor/releases/download/v2.5.7/x.zip"
_cands = updater._mirror_candidates(_url)
check(len(_cands) >= 4, f"候选镜像节点 {len(_cands)} 个")
check(any("ghfast.top" in c for c in _cands), "含 ghfast.top 镜像")
check(any("gh-proxy" in c for c in _cands), "含 gh-proxy 镜像")
check(_cands[0] == _url, "原始 GitHub 节点在列表中")

# ======================================================================
print("[8] 全流程跑帧（双面板 + PvP + 毒圈）")
g.config.pvp_enabled = True
g.config.game_mode = GameMode.ENDLESS
g._init_pvp_zone()
g._dev_state(1).panel_open = True
g._dev_state(2).panel_open = True
g._rebuild_dev_buttons(1)
g._rebuild_dev_buttons(2)
try:
    frames(g, 90)
    check(True, "90 帧双面板 PvP 跑帧无异常")
except Exception as e:
    check(f"跑帧异常: {e!r}", False)

# 单人模式也要能画面板
g.player2 = None
g.camera2 = None
g._dev_state(2).panel_open = False
try:
    frames(g, 30)
    check(True, "30 帧单人模式面板跑帧无异常")
except Exception as e:
    check(f"单人跑帧异常: {e!r}", False)

print()
print(f"===== SMOKE 结果: {PASS} 通过, {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
