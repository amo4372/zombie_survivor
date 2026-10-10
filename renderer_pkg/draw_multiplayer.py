#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同屏多人渲染模块（v2.1.3 结构化重构）
====================================
将"同屏分屏绘制"从 draw_play.py 中抽离为数据驱动的视口编排层：
- SplitViewport：单个玩家视口的纯数据描述（玩家/相机/标签/矩形）
- build_split_viewports：由游戏状态推导视口列表（N 人同屏只需扩展玩家列表）
- render_split_viewports：统一渲染编排（subsurface 切换 + core/HUD 绘制 + 分隔线/标签）

UI 与单人完全分离：单人走 draw_play._draw_playing/_draw_hud（全屏控件），
同屏多人只走本模块 + draw_play 的 _draw_hud_split/_draw_touch_controls_split（半屏视口），
杜绝单人触控控件串染进分屏（"P1 按钮在 P2 上重合"根因修复）。

未来扩展 N 人同屏：只需让 build_split_viewports 返回 N 个 SplitViewport，
分割线/标签循环与渲染循环自动适配，无需改动 draw_play 核心。
"""
import pygame
from dataclasses import dataclass


@dataclass
class SplitViewport:
    """单个玩家视口：同屏分割的纯数据描述（不持有渲染逻辑）"""
    player: object
    camera: object
    label: str          # "P1"/"P2"/...，用于 HUD 标注与升级选卡归属
    rect: pygame.Rect   # 全屏坐标系下的视口矩形（subsurface 区域）
    index: int          # 视口序号（从 0 开始，用于分隔线/标签定位）


def build_split_viewports(game):
    """由游戏状态推导同屏视口列表（数据驱动，N 人扩展点）"""
    sw = game.scaled_width
    sh = game.scaled_height
    players = [("P1", game.player, game.camera)]
    if getattr(game, "player2", None):
        players.append(("P2", game.player2, game.camera2))
    n = len(players)
    half = sw // n
    viewports = []
    for idx, (label, player, camera) in enumerate(players):
        if player is None or camera is None:
            continue
        viewports.append(SplitViewport(
            player=player, camera=camera, label=label,
            rect=pygame.Rect(idx * half, 0, half, sh), index=idx,
        ))
    return viewports


def draw_separators(renderer, game, viewports):
    """分隔线 + 顶部玩家标签（所有视口渲染完成后绘制在全屏上）"""
    screen = renderer.screen
    n = len(viewports)
    sw = game.scaled_width
    sh = game.scaled_height
    scale = game.scale
    for idx in range(1, n):
        x = viewports[0].rect.width * idx
        pygame.draw.line(screen, (120, 90, 140), (x, 0), (x, sh), max(2, int(2 * scale)))
    for vp in viewports:
        tag = game.font_small.render(vp.label, True, (255, 215, 0))
        screen.blit(tag, (vp.rect.x + 8, 6))
    del sw, sh  # 预留：N 人时可在此处绘制整体安全区等


def render_split_viewports(renderer, game, viewports):
    """统一渲染编排：subsurface 切换 + 每视口 core/HUD + 分隔线/标签

    Args:
        renderer: DrawPlay 渲染器实例（复用其 _draw_playing_core/_draw_hud_split）
        game: 游戏实例
        viewports: build_split_viewports 返回的视口列表
    """
    orig_screen = renderer.screen
    for vp in viewports:
        # 场景渲染在 subsurface（视口偏移由 viewport_x 补偿）
        renderer.screen = orig_screen.subsurface(vp.rect)
        renderer._draw_playing_core(vp.player, vp.camera, viewport_x=vp.rect.x)
        # HUD 必须回全屏绘制（_draw_hud_split 内部用全屏绝对坐标 rect.x+…，
        # 且双人触控控件 base_x 本身含半屏偏移）
        renderer.screen = orig_screen
        renderer._draw_hud_split(vp.player, vp.label, vp.rect)
    renderer.screen = orig_screen
    draw_separators(renderer, game, viewports)
