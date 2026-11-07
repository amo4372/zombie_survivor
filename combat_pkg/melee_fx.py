# -*- coding: utf-8 -*-
"""近战挥砍 / 剑气统一渲染系统（v2.9.12）

设计目标
--------
1. **所有近战武器共用一套**：匕首 / 棒球棍 / 电锯 / 死神镰刀 / 拳头…
   按武器给出配色、段数、剑气尺寸，不再各写各的刀光。
2. **有节奏的多段连斩**（武侠感）：一斩横扫 → 二斩反撩 → 三斩力劈，
   每段含「起手蓄力 → 斩击 → 收势残影」，段间有停顿。
3. **剑气**：每段斩击末端向面朝方向射出月牙剑气，带拖尾、残影、
   流光与渐隐；死神镰刀剑气更大更多、紫色系。
4. **性能**：辉光只用**局部小 Surface**（尺寸随半径、有上限），
   绝不分配全屏 Surface；分屏各视口独立传 viewport_x。
5. **纯视觉**：剑气不额外结算伤害，伤害仍走原有扇形判定，
   避免改变平衡 —— 画面所见即判定范围。

用法
----
    game.melee_fx.spawn_slash(x, y, angle_rad, radius, weapon, combo, owner)
    game.melee_fx.update(dt)                       # 主循环
    game.melee_fx.draw(screen, cam_x, cam_y, scale, viewport_x)
"""
import math
import pygame
from collections import deque

# ---------------------------------------------------------------- 武器样式
# 每种近战武器一套：(主刃色, 亮刃色, 辉光色, 段数, 节奏时长, 剑气比例, 剑气数量)
_DEFAULT_STYLE = {
    "name": "拳刃", "blade": (215, 225, 240), "edge": (255, 255, 255),
    "glow": (120, 175, 255), "segs": 3, "duration": 0.36,
    "qi_scale": 0.55, "qi_count": 2, "saw": False,
}

WEAPON_STYLES = {
    "KNIFE": {
        "name": "匕首", "blade": (190, 205, 225), "edge": (255, 255, 255),
        "glow": (110, 190, 255), "segs": 3, "duration": 0.24,
        "qi_scale": 0.45, "qi_count": 2, "saw": False,
    },
    "BAT": {
        "name": "棒球棍", "blade": (185, 130, 75), "edge": (255, 215, 145),
        "glow": (255, 150, 55), "segs": 2, "duration": 0.44,
        "qi_scale": 0.70, "qi_count": 1, "saw": False,
    },
    "CHAINSAW": {
        "name": "电锯", "blade": (255, 125, 45), "edge": (255, 230, 130),
        "glow": (255, 80, 30), "segs": 4, "duration": 0.20,
        "qi_scale": 0.40, "qi_count": 1, "saw": True,
    },
    "SCYTHE": {
        "name": "死神镰刀", "blade": (185, 75, 225), "edge": (255, 215, 255),
        "glow": (150, 45, 220), "segs": 3, "duration": 0.40,
        "qi_scale": 1.35, "qi_count": 3, "saw": False,
    },
    "MACHETE": {
        "name": "砍刀", "blade": (165, 200, 185), "edge": (240, 255, 245),
        "glow": (90, 220, 180), "segs": 3, "duration": 0.34,
        "qi_scale": 0.75, "qi_count": 2, "saw": False,
    },
    "FIRE_AXE": {
        "name": "消防斧", "blade": (220, 80, 55), "edge": (255, 200, 120),
        "glow": (255, 110, 40), "segs": 2, "duration": 0.46,
        "qi_scale": 0.80, "qi_count": 1, "saw": False,
    },
    "AXE": {
        "name": "战斧", "blade": (200, 95, 60), "edge": (255, 205, 135),
        "glow": (240, 120, 50), "segs": 2, "duration": 0.44,
        "qi_scale": 0.78, "qi_count": 1, "saw": False,
    },
    "STUN_BATON": {
        "name": "电击棒", "blade": (90, 200, 255), "edge": (235, 250, 255),
        "glow": (60, 150, 255), "segs": 3, "duration": 0.28,
        "qi_scale": 0.60, "qi_count": 2, "saw": False,
    },
    "ELECTRIC": {
        "name": "电击武器", "blade": (110, 190, 255), "edge": (240, 250, 255),
        "glow": (70, 140, 255), "segs": 3, "duration": 0.28,
        "qi_scale": 0.60, "qi_count": 2, "saw": False,
    },
    "FIST": {
        "name": "拳头", "blade": (225, 195, 165), "edge": (255, 245, 225),
        "glow": (255, 190, 120), "segs": 3, "duration": 0.30,
        "qi_scale": 0.35, "qi_count": 1, "saw": False,
    },
}

