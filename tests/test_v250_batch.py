# -*- coding: utf-8 -*-
"""v2.5.0 批次专项测试（源码文本断言）：
阵营出生点分离 / 钩爪锚点clamp+卡墙断勾 / 勾敌人玩家+QTE挣脱 / 地图边界警示+摄像机clamp /
下滑栏列表区拖动 / 投掷僵尸频率大削 / debuff免疫窗口 / 燃烧弹地面高伤机制 /
冰冻冰块渲染 / 载具碰撞箱加大+透明底 / 狙击/AA12加强+镰刀近战buff / 技能词条审计修复
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

src_gc   = read("zombie_pkg/game_core.py")
src_pl   = read("zombie_pkg/mix_playing.py")
src_sk   = read("zombie_pkg/mix_skills.py")
src_ef   = read("zombie_pkg/mix_effects.py")
src_cb   = read("zombie_pkg/mix_combat.py")
src_gear = read("entities_pkg/gear.py")
src_ply  = read("entities_pkg/player.py")
src_en   = read("entities_pkg/enemy.py")
src_vh   = read("entities_pkg/vehicles.py")
src_buff = read("buff.py")
src_cam  = read("renderer_pkg/camera.py")
src_dui  = read("renderer_pkg/draw_ui.py")
src_dpl  = read("renderer_pkg/draw_play.py")
src_wp   = read("weapons.py")

print("== 1) 阵营出生点分离 ==")
check("按 team_id 四角出生点", "team_id" in src_gc and "出生点" in src_gc)
check("出生点随机化避墙+间距3000", "_margin = 640" in src_gc and "3000" in src_gc and "_pvp_spawn_pool" in src_gc)

print("== 2) 钩爪锚点 clamp + 卡墙断勾 ==")
check("锚点 clamp 到世界边界", "bounds" in src_sk and "clamp" in src_sk)
check("卡墙停滞检测 _pull_stall", "_pull_stall_dist" in src_gear and "_pull_stall_timer" in src_gear and ">= 0.5" in src_gear)
check("停滞断勾 _reset_grapple", "_reset_grapple" in src_gear)

print("== 3) 钩爪勾敌人玩家 + QTE 挣脱 ==")
check("玩家被勾状态 grappled/qte", "grappled" in src_ply and "qte_break_tap" in src_ply and "qte_window" in src_ply)
check("QTE 打断扇形判定", "def _qte_tap_in_sector" in src_gear and "qte_window = 0.8" in src_gear)
check("被勾拉回后眩晕 STUN", "BuffType.STUN" in src_gear)
check("路径目标含异阵营玩家 pvp_enabled", "pvp_enabled" in src_sk and "team_id" in src_sk)
check("被勾 HUD 提示", "被勾住" in src_dpl and "qte" in src_dpl)

print("== 4) 地图边界明显化 + 摄像机 clamp ==")
check("camera.follow 支持 bounds", "bounds" in src_cam and "def follow" in src_cam)
check("follow 传世界边界 bounds=_wbo", "bounds=_wbo" in src_pl)
check("边界警示红框", "地图边界" in src_dpl)

print("== 5) 下滑栏列表区拖动 ==")
check("同屏下拉 dd_drag_moved", "dd_drag_moved" in src_dui and "dd_drag" in src_dui)
check("网络页下拉 net_dd_drag", "net_dd_drag" in src_dui and "net_dd_drag_start" in src_dui)

print("== 6) 投掷僵尸频率大削 ==")
check("初始投掷CD 7-11s", "uniform(7.0, 11.0)" in src_en)
check("投掷后CD 5-9s", "uniform(5.0, 9.0)" in src_en)

print("== 7) debuff 免疫窗口 ==")
check("控制类集合 CONTROL_DEBUFFS", "CONTROL_DEBUFFS" in src_buff)
check("免疫窗口 2 秒", "2.0" in src_buff and "_ctrl_end" in src_buff)
check("到期记录免疫起点", "_ctrl_end[btype]" in src_buff)

print("== 8) 燃烧弹机制重做 ==")
check("直接爆炸伤害调低 0.22", "base_damage * 0.22" in src_ef)
check("地面持续高伤 enemy 35", "take_damage(35)" in src_ef)
check("地面持续高伤 player 12", "take_damage(12" in src_ef)

print("== 9) 冰冻冰块渲染 ==")
check("敌人冰块 is_frozen", "is_frozen()" in src_en)
check("敌人冰块多边形冰晶", "polygon" in src_en and "ice" in src_en.lower())
check("玩家冰块渲染", "player.buff_manager.is_frozen" in src_dpl)

print("== 10) 载具碰撞箱 + 透明底 ==")
check("碰撞箱字段 collision_radius", "collision_radius" in src_vh)
check("撞击判定用 collision_radius", "collision_radius" in src_vh and "enemy" in src_vh)
check("底图黑背景抠透明", "near_bg" in src_vh and "PixelArray" in src_vh)

print("== 11) 武器加强 + 镰刀近战buff ==")
check("AWM 换弹 1.8", '"reload": 1.8' in src_wp)
check("AWM 射程 2600", '"range": 2600' in src_wp)
check("狙击枪 换弹 1.4", '"reload": 1.4' in src_wp)
check("狙击枪 射程 1100", '"range": 1100' in src_wp)
check("AA12 换弹 1.5", '"reload": 1.5' in src_wp)
check("AA12 射程 360", '"range": 360' in src_wp)
check("镰刀吃近战buff MELEE_DAMAGE", "MELEE_DAMAGE" in src_pl and "is_scythe" in src_pl)

print("== 12) 技能词条审计修复 ==")
check("拾取范围对齐词条 +25/级", "current_level * 25" in src_ply)
check("近战精通实现（combat）", "MELEE_DAMAGE" in src_cb)
check("吸血光环实现（击杀回血）", "VAMPIRE_AURA" in src_ef and "heal" in src_ef)
check("嗜血实现（击杀加速）", "BLOODLUST" in src_ef and "SPEED_BOOST" in src_ef)
check("元素精通实现（附魔时长）", "ELEMENTAL_MASTERY" in src_pl and "elem_mult" in src_pl)
check("死亡咏唱实现（击杀减CD）", "KILL_CD_SLASH" in src_ef and "_cut" in src_ef)

print()
print(f"===== v2.5.0 批次: {ok} 通过, {fail} 失败 =====")
sys.exit(1 if fail else 0)
