#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.9.17 综合测试：复制/钩爪/视野/回放/贴图/冰霜/玩家AI/全模式跑帧"""
import os, sys, math, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "_vendor")); sys.path.insert(0, ROOT); os.chdir(ROOT)
PASS = FAIL = 0
def check(c, l):
    global PASS, FAIL
    if c: PASS += 1; print("  OK   " + l)
    else: FAIL += 1; print("  FAIL " + l)
def src(p): return open(p, encoding="utf-8").read()

import pygame
pygame.init(); _S = pygame.display.set_mode((1280, 720))
_F = pygame.font.Font(None, 18)
from config import GameState, ControlMode, GameMode

print("[A] 复制：无 pygame.scrap 时静默降级")
from renderer_pkg.draw_ui import _zs_copy_text
_buf = io.StringIO()
with contextlib.redirect_stderr(_buf):
    _ok = _zs_copy_text("192.168.1.5:26000")
check(_ok is True, "复制返回成功（降级到文件/外部命令）")
check("RuntimeWarning" not in _buf.getvalue(), "不再产生 RuntimeWarning")
check(os.path.exists("clipboard.txt") or _ok, "降级产物存在")

print("[B] 钩爪：锁定圈重置 / 倒地队友 / P2 自动锁定")
from zombie_pkg import Game
from entities_pkg.gear import RiotGear
_g = Game(); _rg = RiotGear()
_rg._grapple_aim_prev = True; _rg._grapple_aim_start = 1.0; _rg._grapple_aim_charge = 1.0
_rg._reset_grapple()
check(_rg._grapple_aim_prev is False and _rg._grapple_aim_start is None
      and _rg._grapple_aim_charge == 0.0, "发射后锁定圈蓄力计时完整重置")
# 倒地队友（alive=False, downed=True）
class _O:
    def __init__(s, x, y, alive=True, downed=False, boss=False):
        s.x, s.y, s.alive, s.downed, s.is_boss = x, y, alive, downed, boss
_down = _O(300, 300, alive=False, downed=True)
_rg2 = RiotGear(); _rg2.grapple_aiming = True
_rg2.update_grapple_lock(0, 0, [], items=None, aim_angle=0, aim_dist=300,
                         players_down=[_down], players_enemy=None, players_teammate=None)
check(_rg2.grapple_locked_target is _down, "倒地队友可被锁定圈自动锁定")
# P2 释放帧不清锁定目标
check("not self._p2_casting_this_frame()" in src("zombie_pkg/mix_multi.py"),
      "P2 释放帧保护锁定目标")
_gm = Game(); _gm.multiplayer_mode = "same_screen"; _gm.config.control_mode = ControlMode.TOUCH
_gm.config.game_mode = GameMode.ENDLESS; _gm.start_game(); _gm.state = GameState.PLAYING
_p2 = _gm.player2
if _p2:
    _p2.riot_gear.grapple_locked_target = _O(1, 1)
    _gm._p2_skill_pending = True
    _gm._update_p2_grapple_lock(_p2, False)
    check(_p2.riot_gear.grapple_locked_target is not None, "P2 释放帧锁定目标保留")

print("[C] 视野：v2.9.18 起恢复 zoom 拉远（镜头位移方案已废弃）")
check(hasattr(_gm.camera, 'zoom'), "Camera 有 zoom")
check("cam.zoom = _cur + (_target - _cur) * _k" in src("zombie_pkg/mix_players.py"),
      "update_dynamic_zoom 用 zoom 拉远")
check("scale = _ui_scale" in src("renderer_pkg/draw_play.py"),
      "HUD 层恢复原始缩放（拉远时按钮不缩小）")
_gm.player._awm_saved = 90.0
_gm.player._charge_active = True
_gm.player._charge_ratio = 1.0
try:
    _w = _gm.player.get_current_weapon()
    if _w is not None:
        _w.hold_charge = True
        _w.range = 1400
except Exception:
    pass
_gm.update_dynamic_zoom(0.5)
check(float(_gm.camera.zoom) < 0.99, "长按瞄准时 zoom 拉远")
try:
    _gm.renderer._draw_playing_core(_gm.player, _gm.camera)
    check(True, "zoom 拉远后世界+HUD 绘制无异常")
except Exception as ex:
    check(False, "绘制异常 %r" % ex)

print("[D] 回放：可保存 + 帧画面数据 + 加载")
import replay as _rp, time
_r = _rp.ReplayRecorder()
_r.start({"mode": "test"})
_pl = [_O(10, 20), _O(30, 40)]
_en = [_O(100, 100)]
_r.tick(0.1, _pl, _en, extra={"bullets": [[1, 2, 3, 4, [255, 200, 100], 4, 0, 0, 0]],
                               "zones": [[50, 50, 90, "frost_zones"]], "fx": []})
_r.tick(0.1, _pl, _en, extra={"bullets": [], "zones": [], "fx": []})
_r.add_event("skill", "测试技能")
_p = "replays/_test_v2917.zsr"; _r.save(_p)
_d = _rp.load_replay(_p)
check(len(_d.frames) == 2, "回放帧数正确")
check(bool(getattr(_d.frames[0], 'extra', {})), "帧含画面增强数据")
_g2 = Game(); _g2.replay_data = _d
_ok = _g2.save_current_replay(name="v2917_test")
check(_ok is True, "回放页「保存」可用")
check(any(f.startswith("v2917_test") for f in os.listdir("replays/saved")), "已存进回放列表目录")
try:
    _g2.state = GameState.REPLAY
    _g2.replay_playing = True
    _g2.replay_show_data = False
    _g2.replay_follow = False
    _g2.replay_touch_btns = {}
    _g2.replay_cam = _rp.FreeCamera()
    _g2.replay_cam.x = 0; _g2.replay_cam.y = 0
    _g2.renderer._draw_replay()
    check(True, "回放画面（含子弹/区域/特效）渲染无异常")
