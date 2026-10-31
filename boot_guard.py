#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.2 启动致命错误自愈引导（boot_guard）

触发条件：**游戏根本打不开**的错误，即 import / 语法 / 顶层执行期异常
（ModuleNotFoundError、ImportError、SyntaxError、NameError、AttributeError
在导入阶段抛出等）。正常游玩中的运行时错误不在此列（由游戏内错误静默处理）。

行为：
  1) 有更高的可用版本 → 正常更新过去
  2) 没有 → 回退上一个版本，并把当前版本标记为"错误版本"（以后跳过）
  3) 都失败 → 提示用户手动重装

用法：python main.py 失败时会自动调用；也可单独 python boot_guard.py 手动修复。
"""

import os
import sys
import time
import traceback

# 命中这些异常类型才认定为"致命启动错误"
FATAL_EXC = (ImportError, ModuleNotFoundError, SyntaxError, NameError,
             IndentationError, TabError)

_FATAL_HINTS = ("No module named", "cannot import name", "ImportError",
                "ModuleNotFoundError", "SyntaxError", "NameError")


def is_fatal_boot_error(exc):
    """判断异常是否属于"游戏打不开"级别的致命错误"""
    if isinstance(exc, FATAL_EXC):
        return True
    _txt = f"{type(exc).__name__}: {exc}"
    # AttributeError/TypeError 只有发生在导入阶段才算（此处无法精确判断，
    # 用文案兜底：出现模块相关关键词才认定）
    if isinstance(exc, (AttributeError, TypeError)):
        return any(h in _txt for h in ("module", "Module", "import"))
    return False


def try_selfheal(error_text, status_cb=None, progress_cb=None):
    """调用 updater 的自愈流程；返回是否成功安排了修复"""
    try:
        import updater
        return updater.handle_boot_failure(error_text, status_cb=status_cb,
                                           progress_cb=progress_cb)
    except Exception as _e:
        if status_cb:
            status_cb(f"自愈模块不可用: {_e}")
        return False


def restart():
    """重启游戏（execv 替换当前进程）"""
    try:
        import pygame
        try:
            pygame.quit()
        except Exception:
            pass
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception:
            pass


def main():
    print("=" * 56)
    print(" 僵尸幸存者 · 启动错误自愈")
    print("=" * 56)
    _err = " ".join(sys.argv[1:]) or "手动触发"
    print(f"错误: {_err[:200]}")
    _ok = try_selfheal(_err, status_cb=lambda s: print(f"  → {s}"))
    if _ok:
        print("修复完成，2 秒后重启...")
        time.sleep(2)
        restart()
    else:
        print("自动修复失败，请手动重新下载安装游戏。")
        try:
            input("按回车退出...")
        except Exception:
            pass
    return 0 if _ok else 1


def guard_exception(exc):
    """main.py 捕获到异常后调用：致命则尝试自愈并重启

    返回 True 表示已处理（不会继续抛出）
    """
    if not is_fatal_boot_error(exc):
        return False
    _txt = traceback.format_exc()
    print("=" * 56)
    print(" 检测到致命启动错误，尝试自动修复...")
    print("=" * 56)
    print(_txt[-800:])
    _ok = try_selfheal(_txt, status_cb=lambda s: print(f"  → {s}"))
    if _ok:
        print("修复完成，重启中...")
        time.sleep(2)
        restart()
    else:
        print("自动修复失败，请手动重新下载安装。")
    return _ok


if __name__ == "__main__":
    sys.exit(main())
