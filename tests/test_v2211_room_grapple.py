# -*- coding: utf-8 -*-
"""v2.2.11 同屏多人房间配置重构（下拉栏+逐玩家设置+显式阵营）+ 钩爪锁定圈全模式修复 专项回归"""
import os, sys, time
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

# ============ 1. 房间配置 UI 下拉栏重构 ============
print("\n[1] 房间配置 UI：下拉栏 + 逐玩家")
_ui = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("全局下拉：人数", "room_dropdown" in _ui and '"count"' in _ui)
check("全局下拉：玩法 PvP 切换", '"pvp"' in _ui)
check("全局下拉：阵营数", '"teams"' in _ui)
check("全局下拉：难度", '"diff"' in _ui)
check("全局下拉：模式", '"mode"' in _ui)
check("全局下拉：地图", '"map"' in _ui)
check("逐玩家武器下拉", '"pweapon"' in _ui)
check("逐玩家角色下拉", '"pchar"' in _ui)
check("逐玩家阵营下拉", '"pteam"' in _ui)
check("一键统一按钮", "_apply_to_all" in _ui)
check("名字输入框聚焦", "room_name_focus" in _ui)
check("房间模式设置", "def _set_room_mode" in _ui)

# ============ 2. 逐玩家配置应用 ============
print("\n[2] 逐玩家配置 + 显式阵营")
_gc = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check("room_player_cfgs 显式阵营优先", 'rcfg.get("team") is not None' in _gc)
check("team 1-based → 0-based 裁剪", "int(_rcfg[\"team\"]) - 1" in _gc)
check("逐玩家名字 nick", "_pp.nick = _nm" in _gc)
check("per-player 武器/角色写入选择槽（创建前）", "setattr(self, f\"selected_weapon_p{_i}\", _w0)" in _gc)
_gin = open("zombie_pkg/mix_input.py", encoding="utf-8").read()
check("房间名字输入 TEXTINPUT", "GameState.MULTI_ROOM_CONFIG and getattr(self, 'room_name_focus'" in _gin)

# ============ 3. 运行时：下拉渲染 + 逐玩家应用 + 显式阵营 ============
print("\n[3] 运行时集成")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
import game
from config import GameState
g = game.Game()
try:
    from config import GameMode
    g.config.game_mode = GameMode.ENDLESS
except Exception:
    pass
g.state = GameState.MULTI_ROOM_CONFIG
g.coop_player_count = 2
class _R:
    def __init__(self, game):
        self.game = game
        self.screen = game.screen
    def _set_room_mode(self, g2, idx):
        pass
    def _cycle_room_mode(self, g2):
        pass
    def _start_multi_room_game(self):
        g2 = self.game
        g2.multiplayer_mode = "same_screen"
        g2.state = GameState.PLAYING
        g2.start_game()
from renderer_pkg.draw_ui import UiMixin
r = _R(g)
r.__class__ = type("R", (_R, UiMixin), {})
r._draw_multi_room_config()
check("room_player_cfgs 初始化", hasattr(g, 'room_player_cfgs') and isinstance(g.room_player_cfgs, dict))
check("room_sel_player 初始化", getattr(g, 'room_sel_player', 0) == 1)
g.room_player_cfgs[1] = {"name": "小明", "weapon": None, "char": "突击手", "team": 1}
g.room_player_cfgs[2] = {"name": "小红", "weapon": None, "char": "医护兵", "team": 2}
g.config.pvp_enabled = True
g.config.pvp_teams = 2
r._draw_multi_room_config()
r._start_multi_room_game()
p1, p2 = g.player, g.player2
check("玩家已创建", p1 is not None and p2 is not None)
check("P1 名字生效", getattr(p1, 'nick', None) == "小明")
check("P2 名字生效", getattr(p2, 'nick', None) == "小红")
check("P1 显式阵营=0", p1.team_id == 0)
check("P2 显式阵营=1", p2.team_id == 1)
check("P1 角色生效", getattr(g, 'selected_character', None) == "突击手")
check("P2 角色生效", getattr(g, 'selected_character2', None) == "医护兵")

# ============ 4. 钩爪锁定圈（锚点跟随/优先级/蓄力） ============
print("\n[4] 钩爪锁定圈全模式修复")
_gr = open("entities_pkg/gear.py", encoding="utf-8").read()
check("update_grapple_lock 支持 aim_angle/aim_dist", "aim_angle=None, aim_dist=None" in _gr)
check("锚点存入 grapple_aim_anchor", "self.grapple_aim_anchor = (_ax, _ay)" in _gr)
check("绘制锚点准星", "预瞄锚点（中心准星标记" in _gr)
check("绘制蓄力进度弧", "蓄力进度弧" in _gr)
from entities_pkg.gear import RiotGear
rg = RiotGear()
rg.equipped = True
rg.grapple_aiming = True
class It:
    pass
class Ez:
    pass
it = It(); it.alive = True; it.x = 500; it.y = 0
e = Ez(); e.alive = True; e.is_boss = False; e.x = 300; e.y = 0
rg._grapple_aim_charge = 0.0
rg._grapple_aim_start = time.time() - 1.0
rg.update_grapple_lock(0, 0, [e], [it], aim_angle=0.0, aim_dist=400)
check("锚点=瞄准方向+距离处", abs(rg.grapple_aim_anchor[0] - 400) < 1)
check("圈内道具优先锁定", rg.grapple_locked_target is it)
rg.update_grapple_lock(0, 0, [e], [], aim_angle=0.0, aim_dist=400)
check("无道具锁定最近敌人", rg.grapple_locked_target is e)
rg.update_grapple_lock(0, 0, [], [], aim_angle=90.0, aim_dist=200)
ax, ay = rg.grapple_aim_anchor
check("锚点跟随瞄准方向", abs(ax) < 1 and abs(ay - 200) < 1)
rg._grapple_aim_start = time.time() - 0.1
rg.update_grapple_lock(0, 0, [e], [it], aim_angle=0.0, aim_dist=400)
r0 = rg.grapple_lock_radius * max(0.35, rg._grapple_aim_charge)
rg._grapple_aim_start = time.time() - 1.0
rg.update_grapple_lock(0, 0, [e], [it], aim_angle=0.0, aim_dist=400)
r1 = rg.grapple_lock_radius * max(0.35, rg._grapple_aim_charge)
check("锁定圈由小到大", r1 > r0)
screen = pygame.display.get_surface()
rg.draw(screen, player_x=0, player_y=0, camera_x=0, camera_y=0, scale=1.0)
check("gear 绘制（含锚点/圈/进度弧）", True)

# ============ 5. P2 触控锁定圈接线 ============
print("\n[5] P2 触控锁定圈")
_mm = open("zombie_pkg/mix_multi.py", encoding="utf-8").read()
check("_update_p2_grapple_lock 支持 caster", "def _update_p2_grapple_lock(self, p2, aiming, caster=None)" in _mm)
check("P2 触控传 caster", "_update_p2_grapple_lock(p2, bool(c2sc.is_aiming), caster=c2sc)" in _mm)
_mp = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("P1 触控传角度/距离", "aim_angle=_aim_ang, aim_dist=_aim_dist" in _mp)

print(f"\n===== 结果: {passed} 通过, {failed} 失败 =====")
sys.exit(1 if failed else 0)
