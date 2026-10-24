# -*- coding: utf-8 -*-
"""v2.4.0 批次专项测试（源码文本断言）：
有限大地图 / 滑动栏整体拖动 / boss 软性限制圈 / 阵营胜负(救援同队+胜利页+分阵营计时) /
多人武器角色金币解锁 / 网络联机下滑栏 / 钩爪 force_self_pull 修复
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

src_world = read("world.py")
src_gc = read("zombie_pkg/game_core.py")
src_pl = read("zombie_pkg/mix_playing.py")
src_ef = read("zombie_pkg/mix_effects.py")
src_cb = read("zombie_pkg/mix_combat.py")
src_sk = read("zombie_pkg/mix_skills.py")
src_draw = read("renderer_pkg/draw_ui.py")
src_dp = read("renderer_pkg/draw_play.py")

print("== 1) 有限大地图（world.py + game_core）==")
check("LIMITED_SIZE=12000 常量", "LIMITED_SIZE = 12000" in src_world or "LIMITED_SIZE=12000" in src_world)
check("limited 参数默认", "limited=False" in src_world or "limited=True" in src_world)
check("世界创建全模式 limited=True", "limited=True" in src_gc)
check("出生点左下角 (400, map_size-400)", "map_size - 400" in src_gc or "11600" in src_gc)
check("clamp_position 有限界内", "def clamp_position" in src_world and "bounds" in src_world)
check("空间网格加速 >60 障碍", "_grid" in src_world and "check_collision" in src_world)
check("新局重置阵营状态 victory_team/team_race", "victory_team = None" in src_gc and "_team_race_inited = False" in src_gc)

print("== 2) 滑动栏整体拖动 ==")
# v2.5.0 任务105：下滑栏改为"列表区任意位置按下拖动"（不再仅滚动条列）
check("v2.5.0 列表区任意位置拖动 dd_drag_moved", "dd_drag_moved" in src_draw and "dd_drag" in src_draw)
check("轨道比例映射 sval", "track_h" in src_draw and "sval" in src_draw)

print("== 3) Boss 软性限制圈 ==")
check("boss 生成设置 boss_zone", "boss_zone" in src_pl)
check("出圈拉回（半径/比例拉回）", "boss_zone" in src_pl and "_pull" in src_pl and "拉回" in src_pl)
check("淡红圈渲染", "boss_zone" in src_dp and "SRCALPHA" in src_dp)

print("== 4) 阵营胜负（救援同队+胜利页+分阵营计时）==")
check("救援限同阵营（PvP 异队不可救）", "_same_team" in src_pl and "pvp_enabled" in src_pl and "team_id" in src_pl)
check("分阵营计时器 _init_team_race", "def _init_team_race" in src_pl and "team_race" in src_pl)
check("阵营胜负判定 _check_round_end", "def _check_round_end" in src_pl and "len(_active) <= 1" in src_pl)
check("阵营胜利结算 _trigger_team_victory", "def _trigger_team_victory" in src_pl and "victory_team" in src_pl)
check("game_core 挂载胜负判定", "_check_round_end(dt)" in src_gc and "_trigger_team_victory(_wt)" in src_gc)
check("GAME_OVER 页阵营胜利标题", "阵营胜利" in src_draw and "victory_team" in src_draw)
check("击杀归属阵营（弹道/爆炸/近战）", "_last_hit_team" in src_pl and "_last_hit_team" in src_cb)
check("击杀加时按击杀者阵营", "_team_race_add_time" in src_ef and "_last_hit_team" in src_ef)
check("P1 HUD 分阵营计时显示", "team_race" in src_dp and "出局" in src_dp)

print("== 5) 多人武器/角色金币解锁 ==")
check("房间武器下拉带锁+购买", "_pick_weapon" in src_draw and "is_weapon_owned" in src_draw and "equip_buy_weapon" in src_draw)
check("房间角色下拉带锁+购买", "_pick_char" in src_draw and "is_character_owned" in src_draw and "equip_buy_character" in src_draw)
check("购买反馈提示 multi_room_tip", "multi_room_tip" in src_draw)

print("== 6) 网络联机下滑栏 ==")
check("网络页 _dd_row 下滑栏", "def _dd_row" in src_draw and "net_dd_key" in src_draw)
check("四项均下滑栏", '"net_cnt"' in src_draw and '"net_pvp"' in src_draw and '"net_mode"' in src_draw and '"net_map"' in src_draw)

print("== 7) 钩爪 force_self_pull 热修复 ==")
check("决策段不再引用未定义 force_self_pull",
      "elif force_self_pull:" not in src_sk.split("def _perform_grapple_at")[1].split("def ")[0])
check("改用 grapple_direct_pull 标志", "getattr(rg, 'grapple_direct_pull', False)" in src_sk)

print(f"\n===== v2.4.0 批次: {ok} 通过, {fail} 失败 =====")
sys.exit(1 if fail else 0)