# 三段节奏：(起始偏移 rad, 扫过弧度 rad)。段数更多时循环取用并缩小幅度
_SEG_RHYTHM = [(-0.95, 1.55), (0.80, -1.45), (-0.35, 1.15), (0.55, -1.05)]


def style_for(weapon=None) -> dict:
    """按武器对象/枚举名取样式；未命中用默认（拳头系）"""
    name = ""
    try:
        wt = getattr(weapon, "weapon_type", weapon)
        name = str(getattr(wt, "name", wt) or "").upper()
    except Exception:
        name = ""
    for key, st in WEAPON_STYLES.items():
        if key in name:
            return st
    # 中文名兜底
    cn = str(getattr(weapon, "name", "") or "")
    for key, st in WEAPON_STYLES.items():
        if st["name"] and st["name"] in cn:
            return st
    return _DEFAULT_STYLE


def _dim(c, k):
    """颜色按系数调暗/调亮（避免每帧建带 alpha 的 Surface）"""
    try:
        return tuple(max(0, min(255, int(v * k))) for v in c[:3])
    except Exception:
        return (200, 200, 200)


def _mix(a, b, k):
    try:
        return tuple(int(a[i] * (1 - k) + b[i] * k) for i in range(3))
    except Exception:
        return a


def _arc(screen, color, cx, cy, r, a0, a1, width):
    """安全画弧（角度可能反向 / 半径为 0）"""
    if r <= 0:
        return
    lo, hi = (a0, a1) if a1 >= a0 else (a1, a0)
    if hi - lo < 0.002:
        return
    try:
        pygame.draw.arc(screen, color,
                        pygame.Rect(int(cx - r), int(cy - r),
                                    int(r * 2), int(r * 2)),
                        lo, hi, max(1, int(width)))
    except Exception:
        pass


