#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""平铺旧版 → 包结构升级链路模拟测试

模拟真实用户路径：
1. 平铺旧版环境（v2.0.7 时代：顶层 .py + assets，无 zombie_pkg/ 包目录）
2. 旧版 updater 逻辑（只复制顶层 .py/version.txt/.md + assets 目录 copytree，
   不复制子目录——v1.x~v2.0.7 行为）
3. 启动新版 game.py → _ensure_package_dirs 从 assets/_pkg_compat.zip 自愈解包
4. 验证 import game 成功 + 后续新版 updater 全量镜像清理旧残留
"""
import os, sys, shutil, tempfile, zipfile
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

SRC = "/home/user/zombie_survivor"
PKG_ZIP = os.path.join(SRC, "releases", "zombie_survivor_v2.1.4_update.zip")

ok = 0
def check(name, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")

# ============ 构造平铺旧版环境 ============
tmp = tempfile.mkdtemp(prefix="flat_old_")
print(f"模拟平铺旧版目录: {tmp}")
for f in ("game.py", "config.py", "lighting.py", "entities.py", "renderer.py",
          "mix_playing.py", "mix_input.py", "mix_multi.py", "records.py", "skills.py",
          "version.txt"):
    p = os.path.join(tmp, f)
    if f == "version.txt":
        open(p, "w").write("2.0.7\n")
    elif f == "game.py":
        open(p, "w").write("# 旧版平铺 game.py（无自愈逻辑）\nimport pygame\n")
    else:
        open(p, "w").write(f"# 旧版顶层模块 {f}\n")
os.makedirs(os.path.join(tmp, "assets"), exist_ok=True)
open(os.path.join(tmp, "assets", "manifest.json"), "w").write("{}")
print("== 1. 旧版 updater 逻辑应用 v2.1.4 包 ==")
# 模拟 v2.0.3 updater：extractall → 找顶层 → 复制顶层 .py/version.txt/.md + assets copytree
work = tempfile.mkdtemp(prefix="old_updater_")
with zipfile.ZipFile(PKG_ZIP) as zf:
    zf.extractall(work)
update_dir = None
for root, dirs, files in os.walk(work):
    if any(f.endswith(".py") for f in files):
        update_dir = root
        break
applied = 0
for f in os.listdir(update_dir):
    src = os.path.join(update_dir, f)
    dst = os.path.join(tmp, f)
    if os.path.isfile(src) and (f.endswith(".py") or f == "version.txt" or f.endswith(".md")):
        shutil.copy2(src, dst)
        applied += 1
up_assets = os.path.join(update_dir, "assets")
if os.path.isdir(up_assets):
    for item in os.listdir(up_assets):
        s = os.path.join(up_assets, item)
        d = os.path.join(tmp, "assets", item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        elif os.path.isfile(s):
            shutil.copy2(s, d)
check("顶层 .py 被新版覆盖（game.py 含自愈逻辑）",
      "_ensure_package_dirs" in open(os.path.join(tmp, "game.py")).read())
check("assets/_pkg_compat.zip 落地（旧版 updater 复制 assets）",
      os.path.isfile(os.path.join(tmp, "assets", "_pkg_compat.zip")))
check("包目录未写入（旧版 updater 不复制子目录）",
      not os.path.isdir(os.path.join(tmp, "zombie_pkg")))
print("== 2. 启动新版 game.py → 自愈 ==")
sys.path.insert(0, tmp)
import importlib
import game  # 执行 _ensure_package_dirs → 解包 compat
check("自愈后 zombie_pkg/ 存在", os.path.isdir(os.path.join(tmp, "zombie_pkg")))
check("自愈后 renderer_pkg/ 存在", os.path.isdir(os.path.join(tmp, "renderer_pkg")))
check("自愈后包内模块齐全（draw_multiplayer）",
      os.path.isfile(os.path.join(tmp, "renderer_pkg", "draw_multiplayer.py")))
check("import game 成功（含新版自愈后 import zombie_pkg）", True)
print("== 3. 新版 updater 全量镜像 → 清理平铺残留 ==")
# 模拟新版 updater 阶段3：清理顶层不在新包中的 .py
with zipfile.ZipFile(PKG_ZIP) as zf:
    prefix = "zombie_survivor_v2.1.4/"
    new_rel = {n[len(prefix):] for n in zf.namelist() if n.startswith(prefix) and not n.endswith("/")}
    new_tops = {os.path.basename(r) for r in new_rel if "/" not in r}
removed = 0
for f in os.listdir(tmp):
    fp = os.path.join(tmp, f)
    if os.path.isfile(fp) and f.endswith(".py") and f not in new_tops:
        os.remove(fp)
        removed += 1
# 新版包不再包含的旧平铺模块（已迁入 zombie_pkg）会被清理：
# mix_playing/mix_input/mix_multi；而 entities/renderer/records/skills 在新包顶层
# 是 shim（from *_pkg import *），会被覆盖保留而非删除。
check("平铺残留 mix 模块被清理（已迁入包）", removed >= 3, f"removed={removed}")
for f in ("mix_playing.py", "mix_input.py", "mix_multi.py"):
    check(f"旧顶层 {f} 已清理", not os.path.exists(os.path.join(tmp, f)))
check("顶层 shim（entities/renderer/records/skills）覆盖保留",
      all(os.path.isfile(os.path.join(tmp, f)) for f in ("entities.py", "renderer.py", "records.py", "skills.py")))
check("shim 已替换为新版（entities.py 指向 entities_pkg）",
      "entities_pkg" in open(os.path.join(tmp, "entities.py")).read())
check("顶层保留模块（config/lighting/game）未被误删",
      all(os.path.isfile(os.path.join(tmp, f)) for f in ("config.py", "lighting.py", "game.py")))

shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(work, ignore_errors=True)
print(f"\n== 结果: {ok} 项通过 ==")
