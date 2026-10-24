# -*- coding: utf-8 -*-
"""GUI 地图编辑器（pygame）—— 编辑 .zmap 二进制大地图

操作：
  鼠标左键拖动   绘制障碍物（墙）
  鼠标右键拖动   擦除（空地）
  X 键切换模式   掩体（可遮挡不阻挡）
  数字键 0-4     放置对象：0玩家出生点 1僵尸出生点 2巡逻点 3出口 4补给点
  S 保存 / L 加载 / C 清空 / Esc 退出
  --dummy 无头测试模式（不依赖显示器，程序化验证保存/加载）

用法：
  python3 rl/map_editor.py                       # 打开 GUI 编辑 rl/maps/demo.zmap
  python3 rl/map_editor.py --dummy               # 无头链路测试
  python3 rl/map_editor.py --map rl/maps/x.zmap
"""
import os
import sys
import argparse
import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from map_format import (make_map, save_map, load_map, demo_map,
                        TILE_SIZE, TILE_EMPTY, TILE_BLOCK, TILE_COVER,
                        TILE_WATER, TILE_SPIKE, TILE_TREE, TILE_VEHICLE,
                        TILE_BUILDING, TILE_FENCE, TILE_DECOR, TILE_NAMES,
                        OBJ_NAMES)

COL_BG = (28, 28, 34)
COL_GRID = (45, 45, 55)
# tile 颜色表（10 种元素）
TILE_COLORS = {
    TILE_EMPTY: None, TILE_BLOCK: (120, 80, 60), TILE_COVER: (90, 130, 90),
    TILE_WATER: (70, 110, 200), TILE_SPIKE: (200, 200, 80), TILE_TREE: (40, 130, 70),
    TILE_VEHICLE: (160, 90, 160), TILE_BUILDING: (110, 110, 120),
    TILE_FENCE: (170, 150, 100), TILE_DECOR: (70, 70, 90),
}
COL_OBJ = {0: (90, 200, 120), 1: (200, 90, 90), 2: (230, 200, 90),
           3: (120, 160, 230), 4: (210, 140, 220)}


