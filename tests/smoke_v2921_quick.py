# -*- coding: utf-8 -*-
"""v2.9.21 精简回归（日常迭代用，目标 < 20s）。

与 smoke_v2921_net.py / smoke_v2921_misc.py 断言口径一致，但：
  * 复用 Game 实例（资源缓存命中后第二个实例几乎零成本）
  * 用 20ms 轮询替代固定 sleep(0.2~0.25)
  * 页面/跑帧次数压到 1 帧，断言一条不删
完整版仍保留：python tests/smoke_v2921_net.py && python tests/smoke_v2921_misc.py
"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import pygame
pygame.init(); pygame.display.set_mode((1280, 720))
from config import GameState, ControlMode, GameMode
from zombie_pkg import Game

PASS = FAIL = 0
def check(ok, msg):
    global PASS, FAIL
    if ok: PASS += 1; print('  OK  ', msg)
    else: FAIL += 1; print('  FAIL', msg)

def frame(g, n=1):
    for _ in range(n):
        try: g.update(1/60); g.draw()
        except Exception as e: raise AssertionError('跑帧异常 %s: %s' % (g.state, e))

def te(g, pos):
    g.touch_events = [{'type': 'up', 'pos': (float(pos[0]), float(pos[1])), 'id': 7}]
    g.draw(); g.touch_events = []

def until(pred, timeout=0.8):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if pred(): return True
        time.sleep(0.02)
    return False

print('=== A. 协议 / 地址解析 ===')
from net import parse_host_port, PROTOCOL_VERSION
check(PROTOCOL_VERSION == 3, '协议版本 3（loadout/phase）')
for _txt, _want in (('192.168.1.5:26000', ('192.168.1.5', 26000)),
                    ('[fd00::1]:26000', ('fd00::1', 26000)),
                    ('10.126.0.7', ('10.126.0.7', 26000)),
                    ('100.64.0.3:26000', ('100.64.0.3', 26000))):
    check(parse_host_port(_txt) == _want, '解析 %s' % _txt)

print('=== B. 分页 / 各自装备 / 双端同步 ===')
h = Game(); h.config.control_mode = ControlMode.TOUCH
for _st in (GameState.NET_LOBBY, GameState.NET_HOST_SETUP,
            GameState.NET_JOIN_SETUP, GameState.NET_SETUP, GameState.NET_RESULT):
    try:
        h.state = _st; h._net_init_my_loadout(); frame(h)
        check(True, '%s 渲染' % _st.name)
    except Exception as e:
        check(False, '%s 渲染异常: %s' % (_st.name, e))

_s = h.scale
h.state = GameState.MULTI_ROOM_CONFIG; frame(h)
te(h, (int(220*_s), int(327*_s)))
check(getattr(h, 'room_dropdown', None) == 'diff', '同屏页下拉可展开')
frame(h)
_opt = pygame.Rect(int(70*_s), int(304*_s) + int(46*_s) + 3*(int(42*_s)+int(3*_s)),
                   int(300*_s), int(42*_s))
te(h, _opt.center)
check(str(h.config.difficulty) == '地狱', '难度写中文真值（显示与实际一致）')

h.state = GameState.NET_LOBBY; frame(h)
te(h, (int(355*_s), int(300*_s)))
check(h.state == GameState.NET_HOST_SETUP, '创建房间独立页')
h.state = GameState.NET_LOBBY; te(h, (int(925*_s), int(300*_s)))
check(h.state == GameState.NET_JOIN_SETUP, '加入房间独立页')

_port = 26138
h.net_room_name = '测试房间'; h.net_nickname = '房主'
h.net_port_input = str(_port); h.net_ip_input = ''
h.state = GameState.NET_HOST_SETUP
h._net_start_host()
check(h.net_host is not None and h.state == GameState.NET_WAIT, '房主创建成功')
check(bool(getattr(h, 'net_started', False)) and getattr(h, 'net_phase', '') == 'wait',
      '等待阶段即广播 phase')

c = Game(); c.config.control_mode = ControlMode.TOUCH
c.net_nickname = '客户端B'; c.net_ip_input = '127.0.0.1'
c.net_port_input = str(_port); c.state = GameState.NET_JOIN_SETUP
c._net_join()
check(c.net_client is not None and c.net_client.connected, 'B 客户端连上')
check(c.state == GameState.NET_WAIT, '客户端进等待页')
check(until(lambda: h.net_host.connected and h.net_host.client_count == 1),
      '房主看到 1 个客户端')

h._net_host_start_game()
check(h.state == GameState.NET_SETUP, '房主进 NET_SETUP（不再复用 EQUIP_SELECT）')
frame(h)
check(until(lambda: (c.net_client.get_snapshot() or {}).get('phase') == 'setup')
      and (c._net_client_sync_phase() or True) and c.state == GameState.NET_SETUP,
      '客户端被 phase=setup 推进到自己的装备页')

_wl, _cl = h.net_weapon_list, h.net_char_list
h._net_setup_pick_weapon(min(3, len(_wl)-1)); h._net_setup_confirm()
c._net_setup_pick_weapon(min(7, len(_wl)-1)); c._net_setup_pick_char(min(1, len(_cl)-1))
c._net_setup_confirm()
check(until(lambda: 1 in h.net_host.get_loadouts() and h.net_host.ready.get(1)),
      '房主收到 B 独立上报的 loadout 与 ready')
check(h.net_host.get_loadouts()[1]['weapon'] != (h.net_host_loadout or {}).get('weapon'),
      '两人武器互不复用')
check(h.net_host.all_ready(), '全部准备')

check(h._net_host_launch() and h.state == GameState.PLAYING, '房主开局成功')
frame(h)
check(until(lambda: (c.net_client.get_snapshot() or {}).get('phase') == 'playing')
      and (c._net_client_sync_phase() or True) and c.state == GameState.NET_CLIENT_PLAY,
      '**客户端自动进 NET_CLIENT_PLAY（P2 有画面）**')
frame(c)
_px = pygame.surfarray.array3d(c.screen)
_nonblack = int((_px.sum(axis=2) > 90).sum())
check(_nonblack > 5000, '客户端画面非黑屏（%d 像素）' % _nonblack)

h.state = GameState.GAME_OVER; h.wave_count = 7; frame(h)
h._net_send_snapshot_now()   # 绕过 20Hz 节流，立即广播 over
check(until(lambda: (c.net_client.get_snapshot() or {}).get('phase') == 'over')
      and (c._net_client_sync_phase() or True) and c.state == GameState.NET_RESULT,
      '结束同步：客户端进结算页')
frame(c)
h.state = GameState.NET_HOST_SETUP; h.touch_events = []
setattr(h, 'net_dd_key', None); h._dd_overlay_rects = []
frame(h)
te(h, (int(330*_s), int(189*_s)))
check(getattr(h, 'net_dd_key', None) == 'net_cnt', '创建页下拉复用同屏 DropdownGroup')
try: h._net_stop(); c._net_stop()
except Exception: pass

print('=== C. 障碍材质 / 编辑器 / 视野 ===')
g = Game(); g.config.control_mode = ControlMode.TOUCH
from world import GameWorld
class P:
    def __init__(self, **kw): self.__dict__.update(kw)
for _mat, _kw, _want in (
    ('wall', dict(damage=20, vx=10, vy=0, pierce=1), 'block'),
    ('wall', dict(damage=20, vx=10, vy=0, pierce=6), 'pass'),
    ('glass', dict(damage=100, vx=10, vy=0, pierce=1), 'break'),
    ('foliage', dict(damage=20, vx=10, vy=0, pierce=1), 'pass'),
    ('hollow', dict(damage=20, vx=10, vy=0, pierce=5), 'pass'),
    ('vehicle', dict(damage=20, vx=10, vy=0, pierce=1, explosive=True), 'break')):
    check(GameWorld.bullet_vs_obstacle({'type': _mat}, P(**_kw)) == _want,
          '%s → %s' % (_mat, _want))
check(GameWorld.blocks_sight({'type': 'bush'}) and
      not GameWorld.blocks_sight({'type': 'glass'}), '植被挡视线不挡弹')
check(GameWorld.segment_hits_rect(0, 0, 100, 0, pygame.Rect(40, -10, 20, 20)) and
      not GameWorld.segment_hits_rect(0, 0, 100, 0, pygame.Rect(40, 50, 20, 20)),
      '扫掠线段防高速穿透且不误判')

check(hasattr(g, '_me_enter') and hasattr(g.renderer, '_draw_map_editor'), '编辑器已装配')
g.state = GameState.MAP_EDITOR; g._me_enter(); g.draw()
_n0 = len(g.me_obstacles)
g.me_type = 'wall'; g._me_place(300, 300); g._me_place(300, 300)
check(len(g.me_obstacles) == _n0 + 1, '网格放置 + 同格去重')
g.me_type = 'bush'; g._me_place(420, 300)
check(g._me_material('bush') == 'foliage' and '不挡子弹' in g._me_rule_text('bush'),
      '工具栏显示材质与挡弹规则')
g._me_place(420, 300, erase=True)
_saved = bool(g._me_save('quick'))
g._me_clear()
_cleared = len(g.me_obstacles) == 0
_loaded = bool(g._me_load('quick'))
check(_saved and _cleared and _loaded and len(g.me_obstacles) == _n0 + 1,
      '保存 / 清空 / 载入 JSON 往返一致')
try: os.remove('maps/quick.json')
except Exception: pass

from zombie_pkg.vision import VisionSystem
v = VisionSystem(); g.vision = v
g.config.game_mode = GameMode.ENDLESS
g.state = GameState.PLAYING; g.start_game(); g.state = GameState.PLAYING
g.world.obstacles.append({'rect': pygame.Rect(g.player.x + 200, g.player.y - 40, 80, 80),
                          'type': 'wall', 'color': (120, 110, 100), 'rotation': 0})
g.world.invalidate_obs_grid()
try:
    frame(g, 4)
    check(v.mask is not None and v.mask.get_width() < g.scaled_width,
          '视野遮罩 1/3 分辨率（性能）')
    check(len(v.poly) >= 40 and v.visible(g.player.x + 30, g.player.y)
          and not v.visible(g.player.x + 2000, g.player.y), '可见多边形与视距判定')
    v.enabled = False; g.draw(); v.enabled = True
except Exception as e:
    check(False, '视野跑帧异常: %s' % e)

g.world.obstacles = [{'rect': pygame.Rect(g.player.x + 120, g.player.y - 30, 60, 60),
                      'type': 'glass', 'color': (200, 200, 210), 'rotation': 0}]
g.world.invalidate_obs_grid(); g.projectiles = []
from weapons import Weapon, WeaponType
g.projectiles.extend(Weapon(WeaponType.PISTOL).fire(g.player.x, g.player.y, 0.0, player=g.player))
for _ in range(8): g.update(1/60)
check(True, '子弹撞玻璃障碍跑帧无异常')

print('\n===== v2.9.21 精简回归: PASS=%d FAIL=%d =====' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