# ---------------------------------------------------------------- 月牙剑气
class SwordQi:
    """飞行的月牙剑气（纯视觉；伤害仍由近战扇形判定统一结算）"""

    MAX_TRAIL = 9

    def __init__(self, x, y, angle, style, scale=1.0, radius=60.0,
                 speed=340.0, life=0.42):
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)
        self.style = style
        self.qi_scale = float(scale)
        self.radius = max(12.0, float(radius))
        self.speed = float(speed)
        self.life = float(life)
        self.max_life = float(life)
        self.trail = deque(maxlen=self.MAX_TRAIL)
        self.spin = 0.0
        self.alive = True

    def update(self, dt):
        self.trail.append((self.x, self.y))
        self.x += math.cos(self.angle) * self.speed * dt
        self.y += math.sin(self.angle) * self.speed * dt
        self.spin += dt * 9.0
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def is_alive(self):
        return self.alive and self.life > 0

    def draw(self, screen, cam_x, cam_y, scale, viewport_x=0):
        k = max(0.0, min(1.0, self.life / self.max_life))
        if k <= 0:
            return
        px = int((self.x - cam_x) * scale) + viewport_x
        py = int((self.y - cam_y) * scale)
        st = self.style
        blade = _dim(st["blade"], 0.78 + 0.22 * k)   # 主色饱和，不被白刃吃掉
        edge = _dim(st["edge"], 0.55 + 0.45 * k)
        glow = st["glow"]
        r = max(6, int(self.radius * self.qi_scale * scale))
        r = min(r, 150)                       # 局部 Surface 尺寸上限
        a = self.angle + math.sin(self.spin) * 0.18

        # ---- 1) 拖尾：由旧到新渐粗渐亮（零 Surface）
        pts = [(int((tx - cam_x) * scale) + viewport_x,
                int((ty - cam_y) * scale)) for tx, ty in self.trail]
        if len(pts) >= 2:
            n = len(pts)
            for i in range(1, n):
                f = i / n
                _c = _mix(_dim(glow, 0.55), blade, f * 0.75)
                try:
                    pygame.draw.line(screen, _c, pts[i - 1], pts[i],
                                     max(1, int((1 + 5 * f) * scale)))
                except Exception:
                    pass
        # ---- 2) 残影月牙（拖尾上的两个旧位置，更小更暗）
        if len(pts) >= 4:
            for idx, f in ((1, 0.42), (3, 0.62)):
                if idx < len(pts):
                    _arc(screen, _dim(glow, 0.30 + 0.25 * f),
                         pts[idx][0], pts[idx][1],
                         max(3, int(r * f * 0.6)), a - 1.5, a + 0.7,
                         max(1, int(2 * scale)))
        # ---- 3) 辉光（局部小 Surface，尺寸受控）
        try:
            # 辉光聚焦在月牙附近；大剑气（死神镰刀）会同时有多道，
            # 按 qi_scale 反向衰减 alpha，避免叠成一整片色盘。
            _soft = k / max(1.0, self.qi_scale)
            gr = min(int(r * 0.70) + 4, 88)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*glow[:3], int(58 * _soft)), (gr, gr), gr)
            pygame.draw.circle(gs, (*blade[:3], int(34 * _soft)), (gr, gr),
                               max(1, gr - 5))
            screen.blit(gs, (int(px - gr), int(py - gr)))
        except Exception:
            pass
        # ---- 4) 三层月牙：外深刃 / 主刃 / 内白刃
        _arc(screen, _dim(blade, 0.55), px, py, r,
             a - 2.0, a + 1.15, max(4, int(8 * scale)))
        _arc(screen, blade, px, py, r, a - 1.8, a + 1.0,
             max(3, int(6 * scale)))
        _arc(screen, _dim(edge, 0.85), px, py, max(3, r - 6),
             a - 1.55, a + 0.75, max(1, int(2 * scale)))
        # ---- 5) 刃尖流光（运动反方向）
        tx = px - math.cos(self.angle) * r * 1.3
        ty = py - math.sin(self.angle) * r * 1.3
        try:
            pygame.draw.line(screen, _dim(glow, 0.85 * k), (px, py),
                             (int(tx), int(ty)), max(1, int(4 * scale)))
            pygame.draw.line(screen, _dim(blade, 0.9 * k), (px, py),
                             (int(tx * 0.5 + px * 0.5), int(ty * 0.5 + py * 0.5)),
                             max(1, int(2 * scale)))
        except Exception:
            pass
        # ---- 6) 中心亮点 + 刃口火花
        try:
            pygame.draw.circle(screen, edge, (px, py), max(1, int(3 * scale)))
            for off in (-1.25, 0.65):
                sx = px + math.cos(a + off) * r
                sy = py + math.sin(a + off) * r
                pygame.draw.circle(screen, _dim(edge, 0.8 * k),
                                   (int(sx), int(sy)), max(1, int(2 * scale)))
        except Exception:
            pass


