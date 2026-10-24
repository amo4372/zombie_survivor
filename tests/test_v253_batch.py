# -*- coding: utf-8 -*-
"""v2.5.3 批次专项测试（源码文本断言）：
#133 多人刷怪每个玩家周围都刷新（随机中心 + 轮转中心）
#134 QTE 操作与画面反馈增强（窗口/免疫/成功失败提示/环形渲染/命中闪光/边缘脉冲）
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()

ok = 0
fail = 0
def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail += 1
        print(f"  [FAIL] {name}")

src_gc = read("zombie_pkg/game_core.py")
src_mp = read("zombie_pkg/mix_playing.py")
src_ge = read("entities_pkg/gear.py")
src_pl = read("entities_pkg/player.py")
src_dp = read("renderer_pkg/draw_play.py")

print("== #133 每个玩家周围都会刷新怪物 ==")
check("随机刷怪中心方法", "def _random_spawn_center" in src_gc and "random.choice(_avail)" in src_gc)
check("轮转刷怪中心方法", "def _next_spawn_center" in src_gc and "_mp_spawn_idx" in src_gc)
check("主刷怪改用随机中心", "self._random_spawn_center()" in src_mp)
check("额外刷怪改用轮转中心", "self._next_spawn_center()" in src_mp)
check("排除倒地/升级暂停玩家", "_downed' is False and not getattr(p, 'upgrade_paused', False)" in src_gc or "getattr(p, 'downed', False) is False" in src_gc)

print("== #134 QTE 操作与画面反馈增强 ==")
check("player QTE 打断字段", "qte_break_tap" in src_pl and "qte_rope_from" in src_pl and "qte_rope_to" in src_pl and "qte_break_hint" in src_pl)
check("输入命中登记单击点", "self.qte_break_tap = None" in src_pl and "qte_break_tap" in src_pl)
check("反馈计时衰减", "qte_success_timer - dt" in src_pl and "qte_immune_timer - dt" in src_pl)
check("打断窗口 0.8s", "qte_window = 0.8" in src_ge)
check("扇形打断判定", "def _qte_tap_in_sector" in src_ge)
check("打断失败提示", "qte_break_fail" in src_ge or "被捕获！" in src_ge or "qte_break_hint" in src_ge)
check("打断成功解除勾取", "grapple_active = False" in src_ge and "qte_break" in src_ge)
check("免疫期间不可再勾", "qte_immune_timer', 0) > 0" in src_ge and "return False" in src_ge)
check("环形倒计时渲染", "环形倒计时" in src_dp or "math.radians(-90 + _a)" in src_dp)
check("扇形提示渲染", "math.radians(80)" in src_dp)
check("命中闪光环", "_q_flash > 0.12" in src_dp)
check("边缘红色脉冲", "(220, 30, 30, _ea)" in src_dp)
check("成功/失败文字", "绳索已打断！" in src_dp and "被捕获！" in src_dp)
check("打断提示文案", "点击绳索打断" in src_dp)
check("命中播放音效", 'play_sound("ui_click")' in src_dp)

print(f"\n结果: {ok} 通过, {fail} 失败")
sys.exit(1 if fail else 0)
