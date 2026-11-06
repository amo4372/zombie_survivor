#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.9 快速测试：抽取机制接入 + 双子 Boss 接入 + 购买移除"""
import os, sys, random
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, _ROOT)
PASS = FAIL = 0
def check(c, n):
    global PASS, FAIL
    if c: PASS += 1; print(f"  [PASS] {n}")
    else: FAIL += 1; print(f"  [FAIL] {n}")

print("[A] 编译")
import py_compile
for f in ("gacha.py","weapon_pool.py","twin_boss.py","zombie_pkg/mix_shop.py",
          "zombie_pkg/mix_twinboss.py","zombie_pkg/__init__.py",
          "zombie_pkg/mix_input.py","renderer_pkg/draw_ui.py",
          "renderer_pkg/draw_play.py","zombie_pkg/mix_playing.py",
          "zombie_pkg/game_core.py","config.py","renderer_pkg/render_core.py"):
    try: py_compile.compile(f, doraise=True)
    except Exception as e: check(False, f"编译 {f}: {e}")
check(FAIL == 0, "关键模块编译通过")

print("[B] 武器不再能直接购买")
from config import WeaponType
_shop = open("zombie_pkg/mix_shop.py", encoding="utf-8").read()
check('return "gacha_only"' in _shop, "equip_buy_weapon 返回 gacha_only")
check("军械库补给」抽取" in open("renderer_pkg/draw_ui.py", encoding="utf-8").read(),
      "UI 提示改为只能抽取")
check("需补给抽取" in open("renderer_pkg/draw_ui.py", encoding="utf-8").read(),
      "武器列表锁标记不再显示价格")

print("[C] 米哈游式保底机制")
from weapon_pool import build_pool
from gacha import (WeaponGacha, GachaBanner, QUALITY_LEGEND, QUALITY_EPIC,
                   LEGEND_HARD_PITY, LEGEND_PITY_START,
                   PITY_5_HARD, PITY_4_HARD, STAR_4, STAR_5, MAX_LEVEL)
pool = build_pool()
# 基础概率
qs = {}
for i in range(4000):
    g0 = WeaponGacha(pool, unlocked=set(), rng=random.Random(i))
    r = g0.draw_one(); qs[r["quality"]] = qs.get(r["quality"], 0) + 1
_l5 = qs.get(QUALITY_LEGEND, 0) / 40.0
_l4 = qs.get(QUALITY_EPIC, 0) / 40.0
check(0.2 <= _l5 <= 1.2, f"5★ 基础概率 ≈0.6%（实测 {_l5:.2f}%）")
check(3.5 <= _l4 <= 7.5, f"4★ 基础概率 ≈5.1%（实测 {_l4:.2f}%）")
# 硬保底
def run(seed):
    g0 = WeaponGacha(pool, unlocked=set(), rng=random.Random(seed))
    for pos in range(1, 300):
        if g0.pool_empty(): g0.unlocked = set()
        r = g0.draw_one()
        if r["quality"] == QUALITY_LEGEND: return pos
    return 999
def run_b(seed):
    g0 = GachaBanner(pool, up_keys=["AWP"], unlocked=set(), rng=random.Random(seed))
    for pos in range(1, 400):
        if g0.pool_empty(): g0.unlocked = set(); g0.levels = {}
        r = g0.draw_one()
        if r and int(r.get("star", 3)) >= STAR_5: return pos
    return 999
ps = [run_b(i) for i in range(400)]
check(all(p <= PITY_5_HARD for p in ps), f"全部在 {PITY_5_HARD} 抽 5★ 硬保底内（最晚 {max(ps)}）")
check(sum(ps)/len(ps) < PITY_5_HARD, f"平均出货 {sum(ps)/len(ps):.1f} 抽")
# 概率提升
g1 = WeaponGacha(pool)
gb = GachaBanner(pool, up_keys=["AWP"], unlocked=set(), rng=random.Random(1))
check(hasattr(gb, "pity_info"), "GachaBanner 提供保底进度接口")
_pi = gb.pity_info()
check("to_hard5" in _pi and "guarantee_up" in _pi, f"保底信息含硬保底与大保底（{_pi}）")
# 十连保底
bad = 0
for i in range(300):
    g2 = GachaBanner(pool, up_keys=["AWP"], unlocked=set(), rng=random.Random(i + 50000))
    if g2.pool_empty(): continue
    res = g2.draw_many(10)
    if res and not any(int(r.get("star", 3)) >= STAR_4 for r in res):
        bad += 1
check(bad == 0, f"十连必出 4★ 及以上（{bad}/300 例外）")
# 奖池仅出未解锁
g3 = WeaponGacha(pool, unlocked={"AWP", "PISTOL"})
check(all(w["key"] not in ("AWP", "PISTOL") for w in g3.available()),
      "奖池仅含未解锁武器")
