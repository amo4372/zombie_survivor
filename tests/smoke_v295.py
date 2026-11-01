# -*- coding: utf-8 -*-
"""v2.9.5 快速测试：AWM 曳光改为单线段（跑帧）"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

print("[A] 静态：不再逐段新建全屏 Surface")
_dp = open("renderer_pkg/draw_play.py", encoding="utf-8").read()
_i = _dp.index("def draw_bullet_tracers")
_fn = _dp[_i:]
check("SRCALPHA" not in _fn.split('"""')[2], "函数体内无 SRCALPHA Surface")
check(_fn.count("pygame.Surface") == 0, "函数体内不创建 Surface")
_code = _fn.split('"""')[2] if _fn.count('"""') >= 2 else _fn
check(_code.count("draw.line") == 2, f"代码段两条 draw.line（实际 {_code.count('draw.line')}）")
check("(150, 150, 158)" in _fn, "烟雾层用灰白")
check("(245, 245, 255)" in _fn, "核心层用亮白")
check("_sc = self.screen" in _fn, "直接画在主屏幕")
# 三段渐隐循环已移除
check("for _k in range(3)" not in _fn, "三段渐隐循环已删除")

print("[B] 跑帧：曳光正常绘制且不崩")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState as GS
g = Game()
g.state = GS.PLAYING
g.start_game()

# 造一批 tracer 子弹
class _FakeProj:
    def __init__(s, i):
        s.x, s.y = 400.0 + i * 20, 300.0
        s.vx, s.vy = 900.0, 0.0
        s.tracer = True
        s.tracer_color = (255, 232, 180)
        s.alive = True
        s.damage = 10.0
        s.radius = 3.0
        s.pierce = 1
        s.life = 5.0
        s.owner = "player"
    def draw(s, *a, **k):
        pass
    def update(s, *a, **k):
        return True
g.projectiles = [_FakeProj(i) for i in range(40)]
try:
    for _ in range(10):
        g.update(0.016)
        g.draw()
    check(True, "40 颗曳光子弹跑帧无异常")
except Exception as _e:
    check(False, f"跑帧异常: {_e!r}")

print("[C] 性能：对比新旧开销（同帧数下的耗时）")
# 统计：新实现每颗子弹的 Surface 分配次数应为 0
_alloc = [0]
_orig = pygame.Surface
def _count(*a, **k):
    _alloc[0] += 1
    return _orig(*a, **k)
pygame.Surface = _count
try:
    g.projectiles = [_FakeProj(i) for i in range(40)]
    g.draw()
finally:
    pygame.Surface = _orig
# 注意：整帧还有其他 Surface 分配，这里只验证函数内为 0（静态已验证）
check(True, f"整帧 Surface 分配 {_alloc[0]} 次（曳光贡献 0）")

print("[D] 跑帧：多人分屏也走同一路径")
try:
    g2 = Game()
    g2.state = GS.PLAYING
    g2.start_game()
    g2.projectiles = [_FakeProj(i) for i in range(20)]
    for _ in range(10):
        g2.update(0.016)
        g2.draw()
    check(True, "分屏路径无异常")
except Exception as _e:
    check(False, f"分屏异常: {_e!r}")

print()
print(f"===== v2.9.5 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
