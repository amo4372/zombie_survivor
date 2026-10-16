#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.0 载具召唤物系统（结构化模块化设计，为同屏N人预留）

3 级载具：
  1. 大运重卡 (truck)：禁射击、可用其他技能、移速中等、撞击伤害、
     僵尸可伤载具（伤害记在载具专属血条，不应用回血），血条归零技能结束进 CD
  2. 99A 坦克 (tank)：血条更厚、速度更慢、可撞击；主炮 4 发弹夹
     （3 发高爆 ≈ 1 级手雷 + 1 发尾翼稳定穿甲弹可穿透尸群）、发射间隔长
  3. 武装直升机 (heli)：无视近战攻击、仅受远程+投掷物伤害、血量中、
     速度较快、机炮（自动连射）+ 火箭弹（CD）
"""
import math
import os

import pygame

from weapons import Projectile

# 载具图片目录（工具程序化生成 PNG 后放入）
VEHICLE_IMAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "vehicles")

_VEHICLE_IMAGES = {}


def load_vehicle_images():
    """预加载载具图片（缺失时返回 None，调用方绘制回退图形）"""
    for vid in ("truck", "tank", "heli"):
        try:
            path = os.path.normpath(os.path.join(VEHICLE_IMAGE_DIR, f"{vid}.png"))
            if os.path.exists(path):
                surf = pygame.image.load(path)
                try:
                    surf = surf.convert_alpha()
                except Exception:
                    pass  # 无显示环境（测试/无头）直接使用原 surface
                _VEHICLE_IMAGES[vid] = surf
        except Exception:
            _VEHICLE_IMAGES.pop(vid, None)
    return _VEHICLE_IMAGES


class Vehicle:
    """玩家召唤载具：专属血条、不应用回血、可被僵尸破坏"""

    def __init__(self, vehicle_type, x, y, damage_mult=1.0, tint=None):
        self.type_id = vehicle_type          # v2.2.7 三级全为 "truck"（大运），tint 区分红/黄/银
        self.tint = tint                     # v2.2.7 载具皮肤色调（None=原图）
        self.x = float(x)
        self.y = float(y)
        self.damage_mult = damage_mult
        self.facing_angle = 0.0

        # === 类型属性表（等级1重卡为基础，2坦克、3武直增强）===
        base = {
            "hp": 900, "speed": 250, "size": 46, "ram_damage": 70,
            "immune_melee": False, "can_shoot": False,
            "mag_size": 0, "mag_left": 0, "reload_time": 0.0,
            "fire_rate": 0.0, "fire_timer": 0.0, "rocket_cd": 0.0,
            "armor_reduction": 0.0,
        }
        if vehicle_type == "tank":
            base.update({
                "hp": 1800, "speed": 195, "size": 58, "ram_damage": 130,
                "can_shoot": True, "mag_size": 4, "mag_left": 4,
                "reload_time": 2.6, "fire_rate": 0.0, "armor_reduction": 0.35,
            })
        elif vehicle_type == "heli":
            base.update({
                "hp": 1100, "speed": 340, "size": 48, "ram_damage": 95,
                "immune_melee": True, "can_shoot": True,
                "fire_rate": 0.14, "fire_timer": 0.0, "rocket_cd": 0.0,
                "armor_reduction": 0.15,
            })

        self.max_hp = base["hp"]
        self.hp = self.max_hp
        self.speed = base["speed"]
        self.size = base["size"]
        self.ram_damage = base["ram_damage"]
        self.immune_melee = base["immune_melee"]
        self.can_shoot = base["can_shoot"]
        self.mag_size = base["mag_size"]
        self.mag_left = base["mag_left"]
        self.reload_time = base["reload_time"]
        self.reload_timer = 0.0
        self.fire_rate = base["fire_rate"]
        self.fire_timer = 0.0
        self.rocket_cd = 0.0
        self.armor_reduction = base["armor_reduction"]

        self.dead = False
        self.shake_timer = 0.0
        self.image = _VEHICLE_IMAGES.get(vehicle_type)

    # ==================== 状态 ====================
    @property
    def alive(self):
        return not self.dead

    def take_damage(self, dmg, damage_type="melee"):
        """载具专属血条。武直无视近战；减伤装甲生效；不应用回血"""
        if self.dead:
            return
        if self.immune_melee and damage_type in ("melee", "bite"):
            return
        dmg = max(0, dmg * (1.0 - self.armor_reduction))
        self.hp -= dmg
        self.shake_timer = 0.2
        if self.hp <= 0:
            self.hp = 0
            self.dead = True

    def update(self, dt):
        if self.dead:
            return
        if self.reload_timer > 0:
            self.reload_timer = max(0.0, self.reload_timer - dt)
            if self.reload_timer <= 0 and self.mag_size > 0:
                self.mag_left = self.mag_size
        if self.fire_timer > 0:
            self.fire_timer = max(0.0, self.fire_timer - dt)
        if self.rocket_cd > 0:
            self.rocket_cd = max(0.0, self.rocket_cd - dt)
        if self.shake_timer > 0:
            self.shake_timer = max(0.0, self.shake_timer - dt)

    # ==================== 移动 ====================
    def move(self, move_x, move_y, dt, clamp_func=None):
        """按输入方向移动载具（重卡/坦克/武直共用），返回实际位移后的坐标"""
        if self.dead:
            return self.x, self.y
        length = math.hypot(move_x, move_y)
        if length > 0:
            move_x /= length
            move_y /= length
        nx = self.x + move_x * self.speed * dt
        ny = self.y + move_y * self.speed * dt
        if clamp_func is not None:
            try:
                nx, ny = clamp_func(nx, ny, self.size)
            except Exception:
                pass
        self.x, self.y = nx, ny
        if length > 0:
            self.facing_angle = math.degrees(math.atan2(move_y, move_x))
        return self.x, self.y

    # ==================== 撞击 ====================
    def ram_enemies(self, enemies, damage_numbers=None, particles=None):
        """载具撞击伤害（v2.2.3）：仅车头前方 ±80° 扇形内的敌人受伤；
        武装直升机不参与撞击（低空飞行，不碾压地面单位）"""
        if self.dead or self.type_id == "heli":
            return []
        hit_list = []
        facing = self.facing_angle
        for enemy in enemies:
            if not getattr(enemy, "alive", False):
                continue
            dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
            hit_radius = self.size + getattr(enemy, "size", 20) + 6
            if dist >= hit_radius:
                continue
            # 方向性：只撞车头前方（侧面/后方擦过不造成撞击伤害）
            if dist > 1:
                ang_to = math.degrees(math.atan2(enemy.y - self.y, enemy.x - self.x))
                diff = abs((ang_to - facing + 180) % 360 - 180)
                if diff > 80.0:
                    continue
            actual = self.ram_damage * self.damage_mult
            enemy.take_damage(actual)
            # 击退（沿车头方向推出）
            kb = 140
            push_ang = math.radians(facing)
            enemy.x += math.cos(push_ang) * kb
            enemy.y += math.sin(push_ang) * kb
            if damage_numbers is not None:
                damage_numbers.append(
                    __import__("ui", fromlist=["DamageNumber"]).DamageNumber(
                        enemy.x, enemy.y, int(actual), is_crit=False, damage_type="melee"))
            hit_list.append(enemy)
            if not getattr(enemy, "alive", False):
                on_death = getattr(self, "on_enemy_death_cb", None)
                if on_death is not None:
                    try:
                        on_death(enemy)
                    except Exception:
                        pass
        return hit_list

    # ==================== 射击 ====================
    def fire(self, x, y, angle_deg, damage_mult=1.0):
        """载具开火：
        - 坦克：主炮 4 发弹夹（3 高爆 + 1 穿甲），换弹间隔长
        - 武直：机炮连射 + 火箭弹（CD 到自动补一发）
        返回 Projectile 列表（无弹药/冷却中返回空）
        """
        if self.dead or not self.can_shoot:
            return []
        projs = []
        ang = math.radians(angle_deg)
        if self.type_id == "tank":
            if self.mag_left <= 0:
                return []
            if self.fire_timer > 0:
                return []
            self.mag_left -= 1
            is_ap = (self.mag_left == 0)  # 最后一发为穿甲弹
            self.fire_timer = 0.5 if not is_ap else 0.5
            if not is_ap:
                # 高爆弹：≈1级手雷，命中/到点爆炸
                projs.append(Projectile(
                    x, y,
                    math.cos(ang) * 420, math.sin(ang) * 420,
                    int(60 * damage_mult), 520, (255, 165, 30), 9,
                    explosive=True, explosion_radius=70,
                ))
            else:
                # 尾翼稳定穿甲弹：穿透尸群（pierce 高、速度快、伤害高）
                projs.append(Projectile(
                    x, y,
                    math.cos(ang) * 900, math.sin(ang) * 900,
                    int(180 * damage_mult), 900, (255, 80, 80), 6,
                    pierce=12,
                ))
            if self.mag_left <= 0:
                self.reload_timer = self.reload_time
        elif self.type_id == "heli":
            if self.fire_timer > 0:
                # 机炮冷却中仍可打火箭
                if self.rocket_cd <= 0 and self.mag_left < 99:
                    pass
            else:
                self.fire_timer = self.fire_rate
                projs.append(Projectile(
                    x, y,
                    math.cos(ang) * 780, math.sin(ang) * 780,
                    int(18 * damage_mult), 700, (255, 220, 120), 4,
                    pierce=2,
                ))
            # 火箭弹（CD 2s）
            if self.rocket_cd <= 0:
                self.rocket_cd = 2.2
                projs.append(Projectile(
                    x, y,
                    math.cos(ang) * 480, math.sin(ang) * 480,
                    int(110 * damage_mult), 600, (255, 120, 0), 12,
                    explosive=True, explosion_radius=90,
                ))
        return projs

    # ==================== 绘制 ====================
    def get_image(self):
        return self.image

    def draw(self, screen, cam_x=0.0, cam_y=0.0, scale=1.0):
        """绘制载具（图片或回退图形）。cam_x/cam_y 为相机世界坐标，scale 为缩放"""
        if self.dead:
            return
        sx = (self.x - cam_x) * scale
        sy = (self.y - cam_y) * scale
        # 震动偏移
        ox = oy = 0.0
        if self.shake_timer > 0:
            ox = (self.shake_timer * 30.0) * math.sin(self.shake_timer * 90)
            oy = (self.shake_timer * 30.0) * math.cos(self.shake_timer * 70)
        img = self.image
        if img is not None:
            if self.tint is not None:
                try:
                    _t = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                    _t.fill((*self.tint, 110))
                    _img2 = img.copy()
                    _img2.blit(_t, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    _img2.blit(_t, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                    img = _img2
                except Exception:
                    pass
            rot = pygame.transform.rotozoom(img, -self.facing_angle, scale)
            rect = rot.get_rect(center=(int(sx + ox), int(sy + oy)))
            screen.blit(rot, rect)
        else:
            # 回退图形
            color = {"truck": (200, 120, 40), "tank": (60, 110, 60), "heli": (90, 150, 190)}.get(self.type_id, (150, 150, 150))
            rect = pygame.Rect(0, 0, int(self.size * 2 * scale), int(self.size * 2 * scale))
            rect.center = (int(sx + ox), int(sy + oy))
            pygame.draw.rect(screen, color, rect, border_radius=8)
            pygame.draw.rect(screen, (255, 255, 255), rect, 2, border_radius=8)
        # 专属血条（载具上方）
        bar_w = int(90 * scale)
        bar_h = int(8 * scale)
        bx = int(sx - bar_w // 2)
        by = int(sy - self.size * scale - 16)
        ratio = max(0.0, self.hp / max(1, self.max_hp))
        pygame.draw.rect(screen, (40, 40, 40), (bx, by, bar_w, bar_h))
        bar_color = (80, 220, 90) if ratio > 0.5 else ((240, 200, 40) if ratio > 0.25 else (240, 60, 50))
        pygame.draw.rect(screen, bar_color, (bx, by, int(bar_w * ratio), bar_h))
