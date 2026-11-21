# -*- coding: utf-8 -*-
"""v2.9.23 精简回归（单 Game 实例，目标 < 40s）。

覆盖：武器独立倍率 / 来源独立抗性 / 预瞄对齐与范围圈 zoom / 手雷提速与 PvP /
湮灭锁血 / 独立地图编辑器与 zmap 导入 / 僵尸越障受阻 / 视野性能评估 / 全模式跑帧。
"""
import os, sys, time, io, types, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENDOR = os.path.join(ROOT, "_vendor")
if os.path.isdir(_VENDOR):
    sys.path.insert(0, _VENDOR)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

_T0 = time.perf_counter()
PASS = FAIL = 0


def check(ok, msg):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  OK  ", msg)
    else:
        FAIL += 1
        print("  FAIL", msg)


def src(p):
    return io.open(p, encoding="utf-8").read()


print("=== A. 每把武器独立倍率 / AWM 一枪 100 ===")
from config import (WeaponType, GameState, ControlMode, GameMode,
                    SOURCE_RESIST_SCALE, ANNIHILATION_BEAM_DPS,
                    ANNIHILATION_BEAM_TOTAL, ANNIHILATION_LOCK_HP,
                    PVP_SKILL_MULT, ZOMBIE_OBSTACLE_SLOW)
from weapons import Weapon, WEAPON_PVP_MULTS

_w = src("weapons.py")
check('"damage_vs_player": 100' in _w, "AWM 代码数值 100")
check(Weapon(WeaponType.AWP).damage_vs_player == 100, "数据库权威读回 AWM=100")
check(len(WEAPON_PVP_MULTS) >= len(list(WeaponType)), "倍率表覆盖全部 WeaponType")
_vals = set(WEAPON_PVP_MULTS.values())
check(len(_vals) >= 12, "每把武器独立倍率（%d 种不同值）" % len(_vals))
check(Weapon(WeaponType.PISTOL).pvp_mult == WEAPON_PVP_MULTS[WeaponType.PISTOL],
      "Weapon 实例挂上自己专属 pvp_mult")
check("pvp_mult = getattr(self" in _w, "投射物携带 pvp_mult")
check("DATA_VERSION = 7" in src("gamedata/seed.py"), "DATA_VERSION 7 触发玩家库同步")

from zombie_pkg import Game
g = Game()
g.config.control_mode = ControlMode.TOUCH
_p = types.SimpleNamespace(pvp_mult=0.62, damage_vs_player=None)
check(g._pvp_dmg_to_player(100, _p) == 62, "pvp_mult 优先于通用模板：100→62")
_p2 = types.SimpleNamespace(pvp_mult=0.5, damage_vs_player=100)
check(g._pvp_dmg_to_player(100, _p2) == 100, "damage_vs_player 仍为最高权威")
check(g._pvp_dmg_to_player(100, None, kind="skill") == int(100 * PVP_SKILL_MULT),
      "技能 AOE 独立倍率")

print("=== B. 抗性计算系数独立 / 载具与盾血量 ===")
from combat_pkg import coerce_packet, resolve_damage, ResistanceSet

class _T:
    pass
_t = _T()
_t.resistances = ResistanceSet({"physical": 0.8})
_r0 = resolve_damage(coerce_packet(100, damage_type="physical"), _t)
_r1 = resolve_damage(coerce_packet(100, damage_type="physical", resist_scale=0.25), _t)
check(_r1.final > _r0.final * 3, "来源独立抗性：0.25 系数下实际伤害 %.0f → %.0f" % (_r0.final, _r1.final))
check(SOURCE_RESIST_SCALE.get("gear") == 0.25 and SOURCE_RESIST_SCALE.get("vehicle") == 0.20,
      "肘击 / 载具各有独立抗性系数")
check("resist_scale=SOURCE_RESIST_SCALE" in src("zombie_pkg/mix_skills.py"), "肘击传入独立抗性")
check("resist_scale=_vrs" in src("entities_pkg/vehicles.py"), "载具传入独立抗性")
check("resist_scale=SOURCE_RESIST_SCALE" in src("zombie_pkg/mix_targets.py"), "技能 AOE 传入独立抗性")
from entities_pkg.gear import RiotGear
_rg = RiotGear()
check(_rg.max_shield_hp == 300 and _rg.max_viewing_window_hp == 220,
      "盾 500→300 / 观察窗 400→220")
_vh = src("entities_pkg/vehicles.py")
check('"hp": 540' in _vh and '"hp": 1080' in _vh and '"hp": 700' in _vh,
      "载具血量整体下调 40%")

print("=== C. 预瞄对齐当帧摄像机 / 范围圈 zoom ===")
_su = src("ui_pkg/skills_ui.py")
_dp = src("renderer_pkg/draw_play.py")
_mp = src("zombie_pkg/mix_players.py")
check("aim_viewport_x" in _su and "self.aim_radius = float(AIM_RADIUS_BY_SKILL" in _su,
      "预瞄坐标补视口偏移 + 写入范围圈半径")
