#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏世界和波次管理模块 - 尸潮系统 + 特殊道具"""

import pygame
import random
import math
from config import (GameMode, EnemyType, ItemType, MapType, MAP_CONFIGS,
                    DARK_GRAY, GRAY, BROWN, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, CYAN, PURPLE, WHITE, CHARCOAL, DARK_RED)

class SpecialItem:
    """特殊道具 - 随机刷新在地图上"""
    def __init__(self, x, y, item_type):
        self.x = x
        self.y = y
        self.item_type = item_type
        self.size = 12
        self.alive = True
        self.lifetime = 45.0
        self.pulse_timer = 0

        self.colors = {
            ItemType.VACCINE: (GREEN, CYAN),
            ItemType.HEALTH_PACK: (RED, WHITE),
            ItemType.AMMO_BOX: (YELLOW, ORANGE),
            ItemType.SPEED_BOOST: (BLUE, CYAN),
            ItemType.DAMAGE_BOOST: (ORANGE, RED),
            ItemType.SHIELD_REPAIR: (BLUE, WHITE),
            ItemType.WEAPON_BOX: ((139, 90, 43), (200, 160, 80)),
            ItemType.TREASURE_CHEST: ((218, 165, 32), (255, 215, 0)),
            ItemType.SKILL_SLOT: ((255, 215, 0), (255, 255, 200)),
            ItemType.BUFF_CHARM: ((0, 200, 200), (150, 255, 255)),
        }
        # 武器箱和宝箱更大、存在更久
        if item_type in (ItemType.WEAPON_BOX, ItemType.TREASURE_CHEST):
            self.size = 18
            self.lifetime = 120.0
        if item_type == ItemType.TREASURE_CHEST:
            self.size = 22
        self.color = self.colors.get(item_type, (WHITE, GRAY))[0]
        self.glow_color = self.colors.get(item_type, (WHITE, GRAY))[1]

    def update(self, dt):
        self.lifetime -= dt
        self.pulse_timer += dt
        if self.lifetime <= 0:
            self.alive = False

    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, self.size * 2, self.size * 2)

    def draw(self, screen, camera_x, camera_y, scale=1.0):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(2, int(self.size * scale))

        pulse = abs(math.sin(self.pulse_timer * 3)) * 0.5 + 0.5

        if self.item_type == ItemType.WEAPON_BOX:
            # 武器箱：木质军箱外观
            glow_s = int(s * (1 + pulse * 0.3))
            glow = pygame.Surface((glow_s * 2, glow_s * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*self.glow_color[:3], int(60 * pulse)), (glow_s, glow_s), glow_s)
            screen.blit(glow, (px - glow_s, py - glow_s))
            # 箱体
            box_rect = pygame.Rect(px - s, py - s, s * 2, s * 2)
            pygame.draw.rect(screen, self.color, box_rect, border_radius=3)
            pygame.draw.rect(screen, (80, 50, 20), box_rect, max(1, int(2 * scale)), border_radius=3)
            # 金属条
            pygame.draw.rect(screen, (100, 100, 110), (px - s, py - int(s * 0.3), s * 2, max(2, int(4 * scale))))
            pygame.draw.rect(screen, (100, 100, 110), (px - int(s * 0.3), py - s, max(2, int(4 * scale)), s * 2))
            # 锁
            pygame.draw.rect(screen, (180, 180, 190), (px - int(s * 0.2), py - int(s * 0.1), int(s * 0.4), int(s * 0.3)), border_radius=2)
        elif self.item_type == ItemType.TREASURE_CHEST:
            # 宝箱：金色发光宝箱
            glow_s = int(s * (1 + pulse * 0.6))
            glow = pygame.Surface((glow_s * 2, glow_s * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*self.glow_color[:3], int(100 * pulse)), (glow_s, glow_s), glow_s)
            screen.blit(glow, (px - glow_s, py - glow_s))
            # 箱体
            box_rect = pygame.Rect(px - s, py - int(s * 0.7), s * 2, int(s * 1.4))
            pygame.draw.rect(screen, (139, 90, 43), box_rect, border_radius=4)
            # 金色边框
            pygame.draw.rect(screen, self.color, box_rect, max(2, int(3 * scale)), border_radius=4)
            # 箱盖
            lid_rect = pygame.Rect(px - s, py - int(s * 0.9), s * 2, int(s * 0.5))
            pygame.draw.rect(screen, (160, 100, 50), lid_rect, border_radius=4)
            pygame.draw.rect(screen, self.glow_color, lid_rect, max(1, int(2 * scale)), border_radius=4)
            # 锁
            pygame.draw.rect(screen, self.glow_color, (px - int(s * 0.2), py - int(s * 0.2), int(s * 0.4), int(s * 0.35)), border_radius=2)
            # 闪光粒子
            for i in range(3):
                angle = self.pulse_timer * 2 + i * 2.1
                spark_x = px + int(math.cos(angle) * s * 1.2)
                spark_y = py + int(math.sin(angle) * s * 1.2)
                pygame.draw.circle(screen, (255, 255, 200, int(150 * pulse)), (spark_x, spark_y), max(1, int(2 * scale)))
        else:
            glow_s = int(s * (1 + pulse * 0.5))
            pygame.draw.circle(screen, (*self.glow_color[:3], int(100 * pulse)), (px, py), glow_s)
            pygame.draw.circle(screen, self.color, (px, py), s)
            pygame.draw.circle(screen, WHITE, (px, py), s, max(1, int(scale)))


