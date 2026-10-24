# -*- coding: utf-8 -*-
"""v2.5.8 批次测试（运行时行为验证 + 源码接线断言）

覆盖本轮改动：
#171 开发者模式多人化——每个玩家独立面板（状态/按钮/视口互不干扰）
#172 开发者面板新增「TP 到某个玩家」（多人/PvP 传送）
#173 开发者面板新增「免疫僵尸伤害但不免疫玩家伤害」（抗尸）
#174 PvP 开发者能力（秒杀敌对玩家 / 面板按阵营）
#175 更新器镜像代理容错（多节点测速 + 失败自动换节点）
"""
import os
import re
import subprocess
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OK = 0
FAIL = 0


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ======================================================================
print("== #171 开发者模式多人化（每玩家独立面板） ==")

_ds = read("dev_state.py")
check("新增 dev_state.py（每玩家状态类）", os.path.exists(os.path.join(ROOT, "dev_state.py")))
check("DevPlayerState 含 god / zombie_immune / panel_open / tp_target",
      all(k in _ds for k in ("self.god", "self.zombie_immune", "self.panel_open", "self.tp_target")))
check("状态可同步到玩家实体（apply_to）", "def apply_to" in _ds and "dev_zombie_immune" in _ds)

_gc = read("zombie_pkg/game_core.py")
check("game_core 引入 build_dev_states", "from dev_state import" in _gc)
check("初始化 dev_states（P1~P4）", "self.dev_states = build_dev_states()" in _gc)
check("dev_god 兼容属性转发 P1", "@property\n    def dev_god" in _gc.replace("\r", ""))
check("dev_panel_open 兼容属性转发 P1", "def dev_panel_open" in _gc)
check("dev_buttons 兼容属性转发 P1", "def dev_buttons" in _gc)
check("提供 _dev_viewport_rect（分屏各自视口）", "def _dev_viewport_rect" in _gc)
check("提供 _dev_player_indices / _dev_tp_targets", "def _dev_player_indices" in _gc and "def _dev_tp_targets" in _gc)
check("__init__ 完整（records/assets 仍在 init 内，未被方法块截断）",
      _gc.index("self.records = GameRecords(base_path)") < _gc.index("def save_ai_stats"))

_mi = read("zombie_pkg/mix_input.py")
check("_rebuild_dev_buttons 支持玩家序号参数", "def _rebuild_dev_buttons(self, index=1)" in _mi)
check("_dev_action 接收面板所属玩家", "def _dev_action(self, index=1, action=\"\")" in _mi)
check("_update_dev_panel 逐玩家遍历面板", "for idx in (1, 2, 3, 4)" in _mi)
check("F9 切 P1 面板 / F10 切 P2 面板", "pygame.K_F9" in _mi and "pygame.K_F10" in _mi)

_dd = read("renderer_pkg/draw_dev.py")
check("面板绘制按玩家循环", "for idx in (1, 2, 3, 4)" in _dd)
check("面板锁在各自视口内（不再全屏固定位置）", "_dev_viewport_rect" in _dd and "_dev_panel_positions" in _dd)
check("面板底板只压暗自身区域", "panel_bg.fill((0, 0, 0, 150))" in _dd)

_rc = read("renderer_pkg/render_core.py")
check("渲染入口：任一面板打开即绘制", "st.panel_open for st in" in _rc)
check("网络客户端也绘制开发者面板",
      "GameState.NET_CLIENT_PLAY" in _rc and "_draw_dev_panel()" in _rc)

# ======================================================================
print("== #172 TP 到某个玩家 ==")
check("_dev_teleport_to 实现存在", "def _dev_teleport_to" in _gc)
check("传送会移动坐标并刷新摄像机", "src.x = dst.x" in _gc and "cam.update" in _gc)
check("面板有 TP 目标选择 + 立即传送按钮", '"tp_target"' in _mi and '"tp_now"' in _mi)
check("TP 目标循环包含自身以外玩家", "[0] + self._dev_tp_targets(idx)" in _mi)

