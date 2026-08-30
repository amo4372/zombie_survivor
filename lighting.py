#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动态光照渲染系统 - 为游戏添加黑暗氛围与动态光源"""

import math
import pygame
from config import *


class Light:
    """单个光源"""
    def __init__(self, x, y, radius, color, intensity=1.0, lifetime=None, flicker=False):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color  # (R, G, B)
        self.intensity = intensity  # 0.0 - 1.0
        self.lifetime = lifetime  # None = 永久
        self.max_lifetime = lifetime
        self.flicker = flicker  # 火焰闪烁效果
        self.flicker_seed = 0
        self.alive = True

    def update(self, dt):
        if self.lifetime is not None:
            self.lifetime -= dt
            if self.lifetime <= 0:
                self.alive = False
        if self.flicker:
            self.flicker_seed += dt * 15

    def get_effective_radius(self):
        """获取有效半径（闪烁时变化）"""
        if self.flicker:
            import math as _m
            flicker_amount = 0.85 + 0.15 * _m.sin(self.flicker_seed) + 0.05 * _m.sin(self.flicker_seed * 2.7)
            return self.radius * flicker_amount
        return self.radius

    def get_alpha(self):
        """获取当前alpha值"""
        base = int(255 * self.intensity)
        if self.lifetime is not None and self.max_lifetime:
            # 快消失时淡出
            life_ratio = self.lifetime / self.max_lifetime
            if life_ratio < 0.3:
                base = int(base * (life_ratio / 0.3))
        return max(0, min(255, base))


