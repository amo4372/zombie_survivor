#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主游戏模块壳（v2.0.9 起逻辑拆分至 zombie_pkg 包，保持 import 兼容）

v2.0.10 兼容引导：旧版本更新器（平铺式）只复制顶层 .py 与 assets 目录，
不会复制 zombie_pkg/renderer_pkg 子目录。因此启动时若发现包目录缺失，
自动从 assets/_pkg_compat.zip（随 assets 一同被旧版更新器带过来）解包自愈，
保证旧版本玩家无需手动操作即可升级到包结构新版本。
"""
import os
import sys
import zipfile

_SAFE_BASE = os.path.dirname(os.path.abspath(__file__))


def _ensure_package_dirs():
    """包目录缺失时从 assets/_pkg_compat.zip 自愈解包。返回 0=无需处理 / N=解包数 / -1=失败"""
    missing = [p for p in ("zombie_pkg", "renderer_pkg")
               if not os.path.isdir(os.path.join(_SAFE_BASE, p))]
    if not missing:
        return 0
    compat = os.path.join(_SAFE_BASE, "assets", "_pkg_compat.zip")
    if not os.path.exists(compat):
        return -1
    try:
        with zipfile.ZipFile(compat) as zf:
            zf.extractall(_SAFE_BASE)
        return len(missing)
    except Exception:
        return -1


_ensure_package_dirs()
from zombie_pkg import Game, Config, logger, _save_encrypt, _save_decrypt  # noqa: F401
from config import GameState  # noqa: F401  （兼容 from game import GameState）

if __name__ == "__main__":
    try:
        game = Game()
        game.run()
    except Exception as e:
        logger.log_exception(e)
        raise
