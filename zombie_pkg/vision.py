# -*- coding: utf-8 -*-
"""VisionSystem — v2.9.21 视野 / 战争迷雾（兼顾性能）。

设计取舍：
  * 遮罩在 **1/3 分辨率** 的 Surface 上绘制，再放大 blit 一次 → 每帧只有
    一次全屏合成，不做逐像素运算；
  * 可见多边形每 3 帧重算一次（48 条射线 vs 视口附近障碍的网格候选），
    其余帧复用上一帧遮罩；
  * 射线只查 `world.obstacle_candidates()` 返回的近邻障碍，不做全表扫描；
  * 提供 `visible(x,y)` 供渲染层跳过视野外的敌人 / 子弹（性能收益 > 绘制成本）；
  * 超难 AI 的透视不走这里（仍读全部实体），符合既有设定。
"""
import math
import pygame

RAY_COUNT = 48
UPDATE_INTERVAL = 3          # 每 3 帧重算
MASK_DIV = 3                 # 遮罩分辨率 = 屏幕 / 3


class VisionSystem:
    def __init__(self, enabled=True, radius=760.0, darkness=175):
        self.enabled = enabled
        self.radius = float(radius)
        self.darkness = int(darkness)
        self.frame = 0
        self.mask = None
        self.poly = []
        self.center = (0.0, 0.0)

    def configure(self, enabled=None, radius=None, darkness=None):
        if enabled is not None: self.enabled = bool(enabled)
        if radius is not None: self.radius = float(radius)
        if darkness is not None: self.darkness = int(darkness)

    # ---------- 射线 ----------
    @staticmethod
    def _ray_hit(px, py, ang, maxd, obstacles):
        """从 (px,py) 沿 ang 找最近遮挡点；返回距离。"""
        _dx, _dy = math.cos(ang), math.sin(ang)
        _best = maxd
        for _o in obstacles:
            if not GameWorldBlocksSight(_o):
                continue
            _r = _o['rect']
            # Liang–Barsky：求射线与 AABB 的最近进入距离
            _ok = True
            _t0, _t1 = 0.0, _best
            for _dir, _org, _lo, _hi in ((_dx, px, _r.left, _r.right),
                                         (_dy, py, _r.top, _r.bottom)):
                if abs(_dir) < 1e-9:
                    if _org < _lo or _org > _hi:
                        _ok = False; break
                    continue
                _ta = (_lo - _org) / _dir
                _tb = (_hi - _org) / _dir
                if _ta > _tb: _ta, _tb = _tb, _ta
                _t0 = max(_t0, _ta)
                _t1 = min(_t1, _tb)
                if _t0 > _t1:
                    _ok = False; break
            if _ok and _t0 < _best and _t0 >= 0:
                _best = _t0
        return _best

    def visible(self, x, y, world=None):
        """点位是否可见（供渲染层跳过视野外实体 / AI 视线判定）。"""
        if not self.enabled or not self.poly:
            return True
        _cx, _cy = self.center
        if math.hypot(x - _cx, y - _cy) > self.radius * 1.05:
            return False
        if world is not None and hasattr(world, 'obstacle_candidates'):
            for _o in world.obstacle_candidates(_cx, _cy, x, y):
                try:
                    from world import GameWorld
                    if GameWorld.blocks_sight(_o) and \
                       GameWorld.segment_hits_rect(_cx, _cy, x, y, _o['rect']):
                        return False
                except Exception:
                    pass
        return True

    def update(self, game, player, camera, scale, cam_x, cam_y):
        """每 3 帧重建低分辨率暗色遮罩 + 可见多边形洞。"""
        self.frame += 1
        if not self.enabled:
            self.mask = None
            return
        if self.frame % UPDATE_INTERVAL != 0 and self.mask is not None:
            return
        _sw, _sh = game.scaled_width, game.scaled_height
        _mw, _mh = max(1, _sw // MASK_DIV), max(1, _sh // MASK_DIV)
        _px, _py = float(getattr(player, 'x', 0)), float(getattr(player, 'y', 0))
        self.center = (_px, _py)
        _world = getattr(game, 'world', None)
        _obs = []
        if _world is not None and hasattr(_world, 'obstacle_candidates'):
            try:
                _obs = _world.obstacle_candidates(
                    _px - self.radius, _py - self.radius,
                    _px + self.radius, _py + self.radius)
            except Exception:
                _obs = list(getattr(_world, 'obstacles', []))[:80]
        _poly = []
        for _i in range(RAY_COUNT):
            _a = 2 * math.pi * _i / RAY_COUNT
            _d = self._ray_hit(_px, _py, _a, self.radius, _obs)
            _wx, _wy = _px + math.cos(_a) * _d, _py + math.sin(_a) * _d
            _poly.append(((_wx - cam_x) * scale / MASK_DIV,
                          (_wy - cam_y) * scale / MASK_DIV))
        self.poly = _poly
        _m = pygame.Surface((_mw, _mh), pygame.SRCALPHA)
        _m.fill((4, 6, 12, self.darkness))
        if len(_poly) >= 3:
            try:
                pygame.draw.polygon(_m, (0, 0, 0, 0), _poly)
                # 视野边缘柔化：再画一圈半透明描边
                pygame.draw.polygon(_m, (0, 0, 0, 40), _poly, 2)
            except Exception:
                pass
        self.mask = _m

    def draw(self, screen):
        if not self.enabled or self.mask is None:
            return
        try:
            _big = pygame.transform.smoothscale(
                self.mask, (screen.get_width(), screen.get_height()))
            screen.blit(_big, (0, 0))
        except Exception:
            pass


def GameWorldBlocksSight(obs):
    try:
        from world import GameWorld
        return GameWorld.blocks_sight(obs)
    except Exception:
        return True
