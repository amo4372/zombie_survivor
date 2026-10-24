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
import math
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


def _screen_pos_of(wx, wy, camera, scale, shake=True):
    """世界坐标 → 视口局部屏幕坐标（与 _draw_playing_core 同口径）"""
    if shake and hasattr(camera, "shake_x"):
        cam_x = camera.x - getattr(camera, "shake_x", 0)
        cam_y = camera.y - getattr(camera, "shake_y", 0)
    else:
        cam_x, cam_y = camera.x, camera.y
    return (wx - cam_x) * scale, (wy - cam_y) * scale


def draw_teammate_arrow(surface, vw, vh, sx, sy, label, downed,
                        font_small, scale, dist_m=0):
    """对方玩家不在本视口内时，在视口边缘绘制方位箭头（倒地也显示）

    Args:
        surface: 目标表面（同屏传 subsurface，全屏网络模式传 screen）
        vw/vh: 该视口逻辑宽高（像素）
        sx/sy: 对方在视口局部坐标系下的屏幕坐标
        label: 对方玩家标签（"P1"/"P2"）
        downed: 是否倒地（倒地显示红色+“倒地”提示）
        font_small: 小号字体
        scale: 缩放
        dist_m: 世界距离（米/格），>0 时显示
    """
    margin = max(18, int(22 * scale))
    if -margin <= sx <= vw + margin and -margin <= sy <= vh + margin:
        return  # 在视口内，无需指示
    cx, cy = vw / 2.0, vh / 2.0
    dx, dy = sx - cx, sy - cy
    dist = math.hypot(dx, dy)
    if dist < 1:
        return
    ux, uy = dx / dist, dy / dist
    # 射线从视口中心指向对方方向，与视口内边（留 margin）求交
    txs = ((vw / 2.0 - margin) / abs(ux)) if abs(ux) > 1e-6 else float("inf")
    tys = ((vh / 2.0 - margin) / abs(uy)) if abs(uy) > 1e-6 else float("inf")
    t = min(txs, tys)
    px = int(cx + ux * t)
    py = int(cy + uy * t)
    # 朝向角
    ang = math.atan2(uy, ux)
    col = (220, 90, 80) if downed else (110, 220, 110)
    # 箭头三角形（沿方向旋转）
    r = max(8, int(12 * scale))
    pts = [
        (px + int(math.cos(ang) * r), py + int(math.sin(ang) * r)),
        (px + int(math.cos(ang + 2.6) * r * 0.7), py + int(math.sin(ang + 2.6) * r * 0.7)),
        (px + int(math.cos(ang - 2.6) * r * 0.7), py + int(math.sin(ang - 2.6) * r * 0.7)),
    ]
    pygame.draw.polygon(surface, col, pts)
    pygame.draw.polygon(surface, (20, 20, 20), pts, max(1, int(scale)))
    # 标签与距离
    tag_text = label + (" 倒地!" if downed else "")
    if dist_m > 0:
        tag_text += f" {dist_m:.0f}m"
    tag = font_small.render(tag_text, True, col)
    surface.blit(tag, tag.get_rect(center=(px, py + (r + 10) * (1 if uy >= 0 else -1))))


def draw_teammate_indicators(renderer, game, viewports, vp):
    """为指定视口绘制其余队友的方位指示（同屏 N 人通用）"""
    sw = vp.rect.width
    sh = vp.rect.height
    for other in viewports:
        if other is vp or other.player is None:
            continue
        sx, sy = _screen_pos_of(other.player.x, other.player.y, vp.camera, game.scale)
        dx, dy = other.player.x - vp.player.x, other.player.y - vp.player.y
        dist_m = math.hypot(dx, dy)
        draw_teammate_arrow(renderer.screen, sw, sh, sx, sy, other.label,
                            bool(getattr(other.player, "downed", False)),
                            game.font_small, game.scale, dist_m=dist_m)


