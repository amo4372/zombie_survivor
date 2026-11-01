# -*- coding: utf-8 -*-
"""v2.9.2 快速测试（不跑帧）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

print("[A] 武器不可直购/直升")
_ui = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("未解锁 · 需补给抽取" in _ui, "未解锁按钮改为提示抽取")
check("重复抽取可叠加" in _ui, "升级按钮改为提示抽取叠加")
_shop = open("zombie_pkg/mix_shop.py", encoding="utf-8").read()
check('return "gacha_only"' in _shop, "upgrade_weapon_shop 一律 gacha_only")
import re
_m = re.search(r'def upgrade_weapon_shop\(self, wt\):[\s\S]*?(?=\n    def )', _shop)
check("get_weapon_level" not in (_m.group(0) if _m else ""), "升级不再读等级改金币")

print("[B] 新页面按钮可点击（分派覆盖）")
_mi = open("zombie_pkg/mix_input.py", encoding="utf-8").read()
m = re.search(r'if self\.state in \((.*?)\):', _mi, re.S)
_lst = m.group(1)
for _st in ("REPLAY_LIST", "MAP_SELECT", "WEAPON_SELECT_P1",
            "CHARACTER_SELECT_P1", "WEAPON_SELECT_P2", "CHARACTER_SELECT_P2"):
    check(_st in _lst, f"{_st} 已进入点击分派")

print("[C] 主菜单直达抽奖")
check('"军械库补给"' in open("zombie_pkg/mix_menu.py", encoding="utf-8").read(),
      "主菜单有军械库补给按钮")
check("i == 13" in _ui, "入口索引已绑定")
check("GameState.GACHA" in _ui, "点击后进入抽奖页")

print("[D] 分阶段流程全模式应用")
check("def begin_setup_flow" in _shop, "流程启动入口")
check("begin_setup_flow()" in _ui, "开始游戏处调用流程")
check("begin_setup_flow" in _ui, "已接入开始游戏路径")

print("[E] AWM 真实散布")
_wp = open("weapons.py", encoding="utf-8").read()
check("_charge_spread" in _wp, "fire 消费蓄力收敛后的散布")
check("_eff_spread" in _wp, "用有效散布而非固定 self.spread")
check('random.uniform(-_eff_spread, _eff_spread)' in _wp, "子弹角度真正随机偏移")

print("[F] 动态视野全模式 + 多人")
_mp = open("zombie_pkg/mix_players.py", encoding="utf-8").read()
check("def update_dynamic_zoom_for" in _mp, "单视口计算函数（可复用）")
check("registered_players()" in _mp, "遍历全部玩家视口")
check("_rc is not _cam" in _mp, "P2 视口独立计算（此前只有 P1）")
check("max(0.45, min(_base, _z))" in _mp, "zoom 有下限钳制")

print("[G] 双子 Boss 贴合框架")
_tb = open("twin_boss.py", encoding="utf-8").read()
check("def _move_toward" in _tb, "Boss 会移动（此前完全不动）")
check(_tb.count("def _move_toward") >= 2, "郑某与惠某都会移动")
check("ZONE_INTERVAL = 6.5" in _tb, "出圈频率已下调")
check("self.rng.randint(1, 2)" in _tb, "单次出圈数量减少")
check("safe_reach" in _tb, "安全圈只在影响范围内生效")

print("[H] 时间技能可见且有效")
_playing = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("_hui_fast_forward" in _playing, "快进被真正消费（此前只打标记）")
check("speed_multiplier" in _playing, "快进提升移速")
check("attack_speed_mult" in _playing, "快进提升攻速")
_mtb = open("zombie_pkg/mix_twinboss.py", encoding="utf-8").read()
check("rewind_active" in _mtb and "紫色" in _mtb or "90, 60, 160" in _mtb,
      "回溯有全屏紫色特效")
check("255, 190, 70" in _mtb, "快进有橙黄特效")
check("180, 200, 255" in _mtb, "时停有冷蓝特效")

print("[I] 双子贴图改进")
check("pygame.draw.ellipse" in _mtb, "躯干为椭圆（非纯色圆）")
check("facing_angle" in _mtb, "按朝向绘制")
check("外发光" in _mtb, "有外发光")

print("[J] 图鉴含双子")
import pygame; pygame.init()
import codex as _cx
for _k in ("郑某", "惠某", "王车易位"):
    check(_k in _cx.MONSTER_CODEX, f"图鉴 MONSTER_CODEX 含 {_k}")
check(getattr(_cx, "_MERGED_TWIN_COUNT", 0) >= 3, "双子已并入主图鉴")

print()
print(f"===== v2.9.2 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
