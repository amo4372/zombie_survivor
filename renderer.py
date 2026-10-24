#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染系统模块壳（v2.0.9 起逻辑拆分至 renderer_pkg 包，保持 import 兼容）

v2.0.10 兼容引导：同 game.py，包目录缺失时从 assets/_pkg_compat.zip 自愈解包
（正常情况下 game.py 已先行解包，此处为独立 import 本模块时的兜底）。
"""
import os
import zipfile

_SAFE_BASE = os.path.dirname(os.path.abspath(__file__))


def _ensure_pkg():
    if os.path.isdir(os.path.join(_SAFE_BASE, "renderer_pkg")):
        return
    compat = os.path.join(_SAFE_BASE, "assets", "_pkg_compat.zip")
    if os.path.exists(compat):
        try:
            with zipfile.ZipFile(compat) as zf:
                zf.extractall(_SAFE_BASE)
        except Exception:
            pass


_ensure_pkg()
from renderer_pkg import Camera, Renderer  # noqa: F401
