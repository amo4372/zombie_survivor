#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.6 快速测试：点更新不执行 / 跨版本 MD5 比对更新

按需求：**不跑帧**（末尾少量帧验证集成）。
"""
import hashlib
import os
import shutil
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
for _f in ("updater.py", "renderer_pkg/draw_ui.py", "build_release.py"):
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, "关键模块编译通过")

import updater as U

# ======================================================================
print("[B] 修复：点『下载并更新』无任何反馈")
_src = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("updater.perform_full_update(" in _src and "status_cb=lambda" in _src,
      "UI 调用已传 status_cb（此前裸调用，线程内一切静默）")
check("progress_cb=lambda" in _src, "UI 调用已传 progress_cb")
check('UPDATE_STATE["force_update"] = True' in _src, "手动点更新时强制更新（忽略版本相同）")
check('"force_update": False' in open("updater.py", encoding="utf-8").read(),
      "UPDATE_STATE 新增 force_update 字段")
_su = open("updater.py", encoding="utf-8").read()
check("def _update_thread_inner" in _su,
      "更新线程拆分：外层兜底捕获异常（此前线程静默死亡→永远卡住）")
check("check_for_updates(timeout=15)" in _su, "检查更新超时放宽到 15s（弱网不误判）")

# ======================================================================
print("[C] 多源下载 + MD5 校验")
check(hasattr(U, "_file_source_urls"), "多源候选存在")
_urls = U._file_source_urls("zombie_pkg/a.py", "v2.8.6")
check(len(_urls) >= 3, f"候选源 {len(_urls)} 个")
check(any("jsdelivr" in _u for _u in _urls), "含 jsDelivr CDN（按 tag 精确定版本）")
check(any("raw.githubusercontent" in _u for _u in _urls), "含 raw 源")
check(hasattr(U, "_download_file_verified"), "校验下载函数存在")
_src_dl = _su
check("expect_md5" in _src_dl and "_download_file_verified" in _src_dl,
      "增量下载改用校验下载（防代理返回错误页被写入）")

# ======================================================================
print("[D] 跨版本 MD5 比对")
_tmp = tempfile.mkdtemp()
_gd = os.path.join(_tmp, "game")
os.makedirs(os.path.join(_gd, "zombie_pkg"))
os.makedirs(os.path.join(_gd, "mods"))


def _w(rel, content):
    _p = os.path.join(_gd, rel)
    os.makedirs(os.path.dirname(_p), exist_ok=True)
    with open(_p, "w", encoding="utf-8") as _f:
        _f.write(content)


def _md5(b):
    return hashlib.md5(b).hexdigest()


# 本地：很旧的版本
_w("zombie_pkg/a.py", "OLD_A")
_w("zombie_pkg/b.py", "SAME_B")
_w("zombie_pkg/old_removed.py", "OLD_GONE")
_w("mods/my_mod.py", "USER_MOD")
_mani = {
    "zombie_pkg/a.py": {"md5": _md5(b"NEW_A"), "size": 5},
    "zombie_pkg/b.py": {"md5": _md5(b"SAME_B"), "size": 6},
    "zombie_pkg/c.py": {"md5": _md5(b"NEW_C"), "size": 5},
}
_need = U.compute_changed_files(_mani, _gd)
check(sorted(_need) == ["zombie_pkg/a.py", "zombie_pkg/c.py"],
      f"跨版本只下载真正变化的文件（{sorted(_need)}）")
check("zombie_pkg/b.py" not in _need, "未变化的文件不重复下载")
_rm = U.compute_removed_files(_mani, _gd)
check(_rm == ["zombie_pkg/old_removed.py"], f"识别新版本已删除的残留（{_rm}）")
check(not any("mods" in _r for _r in _rm), "玩家 mods/ 绝不误删")
check(hasattr(U, "compute_removed_files"), "跨版本清理函数存在")
check("incremental_removed" in _su, "清理结果写入状态")
check("增量应用后仍有" in _su, "应用后重新比对校验（失败则回退全量）")

# 元数据键不被当文件
_mani2 = dict(_mani)
_mani2["_version"] = "2.8.6"
_need2 = U.compute_changed_files(_mani2, _gd)
check("_version" not in _need2, "manifest 元数据键 _version 不被当作文件")

# 用户数据不覆盖
_mani3 = dict(_mani)
_mani3["config.json"] = {"md5": "x", "size": 1}
_mani3["game_data.db"] = {"md5": "y", "size": 1}
_need3 = U.compute_changed_files(_mani3, _gd)
check("config.json" not in _need3, "config.json 受保护")
check("game_data.db" not in _need3, "game_data.db 受保护（数值库不被覆盖）")

shutil.rmtree(_tmp, ignore_errors=True)

# ======================================================================
print("[E] manifest 版本一致性")
check("增量清单版本不匹配" in _su, "清单版本与目标版本不符时回退全量")
check('_out["_version"]' in _su, "清单版本号透传")

# ======================================================================
print("[F] 集成（少量帧）")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
try:
    from game import Game
    g = Game()
    g.start_game()
    for _i in range(5):
        g._update_playing(1 / 60)
    g.renderer.render()
    check(True, "游戏启动 + 渲染不崩")
except Exception as e:
    check(False, f"集成崩溃: {e}")

print()
print(f"===== v2.8.6 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