except Exception as ex:
    check(False, "回放渲染异常 %r" % ex)

print("[E] 程序化僵尸贴图 + 冰霜冷罐")
# v2.9.18：贴图改为按项目原画风生成并注册到 assets（不再用独立子目录）
_keys = ["zombie_hunter", "zombie_bomber", "zombie_frost", "zombie_venom",
         "zombie_berserker", "zombie_ghoul", "zombie_shaman", "zombie_juggernaut"]
check(all(os.path.exists(os.path.join(ROOT, "assets", "images", k + ".png"))
          for k in _keys), "8 张同画风程序化贴图已生成")
check('"zombie_frost":' in src("assets.py"), "敌人绘制走 assets 原生贴图分支")
check('"新增"' not in src("codex.py"), "图鉴「新增」类别已并入既有类别")
_g3 = Game(); _g3.config.game_mode = GameMode.ENDLESS; _g3.start_game(); _g3.state = GameState.PLAYING
class _Frost:
    enemy_type = type("E", (), {"name": "ZOMBIE_FROST"})()
    alive = True; is_boss = False; x = 100; y = 100; id = 7
_g3.enemies.append(_Frost())
_g3._update_frost_throwers(0.016)
check(len(getattr(_g3, 'frost_zones', [])) >= 1, "冰霜僵尸投掷冷罐生成冰冻区")
_z0 = _g3.frost_zones[0]
_g3.player.x, _g3.player.y = _z0["x"], _z0["y"]
_g3._update_frost_zones(0.016)
check(float(getattr(_g3.player, 'frozen_timer', 0)) > 0, "区域内玩家被冻结")

print("[F] 玩家 AI：创建 / 配置 / 战斗 / 升级 / 渲染")
from ai_pkg.player_bots import BotManager, BotDifficulty, BotTactic, BotProfile
check(len(Game.PLAYER_ATTRS) == 10, "玩家注册表扩展到 P1..P10")
_g4 = Game(); _g4.config.game_mode = GameMode.ENDLESS
_g4.config.control_mode = ControlMode.TOUCH
_g4.start_game(); _g4.state = GameState.PLAYING
_bm = _g4._bots()
check(_bm is not None, "BotManager 可获取")
for _i, _p in enumerate(_bm.profiles[:9]):
    _p.enabled = True
    _p.difficulty = BotDifficulty.NIGHTMARE if _i == 0 else BotDifficulty.NORMAL
    _p.tactic = BotTactic.AGGRESSIVE
    _p.hostile = (_i % 2 == 0)
    _p.team = 1 if _p.hostile else 0
_g4.setup_bots(1)
check(len(_bm.bots) == 9, "成功创建 9 个 AI 玩家")
check(len(list(_g4.registered_players())) == 10, "世界内共 10 个玩家")
check(_g4.human_player_count == 1, "1 个人类玩家")
for _f in range(25):
    _g4.update(1/60)
check(True, "含 9 个 AI 连跑 25 帧无异常")
# 单机渲染判定（AI 不应触发分屏）
check("_humans >= 2" in src("renderer_pkg/draw_play.py"), "仅人类≥2 才分屏")
# 配置页渲染
_g4.state = GameState.BOT_CONFIG
try:
    _g4.renderer.render(); check(True, "AI 配置页渲染无异常")
except Exception as ex:
    check(False, "AI 配置页渲染异常 %r" % ex)
# 难度循环
check(BotDifficulty.cycle(BotDifficulty.EASY) is BotDifficulty.NORMAL, "难度循环切换")
check(BotDifficulty.NIGHTMARE.params[4] and BotDifficulty.NIGHTMARE.params[5], "超难含透视与强锁")
# 自动升级不卡住
_b = _bm.bots[0]
_b.player.upgrade_paused = True; _b.player.pending_level_up = True
_bm.auto_upgrade()
check(not bool(_b.player.upgrade_paused), "AI 自动选卡不会卡住整局")

print("[G] 全模式跑帧")
for _m in ("STORY", "ENDLESS", "TIMED"):
    try:
        _gg = Game(); _gg.config.game_mode = getattr(GameMode, _m, None)
        _gg.config.control_mode = ControlMode.TOUCH
        _gg.start_game(); _gg.state = GameState.PLAYING
        for _i in range(30): _gg.update(1/60); _gg.draw()
        check(True, "%s 30 帧无异常" % _m)
    except Exception as ex:
        check(False, "%s 跑帧异常 %r" % (_m, ex))
try:
    _gg = Game(); _gg.multiplayer_mode = "same_screen"
    _gg.config.game_mode = GameMode.ENDLESS; _gg.config.control_mode = ControlMode.TOUCH
    _gg.start_game(); _gg.state = GameState.PLAYING
    for _i in range(30): _gg.update(1/60); _gg.draw()
    check(True, "同屏双人 30 帧无异常")
except Exception as ex:
    check(False, "双人跑帧异常 %r" % ex)
try:
    _gg = Game(); _gg.state = GameState.NET_MULTIPLAYER
    _gg.touch_events = []
    _gg.renderer.render()
    check(True, "网络联机页渲染无异常")
except Exception as ex:
    check(False, "网络页异常 %r" % ex)

print("\n===== v2.9.17 测试: PASS=%d FAIL=%d =====" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
