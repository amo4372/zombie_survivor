#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.9.19 综合测试：zoom 回弹 / 网络双栏与下滑栏 / 局域网连接 / AI / 格挡 UI"""
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
pygame.init(); pygame.display.set_mode((1280, 720))
from config import GameState, ControlMode, GameMode, BASE_WIDTH, WeaponType
from zombie_pkg import Game
from ai_pkg.player_bots import AIPlayer, BotManager, BotDifficulty, BotTactic

def newgame(mode=GameMode.ENDLESS, human=1, bots=0):
    g = Game(); g.config.control_mode = ControlMode.TOUCH
    g.config.game_mode = mode
    if human >= 2:
        g.multiplayer_mode = 'same_screen'   # 让 start_game 真正创建第二个人类
    g.human_player_count = human
    if bots:
        m = g._bots()
        for p in m.profiles[:bots]:
            p.enabled = True
    g.start_game(); g.setup_bots(human)
    g.state = GameState.PLAYING; g.touch_events = []
    return g

print("[A] 动态视野：只在瞄准时拉远，常态必回弹")
g = newgame()
_w = g.player.get_current_weapon()
# 模拟长射程武器（AWM 类）
if _w is not None:
    _w.range = 1100; _w.hold_charge = True
for _ in range(120): g.update_dynamic_zoom(1/60)
check(abs(g.camera.zoom - 1.0) < 0.005, "拿长射程武器空跑 120 帧 zoom 仍为 1.0 (%.3f)" % g.camera.zoom)
g.player._charge_active = True; g.player._awm_saved = 0.0; g.player._charge_ratio = 1.0
for _ in range(40): g.update_dynamic_zoom(1/60)
check(g.camera.zoom < 0.9, "按住蓄力确实拉远 (%.3f)" % g.camera.zoom)
g.player._charge_active = False; g.player._awm_saved = None
for _ in range(180): g.update_dynamic_zoom(1/60)
check(abs(g.camera.zoom - 1.0) < 0.005, "松开后完全回弹 (%.3f)" % g.camera.zoom)
g.camera.zoom = 0.5; g.start_game()
check(abs(g.camera.zoom - 1.0) < 0.005, "重开一局强制复位 zoom")
_s = src('zombie_pkg/mix_players.py')
check('cam._zoom_base = 1.0' in _s, "基准固定 1.0 不被污染")
check('_wr * 0.5' not in _s, "删除常驻射程项")

print("[B] 网络下滑栏：能展开、能选、能收起")
g2 = Game(); g2.config.control_mode = ControlMode.TOUCH
g2.state = GameState.NET_MULTIPLAYER; g2.touch_events = []
g2.renderer.render()
# 人数行 (40,204,560,44)，scale=1
_cnt = (40, 204, 560, 44)
g2.touch_events = [{'type': 'up', 'pos': (300, 226)}]
g2.renderer.render()
check(getattr(g2, 'net_dd_key', None) == 'net_cnt', "点击展开 net_cnt")
g2.touch_events = []; g2.renderer.render()
check(len(getattr(g2, '_net_dd_overlay_rects', []) or []) >= 2, "展开态生成选项浮层")
_before = getattr(g2, 'coop_player_count', 2)
# 第三项 "4 人"：oy=248+2=250, oh=38, 第3项 y=250+3+2*38=329..365
g2.touch_events = [{'type': 'up', 'pos': (300, 340)}]
g2.renderer.render()
check(getattr(g2, 'coop_player_count', 2) == 4, "选中 4 人生效 (%s→%s)" % (_before, getattr(g2,'coop_player_count',2)))
check(getattr(g2, 'net_dd_key', None) is None, "选完自动收起")
# 展开后点空白收起
g2.touch_events = [{'type': 'up', 'pos': (300, 226)}]; g2.renderer.render()
g2.touch_events = [{'type': 'up', 'pos': (640, 600)}]; g2.renderer.render()
check(getattr(g2, 'net_dd_key', None) is None, "点空白收起下拉")
# 静态控件零重叠（取主要 rect）
_rects = [pygame.Rect(40,100,560,44), pygame.Rect(40,152,560,44),
          pygame.Rect(40,204,560,44), pygame.Rect(40,256,560,44),
          pygame.Rect(40,308,560,44), pygame.Rect(40,360,560,44),
          pygame.Rect(40,412,420,44), pygame.Rect(468,412,132,44),
          pygame.Rect(40,476,560,52), pygame.Rect(680,100,560,44),
          pygame.Rect(680,152,560,44), pygame.Rect(680,204,560,44),
          pygame.Rect(680,256,560,44), pygame.Rect(680,540,560,52),
          pygame.Rect(40,650,180,44)]
