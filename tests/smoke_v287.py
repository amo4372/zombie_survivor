#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.7 快速测试

1. AttributeError: 'NoneType' object has no attribute 'draw'（伤害数字列表含 None）
2. 死亡回放按钮一次点击算两次
3. PvP / 多人模式不保存录像、死亡详情空白
4. 钩爪预瞄线/锁定圈泄漏到别的玩家屏幕
5. P2 钩爪自动锁定无效

按需求：**不跑帧**（末尾少量帧验证集成）。
"""
import os
import shutil
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
for _f in ("renderer_pkg/draw_play.py", "mod_loader.py", "ui_pkg/base.py",
           "zombie_pkg/mix_replay.py", "zombie_pkg/mix_feedback.py",
           "zombie_pkg/mix_playing.py", "zombie_pkg/mix_multi.py",
           "entities_pkg/gear.py", "entities_pkg/player.py"):
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, "关键模块编译通过")

# ======================================================================
print("[B] 伤害数字 None 不再打断渲染")
_src = open("renderer_pkg/draw_play.py", encoding="utf-8").read()
check("if dn is None or not hasattr(dn, \"draw\")" in _src,
      "伤害数字遍历前做 None 防御（此前直接 .draw → AttributeError 崩整帧）")
check("self.game.damage_numbers = [" in _src, "渲染时顺手清理不可用元素")
check("if ft is None or not hasattr(ft, \"draw\")" in _src, "浮动文字同样防御")
_sml = open("mod_loader.py", encoding="utf-8").read()
check("from ui import DamageNumber" in _sml, "Mod API 从正确模块导入 DamageNumber")
check("from ui import FloatingText" in _sml, "Mod API 从正确模块导入 FloatingText")

# ======================================================================
print("[C] 按钮一次点击算两次（去抖）")
from ui_pkg.base import Button
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
_b = Button(0, 0, 100, 50, "测试")
check(hasattr(_b, "click_debounce_ms"), "Button 新增去抖间隔")


def _click_seq(mp, pressed, touch=None):
    return _b.update(mp, pressed, touch or [], 1.0)


_r1 = _b.update((50, 25), (True, False, False), [], 1.0)     # 按下
_r2 = _b.update((50, 25), (False, False, False), [], 1.0)    # 抬起 → 第1次
_r3 = _b.update((50, 25), (False, False, False),
                [{"type": "up", "pos": (50, 25)}], 1.0)      # 触控抬起 → 应被去抖
check(_r1 is False and _r2 is True, "鼠标路径首次点击生效")
check(_r3 is False, "紧随其后的触控抬起被去抖（不再算第二次）")
_b2 = Button(0, 0, 100, 50, "测试2")
_b2.update((50, 25), (True, False, False), [], 1.0)
_b2.update((50, 25), (False, False, False), [], 1.0)
time.sleep(0.25)
_b2.update((50, 25), (True, False, False), [], 1.0)
_r4 = _b2.update((50, 25), (False, False, False), [], 1.0)
check(_r4 is True, "超过去抖间隔后的正常连点仍生效（不误伤真实操作）")

# ======================================================================
print("[D] 多人 / PvP 保存录像与死亡详情")
_sr = open("zombie_pkg/mix_replay.py", encoding="utf-8").read()
check("def finalize_replay" in _sr, "新增统一局末归档 finalize_replay")
check("冻结每位玩家的伤害日志" in _sr or "death_detail_snapshot" in _sr, "归档时冻结伤害日志")
_sp = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("finalize_replay(tag=\"victory\")" in _sp,
      "PvP 阵营胜利也归档（此前完全不保存 → 多人无录像）")
_sf = open("zombie_pkg/mix_feedback.py", encoding="utf-8").read()
check("self.finalize_replay(tag=\"death\")" in _sf, "死亡路径改用统一归档")

# ======================================================================
print("[E] 钩爪预瞄不泄漏到别人屏幕")
_sg = open("entities_pkg/gear.py", encoding="utf-8").read()
check("own_view=True" in _sg, "gear.draw 新增 own_view 参数")
check("if own_view and self.grapple_aiming" in _sg,
      "非本人视口不画预瞄/锁定圈（仍画已发射绳索）")
_sp2 = open("entities_pkg/player.py", encoding="utf-8").read()
check("own_view=own_view" in _sp2, "player.draw 透传 own_view")
check("p.draw(self.screen, cam_x, cam_y, self.game.font, scale,\n                           own_view=False)" in _src,
      "其他玩家在本视口绘制时传 own_view=False")

# ======================================================================
print("[F] P2 钩爪自动锁定")
_sm = open("zombie_pkg/mix_multi.py", encoding="utf-8").read()
check("def _p2_grapple_available" in _sm, "新增 P2 钩爪可用性判定")
check("getattr(_rg, 'equipped', False)" in _sm,
      "装备防爆套装即视为钩爪可用（不再只认 GRAPPLE_PULL 技能卡）")
check("_p2_grapple_available(p2)" in _sm, "键控与触控两条分支都改用新判定")

# ======================================================================
print("[G] 集成：多人死亡归档 + 渲染")
try:
    from game import Game
    from config import GameState
    from entities_pkg.player import Player
    shutil.rmtree(os.path.join(_ROOT, "replays"), ignore_errors=True)
    g = Game()
    g.start_game()
    g.player2 = Player(200, 200)
    g.camera2 = type(g.camera)(1280, 720) if getattr(g, 'camera', None) else None
    check(g.is_multiplayer_active(), "多人模式已激活")
    g.state = GameState.PLAYING
    for _i in range(40):
        g._update_playing(1 / 60)
    for _p in g.registered_players():
        _p.hp = 10
        _p._log_damage(20, "melee", "zombie", 0, 0)
        _p.hp = 0
        _p.alive = False
    g._begin_death_reaction()
    check(getattr(g, 'death_replay_saved', False), "多人死亡已保存回放")
    check(os.path.exists(getattr(g, 'replay_last_saved', "") or ""), "回放文件真实存在")
    _snap = getattr(g, 'death_detail_snapshot', {}) or {}
    check(len(_snap) >= 2, f"快照含全部玩家（{list(_snap.keys())}）")
    check(len(g.death_detail_rows()) >= 2, "死亡详情有数据")
    g.renderer.render()
    check(True, "渲染不崩（含 None 防御 / own_view 隔离）")
except Exception as e:
    check(False, f"集成崩溃: {type(e).__name__}: {e}")

print()
print(f"===== v2.8.7 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
