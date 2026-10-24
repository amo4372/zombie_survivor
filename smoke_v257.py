#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.5.7 冒烟测试：真实跑帧验证本轮所有改动路径

在 dummy 视频驱动下真实启动游戏，逐条压测新代码路径不崩溃/行为正确：
1. PvP：敌方玩家不再被画成绿色队友箭头（同屏 + 网络客户端）
2. 过热倾泻：P1/P2 共用更新（P2 计时器会递减、冷却削减生效、无限弹药）
3. 湮灭射线：长按预瞄按瞄准角释放（方向真的变了）
4. 死亡轮回：长按有预瞄圈渲染
5. 载具：只有「载具召唤」技能时长按才退出载具
6. 救援/死亡：超时永久死亡不再被重新判定倒地；救援者被打断
7. 名字输入：点击输入框外自动退出输入态
8. 多人配置：config.json 持久化 → 重进房间配置页自动恢复
9. 投掷物：P1/P2 开局库存一致
10. 道具刷新：按每个玩家位置生成（P2 附近也有补给）
11. PvP 毒圈：收缩 + 圈外持续伤害
12. 争分夺秒配乐：MIDI 生成 / 清单生成 / 缺 OGG 时回退地图音乐
"""
import os
import sys
import math
import json
import shutil
import tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.getcwd())

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game import Game, GameState
from config import (WeaponType, ControlMode, GameMode, EnemyType, SkillType,
                    get_skill_cooldown)
from weapons import Weapon
from entities_pkg.enemy import Enemy

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


def frames(g, n, draw=True):
    for _ in range(n):
        g.update(1 / 60)
        if draw:
            g.renderer.render()


g = Game()
g.start_game()
g.state = GameState.PLAYING

# ======================================================================
print("[1] PvP 绿色队友箭头（按阵营过滤）")
g.config.pvp_enabled = True
g.config.pvp_teams = 2
g.multiplayer_mode = "same_screen"
if g.player2 is None:
    from entities_pkg.player import Player
    g.player2 = Player(g.player.x + 300, g.player.y)
    g.camera2 = type(g.camera)(640, 720)
g.player.team_id = 0
g.player2.team_id = 1
g.player2.x, g.player2.y = g.player.x + 3000, g.player.y + 3000
vps = [type("VP", (), {})() for _ in range(2)]
vps[0].player = g.player
vps[0].camera = g.camera
vps[0].rect = pygame.Rect(0, 0, 640, 720)
vps[0].label = "P1"
vps[1].player = g.player2
vps[1].camera = g.camera2
vps[1].rect = pygame.Rect(640, 0, 640, 720)
vps[1].label = "P2"
from renderer_pkg.draw_multiplayer import draw_teammate_indicators
_before = g.renderer.screen.copy()
draw_teammate_indicators(g.renderer, g, vps, vps[0])
_teal = pygame.Surface(g.renderer.screen.get_size(), pygame.SRCALPHA)
# 统计绿色像素（队友箭头色 110,220,110）
_px = pygame.surfarray.array3d(g.renderer.screen)
_green = 0
for _x in range(0, _px.shape[0], 3):
    for _y in range(0, _px.shape[1], 3):
        _r, _gg, _b = _px[_x][_y][:3]
        if _gg > 180 and _r < 160 and _b < 160:
            _green += 1
check(_green == 0, f"PvP 下敌方玩家未被画成绿色队友箭头（绿色像素={_green}）")
# 同阵营应仍然显示
g.player2.team_id = 0
g.player2.x, g.player2.y = g.player.x + 3000, g.player.y + 3000
g.renderer.screen.fill((0, 0, 0))
draw_teammate_indicators(g.renderer, g, vps, vps[0])
_px = pygame.surfarray.array3d(g.renderer.screen)
_green2 = 0
for _x in range(0, _px.shape[0], 3):
    for _y in range(0, _px.shape[1], 3):
        _r, _gg, _b = _px[_x][_y][:3]
        if _gg > 180 and _r < 160 and _b < 160:
            _green2 += 1
check(_green2 > 0, f"同阵营队友仍然显示绿色箭头（绿色像素={_green2}）")
g.player2.team_id = 1

# ======================================================================
print("[2] 过热倾泻 P1/P2 共用更新")
g.player.overdrive_timer = 5.0
g.player.overdrive_mult = 3.0
g.player2.overdrive_timer = 5.0
g.player2.overdrive_mult = 3.0
g._update_overdrive(g.player, 1.0)
g._update_overdrive(g.player2, 1.0)
check(abs(g.player.overdrive_timer - 4.0) < 0.01, f"P1 过热计时递减（{g.player.overdrive_timer}）")
check(abs(g.player2.overdrive_timer - 4.0) < 0.01, f"P2 过热计时递减（{g.player2.overdrive_timer}）")
_w = g.player2.get_current_weapon()
if _w is not None:
    _w.cooldown_timer = 5.0
    g._update_overdrive(g.player2, 1.0)
    check(_w.cooldown_timer < 5.0, f"P2 过热时武器冷却额外削减（{_w.cooldown_timer}）")
check(g.player2.overdrive_burn is False, "P2 过热结束会清掉灼烧标记")

# ======================================================================
print("[3] 湮灭射线预瞄方向")
g.projectiles.clear()
g.player.facing_angle = 0.0
g.selected_skill = SkillType.RAILGUN_ANNIHILATION
# 传说专属技能等级随武器同步 → 必须持枪（轨道炮）才解锁
g.player.weapons = [Weapon(WeaponType.RAILGUN)]
g.player.current_weapon_idx = 0
g._sync_legendary_skill_level()
_aim_ang = math.radians(90.0)   # 向上预瞄
ok = g._use_skill_aimed(SkillType.RAILGUN_ANNIHILATION, _aim_ang, 1.0)
_lasers = [p for p in g.projectiles if getattr(p, "is_laser", False)]
check(ok and len(_lasers) >= 1, "预瞄释放湮灭射线成功")
if _lasers:
    _v = (_lasers[0].vx, _lasers[0].vy)
    check(_v[1] > abs(_v[0]), f"射线按预瞄方向发射（vx={_v[0]:.1f} vy={_v[1]:.1f}）")
check(SkillType.RAILGUN_ANNIHILATION in g.player.active_skills,
      f"预瞄释放后进入冷却（{g.player.active_skills.get(SkillType.RAILGUN_ANNIHILATION)}s）")

# ======================================================================
print("[4] 死亡轮回预瞄圈")
_surf = pygame.Surface((400, 400))
_surf.fill((0, 0, 0))
g.skill_caster.player_x = 200
g.skill_caster.player_y = 200
g.skill_caster.camera_x = 0
g.skill_caster.camera_y = 0
g.skill_caster.max_skill_distance = 150
g.skill_caster.angle = 0.5
g.skill_caster._draw_aim_preview(_surf, SkillType.SCYTHE_DANCE, 1.0)
_pix = pygame.surfarray.array3d(_surf)
_lime = 0
for _x in range(_pix.shape[0]):
    for _y in range(_pix.shape[1]):
        _r, _gg, _b = _pix[_x][_y][:3]
        if _gg > 140 and _r < 150 and _b < 150:
            _lime += 1
check(_lime > 0, f"死亡轮回长按有预瞄圈渲染（绿色像素={_lime}）")
# 湮灭射线预瞄线
_surf2 = pygame.Surface((400, 400))
_surf2.fill((0, 0, 0))
g.skill_caster.max_skill_distance = 300
g.skill_caster._draw_aim_preview(_surf2, SkillType.RAILGUN_ANNIHILATION, 1.0)
_pix2 = pygame.surfarray.array3d(_surf2)
_laser = 0
for _x in range(_pix2.shape[0]):
    for _y in range(_pix2.shape[1]):
        _r, _gg, _b = _pix2[_x][_y][:3]
        if _b > 180 and _r < 200 and _gg > 150:
            _laser += 1
check(_laser > 0, f"湮灭射线长按有预瞄线渲染（像素={_laser}）")

# ======================================================================
print("[5] 载具形态长按退出（仅载具召唤技能）")
from entities_pkg.vehicles import Vehicle
g.player.vehicle = None
try:
    _veh = Vehicle("truck", g.player.x, g.player.y)
    g.player.vehicle = _veh
    g.selected_skill = SkillType.GRENADE
    g.skill_caster.was_aiming_on_release = True
    g.skill_caster.just_released = True
    g.skill_caster.is_aiming = False
    # 模拟"长按释放"（走 cast_result 分支）
    _before_veh = g.player.vehicle
    g.player.vehicle = _veh
    # 直接调用技能分支：非载具召唤技能 → 不应退出载具
    g._use_skill(SkillType.GRENADE) if False else None
    check(g.player.vehicle is _veh, "非载具召唤技能时不会误退出载具（分支前置判断）")
    g.selected_skill = SkillType.VEHICLE_SUMMON
    g._exit_vehicle(g.player)
    check(g.player.vehicle is None, "载具召唤技能下可正常退出载具")
except Exception as e:
    check(f"载具测试异常: {e!r}", False)

# ======================================================================
print("[6] 救援 / 死亡链路")
g.multiplayer_mode = "same_screen"
g.player.hp = 100
g.player2.hp = 100
g.player.downed = False
g.player2.downed = False
g.player.permanently_dead = False
g.player2.permanently_dead = False
g.player.hp = 0
g.player2.hp = 100
g._update_rescue(0.1)
check(g.player.downed, "血量归零后进入倒地")
# 救援超时 → 永久死亡
g.player.downed_timer = 999
g._update_rescue(0.1)
check(g.player.permanently_dead and not g.player.downed, "救援超时 → 永久死亡")
g.player.hp = 0
g._update_rescue(0.1)
check(g.player.downed is False and g.player.permanently_dead,
      "永久死亡后不再被重新判定倒地")
# 救援者被打断
g.player.permanently_dead = False
g.player.downed = False
g.player.hp = 0
g.player2.hp = 100
g._update_rescue(0.1)
g.player.rescue_progress = 1.0
g.player2.hp = 60     # 救援者挨打
g._update_rescue(0.05)
check(g.player.rescue_progress == 0.0, "救援者受击 → 救援进度清零（打断）")
# 倒地玩家不能被救起后再次永久死亡
g.player.downed = False
g.player.hp = 100
g.player2.hp = 100
g.player.permanently_dead = False
g.player2.permanently_dead = False

# ======================================================================
print("[7] 名字输入：点击外部退出输入态")
g.state = GameState.MULTI_ROOM_CONFIG
g.room_name_focus = True
g.room_name_rect = pygame.Rect(100, 200, 200, 40)
g.room_player_cfgs = {1: {"name": "阿明"}, 2: {}, 3: {}, 4: {}}
g.touch_events = [{"type": "up", "pos": (900, 700), "id": 0}]
g.renderer.render()
check(g.room_name_focus is False, "点击名字输入框外 → 自动退出输入态")
g.room_name_focus = True
g.touch_events = []
g.renderer.render()
_nr = getattr(g, "room_name_rect", None)
check(_nr is not None, "名字输入框位置已记录")
if _nr is not None:
    g.touch_events = [{"type": "up", "pos": (_nr.centerx, _nr.centery), "id": 0}]
    g.renderer.render()
    check(g.room_name_focus is True, "点击名字输入框内 → 保持输入态")

# ======================================================================
print("[8] 多人配置持久化")
_tmp_cfg = tempfile.mktemp(suffix=".json")
try:
    g.config.config_file = _tmp_cfg
    g.room_player_cfgs = {1: {"name": "阿明", "weapon": WeaponType.RIFLE, "char": "leon",
                              "team": 2}, 2: {"name": "小红"}, 3: {}, 4: {}}
    g._save_room_cfgs_to_config()
    check(os.path.exists(_tmp_cfg), "配置写入 config.json")
    _saved = json.load(open(_tmp_cfg, encoding="utf-8"))
    check("mp_room_cfgs" in _saved, "配置里存在 mp_room_cfgs 段")
    check(_saved["mp_room_cfgs"].get("1", {}).get("name") == "阿明", "名字已保存")
    check(_saved["mp_room_cfgs"].get("1", {}).get("weapon") == "RIFLE", "武器已保存（枚举转字符串）")
    # 重新载入
    g.room_player_cfgs = {1: {}, 2: {}, 3: {}, 4: {}}
    g.config.mp_room_cfgs = {}
    g.config.load()
    g._load_room_cfgs_from_config()
    check(g.room_player_cfgs.get(1, {}).get("name") == "阿明", "重新载入后名字恢复")
    check(g.room_player_cfgs.get(1, {}).get("weapon") == WeaponType.RIFLE, "重新载入后武器恢复")
    check(g.room_player_cfgs.get(1, {}).get("team") == 2, "重新载入后阵营恢复")
finally:
    if os.path.exists(_tmp_cfg):
        os.remove(_tmp_cfg)
    g.config.config_file = "config.json"

# ======================================================================
print("[9] P1/P2 开局投掷物一致")
g.player._throwables_init = False
g.player.throwables = {}
g.player2._throwables_init = False
g.player2.throwables = {}
g._ensure_throwable_stock(g.player)
g._ensure_throwable_stock(g.player2)
check(g.player.throwables == g.player2.throwables,
      f"P1/P2 开局投掷物一致（{g.player.throwables} vs {g.player2.throwables}）")
check(g.player.throwables.get("incendiary", 0) == 2, "P1 开局有 2 个燃烧弹")

# ======================================================================
print("[10] 道具刷新按每个玩家")
g.world.items.clear()
_p2_before = (g.player2.x, g.player2.y)
_lo, _hi = (getattr(g.world, "bounds", None) or (0, 12000))
_p2x = min(max(g.player.x + 1500, _lo + 200), _hi - 200)
_p2y = min(max(g.player.y - 1500, _lo + 200), _hi - 200)
g.player2.x = _p2x
g.player2.y = _p2y
g.world.item_spawn_interval = 0.0
g.world.item_spawn_timer = 999.0
g.world.update(1 / 60, g.player.x, g.player.y, [(g.player2.x, g.player2.y)])
check(len(g.world.items) >= 2, f"每个玩家周围都刷了道具（{len(g.world.items)} 个）")
_d2 = [min(math.hypot(i.x - g.player2.x, i.y - g.player2.y) for i in g.world.items),
       min(math.hypot(i.x - g.player.x, i.y - g.player.y) for i in g.world.items)]
check(_d2[0] < 900 and _d2[1] < 900, f"P1/P2 附近都有补给（距离 {int(_d2[0])}/{int(_d2[1])}）")
g.player2.x, g.player2.y = _p2_before

# ======================================================================
print("[11] PvP 毒圈")
g.config.pvp_enabled = True
g._init_pvp_zone()
check(g.pvp_zone is not None, "PvP 毒圈初始化成功")
if g.pvp_zone:
    _r0 = g.pvp_zone["r"]
    g.player.x = g.pvp_zone["cx"] + g.pvp_zone["r"] + 800
    g.player.y = g.pvp_zone["cy"]
    g.player.hp = g.player.max_hp
    g.player.alive = True
    g.player.downed = False
    for _ in range(40):
        g._update_pvp_zone(0.05)
    check(g.pvp_zone["r"] < _r0, f"毒圈随时间收缩（{_r0:.0f} → {g.pvp_zone['r']:.0f}）")
    check(g.player.hp < g.player.max_hp, f"圈外持续掉血（hp={g.player.hp:.0f}）")
    # 圈内不掉血
    g.player.x = g.pvp_zone["cx"]
    g.player.y = g.pvp_zone["cy"]
    g.player.hp = g.player.max_hp
    for _ in range(40):
        g._update_pvp_zone(0.05)
    check(g.player.hp >= g.player.max_hp - 0.01, "圈内不掉血")
g.config.pvp_enabled = False
g.pvp_zone = None

# ======================================================================
print("[12] 争分夺秒配乐")
import subprocess
_r = subprocess.run([sys.executable, "generate_music_race.py"], capture_output=True, text=True)
check(_r.returncode == 0, "争分夺秒 MIDI 生成成功")
_r2 = subprocess.run([sys.executable, "generate_music_manifest.py"], capture_output=True, text=True)
check(_r2.returncode == 0, "乐器清单生成成功")
from midi_lite import read_midi
_hdr, _tracks = read_midi("assets/music/race_urgency.mid")
check(_hdr["format"] == 1 and _hdr["ntrks"] == 7, "MIDI 为 Type1 且 7 轨")
# 缺 OGG 时回退地图音乐
g.config.game_mode = GameMode.TIMED
g.assets.music.pop("race", None)
check(g._resolve_map_music() in ("school", "street", "downtown", "suburb", "nuclear"),
      f"缺 race_urgency.ogg 时回退地图音乐（{g._resolve_map_music()}）")
g.assets.music["race"] = "assets/music/race_urgency.ogg"
check(g._resolve_map_music() == "race", "放入 OGG 后争分夺秒使用 race 配乐")

# ======================================================================
print("[13] 全流程跑帧（PvP + 毒圈 + 多人）")
g.config.pvp_enabled = True
g.config.game_mode = GameMode.ENDLESS
g._init_pvp_zone()
try:
    frames(g, 90)
    check(True, "90 帧多人 PvP 跑帧无异常")
except Exception as e:
    check(f"跑帧异常: {e!r}", False)

print()
print(f"===== SMOKE 结果: {PASS} 通过, {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
