# -*- coding: utf-8 -*-
"""v2.9.7 快速测试（跑帧）"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

print("[A] 三件投掷道具已移出武器")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState as GS
g = Game()
_names = [r[1] for r in g.get_weapon_shop_rows()]
for _n in ("手雷", "燃烧瓶", "烟雾弹"):
    check(_n not in _names, f"武器列表已移除 {_n}")
import weapon_pool
_pool = weapon_pool.build_pool()
for _n in ("手雷", "燃烧瓶", "烟雾弹"):
    check(not any(p.get("name") == _n for p in _pool), f"奖池已移除 {_n}")
check(len(_pool) == len(_names), f"列表与奖池一致 ({len(_names)})")

print("[B] 倍率上调至 10000")
from gacha import SLOT_MULTIPLIERS
_mx = max(int(m["payout"]) for m in SLOT_MULTIPLIERS)
check(_mx >= 10000, f"最高倍率档位 {_mx}")
check(any(m["payout"] == 1000 for m in SLOT_MULTIPLIERS), "含 ×1000 档")
check(all("weight" in m for m in SLOT_MULTIPLIERS), "各档均有权重")
from gacha import SLOT_PAYOUT_CAP
check(SLOT_PAYOUT_CAP > 0, f"派彩上限 {SLOT_PAYOUT_CAP}")

print("[C] 可花金币追加转子（最多 +3）")
g2 = Game()
g2.gacha_init()
_c = int(getattr(g2.slot_machine, "reels", 3))
check(_c == 3, f"初始 {_c} 轴")
g2.records.add_coins(100000)
_ok = [g2.slot_add_reel() for _ in range(3)]
check(all(_ok), "连续添加 3 个均成功")
check(int(g2.slot_machine.reels) == 6, f"达到 6 轴（{g2.slot_machine.reels}）")
check(not g2.slot_add_reel(), "第 4 次被拒绝（上限）")
g2.state = GS.SLOT_MACHINE
g2.draw()
_sb = getattr(g2, "slot_buttons", {})
check("addreel" in _sb, "存在「加转子」按钮")
check("转子已满" in str(_sb["addreel"].text), f"满轴时按钮文案「{_sb['addreel'].text}」")

print("[D] 抽卡演出：铺垫阶段存在且不立即揭示")
from gacha import GachaFx
_fx = GachaFx()
check(hasattr(_fx, "PHASE_FLASH"), "新增 FLASH 闪光阶段")
check(_fx.charge_dur >= 1.2, f"铺垫时长 {_fx.charge_dur}s（原 0.85）")
g3 = Game()
g3.gacha_init()
g3.state = GS.GACHA
g3.draw()
g3.records.add_coins(999999)
g3.do_gacha(1)
check(g3.gacha_fx.phase == GachaFx.PHASE_CHARGE, "抽取后进入铺垫阶段")
check(g3.gacha_fx.cur is not None, "结果已备好但尚未展示")
# 推进到闪光
for _ in range(80):
    g3.draw()
    if g3.gacha_fx.phase != GachaFx.PHASE_CHARGE:
        break
    time.sleep(0.02)
check(g3.gacha_fx.phase in (GachaFx.PHASE_FLASH, GachaFx.PHASE_REVEAL),
      f"铺垫后进入 {g3.gacha_fx.phase}")
_seen = set()
for _ in range(150):
    g3.draw()
    _seen.add(g3.gacha_fx.phase)
    time.sleep(0.02)
check(GachaFx.PHASE_FLASH in _seen or GachaFx.PHASE_REVEAL in _seen,
      f"演出完整推进（见过 {sorted(_seen)}）")

print("[E] 已抽中武器可滑动查看")
g4 = Game()
g4.gacha_init()
g4.state = GS.GACHA
g4.records.add_coins(999999)
g4.do_gacha(10)
check(len(g4.gacha_result or []) >= 5, f"十连产出 {len(g4.gacha_result or [])} 件")
g4.draw()
check(hasattr(g4, "gacha_result_scroll"), "存在滑动偏移字段")
check(hasattr(g4, "gacha_result_sel"), "存在选中索引字段")
# 模拟横向拖动
g4.touch_events = [{"type": "down", "pos": (600, 200), "id": 0}]
g4.draw()
g4.touch_events = [{"type": "move", "pos": (300, 200), "id": 0}]
g4.draw()
g4.touch_events = [{"type": "up", "pos": (300, 200), "id": 0}]
g4.draw()
g4.touch_events = []
check(int(getattr(g4, "gacha_result_scroll", 0)) > 0,
      f"拖动后产生滑动偏移 {getattr(g4, 'gacha_result_scroll', 0)}")

print("[F] 跑帧：整体无异常")
try:
    for _st in (GS.GACHA, GS.SLOT_MACHINE):
        g5 = Game()
        g5.gacha_init()
        g5.records.add_coins(999999)
        g5.state = _st
        for _ in range(20):
            g5.draw()
        if _st == GS.SLOT_MACHINE:
            g5.do_slot(50)
            _t0 = time.time()
            _an = getattr(g5, "slot_anim", None)
            while _an is not None and _an.active and time.time() - _t0 < 10:
                g5.draw()
                time.sleep(0.03)
    check(True, "两个页面各跑 20 帧 + 一次完整旋转无异常")
except Exception as _e:
    check(False, f"跑帧异常: {_e!r}")

print()
print(f"===== v2.9.7 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
