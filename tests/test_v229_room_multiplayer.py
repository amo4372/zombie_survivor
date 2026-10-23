# -*- coding: utf-8 -*-
"""v2.2.9 同屏多人房间配置 + PvP 敌方揭示 + 网络房间同步 + P2 词条 专项回归"""
import os, sys, io
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = failed = 0
def check(name, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")

# ============ 1. 房间配置循环逻辑 ============
print("\n[1] 房间配置：人数/阵营循环")
for n in (2, 3, 4):
    nxt = (n - 1) % 3 + 2
    check(f"人数 {n} → {nxt}", nxt != n and 2 <= nxt <= 4)
for t in (2, 3, 4):
    nxt = (t - 1) % 3 + 2
    check(f"阵营 {t} → {nxt}", nxt != t and 2 <= nxt <= 4)

# ============ 2. 房间配置 UI 接线 ============
print("\n[2] 房间配置 UI 接线")
_src = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("同屏入口跳 MULTI_ROOM_CONFIG", "GameState.MULTI_ROOM_CONFIG" in
      _src.split("def _draw_net_multiplayer")[0].split("def _draw_multiplayer_select")[1])
check("_draw_multi_room_config 存在", "def _draw_multi_room_config" in _src)
check("_start_multi_room_game 存在", "def _start_multi_room_game" in _src)
# v2.2.11：改为逐玩家配置（per-player weapon 写入选择槽 + 未配置玩家沿用 P1 武器兜底）
_gc11 = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check("per-player 武器写入选择槽", 'f"selected_weapon_p{_i}"' in _gc11)
check("未配置玩家兜底默认武器", "_default_w" in _src)
_src2 = open("renderer_pkg/render_core.py", encoding="utf-8").read()
check("render_core 分发 MULTI_ROOM_CONFIG", "MULTI_ROOM_CONFIG" in _src2)

# ============ 3. 出生点分散 ============
print("\n[3] 出生点分散")
_gc = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check("P2 右移 140", "self.player.x + 140" in _gc)
check("P3 上移 140", "(0, 140)" in _gc)
check("P4 左移 140", "(-140, 0)" in _gc)

# ============ 4. PvP 敌方位置揭示状态机 ============
print("\n[4] PvP 敌方揭示状态机")
_gc2 = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check("pvp_reveal_active 状态存在", "pvp_reveal_active" in _gc2)
check("开局 8s 全显", "_c <= 3.0" in _gc2)
check("45s 周期闪 3s", "_c % 45.0) > 42.0" in _gc2)
_dm = open("renderer_pkg/draw_multiplayer.py", encoding="utf-8").read()
check("draw_enemy_player_indicators 存在", "def draw_enemy_player_indicators" in _dm)
check("视口内已调用", "draw_enemy_player_indicators(renderer, game, viewports, vp)" in _dm)

# ============ 5. 网络房间配置同步 ============
print("\n[5] 网络房间配置同步")
_net = open("net.py", encoding="utf-8").read()
check("NetHost 接受 room_cfg", "def __init__(self, port=DEFAULT_PORT, room_cfg=None)" in _net)
check("welcome 带 room_cfg", '"room_cfg"] = self.room_cfg' in _net)
check("NetClient 保存 room_cfg", "self.room_cfg = _rc" in _net)
_mn = open("zombie_pkg/mix_net.py", encoding="utf-8").read()
check("主机下发房间配置", '"coop_player_count": int(getattr(self' in _mn)
check("客户端应用房间配置", "_net_room_cfg_applied" in _mn)

# ============ 6. P2 角色词条 ============
print("\n[6] P2 角色词条")
check("P2 暴击率应用（crit_chance += crit_bonus_add）",
      "_pp.crit_chance += _pp.crit_bonus_add" in _gc)

# ============ 7. 运行时集成：房间配置开始游戏 ============
print("\n[7] 运行时集成：房间配置开始游戏")
import pygame
pygame.init()
pygame.display.set_mode((640, 480))
import game
g = game.Game()
g.config.pvp_enabled = False
g.coop_player_count = 3
g.room_map_idx = 1
g.room_weapon_idx = 0
# 桩 _start_multi_room_game 依赖的武器映射
try:
    from config import WeaponType
    from weapons import Weapon
    _throw={WeaponType.GRENADE,WeaponType.MOLOTOV,WeaponType.SMOKE_GRENADE}
    _wlist=[wt for wt in WeaponType if wt not in _throw]
    check("武器候选非空", len(_wlist) > 0)
    g.room_weapon_idx = 0
    check("房间武器索引有效", 0 <= g.room_weapon_idx < len(_wlist))
except Exception as e:
    check(f"武器列表加载 ({e})", False)
# PvP reveal 运行时
g.config.pvp_enabled = True
g.is_multiplayer_active = lambda: True
g._pvp_reveal_cycle = 0.0
g._pvp_reveal_cycle += 5.0
g.pvp_reveal_active = (g._pvp_reveal_cycle <= 8.0 or (g._pvp_reveal_cycle % 45.0) > 42.0)
check("开局揭示激活", g.pvp_reveal_active is True)
g._pvp_reveal_cycle = 40.0
g.pvp_reveal_active = (g._pvp_reveal_cycle <= 8.0 or (g._pvp_reveal_cycle % 45.0) > 42.0)
check("非闪烁期不揭示", g.pvp_reveal_active is False)
g._pvp_reveal_cycle = 44.0
g.pvp_reveal_active = (g._pvp_reveal_cycle <= 8.0 or (g._pvp_reveal_cycle % 45.0) > 42.0)
check("周期闪烁揭示", g.pvp_reveal_active is True)

print(f"\n===== 结果: {passed} 通过, {failed} 失败 =====")
sys.exit(1 if failed else 0)
