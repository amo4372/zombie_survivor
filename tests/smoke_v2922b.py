# -*- coding: utf-8 -*-
"""v2.9.22.1 轻量冒烟：只验数值/机制，不跑长帧、不验画面。"""
import os, sys, io, ast
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

P = 0; F = 0
def ck(cond, name):
    global P, F
    if cond: P += 1
    else:
        F += 1
        print("  FAIL:", name)

def src(p):
    return io.open(p, encoding="utf-8").read()

print("=== A. 版本与画面基线 ===")
ck(src("version.txt").strip() == "2.9.22.1", "version.txt = 2.9.22.1")
ck(not os.path.exists("glrender_pkg"), "无 GPU 渲染包")
ck(not os.path.exists("renderer_pkg/draw_map_editor.py"), "游戏内编辑器已移除")
ck(not os.path.exists("zombie_pkg/map_editor.py"), "编辑器 Mixin 已移除")
ck(os.path.isfile("tools/map_editor_standalone.py"), "独立编辑器存在")
ck(not hasattr(__import__("config").GameState, "MAP_EDITOR"), "无 MAP_EDITOR 状态")

print("=== B. 渲染改动确实没进来 ===")
_dp = src("renderer_pkg/draw_play.py")
ck("_world_scale" not in _dp, "draw_play 未注入 _world_scale")
ck("_sync_aim_caster" not in _dp, "draw_play 未注入当帧预瞄同步")
_ui = src("ui_pkg/skills_ui.py")
ck("AIM_RADIUS_BY_SKILL" not in _ui, "skills_ui 未引入范围圈半径表")
_mp = src("zombie_pkg/mix_players.py")
ck("_circle_want" not in _mp and "_skill_aim_radius" not in _mp, "拉远视野公式保持 2.9.22")
for f in ("zombie_pkg/mix_playing.py", "zombie_pkg/mix_multi.py"):
    ck("_skill_aim_radius" not in src(f), f + " 无范围圈写入")
ck("VISION_PERF.md" in os.listdir("."), "视野性能评估文档保留（结论：不全量启用）")

print("=== C. 武器与数值 ===")
import config
_wp = src("weapons.py")
ck("WEAPON_PVP_MULTS" in _wp and len(ast.parse(_wp).body) > 0, "每把武器独立倍率表存在")
ck('"damage_vs_player": 100' in _wp, "AWM 对玩家 100")
ck("proj.pvp_mult" in _wp, "投射物携带 pvp_mult")
ck("DATA_VERSION = 7" in src("gamedata/seed.py"), "DATA_VERSION = 7")
ck(config.PVP_SKILL_MULT == 0.75, "技能 AOE PvP 倍率 0.75")
ck(config.SOURCE_RESIST_SCALE == {"gear": 0.25, "vehicle": 0.20,
                                  "skill": 0.45, "default": 1.0}, "抗性系数按来源独立")
ck(config.ANNIHILATION_LOCK_HP == 1 and config.ANNIHILATION_BEAM_DPS == 220.0,
   "湮灭射线锁血常量")
ck(config.ZOMBIE_OBSTACLE_SLOW == 0.35, "僵尸越障减速 0.35")

print("=== D. 伤害管线行为 ===")
from combat_pkg.damage import DamagePacket, resolve_damage

class DummyStatus:
    def vulnerability(self, ch): return 0.0
class DummyResistances:
    """对应 combat_pkg.damage.attach_resistances 挂到实体上的对象。"""
    def __init__(self, val): self.val = val
    def get(self, ch): return self.val
    def multiplier(self, ch): return 1.0 - self.val
class DummyTarget:
    def __init__(self, res):
        self.resistances = DummyResistances(res)
        self.status = DummyStatus(); self.hp = 1000
        self.buffs = []; self.alive = True
for scale, expect in ((1.0, 20.0), (0.25, 80.0), (0.20, 84.0), (0.45, 64.0)):
    t = DummyTarget(0.8)
    r = resolve_damage(DamagePacket(base=100, channel="physical",
                                    resist_scale=scale), t)
    ck(abs(r.final - expect) < 1e-6, "抗性 0.8 + 系数 %.2f -> %.0f" % (scale, expect))

_g = src("entities_pkg/gear.py")
ck("self.shield_hp = 300" in _g and "self.viewing_window_hp = 220" in _g, "盾/观察窗耐久下调")
_v = src("entities_pkg/vehicles.py")
ck('"hp": 540' in _v and '"hp": 1080' in _v and '"hp": 700' in _v, "载具耐久下调 40%")
ck("resist_scale=_vrs" in _v, "载具撞击走独立抗性系数")

print("=== E. 机制 ===")
_sk = src("zombie_pkg/mix_skills.py")
ck("proj.annihilation = True" in _sk and "laser_duration=ANNIHILATION_DURATION" in _sk,
   "湮灭射线改持续帧伤")
ck('SOURCE_RESIST_SCALE.get("gear", 0.25)' in _sk, "肘击走独立抗性系数")
_ef = src("zombie_pkg/mix_effects.py")
ck("players_only=True" in _ef and "EMP 同样作用于敌方玩家" in _ef, "EMP/手雷对敌方玩家生效")
_gc = src("zombie_pkg/game_core.py")
ck("total_dist / 0.32" in _gc and '"timer": 0.32' in _gc, "技能手雷提速到 0.32s")
ck("total_dist / 0.42" in src("zombie_pkg/mix_combat.py"), "投掷物提速到 0.42s")
ck("maps/active.zmap" in _gc and "map_file" in _gc, ".zmap 零配置导入")
ck("ZOMBIE_OBSTACLE_SLOW" in src("entities_pkg/enemy.py"), "僵尸越障减速")
_ta = src("zombie_pkg/mix_targets.py")
ck('kind="skill"' in _ta and "SOURCE_RESIST_SCALE" in _ta, "技能 AOE 独立倍率+抗性系数")
_pl = src("entities_pkg/player.py")
ck("lock_hp is not None" in _pl and "resist_scale=resist_scale" in _pl, "玩家伤害支持锁血与抗性系数")

print("=== F. 网络联机仍为空实现 ===")
ck(not os.path.exists("net.py") and not os.path.exists("net_discovery.py")
   and not os.path.exists("net_p2p.py"), "联机模块未回归")

print("\n===== v2.9.22.1 冒烟: PASS=%d FAIL=%d =====" % (P, F))
sys.exit(0 if F == 0 else 1)
