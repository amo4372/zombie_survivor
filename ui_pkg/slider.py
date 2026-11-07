# -*- coding: utf-8 -*-
"""Slider —— 通用滑动条控件（v2.9.14）

设计要点
--------
* 逻辑坐标（base_x/y/w/h）+ `scale` 缩放，与 `Button` 保持同一套接口，
  可直接放进 HUD 布局体系。
* 触控与鼠标**分开记账**，且按下当帧就生效（不依赖 down→up 配对）：
  手机端没有"鼠标按下"概念，也不需要等到抬手才看到数值变化。
  `touch_id` 精确配对，避免多指互相抢滑块。
* 支持点击轨道任意位置直接跳值 + 拖动连续调整。
* `on_change(value)` 回调只在值真的变化时触发，避免每帧写控件属性。
"""
import pygame

__all__ = ["Slider"]


class Slider:
    TRACK_COLOR = (38, 52, 72)
    FILL_COLOR = (70, 165, 240)
    KNOB_COLOR = (235, 245, 255)
    BORDER_COLOR = (120, 160, 205)
    TEXT_COLOR = (220, 235, 250)

    def __init__(self, x, y, w, h, min_value=0.0, max_value=1.0, value=None,
                 label="", on_change=None, step=0.0, fmt=None):
        self.base_x = int(x)
        self.base_y = int(y)
        self.base_w = int(w)
        self.base_h = int(h)
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        if self.max_value <= self.min_value:
            self.max_value = self.min_value + 1.0
        # step 必须在 _clamp 之前赋值：旧版放后面，构造时 _clamp 读不到
        # self.step 直接走 except 返回 min_value —— 初始值永远是下限。
        self.step = float(step or 0.0)
        self.fmt = fmt
        self.label = str(label)
        self.on_change = on_change
        self.value = self._clamp(float(value if value is not None else min_value))
        self.visible = True
        self.enabled = True
        self.hovered = False
        self.dragging = False
        self._touch_id = None
        self._last_reported = self.value

    # ------------------------------------------------------------------
    def _clamp(self, v):
        try:
            v = max(self.min_value, min(self.max_value, float(v)))
            if self.step > 0:
                v = self.min_value + round((v - self.min_value) / self.step) * self.step
            return v
        except Exception:
            return self.min_value

    def get_scaled_rect(self, scale=1.0):
        return pygame.Rect(
            int(self.base_x * scale), int(self.base_y * scale),
            int(self.base_w * scale), int(self.base_h * scale))

    def set_value(self, v, notify=False):
        nv = self._clamp(v)
        changed = abs(nv - self.value) > 1e-6
        self.value = nv
        if changed and notify and self.on_change:
            self.on_change(nv)
        return changed

    def get_value(self):
        return self.value

    def value_text(self):
        if self.fmt:
            try:
                return self.fmt % self.value
            except Exception:
                pass
        if self.step >= 1.0:
            return str(int(self.value))
        return "%.2f" % self.value

    # ------------------------------------------------------------------
    def _value_from_x(self, px, rect):
        pad = max(6, rect.h // 3)
        usable = max(1, rect.w - pad * 2)
        t = (float(px) - (rect.x + pad)) / usable
        t = max(0.0, min(1.0, t))
        return self._clamp(self.min_value + t * (self.max_value - self.min_value))

    def _apply(self, nv):
        changed = self.set_value(nv, notify=True)
        if changed:
            self._last_reported = self.value
        return changed

    def update(self, mouse_pos, mouse_pressed, touch_events=None, scale=1.0):
        """返回本帧值是否变化。按下当帧即生效，不依赖 up 配对。"""
        if not self.visible or not self.enabled:
            return False
        rect = self.get_scaled_rect(scale)
        self.hovered = rect.collidepoint(mouse_pos)
        changed = False

        # 1) 触控：down 立即生效并按 touch_id 独占拖动
        if touch_events:
            for e in touch_events:
                et = e.get("type")
                tid = e.get("id", -1)
                if et == "down":
                    if self._touch_id is None and rect.collidepoint(e.get("pos", (-1, -1))):
                        self._touch_id = tid
                        self.dragging = True
                        changed = self._apply(self._value_from_x(e["pos"][0], rect)) or changed
                elif et == "move":
                    if self._touch_id == tid and self.dragging:
                        changed = self._apply(self._value_from_x(e["pos"][0], rect)) or changed
                elif et == "up":
                    if self._touch_id == tid:
                        self._touch_id = None
                        self.dragging = False

        # 2) 鼠标：按住拖动（未被触控占用时）
        if self._touch_id is None and mouse_pressed and mouse_pressed[0]:
            if self.dragging or rect.collidepoint(mouse_pos):
                self.dragging = True
                changed = self._apply(self._value_from_x(mouse_pos[0], rect)) or changed
        elif self._touch_id is None:
            self.dragging = False
        return changed

    # ------------------------------------------------------------------
    def draw(self, screen, font, scale=1.0):
        if not self.visible:
            return
        rect = self.get_scaled_rect(scale)
        pad = max(6, rect.h // 3)
        track_y = rect.y + rect.h // 2
        track_h = max(4, int(rect.h * 0.28))
        track = pygame.Rect(rect.x + pad, track_y - track_h // 2,
                            max(1, rect.w - pad * 2), track_h)
        pygame.draw.rect(screen, self.TRACK_COLOR, track, border_radius=track_h // 2)
        pygame.draw.rect(screen, self.BORDER_COLOR, track, 1, border_radius=track_h // 2)

        t = (self.value - self.min_value) / (self.max_value - self.min_value)
        knob_x = int(track.x + t * track.w)
        fill = pygame.Rect(track.x, track.y, max(1, knob_x - track.x), track_h)
        pygame.draw.rect(screen, self.FILL_COLOR, fill, border_radius=track_h // 2)

        kr = max(7, int(rect.h * 0.42))
        col = self.KNOB_COLOR if (self.dragging or self.hovered) else (180, 210, 240)
        pygame.draw.circle(screen, (20, 30, 45), (knob_x, track_y), kr + 2)
        pygame.draw.circle(screen, col, (knob_x, track_y), kr)
        pygame.draw.circle(screen, (255, 255, 255), (knob_x, track_y), max(2, kr // 3))

        if font:
            try:
                txt = "%s  %s" % (self.label, self.value_text()) if self.label else self.value_text()
                lab = font.render(txt, True, self.TEXT_COLOR)
                screen.blit(lab, (rect.x, rect.y - lab.get_height() - 2))
            except Exception:
                pass
