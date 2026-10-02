#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏世界和波次管理模块 - 尸潮系统 + 特殊道具"""

import pygame
import random
import math
from config import *

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
        self.magnetized = False

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
            ItemType.INCENDIARY: ((220, 80, 20), (255, 160, 40)),
            ItemType.SMOKE_GRENADE: ((120, 120, 120), (180, 180, 180)),
            ItemType.CLUSTER_BOMB: ((180, 100, 30), (240, 180, 60)),
            ItemType.EMP_GRENADE: ((0, 180, 220), (100, 240, 255)),
            ItemType.RUNE: ((120, 60, 200), (180, 120, 255)),
            ItemType.MYSTERY_BOX: ((90, 90, 140), (160, 160, 220)),
            ItemType.GOLDEN_CHEST: ((218, 165, 32), (255, 230, 120)),
        }
        # 武器箱和宝箱更大、存在更久
        if item_type in (ItemType.WEAPON_BOX, ItemType.TREASURE_CHEST, ItemType.GOLDEN_CHEST,
                         ItemType.RUNE, ItemType.MYSTERY_BOX):
            self.size = 18
            self.lifetime = 120.0
        if item_type in (ItemType.TREASURE_CHEST, ItemType.GOLDEN_CHEST):
            self.size = 22
        self.color = self.colors.get(item_type, (WHITE, GRAY))[0]
        self.glow_color = self.colors.get(item_type, (WHITE, GRAY))[1]

    def update(self, dt, player_x=None, player_y=None):
        self.lifetime -= dt
        self.pulse_timer += dt
        if self.lifetime <= 0:
            self.alive = False
        if self.magnetized and player_x is not None and player_y is not None:
            dx = player_x - self.x
            dy = player_y - self.y
            dist = math.hypot(dx, dy)
            if dist > 5:
                speed = 6
                self.x += (dx / dist) * speed * dt * 60
                self.y += (dy / dist) * speed * dt * 60

    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, self.size * 2, self.size * 2)

    def draw(self, screen, camera_x, camera_y, scale=1.0, assets=None):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(2, int(self.size * scale))

        pulse = abs(math.sin(self.pulse_timer * 3)) * 0.5 + 0.5

        # === 优先使用assets图片绘制 ===
        img_key = None
        item_img_map = {
            ItemType.VACCINE: "item_vaccine",
            ItemType.HEALTH_PACK: "item_health",
            ItemType.AMMO_BOX: "item_ammo",
            ItemType.SPEED_BOOST: "item_speed",
            ItemType.DAMAGE_BOOST: "item_damage",
            ItemType.SHIELD_REPAIR: "item_shield",
            ItemType.WEAPON_BOX: "item_weapon_box",
            ItemType.TREASURE_CHEST: "item_treasure",
            ItemType.SKILL_SLOT: "item_skill_slot",
            ItemType.BUFF_CHARM: "item_buff_charm",
            ItemType.INCENDIARY: "item_incendiary",
            ItemType.SMOKE_GRENADE: "item_smoke",
            ItemType.CLUSTER_BOMB: "item_cluster",
            ItemType.EMP_GRENADE: "item_emp",
            ItemType.RUNE: "item_rune",
            ItemType.MYSTERY_BOX: "item_mystery",
            ItemType.GOLDEN_CHEST: "item_golden",
        }
        img_key = item_img_map.get(self.item_type)
        if assets is not None and img_key is not None and assets.has_image(img_key):
            # 发光效果
            glow_s = int(s * (1 + pulse * 0.5))
            glow = pygame.Surface((glow_s * 2, glow_s * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*self.glow_color[:3], int(80 * pulse)), (glow_s, glow_s), glow_s)
            screen.blit(glow, (px - glow_s, py - glow_s))
            # 图片
            img = assets.get_image(img_key, s * 2, s * 2)
            screen.blit(img, (px - s, py - s))
            return

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




class TextItem:
    """可拾取的文本资料道具"""
    def __init__(self, x, y, text_id):
        self.x = x
        self.y = y
        self.text_id = text_id
        self.size = 10
        self.alive = True
        self.lifetime = 180.0  # 文本道具存在更久
        self.pulse_timer = 0
        self.magnetized = False
        self.color = (200, 180, 100)  # 羊皮纸色
        self.glow_color = (255, 230, 150)

    def update(self, dt, player_x=None, player_y=None):
        self.lifetime -= dt
        self.pulse_timer += dt
        if self.lifetime <= 0:
            self.alive = False
        if self.magnetized and player_x is not None and player_y is not None:
            dx = player_x - self.x
            dy = player_y - self.y
            dist = math.hypot(dx, dy)
            if dist > 5:
                speed = 6
                self.x += (dx / dist) * speed * dt * 60
                self.y += (dy / dist) * speed * dt * 60

    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, self.size * 2, self.size * 2)

    def draw(self, screen, camera_x, camera_y, scale=1.0, assets=None):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(2, int(self.size * scale))
        pulse = abs(math.sin(self.pulse_timer * 2)) * 0.5 + 0.5

        # 发光效果
        glow_s = int(s * (1 + pulse * 0.6))
        glow = pygame.Surface((glow_s * 2, glow_s * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*self.glow_color[:3], int(80 * pulse)), (glow_s, glow_s), glow_s)
        screen.blit(glow, (px - glow_s, py - glow_s))

        # 纸张外观（折叠的纸条）
        paper_rect = pygame.Rect(px - s, py - int(s * 0.8), s * 2, int(s * 1.6))
        pygame.draw.rect(screen, self.color, paper_rect, border_radius=2)
        pygame.draw.rect(screen, (150, 130, 70), paper_rect, max(1, int(scale)), border_radius=2)
        # 纸张折痕
        pygame.draw.line(screen, (170, 150, 90), (px - s + 2, py), (px + s - 2, py), max(1, int(scale)))
        # 文字线条（模拟文字）
        for i in range(3):
            line_y = py - int(s * 0.5) + i * int(s * 0.4)
            line_w = int(s * 1.2) if i != 2 else int(s * 0.8)
            pygame.draw.line(screen, (120, 100, 50), (px - int(s * 0.6), line_y), (px - int(s * 0.6) + line_w, line_y), max(1, int(scale * 0.8)))

