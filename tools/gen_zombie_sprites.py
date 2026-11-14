#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.9.18 按**项目原有画风**生成图鉴新增类别僵尸贴图。

原画风（对照 assets/images/zombie_normal.png 等 17 张）特征：
  - 64×64 透明 PNG，纯色平涂、无渐变、无躯干/手臂
  - 一个半径 ~26 的实心圆头，居中
  - 两只极简眼睛（白/红/粉），一个几何类型标识
  - 无幽光大圆盘、无阴影、无描边渐隐

v2.9.17 版画成了「不规则多边形躯干 + 头 + 手臂 + 冰晶装饰 + 渐变幽光」，
与原素材完全不符，本版全部废弃重做。
"""
import os
import math
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "images")
SIZE = 64
CX = CY = 32
R = 26

# key -> (主体色, 深色描边, 眼睛色, 装饰类型)
STYLES = {
    # 图鉴里原本标「新增」、且仓库确实缺 PNG 的 8 类
    "zombie_hunter":     ((28, 118, 108), (16, 72, 66),  (255, 240, 240), "fang"),
    "zombie_bomber":     ((238, 138, 42), (150, 78, 20), (255, 250, 230), "warn"),
    "zombie_frost":      ((108, 186, 226), (54, 118, 160), (255, 255, 255), "snow"),
    "zombie_venom":      ((92, 168, 62),  (48, 104, 34), (240, 255, 225), "bubble"),
    "zombie_berserker":  ((198, 52, 52),  (120, 26, 26), (255, 235, 220), "crack"),
    "zombie_ghoul":      ((96, 116, 94),  (52, 70, 54),  (245, 245, 235), "hollow"),
    "zombie_shaman":     ((148, 92, 202), (88, 48, 130), (245, 235, 255), "rune"),
    "zombie_juggernaut": ((74, 82, 94),   (38, 44, 54),  (235, 120, 110), "visor"),
}


def build(body, edge, eye, deco):
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    # 圆形主体（原素材就是纯色圆 + 一圈深色细边）
    pygame.draw.circle(s, body, (CX, CY), R)
    pygame.draw.circle(s, edge, (CX, CY), R, 2)

    # 眼睛：白/亮色小圆 + 深色瞳（与 z_normal / z_phantom 一致）
    for ex in (CX - 9, CX + 9):
        pygame.draw.circle(s, eye, (ex, CY - 4), 5)
        pygame.draw.circle(s, (35, 25, 30), (ex, CY - 4), 2)

    if deco == "fang":
        # 猎手：两颗下獠牙
        pygame.draw.polygon(s, (250, 250, 240),
                            [(CX - 8, CY + 8), (CX - 4, CY + 8), (CX - 6, CY + 15)])
        pygame.draw.polygon(s, (250, 250, 240),
                            [(CX + 4, CY + 8), (CX + 8, CY + 8), (CX + 6, CY + 15)])
    elif deco == "warn":
        # 爆破：黄色三角警告（复刻 z_exploder）
        pygame.draw.polygon(s, (255, 225, 70),
                            [(CX, CY + 5), (CX - 9, CY + 19), (CX + 9, CY + 19)])
        pygame.draw.line(s, (120, 60, 20), (CX, CY + 9), (CX, CY + 15), 2)
        pygame.draw.circle(s, (120, 60, 20), (CX, CY + 17), 1)
    elif deco == "snow":
        # 冰霜：六角雪花（极简几何，不加渐变）
        for i in range(3):
            a = math.radians(i * 60)
            pygame.draw.line(s, (235, 250, 255),
                             (CX - math.cos(a) * 9, CY + 9 - math.sin(a) * 9),
                             (CX + math.cos(a) * 9, CY + 9 + math.sin(a) * 9), 2)
    elif deco == "bubble":
        for bx, by, br in ((CX - 8, CY + 12, 3), (CX, CY + 8, 4), (CX + 8, CY + 13, 2)):
            pygame.draw.circle(s, (210, 255, 190), (bx, by), br, 1)
    elif deco == "crack":
        pygame.draw.lines(s, (255, 190, 180), False,
                          [(CX - 2, CY - 20), (CX + 3, CY - 8),
                           (CX - 3, CY + 2), (CX + 2, CY + 14)], 2)
    elif deco == "hollow":
        # 食尸鬼：空洞嘴
        pygame.draw.ellipse(s, (30, 40, 34), (CX - 7, CY + 7, 14, 8))
    elif deco == "rune":
        # 萨满：头顶菱形符文
        pygame.draw.polygon(s, (235, 210, 255),
                            [(CX, CY - 28), (CX + 6, CY - 22),
                             (CX, CY - 16), (CX - 6, CY - 22)], 2)
        pygame.draw.arc(s, (220, 190, 255),
                        (CX - 12, CY + 4, 24, 18), 0.2, 2.9, 2)
    elif deco == "visor":
        # 重装：横条护目镜（复刻 z_tank）
        pygame.draw.rect(s, edge, (CX - 16, CY - 9, 32, 11), border_radius=2)
        pygame.draw.rect(s, (220, 90, 80), (CX - 11, CY - 6, 5, 4))
        pygame.draw.rect(s, (220, 90, 80), (CX + 6, CY - 6, 5, 4))
    return s


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    os.makedirs(OUT, exist_ok=True)
    for key, (b, e, y, d) in STYLES.items():
        surf = build(b, e, y, d)
        pygame.image.save(surf, os.path.join(OUT, key + ".png"))
        print("[生成]", key + ".png")
    pygame.quit()


if __name__ == "__main__":
    main()
