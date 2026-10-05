# -*- coding: utf-8 -*-
"""二进制大地图格式（.zmap）—— 障碍物/巡逻点/出生点等游戏对象

格式（小端序，struct 打包，无第三方依赖）：
    Header  : magic b"ZMAP" (4B) | version u8 | width u16 | height u16
    Tiles   : width*height 字节，0=空地 1=障碍物(墙/箱) 2=掩体(可遮挡但可穿过)
    Objects : count u16，其后 count 个 16B 记录
              { type u8 | x f32 | y f32 | radius f32 | extra u8 | pad u8 }
              type: 0=玩家出生点 1=僵尸出生点 2=巡逻点 3=出口 4=补给点
    Trailer : magic b"ZEND" (4B) | crc32 u32 (仅 tiles+objects 区)

地图尺寸以"格"为单位（默认 40x30 格，每格 32px → 1280x960 世界）。
"""
import struct
import zlib
import os

MAGIC = b"ZMAP"
END_MAGIC = b"ZEND"
VERSION = 1
TILE_SIZE = 32

# 对象类型
OBJ_PLAYER_SPAWN = 0
OBJ_ZOMBIE_SPAWN = 1
OBJ_PATROL = 2
OBJ_EXIT = 3
OBJ_SUPPLY = 4
OBJ_NAMES = {0: "玩家出生点", 1: "僵尸出生点", 2: "巡逻点", 3: "出口", 4: "补给点"}

TILE_EMPTY = 0
TILE_BLOCK = 1        # 障碍（墙/箱/废墟）
TILE_COVER = 2        # 掩体（可通过、遮挡弹道）
TILE_WATER = 3        # 水坑（减速 50%）
TILE_SPIKE = 4        # 尖刺（持续伤害）
TILE_TREE = 5         # 树木（不可通过+遮挡）
TILE_VEHICLE = 6      # 车辆（不可通过+掩体）
TILE_BUILDING = 7     # 建筑（不可通过+遮挡）
TILE_FENCE = 8        # 栅栏（不可通过）
TILE_DECOR = 9        # 装饰（纯视觉，可通过）

# 阻挡移动的 tile 集合
BLOCK_TILES = (TILE_BLOCK, TILE_TREE, TILE_VEHICLE, TILE_BUILDING, TILE_FENCE)
# 遮挡弹道的 tile 集合（掩体+树+车+建筑）
OCCLUDE_TILES = (TILE_COVER, TILE_TREE, TILE_VEHICLE, TILE_BUILDING)

TILE_NAMES = {
    TILE_EMPTY: "空地", TILE_BLOCK: "障碍", TILE_COVER: "掩体", TILE_WATER: "水坑",
    TILE_SPIKE: "尖刺", TILE_TREE: "树木", TILE_VEHICLE: "车辆", TILE_BUILDING: "建筑",
    TILE_FENCE: "栅栏", TILE_DECOR: "装饰",
}


def make_map(w=40, h=30, default_tile=TILE_EMPTY):
    return {"width": w, "height": h, "tiles": bytearray([default_tile] * (w * h)),
            "objects": [], "name": "untitled"}


def save_map(m, path):
    """m: dict(width,height,tiles,objects,name) → .zmap 文件"""
    w, h = m["width"], m["height"]
    assert len(m["tiles"]) == w * h, "tiles 长度与尺寸不符"
    buf = bytearray()
    buf += MAGIC
    buf += struct.pack("<BHH", VERSION, w, h)
    buf += bytes(m["tiles"])
    objs = m.get("objects", [])
    buf += struct.pack("<H", len(objs))
    for o in objs:
        buf += struct.pack("<BfffBB", int(o["type"]), float(o["x"]),
                           float(o["y"]), float(o.get("r", 12.0)),
                           int(o.get("extra", 0)), 0)
    body = bytes(buf)
    buf += END_MAGIC
    buf += struct.pack("<I", zlib.crc32(body))
    with open(path, "wb") as f:
        f.write(buf)
    return len(buf)


