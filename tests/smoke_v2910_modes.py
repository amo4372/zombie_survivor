# -*- coding: utf-8 -*-
"""v2.9.10 全模式跑帧冒烟（非纯静态，真实 update + draw）"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame

pygame.init()
pygame.display.set_mode((1280, 720))

from game import Game                      # noqa: E402
from config import GameState as GS, GameMode, EnemyType   # noqa: E402
from entities_pkg.enemy import Enemy        # noqa: E402

OK = BAD = 0
_BAD = []


def run(label, fn):
    global OK, BAD
    try:
        fn()
        OK += 1
        print(f"  OK  {label}")
    except Exception as e:
        BAD += 1
        _BAD.append((label, repr(e)))
        print(f"  BAD {label}: {e!r}")
        traceback.print_exc()


def start(mode=None, duo=False):
    g = Game()
    if mode:
        g.config.game_mode = mode
    if duo:
        g.multiplayer_mode = "same_screen"
    g.begin_setup_flow()
    for _ in range(6):
        g.draw()
        g.touch_events = [{"type": "down", "pos": (640, 120), "id": 0}]
        g.draw()
        g.touch_events = [{"type": "up", "pos": (640, 120), "id": 0}]
        g.draw()
        g.touch_events = []
        _nx = g.setup_next()
        _st = g.setup_state_for(_nx)
        if _st is None:
            g.start_game()
            break
        g.state = _st
    g.state = GS.PLAYING          # 跳过开场对话
    return g


print("[1] 各模式开局跑 180 帧")
for _m in (GameMode.STORY, GameMode.ENDLESS, GameMode.TIMED):
    def _f(_m=_m):
        _g = start(_m)
        for _ in range(180):
            _g.update(1 / 60)
            _g.draw()
    run(f"单人 {_m.name}", _f)


def _duo():
    g = start(duo=True)
    assert g.player2 is not None, "P2 未创建"
    for _ in range(180):
        g.update(1 / 60)
        g.draw()
run("同屏双人合作", _duo)


print("[2] 多人 PvP：P1/P2 同时被不同僵尸咬（各自独立 CD）")
def _pvp():
    g = start(duo=True)
    p1, p2 = g.player, g.player2
    assert p2 is not None
    for p in (p1, p2):
        p.hp = p.max_hp = 10000
        p.dodge_chance = 0.0
        p.armor = 0.0
        p.riot_gear.equipped = False
    e1 = Enemy(p1.x + 20, p1.y, EnemyType.ZOMBIE_NORMAL, 1, "普通")
    e2 = Enemy(p2.x + 20, p2.y, EnemyType.ZOMBIE_FAST, 1, "普通")
    for e in (e1, e2):
        e.knockdown_timer = 0
        e.speed = 0
        e.damage = 10
    n1 = n2 = 0
    for _ in range(120):
        e1.x, e1.y = p1.x + 20, p1.y
        e2.x, e2.y = p2.x + 20, p2.y
        a = p1.hp
        g._enemy_collide_damage(e1, p1, None)
        n1 += (a > p1.hp)
        b = p2.hp
        g._enemy_collide_damage(e2, p2, None)
        n2 += (b > p2.hp)
        e1.update(1 / 60, p1.x, p1.y, p1, None)
        e2.update(1 / 60, p2.x, p2.y, p2, None)
        g.update(1 / 60)
        g.draw()
    print(f"     2 秒 P1 命中 {n1} 次、P2 命中 {n2} 次（无 CD 时各 120 次）")
    assert 1 <= n1 <= 4 and 1 <= n2 <= 4
run("PvP 双人受伤", _pvp)


print("[3] Boss 女王召唤（原 AttributeError: difficulty）")
def _queen():
    g = start()
    _q = Enemy(g.player.x + 120, g.player.y, EnemyType.BOSS_QUEEN, 1,
               g.config.difficulty)
    g.enemies.append(_q)
    for _ in range(60):
        g.update(1 / 60)
        g.draw()
    _src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "zombie_pkg", "mix_playing.py"),
        encoding="utf-8").read()
    assert ", 1, self.difficulty)" not in _src
    assert _src.count(", 1, self.config.difficulty)") >= 2
run("女王/召唤刷怪", _queen)


print("[4] 结算页 / 死亡详情 / 主菜单 反复进出")
def _pages():
    g = start()
    for _ in range(3):
        g.state = GS.GAME_OVER
        g.touch_events = []
        for _ in range(10):
            g.draw()
        g.state = GS.DEATH_DETAIL
        for _ in range(10):
            g.draw()
        g.state = GS.MENU
        for _ in range(10):
            g.draw()
run("页面切换", _pages)


print("[5] 12 个菜单/选择页面")
def _menus():
    g = Game()
    for st in (GS.MENU, GS.GACHA, GS.SLOT_MACHINE, GS.CODEX, GS.RECORDS,
               GS.ACHIEVEMENTS, GS.SETTINGS, GS.MOD_MANAGER, GS.REPLAY_LIST,
               GS.MAP_SELECT, GS.WEAPON_SELECT_P1, GS.CHARACTER_SELECT_P1):
        g.state = st
        for _ in range(6):
            g.draw()
run("12 个页面", _menus)


print()
print(f"===== v2.9.10 全模式跑帧冒烟: OK={OK} BAD={BAD} =====")
for b in _BAD:
    print("  ", b)
sys.exit(1 if BAD else 0)