class MapEditor:
    def __init__(self, path="rl/maps/school.zmap", dummy=False):
        self.dummy = dummy
        self.path = path
        if os.path.exists(path):
            self.map = load_map(path)
        else:
            self.map = make_map()
        self.paint = TILE_BLOCK       # 当前绘制 tile
        self.obj_type = -1            # -1 表示绘制模式，0-4 表示放置对象
        self.dirty = False
        self._key_tiles = {pygame.K_b: TILE_BLOCK, pygame.K_c: TILE_COVER,
                           pygame.K_w: TILE_WATER, pygame.K_s: TILE_SPIKE,
                           pygame.K_t: TILE_TREE, pygame.K_v: TILE_VEHICLE,
                           pygame.K_h: TILE_BUILDING, pygame.K_f: TILE_FENCE,
                           pygame.K_d: TILE_DECOR}

    # ---- 编辑操作（与 GUI 解耦，可测试）----
    def paint_at(self, x, y, tile=None):
        """像素坐标 → 涂/擦格；返回 (gx, gy, 是否变更)"""
        m = self.map
        gx, gy = int(x // TILE_SIZE), int(y // TILE_SIZE)
        if not (0 <= gx < m["width"] and 0 <= gy < m["height"]):
            return None
        t = tile if tile is not None else self.paint
        i = gy * m["width"] + gx
        if m["tiles"][i] != t:
            m["tiles"][i] = t
            self.dirty = True
        return (gx, gy, True)

    def place_obj(self, x, y):
        """放置当前对象类型（对象是像素坐标+半径）"""
        if self.obj_type < 0:
            return False
        self.map["objects"].append({"type": self.obj_type, "x": float(x),
                                    "y": float(y), "r": 12.0, "extra": 0})
        self.dirty = True
        return True

    def clear(self):
        self.map = make_map(self.map["width"], self.map["height"])
        self.dirty = True

    def save(self, path=None):
        p = path or self.path
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        save_map(self.map, p)
        self.dirty = False
        return p

    def load(self, path=None):
        p = path or self.path
        if os.path.exists(p):
            self.map = load_map(p)
            self.dirty = False
            return True
        return False

    # ---- GUI（真机使用；--dummy 下跳过窗口）----
    def run(self):
        if self.dummy:
            return self._dummy_test()
        import pygame
        pygame.init()
        w = self.map["width"] * TILE_SIZE
        h = self.map["height"] * TILE_SIZE
        screen = pygame.display.set_mode((w, h))
        pygame.display.set_caption(f"僵尸幸存者 地图编辑器 - {self.path}")
        font = pygame.font.SysFont("microsoftyahei,simhei,arial", 18)
        clock = pygame.time.Clock()
        dragging = False
        drag_erase = False
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    return
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        pygame.quit()
                        return
                    if ev.key == pygame.K_s:
                        print(f"[EDITOR] 已保存: {self.save()}")
                    if ev.key == pygame.K_l:
                        print(f"[EDITOR] 已加载: {self.load()}")
                    if ev.key == pygame.K_c:
                        self.clear()
                        print("[EDITOR] 已清空")
                    if ev.key in self._key_tiles:
                        self.paint = self._key_tiles[ev.key]
                        self.obj_type = -1
                        print(f"[EDITOR] 绘制元素: {TILE_NAMES[self.paint]}")
                    for k in range(5):
                        if ev.key == pygame.K_0 + k:
                            self.obj_type = k
                            print(f"[EDITOR] 放置对象: {OBJ_NAMES[k]}")
                    if ev.key == pygame.K_SPACE:
                        self.obj_type = -1
                        print("[EDITOR] 切换为绘制模式")
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    if ev.button == 1:
                        dragging = True
                        drag_erase = False
                        if self.obj_type >= 0:
                            self.place_obj(*ev.pos)
                        else:
                            self.paint_at(*ev.pos)
                    elif ev.button == 3:
                        dragging = True
                        drag_erase = True
                if ev.type == pygame.MOUSEBUTTONUP:
                    dragging = False
                if ev.type == pygame.MOUSEMOTION and dragging:
                    if drag_erase:
                        self.paint_at(*ev.pos, tile=TILE_EMPTY)
                    elif self.obj_type < 0:
                        self.paint_at(*ev.pos)
            self._draw(screen, font)
            pygame.display.flip()
            clock.tick(60)

    def _draw(self, screen, font):
        m = self.map
        screen.fill(COL_BG)
        for gy in range(m["height"]):
            for gx in range(m["width"]):
                t = m["tiles"][gy * m["width"] + gx]
                c = TILE_COLORS.get(t)
                if c:
                    pygame.draw.rect(screen, c, (gx * TILE_SIZE, gy * TILE_SIZE,
                                                 TILE_SIZE - 1, TILE_SIZE - 1))
        for o in m["objects"]:
            c = COL_OBJ.get(o["type"], (200, 200, 200))
            r = int(o.get("r", 12))
            pygame.draw.circle(screen, c, (int(o["x"]), int(o["y"])), r, 2)
        # 网格
        for gx in range(m["width"] + 1):
            pygame.draw.line(screen, COL_GRID, (gx * TILE_SIZE, 0),
                             (gx * TILE_SIZE, m["height"] * TILE_SIZE))
        for gy in range(m["height"] + 1):
            pygame.draw.line(screen, COL_GRID, (0, gy * TILE_SIZE),
                             (m["width"] * TILE_SIZE, gy * TILE_SIZE))
        hint = (f"S保存 L加载 C清空 X掩体 SPACE绘制 | 数字键: "
                + " ".join(f"{k}={OBJ_NAMES[k]}" for k in range(5)))
        screen.blit(font.render(hint, True, (220, 220, 220)), (8, 4))

    # ---- 无头链路测试 ----
    def _dummy_test(self):
        # 程序化编辑：涂障碍、擦除、放对象、保存、加载、断言
        self.clear()                     # 从空地图开始（防残留）
        self.paint_at(200, 200)          # 涂一格障碍
        self.paint_at(232, 200)          # 相邻格
        self.paint_at(200, 200, tile=TILE_EMPTY)   # 擦掉第一格
        self.obj_type = 1
        self.place_obj(500, 400)         # 放僵尸出生点
        self.obj_type = 2
        self.place_obj(700, 400)         # 放巡逻点
        p = self.save("rl/maps/editor_test.zmap")
        self.map = None
        self.load(p)
        m = self.map
        assert m["tiles"][(200 // 32) + (200 // 32) * m["width"]] == TILE_EMPTY  # 擦除生效
        assert m["tiles"][7 + 6 * m["width"]] == TILE_BLOCK                       # 保留格
        types = [o["type"] for o in m["objects"]]
        assert 1 in types and 2 in types, types
        print(f"[EDITOR] 无头链路测试通过: {p} ({m['width']}x{m['height']}, "
              f"对象 {len(m['objects'])})")
        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="rl/maps/school.zmap")
    ap.add_argument("--dummy", action="store_true", help="无头链路测试（无显示器）")
    args = ap.parse_args()
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if args.dummy:
        args.map = "rl/maps/editor_test.zmap"
    ed = MapEditor(args.map, dummy=args.dummy)
    sys.exit(ed.run())
