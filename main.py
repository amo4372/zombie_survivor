#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
丧尸幸存者 - Zombie Survivor v4.0
黑暗尸潮版本 + 资源系统 + 全局记录
模块化版本入口文件
"""
import sys
import os

# PyInstaller 打包资源路径处理
def resource_path(relative_path):
    """获取资源绝对路径（支持 PyInstaller 打包后）"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

import pygame
from game import Game, logger

try:
    game = Game()
    game.run()
except Exception as e:
    logger.log_exception(e)
    raise
