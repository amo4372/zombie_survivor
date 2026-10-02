#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成王某(BOSS_WANG)专属贴图 boss_wang.png v2
风格：暗色蒙面战士 + 死神镰刀残刃(紫) + 步枪(暗金属)，与其余 Boss 程序化贴图同尺寸(96x96)
v2：增强面部对比、加大发光眼、镰刀弧更醒目、步枪更清晰
运行: SDL_VIDEODRIVER=dummy python3 gen_boss_wang.py
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import math
import pygame

pygame.init()
SIZE = 96
surf = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)

DARK = (22, 24, 32)
HOOD = (30, 32, 42)
SKIN = (222, 190, 160)
SKIN_D = (176, 146, 120)
MASK = (36, 38, 50)
GOLD = (206, 168, 78)
CYAN = (110, 240, 255)
CYAN_HOT = (255, 255, 255)
PURPLE = (172, 72, 220)
PURPLE_L = (226, 150, 252)
GUN = (58, 60, 74)
GUN_D = (40, 42, 54)
RED = (214, 72, 60)

cx, cy = 48, 50

def glow(center, radius, color, alpha=70):
    r = int(radius)
    g = pygame.Surface((r * 2 + 10, r * 2 + 10), pygame.SRCALPHA)
    pygame.draw.circle(g, (*color, alpha), (r + 5, r + 5), r + 4)
    pygame.draw.circle(g, (*color, alpha // 2), (r + 5, r + 5), r + 6)
    surf.blit(g, (center[0] - r - 5, center[1] - r - 5))

# ===== 背景死神镰刀（大紫弧跨头顶，两端露刃尖） =====
glow((40, 30), 34, (120, 40, 190), 55)
pygame.draw.arc(surf, PURPLE_L, (4, -2, 88, 78), math.radians(200), math.radians(340), 10)
pygame.draw.arc(surf, PURPLE, (4, -2, 88, 78), math.radians(200), math.radians(340), 5)
# 刃尖（左上 + 右上，露在头部外侧）
pygame.draw.polygon(surf, PURPLE_L, [(10, 12), (18, 8), (16, 18), (9, 19)])
pygame.draw.polygon(surf, PURPLE_L, [(86, 12), (78, 8), (80, 18), (87, 19)])
# 镰刀柄（右下斜向左上，粗柄+银环）
pygame.draw.line(surf, (88, 72, 54), (16, 90), (66, 40), 8)
pygame.draw.line(surf, (122, 100, 72), (16, 90), (66, 40), 4)
pygame.draw.circle(surf, (150, 154, 172), (64, 42), 6)
pygame.draw.circle(surf, (196, 200, 216), (64, 42), 6, 2)

# ===== 头部 =====
# 兜帽（深色大轮廓）
hood = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
pygame.draw.ellipse(hood, HOOD, (14, 10, 68, 68))
pygame.draw.ellipse(hood, DARK, (14, 10, 68, 68), 3)
surf.blit(hood, (0, 0))
# 面部（冷白肤色椭圆，露眼周与额头）
face = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
pygame.draw.ellipse(face, SKIN, (26, 18, 44, 52))
surf.blit(face, (0, 0))
# 下颚阴影（立体感）
pygame.draw.ellipse(surf, SKIN_D, (29, 46, 38, 24))

# ===== 发光眼（大而锐利的青色狭长眼） =====
glow((35, 38), 9, (70, 210, 255), 90)
glow((61, 38), 9, (70, 210, 255), 90)
# 左眼
pygame.draw.ellipse(surf, CYAN, (26, 34, 16, 8))
pygame.draw.circle(surf, CYAN_HOT, (30, 37), 2)
# 右眼
pygame.draw.ellipse(surf, CYAN, (54, 34, 16, 8))
pygame.draw.circle(surf, CYAN_HOT, (58, 37), 2)

# ===== 面罩（盖住鼻下，露出额与眼） =====
mask = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
pygame.draw.polygon(mask, MASK, [(26, 44), (70, 44), (68, 80), (28, 80)])
surf.blit(mask, (0, 0))
# 面罩金饰条
pygame.draw.line(surf, GOLD, (26, 50), (70, 50), 3)
pygame.draw.circle(surf, GOLD, (48, 50), 3)

# ===== 左颊伤疤（从眼下拉向嘴角） =====
pygame.draw.line(surf, RED, (66, 54), (58, 64), 2)
pygame.draw.line(surf, (150, 46, 40), (66, 54), (58, 64), 1)

# ===== 右侧步枪（枪口朝右上，亮色枪身更清晰） =====
gun = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
pygame.draw.polygon(gun, GUN, [(54, 58), (84, 60), (84, 66), (54, 64)])
pygame.draw.rect(gun, GUN_D, (78, 60, 14, 4), border_radius=1)
pygame.draw.rect(gun, (26, 28, 36), (92, 59, 6, 6))
pygame.draw.polygon(gun, GUN_D, [(60, 64), (68, 64), (66, 78), (58, 78)])
pygame.draw.rect(gun, (84, 88, 102), (66, 52, 12, 6), border_radius=1)
pygame.draw.circle(gun, (150, 220, 235), (71, 55), 2)
pygame.draw.line(gun, GOLD, (54, 58), (84, 60), 2)
surf.blit(gun, (0, 0))

# 头部轮廓描边
pygame.draw.ellipse(surf, (14, 16, 22), (26, 18, 44, 52), 2)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "images", "boss_wang.png")
pygame.image.save(surf, out)
print("saved:", out, os.path.getsize(out), "bytes")