check(WeaponGacha(pool, unlocked={w["key"] for w in pool}).pool_empty(),
      "全解锁后奖池为空")
# 重复抽中叠加等级（米哈游命座式）
_gb = GachaBanner(pool, unlocked={"AWP"}, rng=random.Random(3))
_gb.levels["AWP"] = 1
check(any(w["key"] == "AWP" for w in _gb.available()),
      "未满级的已解锁武器仍在池（可叠加等级）")
_gb.levels["AWP"] = MAX_LEVEL
check(not any(w["key"] == "AWP" for w in _gb.available()),
      f"满级 Lv.{MAX_LEVEL} 后退出奖池")

print("[D] 抽取真正接入游戏（解锁 + 持久化）")
import pygame; pygame.init()
from zombie_pkg.mix_shop import ShopMixin


class _MockRecords:
    def __init__(self):
        self.data = {"coins": 99999, "weapons": {}}
    def get_coins(self):
        return self.data["coins"]
    def spend_coins(self, n):
        self.data["coins"] -= n
        return True
    def is_weapon_owned(self, k):
        return k in self.data["weapons"]
    def unlock_weapon_purchase(self, k):
        self.data["weapons"][k] = 1
    def upgrade_weapon_purchase(self, k, lv):
        self.data["weapons"][k] = lv
    def get_weapon_level(self, k):
        return self.data["weapons"].get(k, 1)
    def add_coins(self, n):
        self.data["coins"] += int(n)
        return True


class _G(ShopMixin):
    def __init__(self):
        self.records = _MockRecords()
        self.gacha = None
        self.gacha_tip = ""
        self.gacha_result = []
        self.slot_bet = 50


g = _G()
g.gacha_init()
check(g.gacha is not None, "gacha 初始化成功")
check(type(g.gacha).__name__ == "GachaBanner", "使用米哈游式 GachaBanner")
check(len(g.gacha.available()) > 0, f"奖池非空（{len(g.gacha.available())} 把）")
_res = g.do_gacha(10)
check(len(_res) == 10, f"十连返回 10 件（{len(_res)}）")
_p0 = g.gacha.pity5
_o = g.do_gacha(1)
check(len(_o) == 1, f"单抽返回 1 件（{len(_o)}）")
check(g.gacha.pity5 - _p0 <= 1, f"单抽只消耗 1 抽（{g.gacha.pity5 - _p0}）")
check(all(g.records.is_weapon_owned((r.get("weapon") or {}).get("key")) for r in _res),
      "抽到的武器已写入存档")
# v2.8.9：未满级武器**仍留在池**（可重复抽取叠等级），只有满级才出池
_n_before = len(g.gacha.available())
# v2.9.10 同步：手雷/燃烧弹/烟雾弹改为投掷道具并移出奖池 → 32 变 29
check(_n_before == 29, "未解锁/未满级武器仍可再抽（叠等级）")
_k1 = (_res[0].get("weapon") or {}).get("key")
g.gacha.levels[_k1] = 5
check(not any((w.get("key") == _k1) for w in g.gacha.available()),
      f"满级武器退出奖池（{_k1}）")
# 保底计数跨会话保留
g._gacha_save()
_saved = g.records.data.get("gacha_state")
check(_saved is not None, "保底计数已写入存档")
_g2 = _G(); _g2.gacha_init()
_g2.gacha.from_save(_saved)
check(_g2.gacha.pity5 == g.gacha.pity5,
      f"保底计数跨会话保留（{_g2.gacha.pity5}）")
# 重复抽取叠加等级
_k0 = (_res[0].get("weapon") or {}).get("key")
_lv0 = g.records.get_weapon_level(_k0) if _k0 else 1
check(_lv0 >= 1, f"抽到武器已记录等级（{_k0} Lv.{_lv0}）")
check(_res[0].get("level", 1) >= 1, "结果带等级字段")
# 老虎机
g.records.data["coins"] = 99999
_sr = g.do_slot(500)
check(_sr is not None and "payout" in (_sr or {}), f"老虎机可下注并返回派彩")
check("kind" in (_sr or {}), f"老虎机返回结果（{_sr and _sr.get('kind')}）")

print("[E] 老虎机六轴接入")
_sm = getattr(g, "slot_machine", None)
check(_sm is not None, "slot_machine 初始化")
if _sm is not None:
    check(_sm.MAX_REELS == 6, "最多 6 轴")
    check(_sm.reels >= 3, "默认 3 轴起")
    _ok6, _ = _sm.unlock_reel(999999, 6)
    check(_ok6 and _sm.reels == 6, "可解锁到 6 轴")
    check(_sm.total_bet(100) == 600, "总注 = 单注 × 轴数")

print()
print(f"===== v2.8.9 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
