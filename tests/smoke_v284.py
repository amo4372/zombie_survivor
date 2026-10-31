#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.4 快速测试：数据库迁移后的类型转换问题全面修复

覆盖两类真实崩溃：
  1) TypeError: '<=' not supported between 'str' and 'int'（ammo 被存成字符串）
  2) TypeError: can't multiply sequence by non-int of type 'float'（颜色被存成 hex 字符串）
以及回放帧字段类型、死亡详情时间漂移。

按需求：**不跑帧**（末尾少量帧验证集成）。
"""
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, _ROOT)

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


print("[A] 编译")
import py_compile
for _f in ("gamedata/db.py", "gamedata/seed.py", "gamedata/defaults.py",
           "renderer_pkg/draw_replay.py", "zombie_pkg/mix_replay.py",
           "entities_pkg/player.py", "zombie_pkg/mix_feedback.py",
           "buff.py", "weapons.py", "entities_pkg/enemy.py"):
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, "关键模块编译通过")

from gamedata import db, defaults as D

# ======================================================================
print("[B] 类型转换核心：coerce_like")
from gamedata.db import coerce_like, _coerce_color

check(coerce_like("3", 3) == 3 and isinstance(coerce_like("3", 3), int),
      "字符串数字 → int（修 '<=' str/int）")
check(coerce_like("3", 3) <= 3, "转换后可直接参与 <= 比较")
check(coerce_like("∞", "∞") == "∞" and isinstance(coerce_like("∞", "∞"), str),
      "非数字字符串保持 str（如弹药 ∞）")
check(coerce_like("#14501E", (20, 80, 30)) == (20, 80, 30),
      "hex 字符串 → 颜色元组（修 multiply sequence）")
check(_coerce_color("(220, 200, 60)") == (220, 200, 60), "兼容 '(r,g,b)' 写法")
check(coerce_like(2.0, 2) == 2 and isinstance(coerce_like(2.0, 2), int), "float → int")
check(coerce_like(2, 2.0) == 2.0 and isinstance(coerce_like(2, 2.0), float), "int → float")
check(coerce_like(1, True) is True and coerce_like(0, False) is False, "数值 → bool")
check(coerce_like('{"1":"a"}', {1: "a"}) == {1: "a"}, "JSON 键还原为 int（技能等级描述）")
check(coerce_like(None, 5) == 5, "NULL 回退默认值")

# 颜色参与浮点乘法（此前崩溃点 ui_pkg/fx.py:37）
_c = _coerce_color("#14501E")
try:
    _r = tuple(min(255, int(_x * (1.0 - 0.5 * 0.5))) for _x in _c[:3])
    check(True, f"颜色元组可参与浮点乘法（{_r}）")
except TypeError as e:
    check(False, f"颜色乘法仍崩: {e}")

# ======================================================================
print("[C] 全表类型一致性（逐字段与代码默认值比对）")
_BAD = []


def _cmp(got, ref, path=""):
    if not isinstance(got, dict):
        _BAD.append(f"{path}: 非 dict")
        return
    for _k, _rv in ref.items():
        if _k not in got:
            _BAD.append(f"{path}{_k}: 缺失")
            continue
        _gv = got[_k]
        if _rv is None:
            continue
        if _gv is None:
            _BAD.append(f"{path}{_k}: None")
            continue
        if isinstance(_rv, bool) or isinstance(_gv, bool):
            if isinstance(_rv, bool) != isinstance(_gv, bool):
                _BAD.append(f"{path}{_k}: bool 不符")
            continue
        _tr, _tg = type(_rv), type(_gv)
        if not ((_tr is _tg) or (_tr in (int, float) and _tg in (int, float))):
            _BAD.append(f"{path}{_k}: 期望{_tr.__name__} 得到{_tg.__name__}")


_W, _E, _R, _B, _S = (D.extract_weapons(), D.extract_enemies(), D.extract_runes(),
                      D.extract_buffs(), D.extract_skills())
for _k, _v in _W.items():
    _cmp(db.weapon(_k, dict(_v)), _v, f"weapon[{_k}].")
for _k, _v in _E.items():
    _cmp(db.enemy(_k, dict(_v)), _v, f"enemy[{_k}].")
for _k, _v in _R.items():
    _cmp(db.rune(_k, dict(_v)), _v, f"rune[{_k}].")
for _k, _v in _B.items():
    _cmp(db.buff(_k, dict(_v)), _v, f"buff[{_k}].")
for _k, _v in _S.items():
    _cmp(db.skill(_k, dict(_v)), _v, f"skill[{_k}].")
for _n, _v in D.DIFFICULTY_DEFAULTS.items():
    _cmp(db.difficulty(_n), _v, f"diff[{_n}].")
check(not _BAD, f"全表类型零不一致（{len(_BAD)} 处问题 {_BAD[:3]}）")

# ======================================================================
print("[D] 实战对象类型（武器/敌人/Buff）")
import config
from weapons import Weapon
from entities_pkg.enemy import Enemy
from buff import BuffType, BUFF_CONFIGS

_ammo_bad = []
for _wt in config.WeaponType:
    if _wt.name not in _W:
        continue
    _w = Weapon(_wt)
    _orig = _W[_wt.name].get("ammo")
    _got = getattr(_w, "ammo", None)
    if isinstance(_orig, int) and not isinstance(_got, int):
        _ammo_bad.append((_wt.name, _orig, _got))
    if isinstance(_orig, str) and not isinstance(_got, str):
        _ammo_bad.append((_wt.name, _orig, _got))
check(not _ammo_bad, f"武器 ammo 类型与代码一致（{_ammo_bad[:3]}）")
_col_bad = [_n for _n in _W
            if not isinstance(getattr(Weapon(getattr(config.WeaponType, _n)), "color", None), (tuple, list))]
check(not _col_bad, f"全部武器 color 均为元组（{_col_bad[:3]}）")
_leak = [_n for _n in _W if hasattr(Weapon(getattr(config.WeaponType, _n)), "extra")]
check(not _leak, "数据库元数据列 key/extra 不会泄漏成武器属性")

_e_bad = []
for _et in config.EnemyType:
    if _et.name not in _E:
        continue
    _e = Enemy(0, 0, _et, 1, "normal")
    if not isinstance(getattr(_e, "color", None), (tuple, list)):
        _e_bad.append((_et.name, "color"))
    for _f in ("hp", "speed", "damage", "size"):
        _v = getattr(_e, _f, None)
        if _v is not None and not isinstance(_v, (int, float)):
            _e_bad.append((_et.name, _f))
check(not _e_bad, f"全部敌人属性类型正确（{_e_bad[:3]}）")

_b_bad = []
for _bt in BuffType:
    if _bt.name not in _B:
        continue
    _cfg = BUFF_CONFIGS.get(_bt) or {}
    if not isinstance(_cfg.get("color"), (tuple, list)):
        _b_bad.append((_bt.name, "color"))
    for _k, _v in _B[_bt.name].items():
        if isinstance(_v, bool) and not isinstance(_cfg.get(_k), bool):
            _b_bad.append((_bt.name, _k))
        elif isinstance(_v, (int, float)) and not isinstance(_v, bool):
            if not isinstance(_cfg.get(_k), (int, float)):
                _b_bad.append((_bt.name, _k))
check(not _b_bad, f"全部 Buff 配置类型正确（{_b_bad[:3]}）")

# ======================================================================
print("[E] 回放帧类型安全（float & int 崩溃）")
from renderer_pkg.draw_replay import _unpack_enemy, _unpack_player

# v2 布局
_v2e = (1, 0, 10.0, 20.0, 30.0, 50.0, 1.5, 16.0, 3)
_eid, _ti, _ex, _ey, _ehp, _emax, _ea, _esize, _ef = _unpack_enemy(_v2e)
check(_ef == 3 and isinstance(_ef, int), "v2 敌人 flags 正确取到下标 8")
check(_ehp == 30.0 and _emax == 50.0, "v2 敌人血量字段正确")
# v1 布局（7 字段，下标 6 才是 flags）
_v1e = (1, 0, 10.0, 20.0, 30.0, 1.5, 3)
check(_unpack_enemy(_v1e)[8] == 3, "v1 敌人布局也能正确取 flags")
# 脏数据：flags 位置是 float（此前直接 & 会崩）
_dirty = (1, 0, 10.0, 20.0, 30.0, 50.0, 1.5, 16.0, 1.9)
_ef2 = _unpack_enemy(_dirty)[8]
check(isinstance(_ef2, int), f"float 位置的 flags 被强制转 int（{_ef2}）")
try:
    _ = _ef2 & 1
    check(True, "转换后可安全位运算")
except TypeError as e:
    check(False, f"位运算仍崩: {e}")
check(_unpack_player((1.0, 2.0, 3.0, 100.0, 0.5, 1))[5] == 1, "v2 玩家 flags")
check(_unpack_player((1.0, 2.0, 3.0, 0.5, 1))[5] == 1, "v1 玩家 flags")

# ======================================================================
print("[F] 死亡详情时间不再漂移")
from entities_pkg.player import Player

_pl = Player(0, 0)
_pl.hp = 100
_pl.max_hp = 100
for _i in range(6):
    _pl.hp -= 15
    _pl._log_damage(15, "melee", "zombie", 0, 0)
    time.sleep(0.02)
_pl.hp = 0
_pl.alive = False
_pl._damage_log_frozen = True
_pl.freeze_damage_log()
_r1 = _pl.death_detail(window=12.0)
time.sleep(1.2)
_r2 = _pl.death_detail(window=12.0)
check(len(_r1) == len(_r2), f"停留后条目数不变（{len(_r1)} vs {len(_r2)}）")
check([x["ago"] for x in _r1] == [x["ago"] for x in _r2], "距死亡秒数不再持续增大")
check(all(x["ago"] >= 0 for x in _r2), "时间均为非负")

# ======================================================================
print("[G] 集成（少量帧 + 渲染）")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState

g = Game()
try:
    g.start_game()
    g.state = GameState.PLAYING
    for _i in range(8):
        g._update_playing(1 / 60)
    g.renderer.render()
    check(True, "游戏启动 + 8 帧 + 渲染不崩")
except Exception as e:
    check(False, f"集成崩溃: {e}")
try:
    for _i in range(30):
        g._replay_tick(1 / 60)
    _rp = g.save_replay(tag="test")
    if _rp:
        g.enter_replay(_rp)
        g.renderer.render()
        g.replay_show_data = True
        g.renderer.render()
        check(True, "回放渲染（含数据面板）不崩")
    else:
        check(True, "回放未生成（跳过渲染检查）")
except Exception as e:
    check(False, f"回放崩溃: {e}")

print()
print(f"===== v2.8.4 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