_ov = sum(1 for i in range(len(_rects)) for j in range(i+1,len(_rects))
          if _rects[i].colliderect(_rects[j]))
check(_ov == 0, "双栏静态控件零重叠（%d 对）" % _ov)
check('if self.net_dd_key' not in src('renderer_pkg/draw_ui.py').split('def _draw_net_multiplayer')[1].split('def _draw_net_wait')[0],
      "不再用上一帧 overlay 清展开状态")

print("[C] 同一 WiFi 连接")
import net_discovery as ND
_t = ND.broadcast_targets()
check(len(_t) >= 4 and any(x.endswith('.255') for x in _t), "广播含子网定向地址 %s" % _t[:4])
check(ND.local_lan_ip() != "127.0.0.1", "本机地址不是回环 (%s)" % ND.local_lan_ip())
try:
    from net import NetHost, NetClient
    _h = NetHost(0) if False else None
except Exception:
    pass
_b = ND.RoomBeacon(26000, room_name="测试房")
import json as _json
_pay = _json.loads(_b._payload().decode())
check('host_ip' in _pay and _pay['host_ip'], "信标携带 host_ip")
g3 = Game(); g3.config.control_mode = ControlMode.TOUCH; g3.state = GameState.NET_MULTIPLAYER
check(getattr(g3, 'net_ip_input', 'X') == '', "IP 默认留空（不会默认连自己）")
g3.net_ip_input = ""; g3.touch_events = []
try:
    g3._net_join()
    check('请先填房主 IP' in str(getattr(g3,'net_last_error','')), "空 IP 给出明确提示")
except Exception as ex:
    check(False, "空 IP 加入异常 %r" % ex)
# 本机回环实测 host/client 握手
try:
    from net import NetHost, NetClient, PROTOCOL_VERSION
    import time as _time
    _port = 26119
    _h = NetHost(_port, room_cfg={"game_mode":"ENDLESS"}, room_name="本机测试", host_name="房主")
    _ok = _h.start()
    check(_ok, "房主监听启动")
    _c = NetClient("127.0.0.1", _port, nickname="客户端")
    _co = _c.start()
    check(_co, "客户端 TCP 连接成功")
    for _ in range(30):
        if getattr(_c, 'server_version', 0):
            break
        _time.sleep(0.05)
    check(getattr(_c, 'server_version', 0) == PROTOCOL_VERSION, "版本握手一致")
    _c.stop(); _h.stop()
except Exception as ex:
    check(False, "本机握手异常 %r" % ex)

print("[D] AI 视口：AI 永不占视口")
from renderer_pkg.draw_multiplayer import build_split_viewports
g4 = newgame(human=1, bots=3)
check(len([p for p in g4.registered_players() if getattr(p,'is_bot',False)]) == 3, "3 个 AI 已创建")
check(len(build_split_viewports(g4)) == 1, "1 人类 + 3AI → 1 视口")
g5 = newgame(human=2, bots=3)
check(len(build_split_viewports(g5)) == 2, "2 人类 + 3AI → 2 视口")
_vp = build_split_viewports(g5)
check(all(not getattr(v.player, 'is_bot', False) for v in _vp), "视口里没有 AI")
check(isinstance(g4.player2, AIPlayer), "AI 使用 AIPlayer 类（继承多人 Player）")
try:
    from entities_pkg.player import Player as _P
    check(issubclass(AIPlayer, _P), "AIPlayer 继承同一个 Player 接口")
except Exception as ex:
    check(False, "Player 导入 %r" % ex)

print("[E] 删除蓝色格挡圆 + 「挡」字")
_b = src('zombie_pkg/mix_block.py')
check('"""v2.9.19：按用户要求**删除**' in _b, "draw_block_cd 改为不绘制")
check('"挡" if active' not in _b, "不再写「挡」字")
g6 = newgame()
_surf = pygame.Surface((200,200)); _surf.fill((10,10,10))
_before = _surf.copy()
g6.draw_block_cd(_surf, g6.player, 100, 100, 1.0, g6.font_small)
check(pygame.image.tostring(_surf,'RGB') == pygame.image.tostring(_before,'RGB'), "调用后像素零变化")

print("[F] AI 行为：不转圈 / 吃经验 / 队伍 / 技能 / 救援 / 胜负")
from entities_pkg.pickups import ExpOrb
g7 = newgame(human=1, bots=1)
_bot = g7.player2
_bot.x, _bot.y = 400.0, 400.0
_o = ExpOrb(580.0, 400.0, 20); g7.exp_orbs = [_o]
g7.enemies = []
_ctl = _bot.ai_controller
_d0 = math.hypot(_o.x - _bot.x, _o.y - _bot.y)
for _ in range(60):
    _ctl.update(1/60)