def load_map(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != MAGIC:
        raise ValueError("不是有效的 .zmap 文件")
    ver, w, h = struct.unpack_from("<BHH", data, 4)
    if ver != VERSION:
        raise ValueError(f"版本不支持: {ver}")
    off = 9
    tiles = bytearray(data[off:off + w * h])
    off += w * h
    n = struct.unpack_from("<H", data, off)[0]
    off += 2
    objs = []
    for _ in range(n):
        t, x, y, r, extra, _p = struct.unpack_from("<BfffBB", data, off)
        objs.append({"type": t, "x": x, "y": y, "r": r, "extra": extra})
        off += 15
    if data[off:off + 4] != END_MAGIC:
        raise ValueError("文件尾损坏")
    crc = struct.unpack_from("<I", data, off + 4)[0]
    if crc != zlib.crc32(data[:off]):
        raise ValueError("CRC 校验失败（文件损坏）")
    return {"width": w, "height": h, "tiles": tiles, "objects": objs,
            "name": os.path.basename(path)}


def tile_at(m, x, y):
    """像素坐标 → 格值（越界视为障碍物）"""
    gx, gy = int(x // TILE_SIZE), int(y // TILE_SIZE)
    if gx < 0 or gy < 0 or gx >= m["width"] or gy >= m["height"]:
        return TILE_BLOCK
    return m["tiles"][gy * m["width"] + gx]


def is_blocked(m, x, y, radius=0.0):
    """圆是否与阻挡类障碍碰撞（掩体/水坑/尖刺/装饰不阻挡移动）"""
    if tile_at(m, x, y) in BLOCK_TILES:
        return True
    if radius <= 0:
        return False
    for dx in (-radius, 0, radius):
        for dy in (-radius, 0, radius):
            if tile_at(m, x + dx, y + dy) in BLOCK_TILES:
                return True
    return False


def speed_factor(m, x, y):
    """所在格移动速度系数（水坑 0.5，其余 1.0）"""
    return 0.5 if tile_at(m, x, y) == TILE_WATER else 1.0


def hazard_dps(m, x, y):
    """所在格每秒伤害（尖刺 8/s）"""
    return 8.0 if tile_at(m, x, y) == TILE_SPIKE else 0.0


def raycast_free(m, x0, y0, ang, max_dist, step=8.0):
    """沿方向采样，返回首个障碍物距离（归一化 0~1）与是否碰撞；-1 表示通畅"""
    d = 0.0
    while d < max_dist:
        d += step
        if tile_at(m, x0 + math_cos(ang) * d, y0 + math_sin(ang) * d) == TILE_BLOCK:
            return min(d / max_dist, 1.0), True
    return 1.0, False


# 独立的小数学（避免依赖 numpy 的轻量实现）
import math as _m
math_cos = _m.cos
math_sin = _m.sin


def demo_map(path="rl/maps/demo.zmap"):
    """生成示例地图：田字障碍 + 出生点 + 巡逻点"""
    m = make_map(40, 30)
    # 田字障碍（中央十字墙 + 四角掩体）
    cx, cy = 20, 15
    for i in range(12):
        m["tiles"][cy * m["width"] + cx - 6 + i] = TILE_BLOCK  # 横墙
    for j in range(9):
        m["tiles"][(cy - 4 + j) * m["width"] + cx] = TILE_BLOCK  # 竖墙
    for (ox, oy) in [(6, 5), (33, 5), (6, 24), (33, 24)]:
        for a in range(3):
            for b in range(3):
                m["tiles"][(oy + a) * m["width"] + ox + b] = TILE_COVER
    # 丰富元素：树木带 / 车辆 / 水坑 / 尖刺 / 栅栏 / 建筑 / 装饰
    for t in range(10):
        m["tiles"][(6 + t) * m["width"] + 4] = TILE_TREE
        m["tiles"][(6 + t) * m["width"] + 3] = TILE_TREE
    for t in range(6):
        m["tiles"][(9 + t) * m["width"] + 30] = TILE_VEHICLE
    for t in range(4):
        m["tiles"][(14 + t) * m["width"] + 33] = TILE_WATER
        m["tiles"][(14 + t) * m["width"] + 34] = TILE_WATER
    for t in range(5):
        m["tiles"][(22 + t) * m["width"] + 6] = TILE_SPIKE
    for t in range(8):
        m["tiles"][20 * m["width"] + 10 + t] = TILE_FENCE
    m["tiles"][2 * m["width"] + 35] = TILE_BUILDING
    m["tiles"][2 * m["width"] + 36] = TILE_BUILDING
    m["tiles"][3 * m["width"] + 35] = TILE_BUILDING
    m["tiles"][3 * m["width"] + 36] = TILE_BUILDING
    for t in range(3):
        m["tiles"][(26 + t) * m["width"] + 28] = TILE_DECOR
    for t in range(3):
        m["tiles"][(26 + t) * m["width"] + 29] = TILE_DECOR
    m["objects"] = [
        {"type": OBJ_PLAYER_SPAWN, "x": 640, "y": 768, "r": 12.0},
        {"type": OBJ_ZOMBIE_SPAWN, "x": 128, "y": 96, "r": 12.0},
        {"type": OBJ_ZOMBIE_SPAWN, "x": 1152, "y": 96, "r": 12.0},
        {"type": OBJ_PATROL, "x": 640, "y": 480, "r": 12.0},
        {"type": OBJ_PATROL, "x": 320, "y": 240, "r": 12.0},
        {"type": OBJ_PATROL, "x": 960, "y": 240, "r": 12.0},
        {"type": OBJ_EXIT, "x": 1216, "y": 864, "r": 12.0},
        {"type": OBJ_SUPPLY, "x": 640, "y": 300, "r": 12.0},
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_map(m, path)
    return m


if __name__ == "__main__":
    p = "rl/maps/demo.zmap"
    m = demo_map(p)
    m2 = load_map(p)
    assert m2["tiles"] == m["tiles"]
    for a, b in zip(m["objects"], m2["objects"]):
        assert a["type"] == b["type"] and abs(a["x"] - b["x"]) < 1e-6 \
            and abs(a["y"] - b["y"]) < 1e-6 \
            and abs(a.get("r", 0) - b.get("r", 0)) < 1e-6
    print(f"[MAP] 示例地图 {p} 写/读一致: {m2['width']}x{m2['height']}, "
          f"对象 {len(m2['objects'])} 个")
    print(f"[MAP] 对象: {[OBJ_NAMES[o['type']] for o in m2['objects']]}")
