#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI组件模块 - 完整重写版：技能卡选择、触控按钮位置调整、半透明范围圈"""

import pygame
import math
import random
import os
import time
from config import *


class DeathAura:
    """敌人死亡光环效果"""
    def __init__(self, x, y, color, max_radius=80, duration=1.5):
        self.x = x
        self.y = y
        self.color = color
        self.max_radius = max_radius
        self.duration = duration
        self.lifetime = duration
        self.rings = 2

    def update(self, dt):
        self.lifetime -= dt
        return self.lifetime > 0

    def draw(self, screen, camera_x, camera_y, scale=1.0):
        progress = 1.0 - (self.lifetime / self.duration)
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        for i in range(self.rings):
            ring_progress = min(1.0, progress * (self.rings - i) / self.rings)
            radius = int(self.max_radius * ring_progress * scale)
            alpha = int(200 * (1.0 - ring_progress))
            if radius > 0:
                ring_color = tuple(min(255, int(c * (1.0 - ring_progress * 0.5))) for c in self.color[:3])
                pygame.draw.circle(screen, ring_color, (px, py), radius, max(1, int(2 * scale)))
                if ring_progress < 0.5:
                    fill_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                    pygame.draw.circle(fill_surf, (*ring_color[:3], alpha // 2), (radius, radius), radius)
                    screen.blit(fill_surf, (px - radius, py - radius))


class DamageNumber:
    # 伤害类型对应的颜色
    TYPE_COLORS = {
        "normal": WHITE,
        "melee": (255, 220, 180),
        "ranged": (180, 220, 255),
        "crit": (255, 200, 50),
        "dot": (255, 120, 80),
        "fire": (255, 100, 20),
        "poison": (120, 200, 50),
        "bleed": (200, 30, 30),
        "corrosion": (150, 200, 50),
        "freeze": (100, 200, 255),
        "explosion": (255, 150, 0),
        "aoe": (255, 180, 50),
        "magic": (200, 100, 255),
        "heal": (80, 255, 120),
    }

    def __init__(self, x, y, damage, color=None, is_crit=False, damage_type="normal"):
        self.x = x
        self.y = y
        self.damage = damage
        self.damage_type = damage_type
        self.is_crit = is_crit
        self._surf_cache = None  # 渲染缓存：字体surface只生成一次，避免大伤害时每帧重渲染
        # 暴击优先用暴击色
        if is_crit:
            self.color = self.TYPE_COLORS["crit"]
        elif color is not None:
            self.color = color
        else:
            self.color = self.TYPE_COLORS.get(damage_type, WHITE)
        self.lifetime = 1.0
        self.vy = -2
        # 是否为buff持续伤害
        self.is_dot = damage_type in ("fire", "poison", "bleed", "corrosion", "freeze", "dot")
        # 根据伤害大小计算字号倍率（整体放大20%）
        if damage < 10:
            self.size_mult = 0.85
        elif damage < 30:
            self.size_mult = 1.0
        elif damage < 60:
            self.size_mult = 1.2
        elif damage < 100:
            self.size_mult = 1.4
        elif damage < 200:
            self.size_mult = 1.65
        else:
            self.size_mult = 2.0
        # 暴击额外放大
        if is_crit:
            self.size_mult *= 1.35
        # buff持续伤害额外放大15%
        if self.is_dot:
            self.size_mult *= 1.15

    def update(self, dt):
        self.y += self.vy * dt * 60
        self.vy += 0.05 * dt * 60
        self.lifetime -= dt

    def draw(self, screen, font, camera_x=0, camera_y=0, scale=1.0):
        alpha = int(255 * self.lifetime)
        # 字体surface缓存：首次渲染一次，之后每帧只set_alpha（避免大伤害时每帧font.render+smoothscale卡顿）
        if self._surf_cache is None:
            import pygame
            text = f"{int(self.damage)}" + ("!" if self.is_crit else "")
            text_surf = font.render(text, True, self.color)
            if self.size_mult != 1.0:
                orig_w, orig_h = text_surf.get_size()
                new_w = max(4, int(orig_w * self.size_mult))
                new_h = max(4, int(orig_h * self.size_mult))
                text_surf = pygame.transform.smoothscale(text_surf, (new_w, new_h))
            self._surf_cache = text_surf
        text_surf = self._surf_cache
        text_surf.set_alpha(alpha)
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        # 居中对齐
        text_rect = text_surf.get_rect(center=(px, py))
        # buff伤害数字添加描边增强可读性
        if self.is_dot and self.lifetime > 0.3:
            import pygame
            outline = pygame.Surface(text_surf.get_size(), pygame.SRCALPHA)
            outline.fill((0, 0, 0, 80))
            outline.blit(text_surf, (0, 0))
            screen.blit(outline, text_rect)
        else:
            screen.blit(text_surf, text_rect)

    def is_alive(self):
        return self.lifetime > 0


class FloatingText:
    def __init__(self, x, y, text, color=YELLOW, lifetime=2.0):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.vy = -1.5
        self._surf_cache = None

    def update(self, dt):
        self.y += self.vy * dt * 60
        self.lifetime -= dt

    def draw(self, screen, font, camera_x=0, camera_y=0, scale=1.0):
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        if self._surf_cache is None:
            self._surf_cache = font.render(self.text, True, self.color)
        text_surf = self._surf_cache
        text_surf.set_alpha(alpha)
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        screen.blit(text_surf, (px, py))

    def is_alive(self):
        return self.lifetime > 0


class SlashArc:
    """刀光弧斩特效：王某死神镰刀横扫/处决 + 枪械曳光"""
    def __init__(self, x, y, angle, radius, color, lifetime=0.45,
                 kind="scythe", start_radius=0, end_angle_offset=1.0):
        self.x = x
        self.y = y
        self.angle = angle          # 主方向（弧度）
        self.radius = radius        # 最大半径
        self.start_radius = start_radius
        self.end_angle_offset = end_angle_offset  # 弧的结束角偏移（相对主方向）
        self.color = color
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.kind = kind            # scythe=弧形刀光 / tracer=直线曳光

    def update(self, dt):
        self.lifetime -= dt

    def draw(self, screen, camera_x=0, camera_y=0, scale=1.0):
        if self.lifetime <= 0:
            return
        progress = 1.0 - (self.lifetime / self.max_lifetime)  # 0→1
        alpha = int(220 * (1.0 - progress))
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        if self.kind == "tracer":
            # 直线曳光：从中心向主方向延伸
            length = int(self.radius * (0.4 + 0.6 * progress) * scale)
            ex = px + math.cos(self.angle) * length
            ey = py + math.sin(self.angle) * length
            mid = px + math.cos(self.angle) * (length * 0.45)
            midy = py + math.sin(self.angle) * (length * 0.45)
            pygame.draw.line(screen, (*self.color[:3], alpha), (px, py), (int(mid), int(midy)), max(2, int(4 * scale)))
            pygame.draw.line(screen, (255, 255, 255), (int(mid), int(midy)), (int(ex), int(ey)), max(1, int(2 * scale)))
            return
        # 弧形刀光：半径随进度扩张
        r = int((self.start_radius + (self.radius - self.start_radius) * progress) * scale)
        w = max(3, int(8 * scale))
        surf = pygame.Surface((r * 2 + w * 2, r * 2 + w * 2), pygame.SRCALPHA)
        cc = r + w
        start_a = self.angle - 2.4
        end_a = self.angle + self.end_angle_offset
        # 外发光
        pygame.draw.arc(surf, (*self.color[:3], alpha // 3), (w, w, r * 2, r * 2), start_a, end_a, w + 3)
        # 主刃光
        pygame.draw.arc(surf, (*self.color[:3], alpha), (w, w, r * 2, r * 2), start_a, end_a, w)
        # 内亮刃
        pygame.draw.arc(surf, (255, 255, 255), (w, w, r * 2, r * 2), start_a + 0.15, end_a - 0.15, max(2, w // 3))
        screen.blit(surf, (px - cc, py - cc))

    def is_alive(self):
        return self.lifetime > 0


class Particle:
    def __init__(self, x, y, color, size, velocity, lifetime):
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        self.vx, self.vy = velocity
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.gravity = 0.1

    def update(self, dt):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.vy += self.gravity * dt * 60
        self.lifetime -= dt
        self.size = max(1, self.size * (self.lifetime / self.max_lifetime))

    def draw(self, screen, camera_x=0, camera_y=0, scale=1.0):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(1, int(self.size * scale))
        pygame.draw.circle(screen, self.color, (px, py), s)

    def is_alive(self):
        return self.lifetime > 0


class ParticleSystem:
    MAX_PARTICLES = 1200  # v2.0.9：粒子总数上限，防止大规模AOE/大伤害时粒子爆炸导致卡顿

    def __init__(self):
        self.particles = []
        self.death_auras = []
        self.quality = "balanced"  # performance / balanced / quality，决定粒子密度

    def _density(self, count):
        """按画质档位调整粒子数量（不砍粒子，只随画质缩放密度）"""
        try:
            n = int(count)
        except (TypeError, ValueError):
            n = 5
        if self.quality == "performance":
            return max(1, int(n * 0.4))
        elif self.quality == "quality":
            return int(n * 1.4)
        return n

    def spawn(self, x, y, color, count=5, size_range=(2, 6),
              velocity_range=(-3, 3), lifetime_range=(0.3, 1.0)):
        # 兼容 float 参数（mod 可能传入浮点值）
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 5
        count = self._density(count)
        try:
            lo, hi = int(size_range[0]), int(size_range[1])
        except (TypeError, ValueError, IndexError):
            lo, hi = 2, 6
        for _ in range(count):
            if len(self.particles) >= self.MAX_PARTICLES:
                return  # 达上限丢弃新增粒子，保证渲染/更新有界
            size = random.randint(lo, hi)
            vx = random.uniform(*velocity_range)
            vy = random.uniform(*velocity_range)
            lifetime = random.uniform(*lifetime_range)
            self.particles.append(Particle(x, y, color, size, (vx, vy), lifetime))

    def spawn_particle(self, x, y, vx, vy, color, lifetime, size):
        """生成单个粒子，带固定速度（用于环形冲击波、拖尾等定向效果）"""
        if len(self.particles) >= self.MAX_PARTICLES:
            return
        self.particles.append(Particle(x, y, color, size, (vx, vy), lifetime))

    def spawn_explosion(self, x, y, color, count=20):
        self.spawn(x, y, color, count, (3, 10), (-8, 8), (0.5, 1.5))

    def add(self, x, y, color, count=5, size_range=(2, 6),
            velocity_range=(-3, 3), lifetime_range=(0.3, 1.0)):
        """Mod 兼容别名：等同于 spawn()"""
        self.spawn(x, y, color, count, size_range, velocity_range, lifetime_range)

    def spawn_blood(self, x, y, count=8):
        self.spawn(x, y, RED, count, (2, 5), (-4, 4), (0.3, 0.8))

    def spawn_heal_particles(self, x, y, count=15):
        """生成治疗粒子（绿色向上飘动）"""
        count = self._density(count)
        for _ in range(count):
            if len(self.particles) >= self.MAX_PARTICLES:
                return
            size = random.randint(3, 7)
            vx = random.uniform(-1.5, 1.5)
            vy = random.uniform(-4, -1.5)
            lifetime = random.uniform(0.5, 1.2)
            self.particles.append(Particle(x, y, LIME, size, (vx, vy), lifetime))

    def spawn_death_aura(self, x, y, color):
        self.death_auras.append(DeathAura(x, y, color))

    def update(self, dt):
        for p in self.particles[:]:
            p.update(dt)
            if not p.is_alive():
                self.particles.remove(p)
        for aura in self.death_auras[:]:
            if not aura.update(dt):
                self.death_auras.remove(aura)

    def draw(self, screen, camera_x=0, camera_y=0, scale=1.0):
        for aura in self.death_auras:
            aura.draw(screen, camera_x, camera_y, scale)
        for p in self.particles:
            p.draw(screen, camera_x, camera_y, scale)


def draw_dashed_line(surface, color, start_pos, end_pos, dash_length=10, gap_length=5, width=1):
    x1, y1 = start_pos
    x2, y2 = end_pos
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    dx_unit = dx / dist
    dy_unit = dy / dist
    step = dash_length + gap_length
    current = 0
    while current < dist:
        seg_start = (x1 + dx_unit * current, y1 + dy_unit * current)
        seg_end_dist = min(current + dash_length, dist)
        seg_end = (x1 + dx_unit * seg_end_dist, y1 + dy_unit * seg_end_dist)
        pygame.draw.line(surface, color, seg_start, seg_end, width)
        current += step
