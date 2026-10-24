#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.0.12 冒烟测试：更新弹窗修复/成就实时结算/图鉴中文名"""
import os, sys, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.getcwd())
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game, GameState
import config

# 1) 更新弹窗按钮位置（设计坐标，弹窗内）
g = Game()
g.state = GameState.MENU
g.update_notice = ("2.0.12", "## v2.0.12\n### 更新器\n- 修复\n[更新包大小 45.2 MB]\n新内容")
g.renderer.render()
from ui import Button
for bx, by, label in [(640-160, 360, "立即更新"), (640+30, 360, "稍后"), (640-65, 440, "更新说明")]:
    b = Button(bx, by, 130, 45, label)
    r = b.get_scaled_rect(g.scale)
    assert 180 < r.y and r.y + r.height < 540, f"{label} 越出弹窗: {r}"
print("1. 更新弹窗按钮位置 OK")

# 2) 更新弹窗"稍后"点击 dismiss（触控链路）
no_btn = Button(670, 360, 130, 45, "稍后")
r = no_btn.get_scaled_rect(g.scale)
pygame.event.post(pygame.event.Event(pygame.FINGERDOWN, x=r.centerx/g.scaled_width, y=r.centery/g.scaled_height, finger_id=1))
pygame.event.post(pygame.event.Event(pygame.FINGERUP, x=r.centerx/g.scaled_width, y=r.centery/g.scaled_height, finger_id=1))
g.handle_events()
g.renderer.render()
assert g.update_notice is None, "稍后未 dismiss"
print("2. 更新弹窗点击有效 OK")

# 3) 成就实时结算
g2 = Game()
g2.start_game()
g2.records.data["total_coins_earned"] = 1500
g2._check_achievements_realtime()
assert g2.records.data["achievements"]["coin_rich"].get("unlocked")
g2.records.data["combo_unlocked"] = ["a", "b", "c"]
g2._check_achievements_realtime()
assert g2.records.data["achievements"]["combo_master"].get("unlocked")
g2.session.data["score"] = 2000000
g2.session.data["difficulty"] = "地狱"  # coef_threshold=2.0 门槛
g2.session.data["time_survived"] = 300
g2.session.data["kills_by_type"] = {"ZOMBIE_NORMAL": 1000}
g2._check_achievements_realtime()
assert g2.records.data["achievements"]["millionaire"].get("unlocked")
print("3. 成就实时结算（coin/combo/millionaire）OK")

# 4) 图鉴中文名
g3 = Game()
g3.start_game()
g3._codex_unlock_toast(True, "ZOMBIE_TANK")
assert g3.ach_toast_queue[-1]["name"] == "坦克僵尸"
print("4. 图鉴中文名 OK")

# 5) 大伤害卡顿复验（快速）
g4 = Game()
g4.start_game()
g4.player.buff_damage_events = [(500, "scythe")] * 50
t0 = time.perf_counter()
for _ in range(60):
    g4.update(0.016)
    g4.renderer.render()
elapsed = (time.perf_counter() - t0) * 1000 / 60
assert elapsed < 30, f"卡顿: {elapsed:.1f}ms"
print(f"5. 大伤害压测 {elapsed:.1f}ms/帧 OK")

print("==== v2.0.12 冒烟全部通过 ====")
