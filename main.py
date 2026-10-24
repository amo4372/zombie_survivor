#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
丧尸幸存者 - Zombie Survivor v4.0
黑暗尸潮版本 + 资源系统 + 全局记录
模块化版本入口文件
"""
import sys
import os

# Pygame 中文输入法（SDL_IME）：必须在 pygame.init() 之前设置
os.environ.setdefault("SDL_IME_SHOW_UI", "1")
os.environ.setdefault("SDL_IME_INTERNAL", "1")

# PyInstaller 打包资源路径处理
def resource_path(relative_path):
    """获取资源绝对路径（支持 PyInstaller 打包后）"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

import pygame
from game import Game, logger

_text_input_started = False
try:
    # 开启文本输入（支持系统输入法中文候选框）
    try:
        pygame.key.start_text_input()
        _text_input_started = True
    except Exception:
        pass
    game = Game()
    if os.environ.get("ZOMBIE_SMOKE") == "1":
        # v2.5.5 运行时错误优先冒烟：跑帧+开局后退出（异常→退出码非0，供测试捕获）
        game._smoke_run()
        sys.exit(0)
    game.run()
except Exception as e:
    logger.log_exception(e)
    raise
finally:
    # v2.5.6：关闭文本输入（对应 start_text_input）——
    # 否则退出/异常时 IME 候选框与文本输入状态残留（Windows 下会残留输入框/焦点异常）
    if _text_input_started:
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass
