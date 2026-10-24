#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.4 决策树 AI（无训练硬编程）替换 RL 测试套件

覆盖：
1. ai_pkg 决策树原语（Selector/Sequence/Condition/Action/Inverter）
2. ZombieTreeAI 接口同构（decide/flush_batch/ready/save_stats）
3. 全类型僵尸接管：普通追击 / 远程保持距离开火 / 爆炸冲锋 / 治疗靠拢 / 精英走位
4. Boss 走原生 Utility AI 硬编程（专属形态保留），CD 不因决策层丢失
5. 异常/不可用回退原生 AI（None 安全）
6. 性能：决策树开销远低于可接受阈值
"""
import os
import sys
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()

from config import EnemyType
from entities_pkg.enemy import Enemy
from ai_pkg import ZombieTreeAI
from ai_pkg.decision_tree import (Selector, Sequence, Condition, Action, Inverter,
                                  SUCCESS, FAILURE, RUNNING)

_PASS = 0
_FAIL = []


def check(name, cond):
    global _PASS
    if cond:
        _PASS += 1
    else:
        _FAIL.append(name)
        print(f"  [FAIL] {name}")


class P:
    def __init__(self, x, y, hp=100):
        self.x, self.y, self.hp = x, y, hp
        self.facing_angle = 0.0
        self.downed = False
        self.upgrade_paused = False


class W:
    def __init__(self, enemies):
        self.enemies = enemies
        self.obstacles = []


def make_ai():
    return ZombieTreeAI()


def make_enemy(t, x, y, ai, world):
    e = Enemy(x, y, t, 1, "normal")
    e.ai_rl = ai
    world.enemies.append(e)
    return e


def run_frames(world, p, frames=300, dt=1 / 60):
    for _ in range(frames):
        for en in world.enemies[:]:
            if en.alive:
                en.update(dt, p.x, p.y, p, world)


# ---------- 1. 决策树原语 ----------
def test_tree_primitives():
    ctx = {"v": 0}
    n = Condition("true", lambda c: True)
    check("condition_true", n.tick(ctx) == SUCCESS)
    n2 = Condition("false", lambda c: False)
    check("condition_false", n2.tick(ctx) == FAILURE)
    a = Action("set", lambda c: c.__setitem__("v", 5))
    check("action", a.tick(ctx) == SUCCESS and ctx["v"] == 5)
    sel = Selector("sel", [n2, a])
    check("selector_shortcut", sel.tick(ctx) == SUCCESS and ctx["v"] == 5)
    seq = Sequence("seq", [n, Condition("ok", lambda c: c["v"] == 5)])
    check("sequence_all", seq.tick(ctx) == SUCCESS)
    inv = Inverter(n2)
    check("inverter", inv.tick(ctx) == SUCCESS)


# ---------- 2. 接口同构 ----------
def test_interface():
    ai = make_ai()
    check("ready_true", ai.ready is True)
    check("flush_noop", ai.flush_batch() is None)
    world = W([])
    p = P(100, 100)
    e = make_enemy(EnemyType.ZOMBIE_NORMAL, 300, 300, ai, world)
    r = ai.decide(e, p, world, world.enemies)
    check("decide_tuple", isinstance(r, tuple) and len(r) == 3)
    check("decide_units", (r[0] is None) or (-1.0 <= r[0] <= 1.0 and -1.0 <= r[1] <= 1.0))
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        pth = os.path.join(d, "stats.json")
        check("save_stats", ai.save_stats(pth) and os.path.exists(pth))
    check("decide_none_player", ai.decide(e, None) == (None, None, False))
    check("decide_none_enemy", ai.decide(None, p) == (None, None, False))


# ---------- 3. 全类型接管 ----------
def test_all_types_controlled():
    ai = make_ai()
    world = W([])
    p = P(640, 480)
    mk = lambda t, x, y: make_enemy(t, x, y, ai, world)
    n = mk(EnemyType.ZOMBIE_NORMAL, 200, 200)
    r = mk(EnemyType.ZOMBIE_RANGED, 300, 300)
    ex = mk(EnemyType.ZOMBIE_EXPLODER, 500, 200)
    h = mk(EnemyType.ZOMBIE_HEALER, 700, 700)
    f = mk(EnemyType.ZOMBIE_FAST, 100, 600)
    tk = mk(EnemyType.ZOMBIE_TANK, 900, 500)
    br = mk(EnemyType.ELITE_BRUTE, 800, 800)
    b1 = mk(EnemyType.BOSS_LONG, 900, 300)
    b2 = mk(EnemyType.BOSS_WANG, 200, 900)
    run_frames(world, p, 360)
    # 普通/快速/坦克/精英/Boss 均追至玩家附近（攻击距离内）
    for e in (n, f, tk, br, b1, b2):
        d = math.hypot(e.x - p.x, e.y - p.y)
        check(f"approach_{e.enemy_type.name}", e.alive and d < 260)
    # 远程保持中距（不过度贴身也不逃离）
    dr = math.hypot(r.x - p.x, r.y - p.y)
    check("ranged_keep_distance", 80 < dr < 340)
    check("ranged_used_skill1", ai.stats["skill_hist"].get(1, 0) > 20)
    # 爆炸冲向玩家
    dex = math.hypot(ex.x - p.x, ex.y - p.y)
    check("exploder_charge", dex < 220)
    # 治疗靠拢
    dh = math.hypot(h.x - p.x, h.y - p.y)
    check("healer_approach", dh < 260)
    # 决策树接管非 Boss（tree_hits 有 melee/ranged/exploder/healer）
    check("tree_hits_all", set(ai.stats["tree_hits"]) >= {"melee", "ranged", "exploder", "healer"})


# ---------- 4. Boss 原生硬编程保留 ----------
def test_boss_keeps_native_ai():
    ai = make_ai()
    world = W([])
    p = P(640, 480)
    b = make_enemy(EnemyType.BOSS_LONG, 900, 300, ai, world)
    # Boss 不进决策树（tree_hits 无 boss 条目），由原生 _boss_behavior 全权
    run_frames(world, p, 400)
    check("boss_no_tree", "boss" not in ai.stats["tree_hits"])
    d = math.hypot(b.x - p.x, b.y - p.y)
    check("boss_alive_near", b.alive and d < 260)
    # Boss 专属 CD 存在且被原生递减（原生允许负值=已就绪，仅需证明在递减不卡死）
    check("boss_cd_fields", hasattr(b, "boss_dash_cd") and hasattr(b, "boss_charge_cd"))
    check("boss_cd_decaying", b.boss_dash_cd <= 2.0 and b.boss_charge_cd <= 2.0)


# ---------- 5. 回退安全 ----------
def test_fallback_safety():
    # 未挂载 ai_rl → 原生规则 AI 路径（不崩、正常移动）
    world = W([])
    p = P(640, 480)
    e = Enemy(200, 200, EnemyType.ZOMBIE_NORMAL, 1, "normal")
    world.enemies.append(e)
    run_frames(world, p, 120)
    d = math.hypot(e.x - p.x, e.y - p.y)
    check("native_fallback_moves", d < 400)
    # 挂载但 decide 异常（打坏）→ 仍不崩
    class BadAI:
        ready = True
        def decide(self, *a, **k):
            raise RuntimeError("boom")
        def flush_batch(self, *a, **k):
            return None
    world2 = W([])
    e2 = Enemy(300, 300, EnemyType.ZOMBIE_NORMAL, 1, "normal")
    e2.ai_rl = BadAI()
    world2.enemies.append(e2)
    run_frames(world2, p, 60)
    check("bad_ai_no_crash", e2.alive)


# ---------- 6. 性能 ----------
def test_performance():
    ai = make_ai()
    world = W([])
    p = P(640, 480)
    for i in range(120):
        make_enemy(EnemyType.ZOMBIE_NORMAL, 100 + (i % 10) * 20, 200 + (i // 10) * 20, ai, world)
    t0 = time.perf_counter()
    run_frames(world, p, 120)
    dt = time.perf_counter() - t0
    # 120 只怪 × 120 帧 = 14400 次 update，应 < 3s（决策树远快于 RL numpy 推理）
    check(f"perf_14400_updates_{dt:.2f}s", dt < 3.0)


if __name__ == "__main__":
    for fn in (test_tree_primitives, test_interface, test_all_types_controlled,
               test_boss_keeps_native_ai, test_fallback_safety, test_performance):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            _FAIL.append(f"{fn.__name__} EXC: {e}")
    print(f"\n结果: {_PASS} 通过, {len(_FAIL)} 失败")
    if _FAIL:
        print("失败项:", _FAIL)
        sys.exit(1)
    print("ALL GREEN")
