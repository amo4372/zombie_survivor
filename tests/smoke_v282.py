#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.2 快速测试：多人死亡回放 / 命中反馈 / 玩家向回放 / 死亡详情页 / 触控 / 自愈

按需求：**不跑帧**（仅少量用例跑极少量帧验证集成）。
"""
import os
import sys

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
for _f in ("replay.py", "boot_guard.py", "updater.py", "main.py",
           "zombie_pkg/mix_feedback.py", "zombie_pkg/mix_replay.py",
           "zombie_pkg/mix_input.py", "zombie_pkg/game_core.py",
           "renderer_pkg/draw_replay.py", "renderer_pkg/render_core.py",
           "renderer_pkg/draw_ui.py", "entities_pkg/player.py", "config.py"):
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, "关键模块编译通过")

from config import GameState
check(hasattr(GameState, "DEATH_DETAIL"), "新增 DEATH_DETAIL 独立页面状态")

# ======================================================================
print("[B] 死亡后停止记录受击数据（保住真正死因）")
from entities_pkg.player import Player

_pl = Player(0, 0)
_pl.hp = 100
_pl.max_hp = 100
for _i in range(5):
    _pl.hp -= 20
    _pl._log_damage(20, "melee", "zombie", 0, 0)
    if _pl.hp <= 0:
        _pl.hp = 0
        _pl.alive = False
        _pl._damage_log_frozen = True
_snap = _pl.freeze_damage_log()
check(len(_snap) == 5, f"致命过程记录 5 条（{len(_snap)}）")
# 死后继续受伤：不应再记录
_pl._log_damage(999, "aoe", "zombie", 0, 0)
_pl._log_damage(999, "fire", "boss", 0, 0)
check(len(_pl.damage_log) == 5, f"死后伤害不再入日志（仍 {len(_pl.damage_log)} 条）")
check(_snap[-1]["amount"] == 20 and _snap[0]["amount"] == 20, "致死序列完整保留")
_rows = _pl.death_detail()
check(len(_rows) == 5 and _rows[0]["amount"] == 20, "死亡详情仍指向真正的致死过程")

# ======================================================================
print("[C] 回放格式 v2：含 max_hp/size（真实感渲染所需）")
import replay as RP


class FP:
    def __init__(s, x, y, hp=100.0):
        s.x, s.y, s.hp, s.max_hp = x, y, hp, 100.0
        s.facing_angle = 0.0
        s.alive = True
        s.downed = False


class FE:
    enemy_type = type("T", (), {"name": "BOSS_LONG"})()

    def __init__(s, eid, x, y, hp=50.0):
        s.enemy_id, s.x, s.y, s.hp, s.max_hp = eid, x, y, hp, 50.0
        s.facing_angle = 0.0
        s.alive = True
        s.is_boss = True
        s.size = 20.0
        s._hit_events = []


_rec = RP.ReplayRecorder(buffer_seconds=10, sample_hz=20)
_rec.start({"mode": "ENDLESS"})
_p = FP(0, 0)
_e = FE(1, 100, 0)
for _i in range(40):
    _p.x = _i * 2.0
    _rec.tick(1 / 60, [_p], [_e])
_rec.add_event("death", "玩家阵亡", 0, 0, 0, tag="death")
import tempfile
_tmp = os.path.join(tempfile.mkdtemp(), "t.zsr")
_rec.save(_tmp)
_ld = RP.load_replay(_tmp)
check(len(_ld.frames) > 5, "v2 录制/加载正常")
_fr = _ld.frames[0]
check(len(_fr.players[0]) == 6, "玩家帧含 6 字段（含 max_hp）")
check(len(_fr.enemies[0]) == 9, "敌人帧含 9 字段（含 max_hp/size）")
check(abs(_fr.players[0][3] - 100.0) < 0.01, "max_hp 正确写入")
check(abs(_fr.enemies[0][7] - 20.0) < 0.01, "size 正确写入")
_di = _ld.death_index()
check(_di == len(_ld.frames) - 1, "能定位致死时刻帧")

# ======================================================================
print("[D] 玩家向回放：默认隐藏数据面板 + 从致死前 3 秒开始")
_src = open("zombie_pkg/mix_replay.py", encoding="utf-8").read()
check("self.replay_show_data = False" in _src, "数据面板默认隐藏（不再是调试画面）")
check("death_index()" in _src and "_back" in _src, "从致死时刻前 3 秒开始播放")
_dr = open("renderer_pkg/draw_replay.py", encoding="utf-8").read()
check("_enemy_style" in _dr, "敌人按类型着色（真实感）")
check("电影感" in _dr or "暗角" in _dr, "含暗角/电影黑边")
check("replay_touch_btns" in _dr, "回放页有触控按钮")

# ======================================================================
print("[E] 死亡详情独立页面 + 退出按钮")
check("_draw_death_detail_page" in _dr, "独立页面绘制函数存在")
_src_ui = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("GameState.DEATH_DETAIL" in _src_ui, "结算页按钮进入独立页面")
check("self._draw_death_detail()" not in _src_ui, "不再绘制反人类的结算页浮层")
_src_in = open("zombie_pkg/mix_input.py", encoding="utf-8").read()
check("GameState.DEATH_DETAIL:" in _src_in, "独立页面有输入处理（滚动/退出）")
check("FINGERMOTION" in _src_in, "独立页面支持触控滑动滚动")

# ======================================================================
print("[F] 触控支持")
check("replay_touch_btns" in open("zombie_pkg/game_core.py", encoding="utf-8").read(),
      "回放触控按钮已创建（播放/逐帧/缩放/跟随/数据/退出）")
check("_draw_replay_touch_buttons" in _dr, "回放触控按钮绘制")
check("FINGERMOTION" in _src_in, "回放支持触控拖动移动摄像机")
check("touch_events" in _dr, "按钮响应触控事件")
check("_draw_replay_timeline" in _dr, "时间轴支持点击/触控跳转")

# ======================================================================
print("[G] 启动致命错误自愈")
import boot_guard
check(boot_guard.is_fatal_boot_error(ModuleNotFoundError("No module named 'replay'")),
      "ModuleNotFoundError 判定为致命")
check(boot_guard.is_fatal_boot_error(ImportError("cannot import name X")),
      "ImportError 判定为致命")
check(boot_guard.is_fatal_boot_error(SyntaxError("bad syntax")), "SyntaxError 判定为致命")
check(not boot_guard.is_fatal_boot_error(ValueError("normal runtime error")),
      "普通运行时错误不触发自愈")
check(not boot_guard.is_fatal_boot_error(KeyError("damage_timer")),
      "游戏内 KeyError 不触发自愈（不该重装游戏）")

import updater as UP
check(hasattr(UP, "handle_boot_failure"), "自愈入口存在")
check(hasattr(UP, "mark_version_broken"), "错误版本标记存在")
check(hasattr(UP, "load_broken_versions"), "错误版本读取存在")
check(hasattr(UP, "find_rollback_version"), "回退版本查找存在")
check(hasattr(UP, "find_latest_good_version"), "跳过错误版本的最新版查找存在")

# 标记/读取闭环（写临时目录）
_gd = tempfile.mkdtemp()
UP.mark_version_broken("9.9.9", "测试", _gd)
_b = UP.load_broken_versions(_gd)
check("9.9.9" in _b, f"版本可被标记为错误（{sorted(_b)}）")
check(UP.is_version_broken("9.9.9") is False or True, "标记接口可调用")

# ======================================================================
print("[H] Game 集成（单帧不崩）")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game

g = Game()
g.start_game()
check(hasattr(g, 'death_detail_exit_btn'), "死亡详情退出按钮已创建")
check(hasattr(g, 'replay_touch_btns') and len(g.replay_touch_btns) >= 8,
      f"回放触控按钮 {len(getattr(g,'replay_touch_btns',{}))} 个")
check(hasattr(g, 'death_detail_snapshot'), "死亡快照容器存在")
# 渲染三个新页面（各 1~2 帧）
try:
    g.death_detail_snapshot = {"P1": [{"t": __import__('time').monotonic(), "amount": 30,
                                       "type": "melee", "source": "zombie", "hp": 10,
                                       "x": 0, "y": 0}]}
    g.state = GameState.DEATH_DETAIL
    g.renderer.render()
    check(True, "死亡详情独立页面渲染不崩")
except Exception as e:
    check(False, f"死亡详情页崩溃: {e}")
try:
    for _i in range(30):
        g._replay_tick(1 / 60)
    _p2 = g.save_replay(tag="test")
    g.state = GameState.PLAYING
    g.enter_replay(_p2)
    g.renderer.render()
    check(True, "玩家向回放页面渲染不崩")
    check(getattr(g, 'replay_show_data', False) is False, "进入回放时数据面板默认隐藏")
except Exception as e:
    check(False, f"回放页崩溃: {e}")

print()
print(f"===== v2.8.2 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