# ======================================================================
print("== #173 免疫僵尸伤害但不免疫玩家伤害 ==")
_pl = read("entities_pkg/player.py")
check("take_damage 增加 source 参数", "def take_damage(self, damage, damage_type=\"melee\"" in _pl
      and "source=\"zombie\"" in _pl)
check("抗尸判定：source != player 才免疫",
      re.search(r"dev_zombie_immune[\s\S]{0,120}source != \"player\"", _pl) is not None)
check("PvP 伤害标记为 player 来源（投射物 3 处）",
      _pl is not None and read("zombie_pkg/mix_playing.py").count("source='player'") >= 3)
check("PvP 近战伤害标记为 player 来源（mix_combat）",
      "source='player'" in read("zombie_pkg/mix_combat.py"))
check("面板有抗尸开关按钮", '"zombie_immune"' in _mi)
check("抗尸状态同步到玩家实体", "st.apply_to(player)" in _mi)

# ======================================================================
print("== #174 PvP 开发者能力 ==")
check("_dev_kill_hostile_players 实现", "def _dev_kill_hostile_players" in _gc)
check("PvP 下只杀敌对阵营", "pvp and getattr(p, \"team_id\", 0) == my_team" in _gc)
check("PvP 时面板多出「秒杀敌对」按钮", 'if pvp:' in _mi and '"kill_hostile"' in _mi)
check("暂停菜单有 P2 开发者面板按钮", "P2开发者面板" in read("zombie_pkg/mix_menu.py"))
check("暂停菜单处理 P2 面板开关", "P2开发者面板" in read("renderer_pkg/draw_ui.py"))

# ======================================================================
print("== #175 更新器镜像代理容错 ==")
_up = read("updater.py")
check("定义多镜像节点列表 GH_MIRRORS", "GH_MIRRORS = [" in _up)
check("镜像节点含 ghfast / gh-proxy 等", "ghfast.top" in _up and "gh-proxy.net" in _up)
check("_mirror_candidates 遍历全部镜像", "for _p in GH_MIRRORS" in _up)
check("下载失败自动换下一个节点", "所有下载节点均失败" in _up and "for _try_url in _cands" in _up)
check("测速最快节点排最前", "_cands.insert(0, _fast)" in _up)