class LightingSystem:
    """动态光照系统 - 全屏黑暗覆盖 + 光源挖洞"""

    # 画质预设
    QUALITY_PRESETS = {
        "performance": {
            "ambient_darkness": 140,
            "player_light_radius": 180,
            "player_light_intensity": 1.0,
            "enemy_lights": False,
            "projectile_lights": False,
            "boss_lights": True,
            "flicker": False,
            "gradient_layers": 8,
            "vignette": False,
        },
        "balanced": {
            "ambient_darkness": 210,
            "player_light_radius": 300,
            "player_light_intensity": 1.4,
            "enemy_lights": True,
            "projectile_lights": True,
            "boss_lights": True,
            "flicker": True,
            "gradient_layers": 18,
            "vignette": True,
            "flashlight": True,
        },
        "quality": {
            "ambient_darkness": 235,
            "player_light_radius": 380,
            "player_light_intensity": 1.8,
            "enemy_lights": True,
            "projectile_lights": True,
            "boss_lights": True,
            "flicker": True,
            "gradient_layers": 28,
            "vignette": True,
            "flashlight": True,
        },
    }

    def __init__(self, screen_width, screen_height, quality="balanced"):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.quality = quality
        self.enabled = True
        self.lights = []  # 动态光源列表
        self._light_surface = None
        self._dark_surface = None
        self._gradient_cache = {}  # 预渲染径向渐变缓存
        self._init_surfaces()
        self._flashlight_angle = 0.0
        self.set_quality(quality)

    def _init_surfaces(self):
        """初始化表面"""
        self._dark_surface = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        self._light_surface = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)

    def set_quality(self, quality):
        """根据画质设置调整光照参数"""
        self.quality = quality
        preset = self.QUALITY_PRESETS.get(quality, self.QUALITY_PRESETS["balanced"])
        self.ambient_darkness = preset["ambient_darkness"]
        self.player_light_radius = preset["player_light_radius"]
        self.player_light_intensity = preset.get("player_light_intensity", 1.0)
        self.enemy_lights_enabled = preset["enemy_lights"]
        self.projectile_lights_enabled = preset["projectile_lights"]
        self.boss_lights_enabled = preset["boss_lights"]
        self.flicker_enabled = preset["flicker"]
        self.gradient_layers = preset["gradient_layers"]
        self.vignette_enabled = preset.get("vignette", False)
        self.flashlight_enabled = preset.get("flashlight", False)
        self._gradient_cache.clear()  # 清除缓存，用新层数重新渲染

    def resize(self, w, h):
        """窗口大小变化时重建表面"""
        self.screen_width = w
        self.screen_height = h
        self._init_surfaces()
        self._gradient_cache.clear()

    def _get_gradient(self, radius, color):
        """获取或创建预渲染的径向渐变光"""
        key = (int(radius), color)
        if key in self._gradient_cache:
            return self._gradient_cache[key]

        # 渲染径向渐变
        size = int(radius * 2)
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = radius
        max_r = radius
        # 分层绘制渐变（性能优化：不用逐像素）
        layers = getattr(self, 'gradient_layers', 16)
        for i in range(layers, 0, -1):
            t = i / layers  # 0=中心, 1=边缘
            r = int(max_r * t)
            if r <= 0:
                continue
            # 更陡的衰减曲线，中心更亮
            brightness = (1 - t) ** 2.2
            alpha = int(255 * brightness)
            # 颜色随距离衰减，但中心保持高饱和
            color_boost = 0.4 + 0.6 * brightness
            cr = min(255, int(color[0] * color_boost))
            cg = min(255, int(color[1] * color_boost))
            cb = min(255, int(color[2] * color_boost))
            pygame.draw.circle(surf, (cr, cg, cb, alpha), (int(center), int(center)), r)
        # 中心亮点
        core_r = max(2, int(max_r * 0.08))
        pygame.draw.circle(surf, (min(255, color[0]+60), min(255, color[1]+60, min(255, color[2]+60)), 200),
                           (int(center), int(center)), core_r)

        self._gradient_cache[key] = surf
        # 限制缓存大小
        if len(self._gradient_cache) > 50:
            oldest = list(self._gradient_cache.keys())[0]
            del self._gradient_cache[oldest]
        return surf

    def add_light(self, x, y, radius, color, intensity=1.0, lifetime=None, flicker=False):
        """添加动态光源"""
        light = Light(x, y, radius, color, intensity, lifetime, flicker)
        self.lights.append(light)
        return light

    def clear_temporary_lights(self):
        """清除所有临时光源（保留永久光源）"""
        self.lights = [l for l in self.lights if l.lifetime is None]

    def update(self, dt):
        """更新所有光源"""
        for light in self.lights[:]:
            light.update(dt)
            if not light.alive:
                self.lights.remove(light)

    def set_flashlight_angle(self, angle):
        """设置手电筒朝向（弧度）"""
        self._flashlight_angle = angle

    def render(self, screen, camera_x, camera_y, scale, player=None, enemies=None, projectiles=None, particles=None):
        """渲染光照层到屏幕

        Args:
            screen: 目标屏幕
            camera_x, camera_y: 摄像机世界坐标
            scale: 缩放比例
            player: 玩家对象（提供恒定光源）
            enemies: 敌人列表（燃烧的敌人提供光源）
            projectiles: 投射物列表（提供尾迹光）
            particles: 粒子系统（爆炸提供光源）
        """
        if not self.enabled:
            return

        # 清空光表面
        self._light_surface.fill((0, 0, 0, 0))

        # 1. 玩家恒定光源
        if player:
            px = int((player.x - camera_x) * scale)
            py = int((player.y - camera_y) * scale)
            player_radius = int(getattr(self, 'player_light_radius', 280) * scale)
            player_intensity = getattr(self, 'player_light_intensity', 1.3)
            gradient = self._get_gradient(player_radius, (255, 245, 210))
            if player_intensity > 1.0:
                gradient = gradient.copy()
                # 叠加一层增强中心亮度
                boost = pygame.Surface(gradient.get_size(), pygame.SRCALPHA)
                boost_r = int(player_radius * 0.5 * min(1.5, player_intensity))
                pygame.draw.circle(boost, (255, 250, 220, int(80 * (player_intensity - 1))),
                                   (player_radius, player_radius), boost_r)
                gradient.blit(boost, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            self._light_surface.blit(gradient, (px - player_radius, py - player_radius),
                                      special_flags=pygame.BLEND_RGBA_ADD)
            # 手电筒：玩家朝向的锥形光源
            if getattr(self, 'flashlight_enabled', False) and hasattr(self, '_flashlight_angle'):
                flash_angle = self._flashlight_angle
                flash_length = int(350 * scale)
                flash_width = 0.6  # 弧度，约35度
                # 绘制锥形光（用多个扇形叠加模拟渐变）
                for layer in range(8, 0, -1):
                    t = layer / 8
                    cone_len = int(flash_length * t)
                    cone_alpha = int(120 * (1 - t) ** 1.5)
                    if cone_alpha <= 0:
                        continue
                    cone_surf = pygame.Surface((cone_len * 2, cone_len * 2), pygame.SRCALPHA)
                    # 绘制扇形
                    start_angle = math.degrees(flash_angle - flash_width / 2)
                    end_angle = math.degrees(flash_angle + flash_width / 2)
                    pygame.draw.arc(cone_surf, (255, 250, 220, cone_alpha),
                                    (0, 0, cone_len * 2, cone_len * 2),
                                    start_angle, end_angle, cone_len)
                    # 填充扇形
                    for ang_i in range(int(start_angle), int(end_angle), 3):
                        rad = math.radians(ang_i)
                        end_x = cone_len + math.cos(rad) * cone_len
                        end_y = cone_len + math.sin(rad) * cone_len
                        pygame.draw.line(cone_surf, (255, 250, 220, cone_alpha // 2),
                                         (cone_len, cone_len), (int(end_x), int(end_y)), 2)
                    self._light_surface.blit(cone_surf, (px - cone_len, py - cone_len),
                                              special_flags=pygame.BLEND_RGBA_ADD)

        # 2. 燃烧/发光的敌人（受画质控制）
        if enemies and getattr(self, 'enemy_lights_enabled', True):
            for enemy in enemies:
                if not getattr(enemy, 'alive', True):
                    continue
                # 燃烧中的敌人
                if hasattr(enemy, 'buff_manager') and enemy.buff_manager.is_burning():
                    ex = int((enemy.x - camera_x) * scale)
                    ey = int((enemy.y - camera_y) * scale)
                    er = int(80 * scale)
                    gradient = self._get_gradient(er, (255, 120, 30))
                    self._light_surface.blit(gradient, (ex - er, ey - er),
                                              special_flags=pygame.BLEND_RGBA_ADD)
                # Boss自带微光（受画质控制）
                elif getattr(enemy, 'is_boss', False) and getattr(self, 'boss_lights_enabled', True):
                    ex = int((enemy.x - camera_x) * scale)
                    ey = int((enemy.y - camera_y) * scale)
                    er = int(120 * scale)
                    gradient = self._get_gradient(er, (180, 50, 200))
                    self._light_surface.blit(gradient, (ex - er, ey - er),
                                              special_flags=pygame.BLEND_RGBA_ADD)

        # 3. 投射物尾迹光（受画质控制）
        if projectiles and getattr(self, 'projectile_lights_enabled', True):
            for proj in projectiles:
                if not getattr(proj, 'alive', True):
                    continue
                proj_x = int((proj.x - camera_x) * scale)
                proj_y = int((proj.y - camera_y) * scale)
                color = getattr(proj, 'color', (255, 255, 200))
                pr = int(40 * scale)
                gradient = self._get_gradient(pr, color[:3])
                self._light_surface.blit(gradient, (proj_x - pr, proj_y - pr),
                                          special_flags=pygame.BLEND_RGBA_ADD)

        # 4. 动态光源（爆炸、技能特效等）
        for light in self.lights:
            if not light.alive:
                continue
            lx = int((light.x - camera_x) * scale)
            ly = int((light.y - camera_y) * scale)
            # 性能模式下禁用闪烁
            if not getattr(self, 'flicker_enabled', True):
                light.flicker = False
            eff_r = int(light.get_effective_radius() * scale)
            if eff_r <= 0:
                continue
            alpha = light.get_alpha()
            gradient = self._get_gradient(eff_r, light.color[:3])
            # 调整alpha
            if alpha < 255:
                gradient.set_alpha(alpha)
            self._light_surface.blit(gradient, (lx - eff_r, ly - eff_r),
                                      special_flags=pygame.BLEND_RGBA_ADD)

        # 5. 构建黑暗层：全屏黑暗 - 光源区域 = 最终黑暗
        self._dark_surface.fill((0, 0, 0, self.ambient_darkness))
        # 用光源表面"挖洞"（从黑暗中减去光）
        self._dark_surface.blit(self._light_surface, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

        # 6. 暗角效果（vignette）
        if getattr(self, 'vignette_enabled', False):
            vw, vh = self.screen_width, self.screen_height
            vignette_surf = pygame.Surface((vw, vh), pygame.SRCALPHA)
            # 四角渐变暗化
            v_steps = 8
            for i in range(v_steps, 0, -1):
                t = i / v_steps
                margin = int(min(vw, vh) * 0.12 * t)
                alpha = int(50 * (1 - t) ** 1.5)
                if margin > 0 and alpha > 0:
                    pygame.draw.rect(vignette_surf, (0, 0, 0, alpha),
                                     (margin//2, margin//2, vw - margin, vh - margin),
                                     border_radius=20)
            self._dark_surface.blit(vignette_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # 7. 应用到屏幕
        screen.blit(self._dark_surface, (0, 0))
