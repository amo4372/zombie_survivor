#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布打包脚本 - 自动更新版本号、打包必要文件、生成发布包
用法:
  python build_release.py --version 1.1.0          # 指定版本号打包
  python build_release.py --bump patch               # 补丁版本+1 (1.0.0 -> 1.0.1)
  python build_release.py --bump minor               # 次版本+1 (1.0.0 -> 1.1.0)
  python build_release.py --bump major               # 主版本+1 (1.0.0 -> 2.0.0)
  python build_release.py --changelog "修复了xxx"    # 附带更新日志
"""

import os
import sys
import json
import zipfile
import argparse
import shutil
from datetime import datetime

# ============ 配置 ============
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = "version.txt"
OUTPUT_DIR = "releases"

# 游戏运行必要文件（打包时包含）
ESSENTIAL_FILES = [
    "main.py", "game.py", "config.py", "entities.py", "world.py",
    "renderer.py", "buff.py", "skills.py", "ui.py", "weapons.py",
    "assets.py", "records.py", "logger.py", "dialogue.py",
    "skill_wheel.py", "runes.py", "lighting.py", "mod_loader.py",
    "codex.py", "skill_tree_view.py", "updater.py", "version.txt",
    "requirements.txt", "README.md",
]

# 必要目录（打包时包含）
ESSENTIAL_DIRS = [
    "assets",      # 游戏资源（图片、音效、音乐）
    "mods",        # Mod目录（如果有）
]

# 排除的文件模式（即使在必要目录中也排除）
EXCLUDE_PATTERNS = [
    "__pycache__", ".pyc", ".pyo", ".pyd",
    ".git", ".gitignore", ".svn",
    "game_log.txt", "config.json", "game_records.json",
    "codex_unlocks.json", "mods_config.json", "skill_tree_unlock.json",
    "savegame.json", "savegame.zss",
    "_update_cache", "_update_backup",
    "dist_encrypted", "releases",
    "fluidsynth_portable",  # FluidSynth便携版，体积大，不打包
]

# 开发工具文件（不打包到发布包，但保留在源码中）
DEV_TOOLS = [
    "build_encrypted.py", "build_release.py",
    "convert_with_sf2.py", "generate_music.py",
    "crypto_tool.py",
    "DEV_GUIDE.md", "MOD_DEV_GUIDE.md", "MANIFEST.md",
]


def get_current_version():
    """获取当前版本号"""
    version_path = os.path.join(PROJECT_DIR, VERSION_FILE)
    if os.path.exists(version_path):
        with open(version_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return "0.0.0"


def bump_version(current, bump_type):
    """递增版本号"""
    parts = current.split('.')
    while len(parts) < 3:
        parts.append('0')
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    elif bump_type == 'patch':
        patch += 1

    return f"{major}.{minor}.{patch}"


def update_version(new_version):
    """更新版本号文件"""
    version_path = os.path.join(PROJECT_DIR, VERSION_FILE)
    with open(version_path, 'w', encoding='utf-8') as f:
        f.write(new_version + '\n')
    print(f"[版本] 已更新为 v{new_version}")


def should_exclude(filepath):
    """检查文件是否应该排除"""
    filename = os.path.basename(filepath)
    for pattern in EXCLUDE_PATTERNS:
        if pattern in filepath or pattern in filename:
            return True
    return False


def collect_files():
    """收集需要打包的文件"""
    files_to_pack = []

    # 必要文件
    for f in ESSENTIAL_FILES:
        fpath = os.path.join(PROJECT_DIR, f)
        if os.path.exists(fpath) and not should_exclude(f):
            files_to_pack.append((fpath, f))

    # 必要目录
    for d in ESSENTIAL_DIRS:
        dpath = os.path.join(PROJECT_DIR, d)
        if not os.path.exists(dpath):
            continue
        for root, dirs, filenames in os.walk(dpath):
            # 排除子目录
            dirs[:] = [d for d in dirs if not should_exclude(d)]
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, PROJECT_DIR)
                if not should_exclude(rel_path):
                    files_to_pack.append((full_path, rel_path))

    return files_to_pack


def create_zip(version, files, changelog=""):
    """创建发布zip包"""
    os.makedirs(os.path.join(PROJECT_DIR, OUTPUT_DIR), exist_ok=True)
    zip_name = f"zombie_survivor_v{version}_update.zip"
    zip_path = os.path.join(PROJECT_DIR, OUTPUT_DIR, zip_name)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for full_path, rel_path in files:
            # 在zip中创建顶层目录
            arcname = os.path.join(f"zombie_survivor_v{version}", rel_path)
            zf.write(full_path, arcname)
            print(f"  [打包] {rel_path}")

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"\n[完成] 发布包已生成: {zip_name}")
    print(f"[大小] {size_mb:.2f} MB")
    print(f"[文件] {len(files)} 个文件")

    # 生成发布信息JSON（用于GitHub release）
    release_info = {
        "tag_name": f"v{version}",
        "name": f"僵尸幸存者 v{version}",
        "body": changelog or f"## 僵尸幸存者 v{version}\n\n发布时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "assets": [zip_name],
    }
    info_path = os.path.join(PROJECT_DIR, OUTPUT_DIR, f"release_info_v{version}.json")
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(release_info, f, ensure_ascii=False, indent=2)
    print(f"[信息] 发布信息已保存: release_info_v{version}.json")

    return zip_path


def main():
    parser = argparse.ArgumentParser(description="僵尸幸存者 - 发布打包脚本")
    parser.add_argument("--version", help="指定版本号 (如 1.1.0)")
    parser.add_argument("--bump", choices=['major', 'minor', 'patch'],
                        help="自动递增版本号")
    parser.add_argument("--changelog", help="更新日志内容")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅显示将打包的文件，不实际打包")

    args = parser.parse_args()

    print("=" * 60)
    print("  僵尸幸存者 - 发布打包工具")
    print("=" * 60)

    # 确定版本号
    current = get_current_version()
    if args.version:
        new_version = args.version
    elif args.bump:
        new_version = bump_version(current, args.bump)
    else:
        new_version = current
        print(f"[提示] 未指定版本号，使用当前版本 v{current}")
        print(f"       使用 --version 1.1.0 指定版本，或 --bump patch/minor/major 递增")

    print(f"\n当前版本: v{current}")
    print(f"发布版本: v{new_version}")

    if new_version != current and not args.dry_run:
        update_version(new_version)

    # 收集文件
    print(f"\n[收集] 正在收集必要文件...")
    files = collect_files()
    print(f"[收集] 共 {len(files)} 个文件")

    if args.dry_run:
        print("\n[预览] 将打包以下文件:")
        for _, rel_path in files:
            print(f"  - {rel_path}")
        print(f"\n[预览] 总计 {len(files)} 个文件")
        return

    # 创建zip
    changelog = args.changelog or ""
    zip_path = create_zip(new_version, files, changelog)

    # 输出上传指南
    print("\n" + "=" * 60)
    print("  GitHub 发布指南")
    print("=" * 60)
    print(f"""
1. 打开 GitHub 仓库: https://github.com/amo4372/zombie_survivor
2. 点击 "Releases" -> "Create a new release"
3. Tag version: v{new_version}
4. Release title: 僵尸幸存者 v{new_version}
5. 描述内容: 粘贴更新日志
6. 上传附件: 将 {os.path.basename(zip_path)} 拖入附件区域
7. 点击 "Publish release"

发布后，游戏内「检查更新」会自动检测到新版本并提示更新。
""")


if __name__ == '__main__':
    main()