# ---------------------------------------------------------------- 多段挥砍
class MeleeSlash:
    """一次挥砍 = 有节奏的多段连斩 + 每段射出的剑气"""

    def __init__(self, x, y, angle, radius, style=None, combo=1, owner=None):
        self.x0 = float(x)
        self.y0 = float(y)
        self.angle = float(angle)          # 弧度
        self.radius = max(24.0, float(radius))
        self.style = style or _DEFAULT_STYLE
        self.combo = max(1, int(combo or 1))
        self.owner = owner
        self.duration = max(0.16, min(0.62, float(self.style["duration"])))
        self.t = 0.0
        self.n = max(1, int(self.style["segs"]))
        self._emitted = set()
        self.alive = True

    @property
    def x(self):
        return float(getattr(self.owner, "x", self.x0)) if self.owner else self.x0

    @property
    def y(self):
        return float(getattr(self.owner, "y", self.y0)) if self.owner else self.y0

    def update(self, dt):
        """推进节奏，返回本帧应发射的剑气列表"""
        self.t += dt
        out = []
        seg_f = min(float(self.n), self.t / self.duration * self.n)
        cur = min(self.n - 1, int(seg_f))
        local = seg_f - cur
        # 每段斩击出鞘瞬间（段内 0.30）射出剑气
        if local >= 0.30 and cur not in self._emitted:
            self._emitted.add(cur)
            st = self.style
            count = max(1, int(st["qi_count"]))
            off, sweep = _SEG_RHYTHM[cur % len(_SEG_RHYTHM)]
            a = self.angle + off + sweep * 0.72
            for i in range(count):
                spread = (i - (count - 1) / 2.0) * 0.20
                qi = SwordQi(
                    self.x + math.cos(self.angle) * self.radius * 0.45,
                    self.y + math.sin(self.angle) * self.radius * 0.45,
                    a + spread, st, scale=st["qi_scale"],
                    radius=self.radius,
                    speed=270.0 + 130.0 * st["qi_scale"],
                    life=0.30 + 0.16 * st["qi_scale"])
                out.append(qi)
        if self.t >= self.duration:
            self.alive = False
        return out

    def is_alive(self):
        return self.alive and self.t < self.duration

    def draw(self, screen, cam_x, cam_y, scale, viewport_x=0, font=None):
        px = int((self.x - cam_x) * scale) + viewport_x
        py = int((self.y - cam_y) * scale)
        r = max(10, int(self.radius * scale))
        r = min(r, 620)                      # 防止极端范围撑爆 Surface
        st = self.style
        blade, edge, glow = st["blade"], st["edge"], st["glow"]
        seg_f = min(float(self.n), self.t / self.duration * self.n)
        cur = min(self.n - 1, int(seg_f))
        local = seg_f - cur

        # ---- 已完成段：淡残影弧
        for si in range(cur):
            off, sweep = _SEG_RHYTHM[si % len(_SEG_RHYTHM)]
            a0 = self.angle + off
            _arc(screen, _dim(blade, 0.38), px, py, r,
                 a0, a0 + sweep, max(1, int(2 * scale)))

        off, sweep = _SEG_RHYTHM[cur % len(_SEG_RHYTHM)]
        a0 = self.angle + off
        a1 = a0 + sweep * min(1.0, local * 1.3)

        # ---- 起手蓄力：收缩的金色预备弧 + 聚光点
        if local < 0.20 and local > 0:
            k = local / 0.20
            rr = max(6, int(r * (1.0 - 0.32 * k)))
            _arc(screen, (255, 205 + int(30 * k), 100), px, py, rr,
                 a0 - 0.42, a0 + 0.42, max(1, int(3 * scale)))
            try:
                pygame.draw.circle(screen, (255, 230, 150),
                                   (int(px + math.cos(a0) * rr),
                                    int(py + math.sin(a0) * rr)),
                                   max(1, int((2 + 3 * k) * scale)))
            except Exception:
                pass

        # ---- 斩击：半透明扇形（局部 Surface，仅当前段一个）
        if local >= 0.15 and r > 0:
            fade = min(1.0, (1.0 - max(0.0, local - 0.82) / 0.18))
            try:
                pad = 4
                surf = pygame.Surface((r * 2 + pad * 2, r * 2 + pad * 2),
                                      pygame.SRCALPHA)
                cc = r + pad
                pts = [(cc, cc)]
                steps = 14
                for i in range(steps + 1):
                    aa = a0 + (a1 - a0) * i / steps
                    pts.append((cc + math.cos(aa) * r, cc + math.sin(aa) * r))
                pygame.draw.polygon(surf, (*glow[:3], int(30 * fade)), pts)
                pygame.draw.polygon(surf, (*blade[:3], int(18 * fade)), pts,
                                    max(1, int(2 * scale)))
                screen.blit(surf, (int(px - cc), int(py - cc)))
            except Exception:
                pass
            # 三层刀光弧
            _arc(screen, glow, px, py, r, a0, a1,
                 max(3, int(11 * scale)))           # 外辉光：武器专属色
            _arc(screen, blade, px, py, r, a0, a1,
                 max(2, int(9 * scale)))            # 主刃：饱和色带加宽
            _arc(screen, _dim(edge, 0.92), px, py, max(4, r - 5),
                 a0 + 0.10, a1 - 0.10, max(1, int(2 * scale)))
            # 刀锋线 + 端点高光
            try:
                ex = px + math.cos(a1) * r
                ey = py + math.sin(a1) * r
                pygame.draw.line(screen, edge, (px, py), (int(ex), int(ey)),
                                 max(1, int(3 * scale)))
                pygame.draw.circle(screen, edge,
                                   (int(ex), int(ey)), max(2, int(4 * scale)))
                pygame.draw.circle(screen, glow, (int(ex), int(ey)),
                                   max(3, int(10 * scale)), max(1, int(2 * scale)))
                # 沿刃口的火花（用武器色，不再一片白）
                for f in (0.25, 0.55, 0.85):
                    aa = a0 + (a1 - a0) * f
                    sx = px + math.cos(aa) * r * (0.78 + 0.18 * f)
                    sy = py + math.sin(aa) * r * (0.78 + 0.18 * f)
                    pygame.draw.circle(screen, blade,
                                       (int(sx), int(sy)),
                                       max(1, int(2 * scale)))
            except Exception:
                pass

        # ---- 电锯：旋转锯齿
        if st.get("saw"):
            for i in range(8):
                aa = pygame.time.get_ticks() / 45.0 + i * math.pi / 4
                try:
                    pygame.draw.circle(screen, (255, 110, 90),
                                       (int(px + math.cos(aa) * r * 0.68),
                                        int(py + math.sin(aa) * r * 0.68)),
                                       max(1, int(3 * scale)))
                except Exception:
                    pass

        # ---- 连击强化：外圈金环 + 段数指示
        if self.combo >= 3:
            _arc(screen, (255, 210, 90), px, py, max(6, int(r * 0.32)),
                 0, math.pi * 2, max(1, int(2 * scale)))
        for i in range(self.n):
            c = (255, 225, 120) if i == cur else _dim(glow, 0.35)
            try:
                pygame.draw.circle(screen, c,
                                   (px - (self.n - 1) * 7 + i * 14,
                                    py + int(18 * scale)),
                                   max(1, int(3 * scale)))
            except Exception:
                pass
        if font and self.combo >= 3:
            try:
                t = font.render(f"连击 x{self.combo}", True, (255, 220, 120))
                screen.blit(t, (int(px - t.get_width() / 2),
                                int(py - r * 0.55)))
            except Exception:
                pass


