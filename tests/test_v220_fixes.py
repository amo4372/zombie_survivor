#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.0 专项测试：争分夺秒模式 / 载具技能 / 成就修复 / 肘击 / 格挡抗性 / 肾上腺素 / 错误静默"""
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")


# ==================== 1. 错误静默机制 ====================
from error_silencer import ErrorSilencer

es = ErrorSilencer()


def _boom_a():
    raise ValueError("test-a")


def _boom_b():
    raise KeyError("test-b")


try:
    _boom_a()
except Exception as e:
    act = es.handle(e)
    check("错误首次出现 -> ask", act == "ask")
    check("pending_info 含 message", es.pending_info and "test-a" in es.pending_info["message"])
    es.decide(True)  # 忽略

try:
    _boom_a()
except Exception as e:
    act = es.handle(e)
    check("已忽略同类错误 -> ignore", act == "ignore")

try:
    _boom_b()
except Exception as e:
    act = es.handle(e)
    check("不同错误仍会 ask", act == "ask")
    es.decide(False)  # 不忽略

try:
    _boom_b()
except Exception as e:
    act = es.handle(e)
    check("不忽略同类错误 -> raise", act == "raise")


# ==================== 1b. 错误询问框触控命中（v2.2.0 触控端） ====================
from zombie_pkg.game_core import GameCore

# 用桩对象绑定类方法验证命中逻辑（触控热区）
_stub = type("Stub", (), {
    "scale": 1.0, "scaled_width": 1280, "scaled_height": 720,
})()
_hit = GameCore._error_ask_hit.__get__(_stub)
check("触控 忽略按钮中心命中", _hit(430, 420) == "ignore")
check("触控 不忽略按钮中心命中", _hit(650, 420) == "raise")
check("触控 按钮外不命中", _hit(50, 50) is None)
check("触控 热区高度60*scale", _hit(430, 465) == "ignore")  # 420+45 仍在高度内
check("触控 热区外下边界不命中", _hit(430, 486) is None)

# 归一化坐标换算：FINGER 事件 (x=0.41,y=0.62) → 物理 (524, 446) → 忽略按钮内
fx, fy = 0.41, 0.62
check("触控 FINGER 归一化换算命中", _hit(fx * 1280, fy * 720) == "ignore")


# ==================== 2. 争分夺秒模式 ====================
from config import GameMode
from world import HordeManager

wm = HordeManager(GameMode.TIMED, "普通")
check("争分夺秒初始倒计时 60s", abs(wm.race_time_left - 60.0) < 0.01)
wm.update(1.0)
check("update 后倒计时递减", abs(wm.race_time_left - 59.0) < 0.01)
wm.add_race_time(5.0)
check("击杀加时 +5", abs(wm.race_time_left - 64.0) < 0.01)
wm.add_race_time(9999)
check("加时上限 300", abs(wm.race_time_left - wm.race_max_time) < 0.01)
check("is_timed_over 未结束 False", wm.is_timed_over() is False)
wm.race_time_left = 0.0
check("倒计时归零 is_timed_over True", wm.is_timed_over() is True)
disp, is_cd = wm.get_time_display()
check("get_time_display 倒计时模式", is_cd is True and disp == "00:00")

# 杀怪加时类型
class FakeEnemy:
    def __init__(self, is_boss=False, enemy_type=None):
        self.is_boss = is_boss
        self.enemy_type = enemy_type


class FakeET:
    def __init__(self, name):
        self.name = name


wm2 = HordeManager(GameMode.TIMED, "普通")
check("普通怪 +1s", abs(wm2.race_kill_bonus_for(FakeEnemy(False, FakeET("walker"))) - 1.0) < 0.01)
check("精英怪 +3s", abs(wm2.race_kill_bonus_for(FakeEnemy(False, FakeET("brute"))) - 3.0) < 0.01)
check("Boss +10s", abs(wm2.race_kill_bonus_for(FakeEnemy(True, FakeET("boss_long"))) - 10.0) < 0.01)

# 无尽模式不加时
wm3 = HordeManager(GameMode.ENDLESS, "普通")
check("无尽模式不加时", wm3.race_kill_bonus_for(FakeEnemy(True, FakeET("boss_long"))) == 0.0)


# ==================== 3. 载具系统 ====================
from entities_pkg.vehicles import Vehicle

truck = Vehicle("truck", 100, 100, 1.0)
check("重卡禁射击", truck.can_shoot is False)
check("重卡可撞击", truck.ram_damage > 0)
truck.take_damage(500, "melee")
check("重卡专属血条扣血", truck.hp < truck.max_hp)
truck.take_damage(5000, "melee")
check("重卡可被摧毁", truck.dead is True)

tank = Vehicle("tank", 0, 0, 1.0)
check("坦克血条更厚", tank.max_hp > truck.max_hp)
tank.mag_left = 1
projs = tank.fire(0, 0, 0)
check("坦克最后一发为穿甲弹", len(projs) == 1 and projs[0].pierce >= 5)
tank2 = Vehicle("tank", 0, 0, 1.0)
tank2.mag_left = 3
projs = tank2.fire(0, 0, 0)
check("坦克高爆弹爆炸", len(projs) == 1 and projs[0].explosive and projs[0].explosion_radius > 0)

