#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏实体模块 - 玩家、敌人(含新机制僵尸)、经验球、防爆套装等"""

import pygame
import math
import random
from config import *
from weapons import Weapon, Projectile
from skills import SkillTree
from buff import BuffManager, BuffType


class ExpOrb:
    def __init__(self, x, y, value):
        self.x = x
        self.y = y
        self.value = value
        # 经验球按所含经验分级：大小与颜色随之变化
        if value < 15:
            self.size = 5
            self.color = (150, 230, 150)   # 淡绿 - 小
        elif value < 40:
            self.size = 7
            self.color = (80, 200, 80)     # 绿 - 中
        elif value < 100:
            self.size = 9
            self.color = (60, 180, 220)    # 青 - 大
        else:
            self.size = 12
            self.color = (235, 210, 90)    # 金 - 特大
        self.alive = True
        self.magnetized = False
        self.lifetime = 30.0

    def update(self, dt, player_x, player_y, pickup_range):
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False
            return

        dx = player_x - self.x
        dy = player_y - self.y
        dist = math.hypot(dx, dy)

        if dist < pickup_range:
            self.magnetized = True

        if self.magnetized and dist > 10:
            speed = 8 if dist < pickup_range else 3
            self.x += (dx / dist) * speed * dt * 60
            self.y += (dy / dist) * speed * dt * 60

    def draw(self, screen, camera_x, camera_y, scale=1.0):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(1, int(self.size * scale))
        col = self.color
        # 发光效果
        glow_s = s + 3
        glow_surf = pygame.Surface((glow_s * 2, glow_s * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*col[:3], 60), (glow_s, glow_s), glow_s)
        screen.blit(glow_surf, (px - glow_s, py - glow_s))
        pygame.draw.circle(screen, col, (px, py), s)
        pygame.draw.circle(screen, WHITE, (px, py), s, max(1, int(scale)))
