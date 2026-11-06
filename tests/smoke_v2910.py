# -*- coding: utf-8 -*-
"""v2.9.10 测试：日志内全部 Traceback 修复 + 僵尸攻击间隔/攻击范围

日志(game_log.txt) 33 个 Traceback 去重后只有 3 类根因：
  1) UnboundLocalError: GameState  (_draw_game_over 局部 import)
  2) AttributeError: 'NoneType'.update  (_dmg_num 从 entities 导入不存在 → None)
  3) AttributeError: difficulty     (self.difficulty → self.config.difficulty)
另含 1309 次静默忽略的同类 None.update。
"""
import os
import sys
import json
import math
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {msg}")


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def src(path):
    return open(os.path.join(_ROOT, path), encoding="utf-8").read()


print("[A] 日志 Traceback #1：UnboundLocalError: GameState")
_ui = src("renderer_pkg/draw_ui.py")
check("from config import *" in _ui, "模块顶部已导入 GameState")
# 确认 _draw_game_over 函数体内没有局部 import GameState
_seg = _ui[_ui.index("def _draw_game_over"):_ui.index("def _draw_victory")]
check("from config import GameState" not in _seg,
      "函数内不再局部 import（否则 MENU 分支 UnboundLocalError）")
check("import GameState" not in _seg, "函数体内无任何 GameState 导入语句")

print("[B] 日志 Traceback #2：'NoneType' object has no attribute 'update'")
_mp2 = src("zombie_pkg/mix_players.py")
check("from ui_pkg.fx import DamageNumber" in _mp2,
      "_dmg_num 改为从正确位置导入")
check("class _DummyDN" in _mp2, "导入失败也有兜底对象，永不返回 None")
_pl = src("zombie_pkg/mix_playing.py")
check("if any(_d is None for _d in self.damage_numbers)" in _pl,
      "update 循环前置剔除 None")
check("except Exception:\n                self.damage_numbers.remove(dn)" in _pl,
      "单个元素异常不影响整帧")

print("[C] 日志 Traceback #3：AttributeError: difficulty")
check(", 1, self.difficulty)" not in _pl, "旧写法已删除")
check(_pl.count(", 1, self.config.difficulty)") >= 2,
      "全部刷怪点统一改读 config.difficulty")

print("[D] 攻击间隔 / 攻击范围 默认值")
from gamedata import defaults as _D  # noqa: E402
_cfg = _D.extract_enemies()
check(len(_cfg) >= 30, f"数据库可提取 {len(_cfg)} 类僵尸")
check(_cfg["ZOMBIE_NORMAL"]["melee_attack_cooldown"] == 1.2, "普通僵尸 1.2s")
check(_cfg["ZOMBIE_FAST"]["melee_attack_cooldown"] == 0.9, "敏捷僵尸 0.9s")
_boss = [k for k, v in _cfg.items() if v.get("is_boss")]
check(_boss and _cfg[_boss[0]]["melee_attack_cooldown"] == 1.6,
      "Boss 1.6s")
check(all("melee_attack_reach" in v for v in _cfg.values()),
      "全部僵尸都有攻击范围字段")
check("def enemy_melee_defaults" in src("gamedata/defaults.py"),
      "默认值单一来源，enemy.py 与数据库共用")

print("[E] 数据库权威：策划改库后游戏读到新值")
import pygame  # noqa: E402
pygame.init()
pygame.display.set_mode((640, 480))
from gamedata.db import GameDatabase  # noqa: E402
from config import EnemyType  # noqa: E402
_tmp = tempfile.mkdtemp()
_dbpath = os.path.join(_tmp, "game_data.db")
_db = GameDatabase(_dbpath)
_db.reload(force=True)
import sqlite3  # noqa: E402
_c = sqlite3.connect(_dbpath)
_r = _c.execute("SELECT extra FROM enemies WHERE key='ZOMBIE_NORMAL'").fetchone()
_ex = json.loads(_r[0]) if _r and _r[0] else {}
check(_ex.get("melee_attack_cooldown") == 1.2
      and _ex.get("melee_attack_reach") == 10.0,
      f"extra 含攻击参数 {_ex}")