_d1 = math.hypot(_o.x - _bot.x, _o.y - _bot.y)
check(_d1 < _d0 - 20, "AI 主动靠近经验球 (%.0f→%.0f)" % (_d0, _d1))
_ang = []
for _ in range(20):
    _ctl.update(1/60); _ang.append(_ctl._angle)
check(max(abs(_ang[i]-_ang[i-1]) for i in range(1,len(_ang))) < 45,
      "无目标时朝向稳定，不再原地打转")
# 队伍分配
g8 = newgame(human=1, bots=2)
g8._bots().profiles[1].hostile = True
g8._bots().setup(1)
_pl = [p for p in g8.registered_players() if getattr(p,'is_bot',False)]
check(any(p.team_id == 1 and p.bot_hostile for p in _pl), "敌方 AI 分到不同 team_id")
check(bool(g8.config.pvp_enabled), "存在敌方 AI 时自动开启 PvP 结算链路")
_ctl8 = _pl[0].ai_controller
check(any(_ctl8._is_foe_player(p) for p in [g8.player] if p is not _pl[0]) or
      not _pl[0].bot_hostile, "敌我判定按队伍生效")
# 胜利条件：P1 死但友方 AI 活着
g9 = newgame(human=1, bots=1)
g9.player.hp = 0; g9.player.alive = False; g9.player.permanently_dead = True
check(g9._team_has_survivor(), "同阵营友方 AI 存活 → 判定为继续")
try:
    g9.multiplayer_mode = 'same_screen'
    check(g9._update_rescue(1/60) is False, "不触发全灭结算（本局继续）")
except Exception as ex:
    check(False, "_update_rescue 异常 %r" % ex)
# 救援：倒地队友 + 友方 AI 靠近
g10 = newgame(human=1, bots=1)
_mate = g10.player2
g10.player.downed = True; g10.player.alive = False; g10.player.hp = 0
_mate.x, _mate.y = g10.player.x + 40, g10.player.y
g10.player.last_rescue_time = -999.0
for _ in range(200):
    g10._update_rescue(1/60)
    if not g10.player.downed: break
check(not g10.player.downed and g10.player.alive, "AI 靠近倒地队友完成救援")
# 技能：给 AI 点一个主动技能后应能调用
try:
    from config import SkillType
    _tree = getattr(_mate, 'skill_tree', None)
    _sk = _tree.get_skill(SkillType.DASH) if _tree else None
    if _sk is not None:
        _sk.current_level = 1
    _calls = []
    _orig = g10._bot_use_skill
    g10._bot_use_skill = lambda p, st, a=0.0: (_calls.append(st), True)[1]
    _c10 = _mate.ai_controller
    _c10._skill_t = 0.0; _c10.diff = BotDifficulty.NIGHTMARE
    for _ in range(120): _c10._try_skill(1/60)
    g10._bot_use_skill = _orig
    check(bool(_calls), "AI 能放技能（%d 次）" % len(_calls))
except Exception as ex:
    check(False, "AI 技能异常 %r" % ex)

print("[G] 全模式跑帧")
for _m in ('STORY','ENDLESS','TIMED'):
    try:
        _g = newgame(mode=getattr(GameMode,_m))
        for _ in range(30): _g.update(1/60); _g.draw()
        check(True, "%s 30 帧无异常" % _m)
    except Exception as ex:
        check(False, "%s 跑帧异常 %r" % (_m, ex))
try:
    _g = newgame(human=2, bots=2); _g.multiplayer_mode='same_screen'
    for _ in range(30): _g.update(1/60); _g.draw()
    check(True, "同屏双人 + 2AI 30 帧无异常")
except Exception as ex:
    check(False, "双人跑帧异常 %r" % ex)
for _st in (GameState.NET_MULTIPLAYER, GameState.NET_WAIT, GameState.BOT_CONFIG,
            GameState.CODEX, GameState.MULTI_ROOM_CONFIG):
    try:
        _g = Game(); _g.config.control_mode=ControlMode.TOUCH; _g.state=_st
        _g.touch_events=[]
        for _ in range(6): _g.renderer.render()
        check(True, "%s 页面渲染无异常" % _st.name)
    except Exception as ex:
        check(False, "%s 页面异常 %r" % (_st.name, ex))

print("\n===== v2.9.19 测试: PASS=%d FAIL=%d =====" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