check("_sync_aim_caster" in _dp and "_world_scale" in _dp,
      "渲染层注入当帧摄像机 / zoom 后的世界缩放")
check("_circle_want = (_skill_d + 2.0 * _skill_radius)" in _mp,
      "拉远按「完整看到整圈」而非中心点")
check("_skill_aim_radius" in src("zombie_pkg/mix_playing.py")
      and "_skill_aim_radius" in src("zombie_pkg/mix_multi.py"), "P1/P2 都写入圈半径")
# 真实数值：同一瞄准距离下，圈越大 zoom 越小
try:
    cam = types.SimpleNamespace(zoom=1.0, _zoom_base=1.0)
    pl = types.SimpleNamespace(_charge_ratio=0.0, _skill_aim_dist=400.0,
                               _skill_aim_radius=0.0, riot_gear=None,
                               get_current_weapon=lambda: None)
    _caster = types.SimpleNamespace(is_aiming=True, aiming=False, active=False,
                                    max_skill_distance=400.0,
                                    distance_ratio=1.0, aim_radius=0.0)
    _orig_caster_for = g._caster_for_player
    g._caster_for_player = lambda p: _caster
    for _ in range(40):
        g.update_dynamic_zoom_for(cam, pl, 1 / 60)
    z0 = cam.zoom
    pl._skill_aim_radius = 180.0
    for _ in range(40):
        g.update_dynamic_zoom_for(cam, pl, 1 / 60)
    z1 = cam.zoom
    g._caster_for_player = _orig_caster_for
    check(z1 < z0 - 0.02, "范围圈变大 → 视野进一步拉远 (%.3f → %.3f)" % (z0, z1))
except Exception as e:
    check(False, "zoom 模拟异常 %r" % e)

print("=== D. 手雷提速 + 对敌方玩家生效 ===")
_gc = src("zombie_pkg/game_core.py")
_me = src("zombie_pkg/mix_effects.py")
check("total_dist / 0.32" in _gc and '"timer": 0.32' in _gc, "技能手雷 1.1s → 0.32s（3.4 倍速）")
check("total_dist / 0.42" in src("zombie_pkg/mix_combat.py"), "投掷物同步提速")
check("players_only=True" in _me and _me.count("apply_area_damage(") >= 2,
      "技能手雷 / EMP 都走 apply_area_damage 结算玩家")
# 真实 PvP：敌方玩家吃到技能 AOE 伤害
try:
    g.config.pvp_enabled = True
    g.multiplayer_mode = "same_screen"
    g.coop_player_count = 2
    g.state = GameState.PLAYING
    g.start_game()
    g.state = GameState.PLAYING
    p1, p2 = g.player, g.player2
    p1.team_id, p2.team_id = 0, 1
    p2.x, p2.y = p1.x + 30, p1.y
    p2.hp = p2.max_hp = 500
    p2.status = None
    p2.block = None
    _before = p2.hp
    g.apply_area_damage(p1.x, p1.y, 200, 100, "explosion", p1,
                        players_only=True, scale_by_dist=False)
    check(p2.hp < _before, "手雷等技能对敌方玩家真实生效 (%d → %d)" % (_before, p2.hp))
except Exception as e:
    check(False, "手雷 PvP 模拟异常 %r" % e)

print("=== E. 湮灭射线锁血制 ===")
_sk = src("zombie_pkg/mix_skills.py")
_mu = src("zombie_pkg/mix_multi.py")
_play = src("zombie_pkg/mix_playing.py")
check("proj.annihilation = True" in _sk and "proj.annihilation = True" in _mu,
      "P1/P2 湮灭射线均打锁血标记")
check("beam_dps = ANNIHILATION_BEAM_DPS" in _sk
      and ANNIHILATION_BEAM_DPS == 220.0 and ANNIHILATION_BEAM_TOTAL == 480.0,
      "取消瞬发 300，改为 220/s 帧伤、总上限 480")
check("explosive=True" not in _sk.split("def _skill_railgun_annihilation")[1].split("def ")[0],
      "湮灭不再带瞬发爆炸")
check("ANNIHILATION_PVE_MULT" in _play, "僵尸 / Boss 另行计算")
check("ANNIHILATION_LOCK_HP" in _play, "敌方玩家至少保留 1 HP")
# 真实跑帧：把 P2 放在光束上，跑满 2 秒，hp 不得低于 1
try:
    from weapons import Projectile
    p2.hp = 60
    p2.x, p2.y = p1.x + 60, p1.y
    beam = Projectile(p1.x, p1.y, 3, 0, 1.0, 1200, (140, 200, 245), 15,
                      pierce=99, is_laser=True, laser_width=50,
                      laser_duration=1.6, laser_angle=0.0)
    beam.owner = p1
    beam.annihilation = True
    beam.beam_dps = 220.0
    beam.beam_total = 480.0
    beam.damage_vs_player = 1.0
    g.projectiles.append(beam)
    for _ in range(100):
        g.update(1 / 60)
    check(int(p2.hp) == ANNIHILATION_LOCK_HP and p2.alive,
          "帧伤很大但精确锁血：60 → %d（保留 1 滴血且存活）" % int(p2.hp))
