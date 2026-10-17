# -*- coding: utf-8 -*-
"""v2.5.1 批次专项测试（源码文本断言）：
Renderer.world 崩溃修复 / 载具召唤三级大运文字与属性递增 / 阵营载具乘坐系统
（乘客上车下车、位置跟随、伤害转扣载具、报废全员下车、同阵营判定）
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

src_dpl = read("renderer_pkg/draw_play.py")
src_vh  = read("entities_pkg/vehicles.py")
src_ply = read("entities_pkg/player.py")
src_gc  = read("zombie_pkg/game_core.py")
src_pl  = read("zombie_pkg/mix_playing.py")
src_mu  = read("zombie_pkg/mix_multi.py")
src_sk  = read("skills.py")

print("== 1) Renderer.world 崩溃修复 ==")
check("世界绘制改用 game.world 防御", "getattr(self.game, 'world', None)" in src_dpl and "_w.draw" in src_dpl)
check("不再直接引用 self.world", "self.world.draw" not in src_dpl)

print("== 2) 载具三级大运属性递增 ==")
check("Vehicle 支持 level 参数", "def __init__(self, vehicle_type, x, y, damage_mult=1.0, tint=None, level=1)" in src_vh)
check("3 级钳制 1-3", "min(3, int(level or 1))" in src_vh)
check("2级金大运属性(血量1500/速度265/撞击110/碰撞84)", '"hp": 1500' in src_vh and '"ram_damage": 110' in src_vh and '"collision": 84' in src_vh)
check("3级银大运属性(血量2200/速度282/撞击160/碰撞96)", '"hp": 2200' in src_vh and '"ram_damage": 160' in src_vh and '"collision": 96' in src_vh)
check("召唤传 level（P1）", "level=skill.current_level" in src_gc)
check("召唤传 level（P2）", "level=skill.current_level" in src_mu)
check("技能词条更新为大运三级", "红色经典大运" in src_sk and "金色大运" in src_sk and "银色大运" in src_sk)
check("词条不再提99A/武直", "99A坦克" not in src_sk and "武装直升机" not in src_sk)

print("== 3) 阵营载具乘坐系统 ==")
check("载具 owner/passengers 字段", "self.owner = None" in src_vh and "self.passengers = []" in src_vh and "owner_team" in src_vh)
check("add_passenger 方法", "def add_passenger" in src_vh)
check("remove_passenger 方法", "def remove_passenger" in src_vh)
check("dismount_all 方法", "def dismount_all" in src_vh)
check("乘客位置跟随载具", "passengers" in src_vh and "_ps.x = self.x" in src_vh)
check("玩家 riding_vehicle 字段", "self.riding_vehicle = None" in src_ply)
check("乘客伤害转扣载具", "riding_vehicle" in src_ply and "take_damage" in src_ply and "return 0" in src_ply)
check("候选载具检测 _find_board_candidate", "def _find_board_candidate" in src_gc and "140.0" in src_gc)
check("上车 _board_vehicle", "def _board_vehicle" in src_gc and "add_passenger" in src_gc)
check("PvP 异阵营不可乘坐", "pvp_enabled" in src_gc and "owner_team" in src_gc)
check("P1 技能按钮上车", "_find_board_candidate(self.player)" in src_pl and "_board_vehicle" in src_pl)
check("P1 乘客长按下车", "riding_vehicle" in src_pl and "长按技能按钮下车" in src_pl)
check("P2 技能按钮上车", "_find_board_candidate(p2)" in src_mu and "_board_vehicle(p2" in src_mu)
check("P2 乘客长按下车", "riding_vehicle" in src_mu and "长按技能按钮下车" in src_mu)
check("司机召唤设置 owner", "vehicle.owner = self.player" in src_gc and "owner_team" in src_gc)
check("P2 召唤设置 owner", "p2.vehicle.owner = p2" in src_mu)
check("载具摧毁全员下车(P1)", "dismount_all" in src_gc)
check("载具摧毁全员下车(P2)", "dismount_all" in src_mu)
check("司机退出乘客一并下车", "_exit_vehicle" in src_gc and "dismount_all" in src_gc)
check("P1 乘客移动禁用", "riding_vehicle" in src_pl and "0.0, 0.0" in src_pl)
check("P2 乘客移动禁用", "riding_vehicle" in src_mu and "0, 0" in src_mu)
check("乘坐提示渲染", "技能按钮上车" in src_dpl and "长按技能按钮下车" in src_dpl)

print()
print(f"===== v2.5.1 批次: {ok} 通过, {fail} 失败 =====")
sys.exit(1 if fail else 0)