def draw_enemy_player_indicators(renderer, game, viewports, vp):
    """v2.2.9 PvP 敌方玩家位置揭示：
    - 周期揭示：开局 3s + 每 45s 闪 3s（只给方位，不给距离）
    - v2.5.6 主动探测：脉冲式扫描（每 30s 自动 3s / V 键手动），扫描窗口内才显示
      近距离敌人的方位与距离。**不再常驻暴露**（v2.5.5 的 400 半径常驻标记已移除）
    """
    try:
        if not getattr(game.config, "pvp_enabled", False):
            return
        sw = vp.rect.width
        sh = vp.rect.height
        me = vp.player
        _periodic = bool(getattr(game, "pvp_reveal_active", False))
        # v2.5.6：探测脉冲窗口（非常驻）
        _scan_on = getattr(game, "pvp_scan_active", 0) > 0
        _scan_r = float(getattr(game, "PVP_SCAN_RADIUS", 500.0))
        for other in viewports:
            if other is vp or other.player is None:
                continue
            op = other.player
            if getattr(me, "team_id", 0) == getattr(op, "team_id", 1):
                continue  # 队友不标红
            sx, sy = _screen_pos_of(op.x, op.y, vp.camera, game.scale)
            _in_view = (0 <= sx <= sw and 0 <= sy <= sh)
            _wdist = math.hypot(op.x - me.x, op.y - me.y)
            if _scan_on and _wdist <= _scan_r:
                # 探测脉冲内：近距离敌人显示方位 + 距离
                _mx, _my = int(sx), int(sy)
                if _in_view:
                    _mr = max(6, int(7 * game.scale))
                    pygame.draw.polygon(renderer.screen, (255, 60, 60),
                                        [(_mx, _my - _mr), (_mx + _mr, _my), (_mx, _my + _mr), (_mx - _mr, _my)])
                    pygame.draw.polygon(renderer.screen, (255, 200, 200),
                                        [(_mx, _my - _mr + 2), (_mx + _mr - 2, _my), (_mx, _my + _mr - 2), (_mx - _mr + 2, _my)], 1)
                    _dt = game.font_small.render(f"{int(_wdist)}", True, (255, 120, 120))
                    renderer.screen.blit(_dt, (_mx - _dt.get_width() // 2, _my + _mr + 2))
                continue
            if not _periodic:
                continue
            if _in_view:
                # 视口内敌人本身可见，不再画常驻红圈（位置揭示只针对屏幕外）
                pass
            else:
                # 屏幕外：边缘红色箭头（只给方位，不给距离）
                cx, cy = sw // 2, sh // 2
                ang = math.atan2(op.y - me.y, op.x - me.x)
                ex = max(16, min(sw - 16, cx + math.cos(ang) * (sw * 0.42)))
                ey = max(16, min(sh - 16, cy + math.sin(ang) * (sh * 0.42)))
                _a1 = ang + 2.6
                _a2 = ang - 2.6
                pygame.draw.polygon(renderer.screen, (255, 60, 60), [
                    (ex + math.cos(ang) * 12, ey + math.sin(ang) * 12),
                    (ex + math.cos(_a1) * 8, ey + math.sin(_a1) * 8),
                    (ex + math.cos(_a2) * 8, ey + math.sin(_a2) * 8)])
    except Exception:
        pass


def build_split_viewports(game):
    """由游戏状态推导同屏视口列表（数据驱动，N 人扩展点）"""
    sw = game.scaled_width
    sh = game.scaled_height
    players = [("P1", game.player, game.camera)]
    if getattr(game, "player2", None):
        players.append(("P2", game.player2, game.camera2))
    # v2.2.7：N 人支持——3/4 号玩家（网络联机补位）同屏分屏渲染
    for _i in (3, 4):
        _pn = getattr(game, f"player{_i}", None)
        _cam = getattr(game, f"camera{_i}", None)
        if _pn is not None and _cam is not None:
            players.append((f"P{_i}", _pn, _cam))
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
    for i, vp in enumerate(viewports):
        # 场景渲染在 subsurface（视口偏移由 viewport_x 补偿）
        # v2.2.7：aim_owner 区分视口——P1 视口画 P1 预瞄、P2 视口画 P2 预瞄，
        # 修复"P2技能/投掷物预瞄线全部画在P1上"（原来 _draw_playing_core 无条件画 P1）
        aim_owner = "P2" if (i == 1 and vp.label == "P2") else "P1"
        renderer.screen = orig_screen.subsurface(vp.rect)
        renderer._draw_playing_core(vp.player, vp.camera, viewport_x=vp.rect.x, aim_owner=aim_owner)
        # v2.1.3：队友方位指示（对方不在本视口内时边缘箭头，倒地仍显示）
        draw_teammate_indicators(renderer, game, viewports, vp)
        # v2.2.9：PvP 敌方玩家位置揭示（开局 8s + 每 45s 闪 3s）
        draw_enemy_player_indicators(renderer, game, viewports, vp)
        # HUD 必须回全屏绘制（_draw_hud_split 内部用全屏绝对坐标 rect.x+…，
        # 且双人触控控件 base_x 本身含半屏偏移）
        renderer.screen = orig_screen
        renderer._draw_hud_split(vp.player, vp.label, vp.rect)
    renderer.screen = orig_screen
    draw_separators(renderer, game, viewports)