_ex["melee_attack_cooldown"] = 2.5
_c.execute("UPDATE enemies SET extra=? WHERE key='ZOMBIE_NORMAL'",
           (json.dumps(_ex),))
_c.commit()
_c.close()
_db.reload(force=True)
_out = _db.enemy(EnemyType.ZOMBIE_NORMAL, fallback={})
check(_out.get("melee_attack_cooldown") == 2.5,
      f"改库后读回 {_out.get('melee_attack_cooldown')}")

print("[F] 实测：敌人实例属性 + CD 递减")
from entities_pkg.enemy import Enemy  # noqa: E402
from entities_pkg.player import Player  # noqa: E402
_e = Enemy(100, 100, EnemyType.ZOMBIE_NORMAL, 1, "普通")
_f = Enemy(100, 100, EnemyType.ZOMBIE_FAST, 1, "普通")
_b = Enemy(100, 100, EnemyType.BOSS_LONG, 1, "普通")
check(abs(_e.melee_attack_cooldown - 1.2) < 0.01, f"NORMAL={_e.melee_attack_cooldown}")
check(abs(_f.melee_attack_cooldown - 0.9) < 0.01, f"FAST={_f.melee_attack_cooldown}")
check(abs(_b.melee_attack_cooldown - 1.6) < 0.01, f"BOSS={_b.melee_attack_cooldown}")
_e.melee_attack_timers[123] = 1.0
_e.update(0.3, 100, 100, None)
check(abs(_e.melee_attack_timers.get(123, 0) - 0.7) < 0.01, "CD 按 dt 递减")
_e.update(1.0, 100, 100, None)
check(123 not in _e.melee_attack_timers, "CD 到期自动清除")

print("[G] 实测：贴身 3 秒不再每帧扣血")
from game import Game  # noqa: E402
from config import GameState as GS  # noqa: E402
_g = Game()
_g.start_game()
_p = _g.player
_p.hp = _p.max_hp = 10000
_p.dodge_chance = 0.0
_p.armor = 0.0
_p.riot_gear.equipped = False
_e2 = Enemy(_p.x + 20, _p.y, EnemyType.ZOMBIE_NORMAL, 1, "普通")
_e2.knockdown_timer = 0
_e2.speed = 0
_e2.damage = 10
_hits = 0
for _ in range(180):                       # 3 秒 @ 60fps
    _e2.x, _e2.y = _p.x + 20, _p.y        # 强制贴身
    _before = _p.hp
    _g._enemy_collide_damage(_e2, _p, None)
    if _before - _p.hp > 0:
        _hits += 1
    _e2.update(1 / 60, _p.x, _p.y, _p, None)
check(2 <= _hits <= 4,
      f"3 秒贴身命中 {_hits} 次（无 CD 时为 180 次）")

print("[H] 实测：攻击范围（中心距离，非矩形碰撞）")
_p.hp = 10000
_e3 = Enemy(_p.x + 200, _p.y, EnemyType.ZOMBIE_NORMAL, 1, "普通")
_e3.knockdown_timer = 0
_before = _p.hp
_g._enemy_collide_damage(_e3, _p, None)
check(_before == _p.hp, "距离 200 不扣血")
_e3.x = _p.x + _e3.size + _p.size + _e3.melee_attack_reach + 1
_before = _p.hp
_g._enemy_collide_damage(_e3, _p, None)
check(_before == _p.hp, "刚超出 reach 不扣血")
_e3.x = _p.x + _e3.size + _p.size + _e3.melee_attack_reach - 1
_before = _p.hp
_g._enemy_collide_damage(_e3, _p, None)
check(_before - _p.hp > 0, "范围内正常扣血")

