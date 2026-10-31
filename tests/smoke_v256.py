#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.5.6 冒烟测试：真实跑帧压测本轮所有改动路径

在 dummy 视频驱动下真实启动游戏，逐条压测新代码路径不崩溃/行为正确：
1. 高速弹丸扫掠碰撞（AWM 单帧位移 100+ 仍能命中；旧落点判定会漏）
2. AWM/轨道炮 蓄力预瞄：按住（不发射、预瞄线跟随）→ 松开（开火一次、预瞄线消失）
3. 多人升级选卡：限时免伤 + 超时自动选卡 + 保护到期后重新被怪物锁定
4. PvPvE 探测：脉冲窗口（非常驻暴露）+ 冷却
5. 争分夺秒：倒计时结束 → 失败结算页（不是结局页）；每阵营 1 分钟
6. 故事结局抉择：6 选项布局不溢出 + 三种结局写入存档
7. 多人故事模式 HUD：双方倒计时 + 尸潮进度条渲染
8. 窗口缩放：0 尺寸 / 过小 / 非 16:9 / 放大，各自都能正常渲染
"""
import os
import sys
import math

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, _ROOT)

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game import Game, GameState
from config import (WeaponType, ControlMode, GameMode, EnemyType, SkillType)
from weapons import Weapon, Projectile
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
print("[1] 高速弹丸扫掠碰撞")
# AWM 速度 34/帧，低帧率 dt=0.05 → 单帧位移 102
p = Projectile(0, 0, 34, 0, 100, 2600, (255, 255, 255), 8)
p.update(0.05)   # 单帧位移 34*0.05*60 = 102px
hit_old = p.get_rect().colliderect(pygame.Rect(60, -10, 20, 20))
hit_new = p.swept_hit_rect(pygame.Rect(60, -10, 20, 20))
check(not hit_old and hit_new, "单帧位移 102px 时旧判定漏命中、新扫掠判定命中")
# 真实对局：AWM 对着僵尸打 60 帧，僵尸应掉血
g.config.control_mode = ControlMode.TOUCH
g.player.weapons = [Weapon(WeaponType.AWP)]
g.player.current_weapon_idx = 0
g.projectiles.clear()
tgt = Enemy(g.player.x + 260, g.player.y, EnemyType.ZOMBIE_NORMAL, 1, None)
tgt.hp = 5000
tgt.max_hp = 5000
tgt.alive = True
g.enemies.append(tgt)
hp0 = tgt.hp
g.aim_button.is_shooting = True
g.aim_button.angle = 0.0
frames(g, 3, draw=False)
check(len(g.projectiles) == 0, "AWM 按住时蓄力（未发射）")
g.aim_button.is_shooting = False
frames(g, 20, draw=False)
check(len(g.projectiles) >= 1, "AWM 松开发射")
check(tgt.hp < hp0, f"AWM 子弹命中远处僵尸（{hp0}→{tgt.hp}）")

print("[2] AWM/轨道炮 蓄力预瞄（按住预览 / 拖拽跟随 / 松开开火 / 预瞄线不卡死）")
g.config.control_mode = ControlMode.TOUCH
g.player.weapons = [Weapon(WeaponType.AWP)]
g.player.current_weapon_idx = 0
g.projectiles.clear()
g.aim_button.is_shooting = True
g.aim_button.angle = 0.0
frames(g, 2, draw=False)
check(g.player._awm_saved is not None, "按住 → 进入蓄力（预瞄角已记录）")
check(len(g.projectiles) == 0, "按住 → 不发射（未松开不发射）")
g.aim_button.angle = 0.9
frames(g, 2, draw=False)
check(abs(g.player._awm_saved - 0.9) < 1e-6, "拖拽 → 预瞄角实时跟随")
g.aim_button.is_shooting = False
frames(g, 2, draw=False)
check(len(g.projectiles) == 1, "松开 → 发射一发")
check(g.player._awm_saved is None, "松开 → 预瞄线立即消失（不卡死）")
# 轨道炮同样支持预瞄
g.player.weapons = [Weapon(WeaponType.RAILGUN)]
g.player.current_weapon_idx = 0
g.projectiles.clear()
g.aim_button.is_shooting = True
g.aim_button.angle = 0.2
frames(g, 2, draw=False)
check(g.player._awm_saved is not None and len(g.projectiles) == 0,
      "轨道炮：按住蓄力不发射")
g.aim_button.is_shooting = False
frames(g, 2, draw=False)
check(len(g.projectiles) == 1 and g.player._awm_saved is None,
      "轨道炮：松开开火且预瞄线消失")
g.config.control_mode = ControlMode.KEYBOARD

print("[3] 多人升级选卡（限时免伤 / 超时自动选卡 / 到期后重新被锁定）")
pl = g.player
pl.upgrade_paused = True
pl.upgrade_grace_timer = 0.0
hp = pl.hp
pl.take_damage(25, damage_type="melee")
check(pl.hp < hp, "保护期过后升级界面不再免疫伤害")
pl.upgrade_grace_timer = 2.0
hp = pl.hp
pl.take_damage(25, damage_type="melee")
check(pl.hp == hp, "保护期内短暂免伤")
pl.upgrade_grace_timer = 0.0
check(not g._player_is_protected(pl), "保护期外不再受保护（怪物会重新锁定）")
# 超时自动选卡
pl.skill_tree.skill_points = max(1, pl.skill_tree.skill_points)
pl.skill_cards = list(pl.skill_tree.get_random_skill_cards(3))
pl.pending_level_up = True
g._upgrade_pause_player = "P1"
g._upgrade_pause_timer = 0.05
frames(g, 12, draw=False)
check(g._upgrade_pause_player is None and not pl.upgrade_paused,
      "选卡超时 → 自动选卡（无法卡界面刷无敌）")
check(pl.pending_level_up is False, "自动选卡后待结算状态已清除")

print("[4] PvPvE 探测脉冲（非常驻暴露）")
g.config.pvp_enabled = True
from entities import Player as _P
g.player2 = _P(150, 0)
g.pvp_scan_active = 0
g.pvp_scan_cd = 0
check(g._trigger_pvp_scan(auto=False), "手动触发扫描脉冲")
check(g.pvp_scan_active > 0, "扫描窗口开启")
g.pvp_scan_active = 0
check(not g._trigger_pvp_scan(auto=False), "冷却期内无法再次扫描")
g.player2 = None
g.config.pvp_enabled = False

print("[5] 争分夺秒：倒计时结束=失败结算页 + 每阵营 1 分钟")
check(abs(g.TEAM_RACE_TIME - 60.0) < 1e-6, "每阵营 60 秒")
g.team_race = {}
g._team_race_inited = False
g.horde_manager = type(g.horde_manager)(GameMode.TIMED, "普通")
g._init_team_race()
check(all(abs(v["time"] - 60.0) < 1e-6 for v in g.team_race.values()),
      "阵营初始计时 60 秒")
g.team_race[0]["time"] = 5.0
g._team_race_add_time(0, 999)
check(abs(g.team_race[0]["time"] - 60.0) < 1e-6, "加时上限 60 秒")
g.state = GameState.PLAYING
g.config.game_mode = GameMode.TIMED
g.horde_manager.race_time_left = 0.0
g._settle_race_auto()
check(g.state == GameState.GAME_OVER, "倒计时结束 → 游戏结束页（不是结局页）")
check((getattr(g, "result_title", "") or "").find("失败") >= 0,
      f"结算标题为挑战失败：{getattr(g, 'result_title', None)}")
frames(g, 5)

print("[6] 故事结局抉择（6 选项 / 布局不溢出 / 结局入库）")
g.state = GameState.PLAYING
g.has_vaccine = True
g._final_dialogue()
_g = 0
while g.dialogue.active and _g < 20:
    g.dialogue.advance()
    _g += 1
check(len(g.dialogue.choices) >= 5, f"结局选项 {len(g.dialogue.choices)} 个")
_lay = g.dialogue.get_choice_layout(g.font, g.scaled_width, g.scaled_height)
check(len(_lay) == len(g.dialogue.choices), "每个选项都有布局矩形")
check(all(r.right <= g.scaled_width and r.bottom <= g.scaled_height
          for _i, r, _t in _lay), "选项全部落在屏幕内（不溢出）")
g._apply_choice_effect("save_all")
check(g.ending_type == "perfect", "三人全救 → perfect")
g._apply_choice_effect("save_wang")
check(g.ending_type == "save_wang", "救王某 → save_wang")
g._apply_choice_effect("save_friends")
check(g.ending_type == "save_friends", "救两个朋友 → save_friends")

print("[7] 多人故事模式 HUD（双方倒计时 + 尸潮进度条）")
g.config.game_mode = GameMode.STORY
g.map_config = {"chapter": "第一章", "name": "学校", "time_limit": 1200}
g.map_time_elapsed = 0.0
g.story_collected_fragments = set()
g.story_fragment_items = []
g.story_pending_fragments = []
g.special_event_triggered = False
g.special_event_active = False
g.survivor_npc = None
g.player2 = _P(150, 0)
g.multiplayer_mode = "same_screen"
g.key_u_held = False
g.key_u_press_start = 0
g.u_aim_started = False
g.key_u_long_threshold = 0.4
g.p2_selected_skill = None
g.p2_selected_throwable = "incendiary"
g.p2_fire_held = False
g.state = GameState.PLAYING
frames(g, 20)
check(True, "多人故事模式渲染 20 帧无异常（双方倒计时+尸潮进度条）")
g.player2 = None
g.multiplayer_mode = "single"
g.config.game_mode = GameMode.TIMED

print("[8] 窗口缩放（0 尺寸 / 过小 / 非 16:9 / 放大）")
for (w, h) in ((0, 0), (320, 200), (1000, 1000), (1920, 1080), (1280, 720)):
    g._apply_resize(w, h)
    g.update(1 / 60)
    g.renderer.render()
    check(g.scale > 0 and g.screen.get_width() > 0,
          f"缩放到 {w}x{h} 正常（实际 {g.screen.get_width()}x{g.screen.get_height()}）")
check(abs(g.content_w / g.content_h - 16 / 9) < 0.02, "内容区保持 16:9 比例")
# 摄像机视口同步：缩放后玩家仍居中
g.state = GameState.PLAYING
g.horde_manager.race_time_left = 60.0   # 争分夺秒倒计时恢复（前面用例清零了）
_b = getattr(getattr(g, "world", None), "bounds", None)
if _b:
    g.player.x = (_b[0] + _b[1]) / 2
    g.player.y = (_b[0] + _b[1]) / 2
g._apply_resize(1000, 1000)
for _ in range(150):
    g.update(1 / 60)
_px = (g.player.x - g.camera.x) * g.scale
_py = (g.player.y - g.camera.y) * g.scale
check(abs(_px - 500) < 60 and abs(_py - 500) < 80,
      f"非 16:9 窗口下玩家居中（{_px:.0f},{_py:.0f}）")

print(f"\n===== SMOKE 结果: {PASS} 通过, {FAIL} 失败 =====")
try:
    pygame.quit()
except Exception:
    pass
sys.exit(1 if FAIL else 0)