# ======================================================================
print("== 运行时行为验证（真实跑帧） ==")
try:
    import pygame
    pygame.init()
    pygame.display.set_mode((1280, 720))
    from game import Game, GameState
    from entities_pkg.player import Player

    g = Game()
    g.start_game()
    g.state = GameState.PLAYING
    g.dev_mode = True
    g.multiplayer_mode = "same_screen"
    g.player2 = Player(g.player.x + 300, g.player.y)
    g.camera2 = type(g.camera)(640, 720)

    # --- 每玩家独立状态 ---
    st1, st2 = g._dev_state(1), g._dev_state(2)
    check("P1/P2 状态对象不同", st1 is not st2)
    g._dev_action(1, "god")
    check("P1 无敌开关只影响 P1", st1.god and not st2.god)
    check("P1 无敌同步到 P1 实体", g.player.dev_god and not g.player2.dev_god)

    g._dev_action(1, "zombie_immune")
    check("P1 抗尸开关只影响 P1", st1.zombie_immune and not st2.zombie_immune)
    check("P1 抗尸同步到 P1 实体", g.player.dev_zombie_immune and not g.player2.dev_zombie_immune)

    # --- 抗尸语义：僵尸伤害被挡、玩家伤害照吃 ---
    # 先关掉全能无敌（否则无敌会先行拦截所有伤害）
    g._dev_action(1, "god")
    check("可单独关闭 P1 无敌", (not st1.god) and st1.zombie_immune)
    g.player.hp = g.player.max_hp
    _hp0 = g.player.hp
    g.player.take_damage(30, damage_type="melee", source="zombie")
    check("抗尸状态下僵尸伤害被完全挡住", g.player.hp == _hp0, f"hp={g.player.hp}")
    g.player.take_damage(30, damage_type="ranged", source="player", bypass_dodge=True)
    check("抗尸状态下玩家伤害照吃", g.player.hp < _hp0, f"hp={g.player.hp}")

    # --- 全能无敌仍挡玩家伤害 ---
    g._dev_action(1, "god")   # 重新打开无敌
    check("P1 无敌重新打开", st1.god)
    g.player.hp = g.player.max_hp
    g.player.take_damage(30, damage_type="ranged", source="player", bypass_dodge=True)
    check("无敌状态下玩家伤害也被挡住", g.player.hp == g.player.max_hp)

    # --- TP 到玩家 ---
    g.player.x, g.player.y = 100.0, 100.0
    g.player2.x, g.player2.y = 900.0, 900.0
    g._dev_action(1, "tp_target")
    check("TP 目标可选到 P2", st1.tp_target == 2, f"tp={st1.tp_target}")
    ok, msg = g._dev_teleport_to(1, st1.tp_target)
    check("传送成功", ok, msg)
    check("P1 落到 P2 附近",
          abs(g.player.x - g.player2.x) < 200 and abs(g.player.y - g.player2.y) < 200,
          f"p1=({g.player.x:.0f},{g.player.y:.0f}) p2=({g.player2.x:.0f},{g.player2.y:.0f})")

    # --- 面板独立性 ---
    g._rebuild_dev_buttons(1)
    g._rebuild_dev_buttons(2)
    check("P1/P2 按钮列表互相独立", g.dev_states[1].buttons is not g.dev_states[2].buttons)
    check("按钮带动作标记", all(hasattr(b, "dev_action") for b in g.dev_states[1].buttons))
    check("面板按钮在各自视口内（P1 左半 / P2 右半）",
          g._dev_viewport_rect(1).x == 0 and g._dev_viewport_rect(2).x == 640,
          f"{g._dev_viewport_rect(1)} {g._dev_viewport_rect(2)}")
    _p1 = g._dev_panel_positions(1)
    _p2 = g._dev_panel_positions(2)
    check("P1 面板按钮全在左半屏", all(x < 640 for x, _ in _p1))
    check("P2 面板按钮全在右半屏", all(x >= 640 for x, _ in _p2))

    # --- PvP：秒杀敌对 ---
    g.config.pvp_enabled = True
    g.config.pvp_teams = 2
    g.player.team_id = 0
    g.player2.team_id = 1
    g._rebuild_dev_buttons(1)
    _texts = [b.text for b in g.dev_states[1].buttons]
    check("PvP 面板出现「秒杀敌对」", "秒杀敌对" in _texts, str(_texts))
    g.player2.alive = True
    g.player2.hp = 100
    n = g._dev_kill_hostile_players(1)
    check("秒杀敌对玩家生效", n >= 1 and not g.player2.alive, f"n={n}")

    # --- 渲染不崩 ---
    st1.panel_open = True
    st2.panel_open = True
    for _ in range(20):
        g.update(1 / 60)
        g.renderer.render()
    check("双面板分屏渲染 20 帧无异常", True)

    # --- 关闭面板 ---
    g._dev_action(2, "close")
    check("P2 可单独关闭自己的面板", (not st2.panel_open) and st1.panel_open)

    # --- 开局重置 ---
    g._dev_reset_states()
    check("新局重置所有开发者状态",
          (not st1.god) and (not st1.zombie_immune) and (not st1.panel_open))
    pygame.quit()
except Exception as e:
    import traceback
    traceback.print_exc()
    check(f"运行时验证异常: {e!r}", False)

# ======================================================================
print("== 运行时冒烟（子进程实跑 main.py） ==")
try:
    r = subprocess.run(
        [sys.executable, "main.py"],
        cwd=ROOT, timeout=180,
        env={**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy",
             "ZOMBIE_SMOKE": "1"},
        capture_output=True, text=True)
    out = r.stdout + r.stderr
    has_err = bool(re.search(r"Traceback \(most recent call last\)", out)) or "RuntimeError" in out
    check("子进程退出码=0", r.returncode == 0, out[-600:])
    check("输出含冒烟通过标记", "[SMOKE] 运行时冒烟通过" in out, out[-400:])
    check("无 Traceback/运行时异常", not has_err, out[-600:])
except Exception as e:
    check(f"子进程启动(超时/环境): {e}", False)

print()
print(f"===== v2.5.8 批次结果: {OK} 通过, {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
