#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""武器系统模块 - 添加更多详细枪械"""

import math
import random
import pygame
from config import *

class Projectile:
    def __init__(self, x, y, vx, vy, damage, max_range, color, size, 
                 pierce=1, explosive=False, explosion_radius=0, is_flame=False,
                 is_plasma=False, is_chain=False, is_rail=False, gravity=0,
                 is_laser=False, laser_width=0, laser_duration=0, laser_angle=0,
                 is_scythe_throw=False):
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
        self.is_scythe_throw = is_scythe_throw
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
        elif self.is_scythe_throw:
            # ===== 死神镰刀抛掷：旋转镰刀（紫刃+长柄），局内清晰可见 =====
            import math as _m
            _spin = _m.radians((pygame.time.get_ticks() / 6.0) % 360)  # 持续旋转
            _blade_r = max(10, int(20 * scale))
            _dir = _m.atan2(self.vy, self.vx)
            # 紫光晕
            _g = pygame.Surface((_blade_r * 2 + 12, _blade_r * 2 + 12), pygame.SRCALPHA)
            _gc = _blade_r + 6
            pygame.draw.circle(_g, (180, 60, 220, 60), (_gc, _gc), _blade_r + 4)
            screen.blit(_g, (px - _gc, py - _gc))
            # 旋转刀弧（朝向运动方向 + 旋转偏移）
            _base = _dir + _spin
            # 刀刃（亮紫弧）
            pygame.draw.arc(screen, (216, 130, 250), (px - _blade_r, py - _blade_r, _blade_r * 2, _blade_r * 2),
                            _base - 2.3, _base + 0.7, max(3, int(6 * scale)))
            pygame.draw.arc(screen, (150, 60, 210), (px - _blade_r, py - _blade_r, _blade_r * 2, _blade_r * 2),
                            _base - 2.1, _base + 0.5, max(2, int(3 * scale)))
            # 柄（从中心朝反方向）
            _hx = px - _m.cos(_base) * (_blade_r + 8)
            _hy = py - _m.sin(_base) * (_blade_r + 8)
            pygame.draw.line(screen, (110, 90, 62), (px, py), (int(_hx), int(_hy)), max(2, int(4 * scale)))
            pygame.draw.line(screen, (150, 122, 82), (px, py), (int(_hx), int(_hy)), max(1, int(2 * scale)))
            # 柄端银环
            pygame.draw.circle(screen, (170, 174, 190), (int(_hx), int(_hy)), max(2, int(3 * scale)))
            # 白亮高光点
            pygame.draw.circle(screen, WHITE, (px, py), max(1, int(2 * scale)))
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
        # 近战攻击标记
        self.melee_attack_triggered = False
        self.melee_attack_angle = 0
        self.melee_attack_x = 0
        self.melee_attack_y = 0
        self.melee_attack_damage = 0
        self._setup_weapon()

    def _setup_weapon(self):
        configs = {
            WeaponType.PISTOL: {
                "name": "手枪", "damage": 17, "fire_rate": 0.38, 
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
            # ========== 近战武器 ==========
            WeaponType.KNIFE: {
                "name": "匕首", "damage": 28, "fire_rate": 0.25,
                "range": 60, "speed": 0, "spread": 0, "pierce": 1,
                "color": (192, 192, 192), "projectile_size": 0, "shake": 2,
                "desc": "快速近战，高暴击率",
                "ammo": "∞", "reload": 0, "is_melee": True, "crit_chance": 0.3
            },
            WeaponType.BAT: {
                "name": "棒球棍", "damage": 40, "fire_rate": 0.6,
                "range": 70, "speed": 0, "spread": 0, "pierce": 1,
                "color": BROWN, "projectile_size": 0, "shake": 4,
                "desc": "中速近战，有击退效果",
                "ammo": "∞", "reload": 0, "is_melee": True, "knockback": 15
            },
            WeaponType.CHAINSAW: {
                "name": "电锯", "damage": 22, "fire_rate": 0.08,
                "range": 55, "speed": 0, "spread": 0, "pierce": 1,
                "color": ORANGE, "projectile_size": 0, "shake": 3,
                "desc": "持续高DPS，移动减速",
                "ammo": "∞", "reload": 0, "is_melee": True, "move_slow": 0.5
            },
            WeaponType.SCYTHE: {
                "name": "死神镰刀", "damage": 45, "fire_rate": 0.5,
                "range": 80, "speed": 0, "spread": 0, "pierce": 3,
                "color": (180, 60, 220), "projectile_size": 0, "shake": 4,
                "desc": "死神之镰：近战挥砍，换弹时朝面朝方向扔出并返回",
                "ammo": "∞", "reload": 1.4, "is_melee": True, "is_scythe": True,
                "throw_range": 320, "throw_damage": 55, "throw_speed": 13
            },
            # ========== 手枪扩展 ==========
            WeaponType.REVOLVER: {
                "name": "左轮手枪", "damage": 45, "fire_rate": 0.7,
                "range": 450, "speed": 14, "spread": 0.02, "pierce": 2,
                "color": GOLD, "projectile_size": 5, "shake": 5,
                "desc": "高伤害低射速，穿透力强",
                "ammo": 6, "reload": 2.0
            },
            WeaponType.DESERT_EAGLE: {
                "name": "沙漠之鹰", "damage": 60, "fire_rate": 0.8,
                "range": 500, "speed": 16, "spread": 0.03, "pierce": 3,
                "color": (200, 200, 200), "projectile_size": 6, "shake": 7,
                "desc": "超高伤害手枪，后坐力大",
                "ammo": 7, "reload": 2.5
            },
            # ========== 冲锋枪扩展 ==========
            WeaponType.SMG: {
                "name": "冲锋枪", "damage": 14, "fire_rate": 0.08,
                "range": 350, "speed": 13, "spread": 0.07, "pierce": 1,
                "color": DARK_GRAY, "projectile_size": 3, "shake": 2,
                "desc": "高射速基础冲锋枪",
                "ammo": 30, "reload": 1.8
            },
            WeaponType.UMP45: {
                "name": "UMP45", "damage": 18, "fire_rate": 0.12,
                "range": 400, "speed": 13, "spread": 0.05, "pierce": 1,
                "color": BLACK, "projectile_size": 4, "shake": 3,
                "desc": "高伤害冲锋枪，精度较好",
                "ammo": 25, "reload": 2.0
            },
            WeaponType.P90: {
                "name": "P90", "damage": 13, "fire_rate": 0.06,
                "range": 380, "speed": 14, "spread": 0.06, "pierce": 1,
                "color": (180, 160, 120), "projectile_size": 3, "shake": 2,
                "desc": "极高射速，大容量弹匣",
                "ammo": 50, "reload": 2.2
            },
            # ========== 步枪扩展 ==========
            WeaponType.AK47: {
                "name": "AK47", "damage": 32, "fire_rate": 0.12,
                "range": 500, "speed": 15, "spread": 0.06, "pierce": 2,
                "color": (139, 90, 43), "projectile_size": 5, "shake": 4,
                "desc": "高伤害步枪，后坐力较大",
                "ammo": 30, "reload": 2.2
            },
            WeaponType.M4A1: {
                "name": "M4A1", "damage": 26, "fire_rate": 0.1,
                "range": 520, "speed": 16, "spread": 0.03, "pierce": 2,
                "color": BLACK, "projectile_size": 4, "shake": 3,
                "desc": "均衡可靠的突击步枪",
                "ammo": 30, "reload": 2.0
            },
            WeaponType.SCAR: {
                "name": "SCAR", "damage": 28, "fire_rate": 0.11,
                "range": 550, "speed": 15, "spread": 0.02, "pierce": 2,
                "color": (180, 160, 120), "projectile_size": 5, "shake": 3,
                "desc": "高精度突击步枪",
                "ammo": 30, "reload": 2.1
            },
            # ========== 狙击枪扩展 ==========
            WeaponType.AWP: {
                "name": "AWP", "damage": 150, "fire_rate": 2.0,
                "range": 1000, "speed": 25, "spread": 0, "pierce": 8,
                "color": GREEN, "projectile_size": 8, "shake": 12,
                "desc": "超高伤害狙击枪，一枪毙命",
                "ammo": 5, "reload": 3.5
            },
            # ========== 霰弹枪扩展 ==========
            WeaponType.AA12: {
                "name": "AA12", "damage": 14, "fire_rate": 0.2,
                "range": 280, "speed": 11, "spread": 0.12, "pierce": 1,
                "pellets": 6, "color": BLACK, "projectile_size": 3, "shake": 4,
                "desc": "全自动霰弹枪，近距离压制",
                "ammo": 20, "reload": 3.0
            },
            # ========== 重武器扩展 ==========
            WeaponType.LMG: {
                "name": "轻机枪", "damage": 20, "fire_rate": 0.1,
                "range": 500, "speed": 14, "spread": 0.07, "pierce": 2,
                "color": DARK_GRAY, "projectile_size": 5, "shake": 3,
                "desc": "大容量弹匣，持续火力压制",
                "ammo": 100, "reload": 4.0
            },
            # ========== 投掷物 ==========
            WeaponType.GRENADE: {
                "name": "手雷", "damage": 100, "fire_rate": 1.5,
                "range": 300, "speed": 8, "spread": 0, "pierce": 1,
                "color": GREEN, "projectile_size": 6, "shake": 10,
                "desc": "范围爆炸伤害",
                "ammo": 3, "reload": 0, "is_throwable": True, "explosion_radius": 100
            },
            WeaponType.MOLOTOV: {
                "name": "燃烧瓶", "damage": 15, "fire_rate": 1.5,
                "range": 280, "speed": 7, "spread": 0, "pierce": 1,
                "color": FIRE_ORANGE, "projectile_size": 6, "shake": 5,
                "desc": "持续燃烧区域伤害",
                "ammo": 3, "reload": 0, "is_throwable": True, "burn_duration": 5, "burn_radius": 80
            },
            WeaponType.SMOKE_GRENADE: {
                "name": "烟雾弹", "damage": 0, "fire_rate": 1.5,
                "range": 250, "speed": 7, "spread": 0, "pierce": 1,
                "color": LIGHT_GRAY, "projectile_size": 6, "shake": 2,
                "desc": "减速视野内敌人",
                "ammo": 3, "reload": 0, "is_throwable": True, "slow_radius": 100, "slow_duration": 8
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

        # 近战武器：不发射投射物，触发近战攻击标记
        if getattr(self, "is_melee", False):
            self.melee_attack_triggered = True
            self.melee_attack_angle = angle
            self.melee_attack_x = x
            self.melee_attack_y = y
            self.melee_attack_damage = self.damage * damage_mult
            if player and hasattr(player, 'recoil_offset'):
                recoil_strength = getattr(self, 'shake', 2) * 2
                recoil_angle = angle + math.pi
                player.recoil_offset[0] += math.cos(recoil_angle) * recoil_strength
                player.recoil_offset[1] += math.sin(recoil_angle) * recoil_strength
            return []

        # 投掷物：抛物线轨迹+爆炸
        if getattr(self, "is_throwable", False):
            if isinstance(self.current_ammo, (int, float)) and self.current_ammo != "∞":
                self.current_ammo -= 1
                if self.current_ammo <= 0:
                    self.current_ammo = 0
            throw_speed = getattr(self, "speed", 8)
            proj = Projectile(
                x, y,
                math.cos(angle) * throw_speed * speed_mult,
                math.sin(angle) * throw_speed * speed_mult - 2,
                self.damage * damage_mult,
                self.range,
                self.color,
                self.projectile_size,
                self.pierce,
                True,
                getattr(self, "explosion_radius", 80),
                False, False, False, False,
                0.4,  # 重力
                False, 0, 0, 0
            )
            proj.is_grenade_type = getattr(self, "weapon_type", None)
            proj.burn_duration = getattr(self, "burn_duration", 0)
            proj.burn_radius = getattr(self, "burn_radius", 0)
            proj.slow_radius = getattr(self, "slow_radius", 0)
            proj.slow_duration = getattr(self, "slow_duration", 0)
            return [proj]

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

def render_weapon_icon(weapon_type):
    """程序化生成武器专属贴图（透明surface，枪口朝右/0度），局内玩家手持与图鉴共用。
    每把武器都有独立的造型、配色与部件，一眼可辨。"""
    from config import WeaponType
    wt = weapon_type.value if hasattr(weapon_type, 'value') else weapon_type
    try:
        wt = WeaponType(wt)
    except Exception:
        pass
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    cx, cy = 32, 32
    name = wt.name if hasattr(wt, 'name') else str(wt)

    # ===== 近战专属 =====
    if name == "SCYTHE":
        pygame.draw.arc(surf, (225, 230, 240), (cx - 30, cy - 26, 66, 56), 0, 3.3, 9)
        pygame.draw.line(surf, (150, 120, 82), (cx + 28, cy + 2), (cx - 26, cy + 42), 8)
        pygame.draw.circle(surf, (165, 135, 92), (cx + 28, cy + 2), 8)
        return surf
    if name == "KNIFE":
        pygame.draw.polygon(surf, (205, 210, 220),
                            [(cx - 6, cy - 6), (cx + 26, cy - 6), (cx + 32, cy + 2), (cx - 10, cy + 2)])
        pygame.draw.rect(surf, (135, 98, 62), (cx - 26, cy - 4, 24, 10))
        return surf
    if name == "BAT":
        pygame.draw.line(surf, (155, 122, 72), (cx - 30, cy + 2), (cx + 30, cy + 2), 11)
        pygame.draw.rect(surf, (125, 92, 62), (cx - 6, cy + 2, 22, 12))
        return surf
    if name == "CHAINSAW":
        pygame.draw.rect(surf, (125, 125, 135), (cx - 30, cy - 4, 60, 14))
        for i in range(-26, 30, 9):
            pygame.draw.circle(surf, (92, 92, 102), (cx + i, cy + 3), 3)
        pygame.draw.rect(surf, (155, 82, 62), (cx - 4, cy + 10, 24, 16))
        return surf

    # ===== 枪械专属配置：body(主体尺寸+色) barrel(枪管长+宽+色) mag(弹匣) grip stock scope special =====
    GUN = {
        "PISTOL":               dict(body=(26, 8, 40, 14, (72, 72, 84)), barrel=(18, 6, (62, 62, 72)), mag="pistol", grip=True, accent=(205, 195, 60)),
        "REVOLVER":             dict(body=(22, 8, 38, 14, (92, 96, 102)), barrel=(20, 6, (86, 86, 92)), grip=True, special="cylinder", accent=(165, 165, 170)),
        "DESERT_EAGLE":         dict(body=(30, 7, 46, 16, (122, 96, 50)), barrel=(22, 7, (112, 86, 46)), mag="pistol", grip=True, accent=(205, 162, 82)),
        "RIFLE":                dict(body=(20, 8, 48, 15, (62, 82, 56)), barrel=(24, 6, (52, 72, 50)), mag="rifle", grip=True, stock=True, accent=(82, 112, 72)),
        "AK47":                 dict(body=(18, 8, 50, 15, (72, 60, 45)), barrel=(24, 6, (92, 76, 56)), mag="ak", grip=True, stock="wood", accent=(185, 142, 82)),
        "M4A1":                 dict(body=(20, 8, 48, 15, (56, 76, 62)), barrel=(24, 6, (46, 66, 52)), mag="rifle", grip=True, stock=True, accent=(92, 122, 88)),
        "SCAR":                 dict(body=(20, 7, 50, 14, (72, 76, 56)), barrel=(26, 6, (62, 66, 48)), mag="rifle", grip=True, stock=True, scope=True, accent=(185, 150, 62)),
        "SMG":                  dict(body=(22, 9, 42, 13, (52, 57, 77)), barrel=(14, 5, (46, 51, 72)), mag="smg", grip=True, accent=(102, 112, 152)),
        "UMP45":                dict(body=(24, 9, 44, 13, (66, 71, 87)), barrel=(16, 5, (61, 66, 82)), mag="smg", grip=True, accent=(132, 137, 162)),
        "P90":                  dict(body=(24, 9, 46, 13, (46, 96, 96)), barrel=(14, 5, (41, 86, 86)), mag="top", grip=True, accent=(92, 192, 192)),
        "SNIPER":               dict(body=(16, 7, 52, 13, (42, 77, 52)), barrel=(30, 5, (36, 67, 47)), mag="bolt", grip=True, stock=True, scope=True, accent=(72, 132, 82)),
        "SEMI_AUTO_SNIPER":     dict(body=(16, 7, 52, 13, (66, 76, 46)), barrel=(26, 5, (61, 71, 41)), mag="rifle", grip=True, stock=True, scope=True, accent=(152, 162, 92)),
        "AWP":                  dict(body=(14, 7, 54, 13, (52, 87, 62)), barrel=(32, 5, (47, 77, 57)), mag="bolt", grip=True, stock=True, scope=True, accent=(225, 202, 82)),
        "SHOTGUN":              dict(body=(20, 9, 46, 15, (112, 71, 50)), barrel=(22, 7, (102, 61, 45)), grip=True, special="pump", accent=(162, 102, 72)),
        "DOUBLE_BARREL":        dict(body=(18, 8, 44, 15, (62, 62, 67)), barrel=(24, 10, (57, 57, 62)), grip=True, special="double", stock="wood", accent=(132, 92, 62)),
        "AA12":                 dict(body=(20, 8, 48, 15, (72, 72, 77)), barrel=(20, 6, (67, 67, 72)), mag="rifle", grip=True, stock=True, accent=(152, 152, 162)),
        "MACHINE_GUN":          dict(body=(18, 8, 52, 16, (82, 97, 56)), barrel=(24, 7, (77, 92, 51)), grip=True, special="belt", stock=True, accent=(142, 162, 82)),
        "MINIGUN":              dict(body=(22, 8, 46, 16, (77, 77, 82)), barrel=(22, 12, (72, 72, 77)), grip=True, special="minigun", accent=(205, 82, 62)),
        "LMG":                  dict(body=(18, 8, 54, 16, (92, 72, 56)), barrel=(26, 7, (87, 67, 51)), mag="box", grip=True, stock=True, accent=(152, 122, 82)),
        "ROCKET_LAUNCHER":      dict(body=(16, 10, 50, 20, (72, 87, 62)), barrel=(20, 9, (67, 82, 57)), grip=True, special="rocket", accent=(205, 142, 52)),
        "FLAMETHROWER":         dict(body=(18, 10, 46, 18, (97, 61, 51)), barrel=(18, 8, (142, 71, 41)), mag="tank", special="flame", accent=(242, 122, 42)),
        "CROSSBOW":             dict(body=(14, 8, 44, 16, (122, 92, 62)), barrel=(18, 6, (112, 82, 57)), grip=True, special="bow", accent=(172, 132, 82)),
        "GRENADE_LAUNCHER":     dict(body=(18, 9, 46, 16, (67, 77, 62)), barrel=(18, 8, (62, 72, 57)), grip=True, special="gl", accent=(205, 182, 72)),
        "PLASMA_RIFLE":         dict(body=(18, 8, 50, 15, (92, 51, 112)), barrel=(24, 6, (122, 62, 152)), mag="rifle", grip=True, stock=True, special="glow", accent=(182, 92, 222)),
        "RAILGUN":              dict(body=(14, 7, 54, 14, (57, 72, 87)), barrel=(32, 6, (72, 92, 112)), grip=True, stock=True, scope=True, special="rail", accent=(142, 202, 232)),
    }
    cfg = GUN.get(name, GUN["PISTOL"])
    bx, by, bw, bh, body_col = cfg["body"]
    blen, bh, bcol = cfg["barrel"]
    # 枪身
    pygame.draw.rect(surf, body_col, (cx - bx, cy - by, bw, bh), border_radius=3)
    # 枪管
    pygame.draw.rect(surf, bcol, (cx - bx + bw - 3, cy - 3, blen, bh), border_radius=2)

    # 弹匣
    mag = cfg.get("mag")
    if mag == "pistol":
        pygame.draw.rect(surf, (50, 50, 60), (cx - 12, cy + 3, 16, 11))
    elif mag == "smg":
        pygame.draw.rect(surf, (45, 48, 62), (cx - 14, cy + 3, 18, 10))
    elif mag == "rifle":
        pygame.draw.rect(surf, (45, 50, 42), (cx - 14, cy + 3, 16, 12))
    elif mag == "ak":
        pygame.draw.polygon(surf, (92, 76, 52), [(cx - 14, cy + 3), (cx - 14, cy + 15), (cx - 2, cy + 15), (cx - 2, cy + 3)])
    elif mag == "top":  # P90 顶部弹匣
        pygame.draw.rect(surf, (40, 80, 80), (cx - 18, cy - 14, 20, 9))
    elif mag == "box":  # LMG 弹箱
        pygame.draw.rect(surf, (70, 55, 42), (cx - 18, cy + 4, 22, 12))
    elif mag == "tank":  # 火焰喷射器燃料罐
        pygame.draw.rect(surf, (140, 68, 40), (cx - 22, cy + 5, 24, 14))
    elif mag == "bolt":  # 狙击拉栓
        pygame.draw.rect(surf, (40, 66, 46), (cx + 6, cy - 12, 10, 7))

    # 握把
    if cfg.get("grip"):
        pygame.draw.rect(surf, (55, 55, 62), (cx - 8, cy + 2, 14, 14), border_radius=3)

    # 枪托
    st = cfg.get("stock")
    if st == "wood":
        pygame.draw.rect(surf, (125, 92, 60), (cx - bx - 14, cy - 6, 16, 12), border_radius=3)
    elif st:
        pygame.draw.rect(surf, (52, 60, 48), (cx - bx - 14, cy - 5, 16, 10), border_radius=3)

    # 瞄准镜
    if cfg.get("scope"):
        pygame.draw.rect(surf, (70, 70, 78), (cx - 4, cy - 13, 14, 7), border_radius=2)
        pygame.draw.circle(surf, (150, 210, 230), (cx + 8, cy - 10), 3)

    # 特殊部件
    sp = cfg.get("special")
    if sp == "cylinder":  # 左轮转轮
        pygame.draw.circle(surf, (100, 103, 108), (cx - 10, cy), 6)
        pygame.draw.circle(surf, (60, 60, 65), (cx - 10, cy), 3)
    elif sp == "pump":  # 霰弹泵动
        pygame.draw.rect(surf, (82, 58, 44), (cx - 6, cy - 5, 10, 12), border_radius=2)
    elif sp == "double":  # 双管
        pygame.draw.rect(surf, (50, 50, 55), (cx + 20, cy - 9, 26, 6))
    elif sp == "belt":  # 机枪弹链
        for i in range(cx - 20, cx + 28, 7):
            pygame.draw.rect(surf, (160, 180, 90), (i, cy + 4, 5, 9))
    elif sp == "minigun":  # 加特林多管
        for a in range(0, 360, 45):
            import math as _m
            r = 7
            dx = int(_m.cos(_m.radians(a)) * r)
            dy = int(_m.sin(_m.radians(a)) * r)
            pygame.draw.circle(surf, (70, 70, 75), (cx + 18, cy + dx // 2), 3)
        pygame.draw.circle(surf, (150, 60, 50), (cx + 18, cy), 8)
    elif sp == "rocket":  # 火箭筒前锥头
        pygame.draw.polygon(surf, (90, 100, 78), [(cx + 48, cy - 8), (cx + 62, cy), (cx + 48, cy + 8)])
    elif sp == "flame":  # 火焰喷射口
        pygame.draw.circle(surf, (250, 150, 50), (cx + 46, cy), 6)
        pygame.draw.circle(surf, (255, 200, 90), (cx + 48, cy), 3)
    elif sp == "bow":  # 十字弩弓
        pygame.draw.line(surf, (100, 70, 45), (cx - 18, cy - 12), (cx + 26, cy - 12), 4)
        pygame.draw.line(surf, (150, 120, 85), (cx - 18, cy + 12), (cx + 26, cy + 12), 4)
        pygame.draw.line(surf, (140, 140, 150), (cx - 18, cy - 12), (cx - 18, cy + 12), 3)
    elif sp == "gl":  # 榴弹发射器下挂
        pygame.draw.rect(surf, (55, 62, 50), (cx - 6, cy + 8, 16, 9))
    elif sp == "glow":  # 等离子发光
        pygame.draw.rect(surf, (200, 130, 240), (cx - 2, cy - 3, 30, 6))
    elif sp == "rail":  # 轨道炮线圈
        for i in range(4):
            pygame.draw.rect(surf, (120, 170, 200), (cx + 6 + i * 8, cy - 6, 6, 12))

    # 枪口/配色点缀
    pygame.draw.rect(surf, cfg["accent"], (cx + 34, cy - 3, 7, 6))
    return surf