# ---------------------------------------------------------------- 管理器
class MeleeFxSystem:
    """挂在 game.melee_fx 上：生成 / 推进 / 绘制"""

    MAX_SLASH = 12
    MAX_QI = 64

    def __init__(self, game=None):
        self.game = game
        self.slashes = []
        self.qis = []

    def clear(self):
        self.slashes.clear()
        self.qis.clear()

    def spawn_slash(self, x, y, angle, radius, weapon=None, combo=1,
                    owner=None):
        # 允许调用方直接传 style_for() 的结果（dict），避免"传样式却按武器解析"
        st = (weapon if isinstance(weapon, dict) and "blade" in weapon
              else style_for(weapon))
        sl = MeleeSlash(x, y, angle, radius, st, combo=combo, owner=owner)
        self.slashes.append(sl)
        if len(self.slashes) > self.MAX_SLASH:
            del self.slashes[:len(self.slashes) - self.MAX_SLASH]
        return sl

    def update(self, dt):
        for sl in self.slashes[:]:
            try:
                self.qis.extend(sl.update(dt))
            except Exception:
                pass
            if not sl.is_alive():
                self.slashes.remove(sl)
        for qi in self.qis[:]:
            try:
                qi.update(dt)
            except Exception:
                pass
            if not qi.is_alive():
                self.qis.remove(qi)
        if len(self.qis) > self.MAX_QI:
            del self.qis[:len(self.qis) - self.MAX_QI]

    def draw(self, screen, cam_x, cam_y, scale, viewport_x=0, font=None):
        # 剑气先画（在世界层，刀光之下）
        for qi in self.qis:
            try:
                qi.draw(screen, cam_x, cam_y, scale, viewport_x)
            except Exception:
                pass
        for sl in self.slashes:
            try:
                sl.draw(screen, cam_x, cam_y, scale, viewport_x, font)
            except Exception:
                pass


