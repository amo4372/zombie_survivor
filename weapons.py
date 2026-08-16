#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""武器系统模块 - 添加更多详细枪械"""

import math
import random
import pygame
from config import WeaponType, YELLOW, ORANGE, RED, GREEN, WHITE, BLACK, CYAN, PURPLE, LIME, BLOOD_RED, RUST, POISON_GREEN

class Projectile:
    def __init__(self, x, y, vx, vy, damage, max_range, color, size, 
                 pierce=1, explosive=False, explosion_radius=0, is_flame=False,
                 is_plasma=False, is_chain=False, is_rail=False, gravity=0,
                 is_laser=False, laser_width=0, laser_duration=0, laser_angle=0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.damage = damage
        self.max_range = max_range
        self.traveled = 0
        self.color = color
        self.size = size
        self.pierce = pierce
        self.hits = []
        self.explosive = explosive
        self.explosion_radius = explosion_radius
        self.is_flame = is_flame
        self.is_plasma = is_plasma
        self.is_chain = is_chain
        self.is_rail = is_rail
        self.is_laser = is_laser
        self.laser_width = laser_width
        self.laser_duration = laser_duration
        self.laser_timer = laser_duration
        self.laser_angle = laser_angle
        self.gravity = gravity
        self.lifetime = 3.0 if is_flame else (laser_duration if is_laser else 10.0)
        self.alive = True
        self.should_explode = False
        # 特效标记
        self.has_shockwave = False
        self.shockwave_radius = 0
        self.shockwave_max_radius = 0
        self.shockwave_speed = 0
        self.has_smoke = False
        self.smoke_timer = 0
        self.smoke_particles = []
        self.has_fire = False
        self.fire_particles = []
        # 等离子特效
        self.plasma_dot = 0
        # 连锁特效
        self.chain_targets = []
        self.chain_count = 0
        self.max_chains = 3
        # 轨迹
        self.trail = []
        self.max_trail_length = 8
        # 激光束终点
        self.laser_end_x = x + math.cos(laser_angle) * max_range if is_laser else x
        self.laser_end_y = y + math.sin(laser_angle) * max_range if is_laser else y

    def update(self, dt):
        if self.is_laser:
            self.laser_timer -= dt
            if self.laser_timer <= 0:
                self.alive = False
            return None

        # 重力影响
        if self.gravity != 0:
            self.vy += self.gravity * dt * 60

        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.traveled += math.hypot(self.vx, self.vy) * dt * 60
        self.lifetime -= dt

        # 记录轨迹
        self.trail.append((self.x, self.y))
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)

        if self.should_explode and self.explosive and self.alive:
            self.alive = False
            return "explode"
        if self.traveled >= self.max_range or self.lifetime <= 0:
            if self.explosive and self.alive:
                self.alive = False
                return "explode"
            self.alive = False
        return None

    def hit_and_explode(self):
        """被击中时触发爆炸（用于爆炸类武器）"""
        if self.explosive and self.alive:
            self.should_explode = True
            self.alive = False
            return "explode"
        self.alive = False
        return None
    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, 
                          self.size * 2, self.size * 2)

    def draw(self, screen, camera_x, camera_y, scale=1.0):
        if self.is_laser:
            # 激光束绘制 - 极长极粗
            sx = int((self.x - camera_x) * scale)
            sy = int((self.y - camera_y) * scale)
            ex = int((self.laser_end_x - camera_x) * scale)
            ey = int((self.laser_end_y - camera_y) * scale)
            lw = max(3, int(self.laser_width * scale))

            # 外发光
            glow_surf = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
            pygame.draw.line(glow_surf, (*self.color[:3], 40), (sx, sy), (ex, ey), lw * 4)
            screen.blit(glow_surf, (0, 0))
            # 中层光
            pygame.draw.line(screen, (*self.color[:3], 120), (sx, sy), (ex, ey), lw * 2)
            # 核心光束
            pygame.draw.line(screen, WHITE, (sx, sy), (ex, ey), lw)
            # 闪烁核心
            if random.random() < 0.5:
                pygame.draw.line(screen, (255, 255, 220), (sx, sy), (ex, ey), max(1, lw // 2))
            return

        # 绘制轨迹
        if len(self.trail) >= 2 and (self.is_rail or self.is_plasma):
            points = []
            for tx, ty in self.trail[-5:]:
                px = int((tx - camera_x) * scale)
                py = int((ty - camera_y) * scale)
                points.append((px, py))
            if len(points) >= 2:
                pygame.draw.lines(screen, (*self.color[:3], 100), False, points, max(1, int(self.size * scale)))

        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(1, int(self.size * scale))

        if self.is_flame:
            # 增强火焰效果
            color = random.choice([ORANGE, RED, YELLOW, (255, 180, 50)])
            s = max(2, int((self.size + random.randint(-2, 4)) * scale))
            glow_s = s + 4
            glow_surf = pygame.Surface((glow_s * 2, glow_s * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 100, 20, 60), (glow_s, glow_s), glow_s)
            screen.blit(glow_surf, (px - glow_s, py - glow_s))
            pygame.draw.circle(screen, color, (px, py), s)
            pygame.draw.circle(screen, (255, 255, 200), (px, py), max(1, s // 2))
        elif self.is_plasma:
            # 增强等离子发光效果
            glow_s = s + 6
            glow_surf = pygame.Surface((glow_s * 2, glow_s * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (50, 255, 255, 80), (glow_s, glow_s), glow_s)
            screen.blit(glow_surf, (px - glow_s, py - glow_s))
            pygame.draw.circle(screen, self.color, (px, py), s + 2)
            pygame.draw.circle(screen, WHITE, (px, py), s)
            pygame.draw.circle(screen, (200, 255, 255), (px, py), max(1, s - 2))
        elif self.is_rail:
            # 轨道炮光束效果
            pygame.draw.circle(screen, (*self.color[:3], 200), (px, py), s + 2)
            pygame.draw.circle(screen, WHITE, (px, py), s)
            pygame.draw.circle(screen, CYAN, (px, py), s - 2)
        else:
            pygame.draw.circle(screen, self.color, (px, py), s)
            if s > 2:
                pygame.draw.circle(screen, (*self.color[:3], 128), 
                                 (int(px - self.vx * 2 * scale), int(py - self.vy * 2 * scale)), 
                                 max(1, s // 2))


class Weapon:
    def __init__(self, weapon_type, level=1):
        self.weapon_type = weapon_type
        self.level = level
        self.cooldown_timer = 0
        self.shake_intensity = 2
        self._setup_weapon()

    def _setup_weapon(self):
        configs = {
            WeaponType.PISTOL: {
                "name": "手枪", "damage": 15, "fire_rate": 0.4, 
                "range": 400, "speed": 12, "spread": 0.05, "pierce": 1,
                "color": YELLOW, "projectile_size": 4, "shake": 2,
                "desc": "基础武器，可靠但威力一般",
                "ammo": "∞", "reload": 0
            },
            WeaponType.RIFLE: {
                "name": "突击步枪", "damage": 25, "fire_rate": 0.15,
                "range": 500, "speed": 15, "spread": 0.03, "pierce": 2,
                "color": ORANGE, "projectile_size": 5, "shake": 3,
                "desc": "均衡的自动武器，适合中距离",
                "ammo": 30, "reload": 2.0
            },
            WeaponType.SHOTGUN: {
                "name": "霰弹枪", "damage": 12, "fire_rate": 0.8,
                "range": 250, "speed": 10, "spread": 0.15, "pierce": 1,
                "pellets": 5, "color": RED, "projectile_size": 3, "shake": 5,
                "desc": "近距离毁灭者，散射多发弹丸",
                "ammo": 8, "reload": 2.5
            },
            WeaponType.SNIPER: {
                "name": "狙击枪", "damage": 80, "fire_rate": 1.5,
                "range": 800, "speed": 20, "spread": 0, "pierce": 5,
                "color": GREEN, "projectile_size": 6, "shake": 8,
                "desc": "超远距离精准打击，穿透多个敌人",
                "ammo": 5, "reload": 3.0
            },
            WeaponType.MACHINE_GUN: {
                "name": "机枪", "damage": 18, "fire_rate": 0.08,
                "range": 450, "speed": 14, "spread": 0.08, "pierce": 2,
                "color": ORANGE, "projectile_size": 4, "shake": 4,
                "desc": "高射速压制武器，适合对付尸潮",
                "ammo": 100, "reload": 4.0
            },
            WeaponType.ROCKET_LAUNCHER: {
                "name": "火箭筒", "damage": 100, "fire_rate": 2.0,
                "range": 600, "speed": 8, "spread": 0.02, "pierce": 1,
                "explosive": True, "explosion_radius": 100,
                "color": RED, "projectile_size": 10, "shake": 12,
                "desc": "发射高爆火箭弹，造成范围伤害",
                "ammo": 4, "reload": 3.5
            },
            WeaponType.FLAMETHROWER: {
                "name": "火焰喷射器", "damage": 10, "fire_rate": 0.03,
                "range": 260, "speed": 9, "spread": 0.15, "pierce": 20,
                "color": ORANGE, "projectile_size": 12, "is_flame": True, "shake": 3,
                "desc": "持续火焰伤害，无视护甲，附带燃烧效果",
                "ammo": 300, "reload": 2.0,
                "burn_damage": 5, "burn_duration": 4.0
            },
            WeaponType.CROSSBOW: {
                "name": "十字弩", "damage": 55, "fire_rate": 1.0,
                "range": 500, "speed": 18, "spread": 0.01, "pierce": 3,
                "color": BLOOD_RED, "projectile_size": 5, "shake": 3,
                "desc": "高穿透弩箭，可回收弹药",
                "ammo": 12, "reload": 2.0
            },
            WeaponType.GRENADE_LAUNCHER: {
                "name": "榴弹发射器", "damage": 70, "fire_rate": 1.2,
                "range": 400, "speed": 10, "spread": 0.05, "pierce": 1,
                "explosive": True, "explosion_radius": 80, "gravity": 0.15,
                "color": RUST, "projectile_size": 8, "shake": 6,
                "desc": "抛物线榴弹，可越过障碍物",
                "ammo": 6, "reload": 3.0
            },
            WeaponType.PLASMA_RIFLE: {
                "name": "等离子步枪", "damage": 60, "fire_rate": 0.14,
                "range": 600, "speed": 16, "spread": 0.02, "pierce": 3,
                "is_plasma": True, "color": CYAN, "projectile_size": 9, "shake": 6,
                "desc": "发射高能等离子弹，穿透并持续灼烧",
                "ammo": 60, "reload": 1.8,
                "dot_damage": 12, "dot_duration": 3.0
            },
            WeaponType.RAILGUN: {
                "name": "轨道炮", "damage": 500, "fire_rate": 4.0,
                "range": 1500, "speed": 0, "spread": 0, "pierce": 99,
                "is_laser": True, "laser_width": 25, "laser_duration": 0.8,
                "color": PURPLE, "projectile_size": 15, "shake": 25,
                "desc": "充能武器，发射极粗激光束，穿透一切",
                "ammo": 3, "reload": 4.0,
                "charge_time": 1.0
            },
            WeaponType.MINIGUN: {
                "name": "加特林", "damage": 12, "fire_rate": 0.018,
                "range": 500, "speed": 22, "spread": 0.12, "pierce": 4,
                "color": BLOOD_RED, "projectile_size": 5, "shake": 8,
                "desc": "极致射速，弹幕压制，移动时精度下降",
                "ammo": 400, "reload": 3.0,
                "suppression": True, "tracer": True
            },
            WeaponType.DOUBLE_BARREL: {
                "name": "双管霰弹", "damage": 25, "fire_rate": 1.0,
                "range": 180, "speed": 12, "spread": 0.2, "pierce": 1,
                "pellets": 8, "color": RUST, "projectile_size": 4, "shake": 8,
                "desc": "双发齐射，近距离毁灭性伤害",
                "ammo": 2, "reload": 2.0
            },
        }

        config = configs.get(self.weapon_type, configs[WeaponType.PISTOL])
        for k, v in config.items():
            setattr(self, k, v)
        self.shake_intensity = config.get("shake", 2)
        self.damage *= (1 + (self.level - 1) * 0.2)
        self.fire_rate *= (0.9 ** (self.level - 1))

        # 弹药系统
        self.max_ammo = config.get("ammo", 0)
        self.current_ammo = self.max_ammo if self.max_ammo != "∞" else "∞"
        self.reload_time = config.get("reload", 0)
        self.reload_timer = 0
        self.is_reloading = False
        self.reload_speed_mult = 1.0  # 换弹速度加成（由玩家技能设置）

    def can_fire(self):
        if self.is_reloading:
            return False
        if self.current_ammo != "∞" and self.current_ammo <= 0:
            return False
        return self.cooldown_timer <= 0

    def fire(self, x, y, angle, damage_mult=1.0, speed_mult=1.0, player=None):
        if not self.can_fire():
            return []

        self.cooldown_timer = self.fire_rate

        # 消耗弹药
        if self.current_ammo != "∞":
            pellets = getattr(self, "pellets", 1)
            self.current_ammo -= pellets
            if self.current_ammo <= 0:
                self.current_ammo = 0
                self.start_reload()

        # 后坐力效果 - 增强
        if player and hasattr(player, 'recoil_offset'):
            recoil_strength = getattr(self, 'shake', 2) * 3
            recoil_angle = angle + math.pi
            player.recoil_offset[0] += math.cos(recoil_angle) * recoil_strength
            player.recoil_offset[1] += math.sin(recoil_angle) * recoil_strength
            player.muzzle_flash_timer = player.muzzle_flash_duration

        projectiles = []
        pellets = getattr(self, "pellets", 1)
        for i in range(pellets):
            spread_angle = angle + random.uniform(-self.spread, self.spread)
            if pellets > 1:
                spread_angle += (i - pellets // 2) * 0.1

            proj = Projectile(
                x, y, 
                math.cos(spread_angle) * self.speed * speed_mult,
                math.sin(spread_angle) * self.speed * speed_mult,
                self.damage * damage_mult,
                self.range,
                self.color,
                self.projectile_size,
                self.pierce,
                getattr(self, "explosive", False),
                getattr(self, "explosion_radius", 0),
                getattr(self, "is_flame", False),
                getattr(self, "is_plasma", False),
                getattr(self, "is_chain", False),
                getattr(self, "is_rail", False),
                getattr(self, "gravity", 0),
                getattr(self, "is_laser", False),
                getattr(self, "laser_width", 0),
                getattr(self, "laser_duration", 0),
                spread_angle if getattr(self, "is_laser", False) else 0
            )
            projectiles.append(proj)
        return projectiles

    def start_reload(self):
        if self.reload_time > 0 and not self.is_reloading and self.current_ammo != self.max_ammo:
            self.is_reloading = True
            self.reload_timer = self.reload_time

    def update(self, dt):
        if self.cooldown_timer > 0:
            self.cooldown_timer -= dt

        if self.is_reloading:
            self.reload_timer -= dt * self.reload_speed_mult
            if self.reload_timer <= 0:
                self.is_reloading = False
                self.current_ammo = self.max_ammo

    def upgrade(self):
        self.level += 1
        self._setup_weapon()

    def get_ammo_text(self):
        if self.current_ammo == "∞":
            return "∞"
        return f"{self.current_ammo}/{self.max_ammo}"
