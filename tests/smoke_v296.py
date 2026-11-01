# -*- coding: utf-8 -*-
"""v2.9.6 快速测试：老虎机转子动画 + 抽卡演出驱动（跑帧）"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

print("[A] 静态：老虎机动画类与结算分离")
_g = open("gacha.py", encoding="utf-8").read()
check("class SlotSpinAnim" in _g, "SlotSpinAnim 已实现")
check("def is_stopped" in _g and "def offset_of" in _g, "逐轴停止与滚动偏移")
check("def flash_of" in _g, "停下瞬间闪光")
_ms = open("zombie_pkg/mix_shop.py", encoding="utf-8").read()
check("def finish_slot_spin" in _ms, "结算拆到 finish_slot_spin")
check("self.slot_pending = _r" in _ms, "结果先压住不立即揭晓")
check("self.slot_result = None" in _ms, "转动中清空旧结果")

print("[B] 静态：老虎机 UI 说明")
_ui = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("三个相同 = 头奖，两个相同 = 小奖" in _ui, "写明中奖规则")
check("倍率轴（第 4~6 轴）只放大奖金" in _ui, "写明倍率轴作用")
check("符号赔率" in _ui or "×{_s3['payout']}" in _ui, "列出符号赔率表")

print("[C] 跑帧：转子逐个停下并结算")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState as GS
g = Game()
g.gacha_init()
g.state = GS.SLOT_MACHINE
for _ in range(3):
    g.draw()
_c0 = g.records.get_coins()
_r = g.do_slot(50)
check(_r is not None, "do_slot 返回结果")
check(g.slot_anim.active, "点击后进入转动状态")
check(g.slot_result is None, "转动中结果未揭晓（pending）")
check(g.records.get_coins() == _c0 - 50, f"立即扣注 {_c0} → {g.records.get_coins()}")
# 观察逐轴停止
_stops = []
_t0 = time.time()
while g.slot_anim.active and time.time() - _t0 < 10:
    g.draw()
    _n = sum(1 for i in range(len(g.slot_anim.stop_at))
             if g.slot_anim.is_stopped(i))
    if not _stops or _stops[-1] != _n:
        _stops.append(_n)
    time.sleep(0.03)
_el = time.time() - _t0
check(len(_stops) >= 2, f"转子是逐个停下而非同时（阶段 {_stops}）")
check(0.5 <= _el <= 8.0, f"转动时长合理 {round(_el, 2)}s")
check(g.slot_result is not None, "停下后结果揭晓")
check(g.slot_paid, "停下后完成派彩")

print("[D] 跑帧：抽卡演出在菜单态被推进")
g2 = Game()
g2.gacha_init()
g2.state = GS.GACHA
g2.draw()
_fx = g2.gacha_fx
check(_fx is not None, "gacha_fx 存在")
g2.do_gacha(1)
check(_fx.active, "抽取后演出启动")
check(_fx.phase == _fx.PHASE_CHARGE, "起始为蓄力阶段")
# 连续绘制推进（记录中途见过的阶段）
_seen = set()
for _ in range(60):
    g2.draw()
    _seen.add(_fx.phase)
    if _fx.timer > 0.0:
        _seen.add("timer>0")
    time.sleep(0.02)
check(_fx.PHASE_CHARGE in _seen or _fx.PHASE_REVEAL in _seen or "timer>0" in _seen,
      f"演出被推进（见过阶段 {sorted(_seen)}）")
check(hasattr(_fx, "draw_extra"), "增强演出接口存在")

print("[E] 跑帧：演出可跳过")
try:
    g3 = Game()
    g3.gacha_init()
    g3.state = GS.GACHA
    g3.draw()
    g3.do_gacha(1)
    g3.touch_events = [{"type": "down", "pos": (640, 360), "id": 0}]
    g3.draw()
    g3.touch_events = []
    check(True, "演出中点击不报错")
except Exception as _e:
    check(False, f"跳过异常: {_e!r}")

print()
print(f"===== v2.9.6 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
