# -*- coding: utf-8 -*-
"""v2.5.4 批次专项测试（源码文本断言）：
#135 强化僵尸AI：低血玩家优先目标 + 决策树狩猎/协同/治疗站位/闪避强化
#136 完善多人UI：N人玩家全部绘制+头顶血条/阵营/倒地倒计时 + 载具血条 + HUD阵营角标
#137 完善全部成就额外文字：所有成就均有 detail 详细文本
"""
import os
import re
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

src_ai = read("ai_pkg/zombie_ai.py")
src_mp = read("zombie_pkg/mix_playing.py")
src_dp = read("renderer_pkg/draw_play.py")
src_rc = read("records.py")

print("== #135 强化僵尸AI ==")
check("目标选择低血玩家优先", "0.6 + 0.8 * _hp_r" in src_mp and "_score = _d *" in src_mp)
check("玩家血比进入上下文", "player_hp_ratio" in src_ai)
check("狩猎条件", "def _c_hunt" in src_ai and "def _c_packed" in src_ai and "def _c_lone" in src_ai and "def _c_ally_near" in src_ai and "def _c_self_hurt" in src_ai)
check("近战树狩猎冲杀", "hunt_charge" in src_ai and "1.35" in src_ai)
check("近战孤立贴脸", "lone_rush" in src_ai)
check("近战成堆包抄加强", "1.1 if not self._c_packed(c, 3) else 1.3" in src_ai)
check("远程狩猎后撤阈值降低", "0.35 if self._c_hunt(c) else 0.45" in src_ai)
check("爆炸僵尸狩猎加速", "1.25 if not self._c_hunt(c) else 1.5" in src_ai)
check("治疗僵尸站位奶(停住)", "heal_stay" in src_ai and "stand_heal" in src_ai)
check("治疗僵尸自保后撤", "self_hurt" in src_ai and "fallback" in src_ai)
check("闪避更快", "self._move_strafe(c, 1.25)" in src_ai)

print("== #136 完善多人UI ==")
check("多人遍历全部玩家绘制", "_mp_players = [pp for pp in self.game._all_players()" in src_dp)
check("头顶血条+名字+阵营色", "_tname" in src_dp and "_tcol" in src_dp and "_wid = max(28" in src_dp)
check("倒地倒计时+救援进度", "_dleft" in src_dp and "rescue_progress" in src_dp)
check("载具头顶血条", "_vpx" in src_dp and "(255, 160, 60)" in src_dp)
check("冰冻渲染覆盖P3/P4", "player3" in src_dp and "player4" in src_dp)
check("HUD阵营角标", "f\"{label} · {_tname2}\"" in src_dp)
check("HUD载具血条+下车提示", "长按技能下车" in src_dp and "riding_vehicle" in src_dp)

print("== #137 完善全部成就额外文字 ==")
def blocks(src):
    out = {}
    for m in re.finditer(r'"([a-z0-9_]+)"\s*:\s*\{', src):
        key = m.group(1)
        i = m.end() - 1; depth = 0; j = i
        while j < len(src):
            if src[j] == '{': depth += 1
            elif src[j] == '}':
                depth -= 1
                if depth == 0:
                    out[key] = src[m.start():j + 1]
                    break
            j += 1
    return out
bs = blocks(src_rc)
achs = {k: v for k, v in bs.items() if '"unlocked"' in v}
no_detail = [k for k, v in achs.items() if '"detail"' not in v]
check("全部成就均有detail", len(no_detail) == 0)
check("成就总数>=64", len(achs) >= 64)
check("新补detail有实质内容", len([v for k, v in achs.items() if '"detail"' in v and len(v.split('"detail"')[1]) > 30]) >= 60)

print(f"\n结果: {ok} 通过, {fail} 失败")
sys.exit(1 if fail else 0)
