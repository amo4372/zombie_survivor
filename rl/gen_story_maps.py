# -*- coding: utf-8 -*-
"""按游戏剧情生成 5 张 RL 训练地图（.zmap 二进制格式）

章节对应：校园(第一章) / 街区(第二章) / 市中心(第三章) / 郊区(第四章) / 核电站(第五章)
肉鸽布局原则：左上出生安全区 → 中部区域化探索区 → 右下出口推进；
             多个补给点(资源)、僵尸出生点、巡逻点；固定障碍叠加在游戏随机障碍之上。

用法：python3 rl/gen_story_maps.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from map_editor import MapEditor
from map_format import (
    TILE_SIZE, TILE_FENCE, TILE_COVER, TILE_SPIKE, TILE_DECOR, TILE_TREE,
    TILE_VEHICLE, TILE_BUILDING, TILE_BLOCK, TILE_WATER,
    OBJ_PLAYER_SPAWN, OBJ_ZOMBIE_SPAWN, OBJ_PATROL, OBJ_EXIT, OBJ_SUPPLY,
)

MAPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps")


def tile(e, gx, gy, t, count=1):
    for i in range(count):
        e.map["tiles"][gy * e.map["width"] + gx + i] = t


def rect(e, gx0, gy0, w, h, t):
    for gy in range(gy0, gy0 + h):
        for gx in range(gx0, gx0 + w):
            tile(e, gx, gy, t)


def obj(e, otype, gx, gy):
    e.map["objects"].append({
        "type": otype,
        "x": gx * TILE_SIZE + TILE_SIZE // 2,
        "y": gy * TILE_SIZE + TILE_SIZE // 2,
        "r": 14,
    })


def base_objects(e):
    """肉鸽公共对象：出生/僵尸/巡逻/出口/补给"""
    obj(e, OBJ_PLAYER_SPAWN, 2, 2)
    obj(e, OBJ_ZOMBIE_SPAWN, 35, 3)
    obj(e, OBJ_ZOMBIE_SPAWN, 36, 25)
    obj(e, OBJ_PATROL, 10, 2)
    obj(e, OBJ_PATROL, 30, 15)
    obj(e, OBJ_PATROL, 15, 27)
    obj(e, OBJ_EXIT, 38, 28)
    obj(e, OBJ_SUPPLY, 8, 12)
    obj(e, OBJ_SUPPLY, 30, 18)
    obj(e, OBJ_SUPPLY, 20, 24)


def _save(e, name):
    e.save()
    print(f"生成 {name}.zmap OK")


# ============ 第一章 校园（SCHOOL） ============
def gen_school():
    e = MapEditor(path=os.path.join(MAPS_DIR, "school.zmap"), dummy=True)
    e.clear()
    base_objects(e)
    # 校园围墙（四周栅栏，留门洞）
    for gy in range(2, 28):
        tile(e, 1, gy, TILE_FENCE)
        tile(e, 38, gy, TILE_FENCE)
    for gx in range(2, 38):
        if gx in (12, 13, 14, 15) or gx in (30, 31, 32, 33):
            continue
        tile(e, gx, 1, TILE_FENCE)
        tile(e, gx, 28, TILE_FENCE)
    # 教学楼区（左上）
    rect(e, 5, 4, 7, 4, TILE_BUILDING)
    rect(e, 5, 9, 7, 2, TILE_BUILDING)
    # 食堂（右上）
    rect(e, 28, 4, 6, 4, TILE_BUILDING)
    # 操场（中央开阔 + 看台掩体 + 单杠障碍）
    rect(e, 15, 13, 3, 1, TILE_COVER)   # 看台
    rect(e, 15, 15, 1, 3, TILE_COVER)
    rect(e, 24, 13, 3, 1, TILE_COVER)
    tile(e, 20, 16, TILE_BLOCK); tile(e, 21, 16, TILE_BLOCK)  # 障碍桩
    # 校车（车辆）
    rect(e, 17, 20, 1, 3, TILE_VEHICLE)
    rect(e, 25, 21, 1, 2, TILE_VEHICLE)
    # 花坛装饰
    for gx, gy in ((8, 12), (12, 11), (10, 16), (27, 12), (32, 11)):
        tile(e, gx, gy, TILE_DECOR)
    # 花坛掩体（点缀）
    tile(e, 9, 13, TILE_COVER, 2); tile(e, 30, 13, TILE_COVER, 2)
    # 树
    tile(e, 34, 18, TILE_TREE, 2); tile(e, 34, 19, TILE_TREE, 2)
    tile(e, 4, 22, TILE_TREE, 2); tile(e, 4, 23, TILE_TREE, 2)
    _save(e, "school")


# ============ 第二章 街区（STREET） ============
def gen_street():
    e = MapEditor(path=os.path.join(MAPS_DIR, "street.zmap"), dummy=True)
    e.clear()
    base_objects(e)
    # 沿街商店建筑
    rect(e, 22, 4, 5, 3, TILE_BUILDING)
    rect(e, 6, 4, 4, 2, TILE_BUILDING)
    rect(e, 6, 20, 4, 3, TILE_BUILDING)
    rect(e, 28, 18, 4, 2, TILE_BUILDING)
    # 连续栅栏（分隔街道与建筑区，留口）
    for gy in (3, 13, 23):
        for gx in range(12, 24):
            if gx in (17, 18):
                continue
            tile(e, gx, gy, TILE_FENCE)
    # 街道车辆（沿街停放）
    for gy in (8, 9, 10, 11):
        tile(e, 33, gy, TILE_VEHICLE)
    for gy in (8, 9):
        tile(e, 3, gy, TILE_VEHICLE, 2)
    for gy in (15, 16):
        tile(e, 28, gy, TILE_VEHICLE, 3)
    # 街角树 + 人行道掩体
    tile(e, 11, 18, TILE_TREE, 2); tile(e, 11, 19, TILE_TREE, 2)
    tile(e, 25, 26, TILE_TREE, 2); tile(e, 25, 27, TILE_TREE, 2)
    for gy in (15, 16, 17):
        tile(e, 15, gy, TILE_COVER, 2)
    # 路障尖刺（战斗区）
    tile(e, 19, 18, TILE_SPIKE, 2); tile(e, 19, 19, TILE_SPIKE, 2)
    _save(e, "street")


# ============ 第三章 市中心（DOWNTOWN） ============
def gen_downtown():
    e = MapEditor(path=os.path.join(MAPS_DIR, "downtown.zmap"), dummy=True)
    e.clear()
    base_objects(e)
    # 高楼群（左上 + 右上 + 左下）
    rect(e, 3, 3, 7, 6, TILE_BUILDING)
    rect(e, 27, 3, 7, 5, TILE_BUILDING)
    rect(e, 4, 21, 6, 5, TILE_BUILDING)
    rect(e, 30, 20, 6, 5, TILE_BUILDING)
    # 中央广场（开阔 + 花坛掩体 + 雕塑障碍）
    tile(e, 15, 13, TILE_COVER, 3); tile(e, 15, 16, TILE_COVER, 3)
    tile(e, 20, 13, TILE_COVER, 3); tile(e, 20, 16, TILE_COVER, 3)
    tile(e, 18, 15, TILE_BLOCK, 2)   # 广场雕塑
    # 街道车辆（消防车/出租车）
    rect(e, 13, 8, 1, 3, TILE_VEHICLE)
    rect(e, 24, 9, 1, 3, TILE_VEHICLE)
    rect(e, 12, 22, 2, 1, TILE_VEHICLE)
    # 地铁出入口（掩体）+ 装饰
    tile(e, 11, 15, TILE_COVER, 2); tile(e, 11, 17, TILE_COVER, 2)
    tile(e, 26, 14, TILE_DECOR, 2); tile(e, 26, 16, TILE_DECOR, 2)
    tile(e, 7, 14, TILE_DECOR); tile(e, 32, 13, TILE_DECOR)
    # 破损围栏（尖刺战斗带）
    tile(e, 16, 20, TILE_SPIKE, 4); tile(e, 16, 21, TILE_SPIKE, 4)
    # 行道树
    tile(e, 14, 11, TILE_TREE); tile(e, 22, 11, TILE_TREE)
    tile(e, 14, 18, TILE_TREE); tile(e, 22, 18, TILE_TREE)
    _save(e, "downtown")


# ============ 第四章 郊区（SUBURB） ============
def gen_suburb():
    e = MapEditor(path=os.path.join(MAPS_DIR, "suburb.zmap"), dummy=True)
    e.clear()
    base_objects(e)
    # 分散别墅（4 处建筑）
    rect(e, 5, 5, 4, 3, TILE_BUILDING)
    rect(e, 28, 4, 4, 3, TILE_BUILDING)
    rect(e, 6, 18, 4, 3, TILE_BUILDING)
    rect(e, 25, 22, 4, 3, TILE_BUILDING)
    # 花园栅栏（别墅周围小段）
    for gy in (3, 4):
        tile(e, 4, gy, TILE_FENCE, 2); tile(e, 9, gy, TILE_FENCE, 2)
    for gy in (2, 3):
        tile(e, 27, gy, TILE_FENCE, 2); tile(e, 32, gy, TILE_FENCE, 2)
    for gy in (17, 18):
        tile(e, 5, gy, TILE_FENCE, 2); tile(e, 10, gy, TILE_FENCE, 2)
    for gy in (21, 22):
        tile(e, 24, gy, TILE_FENCE, 2); tile(e, 29, gy, TILE_FENCE, 2)
    # 树林（三片）
    rect(e, 13, 6, 4, 3, TILE_TREE)
    rect(e, 30, 13, 3, 3, TILE_TREE)
    rect(e, 12, 22, 3, 3, TILE_TREE)
    # 池塘（水坑）
    rect(e, 18, 8, 4, 3, TILE_WATER)
    rect(e, 22, 17, 3, 2, TILE_WATER)
    # 铁丝网（尖刺）
    tile(e, 17, 15, TILE_SPIKE, 3); tile(e, 17, 16, TILE_SPIKE, 3)
    tile(e, 27, 10, TILE_SPIKE, 2)
    # 道路掩体（护栏）
    tile(e, 14, 14, TILE_COVER, 3); tile(e, 21, 14, TILE_COVER, 3)
    _save(e, "suburb")


# ============ 第五章 核电站（NUCLEAR_PLANT） ============
def gen_nuclear():
    e = MapEditor(path=os.path.join(MAPS_DIR, "nuclear.zmap"), dummy=True)
    e.clear()
    base_objects(e)
    # 反应堆核心（中央大建筑 + 放射尖刺环）
    rect(e, 17, 12, 7, 7, TILE_BUILDING)
    for gy in (10, 11, 20, 21):
        tile(e, 16, gy, TILE_SPIKE, 4)
        tile(e, 21, gy, TILE_SPIKE, 4)
    for gx in (14, 15, 24, 25):
        tile(e, gx, 11, TILE_SPIKE, 2)
        tile(e, gx, 20, TILE_SPIKE, 2)
    # 冷却塔（右上）+ 控制室（左上）
    rect(e, 29, 4, 6, 5, TILE_BUILDING)
    rect(e, 4, 4, 6, 4, TILE_BUILDING)
    # 废料障碍块
    rect(e, 5, 15, 3, 2, TILE_BLOCK)
    rect(e, 30, 16, 3, 2, TILE_BLOCK)
    rect(e, 12, 23, 2, 3, TILE_BLOCK)
    # 管道掩体
    rect(e, 13, 5, 2, 2, TILE_COVER)
    rect(e, 22, 5, 2, 2, TILE_COVER)
    rect(e, 13, 18, 2, 2, TILE_COVER)
    # 辐射标记装饰
    for gx, gy in ((8, 12), (12, 9), (27, 13), (32, 12), (18, 25)):
        tile(e, gx, gy, TILE_DECOR)
    # 冷却池（水坑，核电站特色）
    rect(e, 25, 10, 3, 2, TILE_WATER)
    rect(e, 25, 24, 3, 2, TILE_WATER)
    # 铁丝网（尖刺边缘）
    tile(e, 10, 20, TILE_SPIKE, 3); tile(e, 10, 21, TILE_SPIKE, 3)
    _save(e, "nuclear")


def main():
    os.makedirs(MAPS_DIR, exist_ok=True)
    # 删除不符合剧情的旧地图
    for old in ("forest", "factory", "graveyard", "hospital"):
        p = os.path.join(MAPS_DIR, f"{old}.zmap")
        if os.path.exists(p):
            os.remove(p)
            print(f"删除旧图 {old}.zmap")
    gen_school()
    gen_street()
    gen_downtown()
    gen_suburb()
    gen_nuclear()
    print("全部剧情地图生成完成：")


if __name__ == "__main__":
    main()
