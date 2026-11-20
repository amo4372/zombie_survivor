# -*- coding: utf-8 -*-
"""v2.9.22 精简回归（单 Game 实例，目标 < 30s）。

覆盖：
  A. 网络联机代码彻底移除（含原 Traceback 崩溃点）
  B. PvP 对玩家伤害按来源独立结算 + AWM 数值
  C. 无畏冲锋撞 Boss / 敌方玩家后退出
  D. debuff 免疫：叠层 → 覆盖 → 免疫，不清除现有 debuff
  E. 冰冻区域稳定冻结（不再冻一下马上解冻）
  F. 全模式 / 同屏双人跑帧
"""
import os, sys, time, types, io, importlib.util
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)
_VENDOR = os.path.join(ROOT, "_vendor")
if os.path.isdir(_VENDOR):
    sys.path.insert(0, _VENDOR)
import pygame
pygame.init(); pygame.display.set_mode((1280, 720))

PASS = FAIL = 0
def check(ok, msg):
    global PASS, FAIL
    if ok: PASS += 1; print('  OK  ', msg)
    else: FAIL += 1; print('  FAIL', msg)

def src(p):
    return io.open(p, encoding='utf-8').read()

print('=== A. 网络联机彻底移除 ===')
for p in ('net.py', 'net_discovery.py', 'net_p2p.py',
          'zombie_pkg/mix_net.py', 'zombie_pkg/mix_net_lobby.py',
          'renderer_pkg/draw_net_lobby.py',
          'NETWORK_DESIGN.md', 'NETWORK_SELFTEST.md', 'tools/lan_selftest.py'):
    check(not os.path.exists(p), '已删除 ' + p)
_cfg = src('config.py')
check('NET_LOBBY' not in _cfg and 'NET_CLIENT_PLAY' not in _cfg
      and 'NET_MULTIPLAYER' not in _cfg, 'GameState 无网络状态枚举')
from config import GameState, ControlMode, GameMode
check(not [x.name for x in GameState if x.name.startswith('NET')],
      '运行时枚举无 NET_* 成员')
from zombie_pkg import Game
from renderer_pkg import Renderer
check(not any('NetMixin' in c.__name__ or 'NetLobby' in c.__name__
              for c in Game.__mro__), 'Game MRO 无联机 Mixin')
check(not any('NetLobby' in c.__name__ for c in Renderer.__mro__),
      'Renderer MRO 无联机 Mixin')
_du = src('renderer_pkg/draw_ui.py')
check('_draw_net_client' not in _du and '_draw_net_wait' not in _du
      and '_draw_net_multiplayer' not in _du,
      '**原 IndexError 崩溃点 `_draw_net_client` 已删除**')
check('网络联机' not in src('zombie_pkg/mix_menu.py'), '菜单无网络联机按钮')
# 运行代码里不再有任何联机符号
_syms = ('NetHost', 'NetClient', 'NetDiscovery', 'net_discovery', 'net_p2p',
         '_net_send_snapshot', '_net_client_sync_phase', 'mix_net_lobby')
_bad = []
for _dp, _dn, _fn in os.walk('.'):
    if any(x in _dp for x in ('__pycache__', '_vendor', 'releases', 'tests', 'tools', '.git')):
        continue
    for _f in _fn:
        if _f.endswith('.py'):
            _p = os.path.join(_dp, _f)
            _s = src(_p)
            for _k in _syms:
                if _k in _s:
                    _bad.append((_p, _k))
check(not _bad, '运行代码零联机符号残留 %s' % (_bad[:3],))

print('=== B. PvP 伤害按来源独立 ===')
g = Game(); g.config.control_mode = ControlMode.TOUCH
check(g._pvp_dmg_to_player(100, None) == 60, '通用武器 ×0.6（原 ×0.2）')
check(g._pvp_dmg_to_player(100, types.SimpleNamespace(weapon_type='WeaponType.AWP')) == 90,
      '狙击武器 ×0.9')
check(g._pvp_dmg_to_player(100, None, kind='gear') == 85, '防爆套装独立 ×0.85')
check(g._pvp_dmg_to_player(100, None, kind='vehicle') == 115, '载具独立 ×1.15')
check(g._pvp_dmg_to_player(100, types.SimpleNamespace(pvp_no_atten=True)) == 120,
      '特高伤武器 ×1.2')
check(g._pvp_dmg_to_player(999, types.SimpleNamespace(damage_vs_player=110)) == 110,
      'damage_vs_player 权威值优先')
check('"damage_vs_player": 110' in src('weapons.py'), 'AWM 对玩家 80 → 110')
check('DATA_VERSION = 6' in src('gamedata/seed.py'), '数据版本 6，玩家库随更新同步')
_sk = src('zombie_pkg/mix_skills.py')
check("kind='gear'" in _sk and '0.45 * player.damage_mult' in _sk,
      '防爆肘击走独立倍率且基础系数上调')
_vh = src('entities_pkg/vehicles.py')
check('PVP_VEHICLE_MULT' in _vh, '载具撞击走独立倍率')

print('=== C. 无畏冲锋撞 Boss / 玩家退出 ===')
check(_sk.count('rg.charge_timer = min(rg.charge_timer, 0.0)') >= 2,
      '撞 Boss / 撞敌方玩家两处均提前结束冲锋')
