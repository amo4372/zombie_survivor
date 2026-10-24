import random
import math
import pygame

class Camera:
    def __init__(self, width, height):
        self.x = 0
        self.y = 0
        self.width = width
        self.height = height
        self.shake_x = 0
        self.shake_y = 0
        self.shake_duration = 0
        self.shake_intensity = 0
        self.shake_enabled = True

    def shake(self, intensity=5, duration=0.3):
        if not self.shake_enabled:
            return
        self.shake_intensity = intensity
        self.shake_duration = duration

    def follow(self, target_x, target_y, dt, smooth=0.1, bounds=None):
        target_cam_x = target_x - self.width // 2
        target_cam_y = target_y - self.height // 2
        # v2.5.0 摄像机钳制到地图界内（边界明显化：玩家到墙边时镜头停住露出边界墙）
        if bounds:
            try:
                _lo, _hi = bounds
                target_cam_x = max(_lo - self.width, min(_hi - self.width, target_cam_x))
                target_cam_y = max(_lo - self.height, min(_hi - self.height, target_cam_y))
            except Exception:
                pass
        self.x += (target_cam_x - self.x) * smooth
        self.y += (target_cam_y - self.y) * smooth

        if self.shake_duration > 0:
            self.shake_x = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_y = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_duration -= dt
            self.shake_intensity *= 0.9
        else:
            self.shake_x = 0
            self.shake_y = 0

    def shake(self, intensity=5, duration=0.3):
        self.shake_intensity = intensity
        self.shake_duration = duration

    def apply(self, x, y):
        return x - self.x + self.shake_x, y - self.y + self.shake_y

