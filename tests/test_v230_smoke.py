# -*- coding: utf-8 -*-
"""v2.3.0 专项冒烟：
1) 同屏房间固定 2 人（coop_player_count==2，P3/P4 不再创建）
2) 敌人目标选择覆盖全玩家（P1~P2 至少，含 player2）
3) 钩爪直拉模式 direct_pull：长按未锁定→use_grapple(direct_pull=True) 且碰撞检测整体跳过
4) 武器选择栏=图鉴 32 把（含投掷物），投掷物开局附带手枪备用
5) 下拉不再自动清除（"一闪而过"根因移除）
"""
import os, sys, math
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame

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

from config import WeaponType, GameMode, ControlMode
from weapons import Weapon

# ---- 1) 同屏固定 2 人（UI 源码语义）----
src_draw = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "renderer_pkg", "draw_ui.py"), encoding="utf-8").read()
check("同屏房间页固定 2 人（无 count 下拉）",
      '"count"' not in src_draw.split("def _start_multi_room_game")[0].split("def _draw_multi_room_config")[1]
      and "人数：2 人（同屏）" in src_draw)
check("同屏 start 强制 coop_player_count=2",
      ("g.multiplayer_mode = \"same_screen\"" in src_draw
       and "g.coop_player_count = 2  # v2.2.12" in src_draw))
check("阵营数固定 2（无 teams 下拉）", '"teams"' not in src_draw and "2 阵营（1v1）" in src_draw)

# ---- 2) 武器选择栏 = 图鉴 32 把 ----
src_shop = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "zombie_pkg", "mix_shop.py"), encoding="utf-8").read()
check("商店行=全部 WeaponType（含投掷物）", "return list(WeaponType)" in src_shop)

# Weapon 投掷物可构造
g1 = Weapon(WeaponType.GRENADE)
check("投掷物 Weapon 构造", getattr(g1, "is_throwable", False) and g1.max_ammo == 3)
src_pl = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "entities_pkg", "player.py"), encoding="utf-8").read()
check("投掷物开局附带手枪备用", 'self.weapons.append(Weapon(WeaponType.PISTOL))' in src_pl)

# ---- 3) 钩爪直拉模式 ----
src_gear = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "entities_pkg", "gear.py"), encoding="utf-8").read()
check("use_grapple 支持 direct_pull", "direct_pull=False" in src_gear and "grapple_direct_pull" in src_gear)
src_sk = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "zombie_pkg", "mix_skills.py"), encoding="utf-8").read()
# v2.4.0 修复：force_self_pull 残留未定义引用 → 改用 grapple_direct_pull 标志
check("钩爪决策：未锁定长按→grapple_direct_pull 直拉",
      "getattr(rg, 'grapple_direct_pull', False)" in src_sk and "direct_pull=True" in src_sk)
src_pl2 = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "zombie_pkg", "mix_playing.py"), encoding="utf-8").read()
check("碰撞检测直拉模式跳过", "grapple_direct_pull" in src_pl2 and "return" in src_pl2.split("grapple_direct_pull")[1][:80])
check("P1 up 帧保留锁定目标", "not cast_result" in src_pl2 and "grapple_locked_target = None" in src_pl2)
src_mm = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "zombie_pkg", "mix_multi.py"), encoding="utf-8").read()
check("P2 长按未锁定→direct_pull 直拉", "_direct_pull" in src_mm and "direct_pull=locals()" in src_mm)

# ---- 4) 敌人目标选择全玩家（_all_players）----
check("敌人目标遍历 _all_players", "for _pp in self._all_players():" in src_pl2)

# ---- 5) 下拉自动清除移除 ----
check("下拉自动清除已移除（无事件帧不再误关）",
      "room_dropdown = None" in src_draw and "if _dd and not any" not in src_draw)

print(f"\n===== 结果: {ok} 通过, {fail} 失败 =====")
sys.exit(1 if fail else 0)