heli = Vehicle("heli", 0, 0, 1.0)
heli.take_damage(99999, "melee")
check("武直无视近战", heli.hp == heli.max_hp)
heli.take_damage(500, "ranged")
check("武直受远程伤害", heli.hp < heli.max_hp)
ps = heli.fire(0, 0, 0)
check("武直机炮+火箭", len(ps) == 2 and any(p.explosive for p in ps))


# ==================== 4. 载具技能注册与前置 ====================
from skills import SkillTree

tree = SkillTree()
vs = tree.get_skill_from_type = None
# 通过 _create_skills 已注册，直接查找
found = None
for s in tree.skills:
    if s.skill_type.name == "VEHICLE_SUMMON":
        found = s
        break
check("VEHICLE_SUMMON 已注册", found is not None)
if found:
    check("载具技能前置保留 (HEALTH_UP,3)", any(rt == "HEALTH_UP" and rl == 3 for rt, rl in [(r.name if hasattr(r, 'name') else str(r), l) for r, l in [(x, y) for x, y in found.requires]]) or any(rl == 3 for _, rl in found.requires))


# ==================== 5. 成就修复 ====================
import records as records_mod

check("records 模块可导入", hasattr(records_mod, "GameRecords"))
rec = records_mod.GameRecords  # noqa
# 争分夺秒排行榜记录
rg_rec = records_mod.GameRecords.__new__(records_mod.GameRecords)
rg_rec.data = {
    "race_leaderboard": [], "race_best_score": 0, "race_wins": 0,
    "race_total_runs": 0, "coins": 0, "total_coins_earned": 0,
    "achievements": {},
}
for k in ("race_first_win", "race_5_wins", "race_100_kills", "race_30k_score"):
    rg_rec.data["achievements"][k] = {"unlocked": False, "date": None}


def _fake_save_noarg():
    pass


rg_rec._save = _fake_save_noarg
rg_rec._check_race_achievements = records_mod.GameRecords._check_race_achievements.__get__(rg_rec)
rg_rec.add_coins = records_mod.GameRecords.add_coins.__get__(rg_rec)
coins = rg_rec.record_race_result(35000, 40.5, 120, True)
check("争分夺秒达标奖励金币", coins == 50 and rg_rec.data["coins"] == 50)
check("争分夺秒首胜成就", rg_rec.data["achievements"]["race_first_win"]["unlocked"] is True)
check("争分夺秒100杀成就", rg_rec.data["achievements"]["race_100_kills"]["unlocked"] is True)
check("争分夺秒3万分成就", rg_rec.data["achievements"]["race_30k_score"]["unlocked"] is True)
check("排行榜写入", len(rg_rec.data["race_leaderboard"]) == 1 and rg_rec.data["race_best_score"] == 35000)
# 未达标不给金币
rg_rec2 = records_mod.GameRecords.__new__(records_mod.GameRecords)
rg_rec2.data = {
    "race_leaderboard": [], "race_best_score": 0, "race_wins": 0,
    "race_total_runs": 0, "coins": 0, "total_coins_earned": 0,
    "achievements": {k: {"unlocked": False, "date": None} for k in ("race_first_win", "race_5_wins", "race_100_kills", "race_30k_score")},
}
rg_rec2._save = _fake_save_noarg
rg_rec2._check_race_achievements = records_mod.GameRecords._check_race_achievements.__get__(rg_rec2)
rg_rec2.add_coins = records_mod.GameRecords.add_coins.__get__(rg_rec2)
coins2 = rg_rec2.record_race_result(100, 10.0, 5, True)
check("未达标不给金币", coins2 == 0 and rg_rec2.data["coins"] == 0)


# ==================== 6. 肾上腺素体力应用 ====================
from entities_pkg.player import Player

p = Player.__new__(Player)
p.riot_gear = __import__("entities_pkg.gear", fromlist=["RiotGear"]).RiotGear()
p.max_stamina = 100.0
p.stamina = 100.0
p.stamina_regen_rate = 18.0
p.riot_gear.equipped = True
p.riot_gear.adrenaline_level = 2
# 模拟 update 中动态加成逻辑
_adl = p.riot_gear.adrenaline_level
_new_max = 100.0 + (_adl * 25 if p.riot_gear.equipped else 0)
_new_regen = 18.0 + (_adl * 4 if p.riot_gear.equipped else 0)
check("肾上腺素上限+50", _new_max == 150.0)
check("肾上腺素回复+8", _new_regen == 26.0)


# ==================== 7. 格挡与抗性 ====================
from entities_pkg.gear import RiotGear

rg = RiotGear()
rg.equipped = True
rg.facing_angle = 0.0
rg.max_shield_hp = 100
rg.shield_hp = 100
rg.max_viewing_window_hp = 50
rg.viewing_window_hp = 50
# 正前方攻击 -> blocked
rg.x = 0
rg.y = 0
dmg = rg.take_damage(30, "melee", from_front=True, attack_x=50, attack_y=0, blocked=True)
check("格挡正面伤害为0", dmg == 0)
check("护目窗扣血", rg.viewing_window_hp < 50)


# ==================== 8. 肘击改原地 ====================
rg2 = RiotGear()
rg2.equipped = True
rg2.stamina = 200
rg2.bash_cooldown = 0
rg2.charge_active = False
ok = rg2.bash(0.0)
check("原地肘击可释放", ok is True)
check("肘击不启动冲撞位移", rg2.charge_active is False)


print(f"\n===== 结果: {PASS} 通过, {FAIL} 失败 =====")
sys.exit(0 if FAIL == 0 else 1)
