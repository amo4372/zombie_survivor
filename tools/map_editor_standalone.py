#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""丧尸幸存者 · 独立地图编辑器（v2.9.23）

**不内置在游戏里**：独立进程运行，编辑结果导出为 `.zmap`，由游戏端
`zombie_pkg/map_loader.apply_zmap()` 装载成障碍物 / 效果区 / 出生点。

用法：
    python3 tools/map_editor_standalone.py                 # 编辑 maps/custom.zmap
    python3 tools/map_editor_standalone.py --map maps/x.zmap
    python3 tools/map_editor_standalone.py --dummy         # 无头链路自检（测试用）

键控：
    1~9 / 0 / B C W S T V H F D   切换地块
    F1~F5                        切换对象（玩家/僵尸出生、巡逻、出口、补给）
    左键拖动绘制 / 右键拖动擦除 / 中键拖动平移
    方向键 / WASD 平移，+ - 缩放
    Ctrl+S 保存，L 载入，X 清空，Esc 退出

触控：
    单指点击/拖动画布绘制，工具栏按钮直接点；
    底部方向按钮平移画布，「导出为当前地图」后游戏零配置自动加载。
"""
import os
import sys
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENDOR = os.path.join(ROOT, "_vendor")
if os.path.isdir(_VENDOR):
    sys.path.insert(0, _VENDOR)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "rl"))
os.chdir(ROOT)

import pygame

from map_format import (make_map, save_map, load_map, TILE_SIZE,
                        TILE_EMPTY, TILE_BLOCK, TILE_COVER, TILE_WATER,
                        TILE_SPIKE, TILE_TREE, TILE_VEHICLE, TILE_BUILDING,
                        TILE_FENCE, TILE_DECOR, TILE_NAMES, OBJ_NAMES,
                        BLOCK_TILES, OCCLUDE_TILES)

COL_BG = (24, 26, 32)
COL_PANEL = (36, 40, 50)
COL_GRID = (58, 62, 74)
COL_TEXT = (232, 236, 244)
COL_HINT = (150, 210, 255)
TILE_COLORS = {
    TILE_EMPTY: (44, 46, 54), TILE_BLOCK: (128, 88, 66),
    TILE_COVER: (92, 138, 96), TILE_WATER: (70, 118, 206),
    TILE_SPIKE: (202, 196, 84), TILE_TREE: (42, 136, 74),
    TILE_VEHICLE: (164, 94, 164), TILE_BUILDING: (112, 114, 126),
    TILE_FENCE: (176, 152, 104), TILE_DECOR: (76, 76, 96),
}
OBJ_COLORS = [(90, 210, 130), (220, 92, 92), (232, 206, 96),
              (126, 166, 236), (214, 142, 224)]

# 地块工具顺序（数字键 1..9 / 0 与字母键）
TILE_TOOLS = [TILE_BLOCK, TILE_COVER, TILE_WATER, TILE_SPIKE, TILE_TREE,
              TILE_VEHICLE, TILE_BUILDING, TILE_FENCE, TILE_DECOR, TILE_EMPTY]
KEY_TO_TILE = {pygame.K_1: TILE_BLOCK, pygame.K_2: TILE_COVER,
               pygame.K_3: TILE_WATER, pygame.K_4: TILE_SPIKE,
               pygame.K_5: TILE_TREE, pygame.K_6: TILE_VEHICLE,
               pygame.K_7: TILE_BUILDING, pygame.K_8: TILE_FENCE,
               pygame.K_9: TILE_DECOR, pygame.K_0: TILE_EMPTY,
               # 只保留不与 WASD 平移冲突的字母键；W/S/D 让给方向键位
               pygame.K_b: TILE_BLOCK, pygame.K_c: TILE_COVER,
               pygame.K_t: TILE_TREE, pygame.K_v: TILE_VEHICLE,
               pygame.K_h: TILE_BUILDING, pygame.K_f: TILE_FENCE,
               pygame.K_g: TILE_DECOR}


def font(size=18, bold=False):
    for name in ("WenQuanYi Micro Hei", "Noto Sans CJK SC", "Arial"):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, size)


class StandaloneMapEditor:
    def __init__(self, path="maps/custom.zmap"):
        self.path = path
        self.map = load_map(path) if os.path.isfile(path) else make_map()
        self.tile = TILE_BLOCK
        self.obj_type = -1            # -1 = 画地块，0..4 = 放对象
        self.dirty = False
        self.cam_x, self.cam_y = 0.0, 0.0
        self.zoom = 1.0
        self.tip = ""
        self.tip_timer = 0.0
        self.buttons = []             # (rect, label, callback)
        self._drag = None             # (finger_id/mouse button, mode)
        self._last_cell = None

    # ---------------- 编辑核心（可无头调用） ----------------
    def paint_world(self, wx, wy, tile=None, erase=False):
        gx, gy = int(wx // TILE_SIZE), int(wy // TILE_SIZE)
        w, h = self.map["width"], self.map["height"]
        if not (0 <= gx < w and 0 <= gy < h):
            return False
        t = TILE_EMPTY if erase else (tile if tile is not None else self.tile)
        i = gy * w + gx
        if self.map["tiles"][i] != t:
            self.map["tiles"][i] = t
            self.dirty = True
        return True

    def place_world(self, wx, wy):
        if self.obj_type < 0:
            return False
        self.map["objects"].append({"type": self.obj_type, "x": float(wx),
                                    "y": float(wy), "r": 12.0, "extra": 0})
        self.dirty = True
        return True

    def clear(self):
        self.map = make_map(self.map["width"], self.map["height"])
        self.dirty = True

    def save(self, path=None):
        p = path or self.path
        d = os.path.dirname(os.path.abspath(p))
        if d:
            os.makedirs(d, exist_ok=True)
        save_map(self.map, p)
        self.dirty = False
        return p

    def load(self, path=None):
        p = path or self.path
        if os.path.isfile(p):
            self.map = load_map(p)
            self.path = p
            self.dirty = False
            return True
        return False

    def export_active(self):
        """导出为游戏零配置自动加载的地图"""
        self.save("maps/active.zmap")
        self.save(self.path)
        return "maps/active.zmap"

    def set_tip(self, text):
        self.tip, self.tip_timer = text, 2.4

    # ---------------- 坐标换算 ----------------
    def screen_to_world(self, sx, sy, canvas_top):
        return ((sx - 12) / self.zoom + self.cam_x,
                (sy - canvas_top) / self.zoom + self.cam_y)

    def world_to_screen(self, wx, wy, canvas_top):
        return (int((wx - self.cam_x) * self.zoom + 12),
                int((wy - self.cam_y) * self.zoom + canvas_top))

    # ---------------- UI ----------------
    def build_buttons(self, sw, sh):
        b = []
        top_h = 56
        bw = min(116, max(78, (sw - 24) // len(TILE_TOOLS)))
        for i, t in enumerate(TILE_TOOLS):
            r = pygame.Rect(12 + i * bw, 8, bw - 4, 40)
            b.append((r, TILE_NAMES[t], ("tile", t), t == self.tile and self.obj_type < 0))
        by = sh - 52
        labels = ["玩家出生", "僵尸出生", "巡逻点", "出口", "补给点"]
        for i, lab in enumerate(labels):
            r = pygame.Rect(12 + i * 112, by, 106, 40)
            b.append((r, lab, ("obj", i), self.obj_type == i))
        ops = [("保存", "save"), ("载入", "load"), ("清空", "clear"),
               ("导出为当前地图", "export"), ("退出", "quit"),
               ("左", ("pan", -60, 0)), ("右", ("pan", 60, 0)),
               ("上", ("pan", 0, -60)), ("下", ("pan", 0, 60)),
               ("放大", ("zoom", 0.2)), ("缩小", ("zoom", -0.2))]
        x = sw - 12
        for lab, act in reversed(ops):
            w = 132 if lab == "导出为当前地图" else 76
            x -= w + 6
            r = pygame.Rect(x, by - 48, w, 36)
            b.append((r, lab, ("op", act), False))
        self.buttons = b
        return top_h, by - 56

    def handle_action(self, act):
        if isinstance(act, tuple) and act[0] == "tile":
            self.tile, self.obj_type = act[1], -1
            self.set_tip("工具：" + TILE_NAMES[self.tile])
        elif isinstance(act, tuple) and act[0] == "obj":
            self.obj_type = act[1]
            self.set_tip("对象：" + OBJ_NAMES[self.obj_type])
        elif isinstance(act, tuple) and act[0] == "pan":
            self.cam_x += act[1] / self.zoom
            self.cam_y += act[2] / self.zoom
        elif isinstance(act, tuple) and act[0] == "zoom":
            self.zoom = max(0.5, min(2.0, self.zoom + act[1]))
        elif act == "save":
            self.set_tip("已保存 " + self.save())
        elif act == "load":
            self.set_tip("已载入 " + self.path if self.load() else "文件不存在")
        elif act == "clear":
            self.clear(); self.set_tip("已清空")
        elif act == "export":
            self.set_tip("已导出 " + self.export_active() + "，启动游戏即生效")
        elif act == "quit":
            return False
        return True

    def click_button(self, pos):
        for r, _lab, act, _sel in self.buttons:
            if r.collidepoint(pos):
                return self.handle_action(act)
        return True

    # ---------------- 主循环 ----------------
    def run(self, window=None):
        pygame.init()
        if window:
            sw, sh = window
            screen = pygame.display.set_mode((sw, sh))
        else:
            _i = pygame.display.Info()
            sw, sh = min(1280, _i.current_w), min(800, _i.current_h)
            screen = pygame.display.set_mode((sw, sh))
        pygame.display.set_caption("丧尸幸存者 · 独立地图编辑器 (.zmap)")
        clock = pygame.time.Clock()
        f18, f14 = font(18), font(14)
        running = True
        while running:
            top_h, canvas_bottom = self.build_buttons(sw, sh)
            canvas_top = top_h
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False
                    elif ev.key in KEY_TO_TILE:
                        self.tile, self.obj_type = KEY_TO_TILE[ev.key], -1
                    elif ev.key in (pygame.K_F1, pygame.K_F2, pygame.K_F3,
                                    pygame.K_F4, pygame.K_F5):
                        self.obj_type = ev.key - pygame.K_F1
                    elif ev.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        self.set_tip("已保存 " + self.save())
                    elif ev.key == pygame.K_l:
                        self.load(); self.set_tip("已载入 " + self.path)
                    elif ev.key == pygame.K_x:
                        self.clear(); self.set_tip("已清空")
                    elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self.zoom = min(2.0, self.zoom + 0.2)
                    elif ev.key == pygame.K_MINUS:
                        self.zoom = max(0.5, self.zoom - 0.2)
                    elif ev.key in (pygame.K_LEFT, pygame.K_a):
                        self.cam_x -= 60 / self.zoom
                    elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                        self.cam_x += 60 / self.zoom
                    elif ev.key in (pygame.K_UP, pygame.K_w):
                        self.cam_y -= 60 / self.zoom
                    elif ev.key in (pygame.K_DOWN, pygame.K_s):
                        self.cam_y += 60 / self.zoom
                elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                    if ev.type == pygame.FINGERDOWN:
                        pos = (int(ev.x * sw), int(ev.y * sh))
                        fid = ev.finger_id
                    else:
                        pos, fid = ev.pos, -1
                    if pos[1] < canvas_top or pos[1] > canvas_bottom:
                        self._drag = None
                        if ev.type == pygame.MOUSEBUTTONDOWN:
                            running = self.click_button(pos)
                        continue
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 2:
                        self._drag = (fid, "pan", pos)
                    elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
                        self._drag = (fid, "erase", pos)
                        self.paint_at_screen(pos, canvas_top, erase=True)
                    else:
                        self._drag = (fid, "paint", pos)
                        self.paint_at_screen(pos, canvas_top)
                elif ev.type in (pygame.MOUSEMOTION, pygame.FINGERMOTION):
                    if not self._drag:
                        continue
                    if ev.type == pygame.FINGERMOTION:
                        pos = (int(ev.x * sw), int(ev.y * sh))
                    else:
                        pos = ev.pos
                    mode = self._drag[1]
                    if mode == "pan":
                        self.cam_x -= (pos[0] - self._drag[2][0]) / self.zoom
                        self.cam_y -= (pos[1] - self._drag[2][1]) / self.zoom
                        self._drag = (self._drag[0], mode, pos)
                    elif mode == "paint":
                        self.paint_at_screen(pos, canvas_top)
                    elif mode == "erase":
                        self.paint_at_screen(pos, canvas_top, erase=True)
                elif ev.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                    if ev.type == pygame.FINGERUP:
                        pos = (int(ev.x * sw), int(ev.y * sh))
                        if self._drag is None and (pos[1] < canvas_top or pos[1] > canvas_bottom):
                            running = self.click_button(pos)
                    self._drag = None
                    self._last_cell = None

            # ---------- 绘制 ----------
            screen.fill(COL_BG)
            step = int(TILE_SIZE * self.zoom)
            ox = int(-self.cam_x * self.zoom) % step if step > 0 else 0
            oy = int(-self.cam_y * self.zoom) % step if step > 0 else 0
            for gx in range(self.map["width"]):
                for gy in range(self.map["height"]):
                    t = self.map["tiles"][gy * self.map["width"] + gx]
                    if t == TILE_EMPTY:
                        continue
                    sx, sy = self.world_to_screen(gx * TILE_SIZE, gy * TILE_SIZE, canvas_top)
                    if sx < -step or sx > sw or sy < canvas_top or sy > canvas_bottom:
                        continue
                    pygame.draw.rect(screen, TILE_COLORS.get(t, (110, 110, 110)),
                                    (sx, sy, max(1, step - 1), max(1, step - 1)))
            for gx in range(ox, sw, max(1, step)):
                pygame.draw.line(screen, COL_GRID, (gx, canvas_top), (gx, canvas_bottom))
            for gy in range(canvas_top + oy, canvas_bottom, max(1, step)):
                pygame.draw.line(screen, COL_GRID, (0, gy), (sw, gy))
            for o in self.map.get("objects", []):
                sx, sy = self.world_to_screen(o["x"], o["y"], canvas_top)
                c = OBJ_COLORS[o["type"] % len(OBJ_COLORS)]
                pygame.draw.circle(screen, c, (sx, sy), max(4, int(10 * self.zoom)))
                pygame.draw.circle(screen, (255, 255, 255), (sx, sy),
                                   max(4, int(10 * self.zoom)), 1)
            # 面板
            pygame.draw.rect(screen, COL_PANEL, (0, 0, sw, top_h))
            pygame.draw.rect(screen, COL_PANEL, (0, canvas_bottom, sw, sh - canvas_bottom))
            for r, lab, _act, sel in self.buttons:
                pygame.draw.rect(screen, (64, 92, 128) if sel else (52, 58, 72), r, border_radius=6)
                pygame.draw.rect(screen, (210, 180, 90) if sel else (92, 100, 116), r, 2,
                                 border_radius=6)
                screen.blit(f14.render(lab, True, COL_TEXT),
                            f14.render(lab, True, COL_TEXT).get_rect(center=r.center))
            cur = TILE_NAMES[self.tile] if self.obj_type < 0 else OBJ_NAMES[self.obj_type]
            _rule = "挡弹+挡视线" if self.tile in OCCLUDE_TILES and self.tile in BLOCK_TILES \
                else ("挡弹" if self.tile in BLOCK_TILES else
                      ("挡视线" if self.tile in OCCLUDE_TILES else "可通行"))
            info = "工具: %s (%s)  |  %s  |  %s  |  缩放 %.1f  |  %s" % (
                cur, _rule, self.path, "已修改" if self.dirty else "已保存",
                self.zoom, self.tip if self.tip_timer > 0 else
                "键控 1-9/B C W S T V H F D · 触控点选工具 · Ctrl+S 保存 · 导出为当前地图")
            screen.blit(f14.render(info, True, COL_HINT), (12, top_h + 6))
            if self.tip_timer > 0:
                self.tip_timer -= clock.get_time() / 1000.0
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()
        return 0

    def paint_at_screen(self, pos, canvas_top, erase=False):
        wx, wy = self.screen_to_world(pos[0], pos[1], canvas_top)
        cell = (int(wx // TILE_SIZE), int(wy // TILE_SIZE))
        if self.obj_type >= 0 and not erase:
            if cell == self._last_cell:
                return
            self._last_cell = cell
            self.place_world(cell[0] * TILE_SIZE + TILE_SIZE / 2,
                             cell[1] * TILE_SIZE + TILE_SIZE / 2)
        else:
            self.paint_world(wx, wy, erase=erase)


def dummy_selftest():
    """无头链路：建图 → 涂格 → 放对象 → 存 .zmap → 载入 → 校验"""
    import tempfile
    p = os.path.join(tempfile.gettempdir(), "zs_map_editor_selftest.zmap")
    e = StandaloneMapEditor(p)
    e.clear()
    assert e.paint_world(100, 100, TILE_BLOCK)
    assert e.paint_world(200, 100, TILE_WATER)
    e.obj_type = 0
    assert e.place_world(320, 160)
    e.save(p)
    e2 = StandaloneMapEditor(p)
    w = e2.map["width"]
    assert e2.map["tiles"][int(100 // TILE_SIZE) + int(100 // TILE_SIZE) * w] == TILE_BLOCK
    assert e2.map["tiles"][int(200 // TILE_SIZE) + int(100 // TILE_SIZE) * w] == TILE_WATER
    assert len(e2.map["objects"]) == 1 and e2.map["objects"][0]["type"] == 0
    print("[DUMMY] zmap 往返 OK:", os.path.getsize(p), "bytes")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="maps/custom.zmap")
    ap.add_argument("--dummy", action="store_true")
    ap.add_argument("--window", default="")     # "1280x800"
    a = ap.parse_args()
    if a.dummy:
        sys.exit(dummy_selftest())
    win = None
    if a.window and "x" in a.window:
        try:
            win = tuple(int(v) for v in a.window.lower().split("x")[:2])
        except Exception:
            pass
    sys.exit(StandaloneMapEditor(a.map).run(win))
