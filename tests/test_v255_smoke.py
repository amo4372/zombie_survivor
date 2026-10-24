# -*- coding: utf-8 -*-
"""v2.5.5 批次测试：运行时错误优先（子进程实跑 main.py 捕获异常）+ 机制断言
覆盖：#138 QTE打断绳索 #139 P2勾取玩家 #140 载具碰撞箱 #141 PvP伤害+AWM/轨道炮
#142 P2角色 #143 边界线 #144 PvP探测+出生点随机 #145 错误静默 #146 冒烟重构
"""
import os
import re
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OK = 0
FAIL = 0

def check(name, cond):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")

def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()

print("== #146 运行时冒烟（子进程真实跑帧，异常即失败） ==")
try:
    r = subprocess.run(
        [sys.executable, "main.py"],
        cwd=ROOT,
        timeout=90,
        env={**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy",
             "ZOMBIE_SMOKE": "1"},
        capture_output=True, text=True)
    out = r.stdout + r.stderr
    has_err = bool(re.search(r"Traceback \(most recent call last\)", out)) or "RuntimeError" in out
    check("子进程退出码=0", r.returncode == 0)
    check("输出含冒烟通过标记", "[SMOKE] 运行时冒烟通过" in out)
    check("无 Traceback/运行时异常", not has_err)
except Exception as e:
    check(f"子进程启动(超时/环境): {e}", False)

gc = read("zombie_pkg/game_core.py")
gp = read("zombie_pkg/mix_playing.py")
ge = read("entities_pkg/gear.py")
pl = read("entities_pkg/player.py")
ve = read("entities_pkg/vehicles.py")
wp = read("weapons.py")
mm = read("zombie_pkg/mix_multi.py")
wl = read("world.py")
dm = read("renderer_pkg/draw_multiplayer.py")
dp = read("renderer_pkg/draw_play.py")
cd = read("codex.py")

print("== #138 打断绳索 QTE（0.8s 扇形单点） ==")
check("qte_window=0.8 初始化", "target.qte_window = 0.8" in ge)
check("扇形打断判定", "def _qte_tap_in_sector" in ge and "math.radians(80)" in ge)
check("qte_break_tap 字段", "qte_break_tap" in pl)
check("单击登记(P1)", "self.player.qte_break_tap" in gp)
check("单击登记(P2)", "p2.qte_break_tap" in mm)
check("QTE渲染打断提示", "点击绳索打断" in dp and "绳索已打断！" in dp)

print("== #139 P2 钩爪勾取 P1 + 锁定玩家 ==")
check("P2 短按勾取倒地队友", "_downed_teammates_of(p2)" in mm)
check("P2 短按勾取敌对玩家", "self._enemy_players_of(p2)" in mm and "pvp_enabled" in mm)
check("锁定优先级玩家>僵尸", "players_enemy" in ge and "players_down" in ge)

print("== #140 载具贴合车体碰撞箱 ==")
check("多圆碰撞箱构建", "_build_collision_hull" in ve and "collision_hull_rel" in ve)
check("贴合车体碰撞检测", "def hull_overlap" in ve)
check("撞击改用贴合碰撞箱", "self.hull_overlap(enemy.x, enemy.y" in ve)

print("== #141 PvP 互伤 + 伤害衰减 + AWM/轨道炮 ==")
check("PvP 伤害缩放 helper", "def _pvp_dmg_to_player" in gc and "0.2" in gc)
check("爆炸AOE衰减+必中", "bypass_dodge=True" in gp)
check("直接命中衰减+必中", "_pvp_dmg_to_player(proj.damage, proj)" in gp)
check("激光命中玩家(轨道炮修复)", "激光武器 PvP" in gp)
check("AWP→AWM 更名", '"name": "AWM"' in wp)
check("AWM 弹夹10/射程/穿透", '"ammo": 10' in wp and '"range": 2600' in wp and '"pierce": 30' in wp)
check("AWM 蓄力开火", "hold_charge" in wp and "_awm_saved" in gp)
check("AWM 弹道预览渲染", "_awm_saved" in dp)
check("轨道炮射速大增+弹夹5+长换弹", '"fire_rate": 1.6' in wp and '"ammo": 5' in wp and '"reload": 5.5' in wp)
check("单发特高伤不作衰减", "pvp_no_atten" in wp)
check("codex 图鉴 AWM", '"name": "AWM"' in cd)

print("== #142 P2 角色效果 + 预瞄渲染 ==")
check("角色加成扩展N人", 'selected_character3' in gc and 'selected_character4' in gc)
check("P2 预瞄按视口隔离(aim_owner)", "aim_owner == \"P2\"" in dp or "aim_owner" in dp)

print("== #143 空气墙边界线 ==")
check("有限地图边界线绘制", "空气墙边界线" in wl)

print("== #144 PvP 周期暴露 + 主动探测 + 出生点随机 ==")
check("PvP 周期暴露保留", "pvp_reveal_active = _c <= 3.0" in gc)
# v2.5.6：常驻近距离暴露已移除，改为脉冲式扫描（详见 tests/test_v256_batch.py）
check("主动探测改为脉冲式（非常驻暴露）",
      "_scan_r = 400.0" not in dm and "pvp_scan_active" in dm)
check("出生点随机化(非固定角)", "_pvp_spawn_pool" in gc and "3000" in gc)

print("== #145 错误静默完善 ==")
check("每次错误弹窗(无raise路径)", '"ask"' in read("error_silencer.py"))
check("强制写错误日志", "ERROR_LOG" in read("error_silencer.py"))
check("三按钮+复制+返回菜单", "_error_ask_menu" in gc and "copy" in gc)

print(f"\n结果: {OK} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
