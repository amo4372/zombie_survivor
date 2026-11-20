# -*- coding: utf-8 -*-
"""v2.9.21 联机专项：单设备 TCP 回环双端 + 五页跑帧 + 下拉点击。

重点验证本轮反馈：
  * 创建/加入分页、各自选装备（不复用同屏 EQUIP_SELECT）
  * 房主全阶段广播 phase，客户端从 wait→setup→playing 自动推进
  * 客户端进入 NET_CLIENT_PLAY 后确实有画面（非黑屏）
  * 下拉控件点击展开 / 选中生效，且同屏页难度键写的是中文真值
"""
import os, sys, time, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from config import GameState, ControlMode, GameMode
from zombie_pkg import Game

PASS = FAIL = 0
def check(ok, msg):
    global PASS, FAIL
    if ok: PASS += 1; print('  OK  ', msg)
    else: FAIL += 1; print('  FAIL', msg)

def frame(g, n=2):
    for _ in range(n):
        try:
            g.update(1/60); g.draw()
        except Exception as e:
            raise AssertionError('跑帧异常 %s: %s' % (g.state, e))

def te(g, typ, pos):
    g.touch_events = [{'type': typ, 'pos': (float(pos[0]), float(pos[1])), 'id': 7}]
    g.draw()
    g.touch_events = []

print('=== A. 协议与地址解析 ===')
from net import parse_host_port, PROTOCOL_VERSION, NetHost, NetClient
check(PROTOCOL_VERSION == 3, '协议版本 3（loadout/phase）')
check(parse_host_port('192.168.1.5:26000') == ('192.168.1.5', 26000), 'IPv4:端口 一次粘贴')
check(parse_host_port('[fd00::1]:26000') == ('fd00::1', 26000), 'IPv6 虚拟网卡地址')
check(parse_host_port('10.126.0.7') == ('10.126.0.7', 26000), '陶瓦/EasyTier 虚拟 IPv4')
check(parse_host_port('100.64.0.3:26000') == ('100.64.0.3', 26000), 'CGNAT 虚拟网段')

print('=== B. 五个新页面渲染 ===')
_g = Game()
_g.config.control_mode = ControlMode.TOUCH
for _st in (GameState.NET_LOBBY, GameState.NET_HOST_SETUP,
            GameState.NET_JOIN_SETUP, GameState.NET_SETUP,
            GameState.NET_RESULT):
    try:
        _g.state = _st
        _g._net_init_my_loadout()
        frame(_g, 2)
        check(True, '%s 渲染无异常' % _st.name)
    except Exception as e:
        check(False, '%s 渲染异常: %s' % (_st.name, e))

print('=== C. 同屏页下拉与难度真值 ===')
_g.state = GameState.MULTI_ROOM_CONFIG
_g.touch_events = []
frame(_g, 1)
# 难度行：lx=70,rh=46,y 依次 130/188/246/304/362；难度在第 4 行 y=304
_s = _g.scale
_r = pygame.Rect(int(70*_s), int(304*_s), int(300*_s), int(46*_s))
te(_g, 'up', _r.center)
check(getattr(_g, 'room_dropdown', None) == 'diff', '同屏页下拉点击可展开')
frame(_g, 1)
# 选「地狱」（第 4 个选项）
_ih = int(42*_s) + int(3*_s)
_opt = pygame.Rect(int(70*_s), int(304*_s) + int(46*_s) + 3*_ih,
                   int(300*_s), int(42*_s))
te(_g, 'up', _opt.center)
check(str(_g.config.difficulty) == '地狱', '难度写的是中文真值（与 difficulty 表一致）')

print('=== D. 创建/加入分页入口 ===')
_g.state = GameState.NET_LOBBY
_g.touch_events = []
frame(_g, 1)
te(_g, 'up', (int(355*_s), int(300*_s)))       # 创建卡片
check(_g.state == GameState.NET_HOST_SETUP, '入口「创建房间」切到独立创建页')
_g.state = GameState.NET_LOBBY
te(_g, 'up', (int(925*_s), int(300*_s)))       # 加入卡片
check(_g.state == GameState.NET_JOIN_SETUP, '入口「加入房间」切到独立加入页')
check(GameState.NET_HOST_SETUP != GameState.NET_JOIN_SETUP, '创建页与加入页是两个独立状态')

print('=== E. 双端 TCP 回环：房主权威全流程 ===')
_port = 26137
_h = Game(); _h.config.control_mode = ControlMode.TOUCH
_h.net_room_name = '测试房间'; _h.net_nickname = '房主'
_h.net_port_input = str(_port)
_h.net_ip_input = ''
_h.state = GameState.NET_HOST_SETUP
_h._net_start_host()
check(_h.net_host is not None and _h.state == GameState.NET_WAIT,
      '房主创建房间成功并进入等待页')
check(bool(getattr(_h, 'net_started', False)) and getattr(_h, 'net_phase', '') == 'wait',
      '房主等待阶段即开启 phase 广播')

