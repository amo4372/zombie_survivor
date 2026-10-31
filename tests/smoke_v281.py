#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.1 快速测试：三处崩溃 + 增量更新 + 争分夺秒合作模式

按需求：**不跑帧**（仅最后两个用例各跑极少量帧验证集成）。
"""
import os
import sys

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
for _f in ("updater.py", "build_release.py", "zombie_pkg/mix_playing.py",
           "zombie_pkg/mix_effects.py", "zombie_pkg/game_core.py", "replay.py"):
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, "关键模块编译通过")

# ======================================================================
print("[B] KeyError: 'damage_timer'")
_src = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check('"radius": 120, "timer": 5.0, "damage_timer": 0.0' in _src,
      "向某烟雾弹区域补上 damage_timer 字段")
_srce = open("zombie_pkg/mix_effects.py", encoding="utf-8").read()
check('_zone.get("damage_timer", 0.0)' in _srce or 'zone.get("damage_timer", 0.0)' in _srce,
      "区域更新用 .get 兜底（任何缺字段区域都不再崩）")

# 实跑一遍：缺字段的 zone 不应抛异常
import zombie_pkg.mix_effects as ME


class _G(ME.EffectsMixin):
    def __init__(self):
        self.fire_zones = []
        self.smoke_zones = []
        self.enemies = []
        self.particles = _StubParticles()

    def _alive_players(self):
        return []


class _StubParticles:
    def spawn(self, *a, **k):
        pass

    def spawn_explosion(self, *a, **k):
        pass

    def update(self, dt):
        pass


_g = _G()
_g.smoke_zones.append({"x": 0, "y": 0, "radius": 120, "timer": 5.0})  # 缺 damage_timer
try:
    _g._update_smoke_zones(0.1)
    check(True, "缺 damage_timer 的烟雾区域更新不再抛 KeyError")
except KeyError as e:
    check(False, f"仍抛 KeyError: {e}")
_g.fire_zones.append({"x": 0, "y": 0, "radius": 100, "timer": 5.0})   # 缺 damage_timer
try:
    _g._update_fire_zones(0.1)
    check(True, "缺 damage_timer 的燃烧区域更新不再抛 KeyError")
except KeyError as e:
    check(False, f"仍抛 KeyError: {e}")

# ======================================================================
print("[C] NoneType object has no attribute 'update'（防御）")
_src2 = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("if getattr(self, 'world', None) is not None:\n            self.world.update" in _src2
      or "getattr(self, 'world', None) is not None" in _src2, "world.update 有 None 防御")
check("getattr(self, 'horde_manager', None) is not None" in _src2,
      "horde_manager.update 有 None 防御")
check("if getattr(self, 'particles', None) is not None:\n            self.particles.update" in _src2,
      "particles.update 有 None 防御")

# ======================================================================
print("[D] ModuleNotFoundError: No module named 'replay'")
_br = open("build_release.py", encoding="utf-8").read()
check('"replay.py"' in _br, "replay.py 已加入发布包必需文件清单")
check(os.path.exists("replay.py"), "replay.py 存在于工程根目录")
import replay
check(hasattr(replay, "ReplayRecorder") and hasattr(replay, "load_replay"),
      "replay 模块可正常导入")

# ======================================================================
print("[E] 增量更新")
import updater
check(hasattr(updater, "try_incremental_update"), "增量更新入口存在")
check(hasattr(updater, "fetch_update_manifest"), "远端清单获取存在")
check(hasattr(updater, "compute_changed_files"), "本地差异比对存在")
check(hasattr(updater, "download_incremental_files"), "逐文件下载存在")


class _FakeManifest:
    pass


_gd = os.path.dirname(os.path.abspath("updater.py"))
# 用真实文件验证比对：version.txt 的 md5 与"远端"一致 → 无需下载
_m = {"version.txt": {"md5": updater._compute_md5("version.txt"), "size": 1},
      "replay.py": {"md5": updater._compute_md5("replay.py"), "size": 1},
      "no_such_file_zz.py": {"md5": "0" * 32, "size": 1}}
_need = updater.compute_changed_files(_m, _gd)
check(_need == ["no_such_file_zz.py"], f"只挑出真正变化/缺失的文件（{_need}）")
# 用户数据不参与比对
_m2 = {"config.json": {"md5": "x"}}
check(updater.compute_changed_files(_m2, _gd) == [], "用户数据文件不参与更新比对")
_src3 = open("updater.py", encoding="utf-8").read()
check("增量更新不可用，改为下载完整更新包" in _src3, "增量失败自动回退全量包")

# ======================================================================
print("[F] 争分夺秒 + 合作模式：不再开局即结束")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game, GameState
from config import GameMode

g = Game()
g.config.game_mode = GameMode.TIMED
g.config.pvp_enabled = False          # 合作模式
g.multiplayer_mode = "same_screen"
g.start_game()
g.state = GameState.PLAYING
_p2 = g.ensure_player("P2")
_p2.team_id = 0                       # 与 P1 同阵营
check(g.player.team_id == _p2.team_id, "合作模式：双方同阵营")
_r = g._check_round_end(1 / 60)
check(_r is None, f"同阵营合作模式不判阵营胜利（返回 {_r}）")
_wt_before = getattr(g, 'victory_team', None)
for _i in range(12):
    g.player.hp = g.player.max_hp
    _p2.hp = _p2.max_hp
    g.player.alive = _p2.alive = True
    g.update(1 / 60)
    if g.state != GameState.PLAYING:
        break
check(g.state == GameState.PLAYING, f"合作争分夺秒保持游玩中（{g.state}）")

# PvP 异阵营仍应能判胜负
g2 = Game()
g2.config.game_mode = GameMode.ENDLESS
g2.config.pvp_enabled = True
g2.multiplayer_mode = "same_screen"
g2.start_game()
g2.state = GameState.PLAYING
_q2 = g2.ensure_player("P2")
_q2.team_id = 1
g2.player.team_id = 0
_q2.alive = False                      # 敌方全灭
check(g2._check_round_end(1 / 60) == 0, "PvP 异阵营仍正确判定胜负")

print()
print(f"===== v2.8.1 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
