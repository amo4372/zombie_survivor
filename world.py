#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏世界和波次管理模块 - 尸潮系统 + 特殊道具"""

import pygame
import random
import math
from config import GameMode, EnemyType, ItemType, DARK_GRAY, GRAY, BROWN, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, CYAN, PURPLE, WHITE, CHARCOAL, DARK_RED

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
        }
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
        glow_s = int(s * (1 + pulse * 0.5))

        pygame.draw.circle(screen, (*self.glow_color[:3], int(100 * pulse)), (px, py), glow_s)
        pygame.draw.circle(screen, self.color, (px, py), s)
        pygame.draw.circle(screen, WHITE, (px, py), s, max(1, int(scale)))


class GameWorld:
    def __init__(self, chunk_size=2000):
        self.chunk_size = chunk_size
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

        num_obstacles = random.randint(5, 12)
        for _ in range(num_obstacles):
            obstacle_type = random.choice([
                'building', 'car', 'fence', 'wall', 'barricade', 
                'container', 'debris_pile', 'pillar', 'broken_wall'
            ])

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

        weights = [0.05, 0.25, 0.25, 0.2, 0.15, 0.1]
        types = [ItemType.VACCINE, ItemType.HEALTH_PACK, ItemType.AMMO_BOX, 
                ItemType.SPEED_BOOST, ItemType.DAMAGE_BOOST, ItemType.SHIELD_REPAIR]
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
                    offset_x = random.randint(-radius//2, radius//2)
                    offset_y = random.randint(-radius//2, radius//2)
                    upper = max(3, radius // 3)
                    r2 = random.randint(3, upper)

                    pygame.draw.circle(screen, (color[0]+15, color[1]+15, color[2]+15),
                                     (center[0]+offset_x, center[1]+offset_y), r2)
            elif obs_type == 'pillar':
                pygame.draw.rect(screen, color, draw_rect, border_radius=max(2, int(4*scale)))
                pygame.draw.rect(screen, (color[0]+20, color[1]+20, color[2]+20), draw_rect, 
                                max(1, int(2*scale)), border_radius=max(2, int(4*scale)))
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
        self.base_horde_cooldown = 42.0
        self.min_horde_cooldown = 20.0    # 冷却间隔下限

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