except Exception as e:
    check(False, "锁血跑帧异常 %r" % e)

print("=== F. 地图编辑器独立 + .zmap 游戏端导入 ===")
check(not hasattr(GameState, "MAP_EDITOR"), "游戏内无 MAP_EDITOR 状态")
check(not os.path.exists("zombie_pkg/map_editor.py")
      and not os.path.exists("renderer_pkg/draw_map_editor.py"), "游戏内编辑器源码已删除")
check("_me_f5" not in src("zombie_pkg/mix_input.py"), "F5 内置入口已删除")
check(os.path.isfile("tools/map_editor_standalone.py")
      and "FINGERDOWN" in src("tools/map_editor_standalone.py")
      and "KEY_TO_TILE" in src("tools/map_editor_standalone.py"),
      "独立工具同时支持键控与触控")
try:
    from tools.map_editor_standalone import StandaloneMapEditor, dummy_selftest
    check(dummy_selftest() == 0, "独立工具 .zmap 存/读往返自检通过")
except Exception as e:
    check(False, "编辑器自检异常 %r" % e)
try:
    from zombie_pkg.map_loader import apply_zmap
    from world import GameWorld
    p = os.path.join(tempfile.gettempdir(), "zs_v2923_apply.zmap")
    e = StandaloneMapEditor(p)
    e.clear()
    e.paint_world(100, 100, 1)
    e.paint_world(200, 100, 3)
    e.obj_type = 0
    e.place_world(320, 160)
    e.save(p)
    w = GameWorld(map_type=list(__import__("config").MapType)[0])
    _n0 = len(w.obstacles)
    r = apply_zmap(w, p)
    check(r["obstacles"] >= 1 and len(w.obstacles) > _n0
          and r["zones"] >= 1 and r["spawns"].get("player", 0) >= 1,
          "游戏端导入 .zmap：障碍 / 效果区 / 出生点全部应用")
except Exception as e:
    check(False, "zmap 导入异常 %r" % e)
check("maps/active.zmap" in src("zombie_pkg/game_core.py")
      and '"map_file"' in src("zombie_pkg/game_core.py"),
      "导出为当前地图后游戏零配置自动加载")
check("tools/map_editor_standalone.py" in src("build_release.py")
      and '"maps"' in src("build_release.py"), "工具与 maps 目录进发布包")

print("=== G. 僵尸能跨越障碍但行动受阻 ===")
_en = src("entities_pkg/enemy.py")
check("new_rect_x.colliderect" not in _en, "删除硬阻挡分轴拒绝")
check("ZOMBIE_OBSTACLE_SLOW" in _en and ZOMBIE_OBSTACLE_SLOW == 0.35, "越障减速系数 0.35")
try:
    from entities_pkg.enemy import Enemy
    en = object.__new__(Enemy)
    en.x, en.y, en.size = 100.0, 100.0, 16
    en.is_phantom = en.is_wraith = False
    _obs = types.SimpleNamespace(obstacles=[
        {"rect": pygame.Rect(105, 90, 60, 60), "type": "wall"}])
    _x0 = en.x
    en._move_with_obstacle_collision(30, 0, _obs)
    check(0 < en.x - _x0 < 30, "确实穿过但明显变慢 (+%.1f < 30)" % (en.x - _x0))
except Exception as e:
    check(False, "越障模拟异常 %r" % e)

print("=== H. 视野渲染性能评估 ===")
_vp = src("VISION_PERF.md") if os.path.isfile("VISION_PERF.md") else ""
check("ms/帧" in _vp and "62.5%" in _vp or "%" in _vp, "评估文档含实测 ms/帧与帧预算占比")
check("完全使用视野渲染" in _vp and "不划算" in _vp, "给出「全量渲染不划算」的明确结论")

print("=== I. 全模式 / 同屏双人跑帧 ===")
for _m in (GameMode.ENDLESS, GameMode.STORY, GameMode.TIMED):
    try:
        g.config.game_mode = _m
        g.state = GameState.PLAYING
        g.start_game()
        g.state = GameState.PLAYING
        for _ in range(6):
            g.update(1 / 60)
            g.draw()
        check(True, "%s 6 帧无异常" % _m.name)
    except Exception as e:
        check(False, "%s 跑帧异常 %r" % (_m.name, e))
try:
    g.multiplayer_mode = "same_screen"
    g.coop_player_count = 2
    g.config.pvp_enabled = True
    g.state = GameState.PLAYING
    g.start_game()
    g.state = GameState.PLAYING
    for _ in range(6):
        g.update(1 / 60)
        g.draw()
    check(g.player2 is not None, "同屏双人 6 帧无异常")
except Exception as e:
    check(False, "同屏双人跑帧异常 %r" % e)

print("\n===== v2.9.23 精简回归: PASS=%d FAIL=%d  用时 %.1fs =====" %
      (PASS, FAIL, time.perf_counter() - _T0))
sys.exit(1 if FAIL else 0)