class GameWorld:
    def __init__(self, chunk_size=2000, map_type=MapType.SCHOOL):
        self.chunk_size = chunk_size
        self.map_type = map_type
        self.map_config = MAP_CONFIGS.get(map_type, MAP_CONFIGS[MapType.SCHOOL])
        self.obstacles = []
        self.generated_chunks = set()
        self.items = []
        self.item_spawn_timer = 0
        self.item_spawn_interval = 15.0
        self._generate_initial_area()

    def _generate_initial_area(self):
        self._generate_chunk(0, 0)

    def _get_chunk_key(self, x, y):
        cx = math.floor(x / self.chunk_size)
        cy = math.floor(y / self.chunk_size)
        return (cx, cy)

    def _generate_chunk(self, cx, cy):
        if (cx, cy) in self.generated_chunks:
            return
        self.generated_chunks.add((cx, cy))

        wx_start = cx * self.chunk_size
        wy_start = cy * self.chunk_size

        num_obstacles = random.randint(18, 30)
        # 根据地图类型选择障碍物
        obstacle_pool = self.map_config.get("obstacle_types", [
            'desk', 'chair', 'fence', 'wall', 'barricade', 'pillar', 'debris_pile'
        ])
        for _ in range(num_obstacles):
            obstacle_type = random.choice(obstacle_pool)

            x = random.randint(wx_start + 80, wx_start + self.chunk_size - 80)
            y = random.randint(wy_start + 80, wy_start + self.chunk_size - 80)

            if obstacle_type == 'building':
                w = random.randint(80, 200)
                h = random.randint(80, 200)
                color = random.choice([(60, 50, 45), (55, 55, 60), (50, 45, 40)])
            elif obstacle_type == 'car':
                w = random.randint(50, 80)
                h = random.randint(25, 40)
                color = random.choice([(80, 30, 30), (30, 40, 60), (50, 50, 50), (60, 50, 30)])
            elif obstacle_type == 'fence':
                w = random.randint(100, 250)
                h = random.randint(8, 15)
                color = (70, 65, 55)
            elif obstacle_type == 'wall':
                w = random.randint(60, 150)
                h = random.randint(15, 25)
                color = (65, 60, 55)
            elif obstacle_type == 'barricade':
                w = random.randint(40, 80)
                h = random.randint(20, 35)
                color = (90, 70, 40)
            elif obstacle_type == 'container':
                w = random.randint(60, 100)
                h = random.randint(30, 50)
                color = random.choice([(50, 60, 50), (60, 50, 40), (45, 45, 55)])
            elif obstacle_type == 'debris_pile':
                w = random.randint(30, 60)
                h = random.randint(20, 40)
                color = (55, 50, 45)
            elif obstacle_type == 'pillar':
                w = random.randint(15, 30)
                h = random.randint(15, 30)
                color = (70, 70, 75)
            # === 学校特色障碍物 ===
            elif obstacle_type == 'desk':
                w = random.randint(45, 60)
                h = random.randint(28, 35)
                color = random.choice([(139, 119, 101), (160, 140, 120), (120, 100, 80)])
            elif obstacle_type == 'chair':
                w = random.randint(20, 28)
                h = random.randint(20, 28)
                color = random.choice([(80, 70, 60), (90, 80, 70), (70, 60, 50)])
            elif obstacle_type == 'podium':
                w = random.randint(50, 70)
                h = random.randint(35, 45)
                color = (100, 80, 60)
            elif obstacle_type == 'blackboard':
                w = random.randint(120, 200)
                h = random.randint(15, 20)
                color = (30, 60, 40)
            elif obstacle_type == 'bookshelf':
                w = random.randint(60, 90)
                h = random.randint(20, 30)
                color = (90, 60, 40)
            elif obstacle_type == 'locker':
                w = random.randint(30, 50)
                h = random.randint(40, 55)
                color = random.choice([(60, 80, 100), (80, 60, 60), (60, 80, 60)])
            elif obstacle_type == 'basketball_hoop':
                w = random.randint(25, 35)
                h = random.randint(25, 35)
                color = (200, 80, 80)
            elif obstacle_type == 'pingpong_table':
                w = random.randint(70, 90)
                h = random.randint(35, 45)
                color = (40, 80, 120)
            elif obstacle_type == 'water_dispenser':
                w = random.randint(25, 35)
                h = random.randint(40, 50)
                color = (200, 200, 210)
            elif obstacle_type == 'trash_bin':
                w = random.randint(20, 30)
                h = random.randint(25, 35)
                color = (50, 80, 50)
            elif obstacle_type == 'flower_bed':
                w = random.randint(50, 80)
                h = random.randint(30, 50)
                color = (60, 100, 50)
            elif obstacle_type == 'school_bus':
                w = random.randint(100, 140)
                h = random.randint(40, 55)
                color = (220, 180, 30)
            # === 街区特色障碍物 ===
            elif obstacle_type == 'bus_stop':
                w = random.randint(40, 55)
                h = random.randint(20, 30)
                color = (50, 70, 90)
            elif obstacle_type == 'streetlight':
                w = random.randint(12, 18)
                h = random.randint(50, 70)
                color = (70, 70, 75)
            elif obstacle_type == 'mailbox':
                w = random.randint(15, 22)
                h = random.randint(25, 35)
                color = (40, 60, 120)
            elif obstacle_type == 'fire_hydrant':
                w = random.randint(14, 20)
                h = random.randint(20, 28)
                color = (180, 40, 40)
            elif obstacle_type == 'bench':
                w = random.randint(45, 65)
                h = random.randint(15, 22)
                color = (90, 70, 50)
            elif obstacle_type == 'shopping_cart':
                w = random.randint(25, 35)
                h = random.randint(30, 40)
                color = (80, 80, 85)
            elif obstacle_type == 'vending_machine':
                w = random.randint(28, 38)
                h = random.randint(45, 55)
                color = random.choice([(150, 40, 40), (40, 80, 120), (50, 100, 60)])
            elif obstacle_type == 'dumpster':
                w = random.randint(45, 60)
                h = random.randint(30, 40)
                color = (60, 80, 50)
            # === 市中心特色障碍物 ===
            elif obstacle_type == 'bus':
                w = random.randint(90, 120)
                h = random.randint(35, 45)
                color = random.choice([(180, 160, 40), (50, 80, 120)])
            elif obstacle_type == 'truck':
                w = random.randint(80, 110)
                h = random.randint(35, 45)
                color = random.choice([(120, 50, 40), (50, 60, 70)])
            elif obstacle_type == 'checkpoint':
                w = random.randint(50, 70)
                h = random.randint(25, 35)
                color = (100, 80, 40)
            elif obstacle_type == 'sandbag':
                w = random.randint(30, 50)
                h = random.randint(15, 22)
                color = (130, 110, 70)
            elif obstacle_type == 'wrecked_tank':
                w = random.randint(70, 90)
                h = random.randint(40, 50)
                color = (50, 55, 45)
            elif obstacle_type == 'burning_car':
                w = random.randint(50, 70)
                h = random.randint(25, 35)
                color = (80, 30, 20)
            elif obstacle_type == 'billboard':
                w = random.randint(80, 120)
                h = random.randint(12, 18)
                color = (70, 70, 80)
            # === 郊区特色障碍物 ===
            elif obstacle_type == 'house':
                w = random.randint(70, 100)
                h = random.randint(50, 70)
                color = random.choice([(120, 90, 60), (100, 80, 70), (90, 100, 80)])
            elif obstacle_type == 'shed':
                w = random.randint(35, 50)
                h = random.randint(30, 40)
                color = (100, 70, 45)
            elif obstacle_type == 'tree':
                w = random.randint(30, 45)
                h = random.randint(30, 45)
                color = (30, 70, 30)
            elif obstacle_type == 'bush':
                w = random.randint(25, 40)
                h = random.randint(20, 30)
                color = (40, 80, 35)
            elif obstacle_type == 'well':
                w = random.randint(25, 35)
                h = random.randint(25, 35)
                color = (90, 85, 75)
            elif obstacle_type == 'haystack':
                w = random.randint(35, 50)
                h = random.randint(30, 40)
                color = (180, 150, 60)
            elif obstacle_type == 'tractor':
                w = random.randint(45, 60)
                h = random.randint(35, 45)
                color = (40, 70, 40)
            elif obstacle_type == 'water_tower':
                w = random.randint(35, 50)
                h = random.randint(55, 70)
                color = (100, 100, 110)
            # === 核电站特色障碍物 ===
            elif obstacle_type == 'reactor':
                w = random.randint(80, 110)
                h = random.randint(80, 110)
                color = (40, 50, 70)
            elif obstacle_type == 'pipe':
                w = random.randint(60, 100)
                h = random.randint(12, 20)
                color = (70, 75, 85)
            elif obstacle_type == 'control_panel':
                w = random.randint(40, 60)
                h = random.randint(25, 35)
                color = (50, 55, 65)
            elif obstacle_type == 'barrel':
                w = random.randint(18, 25)
                h = random.randint(25, 32)
                color = random.choice([(150, 120, 30), (40, 80, 100), (120, 40, 40)])
            elif obstacle_type == 'crate':
                w = random.randint(25, 35)
                h = random.randint(25, 35)
                color = (110, 85, 50)
            elif obstacle_type == 'generator':
                w = random.randint(45, 60)
                h = random.randint(35, 45)
                color = (60, 60, 70)
            elif obstacle_type == 'cooling_tower':
                w = random.randint(60, 80)
                h = random.randint(70, 90)
                color = (80, 85, 95)
            elif obstacle_type == 'radiation_barrier':
                w = random.randint(40, 60)
                h = random.randint(15, 22)
                color = (200, 180, 30)
            elif obstacle_type == 'terminal':
                w = random.randint(25, 35)
                h = random.randint(30, 40)
                color = (30, 35, 45)
            elif obstacle_type == 'server_rack':
                w = random.randint(30, 45)
                h = random.randint(50, 65)
                color = (35, 40, 50)
            else:
                w = random.randint(40, 100)
                h = random.randint(10, 20)
                color = (60, 55, 50)

            self.obstacles.append({
                'rect': pygame.Rect(x, y, w, h),
                'type': obstacle_type,
                'color': color,
                'rotation': random.randint(-5, 5) if obstacle_type in ['car', 'debris_pile'] else 0
            })

    def ensure_chunks_around(self, x, y, radius=1500):
        min_cx = math.floor((x - radius) / self.chunk_size)
        max_cx = math.floor((x + radius) / self.chunk_size)
        min_cy = math.floor((y - radius) / self.chunk_size)
        max_cy = math.floor((y + radius) / self.chunk_size)

        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                self._generate_chunk(cx, cy)

    def spawn_item(self, player_x, player_y, min_dist=300, max_dist=800):
        angle = random.uniform(0, math.pi * 2)
        dist = random.uniform(min_dist, max_dist)
        x = player_x + math.cos(angle) * dist
        y = player_y + math.sin(angle) * dist

        weights = [0.04, 0.20, 0.20, 0.16, 0.12, 0.08, 0.07, 0.04, 0.05, 0.04]
        types = [ItemType.VACCINE, ItemType.HEALTH_PACK, ItemType.AMMO_BOX, 
                ItemType.SPEED_BOOST, ItemType.DAMAGE_BOOST, ItemType.SHIELD_REPAIR,
                ItemType.WEAPON_BOX, ItemType.TREASURE_CHEST,
                ItemType.SKILL_SLOT, ItemType.BUFF_CHARM]
        item_type = random.choices(types, weights=weights)[0]

        self.items.append(SpecialItem(x, y, item_type))

    def update(self, dt, player_x, player_y):
        self.ensure_chunks_around(player_x, player_y)

        for item in self.items[:]:
            item.update(dt)
            if not item.alive:
                self.items.remove(item)

        self.item_spawn_timer += dt
        if self.item_spawn_timer >= self.item_spawn_interval:
            self.item_spawn_timer = 0
            if len(self.items) < 8:
                self.spawn_item(player_x, player_y)

    def check_collision(self, rect):
        for obs in self.obstacles:
            if rect.colliderect(obs['rect']):
                return True
        return False


    def is_position_safe(self, x, y, size):
        """检查位置是否安全（不在障碍物内）"""
        test_rect = pygame.Rect(x - size, y - size, size * 2, size * 2)
        return not self.check_collision(test_rect)

    def find_safe_position(self, x, y, size, max_search_radius=200):
        """找到最近的安全位置"""
        if self.is_position_safe(x, y, size):
            return x, y

        # 螺旋搜索
        for radius in range(10, max_search_radius + 1, 10):
            for angle in range(0, 360, 30):
                rad = math.radians(angle)
                test_x = x + math.cos(rad) * radius
                test_y = y + math.sin(rad) * radius
                if self.is_position_safe(test_x, test_y, size):
                    return test_x, test_y
        return x, y  # 如果找不到，返回原位置

    def clamp_position(self, x, y, size):
        self.ensure_chunks_around(x, y)
        return x, y

    def draw(self, screen, camera_x, camera_y, scale=1.0):
        screen_w = screen.get_width()
        screen_h = screen.get_height()

        visible_left = camera_x - 100
        visible_right = camera_x + screen_w / scale + 100
        visible_top = camera_y - 100
        visible_bottom = camera_y + screen_h / scale + 100

        tile_size = int(100 * scale)

        start_x = math.floor(visible_left / 100) * 100
        start_y = math.floor(visible_top / 100) * 100

        for x in range(int(start_x), int(visible_right) + 100, 100):
            for y in range(int(start_y), int(visible_bottom) + 100, 100):
                px = int((x - camera_x) * scale)
                py = int((y - camera_y) * scale)
                if -tile_size <= px <= screen_w and -tile_size <= py <= screen_h:
                    color = CHARCOAL if (x // 100 + y // 100) % 2 == 0 else DARK_GRAY
                    pygame.draw.rect(screen, color, (px, py, tile_size + 1, tile_size + 1))

        for item in self.items:
            item.draw(screen, camera_x, camera_y, scale)

        for obs in self.obstacles:
            rect = obs['rect']
            if rect.right < visible_left or rect.left > visible_right or                rect.bottom < visible_top or rect.top > visible_bottom:
                continue

            draw_rect = pygame.Rect(
                int((rect.x - camera_x) * scale),
                int((rect.y - camera_y) * scale),
                int(rect.width * scale),
                int(rect.height * scale)
            )

            obs_type = obs['type']
            color = obs['color']

            if obs_type == 'building':
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.rect(screen, (color[0]+20, color[1]+20, color[2]+20), draw_rect, max(1, int(2*scale)))
                for wx in range(draw_rect.x + 5, draw_rect.right - 5, 20):
                    for wy in range(draw_rect.y + 5, draw_rect.bottom - 5, 20):
                        if random.random() < 0.3:
                            win_color = (80, 90, 100) if random.random() < 0.5 else (20, 20, 25)
                            pygame.draw.rect(screen, win_color, 
                                (wx, wy, int(8*scale), int(8*scale)))
            elif obs_type == 'car':
                pygame.draw.ellipse(screen, color, draw_rect)
                pygame.draw.ellipse(screen, (color[0]-20, color[1]-20, color[2]-20), draw_rect, max(1, int(2*scale)))
                win_rect = pygame.Rect(draw_rect.x + draw_rect.width//4, 
                                      draw_rect.y + 2, 
                                      draw_rect.width//2, 
                                      draw_rect.height//3)
                pygame.draw.rect(screen, (40, 50, 60), win_rect)
            elif obs_type == 'fence':
                pygame.draw.rect(screen, color, draw_rect)
                for fx in range(draw_rect.x, draw_rect.right, 15):
                    pygame.draw.line(screen, (color[0]+15, color[1]+15, color[2]+15),
                                    (fx, draw_rect.y), (fx, draw_rect.bottom), max(1, int(scale)))
            elif obs_type == 'wall':
                pygame.draw.rect(screen, color, draw_rect)
                brick_h = max(3, int(6 * scale))
                for by in range(draw_rect.y, draw_rect.bottom, brick_h):
                    offset = (by // brick_h) % 2 * 10
                    for bx in range(draw_rect.x + offset, draw_rect.right, 20):
                        pygame.draw.line(screen, (color[0]-10, color[1]-10, color[2]-10),
                                        (bx, by), (bx, min(by+brick_h, draw_rect.bottom)), max(1, int(scale)))
            elif obs_type == 'barricade':
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.line(screen, (color[0]+30, color[1]+30, color[2]+30),
                                draw_rect.topleft, draw_rect.bottomright, max(2, int(3*scale)))
                pygame.draw.line(screen, (color[0]+30, color[1]+30, color[2]+30),
                                draw_rect.topright, draw_rect.bottomleft, max(2, int(3*scale)))
            elif obs_type == 'container':
                pygame.draw.rect(screen, color, draw_rect)
                stripe_h = max(2, int(4 * scale))
                for sy in range(draw_rect.y, draw_rect.bottom, stripe_h * 2):
                    pygame.draw.rect(screen, (color[0]+10, color[1]+10, color[2]+10),
                                    (draw_rect.x, sy, draw_rect.width, stripe_h))
            elif obs_type == 'debris_pile':
                center = draw_rect.center
                radius = min(draw_rect.width, draw_rect.height) // 2
                pygame.draw.circle(screen, color, center, radius)
                for _ in range(5):
                    offset_x = random.randint(-max(1, radius//2), max(1, radius//2))
                    offset_y = random.randint(-max(1, radius//2), max(1, radius//2))
                    upper = max(3, radius // 3)
                    r2 = random.randint(2, upper)

                    pygame.draw.circle(screen, (color[0]+15, color[1]+15, color[2]+15),
                                     (center[0]+offset_x, center[1]+offset_y), r2)
            elif obs_type == 'pillar':
                pygame.draw.rect(screen, color, draw_rect, border_radius=max(2, int(4*scale)))
                pygame.draw.rect(screen, (color[0]+20, color[1]+20, color[2]+20), draw_rect, 
                                max(1, int(2*scale)), border_radius=max(2, int(4*scale)))
            # === 学校特色障碍物绘制 ===
            elif obs_type == 'desk':
                # 课桌：桌面+桌腿
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.rect(screen, (color[0]-20, color[1]-20, color[2]-20), draw_rect, max(1, int(2*scale)))
                # 桌洞
                hole_rect = pygame.Rect(draw_rect.x + 5, draw_rect.y + 3, draw_rect.width - 10, draw_rect.height // 3)
                pygame.draw.rect(screen, (color[0]-30, color[1]-30, color[2]-30), hole_rect)
            elif obs_type == 'chair':
                # 椅子：座面+靠背
                pygame.draw.rect(screen, color, draw_rect)
                back_rect = pygame.Rect(draw_rect.x, draw_rect.y - draw_rect.height // 2, draw_rect.width, draw_rect.height // 2)
                pygame.draw.rect(screen, (color[0]-15, color[1]-15, color[2]-15), back_rect)
            elif obs_type == 'podium':
                # 讲台：梯形感
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.rect(screen, (color[0]+20, color[1]+20, color[2]+20), draw_rect, max(1, int(2*scale)))
                # 讲台桌面
                top_rect = pygame.Rect(draw_rect.x - 3, draw_rect.y - 4, draw_rect.width + 6, 6)
                pygame.draw.rect(screen, (color[0]+10, color[1]+10, color[2]+10), top_rect)
            elif obs_type == 'blackboard':
                # 黑板：绿色板面+木框
                pygame.draw.rect(screen, (80, 50, 30), draw_rect)  # 木框
                inner = pygame.Rect(draw_rect.x + 3, draw_rect.y + 3, max(2, draw_rect.width - 6), max(2, draw_rect.height - 6))
                pygame.draw.rect(screen, color, inner)
                # 粉笔字迹
                if random.random() < 0.5 and inner.width > 20 and inner.height > 8:
                    for _ in range(3):
                        wx = random.randint(inner.x + 5, max(inner.x + 6, inner.right - 15))
                        wy = random.randint(inner.y + 2, max(inner.y + 3, inner.bottom - 3))
                        line_len = random.randint(3, max(4, min(15, inner.width // 3)))
                        pygame.draw.line(screen, (200, 200, 200), (wx, wy), (wx + line_len, wy), max(1, int(scale)))
            elif obs_type == 'bookshelf':
                # 书架：多层隔板+书籍
                pygame.draw.rect(screen, color, draw_rect)
                shelf_h = max(4, draw_rect.height // 3)
                for i in range(1, 3):
                    pygame.draw.line(screen, (color[0]-20, color[1]-20, color[2]-20),
                                    (draw_rect.x, draw_rect.y + shelf_h * i),
                                    (draw_rect.right, draw_rect.y + shelf_h * i), max(1, int(2*scale)))
                # 书籍
                if draw_rect.width > 15 and shelf_h > 6:
                    book_colors = [(180, 50, 50), (50, 80, 150), (180, 150, 50), (100, 50, 120), (50, 120, 80)]
                    for row in range(3):
                        bx = draw_rect.x + 3
                        while bx < draw_rect.right - 5:
                            bw = random.randint(3, min(8, max(3, (draw_rect.width - 10) // 4)))
                            bc = random.choice(book_colors)
                            pygame.draw.rect(screen, bc, (bx, draw_rect.y + row * shelf_h + 2, bw, max(2, shelf_h - 4)))
                            bx += bw + 1
            elif obs_type == 'locker':
                # 储物柜：多格柜门
                pygame.draw.rect(screen, color, draw_rect)
                cols = 2 if draw_rect.width > 35 else 1
                rows = 3 if draw_rect.height > 45 else 2
                cw = max(4, draw_rect.width // cols)
                rh = max(6, draw_rect.height // rows)
                for c in range(cols):
                    for r in range(rows):
                        lx = draw_rect.x + c * cw + 1
                        ly = draw_rect.y + r * rh + 1
                        locker_rect = pygame.Rect(lx, ly, max(2, cw - 2), max(2, rh - 2))
                        pygame.draw.rect(screen, (color[0]+15, color[1]+15, color[2]+15), locker_rect, max(1, int(1*scale)))
                        # 门把手
                        if cw > 8:
                            pygame.draw.circle(screen, (200, 200, 100), 
                                             (locker_rect.right - 3, locker_rect.centery), max(1, int(2*scale)))
            elif obs_type == 'basketball_hoop':
                # 篮球架：立柱+篮板+篮筐
                pygame.draw.rect(screen, (80, 80, 80), 
                                pygame.Rect(draw_rect.centerx - 2, draw_rect.y, 4, draw_rect.height))
                backboard = pygame.Rect(draw_rect.x, draw_rect.y, draw_rect.width, draw_rect.height // 2)
                pygame.draw.rect(screen, (240, 240, 240), backboard)
                pygame.draw.rect(screen, (100, 100, 100), backboard, max(1, int(2*scale)))
                # 篮筐
                pygame.draw.circle(screen, (200, 80, 80), 
                                 (backboard.centerx, backboard.bottom + 3), max(2, int(5*scale)), max(1, int(2*scale)))
            elif obs_type == 'pingpong_table':
                # 乒乓球桌：蓝色桌面+中线+球网
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.rect(screen, (255, 255, 255), draw_rect, max(1, int(2*scale)))
                # 中线
                pygame.draw.line(screen, (255, 255, 255), 
                                (draw_rect.centerx, draw_rect.y), 
                                (draw_rect.centerx, draw_rect.bottom), max(1, int(scale)))
                # 球网
                pygame.draw.line(screen, (50, 50, 50), 
                                (draw_rect.x, draw_rect.centery), 
                                (draw_rect.right, draw_rect.centery), max(1, int(2*scale)))
            elif obs_type == 'water_dispenser':
                # 饮水机：机身+水桶
                pygame.draw.rect(screen, color, 
                                pygame.Rect(draw_rect.x, draw_rect.y + draw_rect.height // 3, draw_rect.width, draw_rect.height * 2 // 3))
                # 水桶（蓝色）
                bottle = pygame.Rect(draw_rect.x + 3, draw_rect.y, draw_rect.width - 6, draw_rect.height // 3)
                pygame.draw.ellipse(screen, (60, 120, 200), bottle)
                # 出水口
                pygame.draw.rect(screen, (150, 150, 150), 
                                pygame.Rect(draw_rect.centerx - 3, draw_rect.centery, 6, 8))
            elif obs_type == 'trash_bin':
                # 垃圾桶：圆柱感+盖子
                pygame.draw.rect(screen, color, draw_rect, border_radius=max(2, int(4*scale)))
                pygame.draw.rect(screen, (color[0]-20, color[1]-20, color[2]-20), 
                                pygame.Rect(draw_rect.x - 2, draw_rect.y - 3, draw_rect.width + 4, 5))
            elif obs_type == 'flower_bed':
                # 花坛：泥土+花朵
                pygame.draw.rect(screen, (80, 50, 30), draw_rect)  # 边框
                inner = pygame.Rect(draw_rect.x + 2, draw_rect.y + 2, max(2, draw_rect.width - 4), max(2, draw_rect.height - 4))
                pygame.draw.rect(screen, (60, 40, 25), inner)  # 泥土
                # 花朵
                if inner.width > 10 and inner.height > 10:
                    flower_colors = [(255, 100, 150), (255, 200, 50), (150, 100, 255), (255, 150, 50)]
                    for _ in range(random.randint(2, 5)):
                        fx = random.randint(inner.x + 3, max(inner.x + 4, inner.right - 3))
                        fy = random.randint(inner.y + 3, max(inner.y + 4, inner.bottom - 3))
                        pygame.draw.circle(screen, random.choice(flower_colors), (fx, fy), max(2, int(3*scale)))
            elif obs_type == 'school_bus':
                # 校车：车身+窗户+轮子
                pygame.draw.rect(screen, color, draw_rect, border_radius=max(2, int(5*scale)))
                # 窗户
                win_w = draw_rect.width // 5
                for i in range(4):
                    win_rect = pygame.Rect(draw_rect.x + 8 + i * win_w, draw_rect.y + 5, win_w - 4, draw_rect.height // 3)
                    pygame.draw.rect(screen, (150, 200, 230), win_rect)
                # 轮子
                pygame.draw.circle(screen, (30, 30, 30), 
                                 (draw_rect.x + draw_rect.width // 4, draw_rect.bottom), max(3, int(6*scale)))
                pygame.draw.circle(screen, (30, 30, 30), 
                                 (draw_rect.right - draw_rect.width // 4, draw_rect.bottom), max(3, int(6*scale)))
            else:
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.rect(screen, (color[0]-15, color[1]-15, color[2]-15), draw_rect, max(1, int(2*scale)))

            shadow_rect = draw_rect.copy()
            shadow_rect.y += max(2, int(3*scale))
            pygame.draw.rect(screen, (0, 0, 0, 80), shadow_rect, border_radius=2)


class HordeManager:
    def __init__(self, game_mode, difficulty):
        self.game_mode = game_mode
        self.difficulty = difficulty

        # 基础参数（开局）
        self.base_horde_duration = 32.0
        self.min_horde_duration = 14.0    # 尸潮持续时间下限，不能比这个更短
        self.base_horde_cooldown = 60.0
        self.min_horde_cooldown = 30.0    # 冷却间隔下限

        self.base_boss_chance_horde = 0.08
        self.base_spawn_rate_horde = 0.35
        self.base_spawn_rate_normal = 1.8

        # 难度修正系数
        diff_mod = {
            "简单": {"dur_mod":1.2, "cd_mod":1.2, "boss":0.04, "spawn_h":0.5, "spawn_n":2.2},
            "普通": {"dur_mod":1.0, "cd_mod":1.0, "boss":0.08, "spawn_h":0.35, "spawn_n":1.8},
            "困难": {"dur_mod":0.85, "cd_mod":0.85, "boss":0.12, "spawn_h":0.28, "spawn_n":1.4},
            "地狱": {"dur_mod":0.70, "cd_mod":0.70, "boss":0.16, "spawn_h":0.20, "spawn_n":1.0},
        }[difficulty]

        self.dur_mod = diff_mod["dur_mod"]
        self.cd_mod = diff_mod["cd_mod"]
        self.base_boss_chance_horde = diff_mod["boss"]
        self.base_spawn_rate_horde = diff_mod["spawn_h"]
        self.base_spawn_rate_normal = diff_mod["spawn_n"]

        self.horde_active = False
        self.timer = self.base_horde_cooldown * self.cd_mod

        self.boss_spawned_this_horde = False
        self.spawn_timer = 0.0
        self.total_time = 0.0

        self.endless_glitch_shown = False
        self.glitch_trigger_time = 1200.0
        # 无尽模式专属：前置倒计时（较短，营造紧张感后出错）
        self.endless_countdown_total = 90
        self.endless_countdown_left = 90

    def update(self, dt):
        self.total_time += dt
        if self.game_mode == GameMode.ENDLESS:
            # 先走倒计时，倒计时归零后触发glitch变为正向计时
            if not self.endless_glitch_shown:
                self.endless_countdown_left -= dt
                if self.endless_countdown_left <= 0:
                    self.endless_glitch_shown = True
        # 尸潮逻辑
        self.timer -= dt
        if self.horde_active:
            if self.timer <= 0:
                self.horde_active = False
                new_cd = self._get_current_horde_cooldown()
                self.timer = new_cd
                self.boss_spawned_this_horde = False
        else:
            if self.timer <= 0:
                self.horde_active = True
                new_dur = self._get_current_horde_duration()
                self.timer = new_dur
                self.boss_spawned_this_horde = False
        self.spawn_timer -= dt

    def get_time_display(self):
        """返回(显示文本, 是否倒计时模式)"""
        if self.game_mode == GameMode.TIMED:
            # 限时模式原有逻辑不变
            remain = max(0, 900 - self.total_time)
            m = int(remain // 60)
            s = int(remain % 60)
            return f"{m:02d}:{s:02d}", True
        else:
            # 无尽模式
            if not self.endless_glitch_shown:
                # 前置倒计时
                cd = max(0, self.endless_countdown_left)
                m = int(cd // 60)
                s = int(cd % 60)
                return f"{m:02d}:{s:02d}", True
            else:
                # glitch阶段正向计时（从倒计时结束后开始算）
                secs = self.total_time - self.endless_countdown_total
                m = int(secs // 60)
                s = int(secs % 60)
                return f"{m}:{s:02d}", False

    def is_horde_active(self):
        return self.horde_active

    def get_horde_progress(self):
        if self.horde_active:
            return 0.0
        return min(1.0, 1.0 - (self.timer / (self._get_current_horde_cooldown())))

    def _get_current_horde_duration(self):
        """计算当前尸潮持续时间：随时间变短，有下限，叠加难度"""
        # 每120秒，尸潮时长衰减一部分，最大衰减系数0.45
        time_decay = max(0.45, 1.0 - self.total_time / 240.0)
        dur = self.base_horde_duration * self.dur_mod * time_decay
        return max(self.min_horde_duration, dur)

    def _get_current_horde_cooldown(self):
        """计算当前尸潮冷却间隔，随时间变短，有下限"""
        time_decay = max(0.50, 1.0 - self.total_time / 300.0)
        cd = self.base_horde_cooldown * self.cd_mod * time_decay
        return max(self.min_horde_cooldown, cd)

    def should_spawn(self):
        import random
        time_factor = min(2.2, 1.0 + self.total_time / 180.0)

        spawn_rate_horde = self.base_spawn_rate_horde / time_factor
        spawn_rate_normal = self.base_spawn_rate_normal / time_factor
        boss_chance_horde = self.base_boss_chance_horde * time_factor

        if self.horde_active:
            spawn_rate = spawn_rate_horde
        else:
            spawn_rate = spawn_rate_normal

        if self.spawn_timer > 0:
            return None
        self.spawn_timer = spawn_rate

        if self.horde_active and (not self.boss_spawned_this_horde) and random.random() < boss_chance_horde:
            if random.random() < 0.5:
                boss_type = EnemyType.BOSS_LONG
            else:
                boss_type = EnemyType.BOSS_XIANG
            self.boss_spawned_this_horde = True
            return boss_type

        base_pool = [
            EnemyType.ZOMBIE_NORMAL,
            EnemyType.ZOMBIE_FAST,
            EnemyType.ZOMBIE_TANK,
        ]
        mid_pool = [
            EnemyType.ZOMBIE_RANGED,
            EnemyType.ZOMBIE_CRAWLER,
        ]
        advanced_pool = [
            EnemyType.ZOMBIE_EXPLODER,
            EnemyType.ZOMBIE_SPLITTER,
            EnemyType.ZOMBIE_SHIELD,
            EnemyType.ZOMBIE_HEALER,
            EnemyType.ZOMBIE_PHANTOM,
        ]

        final_pool = base_pool.copy()
        if self.total_time >= 60.0:
            final_pool.extend(mid_pool)
        if self.total_time >= 120.0:
            final_pool.extend(advanced_pool)

        if self.horde_active:
            return random.choice(final_pool)
        else:
            return random.choice(base_pool)

    def is_timed_over(self):
        if self.game_mode == GameMode.TIMED:
            return self.total_time >= 1200.0
        return False