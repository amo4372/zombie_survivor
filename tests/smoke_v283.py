#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.3 快速测试：CACHE_DIR 修复 + 数据/行为分离（SQLite）+ 文件结构整理

按需求：**不跑帧**（仅末尾跑极少量帧验证集成）。
"""
import os
import sys
import tempfile

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
for _f in ("updater.py", "config.py", "weapons.py", "runes.py", "main.py",
           "gamedata/__init__.py", "gamedata/db.py", "gamedata/schema.py",
           "gamedata/defaults.py", "gamedata/seed.py", "gamedata/cli.py",
           "entities_pkg/enemy.py", "build_release.py"):
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, "关键模块编译通过")

# ======================================================================
print("[B] NameError: CACHE_DIR 未定义")
_src = open("updater.py", encoding="utf-8").read()
import re as _re
_bad = []
for _ln in _src.splitlines():
    if _ln.strip().startswith("#"):
        continue
    for _m in _re.finditer(r"\bCACHE_DIR\b", _ln):
        if _ln[:_m.start()].rstrip().endswith("UPDATE_"):
            continue
        if "_UPDATE_CACHE_DIR" in _ln:
            continue
        _bad.append(_ln.strip()[:60])
check(not _bad, f"不再引用未定义的 CACHE_DIR（裸引用 {len(_bad)} 处）")
check("os.path.join(game_dir, UPDATE_CACHE_DIR, \"incremental\")" in _src,
      "改用正确的 UPDATE_CACHE_DIR")
import updater
check(hasattr(updater, "UPDATE_CACHE_DIR"), "UPDATE_CACHE_DIR 常量存在")
check(not hasattr(updater, "CACHE_DIR"), "CACHE_DIR 确实不存在（故此前报错）")
# 实跑增量下载（用不存在的版本，验证不会因 NameError 崩，只返回 None）
_r = updater.download_incremental_files(["zzz_no_such.py"], "v0.0.0",
                                        tempfile.mkdtemp())
check(_r is None, "download_incremental_files 不再抛 NameError（失败返回 None）")

# ======================================================================
print("[C] 数据/行为分离：SQLite")
from gamedata import db, db_path, DB_FILENAME
from gamedata import defaults as D

check(os.path.exists(db_path()), f"数据库已生成 {DB_FILENAME}")
_st = db.status()
check(_st["available"], "数据库可用")
check(_st["tables"]["weapons"] > 0, f"武器表 {_st['tables']['weapons']} 行")
check(_st["tables"]["enemies"] > 0, f"敌人表 {_st['tables']['enemies']} 行")
check(_st["tables"]["runes"] > 0, f"符文表 {_st['tables']['runes']} 行")
check(_st["tables"]["difficulty"] == 4, "难度表 4 行")
check(_st["tables"]["tuning"] > 0, f"调参表 {_st['tables']['tuning']} 行")

# 抽取（纯 AST，不 import 游戏模块）
_w = D.extract_weapons()
_e = D.extract_enemies()
_r2 = D.extract_runes()
check(len(_w) >= 20, f"从代码抽取武器 {len(_w)} 种")
check(len(_e) >= 20, f"从代码抽取敌人 {len(_e)} 种")
check(len(_r2) >= 5, f"从代码抽取符文 {len(_r2)} 种")
check("PISTOL" in _w and _w["PISTOL"].get("name") == "手枪", "武器抽取内容正确")

# 读取
_p = db.weapon("PISTOL")
check(_p.get("name") == "手枪", f"武器读取: {_p.get('name')}")
check(db.enemy("ZOMBIE_NORMAL", {}).get("hp") is not None, "敌人读取含 hp")
check(db.difficulty("地狱").get("enemy_hp_mult") == 2.2, "难度读取正确")
check(db.tuning("player_base_hp") == 100.0, "调参读取正确")
check(db.tuning("不存在的键", 42) == 42, "调参缺失回退默认值")

# 兜底：数据库损坏时不崩
_bad = os.path.join(tempfile.mkdtemp(), "bad.db")
with open(_bad, "wb") as _f:
    _f.write(b"\x00\x01not a database" * 50)
from gamedata.db import GameDatabase
_gdb = GameDatabase(_bad)
check(_gdb.weapon("PISTOL", {"damage": 17}).get("damage") == 17,
      "数据库损坏时回退代码默认值（不崩）")
check(_gdb.difficulty("普通").get("enemy_hp_mult") == 1.0, "损坏时难度也回退")

# ======================================================================
print("[D] 代码真的从数据库读")
import config, runes
check(len(config.DIFFICULTY_CONFIG) == 4, "难度配置已接入")
_wc = runes.RUNE_CONFIG
check(len(_wc) >= 5, f"符文配置已接入（{len(_wc)}）")
_src_w = open("weapons.py", encoding="utf-8").read()
check("_gdb.weapon(self.weapon_type" in _src_w, "武器代码读取数据库")
_src_e = open("entities_pkg/enemy.py", encoding="utf-8").read()
check("_gdb.enemy(self.enemy_type" in _src_e, "敌人代码读取数据库")
_src_c = open("config.py", encoding="utf-8").read()
check("_gdb.difficulty(" in _src_c, "难度配置读取数据库")

# 改库 → 立即生效
from gamedata.db import connect
_c = connect(db_path())
_c.execute("UPDATE weapons SET damage=? WHERE key='PISTOL'", (555,))
_c.commit()
_c.close()
import importlib
import weapons as _wm
importlib.reload(_wm)
_wobj = _wm.Weapon(config.WeaponType.PISTOL)
check(_wobj.damage == 555, f"改数据库后武器伤害生效（{_wobj.damage}）")
_c = connect(db_path()); _c.execute("UPDATE weapons SET damage=17 WHERE key='PISTOL'"); _c.commit(); _c.close()

# ======================================================================
print("[E] 数据库不被更新覆盖")
_src_u = open("updater.py", encoding="utf-8").read()
check('"game_data.db"' in _src_u, "数据库列入 updater 用户数据（更新不覆盖）")
_src_b = open("build_release.py", encoding="utf-8").read()
check('"game_data.db"' in _src_b, "数据库不进发布包（不会覆盖玩家调好的数值）")
check('"gamedata"' in _src_b, "gamedata 包已加入打包白名单")

# ======================================================================
print("[F] 文件结构整理")
check(os.path.isdir("gamedata"), "新增 gamedata/ 数据包")
for _f in ("__init__.py", "db.py", "schema.py", "defaults.py", "seed.py", "cli.py"):
    check(os.path.exists(os.path.join("gamedata", _f)), f"gamedata/{_f} 存在")
_n_root = len([f for f in os.listdir(_ROOT) if f.endswith(".py")])
check(_n_root <= 28, f"根目录 .py 文件数收敛到 {_n_root}")
check(not os.path.exists(os.path.join(_ROOT, "smoke_v282.py")),
      "测试脚本已移入 tests/")
check(os.path.exists(os.path.join(_ROOT, "tools", "generate_music.py")),
      "开发工具已移入 tools/")

# ======================================================================
print("[G] 集成（少量帧）")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState
g = Game()
try:
    g.start_game()
    g.state = GameState.PLAYING
    for _i in range(5):
        g._update_playing(1 / 60)
    check(True, "游戏启动 + 5 帧不崩")
except Exception as e:
    check(False, f"启动崩溃: {e}")
check(g.player is not None, "玩家已创建")

print()
print(f"===== v2.8.3 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
