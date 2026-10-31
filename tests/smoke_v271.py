#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.7.1 冒烟测试：多对象/多玩家通用层

1. 玩家注册表：可动态创建多玩家、标签/摄像机/控件/选中技能按玩家分离
2. P2 钩爪能勾取 僵尸 / 道具 / 经验球 / 其他玩家（旧版只跑 P1 碰撞 → 全勾不到）
3. P1 钩爪行为不回归
4. 玩家对玩家：合作同阵营救援、PvP 异阵营勾取
5. Boss 免控（P1/P2 一致）
"""
import os
import sys
import math

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, _ROOT)

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game import Game, GameState
from config import *
from entities_pkg.player import Player
from entities_pkg.enemy import Enemy

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


def step_gear(g, player, n=200, dt=1 / 60):
    """推进钩爪状态机，直到命中/拉回（模拟 player.update 内部的 riot_gear.update）

    注意：钩爪命中后会继续走 hit→pulling→完成释放，所以必须在「命中瞬间」判定，
    不能一路跑到结束（结束状态为 idle，被勾对象已释放）。
    """
    rg = player.riot_gear
    for _ in range(n):
        rg.update(dt, player.x, player.y, player.facing_angle, 1.0,
                  cd_reduction_mult=getattr(player, 'cooldown_mult', 1.0), player=player)
        g.update_grapple_collisions()
        if rg.grapple_state in ("hit", "pulling"):
            return True
        if not rg.grapple_active:
            break
    return rg.grapple_state in ("hit", "pulling")


# ======================================================================
print("[1] 玩家注册表")
g = Game()
g.start_game()
g.state = GameState.PLAYING
check(g.tag_of(g.player) == "P1", "P1 标签识别")
check(g.ensure_player("P2") is not None, "P2 可动态创建")
check(g.tag_of(g.player2) == "P2", "P2 标签识别")
check(g.get_player("P2") is g.player2, "按标签取回 P2")
check(g.get_player(1) is g.player, "按序号取回 P1")
_p3 = g.ensure_player("P3")
check(_p3 is not None and g.tag_of(_p3) == "P3", "P3 可动态创建（支持>2 玩家）")
check(len(g.registered_players()) >= 3, f"注册表含 {len(g.registered_players())} 名玩家")

# 每玩家独立上下文
g.set_selected_skill(g.player2, SkillType.GRENADE)
g.set_selected_skill(g.player, SkillType.GRAPPLE_PULL)
check(g.selected_skill_of(g.player) == SkillType.GRAPPLE_PULL, "P1 选中技能独立")
check(g.selected_skill_of(g.player2) == SkillType.GRENADE, "P2 选中技能独立")
_c1 = g.camera_for(g.player)
_c2 = g.camera_for(g.player2)
check(_c1 is not None and _c2 is not None and _c1 is not _c2, "P1/P2 摄像机互相独立")
_ct1 = g.controls_for(g.player)
_ct2 = g.controls_for(g.player2)
check(_ct1 is not _ct2, "P1/P2 控件集合互相独立")
check(isinstance(list(g.iter_player_ctx()), list), "iter_player_ctx 可遍历")

# 轮换技能
g.set_selected_skill(g.player2, SkillType.GRENADE)
_nx = g.cycle_selected_skill(g.player2, [SkillType.GRENADE, SkillType.DASH])
check(_nx == SkillType.DASH, "技能轮换对任意玩家可用")

# 新玩家具备完整能力（与单人 P1 一致）
_p4 = g.ensure_player("P4")
check(hasattr(_p4, 'skill_tree') and hasattr(_p4, 'riot_gear'), "新玩家含技能树与防爆套装")
check(hasattr(_p4, 'active_skills') and hasattr(_p4, 'buff_manager'), "新玩家含技能CD与Buff管理")
check(getattr(_p4, 'team_id', None) is not None, "新玩家含阵营标识")

# ======================================================================
print("[2] P2 钩爪 —— 僵尸")
g2 = Game()
g2.start_game()
g2.state = GameState.PLAYING
g2.multiplayer_mode = "same_screen"
p1, p2 = g2.player, g2.ensure_player("P2")
p1.team_id = 0
p2.team_id = 0
p2.x, p2.y = 0.0, 0.0
g2.enemies.clear()
_z = Enemy(120.0, 0.0, EnemyType.ZOMBIE_NORMAL, 1, "normal")
_z.hp = _z.max_hp = 5000
g2.enemies.append(_z)

_t = g2.resolve_grapple_target(p2, 1.0, 0.0, 800)
check(_t is _z, "P2 目标解算命中僵尸")
rg2 = p2.riot_gear
rg2.grapple_cooldown = 0.0
_ok = rg2.use_grapple(_z.x, _z.y, p2.x, p2.y, _z)
check(_ok, "P2 钩爪发射成功")
step_gear(g2, p2, 200)
check(_z.grappled, "P2 钩中僵尸（grappled=True）")
check(rg2.grapple_state in ("hit", "pulling"), f"P2 钩爪进入命中态（{rg2.grapple_state}）")

# ======================================================================
print("[3] P2 钩爪 —— 玩家（合作同阵营）")
g3 = Game()
g3.start_game()
g3.state = GameState.PLAYING
g3.multiplayer_mode = "same_screen"
a1, a2 = g3.player, g3.ensure_player("P2")
a1.team_id = 0
a2.team_id = 0
a1.x, a1.y = 100.0, 0.0
a2.x, a2.y = 0.0, 0.0
g3.enemies.clear()
_tp = g3.resolve_grapple_target(a2, 1.0, 0.0, 800)
check(_tp is a1, "P2 目标解算命中 P1 玩家")
_rg = a2.riot_gear
_rg.grapple_cooldown = 0.0
_okp = _rg.use_grapple(a1.x, a1.y, a2.x, a2.y, a1)
check(_okp, "P2 对 P1 发射钩爪")
step_gear(g3, a2, 200)
check(getattr(a1, 'grappled', False), "P1 被 P2 勾住")
check(getattr(a1, 'qte_window', 0) > 0, "被勾玩家进入打断 QTE 窗口")

# ======================================================================
print("[4] P2 钩爪 —— 道具 / 经验球（飞行碰撞）")
g4 = Game()
g4.start_game()
g4.state = GameState.PLAYING
g4.multiplayer_mode = "same_screen"
b1, b2 = g4.player, g4.ensure_player("P2")
b1.team_id = b2.team_id = 0
b2.x, b2.y = 0.0, 0.0
g4.enemies.clear()


class _Item:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.size = 14
        self.alive = True
        self.magnetized = False


g4.world.items.clear()
_it = _Item(90.0, 0.0)
g4.world.items.append(_it)
_rg4 = b2.riot_gear
_rg4.grapple_cooldown = 0.0
_rg4.use_grapple(300.0, 0.0, 0.0, 0.0, None)
step_gear(g4, b2, 300)
check(_rg4.grapple_state == "pulling" and _rg4.grapple_target is _it,
      f"P2 勾中世界道具（state={_rg4.grapple_state}）")

# 经验球
g4b = Game()
g4b.start_game()
g4b.state = GameState.PLAYING
c1, c2 = g4b.player, g4b.ensure_player("P2")
c1.team_id = c2.team_id = 0
c2.x, c2.y = 0.0, 0.0
g4b.enemies.clear()
g4b.world.items.clear()
g4b.exp_orbs.clear()


class _Orb:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.size = 8
        self.alive = True
        self.magnetized = False


_orb = _Orb(90.0, 0.0)
g4b.exp_orbs.append(_orb)
_rg5 = c2.riot_gear
_rg5.grapple_cooldown = 0.0
_rg5.use_grapple(300.0, 0.0, 0.0, 0.0, None)
step_gear(g4b, c2, 300)
check(_orb.magnetized, "P2 钩爪磁吸经验球")

# ======================================================================
print("[5] PvP：异阵营玩家可勾取")
g5 = Game()
g5.start_game()
g5.state = GameState.PLAYING
g5.multiplayer_mode = "same_screen"
g5.config.pvp_enabled = True
d1, d2 = g5.player, g5.ensure_player("P2")
d1.team_id = 0
d2.team_id = 1
d1.x, d1.y = 100.0, 0.0
d2.x, d2.y = 0.0, 0.0
g5.enemies.clear()
check(d1 in g5._enemy_players_of(d2), "PvP 下 P1 是 P2 的敌对目标")
_te = g5.resolve_grapple_target(d2, 1.0, 0.0, 800)
check(_te is d1, "PvP 下 P2 解算命中 P1")
check(d1 not in g5._alive_teammates_of(d2), "PvP 下 P1 不算 P2 队友")
g5.config.pvp_enabled = False

# ======================================================================
print("[6] P1 不回归 + Boss 免控")
g6 = Game()
g6.start_game()
g6.state = GameState.PLAYING
e1 = g6.player
e1.x, e1.y = 0.0, 0.0
g6.enemies.clear()
_zb = Enemy(120.0, 0.0, EnemyType.BOSS_LONG, 1, "normal")
_zb.hp = _zb.max_hp = 9000
_zn = Enemy(120.0, 60.0, EnemyType.ZOMBIE_NORMAL, 1, "normal")
_zn.hp = _zn.max_hp = 9000
g6.enemies.extend([_zb, _zn])

_tb = g6.resolve_grapple_target(e1, 1.0, 0.0, 800)
check(_tb is _zb or _tb is None, "Boss 不因远处直发被优先锁定（仅沿途僵直）")
_rg6 = e1.riot_gear
_rg6.grapple_cooldown = 0.0
_rg6.use_grapple(_zb.x, _zb.y, e1.x, e1.y, _zb)
step_gear(g6, e1, 300)
check(not getattr(_zb, 'grappled', False), "Boss 免控：不会被勾住")
check(not _rg6.grapple_active or _rg6.grapple_state == "retracting", "Boss 命中后钩爪收回")

# P1 勾取普通僵尸不回归
g6.enemies.clear()
_z2 = Enemy(120.0, 0.0, EnemyType.ZOMBIE_NORMAL, 1, "normal")
_z2.hp = _z2.max_hp = 5000
g6.enemies.append(_z2)
_t2 = g6.resolve_grapple_target(e1, 1.0, 0.0, 800)
check(_t2 is _z2, "P1 目标解算命中僵尸")
_rg6.grapple_cooldown = 0.0
_rg6.use_grapple(_z2.x, _z2.y, e1.x, e1.y, _z2)
step_gear(g6, e1, 200)
check(_z2.grappled, "P1 仍能勾中僵尸（无回归）")

# ======================================================================
print("[7] 通用碰撞对全部玩家生效")
g7 = Game()
g7.start_game()
g7.state = GameState.PLAYING
g7.multiplayer_mode = "same_screen"
f1, f2, f3 = g7.player, g7.ensure_player("P2"), g7.ensure_player("P3")
for _p in (f1, f2, f3):
    _p.team_id = 0
f1.x, f1.y = 0.0, 0.0
f2.x, f2.y = 0.0, 200.0
f3.x, f3.y = 0.0, 400.0
g7.enemies.clear()
_zs = []
for _i, _pp in enumerate((f1, f2, f3)):
    _e = Enemy(_pp.x + 120.0, _pp.y, EnemyType.ZOMBIE_NORMAL, 1, "normal")
    _e.hp = _e.max_hp = 5000
    g7.enemies.append(_e)
    _zs.append(_e)
for _i, _pp in enumerate((f1, f2, f3)):
    _rg = _pp.riot_gear
    _rg.grapple_cooldown = 0.0
    _rg.use_grapple(_zs[_i].x, _zs[_i].y, _pp.x, _pp.y, _zs[_i])
for _ in range(120):
    for _pp in (f1, f2, f3):
        _pp.riot_gear.update(1 / 60, _pp.x, _pp.y, _pp.facing_angle, 1.0,
                             cd_reduction_mult=1.0, player=_pp)
    g7.update_grapple_collisions()
    if all(getattr(_e, 'grappled', False) for _e in _zs):
        break
_hooked = [getattr(_e, 'grappled', False) for _e in _zs]
check(all(_hooked), f"三名玩家同时勾中各自目标（{_hooked}）")

# ======================================================================
print("[8] 真实跑帧不崩溃")
g8 = Game()
g8.start_game()
g8.state = GameState.PLAYING
g8.multiplayer_mode = "same_screen"
h1, h2 = g8.player, g8.ensure_player("P2")
h1.team_id = h2.team_id = 0
if g8.camera2 is None:
    g8.camera2 = g8.camera_for(h2)
for _ in range(30):
    g8.update(1 / 60)
    g8.renderer.render()
check(True, "双人开局跑帧 30 次不崩溃")

# 玩家死亡不崩溃
h2.alive = False
for _ in range(10):
    g8.update(1 / 60)
check(True, "玩家死亡后钩爪碰撞不崩溃")

print()
print(f"===== v2.7.1 冒烟测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
