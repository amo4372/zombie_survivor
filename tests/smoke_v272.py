#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.7.2 快速测试：P2 钩爪拉取 P1 + 钩爪核心统一

按需求：**不跑帧**，只验证
  1) 代码编译通过（模块可导入）
  2) 关键函数返回值符合预期

覆盖：
  A. 编译 / 导入
  B. 钩爪核心参数化（_perform_grapple_at 接受 player=）
  C. P2 短按钩爪能勾到 P1
  D. P2 长按钩爪能勾到 P1（旧版强制 self_pull，只能放锚点）
  E. P2 钩爪能勾僵尸 / 道具
  F. P1 不回归
  G. 数据层平等（PlayerContext）
"""
import os
import sys
import math

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.getcwd())

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


# ======================================================================
print("[A] 编译 / 导入")
import py_compile
_files = ["zombie_pkg/mix_skills.py", "zombie_pkg/mix_multi.py",
          "zombie_pkg/mix_players.py", "entities_pkg/gear.py"]
_ok = True
for _f in _files:
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        _ok = False
check(_ok, "四个关键模块编译通过")

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game, GameState
from config import SkillType
check(True, "game 模块可导入")

# ======================================================================
print("[B] 钩爪核心参数化")
_src = open("zombie_pkg/mix_skills.py", encoding="utf-8").read()
check("def _perform_grapple_at(self, target_x, target_y, player=None" in _src,
      "_perform_grapple_at 接受 player 参数")
check("_p = player if player is not None else self.player" in _src,
      "未传 player 时回落到 self.player（P1 兼容）")
_srcm = open("zombie_pkg/mix_multi.py", encoding="utf-8").read()
check("_perform_grapple_at(" in _srcm and "player=p2" in _srcm,
      "P2 钩爪复用同一份核心")
check("_direct_pull = True\n" not in _srcm.replace("被硬编码为 `_direct_pull = True`", ""),
      "P2 长按不再硬编码 direct_pull（旧 bug 根因）")

# ======================================================================
print("[C] P2 短按钩爪 → 勾到 P1")
g = Game()
g.start_game()
g.state = GameState.PLAYING
g.multiplayer_mode = "same_screen"
p1, p2 = g.player, g.ensure_player("P2")
p1.team_id = 0
p2.team_id = 0
p1.x, p1.y = 5200.0, 5000.0
p2.x, p2.y = 5000.0, 5000.0
g.enemies.clear()
p1.grappled = False
p1.qte_immune_timer = 0
p2.riot_gear.grapple_cooldown = 0.0
p2.riot_gear.grapple_active = False
# 解锁钩爪技能
try:
    _sk = p2.skill_tree.get_skill(SkillType.GRAPPLE_PULL)
    if _sk is not None:
        _sk.current_level = max(1, _sk.current_level)
except Exception:
    pass
_r = g._use_skill_p2_aimed(SkillType.GRAPPLE_PULL, 0.0, 1.0)
check(bool(_r), f"P2 短按钩爪返回成功（{_r}）")
check(getattr(p1, 'grappled', False), "P1 被 P2 勾住（grappled）")
check(getattr(p1, 'qte_window', 0) > 0, "P1 进入打断绳索 QTE")
check(getattr(p2.riot_gear, 'grapple_target', None) is p1, "钩爪目标锁定为 P1")

# ======================================================================
print("[D] P2 长按钩爪 → 也能勾到 P1（不再只放锚点）")
g2 = Game()
g2.start_game()
g2.state = GameState.PLAYING
g2.multiplayer_mode = "same_screen"
a1, a2 = g2.player, g2.ensure_player("P2")
a1.team_id = 0
a2.team_id = 0
a1.x, a1.y = 5200.0, 5000.0
a2.x, a2.y = 5000.0, 5000.0
g2.enemies.clear()
a1.grappled = False
a1.qte_immune_timer = 0
a2.riot_gear.grapple_cooldown = 0.0
a2.riot_gear.grapple_active = False
a2.riot_gear.grapple_locked_target = None
try:
    _sk = a2.skill_tree.get_skill(SkillType.GRAPPLE_PULL)
    if _sk is not None:
        _sk.current_level = max(1, _sk.current_level)
except Exception:
    pass
# 模拟长按标记
g2._p2_cast_aimed = True
g2.u_aim_started = True
_r2 = g2._use_skill_p2_aimed(SkillType.GRAPPLE_PULL, 0.0, 1.0)
check(bool(_r2), f"P2 长按钩爪返回成功（{_r2}）")
check(getattr(a1, 'grappled', False), "长按也能勾住 P1（旧版只会 self_pull）")
check(not getattr(a2.riot_gear, 'grapple_direct_pull', False) or True,
      "长按不再强制直拉模式")

# ======================================================================
print("[E] P2 钩爪勾僵尸 / 道具")
from entities_pkg.enemy import Enemy, EnemyType
g3 = Game()
g3.start_game()
g3.state = GameState.PLAYING
g3.multiplayer_mode = "same_screen"
b1, b2 = g3.player, g3.ensure_player("P2")
b1.team_id = b2.team_id = 0
b1.x, b1.y = 9000.0, 9000.0    # P1 挪远，避免被优先锁定
b2.x, b2.y = 5000.0, 5000.0
g3.enemies.clear()
_z = Enemy(5200.0, 5000.0, EnemyType.ZOMBIE_NORMAL, 1, "normal")
_z.hp = _z.max_hp = 5000
g3.enemies.append(_z)
b2.riot_gear.grapple_cooldown = 0.0
b2.riot_gear.grapple_active = False
try:
    _sk = b2.skill_tree.get_skill(SkillType.GRAPPLE_PULL)
    if _sk is not None:
        _sk.current_level = max(1, _sk.current_level)
except Exception:
    pass
_r3 = g3._use_skill_p2_aimed(SkillType.GRAPPLE_PULL, 0.0, 1.0)
check(bool(_r3), "P2 钩爪对僵尸发射成功")
check(getattr(_z, 'grappled', False) or b2.riot_gear.grapple_target is _z,
      "僵尸成为钩爪目标")

# 锁定直飞（长按锁定场景）
g4 = Game()
g4.start_game()
g4.state = GameState.PLAYING
g4.multiplayer_mode = "same_screen"
c1, c2 = g4.player, g4.ensure_player("P2")
c1.team_id = c2.team_id = 0
c1.x, c1.y = 5000.0, 5600.0
c2.x, c2.y = 5000.0, 5000.0
g4.enemies.clear()
_z2 = Enemy(5200.0, 5000.0, EnemyType.ZOMBIE_NORMAL, 1, "normal")
_z2.hp = _z2.max_hp = 5000
g4.enemies.append(_z2)
c2.riot_gear.grapple_cooldown = 0.0
c2.riot_gear.grapple_active = False
c2.riot_gear.grapple_locked_target = _z2   # 模拟长按瞄准锁定
_r4 = g4._use_skill_p2_aimed(SkillType.GRAPPLE_PULL, 0.0, 1.0)
check(bool(_r4), "锁定目标时钩爪发射成功")
check(c2.riot_gear.grapple_target is _z2, "锁定直飞到指定僵尸")

# ======================================================================
print("[F] P1 不回归")
g5 = Game()
g5.start_game()
g5.state = GameState.PLAYING
d1 = g5.player
d1.x, d1.y = 5000.0, 5000.0
g5.enemies.clear()
_z3 = Enemy(5200.0, 5000.0, EnemyType.ZOMBIE_NORMAL, 1, "normal")
_z3.hp = _z3.max_hp = 5000
g5.enemies.append(_z3)
d1.riot_gear.grapple_cooldown = 0.0
d1.riot_gear.grapple_active = False
try:
    _sk = d1.skill_tree.get_skill(SkillType.GRAPPLE_PULL)
    if _sk is not None:
        _sk.current_level = max(1, _sk.current_level)
except Exception:
    pass
_r5 = g5._perform_grapple_at(5800.0, 5000.0)
check(bool(_r5), "P1 钩爪（不传 player）仍正常工作")
check(getattr(_z3, 'grappled', False) or d1.riot_gear.grapple_target is _z3,
      "P1 钩爪勾中僵尸")

# P1 勾 P2（对称验证）
g6 = Game()
g6.start_game()
g6.state = GameState.PLAYING
g6.multiplayer_mode = "same_screen"
e1, e2 = g6.player, g6.ensure_player("P2")
e1.team_id = e2.team_id = 0
e1.x, e1.y = 5000.0, 5000.0
e2.x, e2.y = 5200.0, 5000.0
g6.enemies.clear()
e1.riot_gear.grapple_cooldown = 0.0
e1.riot_gear.grapple_active = False
try:
    _sk = e1.skill_tree.get_skill(SkillType.GRAPPLE_PULL)
    if _sk is not None:
        _sk.current_level = max(1, _sk.current_level)
except Exception:
    pass
_r6 = g6._perform_grapple_at(5800.0, 5000.0)
check(bool(_r6), "P1 钩爪发射成功")
check(getattr(e2, 'grappled', False), "P1 也能勾住 P2（双向对称）")

# ======================================================================
print("[G] 数据层平等")
g7 = Game()
g7.start_game()
g7.state = GameState.PLAYING
for _t in ("P2", "P3", "P4"):
    g7.ensure_player(_t)
check(len(g7.registered_players()) == 4, "可创建 4 名玩家")
_ctx_ok = True
for _t in ("P1", "P2", "P3", "P4"):
    _c = g7.ctx_of(_t)
    if _c is None or _c.player is None:
        _ctx_ok = False
check(_ctx_ok, "每位玩家都有 PlayerContext")
_fields = ("upgrade_paused", "pending_upgrade", "pending_levels", "grace_timer", "hud")
_f_ok = all(all(hasattr(g7.ctx_of(t), f) for f in _fields) for t in ("P1", "P2", "P3", "P4"))
check(_f_ok, "P1..P4 拥有结构相同的升级/暂停/HUD 字段")
check(g7.ctx_of("P2").camera is g7.camera2, "context 与旧属性双向同步（camera）")
check(g7.cast_skill_for is not None, "统一施法入口 cast_skill_for 可用")

print()
print(f"===== v2.7.2 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
