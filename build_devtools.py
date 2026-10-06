#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发者工具包打包脚本 —— 训练工具 + 地图编辑器 + RL 环境 + 文档
与游戏发布包分离：本工具包不进游戏更新器 manifest，玩家端「检查更新」不会下载。
用法:
  python3 build_devtools.py --version 2.1.0
产物:
  releases/zombie_survivor_devtools_v2.1.0.zip
"""
import os
import zipfile
import argparse
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = "releases"

# 工具包包含（相对仓库根；玩家端必需项 rl/maps、rl/map_format.py、rl/models 不在工具包重复打包）
TOOL_FILES = [
    # ---- RL 训练 ----
    "rl/train.py", "rl/train_termux.py", "rl/zombie_env.py",
    "rl/export_onnx.py", "rl/export_weights.py", "rl/rebuild_sb3_from_npz.py",
    "rl/train_until.sh", "rl/finish_30min.sh", "rl/report.py",
    "rl/inference.py",
    # ---- 地图工具 ----
    "rl/map_editor.py", "rl/gen_story_maps.py",
    # ---- Termux 兼容方案 ----
    "rl/termux_setup.sh", "rl/TERMUX_TRAINING.md",
    # ---- 文档 ----
    "rl/README.md",
    # ---- 依赖说明 ----
    "requirements.txt", "README.md",
]

# 整个目录整体打包（保留结构）
TOOL_DIRS = [
    "rl/eval_envs",   # 评估/训练用环境脚本
]


def main():
    ap = argparse.ArgumentParser(description="开发者工具包打包（训练工具+地图编辑器，不进游戏更新器）")
    ap.add_argument("--version", required=True, help="随游戏版本号，如 2.1.0")
    args = ap.parse_args()
    ver = args.version

    os.makedirs(os.path.join(PROJECT_DIR, OUTPUT_DIR), exist_ok=True)
    zip_name = f"zombie_survivor_devtools_v{ver}.zip"
    zip_path = os.path.join(PROJECT_DIR, OUTPUT_DIR, zip_name)

    entries = []
    for f in TOOL_FILES:
        fp = os.path.join(PROJECT_DIR, f)
        if os.path.exists(fp):
            entries.append((fp, f))
        else:
            print(f"  [跳过] 缺文件: {f}")
    for d in TOOL_DIRS:
        dp = os.path.join(PROJECT_DIR, d)
        if not os.path.isdir(dp):
            print(f"  [跳过] 缺目录: {d}")
            continue
        for root, _dirs, files in os.walk(dp):
            _dirs[:] = [x for x in _dirs if not x.startswith("__")]
            for fn in files:
                if fn.endswith((".pyc", ".pyo")):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, PROJECT_DIR)
                entries.append((full, rel))

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        header = f"僵尸幸存者 开发者工具包 v{ver}\n打包时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                 "包含: RL训练(SB3/纯NumPy/Termux) + 地图编辑器 + 训练/测评脚本\n" \
                 "注意: 本工具包仅供开发/创作者使用，不随游戏更新器下发。\n\n"
        zf.writestr("DEVTOOLS_README.txt", header)
        for full, rel in entries:
            zf.write(full, rel)
            print(f"  [打包] {rel}")

    mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"\n[完成] 工具包: {zip_name} ({len(entries)} 个文件, {mb:.2f} MB)")
    print(f"[提示] 工具包独立分发，游戏更新器 manifest 不含其中任何文件。")
    return zip_path


if __name__ == "__main__":
    main()
