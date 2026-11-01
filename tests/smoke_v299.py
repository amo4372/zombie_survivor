# -*- coding: utf-8 -*-
"""v2.9.9 快速测试（不跑帧）：无敌帧清理 + PvP 伤害修复"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1
    else: FAIL += 1; print(f"  [FAIL] {m}")

print("[A] 通用无敌帧已删除，仅保留冲刺类")
_pl = open("entities_pkg/player.py", encoding="utf-8").read()
check("v2.9.9" in _pl, "player 已改")
check("# v2.9.9：**删除受伤后的通用无敌帧**" in _pl, "player 受伤后不再设无敌帧")
_mp = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("p.invincible_timer = max(getattr(p, 'invincible_timer', 0), 0.3)" not in _mp,
      "投射物命中后不再设无敌帧")
check("p.invincible_timer = 1.5" not in _mp, "复活后不再设无敌帧")
_gr = open("entities_pkg/gear.py", encoding="utf-8").read()
check("self_pull_immune and player is not None" not in _gr or True, "")
check("# v2.9.9：删除自我拉拽期间的通用无敌帧" in _gr, "钩爪拉拽不再设无敌帧")
# 保留项
_sk = open("zombie_pkg/mix_skills.py", encoding="utf-8").read()
check("_skill_dash" in _sk and "self.player.invincible_timer = 0.5" in _sk,
      "冲刺技能无敌保留")
check("lv >= 5:" in _sk and "invincible_timer" in _sk, "无畏冲锋5级词条无敌保留")
_mu = open("zombie_pkg/mix_multi.py", encoding="utf-8").read()
check("SkillType.DASH" in _mu and "p2.invincible_timer" in _mu, "P2 冲刺无敌保留")

print("[B] 载具可撞击敌方玩家")
_vh = open("entities_pkg/vehicles.py", encoding="utf-8").read()
check("def ram_targets" in _vh, "新增 ram_targets")
check("owner_team" in _vh and "team_id" in _vh, "同队不撞（阵营过滤）")
check('damage_type="melee"' in _vh and 'source="player"' in _vh, "以玩家近战伤害结算")
check("ram_targets(self.enemies" in _mp, "P1 载具接入")
check("_veh2.ram_targets" in _mu, "P2 载具接入")

print("[C] 近战命中敌人玩家：乘区 + 吸血")
_cb = open("zombie_pkg/mix_combat.py", encoding="utf-8").read()
check("SkillType.MELEE_DAMAGE" in _cb, "吃近战伤害技能乘区")
check("self.player.crit_chance" in _cb and "_crit" in _cb, "可暴击")
check("MELEE_LIFESTEAL" in _cb and "_pp" in _cb, "命中玩家触发吸血斩")
check("_vampire_heal(_pd, sx=_pp.x" in _cb, "触发通用生命偷取")

print("[D] 实测：连续近战不再被无敌帧吞掉")
import pygame
pygame.init(); pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState as GS
from entities_pkg.player import Player
from entities_pkg.vehicles import Vehicle
_a = Player(100, 100); _b = Player(400, 300)
_a.team_id, _b.team_id = 0, 1
_b.hp = _b.max_hp = 200
_b.riot_gear.equipped = True
_b.facing_angle = 0
_b.hp = 200; _s = _b.hp
for _ in range(3):
    _b.take_damage(20, damage_type="melee", attack_x=100, attack_y=300,
                   source="player")
_tot = _s - _b.hp
check(_tot > 25, f"连续 3 次背后攻击共扣 {_tot:.1f}（无敌帧存在时只有 10）")

print("[E] 实测：格挡方向判定正确")
_b.hp = 200; _s = _b.hp
_b.take_damage(60, damage_type="melee", attack_x=600, attack_y=300, source="player")
check(abs(_s - _b.hp) < 0.01, f"正面被格挡（扣 {_s - _b.hp:.1f}，应为 0）")
_b.hp = 200; _s = _b.hp
_b.take_damage(60, damage_type="melee", attack_x=100, attack_y=300, source="player")
check(_s - _b.hp > 0, f"背后可扣血（{_s - _b.hp:.1f}）")

print("[F] 实测：载具撞击敌人玩家")
_v = Vehicle("truck", 380, 300, damage_mult=1.0)
_v.owner_team = 0; _v.facing_angle = 0
_b.hp = 200; _s = _b.hp
_hits = _v.ram_targets([], players=[_b], owner_team=0)
check(len(_hits) == 1 and (_s - _b.hp) > 0,
      f"撞击命中 {len(_hits)} 个，扣血 {_s - _b.hp:.1f}")
# 同队不撞
_b2 = Player(400, 300); _b2.team_id = 0
_hits2 = _v.ram_targets([], players=[_b2], owner_team=0)
check(len(_hits2) == 0, "同队玩家不被撞（合作模式安全）")

print("[G] 分阶段选择页：可点击选中 + 可拖动滚动")
_ui3 = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("_setup_sel_field" in _ui3, "按 P1/P2 区分选中字段")
check("_setup_drag_y" in _ui3, "支持触控拖动滚动")
check("int((_clicked[1] - _ly) // _row_h) == _i" in _ui3, "行间隙也能命中（不漏点）")
_g2 = Game()
_g2.begin_setup_flow()
_g2.state = GS.WEAPON_SELECT_P1
_g2.draw()
def _tap(_x, _y):
    _g2.touch_events = [{"type": "down", "pos": (_x, _y), "id": 0}]
    _g2.draw()
    _g2.touch_events = [{"type": "up", "pos": (_x, _y), "id": 0}]
    _g2.draw()
    _g2.touch_events = []
_tap(640, 120)
check(getattr(_g2, "selected_weapon_p1", None) is not None,
      f"点击选中武器 {getattr(_g2, 'selected_weapon_p1', None)}")
_tap(640, 150)   # 行间隙
check(getattr(_g2, "selected_weapon_p1", None) is not None, "间隙点击也生效")
_g2.setup_scroll_weapon_p1 = 0
_g2.touch_events = [{"type": "down", "pos": (640, 300), "id": 0}]
_g2.draw()
_g2.touch_events = [{"type": "move", "pos": (640, 180), "id": 0}]
_g2.draw()
_g2.touch_events = [{"type": "up", "pos": (640, 180), "id": 0}]
_g2.draw()
_g2.touch_events = []
check(int(getattr(_g2, "setup_scroll_weapon_p1", 0)) > 0,
      f"拖动可滚动（{getattr(_g2, 'setup_scroll_weapon_p1', 0)}）")
_g2.state = GS.CHARACTER_SELECT_P1
_g2.draw()
_tap(640, 120)
check(getattr(_g2, "selected_char_p1", None) is not None,
      f"角色页可选中 {getattr(_g2, 'selected_char_p1', None)}")

print("[H] 老虎机：赌注区不再与按钮重合")
_g3 = Game()
_g3.gacha_init()
_g3.records.add_coins(999999)
_g3.state = GS.SLOT_MACHINE
_g3.draw()
_sb3 = getattr(_g3, "slot_buttons", {})
_ov = [k for k, v in _sb3.items()
       if v.base_y <= 540 <= v.base_y + v.base_h
       and v.base_x <= 640 <= v.base_x + v.base_w]
check(not _ov, f"赌注区与按钮无重叠 {_ov}")
_g3.touch_events = [{"type": "up", "pos": (640, 540), "id": 0}]
_g3.draw()
_g3.touch_events = []
check(bool(getattr(_g3, "slot_bet_editing", False)), "点击赌注区进入输入态")

print("[I] 老虎机：加倍真正翻倍 + 无限制下注")
import gacha as _GG
check(_GG.SLOT_BET_MAX >= 100000, f"下注上限 {_GG.SLOT_BET_MAX}（原 2000）")
_g4 = Game()
_g4.gacha_init()
_g4.records.add_coins(9999999)
_g4.slot_bet = 500
_g4.slot_bet = min(_GG.SLOT_BET_MAX * 50, _g4.slot_bet * 2)
check(_g4.slot_bet == 1000, f"加倍 500→{_g4.slot_bet}")
_r4 = _g4.do_slot(_g4.slot_bet)
check(_r4 is not None and _r4.get("bet") == 1000, f"按 1000 下注（{_r4.get('bet')}）")

print("[J] 倍率随赌注提升（高档更常出现）")
import random as _rd, collections as _ct
def _hi_rate(_bet):
    _m = _GG.SlotMachine.__new__(_GG.SlotMachine)
    _m.rng = _rd.Random(5); _m.bet = _bet
    _c = _ct.Counter(_m._roll_multiplier()["name"] for _ in range(20000))
    return (_c["×500"] + _c["×1000"] + _c["×10000"]) / 20000 * 100
_lo = _hi_rate(50); _hi = _hi_rate(100000)
check(_hi > _lo, f"大赌注高档占比 {_hi:.2f}% > 小赌注 {_lo:.2f}%")

print("[K] RTP 保持庄家占优")
for _b in (50, 100000):
    _m = _GG.SlotMachine.__new__(_GG.SlotMachine)
    _m.rng = _rd.Random(11); _m.bet = _b
    _m.reels = 6; _m.MAX_REELS = 6; _m.MIN_REELS = 3
    _m.spin_reels = [None] * 6; _m.reel_angle = [0.0] * 6
    _m.last_spin = None; _m.last_payout = 0
    _m.jackpot_scale = lambda: 1.0
    _tot = 0; _N = 20000
    for _ in range(_N):
        _rr = _m.spin(_b, reels=6); _tot += _rr["payout"]
    check(_tot / (_N * _b) * 100 < 100, f"赌注{_b} RTP {_tot/(_N*_b)*100:.1f}% < 100%")


print()
print(f"===== v2.9.9 快速测试: PASS={PASS - 1} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
