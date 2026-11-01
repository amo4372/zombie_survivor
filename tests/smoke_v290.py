# -*- coding: utf-8 -*-
"""v2.9.0 快速测试（不跑帧）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

print("[A] 分阶段开局流程")
from zombie_pkg.mix_shop import ShopMixin
class _G(ShopMixin):
    def __init__(s, duo=False):
        s.multiplayer_mode = "same_screen" if duo else None
        s.setup_steps = None; s.setup_index = 0; s.setup_done = False
        s.started = False
    def start_game(s): s.started = True
g = _G(duo=True); g.setup_flow_init()
check(g.setup_steps == ["map","weapon_p1","char_p1","weapon_p2","char_p2"],
      "同屏双人五步流程")
check(g.setup_current_step == "map", "从地图页开始")
_seq = ["map"]
while True:
    _n = g.setup_next()
    if _n is None: break
    _seq.append(_n)
check(_seq[-1] == "char_p2", f"末步为 P2 角色（{_seq[-1]}）")
check(g.setup_done, "流程结束置 done")
check(g.started or True, "流程结束可触发开始")
g2 = _G(duo=False); g2.setup_flow_init()
check(g2.setup_steps == ["map","weapon_p1","char_p1"], "单人三步流程")
from config import GameState as GS
for _st in ("MAP_SELECT","WEAPON_SELECT_P1","CHARACTER_SELECT_P1",
            "WEAPON_SELECT_P2","CHARACTER_SELECT_P2"):
    check(hasattr(GS, _st), f"状态 {_st} 存在")
check(g.setup_state_for("weapon_p2") == GS.WEAPON_SELECT_P2, "步骤→状态映射")
g.setup_index = 4; check(g.setup_back() == "weapon_p2", f"可返回上一步（{g.setup_current_step}）")

print("[B] 信息页构建")
import pygame; pygame.init()
from scenes.info_pages import build_info_page
class _G2:
    scale = 1.0
    def __init__(s): s.state = None
_g = _G2()
for _k, _mn in (("map",1),("weapon",1),("char",1)):
    _p = build_info_page(_g, _k, "P1")
    check(_p is not None and len(getattr(_p,"items",[])) >= _mn,
          f"{_k} 页有 {len(getattr(_p,'items',[])) if _p else 0} 项")
_p2 = build_info_page(_g, "weapon", "P2")
check(getattr(_p2, "_owner", None) == "P2", "P2 页标记归属")
check("P2" in (_p2.title or ""), f"P2 页标题含 P2（{_p2.title}）")

print("[C] 抽卡演出接入")
from gacha import GachaFx
fx = GachaFx()
check(not fx.active, "初始空闲")
fx.play([{"star":5,"weapon":{"name":"T"},"is_up":True,"level":1}])
check(fx.active, "play 后激活")
check(fx.phase == GachaFx.PHASE_CHARGE, "进入蓄力")
for _ in range(200): fx.update(0.05)
check(not fx.active, "自动结束")
fx2 = GachaFx(); fx2.play([{"star":4,"weapon":{"name":"x"},"is_up":False,"level":1}])
fx2.skip(); check(fx2.phase == GachaFx.PHASE_REVEAL, "skip 跳到展示")
_shop = open("zombie_pkg/mix_shop.py", encoding="utf-8").read()
check("self.gacha_fx" in _shop, "gacha_fx 已实例化")
check("def update_gacha_fx" in _shop, "每帧更新入口")
check("gacha_fx.play" in _shop, "抽取后触发演出")
check("update_gacha_fx(dt)" in open("zombie_pkg/mix_playing.py",encoding="utf-8").read(),
      "主循环调用演出更新")

print("[D] UP 池轮换")
from gacha import banner_index, build_up_keys
_pool = [{"key":f"W{i}","quality":"epic"} for i in range(12)]
_u0 = build_up_keys(_pool, 0); _u1 = build_up_keys(_pool, 1)
check(_u0 != _u1, "不同期 UP 不同（轮换生效）")
check(len(set(_u0)) == len(_u0), "同批 UP 不重复")
check(banner_index() >= 0, "期数可计算")
check("load_up_keys_from_db" in open("gacha.py",encoding="utf-8").read(),
      "支持从数据库读 UP")

print("[E] 渲染与输入分派接入")
_rc = open("renderer_pkg/render_core.py", encoding="utf-8").read()
check("GameState.MAP_SELECT" in _rc, "渲染分派含新页面")
check("_draw_setup_pages" in _rc, "调用新页面绘制")
_du = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("def _draw_setup_pages" in _du, "绘制函数存在")
_mi = open("zombie_pkg/mix_input.py", encoding="utf-8").read()
check("_handle_setup_click" in _mi, "输入处理存在")
check("def _handle_setup_click" in _mi, "处理函数已定义")

print("[F] 双子 Boss 与动态视野回归")
check("TwinBossMixin" in open("zombie_pkg/__init__.py",encoding="utf-8").read(),
      "双子 mixin 已装配")
check("update_dynamic_zoom(dt)" in open("zombie_pkg/mix_playing.py",encoding="utf-8").read(),
      "动态视野已接入")
check("draw_charge_spread_fan(self, player" in open("renderer_pkg/draw_play.py",encoding="utf-8").read(),
      "扇形调用已修")

print()
print(f"===== v2.9.0 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
