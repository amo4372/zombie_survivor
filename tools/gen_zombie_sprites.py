#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.9.17 程序化生成图鉴新增类别僵尸贴图。

画风与游戏内 `_enemy_style` 一致：暗色破损剪影 + 类型色幽光 +
高光边缘 + 冰晶/电弧/毒雾等类型装饰。生成 96x96 透明 PNG，
运行时由 assets.get_image 缓存加载；无贴图时回退原有程序化圆体绘制。
"""
import os, math, random
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "images", "zombies")

# key -> (主体色, 幽光色, 边缘色, 装饰)
STYLES = {
    "frost":    ((74, 104, 128), (150, 215, 255), (205, 240, 255), "ice"),
    "electric": ((72, 80, 104), (140, 200, 255), (220, 235, 255), "bolt"),
    "poison":   ((58, 92, 52),  (120, 220, 90),  (190, 245, 150), "bubble"),
    "phantom":  ((66, 58, 92),  (180, 140, 240), (220, 200, 255), "wisp"),
    "shield":   ((84, 84, 92),  (200, 205, 215), (235, 238, 245), "shield"),
    "healer":   ((86, 66, 76),  (255, 150, 170), (255, 210, 220), "cross"),
    "exploder": ((104, 62, 44), (255, 140, 60),  (255, 205, 140), "flame"),
    "splitter": ((78, 72, 58),  (220, 200, 120), (245, 235, 180), "crack"),
}
SIZE = 96


def build(key, body, glow, edge, deco, seed):
    random.seed(seed)
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    cx, cy = SIZE // 2, SIZE // 2
    # 幽光（局部小 Surface，不产生整屏开销）
    gs = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    for r, a in ((40, 20), (30, 30), (20, 42)):
        pygame.draw.circle(gs, (*glow, a), (cx, cy), r)
    s.blit(gs, (0, 0))
    # 躯干：不规则多边形（破损剪影）
    pts = []
    for i in range(11):
        a = i / 11 * math.pi * 2
        rr = 23 + random.uniform(-4, 5)
        pts.append((cx + math.cos(a) * rr * 0.82,
                    cy + math.sin(a) * rr * 1.08 + 4))
    pygame.draw.polygon(s, body, pts)
    pygame.draw.polygon(s, (*edge, 150), pts, 2)
    # 头部
    pygame.draw.ellipse(s, tuple(min(255, c + 18) for c in body),
                        (cx - 12, cy - 30, 24, 21))
    pygame.draw.ellipse(s, (*edge, 120), (cx - 12, cy - 30, 24, 21), 2)
    # 眼睛（两点类型色）
    pygame.draw.circle(s, glow, (cx - 5, cy - 21), 2)
    pygame.draw.circle(s, glow, (cx + 5, cy - 21), 2)
    # 手臂
    pygame.draw.line(s, body, (cx - 16, cy - 2), (cx - 30, cy + 14), 6)
    pygame.draw.line(s, body, (cx + 16, cy - 2), (cx + 30, cy + 12), 6)
    # 类型装饰
    if deco == "ice":
        for i in range(6):
            a = i / 6 * math.pi * 2
            x, y = cx + math.cos(a) * 30, cy + math.sin(a) * 32
            pygame.draw.line(s, (*glow, 190), (x, y),
                             (x + math.cos(a) * 8, y + math.sin(a) * 8), 2)
        pygame.draw.polygon(s, (*glow, 90),
                            [(cx - 8, cy - 8), (cx, cy - 18), (cx + 8, cy - 8), (cx, cy + 2)])
    elif deco == "bolt":
        for i in range(3):
            x = cx - 24 + i * 22
            pygame.draw.lines(s, (*glow, 210), False,
                              [(x, cy - 34), (x + 8, cy - 20), (x + 2, cy - 18),
                               (x + 12, cy - 4)], 2)
    elif deco == "bubble":
        for i in range(7):
            x = cx + random.randint(-32, 32)
            y = cy + random.randint(-30, 30)
            pygame.draw.circle(s, (*glow, 110), (x, y), random.randint(2, 6), 1)
    elif deco == "wisp":
        for i in range(4):
            pygame.draw.arc(s, (*glow, 90),
                           (cx - 34 + i * 4, cy - 34 + i * 4, 68 - i * 8, 68 - i * 8),
                           0.3, 2.4, 2)
    elif deco == "shield":
        pygame.draw.arc(s, (*edge, 210), (cx - 34, cy - 32, 26, 60),
                        -math.pi / 2, math.pi / 2, 5)
    elif deco == "cross":
        pygame.draw.line(s, glow, (cx, cy - 8), (cx, cy + 8), 4)
        pygame.draw.line(s, glow, (cx - 8, cy), (cx + 8, cy), 4)
    elif deco == "flame":
        for i in range(5):
            x = cx + random.randint(-22, 22)
            pygame.draw.polygon(s, (*glow, 150),
                                [(x, cy + 20), (x - 4, cy + 6), (x, cy - 2), (x + 4, cy + 6)])
    elif deco == "crack":
        pygame.draw.lines(s, (*edge, 170), False,
                          [(cx - 2, cy - 28), (cx + 3, cy - 10), (cx - 4, cy + 4),
                           (cx + 2, cy + 22)], 2)
    # 边缘破损高光
    for _ in range(5):
        a = random.uniform(0, math.pi * 2)
        x, y = cx + math.cos(a) * 24, cy + math.sin(a) * 26
        pygame.draw.line(s, (*edge, 130), (x, y),
                         (x + math.cos(a) * 4, y + math.sin(a) * 4), 1)
    return s


def main():
    os.makedirs(OUT, exist_ok=True)
    pygame.init()
    for i, (key, (b, g, e, d)) in enumerate(STYLES.items()):
        surf = build(key, b, g, e, d, seed=1000 + i)
        path = os.path.join(OUT, "zombie_%s.png" % key)
        pygame.image.save(surf, path)
        print("[生成]", path)
    pygame.quit()


if __name__ == "__main__":
    main()
