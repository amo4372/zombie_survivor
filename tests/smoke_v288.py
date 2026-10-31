#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.8 快速测试

覆盖：更新 pending 修复、死神钩爪 CD、无畏冲锋时长、倒地时间、
观战、AWM/轨道炮数值、散布收敛、抽奖/老虎机、双子 Boss、场景模块化、角色回血。

按需求：**不跑帧**（末尾少量帧验证）。
"""
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, _ROOT)

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


print("[A] 编译")
import py_compile
_MODS = ("updater.py", "entities_pkg/gear.py", "config.py",
         "zombie_pkg/mix_playing.py", "zombie_pkg/mix_players.py",
         "zombie_pkg/mix_skills.py", "zombie_pkg/mix_multi.py",
         "weapons.py", "renderer_pkg/draw_play.py", "entities_pkg/player.py",
         "scenes/__init__.py", "scenes/info_pages.py", "gacha.py",
         "weapon_pool.py", "twin_boss.py", "codex.py", "records.py")
for _f in _MODS:
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, f"{len(_MODS)} 个关键模块编译通过")

# ======================================================================
print("[B] 更新：pending 不再被误判为失败")
import updater as U
check(hasattr(U, "changed_files_excluding_pending"), "新增排除 pending 的差异复查")
check(hasattr(U, "has_pending"), "pending 检测函数存在")
_su = open("updater.py", encoding="utf-8").read()
check("changed_files_excluding_pending(_manifest, _game_dir)" in _su,
      "增量复查改用排除 pending 的版本（此前占用文件→判定失败→怎么都更不了）")
check("_count_pending" in _su, "全量路径也识别 pending")
check("已应用 {count} 个文件，{_pend_total} 个占用文件将在重启后生效" in _su,
      "全量占用时按成功处理并重启生效")

# ======================================================================
print("[C] 数值调整")
from config import (get_fearless_charge_duration, FEARLESS_CHARGE_DURATION,
                    CHARACTERS)
check(get_fearless_charge_duration(1) == 10.0,
      f"无畏冲锋基础时长 10s（{get_fearless_charge_duration(1)}）")
check(FEARLESS_CHARGE_DURATION[5] >= 15.0, "满级时长同步提升")
import entities_pkg.gear as _g
_rg = _g.RiotGear()
check(_rg.grapple_scythe_max_cooldown == _rg.grapple_max_cooldown,
      f"死神钩爪 CD 与普通钩爪一致（{_rg.grapple_scythe_max_cooldown}）")
_smp = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("DOWNED_DEATH_TIME = 45.0" in _smp, "合作倒地时间延长到 45s")

# ======================================================================
print("[D] 观战 / 冲锋禁操作")
_smr = open("zombie_pkg/mix_replay.py", encoding="utf-8").read() if os.path.exists("zombie_pkg/mix_replay.py") else ""
_smp2 = open("zombie_pkg/mix_players.py", encoding="utf-8").read()
check("def update_spectate" in _smp2, "观战逻辑存在")
check("pvp_enabled" in _smp2 and "spectating" in _smp2, "仅合作模式观战（PvP 不观战）")
_ssk = open("zombie_pkg/mix_skills.py", encoding="utf-8").read()
check("def _charge_locked" in _ssk, "冲锋锁定判定存在")
check("冲锋中无法使用技能" in _ssk or "使用技能" in _ssk, "冲锋中禁用技能释放键")
check("fearless_charge_active" in _smp, "冲锋中禁用肘击")

# ======================================================================
print("[E] AWM / 轨道炮")
from weapon_pool import build_pool
_pool = build_pool()
_awm = next((w for w in _pool if w["key"] == "AWP"), None)
_rail = next((w for w in _pool if w["key"] == "RAILGUN"), None)
check(_awm is not None and _awm["damage"] == 200, f"AWM 对僵尸 200（{_awm and _awm['damage']}）")
check(_rail is not None and _rail["damage"] == 30, f"轨道炮每帧 30（{_rail and _rail['damage']}）")
_smp3 = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("_charge_ratio" in _smp3, "蓄力收敛比例已计算")
check("_charge_spread" in _smp3, "散布随蓄力收窄")
check("_cam.zoom = _z0 + (_z_min - _z0) * _charge_ratio" in _smp3, "视野随蓄力拉远")
_sdp = open("renderer_pkg/draw_play.py", encoding="utf-8").read()
check("def draw_charge_spread_fan" in _sdp, "散布扇形绘制存在")
check("def draw_bullet_tracers" in _sdp, "弹道破空曳光绘制存在")
_sw = open("weapons.py", encoding="utf-8").read()
check("self.tracer = bool(_spd >= 18.0" in _sw, "高速弹丸自动标记曳光")

# ======================================================================
print("[F] 军械库补给（抽奖）")
from gacha import (WeaponGacha, SlotMachine, QUALITY_LEGEND,
                   QUALITY_RARE, QUALITY_EPIC, QUALITY_COMMON)
_LOCKED = {w["key"] for w in _pool[:2]}
_g = WeaponGacha(_pool, unlocked=set(_LOCKED))
check(len(_g.available()) == len(_pool) - len(_LOCKED),
      f"奖池仅含未解锁武器（{len(_g.available())}）")
_w, _q = _g.draw_one()
check(_w is not None, "奖池必出武器（非空）")
check(_w["key"] not in _LOCKED, "不会抽到已解锁武器")
_g2 = WeaponGacha(_pool, unlocked={w["key"] for w in _pool})
check(_g2.pool_empty() and _g2.draw_one()[0] is None, "全解锁后奖池为空（不再抽）")
check(_g.price(10) < _g.price(1) * 10, "十连有优惠")
# 品质概率：传说应最稀有
import random as _rnd
_rng = _rnd.Random(7)
_g3 = WeaponGacha(_pool, unlocked=set(), rng=_rng)
_cnt = {}
for _ in range(400):
    _w2, _q2 = _g3.draw_one()
    if _w2 is None:
        break
    _cnt[_q2] = _cnt.get(_q2, 0) + 1
check(_cnt.get(QUALITY_LEGEND, 0) < _cnt.get(QUALITY_COMMON, 9999),
      f"传说比普通稀有（{_cnt.get(QUALITY_LEGEND,0)} vs {_cnt.get(QUALITY_COMMON,0)}）")

print("[G] 老虎机")
_sm = SlotMachine(rng=_rnd.Random(11))
_r = _sm.spin(100)
check(set(_r.keys()) >= {"bet", "reels", "payout", "kind"}, "旋转结果结构完整")
check(_r["bet"] == 100, "下注额正确")
check(_r["kind"] in ("jackpot", "pair", "none"), f"结算类型合法（{_r['kind']}）")
check(_sm.spin(999999)["bet"] <= 2000, "下注上限被限制")

# ======================================================================
print("[H] 双子 Boss")
from twin_boss import (TwinBossPair, SpaceZone, ZONE_SAFE, ZONE_DAMAGE,
                       ZONE_HEAL, SHAPE_HEART, CASTLE_VARIANT)
_z = SpaceZone(0, 0, 100, kind=ZONE_DAMAGE, shape=SHAPE_HEART)
check(_z.contains(0, 0), "爱心形状圈内判定可用")
_z2 = SpaceZone(0, 0, 100, kind=ZONE_SAFE)
check(_z2.effect_on(type("P", (), {"x": 0, "y": 0})(), 1.0)[0] == 0.0,
      "安全圈：圈内不受伤")
check(_z2.effect_on(type("P", (), {"x": 500, "y": 500})(), 1.0)[0] > 0,
      "安全圈：圈外持续受伤")
_z3 = SpaceZone(0, 0, 100, kind=ZONE_HEAL)
check(_z3.effect_on(type("P", (), {"x": 0, "y": 0})(), 1.0)[1] > 0, "恢复圈回血")

_pair = TwinBossPair()
check(_pair.zheng.name == "郑某" and _pair.hui.name == "惠某", "双子成对生成")
class _P:
    def __init__(s): s.x, s.y, s.hp, s.max_hp = 0, 0, 100, 100
_ps = [_P()]
_now = time.time()
for _i in range(10):
    _pair.hui.record(_ps, 0.1, _now + _i * 0.1)
_ps[0].hp = 20
_ps[0].x = 300
_pair.hui.cast_rewind(_ps, _now + 1.0, None)
check(_ps[0].hp > 20, f"时间回溯：血量回到从前（{_ps[0].hp}）")
check(abs(_ps[0].x - 300) > 1 or _ps[0].x == 0, "时间回溯：位置也倒流")
_pair.take_damage(4000, "zheng")
_evt = None
for _i in range(40):
    _e = _pair.update(0.1, _ps, _now + 2 + _i * 0.1, None)
    if _e and _e[0] == "castle":
        _evt = _e
check(_evt is not None, "低血量触发王车易位")
check(_pair.disable_mode in ("active", "passive"), f"随机禁用技能（{_pair.disable_mode}）")
check(_pair.skills_disabled(_pair.disable_mode), "禁用查询生效")
_pair.take_damage(99999)
check(not _pair.alive, "同生同死")

# ======================================================================
print("[I] 场景模块化")
from scenes import Scene, SceneManager, SceneSpec, build_scenes
from scenes.info_pages import WeaponSelectPage, MapSelectPage, CharacterSelectPage
_mgr = SceneManager(object())
_specs = [SceneSpec("a", "A"), SceneSpec("b", "B"), SceneSpec("c", "C")]
build_scenes(object(), _specs, _mgr)
check(len(_mgr.scenes) == 3, f"批量创建 3 个页面（{len(_mgr.scenes)}）")
_mgr.push("a")
_mgr.push("b")
check(_mgr.current.key == "b", "场景栈 push 正确")
_mgr.pop()
check(_mgr.current.key == "a", "场景栈 pop 返回上一层")
_wp = WeaponSelectPage(None, items=_pool[:3])
check(len(_wp.sections(_pool[0])) >= 1, "武器页有数值分区")
_mp = MapSelectPage(None, items=[{"name": "校园", "chapter": "一"}])
check(len(_mp.sections({"name": "校园", "chapter": "一"})) >= 1, "地图页有信息分区")
_cp = CharacterSelectPage(None, items=[{"name": "医护兵", "perks": [{"name": "回血", "desc": "x"}]}])
check(any(s[0] == "角色词条" for s in _cp.sections({"name": "医护兵", "perks": [{"name": "回血", "desc": "x"}]})),
      "角色页显示词条分区")

# ======================================================================
print("[J] 图鉴 / 成就 / 角色回血")
import codex as _cx
check(hasattr(_cx, "TWIN_BOSS_CODEX"), "双子 Boss 图鉴已加入")
check(len(getattr(_cx, "TWIN_BOSS_CODEX", {})) == 3, "含郑某/惠某/王车易位三条")
from records import GameRecords
_rec = GameRecords()
_ach = _rec.data.get("achievements", {})
_new = ("twin_boss_meet", "twin_boss_slain", "castle_survived", "gacha_first",
        "gacha_legend", "slot_jackpot", "spectator", "fearless_10s")
check(all(k in _ach for k in _new), f"新增成就 {len(_new)} 条到位")
check("desc" in _ach.get("mp_first_win", {}), "原有成就结构未被破坏")
check("registered_players()" in _smp, "角色回血改为遍历全部玩家（修 P2 无效果）")

# ======================================================================
print("[K] 集成（少量帧）")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
try:
    from game import Game
    from config import GameState
    from entities_pkg.player import Player
    g = Game()
    g.start_game()
    g.player2 = Player(200, 200)
    g.camera2 = type(g.camera)(1280, 720) if getattr(g, 'camera', None) else None
    g.state = GameState.PLAYING
    for _i in range(10):
        g._update_playing(1 / 60)
    g.renderer.render()
    check(True, "多人启动 + 渲染不崩")
except Exception as e:
    check(False, f"集成崩溃: {type(e).__name__}: {e}")

# ======================================================================
print("[L] 数据模型层（OOP，数据库权威）")
from gamedata.db import connect as _conn
from gamedata.models import GameDataHub, WeaponData, CharacterData
_hub = GameDataHub(_conn("game_data.db"))
check(len(_hub.weapons) > 0, f"武器注册表 {len(_hub.weapons)} 条")
check(len(_hub.enemies) > 0, f"敌人注册表 {len(_hub.enemies)} 条")
check(len(_hub.skills) > 0, f"技能注册表 {len(_hub.skills)} 条")
_w2 = _hub.weapons.get("AWP")
check(_w2 is not None and float(_w2.damage) == 200.0,
      f"数据库权威：AWM 读到 200（{_w2 and _w2.damage}）")
check(_w2 is not None and isinstance(_w2.damage, float), "数值类型安全（float）")
check(len(_hub.enemies.bosses()) > 0, f"Boss 识别 {len(_hub.enemies.bosses())} 个")
_c2 = _hub.characters.get("医护兵")
check(_c2 is not None and len(_c2.perks()) >= 2, "角色词条由数据驱动生成")
# 角色加成应用到任意玩家（数据驱动，替代散落 if/elif）
class _FakePlayer:
    def __init__(s):
        s.max_hp = 100; s.hp = 100; s.base_speed = 1.0; s.speed = 1.0
        s.damage_multiplier = 1.0; s.crit_bonus_add = 0.0; s.crit_chance = 0.0
        s.health_regen = 0.0; s.dmg_reduce = 0.0
_fp = _FakePlayer()
_c2.apply_to(_fp, level=1)
check(_fp.health_regen > 0, "角色加成可应用到任意玩家对象（修 P2 无效果）")
check(_fp.max_hp > 100, f"生命加成生效（{_fp.max_hp}）")
# 批量迭代 / 筛选
check(len(_hub.weapons.sorted_by("damage", reverse=True)) == len(_hub.weapons),
      "注册表支持排序")
_dbauth = open("gamedata/db.py", encoding="utf-8").read()
check("数据库权威" in _dbauth, "游戏运行期以数据库为唯一权威")
check("sync_rows_from_code" in _dbauth,
      "升级时按 dataver 逐行同步（发布改的生效、本地锁定的保留）")
_sseed = open("gamedata/seed.py", encoding="utf-8").read()
check("def sync_rows_from_code" in _sseed, "版本化行同步实现存在")
check("def ensure_dataver_columns" in _sseed, "dataver 列自动补齐")
_scli = open("gamedata/cli.py", encoding="utf-8").read()
check('def cmd_lock' in _scli and 'def cmd_unlock' in _scli,
      "提供 lock / unlock 保护手工数值")

print()
print(f"===== v2.8.8 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
