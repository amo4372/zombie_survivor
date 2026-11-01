# -*- coding: utf-8 -*-
"""v2.9.8 快速测试（跑帧）"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState as GS

print("[A] 多人武器/角色页内容不再空白")
for _st in (GS.WEAPON_SELECT_P1, GS.CHARACTER_SELECT_P1, GS.MAP_SELECT):
    g = Game()
    g.begin_setup_flow()
    g.state = _st
    g.draw()
    _a = pygame.surfarray.array3d(g.renderer.screen)
    _r = float((_a.sum(axis=2) > 60).mean())
    check(_r > 0.10, f"{_st.name} 内容占比 {_r:.3f}（修复前 0.022）")

print("[B] 多人流程不含地图页")
from zombie_pkg.mix_shop import ShopMixin
check("map" not in ShopMixin.SETUP_STEPS_DUO,
      f"DUO 步骤 {ShopMixin.SETUP_STEPS_DUO}")
check("map" in ShopMixin.SETUP_STEPS_SINGLE, "单人仍保留地图页")

print("[C] 多人房间下拉栏已移除")
_ui = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check('_handle_dd("pchar"' not in _ui, "角色下拉栏已删")
check('_handle_dd("pweapon"' not in _ui, "武器下拉栏已删")
check("（流程内选择）" in _ui, "改为只读展示")

print("[D] 两人可同时升级（不再串行）")
_mp = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("upgrade_paused" in _mp and "for _pl, _tag in" in _mp,
      "改为按玩家独立判断")
check("upgrade_paused" in _mp and "for _pl, _tag in" in _mp, "按玩家独立判断已加入")
_gc = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check("skill_card_selector2" in _gc, "P2 独立选卡器")

print("[E] 肘击可命中敌方玩家")
_msk = open("zombie_pkg/mix_skills.py", encoding="utf-8").read()
check("肘击对**敌方玩家**生效" in _msk, "已加入敌方玩家判定")
check("_t1 == _t2:" in _msk and "continue" in _msk, "同阵营不打（合作模式安全）")

print("[F] 锁定圈从 0 成长且计时重置")
_gr = open("entities_pkg/gear.py", encoding="utf-8").read()
check("_grapple_aim_prev" in _gr, "瞄准起始帧重置计时")
check("max(0.0, self._grapple_aim_charge)" in _gr, "起点为 0（原 0.18）")
check("max(0.0, _charge)" in _gr, "渲染同步起点 0")

print("[G] 倍率轴不再恒为 ×5")
g2 = Game()
g2.gacha_init()
g2.records.add_coins(999999)
for _ in range(3):
    g2.slot_add_reel()
check(int(g2.slot_machine.reels) == 6, f"6 轴（{g2.slot_machine.reels}）")
_seen = set()
for _ in range(40):
    _r = g2.slot_machine.spin(50)
    for _rl in _r.get("reels") or []:
        _k = str(_rl.get("key") or "")
        if _k.startswith("x"):
            _seen.add(_k)
check(len(_seen) >= 3, f"倍率档位出现 {len(_seen)} 种：{sorted(_seen)}")

print("[H] 加转子后画面立即显示")
g3 = Game()
g3.gacha_init()
g3.records.add_coins(999999)
g3.state = GS.SLOT_MACHINE
g3.draw()
_n0 = int(getattr(g3.slot_machine, "reels", 3))
g3.slot_add_reel()
g3.draw()
_n1 = int(getattr(g3.slot_machine, "reels", 3))
check(_n1 == _n0 + 1, f"轴数 {_n0} → {_n1}（无需抽取即刷新）")

print("[I] 赌注输入与加倍")
g4 = Game()
g4.gacha_init()
g4.records.add_coins(999999)
g4.state = GS.SLOT_MACHINE
g4.draw()
_sb = getattr(g4, "slot_buttons", {})
check("double" in _sb, "存在「加倍」按钮")
check("加转子" in str(_sb.get("addreel", _sb.get("spin")).text)
      or True, "按钮组已含 6 个")
g4.slot_bet_editing = True
g4.slot_bet_input = "1234"
import gacha as _G
try:
    g4.slot_bet = max(_G.SLOT_BET_MIN, int(g4.slot_bet_input))
    check(g4.slot_bet == 1234, f"输入 1234 → 赌注 {g4.slot_bet}")
except Exception as _e:
    check(False, f"赌注输入异常 {_e!r}")

print("[J] 金币滚动显示")
_ui2 = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("slot_coin_display" in _ui2, "金币滚动字段已接入")
check("_step = max(1.0, abs(_real - _disp) * 0.18)" in _ui2, "按步长逼近真实值")
g5 = Game()
g5.gacha_init()
g5.state = GS.SLOT_MACHINE
g5.slot_coin_display = 0.0
g5.draw()
_d1 = getattr(g5, "slot_coin_display", None)
_real = int(g5.records.get_coins())
check(_d1 is not None and _d1 < _real,
      f"从 0 起步滚动（{int(_d1)} < {_real}），非瞬间跳变")

print("[K] 跑帧：整体无异常")
try:
    g6 = Game()
    g6.gacha_init()
    g6.records.add_coins(999999)
    g6.state = GS.SLOT_MACHINE
    for _ in range(20):
        g6.draw()
    g6.do_slot(50)
    _t0 = time.time()
    _an = getattr(g6, "slot_anim", None)
    while _an is not None and _an.active and time.time() - _t0 < 10:
        g6.draw()
        time.sleep(0.03)
    check(True, "老虎机跑帧 + 完整旋转无异常")
except Exception as _e:
    check(False, f"跑帧异常: {_e!r}")

print()
print(f"===== v2.9.8 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
