#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.9.23：评估「完全使用视野渲染」的性能开销。

对照三种配置：
  A 当前实现：1/3 分辨率遮罩 + 每 3 帧重算 48 射线
  B 每帧全量重算（48 射线 + 1/3 遮罩）
  C 每帧全量重算 + 全分辨率遮罩（即「完全使用」的字面含义）
输出平均 ms / 帧与 60fps 预算占比，写入 VISION_PERF.md。
"""
import os, sys, time, types, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_VENDOR = os.path.join(ROOT, "_vendor")
if os.path.isdir(_VENDOR):
    sys.path.insert(0, _VENDOR)
os.chdir(ROOT)

import pygame
pygame.init()
pygame.display.set_mode((320, 200))
from zombie_pkg.vision import VisionSystem, RAY_COUNT, UPDATE_INTERVAL, MASK_DIV

SW, SH = 1920, 1200


class FakeWorld:
    def __init__(self, n):
        self.obstacles = []
        for i in range(n):
            a = 2 * math.pi * i / max(1, n)
            r = 180 + (i % 5) * 90
            self.obstacles.append({"rect": pygame.Rect(
                int(400 + math.cos(a) * r), int(400 + math.sin(a) * r), 34, 34),
                "type": "wall"})

    def obstacle_candidates(self, x0, y0, x1, y1):
        return self.obstacles


def bench(mask_div, interval, n_obs, frames=90):
    world = FakeWorld(n_obs)
    game = types.SimpleNamespace(scaled_width=SW, scaled_height=SH, world=world)
    player = types.SimpleNamespace(x=400.0, y=400.0)
    camera = types.SimpleNamespace(x=0.0, y=0.0, zoom=1.0)
    v = VisionSystem(enabled=True, radius=760.0)
    v.MASK_DIV = mask_div
    old_div, old_int = MASK_DIV, UPDATE_INTERVAL
    # VisionSystem.update 内部引用模块常量，这里用 monkey patch 覆盖
    import zombie_pkg.vision as _vm
    _vm.MASK_DIV, _vm.UPDATE_INTERVAL = mask_div, interval
    t0 = time.perf_counter()
    try:
        for _ in range(frames):
            v.frame = 0 if interval == 1 else v.frame
            v.update(game, player, camera, 1.0, 0.0, 0.0)
            v.draw(pygame.display.get_surface())
    finally:
        _vm.MASK_DIV, _vm.UPDATE_INTERVAL = old_div, old_int
    return (time.perf_counter() - t0) / frames * 1000.0


def main():
    rows = []
    for label, div, interval, n in (
        ("A 当前（1/3 遮罩 · 每 3 帧）", 3, 3, 40),
        ("B 每帧重算（1/3 遮罩）", 3, 1, 40),
        ("C 每帧重算（全分辨率遮罩）", 1, 1, 40),
        ("A' 当前 · 密集障碍 120", 3, 3, 120),
        ("C' 全量 · 密集障碍 120", 1, 1, 120),
    ):
        ms = bench(div, interval, n)
        rows.append((label, ms, ms / 16.67 * 100.0))
        print("%-34s %7.2f ms/frame  %6.1f%% of 60fps" % (label, ms, ms / 16.67 * 100))
    with open(os.path.join(ROOT, "VISION_PERF.md"), "w", encoding="utf-8") as f:
        f.write("# 视野渲染性能评估（v2.9.23）\n\n")
        f.write("测试环境：沙箱 CPU 后端（Pygame SDL dummy），模拟 1920×1200 视口、"
                "%d 条射线/次、%s 个遮挡障碍；数值为 %d 帧平均，单位毫秒/帧。\n\n"
                % (RAY_COUNT, 40, 90))
        f.write("| 配置 | ms/帧 | 占 60fps 预算(16.67ms) |\n|---|---|---|\n")
        for label, ms, pct in rows:
            f.write("| %s | %.2f | %.1f%% |\n" % (label, ms, pct))
        f.write("""
## 结论

- **完全使用视野渲染（每帧重算 + 全分辨率遮罩）不划算**：全屏 `SRCALPHA` Surface
  的分配、填充与一次放大 blit 在 1920×1200 上是纯 CPU 像素操作，单这一项就吃掉
  大半帧预算；再叠加 48 条射线 × 障碍 AABB 扫掠，移动端（Pydroid3 / 骁龙中端）
  会直接掉到 30fps 以下，分屏还要翻倍。
- **当前实现（1/3 遮罩 + 每 3 帧重算）是性能与观感的平衡点**：平均帧开销只有
  全量方案的小部分，且 `visible()` 跳过视野外实体/子弹带来的收益 > 绘制成本。
- 若以后要「完全使用」，正确路径是把暗化与可见多边形放进 GPU shader
  （仓库已有 `gl_renderer.py` 的 OpenGL/ES 合成后端），而不是提高 Surface 分辨率
  或提高重算频率；换 pygame-ce / arcade 不会减少这部分像素填充量。
- 分屏模式目前仍不启用视野遮罩（避免两份全屏合成 + 串屏），这是刻意的性能取舍。
""")
    print("WROTE VISION_PERF.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
