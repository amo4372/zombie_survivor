#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1.5：低画质档（performance/balanced）关闭动态光照——修复黑屏+性能"""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "/home/user/zombie_survivor")

import pygame
pygame.init()
from lighting import LightingSystem

ok = 0
def check(name, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")

print("== 1. 低档关闭动态光照 ==")
for q, expect in (("performance", False), ("balanced", False), ("quality", True)):
    ls = LightingSystem(1280, 720, quality=q)
    check(f"{q} → enabled={expect}", ls.enabled == expect, f"got={ls.enabled}")

print("== 2. 黑屏回归：低档 render 不改屏幕 ==")
for q in ("performance", "balanced"):
    ls = LightingSystem(1280, 720, quality=q)
    screen = pygame.Surface((1280, 720))
    screen.fill((255, 0, 0))  # 红色参考画面
    before = screen.copy()
    ls.add_light(640, 360, 300, (255, 255, 255))
    ls.render(screen, 0, 0, 1.0, player=None, enemies=[], projectiles=[], viewport_x=0)
    same = all(screen.get_at((x, y)) == before.get_at((x, y))
               for x in range(0, 1280, 160) for y in range(0, 720, 90))
    check(f"{q} 画面不被覆盖（无黑屏）", same)

print("== 3. 画质切换同步 ==")
ls = LightingSystem(1280, 720, quality="balanced")
check("初始 balanced 关闭", ls.enabled is False)
ls.set_quality("quality")
check("切到 quality 启用", ls.enabled is True)
ls.set_quality("performance")
check("切回 performance 关闭", ls.enabled is False)

print("== 4. quality 档光照仍工作 ==")
ls = LightingSystem(1280, 720, quality="quality")
screen = pygame.Surface((1280, 720), pygame.SRCALPHA)
screen.fill((255, 255, 255, 255))
ls.add_light(640, 360, 200, (255, 255, 255), intensity=1.5)
ls.render(screen, 0, 0, 1.0, player=None, enemies=[], projectiles=[], viewport_x=0)
_any_dark = any(screen.get_at((x, y))[0] < 250 for x in range(0, 1280, 128) for y in range(0, 720, 72))
check("quality 档渲染出暗化层", _any_dark)

print(f"\n== 结果: {ok} 项通过 ==")
pygame.quit()