check('if fearless and _is_boss:' in _sk and 'v2.9.22：无畏冲锋撞到敌方玩家后退出冲锋状态' in _sk,
      '退出条件与分支位置正确')
# 真实模拟：假 Boss 贴近冲锋玩家，跑一帧后冲锋应结束
class _FakeBoss:
    is_boss = True; alive = True; max_hp = 5000; hp = 5000; size = 30
    def __init__(self, x, y): self.x, self.y = x, y; self._last_hit_player = None
    def take_damage(self, *a, **k): pass
    def apply_buff(self, *a, **k): pass
    def knockdown(self, *a, **k): pass
try:
    g.config.game_mode = GameMode.ENDLESS
    g.state = GameState.PLAYING; g.start_game(); g.state = GameState.PLAYING
    rg = g.player.riot_gear
    rg.charge_active = True; rg.charge_timer = 10.0; rg.charge_hit_ids = set()
    rg.fearless_active = True; rg.fearless_level = 1
    rg.charge_direction = 0.0; rg.charge_speed = 0.0
    g.player.fearless_charge_active = True
    g.enemies.append(_FakeBoss(g.player.x + 10, g.player.y))
    g._update_charge(1/60, player=g.player)
    check(not rg.charge_active and not rg.fearless_active
          and not g.player.fearless_charge_active,
          '**实际撞到 Boss 后冲锋状态已退出**')
    g.enemies.clear()
except Exception as e:
    check(False, '冲锋模拟异常 %r' % e)

print('=== D. debuff 免疫：叠层→覆盖→免疫 ===')
from combat_pkg.status import (EntityStatus, IMMUNITY_THRESHOLD,
                               IMMUNITY_DURATION, status_meta)
st = EntityStatus()
_p = EntityStatus()
for _ in range(3):
    _p.apply('poison', bridge=False)
check(_p.get('poison').stacks == 3 and not _p.is_immune('poison'),
      '未达 5 层上限时只叠层，不触发免疫')
for _ in range(IMMUNITY_THRESHOLD + 1):
    st.apply('freeze', bridge=False)
check(st.is_immune('freeze'), '满层后覆盖 %d 次 → 免疫' % IMMUNITY_THRESHOLD)
check(st.has('freeze'), '免疫不清除当前已有的 debuff')
_cur = st.get('freeze'); _t0 = _cur.time
st.update(0.5)
_r = st.apply('freeze', bridge=False)
check(_r is _cur and abs(_r.time - (_t0 - 0.5)) < 1e-6,
      '免疫窗口内不再覆盖 / 不刷新时长')
check(len(st.immune_buffs()) == 1 and st.immune_buffs()[0].kind == 'immune_freeze',
      '免疫本身是可见 buff')
check(status_meta('immune_freeze')['name'] == '免疫·冰冻', '免疫 buff 元数据')
st.update(IMMUNITY_DURATION + 0.1)
check(not st.is_immune('freeze') and not st.has('freeze')
      and st.refresh_count('freeze') == 0,
      '免疫到期 / debuff 自然结束后计数归零')
check(st.apply('freeze', bridge=False) is not None, '之后可重新被该 debuff 命中')

print('=== E. 冰冻区域稳定冻结 ===')
try:
    g.frost_zones = [{"x": g.player.x, "y": g.player.y, "radius": 96.0,
                      "timer": 0.0, "duration": 4.6, "applied": {}}]
    g.frost_cans = []
    g.player.status.clear() if hasattr(g.player, 'status') and g.player.status else None
    _stable = True
    for _i in range(120):          # 2 秒，跨过 2 次 0.9s 节流
        g._update_frost_zones(1/60)
        _s = getattr(g.player, 'status', None)
        if _s is None or not _s.has('freeze'):
            _stable = False
            break
    check(_stable, '区域内连续 2 秒保持冻结（不再冻一下马上解冻）')
    check(float(getattr(g.player, 'frozen_timer', 0) or 0) > 0,
          '旧渲染链路 frozen_timer 同步保持')
    check('duration=3.2' in src('zombie_pkg/mix_playing.py'),
          '区域 debuff 持续 3.2s > 0.9s 节流间隔')
except Exception as e:
    check(False, '冰冻区域异常 %r' % e)

print('=== F. 全模式 / 同屏双人跑帧 ===')
for _m in (GameMode.ENDLESS, GameMode.STORY, GameMode.TIMED):
    try:
        g.config.game_mode = _m
        g.state = GameState.PLAYING; g.start_game(); g.state = GameState.PLAYING
        for _ in range(6): g.update(1/60); g.draw()
        check(True, '%s 6 帧无异常' % _m.name)
    except Exception as e:
        check(False, '%s 跑帧异常 %r' % (_m.name, e))
try:
    g.multiplayer_mode = 'same_screen'
    g.coop_player_count = 2
    g.config.pvp_enabled = True
    g.state = GameState.PLAYING; g.start_game(); g.state = GameState.PLAYING
    for _ in range(6): g.update(1/60); g.draw()
    check(g.player2 is not None, '同屏双人 P2 正常创建')
    check(True, '同屏双人 6 帧无异常')
except Exception as e:
    check(False, '同屏双人跑帧异常 %r' % e)

print('\n===== v2.9.22 精简回归: PASS=%d FAIL=%d =====' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