print("[I] 实测：P1/P2 各自独立 CD")
_e4 = Enemy(_p.x + 20, _p.y, EnemyType.ZOMBIE_NORMAL, 1, "普通")
_e4.knockdown_timer = 0
_p2 = Player(_p.x, _p.y)
_p2.hp = _p2.max_hp = 10000
_p2.dodge_chance = 0.0
_p2.armor = 0.0
_p2.riot_gear.equipped = False
_p.hp = 10000
_g._enemy_collide_damage(_e4, _p, None)
_a1 = 10000 - _p.hp
_g._enemy_collide_damage(_e4, _p2, None)
_a2 = 10000 - _p2.hp
check(_a1 > 0 and _a2 > 0, f"P1 扣 {_a1}、P2 扣 {_a2}（互不阻塞）")

print("[J] 实测：_draw_game_over 两个分支都不崩")


def _scenario(click_detail):
    _g2 = Game()
    _g2.start_game()
    _g2.state = GS.GAME_OVER
    _g2.touch_events = []
    _g2.renderer._draw_game_over()
    _btn = _g2.gameover_death_btn if click_detail else _g2.gameover_back_btn
    _r = _btn.get_scaled_rect(_g2.scale)
    _pos = (_r.x + _r.width // 2, _r.y + _r.height // 2)
    _g2.touch_events = [{"type": "down", "pos": _pos, "id": 0}]
    _g2.renderer._draw_game_over()
    _g2.touch_events = [{"type": "up", "pos": _pos, "id": 0}]
    try:
        _g2.renderer._draw_game_over()
    except Exception as _ex2:
        return ("EXC", repr(_ex2))
    return ("OK", _g2.state.name)


_r1 = _scenario(True)
_r2 = _scenario(False)
check(_r1[0] == "OK" and _r1[1] == "DEATH_DETAIL",
      f"死亡详情分支 {_r1}")
check(_r2[0] == "OK" and _r2[1] == "MENU",
      f"返回菜单分支 {_r2}（日志里 21 次崩溃点）")

print("[K] 实测：damage_numbers 混入 None 不再打断主循环")
_g3 = Game()
_g3.start_game()
_g3.state = GS.PLAYING          # 跳过开场对话，确保走 _update_playing
_g3.damage_numbers.append(None)
_g3.damage_numbers.append(None)
for _ in range(5):
    _g3.update(1 / 60)
check(sum(1 for d in _g3.damage_numbers if d is None) == 0,
      "None 被自动剔除")
check(_g3._dmg_num(1, 2, 3, (255, 0, 0)) is not None,
      "_dmg_num 永不返回 None")

print("[L] 跑帧冒烟：单人开局 + 菜单各页面")
try:
    _g4 = Game()
    _g4.begin_setup_flow()
    for _ in range(4):
        _g4.draw()
        _g4.touch_events = [{"type": "down", "pos": (640, 120), "id": 0}]
        _g4.draw()
        _g4.touch_events = [{"type": "up", "pos": (640, 120), "id": 0}]
        _g4.draw()
        _g4.touch_events = []
        _nx = _g4.setup_next()
        _st = _g4.setup_state_for(_nx)
        if _st is None:
            _g4.start_game()
            break
        _g4.state = _st
    for _ in range(120):
        _g4.update(1 / 60)
        _g4.draw()
    check(True, "单人完整流程 120 帧无异常")
except Exception as _ex3:
    check(False, f"跑帧异常 {_ex3!r}")

_ok_pages = 0
_g5 = Game()
for _st2 in (GS.MENU, GS.GACHA, GS.SLOT_MACHINE, GS.CODEX,
             GS.RECORDS, GS.ACHIEVEMENTS):
    try:
        _g5.state = _st2
        for _ in range(8):
            _g5.draw()
        _ok_pages += 1
    except Exception:
        pass
check(_ok_pages == 6, f"{_ok_pages}/6 个菜单页渲染正常")

print()
print(f"===== v2.9.10 测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
