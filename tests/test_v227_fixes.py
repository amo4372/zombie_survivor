# -*- coding: utf-8 -*-
"""v2.2.7 修复回归：换弹卡死 / 救援反馈 / N人+阵营 / PvPvE / 钩爪机制 / 载具三级 / 回血特效
运行：SDL dummy 下纯逻辑/源码级断言，不启动游戏窗口"""
import os, sys, time
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()

passed = failed = 0
def check(cond, name):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")

print("[A] 换弹卡死修复")
from weapons import Weapon, WeaponType
w = Weapon(WeaponType.RIFLE)
w.current_ammo = 0
w.start_reload()
check(w.is_reloading, "start_reload 进入换弹")
w.reset_reload()
check(not w.is_reloading and w.reload_timer == 0, "reset_reload 强制清换弹状态")
w.current_ammo = 0
w.start_reload()
w.update(0.05)  # 换弹中
check(w.is_reloading, "换弹进行中仍 is_reloading")
src_p = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("_reset_weapons_reload" in src_p, "mix_playing 存在 _reset_weapons_reload helper")
check(src_p.count("_reset_weapons_reload(") >= 3, "倒地/救活/加载三处调用 _reset_weapons_reload")
src_r = open("zombie_pkg/mix_records.py", encoding="utf-8").read()
check("_reset_weapons_reload(self.player)" in src_r, "存档加载后清换弹状态")

print("[B] 救援者 UI 反馈")
check("正在救援" in src_p and "队友正在救援" in src_p, "救援进度浮字（救援者+被救者双方）")
check("_rescue_fb_timer" in src_p, "救援浮字节流计时器")

print("[C] N 人 + 阵营分配")
src_g = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check("coop_player_count" in src_g, "同屏 N 人创建（coop_player_count）")
check("team_id" in src_g, "start_game 全员 team_id 分配（PvPvE 阵营）")
src_m = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("_all_players" in src_m and "player3" in src_m and "player4" in src_m, "P1~P4 全玩家枚举")
check("pvp_enabled" in src_m, "PvPvE 开关判定存在")

print("[D] 钩爪 v2.2.7 机制")
from entities_pkg.gear import RiotGear
g = RiotGear()
check(g.self_pull_speed == 560, f"自我拉拽提速 560（实际 {g.self_pull_speed}）")
src_g2 = open("entities_pkg/gear.py", encoding="utf-8").read()
check("_grapple_aim_charge" in src_g2, "蓄力圈由小到大")
check("_grapple_aim_start" in src_g2, "蓄力计时锚点")
class _SE:
    def __init__(s, x, y, boss=False, alive=True):
        s.x, s.y, s.is_boss, s.alive = x, y, boss, alive
class _SI:
    def __init__(s, x, y, alive=True):
        s.x, s.y, s.alive = x, y, alive
g2 = RiotGear(); g2.grapple_aiming = True; g2.aim_line_angle = 0.0; g2.grapple_max_range = 800
g2._grapple_aim_charge = 1.0; g2._grapple_aim_start = time.time()
lock = g2.update_grapple_lock(0, 0, [_SE(150, 0)], items=[_SI(790, 0)])
check(lock is not None and not hasattr(lock, "is_boss"), "优先锁定特殊道具")
g2b = RiotGear(); g2b.grapple_aiming = True; g2b.aim_line_angle = 0.0; g2b.grapple_max_range = 800
g2b._grapple_aim_charge = 1.0; g2b._grapple_aim_start = time.time()
lock2 = g2b.update_grapple_lock(0, 0, [_SE(790, 0), _SE(700, 0)], items=None)
check(lock2 is not None and lock2.x == 790, "锚点圈内锁定最近非 Boss")
check("_inp_dx" not in src_g2.split("self_pull")[1].split("def _begin_self_pull")[0], "拉取期间禁用玩家位移叠加")
check("grapple_locked_target" in src_m and "items=" in src_m, "锁定传入 world.items（P1）")
src_mm = open("zombie_pkg/mix_multi.py", encoding="utf-8").read()
check("items=" in src_mm and "update_grapple_lock" in src_mm, "P2 锁定传入 items")

print("[E] 载具三级全大运 + 无敌修复")
from entities_pkg.vehicles import Vehicle
v = Vehicle("truck", 0, 0, tint=(225, 55, 40))
check(v.tint == (225, 55, 40), "载具 tint 皮肤（红）")
check("tint" in src_g and "大运重卡" in src_g, "P1 三级全大运（红/金/银）")
check("tint" in src_mm and "大运重卡" in src_mm, "P2 三级全大运")
check("self_pull_active" in src_g and "_reset_grapple" in src_g, "钩爪拉取中召唤载具先终止（防永久无敌）")
check("载具中无法使用钩爪" in src_mm, "P2 载具中禁用钩爪")

print("[F] 回血特效全模式")
src_r2 = open("zombie_pkg/mix_records.py", encoding="utf-8").read()
check("spawn_heal_particles" in src_r2, "回血道具触发绿色粒子（全模式）")

print(f"\n===== 结果: {passed} 通过, {failed} 失败 =====")
sys.exit(1 if failed else 0)