_c = Game(); _c.config.control_mode = ControlMode.TOUCH
_c.net_nickname = '客户端B'
_c.net_ip_input = '127.0.0.1'
_c.net_port_input = str(_port)
_c.state = GameState.NET_JOIN_SETUP
_c._net_join()
check(_c.net_client is not None and _c.net_client.connected, 'B 客户端连上房主')
check(_c.state == GameState.NET_WAIT, '客户端进入等待页')
time.sleep(0.25)
frame(_h, 2); frame(_c, 2)
check(_h.net_host.connected and _h.net_host.client_count == 1, '房主看到 1 个客户端')
check(_c.net_client.player_index == 1, '客户端分配到 P2 索引')

# 房主进入装备选择 → 广播 phase=setup
_h._net_host_start_game()
check(_h.state == GameState.NET_SETUP, '房主进的是 NET_SETUP（不再是 EQUIP_SELECT）')
frame(_h, 2)
time.sleep(0.2)
_c._net_client_sync_phase()
check(_c.state == GameState.NET_SETUP, '客户端被 phase=setup 推进到自己的装备页')
check(_c.net_role == 'client' and _h.net_role == 'host', '两端角色互不混淆')

# 各自独立选择
from config import WeaponType, CHARACTERS
_wl = _h.net_weapon_list; _cl = _h.net_char_list
check(len(_wl) >= 20 and len(_cl) >= 1, '装备页有武器与角色候选')
_h._net_setup_pick_weapon(min(3, len(_wl)-1))
_h._net_setup_confirm()
_c._net_setup_pick_weapon(min(7, len(_wl)-1))
_c._net_setup_pick_char(min(1, len(_cl)-1))
_c._net_setup_confirm()
time.sleep(0.2)
frame(_h, 2)
_los = _h.net_host.get_loadouts()
check(1 in _los and bool(_los[1].get('weapon')) and bool(_h.net_host.ready.get(1)),
      '房主收到 B 客户端独立上报的 loadout 与 ready')
check(_los[1]['weapon'] != (_h.net_host_loadout or {}).get('weapon'),
      '两人武器选择互不复用（各自独立）')
check(_h.net_host.all_ready(), '全部玩家已准备')

# 房主开局 → phase=playing 广播
_ok = _h._net_host_launch()
check(_ok, '房主点开始游戏成功')
check(_h.state == GameState.PLAYING, '房主进入 PLAYING')
frame(_h, 3)
time.sleep(0.2)
_c._net_client_sync_phase()
check(_c.state == GameState.NET_CLIENT_PLAY,
      '**客户端自动进入 NET_CLIENT_PLAY（修复 P2 无画面）**')
_snap = _c.net_client.get_snapshot() or {}
check(bool(_snap.get('players')) and _snap.get('phase') == 'playing',
      '客户端收到含玩家的世界快照')
try:
    frame(_c, 3)
    _px = pygame.surfarray.array3d(_c.screen)
    _nonblack = int((_px.sum(axis=2) > 90).sum())
    check(_nonblack > 5000, '客户端画面非黑屏（渲染像素 %d）' % _nonblack)
except Exception as e:
    check(False, '客户端渲染异常: %s' % e)
check(_c.player_index if hasattr(_c, 'player_index') else
      getattr(_c.net_client, 'player_index', 1) == 1, '客户端索引正确')

print('=== F. 结算同步 ===')
_h.state = GameState.GAME_OVER
_h.wave_count = 7
frame(_h, 2)
time.sleep(0.2)
_c._net_client_sync_phase()
check(_c.state == GameState.NET_RESULT, '房主结束对局后客户端被推进到结算页')
try:
    frame(_c, 2)
    check(True, '结算页渲染无异常')
except Exception as e:
    check(False, '结算页渲染异常: %s' % e)

print('=== G. 各自装备页 / 创建页下拉点击 ===')
_h.state = GameState.NET_SETUP
_h._net_init_my_loadout()
te(_h, 'up', (int(300*_h.scale), int(207*_h.scale)))   # 武器列表第二行
check(_h.net_my_weapon is not None, '装备页点武器行生效且未崩')
_c.state = GameState.NET_SETUP
frame(_c, 2)
check(True, '客户端装备页渲染无异常')

_h.state = GameState.NET_HOST_SETUP
_h.touch_events = []
setattr(_h, 'net_dd_key', None)      # 模拟「刚进入页面」的干净状态
_h._dd_overlay_rects = []
frame(_h, 1)
_rr = pygame.Rect(int(40*_h.scale), int(168*_h.scale),
                  int(580*_h.scale), int(42*_h.scale))
te(_h, 'up', _rr.center)
check(getattr(_h, 'net_dd_key', None) == 'net_cnt',
      '创建页下拉（复用同屏双人 DropdownGroup）点击可展开')
frame(_h, 1)

try:
    _h._net_stop(); _c._net_stop()
except Exception:
    pass

print('\n===== v2.9.21 联机专项: PASS=%d FAIL=%d =====' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
