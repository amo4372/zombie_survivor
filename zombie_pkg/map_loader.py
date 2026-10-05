# -*- coding: utf-8 -*-
"""游戏端 .zmap 大地图加载 —— 把二进制地图接入游戏世界

- 障碍 tile（障碍/树/车/栅栏/建筑）→ 行合并矩形 → world._add_obs
- 掩体 tile → crate 障碍（视觉掩体）
- 水坑/尖刺 → world.zones 效果区（减速/伤害，作用于玩家）
- 出生点/巡逻点 → world.spawn_points
- 装饰 tile → 跳过（纯视觉）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from rl.map_format import (load_map, TILE_SIZE,
                               TILE_BLOCK, TILE_COVER, TILE_WATER, TILE_SPIKE,
                               TILE_TREE, TILE_VEHICLE, TILE_BUILDING, TILE_FENCE,
                               TILE_DECOR, BLOCK_TILES, OBJ_PLAYER_SPAWN,
                               OBJ_ZOMBIE_SPAWN, OBJ_PATROL, OBJ_EXIT, OBJ_SUPPLY)
except ImportError:
    from map_format import (load_map, TILE_SIZE,
                            TILE_BLOCK, TILE_COVER, TILE_WATER, TILE_SPIKE,
                            TILE_TREE, TILE_VEHICLE, TILE_BUILDING, TILE_FENCE,
                            TILE_DECOR, BLOCK_TILES, OBJ_PLAYER_SPAWN,
                            OBJ_ZOMBIE_SPAWN, OBJ_PATROL, OBJ_EXIT, OBJ_SUPPLY)

# tile → 游戏障碍类型
_TILE_TO_OBSTYPE = {
    TILE_BLOCK: "wall",
    TILE_TREE: "tree",
    TILE_VEHICLE: "barricade",
    TILE_BUILDING: "wall",
    TILE_FENCE: "fence",
    TILE_COVER: "crate",
}
_ZONE_TILES = {TILE_WATER: "water", TILE_SPIKE: "spike"}


def _merge_runs(tiles, w, h, wanted):
    """行内连续同类型格 → [(gx, gy, run_len)]"""
    runs = []
    for gy in range(h):
        gx = 0
        while gx < w:
            if tiles[gy * w + gx] == wanted:
                gx0 = gx
                while gx < w and tiles[gy * w + gx] == wanted:
                    gx += 1
                runs.append((gx0, gy, gx - gx0))
            else:
                gx += 1
    return runs


def apply_zmap(world, map_path):
    """把 .zmap 应用到游戏世界（world.obstacles / world.zones / world.spawn_points）"""
    m = load_map(map_path)
    w, h = m["width"], m["height"]
    added = 0
    for tile, otype in _TILE_TO_OBSTYPE.items():
        for gx, gy, run in _merge_runs(m["tiles"], w, h, tile):
            x, y = gx * TILE_SIZE, gy * TILE_SIZE
            world._add_obs(otype, x, y, run * TILE_SIZE, TILE_SIZE)
            added += 1
    # 效果区
    zones = []
    for tile, ztype in _ZONE_TILES.items():
        for gx, gy, run in _merge_runs(m["tiles"], w, h, tile):
            zones.append({"rect": __import__("pygame").Rect(
                gx * TILE_SIZE, gy * TILE_SIZE, run * TILE_SIZE, TILE_SIZE),
                "type": ztype, "timer": 0.0})
    if not hasattr(world, "zones"):
        world.zones = []
    world.zones.extend(zones)
    # 出生点/巡逻点
    if not hasattr(world, "spawn_points"):
        world.spawn_points = {"player": [], "zombie": [], "patrol": [],
                              "exit": [], "supply": []}
    for o in m["objects"]:
        key = {OBJ_PLAYER_SPAWN: "player", OBJ_ZOMBIE_SPAWN: "zombie",
               OBJ_PATROL: "patrol", OBJ_EXIT: "exit", OBJ_SUPPLY: "supply"}.get(o["type"])
        if key:
            world.spawn_points[key].append((o["x"], o["y"], o.get("r", 12)))
    return {"obstacles": added, "zones": len(zones),
            "spawns": {k: len(v) for k, v in world.spawn_points.items()}}


def apply_player_zones(world, player, dt, enemies=None):
    """玩家与效果区交互：水坑减速（返回速度系数）/ 尖刺持续伤害"""
    if not getattr(world, "zones", None):
        return 1.0
    speed_mult = 1.0
    for z in world.zones:
        if z["rect"].collidepoint(player.x, player.y):
            if z["type"] == "water":
                speed_mult = 0.5
            elif z["type"] == "spike":
                z["timer"] += dt
                if z["timer"] >= 0.6:
                    z["timer"] = 0.0
                    player.hp = max(0, player.hp - 4)
                    if hasattr(player, "damage_flash_timer"):
                        player.damage_flash_timer = 0.15
    return speed_mult
