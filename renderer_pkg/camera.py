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

    def follow(self, target_x, target_y, dt, smooth=0.1):
        target_cam_x = target_x - self.width // 2
        target_cam_y = target_y - self.height // 2
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