class GameWorld:
    def __init__(self, chunk_size=2000, map_type=MapType.SCHOOL):
        self.chunk_size = chunk_size
        self.map_type = map_type
        self.map_config = MAP_CONFIGS.get(map_type, MAP_CONFIGS[MapType.SCHOOL])
        # 地图专属地面瓷砖颜色
        self.ground_colors = {
            MapType.SCHOOL: ((55, 52, 48), (62, 58, 53)),       # 校园 - 灰黄地砖
            MapType.STREET: ((48, 50, 55), (55, 57, 62)),         # 街区 - 灰沥青
            MapType.DOWNTOWN: ((60, 35, 25), (70, 42, 30)),       # 市中心 - 火光橙红
            MapType.SUBURB: ((40, 55, 38), (48, 62, 45)),         # 郊区 - 墨绿草地
            MapType.NUCLEAR_PLANT: ((35, 35, 60), (42, 42, 70)),  # 核电站 - 深紫辐射
        }
        self.tile_color_a, self.tile_color_b = self.ground_colors.get(map_type, ((50, 48, 45), (58, 55, 50)))
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
        self._cx, self._cy = cx, cy
        wx_start = cx * self.chunk_size
        wy_start = cy * self.chunk_size
        margin = 240
        bx0, by0 = wx_start + margin, wy_start + margin
        bx1, by1 = wx_start + self.chunk_size - margin, wy_start + self.chunk_size - margin
        gen = {
            MapType.SCHOOL: self._gen_school,
            MapType.STREET: self._gen_street,
            MapType.DOWNTOWN: self._gen_downtown,
            MapType.SUBURB: self._gen_suburb,
            MapType.NUCLEAR_PLANT: self._gen_nuclear,
        }.get(self.map_type, self._gen_school)
        # 删除情景化大地图：改为普通零散障碍物
        self._gen_scattered(bx0, by0, bx1, by1)

    # ================= 情景化生成辅助 =================
    def _gen_scattered(self, x0, y0, x1, y1):
        """普通零散障碍物：随机散落的基础障碍物（墙壁段/路障/木箱/碎石堆/垃圾桶/树），无情景化布局"""
        W, H = x1 - x0, y1 - y0
        types = ['wall', 'barricade', 'crate', 'debris_pile', 'trash_bin', 'tree']
        count = random.randint(9, 15)
        attempts = 0
        placed = 0
        while placed < count and attempts < 60:
            attempts += 1
            t = random.choice(types)
            if t == 'wall':
                w = random.randint(30, 80); h = random.randint(12, 18)
            elif t == 'tree':
                w = random.randint(22, 34); h = random.randint(22, 34)
            else:
                w = random.randint(16, 34); h = random.randint(16, 34)
            if W - w - 20 <= 0 or H - h - 20 <= 0:
                continue
            cx = x0 + random.randint(10, int(W) - w - 10)
            cy = y0 + random.randint(10, int(H) - h - 10)
            rot = random.choice([0, 90]) if t == 'wall' else 0
            self._add_obs(t, cx, cy, w, h, rot=rot)
            placed += 1

    def _add_obs(self, otype, x, y, w, h, color=None, rot=0):
        """添加一个障碍物(带碰撞), 与已有障碍物重叠则跳过"""
        r = pygame.Rect(int(x), int(y), int(w), int(h))
        if r.width < 4 or r.height < 4:
            return
        # 出生 chunk (0,0) 的玩家出生区保留空地(玩家出生在左上角 0,0)
        if getattr(self, '_cx', None) == 0 and getattr(self, '_cy', None) == 0:
            if r.colliderect(pygame.Rect(0, 0, 460, 460)):
                return
        for o in self.obstacles:
            if o['rect'].colliderect(r):
                return
        if color is None:
            color = self._obs_color(otype)
        self.obstacles.append({'rect': r, 'type': otype, 'color': color, 'rotation': rot})

    def _obs_color(self, otype):
        palettes = {
            'desk': (139,119,101), 'chair': (80,70,60), 'podium': (100,80,60),
            'blackboard': (30,60,40), 'bookshelf': (90,60,40), 'locker': (60,80,100),
            'wall': (145,130,115), 'fence': (150,135,110), 'barricade': (90,70,40),
            'building': (140,120,105), 'car': (170,80,80), 'house': (120,90,60),
            'tree': (30,70,30), 'reactor': (40,50,70), 'pipe': (70,75,85),
            'debris_pile': (55,50,45), 'pillar': (70,70,75), 'basketball_hoop': (200,80,80),
            'pingpong_table': (40,80,120), 'water_dispenser': (200,200,210),
            'trash_bin': (50,80,50), 'flower_bed': (60,100,50), 'school_bus': (220,180,30),
            'bus_stop': (50,70,90), 'streetlight': (70,70,75), 'mailbox': (40,60,120),
            'fire_hydrant': (180,40,40), 'bench': (90,70,50), 'shopping_cart': (80,80,85),
            'vending_machine': (150,40,40), 'dumpster': (60,80,50), 'bus': (180,160,40),
            'truck': (120,50,40), 'checkpoint': (100,80,40), 'sandbag': (130,110,70),
            'wrecked_tank': (50,55,45), 'burning_car': (80,30,20), 'billboard': (70,70,80),
            'shed': (100,70,45), 'bush': (40,80,35), 'well': (90,85,75),
            'haystack': (180,150,60), 'tractor': (40,70,40), 'water_tower': (100,100,110),
            'control_panel': (50,55,65), 'barrel': (150,120,30), 'crate': (110,85,50),
            'generator': (60,60,70), 'cooling_tower': (80,85,95),
            'radiation_barrier': (200,180,30), 'terminal': (30,35,45),
            'server_rack': (35,40,50), 'container': (50,60,50),
            'bus_stop': (50,70,90), 'school_bus': (220,180,30),
        }
        return palettes.get(otype, (60,55,50))

    def _add_wall_run(self, otype, x, y, length, th, horizontal=True, gap_frac=None):
        """沿方向铺一段墙, 中间留缺口"""
        if gap_frac is None:
            gap_frac = (0.45, 0.55)
        gs = int(length * gap_frac[0])
        ge = int(length * gap_frac[1])
        if horizontal:
            if gs > 0:
                self._add_obs(otype, x, y, gs, th)
            if length - ge > 0:
                self._add_obs(otype, x + ge, y, length - ge, th)
        else:
            if gs > 0:
                self._add_obs(otype, x, y, th, gs)
            if length - ge > 0:
                self._add_obs(otype, x, y + ge, th, length - ge)

    def _add_room(self, x, y, w, h, otype='wall', wall_h=16, gaps=None):
        """生成矩形房间四面墙(每边留门洞), 返回内部区域"""
        if gaps is None:
            gaps = {'top':(0.44,0.56),'bottom':(0.44,0.56),'left':(0.44,0.56),'right':(0.44,0.56)}
        self._add_wall_run(otype, x, y, w, wall_h, True, gaps['top'])
        self._add_wall_run(otype, x, y + h - wall_h, w, wall_h, True, gaps['bottom'])
        self._add_wall_run(otype, x, y, h, wall_h, False, gaps['left'])
        self._add_wall_run(otype, x + w - wall_h, y, h, wall_h, False, gaps['right'])
        return pygame.Rect(x + wall_h, y + wall_h, max(20, w - 2*wall_h), max(20, h - 2*wall_h))

    def _fill_classroom(self, inner):
        """教室内布局: 黑板+讲台+课桌成排+书架+储物柜"""
        # 黑板(上墙)
        self._add_obs('blackboard', inner.x + inner.w//4, inner.y - 2, inner.w//2, 18)
        # 讲台
        self._add_obs('podium', inner.centerx - 40, inner.y + 30, 80, 44)
        # 课桌成排(网格，隔格放置降低密度)
        desk_w, desk_h, gap = 100, 62, 46
        cols = max(1, (inner.w - 30) // (desk_w + gap))
        rows = max(1, (inner.h - 130) // (desk_h + gap + 30))
        sx = inner.x + 15
        sy = inner.y + 90
        for r_ in range(rows):
            for c_ in range(cols):
                if (r_ + c_) % 2 != 0:  # 隔格放置，仅保留一半课桌
                    continue
                dx = sx + c_ * (desk_w + gap)
                dy = sy + r_ * (desk_h + gap + 30)
                self._add_obs('desk', dx, dy, desk_w, desk_h)
                # 配椅子
                if c_ % 2 == 0:
                    self._add_obs('chair', dx - 26, dy + desk_h - 10, 34, 30)
        # 靠墙书架/储物柜
        self._add_obs('bookshelf', inner.x + 8, inner.y + inner.h - 44, 70, 34)
        self._add_obs('locker', inner.right - 60, inner.y + inner.h - 70, 52, 60)
        self._add_obs('trash_bin', inner.right - 16, inner.y + inner.h - 40, 26, 34)

    def _gen_school(self, x0, y0, x1, y1):
        """校园: 教室(课桌成排+黑板+讲台) + 走廊 + 拐角 + 墙体"""
        W, H = x1 - x0, y1 - y0
        cw = int(W * 0.36); ch = int(H * 0.40)
        # 三间教室
        rooms = [
            (x0 + 10, y0 + 12, cw, ch),                       # 左上教室
            (x0 + W - cw - 10, y0 + 12, cw, ch),              # 右上教室
            (x0 + 10, y0 + H - ch - 12, cw, ch),              # 左下教室
        ]
        for rx, ry, rw, rh in rooms:
            inner = self._add_room(rx, ry, rw, rh, 'wall', 18)
            self._fill_classroom(inner)
        # 中间纵向走廊(两段墙留出入口)
        corr_x = x0 + W//2 - 100
        self._add_wall_run('wall', corr_x, y0, H, 18, False, (0.30,0.42))
        self._add_wall_run('wall', corr_x + 200, y0, H, 18, False, (0.58,0.70))
        # 走廊内储物柜/垃圾桶
        for i in range(3):
            self._add_obs('locker', corr_x + 20 + i*60, y0 + 40, 48, 58)
            self._add_obs('locker', corr_x + 20 + i*60, y0 + H - 100, 48, 58)
        # 右下空地: 篮球架/乒乓球桌/饮水机/花坛
        gx = x0 + W - 300; gy = y0 + H - 220
        self._add_obs('basketball_hoop', gx + 40, gy, 60, 60)
        self._add_obs('pingpong_table', gx + 150, gy, 110, 60)
        self._add_obs('water_dispenser', gx + 40, gy + 110, 44, 56)
        self._add_obs('flower_bed', gx + 160, gy + 100, 90, 46)
        self._add_obs('trash_bin', gx + 60, gy + 170, 26, 32)

    def _gen_street(self, x0, y0, x1, y1):
        """街区: 纵向主路 + 两侧建筑/车辆/设施"""
        W, H = x1 - x0, y1 - y0
        road_cx = x0 + W//2
        road_w = 220
        # 路两侧建筑(排成排)
        for side in (0, 1):
            build_x = x0 + (10 if side == 0 else W - 190)
            y = y0 + 20
            while y < y1 - 150:
                bw = 170; bh = 120
                self._add_obs('building', build_x, y, bw, bh)
                # 门前设施
                self._add_obs('mailbox', build_x + 30, y + bh, 26, 36)
                self._add_obs('bench', build_x + 90, y + bh, 60, 24)
                y += bh + 90
        # 路边车辆与设施
        for i in range(4):
            y = y0 + 60 + i * (H//4)
            side = 0 if i % 2 == 0 else 1
            cx = road_cx + (120 if side == 0 else -120 - 90)
            self._add_obs('car', cx, y, 90, 46)
            self._add_obs('streetlight', road_cx + (150 if side==0 else -150-18), y, 16, 60)
            self._add_obs('fire_hydrant', road_cx + (70 if side==0 else -70-18), y + 40, 20, 26)
        # 路障/废墟点缀
        for i in range(3):
            self._add_obs('barricade', road_cx - 60 + i*70, y0 + 260 + i*80, 90, 30)
        self._add_obs('vending_machine', x0 + 230, y0 + 80, 44, 60)
        self._add_obs('dumpster', x1 - 240, y1 - 120, 70, 46)
        self._add_obs('school_bus', road_cx - 50, y1 - 100, 160, 60)

    def _gen_downtown(self, x0, y0, x1, y1):
        """市中心: 密集楼宇 + 废墟 + 燃烧车辆 + 检查站/路障 + 十字通道"""
        W, H = x1 - x0, y1 - y0
        # 高密度建筑群(网格布置, 留十字道路)
        bw, bh, gap = 190, 160, 90
        cols = max(1, W // (bw + gap))
        rows = max(1, H // (bh + gap))
        for r_ in range(rows):
            for c_ in range(cols):
                if (r_ + c_) % 2 != 0:  # 隔格放置，降低密度
                    continue
                bx = x0 + c_ * (bw + gap) + 15
                by = y0 + r_ * (bh + gap) + 15
                if random.random() < 0.7:
                    self._add_obs('building', bx, by, bw, bh)
                else:
                    self._add_obs('debris_pile', bx + 40, by + 40, 80, 60)
        # 街道废墟/燃烧车/检查站
        for i in range(3):
            self._add_obs('burning_car', x0 + 40 + i*140, y0 + 150, 80, 42)
            self._add_obs('debris_pile', x0 + 90 + i*180, y1 - 160, 70, 50)
        self._add_obs('checkpoint', x0 + W - 260, y0 + 90, 90, 40)
        self._add_obs('sandbag', x0 + W - 230, y0 + 150, 120, 30)
        self._add_obs('wrecked_tank', x0 + 60, y1 - 90, 100, 56)
        self._add_obs('truck', x1 - 200, y1 - 130, 130, 56)
        self._add_obs('bus', x0 + 220, y0 + 320, 130, 56)

    def _gen_suburb(self, x0, y0, x1, y1):
        """郊区: 分散独栋房屋 + 院子围栏 + 树/灌木 + 小路"""
        W, H = x1 - x0, y1 - y0
        hw, hh = 170, 120
        gap_x, gap_y = 180, 140
        cols = max(2, W // (hw + gap_x))
        rows = max(2, H // (hh + gap_y))
        for r_ in range(rows):
            for c_ in range(cols):
                if (r_ + c_) % 2 != 0:  # 隔格放置，降低密度
                    continue
                hx = x0 + c_ * (hw + gap_x) + 10
                hy = y0 + r_ * (hh + gap_y) + 10
                if random.random() < 0.6:
                    self._add_obs('house', hx, hy, hw, hh)
                    # 院子围栏
                    self._add_wall_run('fence', hx - 40, hy + hh + 10, hw + 80, 12, True, (0.2,0.8))
                    self._add_wall_run('fence', hx - 40, hy + hh + 10, 12, 90, False)
                    self._add_wall_run('fence', hx + hw + 28, hy + hh + 10, 12, 90, False)
                    # 院中树/灌木
                    self._add_obs('tree', hx + hw + 60, hy + 20, 50, 50)
                    self._add_obs('bush', hx + 40, hy + hh + 40, 40, 30)
                else:
                    self._add_obs('haystack', hx, hy + 20, 60, 44)
                    self._add_obs('tractor', hx + 90, hy + 30, 70, 50)
        # 池塘/水塔/水井
        self._add_obs('well', x0 + 60, y0 + 60, 40, 34)
        self._add_obs('water_tower', x1 - 130, y0 + 60, 60, 80)
        self._add_obs('shed', x0 + W - 220, y1 - 160, 80, 56)

    def _gen_nuclear(self, x0, y0, x1, y1):
        """核电站: 厂房 + 反应堆 + 冷却塔 + 管道 + 围栏 + 辐射屏障"""
        W, H = x1 - x0, y1 - y0
        # 主厂房
        main_inner = self._add_room(x0 + 80, y0 + 80, W - 160, H - 160, 'wall', 20)
        # 厂房内: 反应堆 + 控制台 + 服务器 + 发电机 + 管道
        self._add_obs('reactor', main_inner.x + main_inner.w//2 - 60, main_inner.y + 60, 120, 110)
        self._add_obs('control_panel', main_inner.x + 40, main_inner.y + 50, 80, 44)
        self._add_obs('server_rack', main_inner.right - 90, main_inner.y + 50, 50, 70)
        self._add_obs('generator', main_inner.x + main_inner.w//2 - 40, main_inner.bottom - 120, 80, 56)
        # 管道沿墙
        self._add_obs('pipe', main_inner.x + 30, main_inner.y + main_inner.h//2, main_inner.w - 60, 16)
        # 冷却塔(厂房外)
        self._add_obs('cooling_tower', x0 + 40, y1 - 150, 90, 110)
        self._add_obs('cooling_tower', x1 - 130, y1 - 150, 90, 110)
        # 油桶/板条箱点缀
        for i in range(4):
            self._add_obs('barrel', main_inner.x + 60 + i*70, main_inner.bottom - 60, 30, 36)
        self._add_obs('crate', main_inner.right - 70, main_inner.bottom - 60, 40, 40)
        # 辐射屏障(出入口)
        self._add_obs('radiation_barrier', x0 + W//2 - 90, y0 + 30, 180, 22)
        # 核电站围栏(四周)
        self._add_wall_run('fence', x0, y0 + H - 40, W, 12, True, (0.1,0.9))

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

        weights = [0.04, 0.18, 0.18, 0.12, 0.10, 0.07, 0.06, 0.04, 0.04, 0.03,
                   0.05, 0.04, 0.03, 0.02]
        types = [ItemType.VACCINE, ItemType.HEALTH_PACK, ItemType.AMMO_BOX, 
                ItemType.SPEED_BOOST, ItemType.DAMAGE_BOOST, ItemType.SHIELD_REPAIR,
                ItemType.WEAPON_BOX, ItemType.TREASURE_CHEST,
                ItemType.SKILL_SLOT, ItemType.BUFF_CHARM,
                ItemType.INCENDIARY, ItemType.SMOKE_GRENADE,
                ItemType.CLUSTER_BOMB, ItemType.EMP_GRENADE]
        item_type = random.choices(types, weights=weights)[0]

        self.items.append(SpecialItem(x, y, item_type))

    def update(self, dt, player_x, player_y):
        self.ensure_chunks_around(player_x, player_y)

        for item in self.items[:]:
            item.update(dt, player_x, player_y)
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

    def draw(self, screen, camera_x, camera_y, scale=1.0, assets=None):
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
                    color = self.tile_color_a if (x // 100 + y // 100) % 2 == 0 else self.tile_color_b
                    pygame.draw.rect(screen, color, (px, py, tile_size + 1, tile_size + 1))
                    # 地砖缝隙
                    pygame.draw.rect(screen, (color[0]-8, color[1]-8, color[2]-8), (px, py, tile_size + 1, tile_size + 1), max(1, int(scale)))

        for item in self.items:
            item.draw(screen, camera_x, camera_y, scale, assets)

        # 预分配一个SRCALPHA阴影surface供所有障碍物复用（性能优化）
        shadow_surf = pygame.Surface((8, 8), pygame.SRCALPHA)

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
                # 简化：固定两个窗口，去循环
                if draw_rect.width > 24:
                    pygame.draw.rect(screen, (40, 45, 50),
                                    pygame.Rect(draw_rect.x+draw_rect.width//4, draw_rect.y+4,
                                                max(4, draw_rect.width//3), max(3, draw_rect.height//3)))
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
                pygame.draw.line(screen, (color[0]+15, color[1]+15, color[2]+15),
                                (draw_rect.centerx, draw_rect.y), (draw_rect.centerx, draw_rect.bottom), max(1, int(scale)))
            elif obs_type == 'wall':
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.rect(screen, (color[0]-10, color[1]-10, color[2]-10), draw_rect, max(1, int(2*scale)))
            elif obs_type == 'barricade':
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.line(screen, (color[0]+30, color[1]+30, color[2]+30),
                                draw_rect.topleft, draw_rect.bottomright, max(2, int(3*scale)))
                pygame.draw.line(screen, (color[0]+30, color[1]+30, color[2]+30),
                                draw_rect.topright, draw_rect.bottomleft, max(2, int(3*scale)))
            elif obs_type == 'container':
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.rect(screen, (color[0]+10, color[1]+10, color[2]+10), draw_rect, max(1, int(scale)))
            elif obs_type == 'debris_pile':
                center = draw_rect.center
                radius = min(draw_rect.width, draw_rect.height) // 2
                pygame.draw.circle(screen, color, center, radius)
                pygame.draw.circle(screen, (color[0]+15, color[1]+15, color[2]+15),
                                 (center[0]+radius//3, center[1]-radius//3), max(2, radius//3))
            elif obs_type == 'pillar':
                pygame.draw.rect(screen, color, draw_rect, border_radius=max(2, int(4*scale)))
                pygame.draw.rect(screen, (color[0]+20, color[1]+20, color[2]+20), draw_rect, 
                                max(1, int(2*scale)), border_radius=max(2, int(4*scale)))
            # === 学校特色障碍物绘制 ===
            elif obs_type == 'desk':
                # 课桌：桌面（浅色）+ 桌腿（深色）+ 桌洞
                desk_top = pygame.Rect(draw_rect.x, draw_rect.y, draw_rect.width, max(4, draw_rect.height // 3))
                pygame.draw.rect(screen, (color[0]+25, color[1]+20, color[2]+15), desk_top)  # 桌面浅色
                pygame.draw.rect(screen, (color[0]-15, color[1]-15, color[2]-15), draw_rect, max(1, int(2*scale)))
                # 桌腿
                leg_w = max(2, int(3 * scale))
                pygame.draw.rect(screen, (color[0]-30, color[1]-30, color[2]-30),
                                 (draw_rect.x + 2, desk_top.bottom, leg_w, draw_rect.height - desk_top.height))
                pygame.draw.rect(screen, (color[0]-30, color[1]-30, color[2]-30),
                                 (draw_rect.right - leg_w - 2, desk_top.bottom, leg_w, draw_rect.height - desk_top.height))
                # 桌洞（储物空间）
                if draw_rect.width > 15:
                    hole_rect = pygame.Rect(draw_rect.x + 4, desk_top.bottom + 2, draw_rect.width - 8, max(3, draw_rect.height // 4))
                    pygame.draw.rect(screen, (color[0]-40, color[1]-40, color[2]-40), hole_rect)
                # 桌面上的书（固定一本，去循环）
                if draw_rect.width > 20:
                    pygame.draw.rect(screen, (150, 90, 90),
                                    (desk_top.x + 4, desk_top.y + 2, max(3, desk_top.width//3), max(2, desk_top.height - 4)))
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
                # 粉笔字迹（固定一条，去循环）
                if inner.width > 20 and inner.height > 8:
                    pygame.draw.line(screen, (200, 200, 200),
                                    (inner.x + 5, inner.y + inner.height//2),
                                    (inner.x + inner.width//2, inner.y + inner.height//2), max(1, int(scale)))
            elif obs_type == 'bookshelf':
                # 书架：简单隔板+几本书（去循环）
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.line(screen, (color[0]-20, color[1]-20, color[2]-20),
                                (draw_rect.x, draw_rect.centery),
                                (draw_rect.right, draw_rect.centery), max(1, int(2*scale)))
                if draw_rect.width > 15:
                    pygame.draw.rect(screen, (150, 80, 80),
                                    (draw_rect.x+3, draw_rect.y+3, max(3, draw_rect.width//4), max(2, draw_rect.height//3)))
                    pygame.draw.rect(screen, (60, 90, 150),
                                    (draw_rect.x+draw_rect.width//4+3, draw_rect.centery+3, max(3, draw_rect.width//4), max(2, draw_rect.height//3)))
            elif obs_type == 'locker':
                # 储物柜：简单柜门（去循环）
                pygame.draw.rect(screen, color, draw_rect)
                pygame.draw.rect(screen, (color[0]+15, color[1]+15, color[2]+15), draw_rect, max(1, int(2*scale)))
                pygame.draw.line(screen, (color[0]+15, color[1]+15, color[2]+15),
                                (draw_rect.centerx, draw_rect.y), (draw_rect.centerx, draw_rect.bottom), max(1, int(scale)))
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

            # 底部投影（用SRCALPHA surface正常alpha混合, 避免pygame.draw不支持alpha导致纯黑块）
            # 复用单一surface，避免每个障碍物重复创建
            shadow_rect = pygame.Rect(draw_rect.x + 3, draw_rect.bottom - max(2, int(3*scale)),
                                      max(1, draw_rect.width), max(3, int(5*scale)))
            shadow_surf.scroll(0, 0)
            shadow_surf.fill((0, 0, 0, 0))
            pygame.draw.rect(shadow_surf, (0, 0, 0, 70), shadow_surf.get_rect())
            screen.blit(shadow_surf, (shadow_rect.x, shadow_rect.y))


class HordeManager:
    # 尸潮规模等级
    SCALE_SMALL = 1    # 小型：普通僵尸，无Boss
    SCALE_MEDIUM = 2   # 中型：精英怪，有概率Boss
    SCALE_LARGE = 3    # 大型：必刷Boss，大量精英
    SCALE_MASSIVE = 4  # 巨型：多Boss，尸潮女王级

    def __init__(self, game_mode, difficulty):
        self.game_mode = game_mode
        self.difficulty = difficulty

        # 基础参数（开局）：尸潮间隔大幅延长、持续时间大幅延长
        self.base_horde_duration = 120.0
        self.min_horde_duration = 60.0
        self.base_horde_cooldown = 240.0
        self.min_horde_cooldown = 120.0

        self.base_boss_chance_horde = 0.08
        self.base_spawn_rate_horde = 0.35
        self.base_spawn_rate_normal = 1.8

        # 兼容中英文难度名称
        diff_map = {"easy":"简单", "normal":"普通", "hard":"困难", "hell":"地狱",
                    "Easy":"简单", "Normal":"普通", "Hard":"困难", "Hell":"地狱"}
        difficulty = diff_map.get(difficulty, difficulty)
        diff_mod = {
            "简单": {"dur_mod":1.2, "cd_mod":1.2, "boss":0.04, "spawn_h":0.5, "spawn_n":2.2},
            "普通": {"dur_mod":1.0, "cd_mod":1.0, "boss":0.08, "spawn_h":0.35, "spawn_n":1.8},
            "困难": {"dur_mod":0.85, "cd_mod":0.85, "boss":0.12, "spawn_h":0.28, "spawn_n":1.4},
            "地狱": {"dur_mod":0.70, "cd_mod":0.70, "boss":0.16, "spawn_h":0.20, "spawn_n":1.0},
        }.get(difficulty, {"dur_mod":1.0, "cd_mod":1.0, "boss":0.08, "spawn_h":0.35, "spawn_n":1.8})

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

        # === 尸潮规模系统 ===
        self.horde_count = 0           # 已发生的尸潮次数
        self.current_scale = self.SCALE_SMALL
        self.boss_guaranteed = False   # 本次尸潮是否保底Boss
        self.vaccine_boss_spawned = False  # 是否已刷出保底疫苗Boss

        # === 每个Boss全局只出现一次：boss_queue 依次消耗 ===
        # 第1个尸潮(初始)无Boss，第2~N+1个尸潮每轮刷一个Boss，共 len(boss)+1 个带Boss流程
        self.boss_queue = [
            EnemyType.BOSS_LONG, EnemyType.BOSS_XIANG, EnemyType.BOSS_MUTANT,
            EnemyType.BOSS_QUEEN, EnemyType.BOSS_TITAN, EnemyType.BOSS_WANG,
        ]
        random.shuffle(self.boss_queue)

        # 故事/限时模式：确保至少刷一个Boss且其中一个爆疫苗
        self.story_boss_guaranteed = game_mode in (GameMode.STORY, GameMode.TIMED)
        self.story_min_horde_for_boss = 2  # 第2波起保底Boss

        self.endless_glitch_shown = False
        self.glitch_trigger_time = 1200.0
        self.endless_countdown_total = 90
        self.endless_countdown_left = 90

    def update(self, dt):
        self.total_time += dt
        if self.game_mode == GameMode.ENDLESS:
            if not self.endless_glitch_shown:
                self.endless_countdown_left -= dt
                if self.endless_countdown_left <= 0:
                    self.endless_glitch_shown = True
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
                self.horde_count += 1
                new_dur = self._get_current_horde_duration()
                self.timer = new_dur
                self.boss_spawned_this_horde = False
                # 计算本次尸潮规模
                self._calculate_horde_scale()
        self.spawn_timer -= dt

    def _calculate_horde_scale(self):
        """根据波次和时间计算尸潮规模"""
        wave = self.horde_count
        time_min = self.total_time / 60.0

        # 基础规模随波次提升
        if wave <= 1:
            base_scale = self.SCALE_SMALL
        elif wave <= 3:
            base_scale = self.SCALE_SMALL if random.random() < 0.5 else self.SCALE_MEDIUM
        elif wave <= 6:
            base_scale = self.SCALE_MEDIUM
        elif wave <= 10:
            base_scale = self.SCALE_MEDIUM if random.random() < 0.4 else self.SCALE_LARGE
        else:
            base_scale = self.SCALE_LARGE if random.random() < 0.6 else self.SCALE_MASSIVE

        # 时间加成
        if time_min > 10:
            base_scale = max(base_scale, self.SCALE_MEDIUM)
        if time_min > 20:
            base_scale = max(base_scale, self.SCALE_LARGE)

        self.current_scale = base_scale

        # 保底Boss判定
        self.boss_guaranteed = False
        if self.current_scale >= self.SCALE_LARGE:
            self.boss_guaranteed = True
        elif self.current_scale == self.SCALE_MEDIUM and wave >= 3:
            self.boss_guaranteed = random.random() < 0.4

        # 故事/限时模式强制保底
        if self.story_boss_guaranteed and wave >= self.story_min_horde_for_boss:
            self.boss_guaranteed = True
            # 确保至少有一个Boss爆疫苗
            if not self.vaccine_boss_spawned:
                self.boss_guaranteed = True

    def get_current_scale_name(self):
        names = {1: "小型尸潮", 2: "中型尸潮", 3: "大型尸潮", 4: "巨型尸潮"}
        return names.get(self.current_scale, "未知")

    def get_scale_color(self):
        colors = {1: (180, 180, 180), 2: (220, 180, 60), 3: (220, 80, 40), 4: (180, 30, 180)}
        return colors.get(self.current_scale, (255, 255, 255))

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
        time_factor = min(2.2, 1.0 + self.total_time / 180.0)

        # 规模影响刷新速率
        scale_mult = {1: 1.2, 2: 0.9, 3: 0.65, 4: 0.45}
        scale_spawn_mult = scale_mult.get(self.current_scale, 1.0)

        spawn_rate_horde = self.base_spawn_rate_horde / time_factor * scale_spawn_mult
        spawn_rate_normal = self.base_spawn_rate_normal / time_factor
        boss_chance_horde = self.base_boss_chance_horde * time_factor

        if self.horde_active:
            spawn_rate = spawn_rate_horde
        else:
            spawn_rate = spawn_rate_normal

        if self.spawn_timer > 0:
            return None
        self.spawn_timer = spawn_rate

        # === Boss刷新逻辑：每个Boss全局只出现一次 ===
        # 第1个尸潮(初始)无Boss；第2个及之后，每轮必刷 boss_queue 中下一个Boss，
        # 直到全部Boss出完(共 len(boss)+1 个流程)，队列耗尽后不再刷Boss。
        if self.horde_active and not self.boss_spawned_this_horde:
            if self.horde_count >= 2 and self.boss_queue:
                self.boss_spawned_this_horde = True
                btype = self._select_boss_type()
                if btype is not None:
                    return btype

        # === 普通怪物池（按规模）===
        base_pool = [
            EnemyType.ZOMBIE_NORMAL,
            EnemyType.ZOMBIE_FAST,
            EnemyType.ZOMBIE_TANK,
            EnemyType.ZOMBIE_GHOUL,
            EnemyType.ZOMBIE_BERSERKER,
        ]
        mid_pool = [
            EnemyType.ZOMBIE_RANGED,
            EnemyType.ZOMBIE_CRAWLER,
            EnemyType.ZOMBIE_SPITTER,
            EnemyType.ZOMBIE_LEAPER,
            EnemyType.ZOMBIE_FROST,
            EnemyType.ZOMBIE_VENOM,
            EnemyType.ZOMBIE_HUNTER,
        ]
        elite_pool = [
            EnemyType.ELITE_BRUTE,
            EnemyType.ELITE_ASSASSIN,
            EnemyType.ELITE_SORCERER,
            EnemyType.ELITE_GUARDIAN,
        ]
        advanced_pool = [
            EnemyType.ZOMBIE_EXPLODER,
            EnemyType.ZOMBIE_SPLITTER,
            EnemyType.ZOMBIE_SHIELD,
            EnemyType.ZOMBIE_HEALER,
            EnemyType.ZOMBIE_PHANTOM,
            EnemyType.ZOMBIE_WRAITH,
            EnemyType.ZOMBIE_BOMBER,
            EnemyType.ZOMBIE_SHAMAN,
            EnemyType.ZOMBIE_JUGGERNAUT,
        ]

        # 精英怪：中型以上加入（先判精英，权重随时间提升）
        if self.current_scale >= 2:
            elite_weight = 0.15 if self.current_scale == 2 else 0.25
            if random.random() < elite_weight:
                return random.choice(elite_pool)

        # === 严格按时间/章节解锁（前期只普通+快速，避免前期僵尸类型过多）===
        # 时间阈值（秒）；current_scale>=2 时提前解锁一档，加速节奏
        t = self.total_time
        boost = (self.current_scale >= 2)
        unlock_pool = [EnemyType.ZOMBIE_NORMAL]
        if t >= 30.0 or boost:
            unlock_pool.append(EnemyType.ZOMBIE_FAST)
        # 前期尽量只有普通僵尸和快速僵尸；更高级类型显著推迟
        if t >= 120.0 or boost:
            unlock_pool.extend([EnemyType.ZOMBIE_TANK, EnemyType.ZOMBIE_GHOUL])
        if t >= 180.0 or boost:
            unlock_pool.append(EnemyType.ZOMBIE_BERSERKER)
            unlock_pool.extend(mid_pool)
        if t >= 300.0 or self.current_scale >= 3:
            unlock_pool.extend(advanced_pool)

        if self.horde_active:
            return random.choice(unlock_pool)
        else:
            # 非尸潮时间：同样按时间/章节解锁（不设精英概率）
            return random.choice(unlock_pool)

    def _select_boss_type(self):
        """从全局 boss_queue 依次取一个Boss（每个Boss全局只出现一次），标记疫苗Boss"""
        if not self.boss_queue:
            return None
        boss_type = self.boss_queue.pop(0)

        # 标记疫苗Boss：故事/限时模式第一个Boss必爆疫苗
        if self.story_boss_guaranteed and not self.vaccine_boss_spawned:
            self.vaccine_boss_spawned = True
            return (boss_type, True)
        return boss_type

    def is_timed_over(self):
        if self.game_mode == GameMode.TIMED:
            return self.total_time >= 1200.0
        return False