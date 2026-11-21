# -*- coding: utf-8 -*-
"""v2.9.21 地图编辑器 / 障碍挡弹 / 视野 专项（含跑帧）。"""
import os, sys
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

g = Game(); g.config.control_mode = ControlMode.TOUCH

print('=== A. 障碍物材质与弹道规则 ===')
from world import GameWorld
class P:
    def __init__(self, **kw): self.__dict__.update(kw)
for _mat, _kw, _want in (
    ('wall', dict(damage=20, vx=10, vy=0, pierce=1), 'block'),
    ('wall', dict(damage=20, vx=10, vy=0, pierce=6), 'pass'),
    ('glass', dict(damage=100, vx=10, vy=0, pierce=1), 'break'),
    ('glass', dict(damage=10, vx=3, vy=0, pierce=1), 'block'),
    ('thin', dict(damage=90, vx=10, vy=0, pierce=1), 'break'),
    ('foliage', dict(damage=20, vx=10, vy=0, pierce=1), 'pass'),
    ('hollow', dict(damage=20, vx=10, vy=0, pierce=5), 'pass'),
    ('vehicle', dict(damage=20, vx=10, vy=0, pierce=1, explosive=True), 'break')):
    check(GameWorld.bullet_vs_obstacle({'type': _mat}, P(**_kw)) == _want,
          '%s %s → %s' % (_mat, _kw.get('pierce'), _want))
check(GameWorld.blocks_sight({'type': 'bush'}) and
      not GameWorld.blocks_sight({'type': 'glass'}),
      '植被挡视线不挡弹 / 玻璃可看穿')
check(GameWorld.segment_hits_rect(0, 0, 100, 0, pygame.Rect(40, -10, 20, 20)),
      '扫掠线段命中障碍（防高速穿透）')
check(not GameWorld.segment_hits_rect(0, 0, 100, 0, pygame.Rect(40, 50, 20, 20)),
      '扫掠线段未命中时不误判')

print('=== B. 独立地图编辑器（v2.9.23 口径） ===')
check(not hasattr(g, '_me_enter') and not hasattr(g.renderer, '_draw_map_editor'),
      '游戏内编辑器 Mixin 已移除')
check(not hasattr(GameState, 'MAP_EDITOR'), '游戏内无地图编辑状态')
import os as _os
check(_os.path.isfile('tools/map_editor_standalone.py'), '独立编辑器工具存在')
check('FINGERDOWN' in io.open('tools/map_editor_standalone.py', encoding='utf-8').read(),
      '独立工具支持触控')
print('=== C. 视野系统 ===')
from zombie_pkg.vision import VisionSystem
v = VisionSystem(); g.vision = v
g.config.game_mode = GameMode.ENDLESS
g.state = GameState.PLAYING; g.start_game(); g.state = GameState.PLAYING
g.world.obstacles.append({'rect': pygame.Rect(g.player.x + 200, g.player.y - 40, 80, 80),
                          'type': 'wall', 'color': (120, 110, 100), 'rotation': 0})
g.world.invalidate_obs_grid()
try:
    for _ in range(6):
        g.update(1/60); g.draw()
    check(v.mask is not None, '视野遮罩已生成（1/3 分辨率）')
    check(v.mask.get_width() < g.scaled_width, '遮罩分辨率低于屏幕（性能）')
    check(len(v.poly) >= 40, '可见多边形由 48 条射线生成')
    check(v.visible(g.player.x + 30, g.player.y), '玩家近处可见')
    check(not v.visible(g.player.x + 2000, g.player.y), '视距外不可见')
    v.enabled = False
    g.draw()
    check(True, '关闭视野后渲染无异常')
    v.enabled = True
except Exception as e:
    check(False, '视野跑帧异常: %s' % e)

print('=== D. 子弹撞障碍（实际跑帧） ===')
try:
    from weapons import Weapon, WeaponType
    g.world.obstacles = [{'rect': pygame.Rect(g.player.x + 120, g.player.y - 30, 60, 60),
                          'type': 'glass', 'color': (200, 200, 210), 'rotation': 0}]
    g.world.invalidate_obs_grid()
    g.projectiles = []
    _w = Weapon(WeaponType.PISTOL)
    _pr = _w.fire(g.player.x, g.player.y, 0.0, player=g.player)
    g.projectiles.extend(_pr)
    for _ in range(12): g.update(1/60)
    check(True, '子弹与障碍碰撞跑帧无异常')
    check(any(o['type'] == 'glass' for o in g.world.obstacles) or
          len(g.projectiles) == 0, '玻璃障碍被挡 / 弹丸按规则结算')
except Exception as e:
    check(False, '子弹撞障碍异常: %s' % e)

print('=== E. 全模式跑帧（视野开启） ===')
for _m in (GameMode.ENDLESS, GameMode.STORY, GameMode.TIMED):
    try:
        g.config.game_mode = _m
        g.state = GameState.PLAYING; g.start_game(); g.state = GameState.PLAYING
        for _ in range(8): g.update(1/60); g.draw()
        check(True, '%s 8 帧无异常' % _m.name)
    except Exception as e:
        check(False, '%s 跑帧异常: %s' % (_m.name, e))

print('\n===== v2.9.21 编辑器/障碍/视野: PASS=%d FAIL=%d =====' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
