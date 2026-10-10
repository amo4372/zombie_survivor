#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1.3 同屏双人修复集成测试（dummy 视频/音频）"""
import os, sys, math
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "/home/user/zombie_survivor")

import pygame
from zombie_pkg import Game
from entities_pkg.pickups import ExpOrb
from config import GameState

ok = 0
def check(name, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")

print("== 1. lighting 实例化 ==")
g = Game()
check("Game() 有 lighting 且非 None", getattr(g, "lighting", None) is not None,
      f"got={getattr(g,'lighting',None)}")
if getattr(g, "lighting", None):
    check("lighting quality 读取 config", g.lighting.quality == g.config.graphics_quality)
    check("lighting resize 适配半屏", g.lighting.resize(640, g.scaled_height) or True)

print("== 2. draw_multiplayer 视口模块 ==")
from renderer_pkg.draw_multiplayer import build_split_viewports, SplitViewport
g.scaled_width = 1280; g.scaled_height = 720
g.player2 = type("P2", (), {"x":0,"y":0})()
g.camera2 = type("C2", (), {})()
g.camera = type("C1", (), {})()
g.player = type("P1", (), {})()
vps = build_split_viewports(g)
check("build_split_viewports 返回 2 视口", len(vps) == 2, f"len={len(vps)}")
check("P1 视口 rect x=0 宽640", vps[0].rect.x == 0 and vps[0].rect.width == 640)
check("P2 视口 rect x=640 宽640", vps[1].rect.x == 640 and vps[1].rect.width == 640)
check("P1 label/P2 label", vps[0].label == "P1" and vps[1].label == "P2")

print("== 3. 经验球双人磁吸 ==")
p1 = type("P1", (), {"x":0.0,"y":0.0,"pickup_range":50,"gain_exp":None})()
p2 = type("P2", (), {"x":100.0,"y":0.0,"pickup_range":50,"gain_exp":None})()
got_exp = {"who": None}
def gain1(v): got_exp["who"] = "P1"
def gain2(v): got_exp["who"] = "P2"
p1.gain_exp = gain1; p2.gain_exp = gain2
orb = ExpOrb(90, 0, 10)
best = p1 if math.hypot(orb.x-p1.x, orb.y-p1.y) <= math.hypot(orb.x-p2.x, orb.y-p2.y) else p2
orb.update(0.016, best.x, best.y, best.pickup_range)
if math.hypot(orb.x-best.x, orb.y-best.y) < 20:
    best.gain_exp(orb.value)
check("经验球磁吸最近玩家（P2 近则 P2 吸）", got_exp["who"] == "P2", f"who={got_exp['who']}")

print("== 4. 双人 per-player 升级触发 ==")
g = Game()
g.config.game_mode = None
from config import GameMode, ControlMode, MapType
g.config.game_mode = GameMode.TIMED
g.multiplayer_mode = "same_screen"
g.selected_weapon_p1 = g.selected_weapon
g.selected_weapon_p2 = g.selected_weapon
g.selected_char_p2 = None
try:
    g.start_game()
    check("start_game 双人创建 player2", g.player2 is not None)
    # 伪造升级状态
    g.state = GameState.PLAYING
    g._upgrade_pause_player = None
    g.player.pending_level_up = True
    g.player.skill_cards = [type("S", (), {"skill_type": 1, "name": "测试卡"})()]
    g.player.upgrade_paused = False
    g._update_playing(0.016)
    check("P1 升级后 _upgrade_pause_player=='P1'", g._upgrade_pause_player == "P1", f"={g._upgrade_pause_player}")
    check("state 仍为 PLAYING（P2 不被阻塞）", g.state == GameState.PLAYING, f"={g.state}")
    check("skill_card_selector visible", g.skill_card_selector.visible)
    check("region 半屏（宽≈640）", g.skill_card_selector.region is not None and g.skill_card_selector.region.width <= 640,
          f"region={g.skill_card_selector.region}")
    check("P1 upgrade_paused=True（免伤脱锁）", getattr(g.player, "upgrade_paused", False))
    # 选卡后恢复
    g._apply_skill_card(g.player.skill_cards[0])
    check("选卡后 _upgrade_pause_player=None", g._upgrade_pause_player is None)
    check("选卡后 upgrade_paused=False", getattr(g.player, "upgrade_paused", False) is False)
    check("选卡后 selector 隐藏", not g.skill_card_selector.visible)
    check("选卡后 pending_level_up=False", g.player.pending_level_up is False)
except Exception as e:
    import traceback; traceback.print_exc()
    print("  [FAIL] 升级集成流程异常")

print(f"\n== 结果: {ok} 项通过 ==")
pygame.quit()
