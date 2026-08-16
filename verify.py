#!/usr/bin/env python3
"""打包验证脚本 - 检查所有文件是否就绪"""

import os
import sys

required_files = [
    "main.py", "game.py", "renderer.py", "config.py",
    "assets.py", "records.py", "entities.py", "weapons.py",
    "skills.py", "ui.py", "world.py", "dialogue.py",
    "skill_wheel.py", "logger.py", "requirements.txt",
]

optional_dirs = [
    "assets/images",
    "assets/sounds", 
    "assets/music",
]

def check():
    print("=" * 50)
    print("丧尸幸存者 - 打包验证")
    print("=" * 50)

    all_ok = True

    print("\n[必需文件]")
    for f in required_files:
        exists = os.path.exists(f)
        status = "✓" if exists else "✗ MISSING"
        print(f"  {status} {f}")
        if not exists:
            all_ok = False

    print("\n[资源目录]")
    for d in optional_dirs:
        exists = os.path.exists(d)
        status = "✓" if exists else "○ (将使用占位图/静默)"
        print(f"  {status} {d}")

    print("\n[Python依赖]")
    try:
        import pygame
        print(f"  ✓ pygame {pygame.version.ver}")
    except ImportError:
        print("  ✗ pygame (运行: pip install pygame)")
        all_ok = False

    try:
        import PyInstaller
        print(f"  ✓ PyInstaller")
    except ImportError:
        print("  ✗ PyInstaller (运行: pip install pyinstaller)")

    print("\n" + "=" * 50)
    if all_ok:
        print("验证通过! 可以执行打包命令:")
        print("  pyinstaller ZombieSurvivor.spec")
    else:
        print("验证失败! 请检查缺失文件。")
    print("=" * 50)

if __name__ == "__main__":
    check()
