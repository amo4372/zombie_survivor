#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.5 快速测试：数据库自动更新 + 数据编辑模式（后门）+ 数值分发合并

按需求：**不跑帧**（末尾少量帧验证集成）。
"""
import os
import shutil
import subprocess
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


_SNIP = ('import sys; sys.path.insert(0, ".")\n'
         'from gamedata import db\n'
         's = db.status()\n'
         'print("edit=%s|sync=%s|pistol=%s" % (s["edit_mode"], s["sync_state"],'
         ' "Y" if db.row("weapons","PISTOL") else "N"))\n')


def _run(argv=None, env=None):
    _e = dict(os.environ)
    if env:
        _e.update(env)
    _r = subprocess.run([sys.executable, "-c", _SNIP] + (argv or []),
                        capture_output=True, text=True, cwd=_ROOT, env=_e)
    return (_r.stdout or "").strip().splitlines()[-1] if _r.stdout.strip() else ""


print("[A] 编译")
import py_compile
for _f in ("gamedata/editmode.py", "gamedata/db.py", "gamedata/cli.py",
           "updater.py", "main.py", "renderer_pkg/render_core.py", "build_release.py"):
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, "关键模块编译通过")

from gamedata import editmode, db_path
from gamedata.db import connect, GameDatabase

# ======================================================================
print("[B] 编辑模式开关：三种方式")
check(editmode.from_argv(["main.py", "--no-db-sync"]), "命令行 --no-db-sync 生效")
check(editmode.from_argv(["main.py", "--db-edit"]), "命令行 --db-edit 生效")
check(not editmode.from_argv(["main.py"]), "无参数时不开启")
check(not editmode.enabled(), "默认关闭")

# ======================================================================
print("[C] 核心行为：编辑模式下不补种 / 正常模式补种")
_bak = tempfile.mkdtemp() + "/origin.db"
shutil.copy(db_path(), _bak)


def _del_pistol():
    _c = connect(db_path())
    _c.execute("DELETE FROM weapons WHERE key='PISTOL'")
    _c.commit()
    _c.close()


try:
    _del_pistol()
    _r = _run()
    check("pistol=Y" in _r, f"正常模式：删掉的行被补回（{_r}）")

    _del_pistol()
    _r = _run(["--no-db-sync"])
    check("pistol=N" in _r and "edit=True" in _r, f"命令行：不再补回（{_r}）")

    _del_pistol()
    _r = _run(env={"ZS_DB_NO_SYNC": "1"})
    check("pistol=N" in _r, f"环境变量：不再补回（{_r}）")

    editmode.set_enabled(True)
    _del_pistol()
    _r = _run()
    check("pistol=N" in _r, f"开关文件：不再补回（{_r}）")
    editmode.set_enabled(False)
    check(not editmode.from_file(), "开关可关闭")
finally:
    shutil.copy(_bak, db_path())
    print("  （已还原原数据库）")

# ======================================================================
print("[D] 版本感知：无需每次都写库")
_g = GameDatabase(db_path())
_s1 = _g.status()
check(_s1["sync_state"] in ("up_to_date", "synced", "seeded", "edit_mode"),
      f"同步状态可读（{_s1['sync_state']}）")
_g2 = GameDatabase(db_path())
check(_g2.status()["sync_state"] == "up_to_date",
      f"版本未变时跳过补种（{_g2.status()['sync_state']}）")
check(_g.meta("seed_version") is not None, f"seed_version 已写入（{_g.meta('seed_version')}）")

# ======================================================================
print("[E] 编辑模式下改数据仍热重载生效")
from gamedata.db import _coerce_color
_g3 = GameDatabase(db_path())
_c = connect(db_path())
_c.execute("UPDATE weapons SET damage=? WHERE key='PISTOL'", (888,))
_c.commit()
_c.close()
_g3.reload(force=True)
check(_g3.weapon("PISTOL").get("damage") == 888, "改库后重载读到新值")
_c = connect(db_path())
_c.execute("UPDATE weapons SET damage=17 WHERE key='PISTOL'")
_c.commit()
_c.close()

# ======================================================================
print("[F] 数值分发合并（只补不覆盖）")
_src = tempfile.mkdtemp() + "/src.db"
shutil.copy(db_path(), _src)
_c = connect(_src)
_c.execute("UPDATE weapons SET damage=777 WHERE key='PISTOL'")
_c.execute("DELETE FROM weapons WHERE key='SHOTGUN'")
_c.commit()
_c.close()
_c = connect(db_path())
_c.execute("DELETE FROM weapons WHERE key='RIFLE'")
_c.commit()
_c.close()
_ok, _n = GameDatabase(db_path()).merge_from_file(_src)
check(_ok, "合并执行成功")
_c = connect(db_path())
check(_c.execute("SELECT damage FROM weapons WHERE key='PISTOL'").fetchone()[0] == 17.0,
      "玩家改过的行不被覆盖（PISTOL 仍 17）")
check(_c.execute("SELECT COUNT(*) FROM weapons WHERE key='RIFLE'").fetchone()[0] == 1,
      "本地缺失的行被补回（RIFLE）")
_c.close()
# 还原
_c = connect(db_path())
_c.execute("UPDATE weapons SET damage=17 WHERE key='PISTOL'")
_c.commit()
_c.close()

# ======================================================================
print("[G] CLI 子命令")
_r = subprocess.run([sys.executable, "-m", "gamedata", "edit"],
                    capture_output=True, text=True, cwd=_ROOT)
check("数据编辑模式" in _r.stdout, "python -m gamedata edit 可用")
_r = subprocess.run([sys.executable, "-m", "gamedata", "diff"],
                    capture_output=True, text=True, cwd=_ROOT)
check("共" in _r.stdout, f"python -m gamedata diff 可用（{_r.stdout.strip()[:40]}）")

# ======================================================================
print("[H] 保护：开关文件不被更新覆盖/不进包")
_src_u = open("updater.py", encoding="utf-8").read()
check('".db_edit_mode"' in _src_u, "开关文件列入 updater 用户数据")
_src_b = open("build_release.py", encoding="utf-8").read()
check('".db_edit_mode"' in _src_b, "开关文件不进发布包")

# ======================================================================
print("[I] 集成：编辑模式启动 + 渲染角标")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
os.environ["ZS_DB_NO_SYNC"] = "1"
try:
    from game import Game
    from config import GameState
    g = Game()
    g.start_game()
    g.state = GameState.PLAYING
    for _i in range(5):
        g._update_playing(1 / 60)
    g.renderer.render()
    check(True, "编辑模式下启动 + 渲染不崩（含角标）")
except Exception as e:
    check(False, f"集成崩溃: {e}")
finally:
    os.environ.pop("ZS_DB_NO_SYNC", None)

print()
print(f"===== v2.8.5 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
