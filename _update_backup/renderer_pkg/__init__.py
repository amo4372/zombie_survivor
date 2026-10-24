# -*- coding: utf-8 -*-
"""renderer_pkg - 渲染系统包（由 renderer.py 拆分，零逻辑改动）
class Renderer 聚合 RenderCore + 各绘制 Mixin，外部 from renderer import Camera, Renderer 兼容。
"""
from .camera import Camera
from .render_core import RenderCore
from .draw_ui import UiMixin
from .draw_play import PlayMixin
from .draw_dev import DevMixin


class Renderer(RenderCore, UiMixin, PlayMixin, DevMixin):
    """完整渲染器（聚合拆分后的全部绘制 Mixin，逻辑与拆分前等价）"""
    pass


__all__ = ["Camera", "Renderer", "RenderCore"]
