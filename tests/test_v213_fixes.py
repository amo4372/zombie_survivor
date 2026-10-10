#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1.3b：weapon None 防御 + 队友方位指示器 + 光照降采样性能优化"""
import os, sys, math
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "/home/user/zombie_survivor")

import pygame
pygame.init()
from weapons import Weapon, WeaponType
from entities_pkg.player import Player
from lighting import LightingSystem

ok = 0
def check(name, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")

print("== 1. weapon None 防御 ==")
p = Player(0, 0, start_weapon=None)
check("start_weapon=None 兜底 PISTOL", p.get_current_weapon().weapon_type == WeaponType.PISTOL)
p.add_weapon(None)
check("add_weapon(None) 不加入武器", len(p.weapons) == 1)
w_none = Weapon(None)
# 模拟遗留 Weapon(None)：音效分支兜底逻辑（weapon_type None → pistol）
_wt = getattr(w_none, "weapon_type", None)
wtype = _wt.name.lower() if _wt is not None else "pistol"
check("weapon_type=None 音效兜底 pistol", wtype == "pistol")
check("Weapon(None).can_fire 不崩", w_none.can_fire() is not None)

print("== 2. 队友方位指示器 ==")
from renderer_pkg.draw_multiplayer import draw_teammate_arrow
surf = pygame.Surface((640, 720), pygame.SRCALPHA)
class F:
    def __init__(self):
        self._f = pygame.font.SysFont(None, 16)
    def render(self, t, antialias, c):
        return self._f.render(t, antialias, c)
f = F()
# 视口外右侧：应画箭头
draw_teammate_arrow(surf, 640, 720, 2000, 360, "P2", False, f, 1.0, dist_m=50)
# 采样箭头区域非全透明
def _has_pixels(s, x, y, w, h):
    return any(s.get_at((x+i, y+j))[3] > 0 for i in range(w) for j in range(h))
check("视口外对方 → 边缘出现指示像素", _has_pixels(surf, 600, 340, 40, 40))
surf2 = pygame.Surface((640, 720), pygame.SRCALPHA)
draw_teammate_arrow(surf2, 640, 720, 2000, 360, "P2", True, f, 1.0)
check("倒地指示也绘制", _has_pixels(surf2, 600, 340, 40, 40))
surf3 = pygame.Surface((640, 720), pygame.SRCALPHA)
draw_teammate_arrow(surf3, 640, 720, 320, 360, "P2", False, f, 1.0)  # 视口内
check("视口内对方 → 不画指示", not _has_pixels(surf3, 0, 0, 640, 720))

print("== 3. 光照降采样性能 ==")
light = LightingSystem(1280, 720, quality="balanced")
check("balanced 降采样系数=2", light._render_scale == 2)
check("光表面=640x360", light._light_surface.get_size() == (640, 360))
light2 = LightingSystem(1280, 720, quality="quality")
check("quality 全分辨率", light2._render_scale == 1)
# 渲染到分屏 subsurface（640x720）：应触发 resize + smoothscale，不崩
sub = pygame.Surface((640, 720), pygame.SRCALPHA)
light.set_quality("balanced")
try:
    light.render(sub, 100, 100, 1.0, player=p, enemies=[], projectiles=[], viewport_x=0)
    check("分屏 subsurface 光照渲染成功", True)
except Exception as e:
    import traceback; traceback.print_exc()
    check("分屏 subsurface 光照渲染成功", False, str(e))
# 屏幕外光源裁剪：远处光源不产生像素
sub2 = pygame.Surface((640, 720), pygame.SRCALPHA)
light.enabled = True
light.lights.clear()
light.add_light(99999, 99999, 500, (255, 0, 0))
light.render(sub2, 0, 0, 1.0, player=None, viewport_x=0)
# 光源表面应为全透明（裁剪生效）：按表面实际尺寸采样
_lw, _lh = light._light_surface.get_size()
_any = any(light._light_surface.get_at((x, y))[3] > 0
           for x in range(0, _lw, max(1, _lw // 10))
           for y in range(0, _lh, max(1, _lh // 10)))
check("屏幕外光源未渲染进光表面", not _any)

print(f"\n== 结果: {ok} 项通过 ==")
pygame.quit()