# ---------------------------------------------------------------- 投射物剑气
def draw_sword_qi_projectile(screen, px, py, proj, scale, viewport_x=0):
    """死神之镰等**真实剑气投射物**的增强绘制（有伤害的那种）。

    与 MeleeFxSystem 里的纯视觉剑气共用同一套月牙语言，但额外使用
    proj.trail 做长拖尾、按飞行时间做旋转流光。
    """
    import math as _m
    st = {
        "name": "剑气", "blade": tuple(proj.color[:3]) if proj.color else (185, 75, 225),
        "edge": (255, 225, 255), "glow": (150, 50, 215),
    }
    col = st["blade"]
    glow = st["glow"]
    edge = st["edge"]
    _dir = _m.atan2(proj.vy, proj.vx)
    spin = _m.radians((pygame.time.get_ticks() / 8.0) % 360)
    a = _dir + _m.sin(spin) * 0.42
    r = max(14, min(150, int(proj.size * 2.0 * scale)))

    # 长拖尾（proj.trail 已由 Projectile.update 记录）
    trail = list(getattr(proj, "trail", []) or [])[-9:]
    # 调用方传的是屏幕坐标；拖尾用 trail 世界坐标差 × scale 反推相对位移
    if len(trail) >= 2:
        x0w, y0w = trail[-1]
        for i in range(1, len(trail)):
            tx, ty = trail[i - 1]
            nx, ny = trail[i]
            # 用世界坐标差 × scale 得到屏幕相对位移
            p0 = (int(px + (tx - x0w) * scale) + viewport_x,
                  int(py + (ty - y0w) * scale))
            p1 = (int(px + (nx - x0w) * scale) + viewport_x,
                  int(py + (ny - y0w) * scale))
            f = i / len(trail)
            try:
                pygame.draw.line(screen, _mix(_dim(glow, 0.4), edge, f * 0.8),
                                 p0, p1, max(1, int((1 + 6 * f) * scale)))
            except Exception:
                pass
        # 残影月牙
        for idx in (1, 3):
            if idx < len(trail):
                tx, ty = trail[idx]
                hx = int(px + (tx - x0w) * scale) + viewport_x
                hy = int(py + (ty - y0w) * scale)
                _arc(screen, _dim(glow, 0.35), hx, hy,
                     max(3, int(r * 0.45)), a - 1.4, a + 0.6,
                     max(1, int(2 * scale)))

    # 辉光（局部小 Surface）
    try:
        gr = min(int(r * 0.70) + 4, 88)
        gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*glow[:3], 60), (gr, gr), gr)
        pygame.draw.circle(gs, (*col[:3], 38), (gr, gr), max(1, gr - 5))
        screen.blit(gs, (int(px - gr + viewport_x), int(py - gr)))
    except Exception:
        pass
    cx = px + viewport_x
    _arc(screen, _dim(col, 0.55), cx, py, r, a - 2.0, a + 1.15,
         max(4, int(9 * scale)))
    _arc(screen, col, cx, py, r, a - 1.8, a + 1.0, max(3, int(6 * scale)))
    _arc(screen, edge, cx, py, max(3, r - 6), a - 1.55, a + 0.75,
         max(2, int(3 * scale)))
    tx = cx - _m.cos(_dir) * r * 1.35
    ty = py - _m.sin(_dir) * r * 1.35
    try:
        pygame.draw.line(screen, _dim(glow, 0.65), (cx, py),
                         (int(tx), int(ty)), max(1, int(4 * scale)))
        pygame.draw.line(screen, _dim(edge, 0.6), (cx, py),
                         (int((tx + cx) / 2), int((ty + py) / 2)),
                         max(1, int(2 * scale)))
        pygame.draw.circle(screen, (255, 255, 255), (int(cx), int(py)),
                           max(1, int(3 * scale)))
    except Exception:
        pass


__all__ = ["WEAPON_STYLES", "style_for", "MeleeSlash", "SwordQi",
           "MeleeFxSystem", "draw_sword_qi_projectile"]
