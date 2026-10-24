#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.6 程序化生成载具俯视图 PNG（v2 重绘：参考真实外观，大幅提升像真度）
- 大运重卡：红色经典款——平头驾驶室（前脸格栅+双大灯+顶部"大运"黄字）+红色货箱（竖纹+顶棚+后门）+10轮底盘+油箱排气管
- 99A主战坦克：楔形炮塔+长身管125滑膛炮（炮管超过车身一半）+数码迷彩+首上倾斜装甲+侧裙板+6对负重轮+尾部储物篮
- 武装直升机（直-10风格）：细长流线机身+5片主旋翼+细长尾梁+星形尾桨+短翼挂架（火箭巢/导弹）+机炮吊舱+机头观瞄
输出到 assets/vehicles/*.png（PIL 仅构建期依赖，游戏运行时直接导入 PNG）
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter


def _rr(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def _vgrad(img, box, c_top, c_bottom):
    """竖向渐变填充（增强立体感）"""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    for yy in range(y0, y1):
        t = (yy - y0) / max(1, (y1 - y0 - 1))
        c = tuple(int(a + (b - a) * t) for a, b in zip(c_top, c_bottom))
        d.line([x0, yy, x1, yy], fill=c)


def _camo(d, box, seed=7):
    """数码迷彩：随机绿/沙小方块网格（99A 特征涂装）"""
    x0, y0, x1, y1 = box
    rng = random.Random(seed)
    colors = [(88, 116, 72), (108, 138, 92), (140, 128, 92), (76, 98, 64)]
    size = 12
    for yy in range(y0, y1, size):
        for xx in range(x0, x1, size):
            if rng.random() < 0.72:
                d.rectangle([xx, yy, min(xx + size - 1, x1), min(yy + size - 1, y1)],
                            fill=rng.choice(colors))


def make_truck():
    """大运重卡（红色经典款·v2）：平头驾驶室+红色货箱+10轮底盘，前脸细节丰富"""
    img = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # ===== 底盘 =====
    d.rectangle([18, 128, 282, 140], fill=(58, 50, 44), outline=(24, 20, 18), width=2)
    # 油箱（右侧）
    d.rounded_rectangle([70, 118, 150, 130], 5, fill=(170, 176, 182), outline=(90, 94, 100), width=2)
    d.rectangle([74, 121, 146, 127], fill=(120, 124, 130))
    # 排气管（左侧，镀铬竖管）
    d.rectangle([46, 108, 52, 128], fill=(196, 200, 206), outline=(110, 114, 120), width=1)
    d.ellipse([44, 102, 54, 112], fill=(210, 214, 220), outline=(120, 124, 130), width=1)
    # ===== 轮胎（前2 + 后8：双轴双胎）=====
    for tx in (40, 74, 130, 162, 194, 226, 258, 286):
        d.ellipse([tx - 19, 118, tx + 19, 162], fill=(26, 26, 30), outline=(8, 8, 10), width=3)
        d.ellipse([tx - 6, 130, tx + 6, 150], fill=(96, 98, 106))
        d.ellipse([tx - 2, 134, tx + 2, 146], fill=(46, 48, 54))
    # ===== 货箱（红色，竖纹+顶棚+后门）=====
    d.rectangle([20, 26, 196, 118], fill=(198, 32, 28), outline=(118, 14, 12), width=3)
    _vgrad(img, (20, 26, 196, 118), (224, 44, 38), (178, 24, 22))
    for i in range(6):
        x0 = 32 + i * 28
        d.rectangle([x0, 32, x0 + 4, 112], fill=(240, 52, 46))
        d.rectangle([x0 + 9, 32, x0 + 12, 112], fill=(162, 20, 18))
    # 货箱顶棚（前部弧形罩）
    d.rounded_rectangle([20, 18, 196, 30], 6, fill=(214, 40, 34), outline=(118, 14, 12), width=2)
    # 货箱后门（尾部，带合页）
    d.rectangle([20, 108, 196, 116], fill=(150, 18, 16), outline=(100, 10, 8), width=2)
    d.rectangle([104, 22, 112, 108], fill=(150, 18, 16), outline=(100, 10, 8), width=1)
    # 侧栏板
    d.rectangle([20, 112, 196, 120], fill=(214, 40, 34), outline=(118, 14, 12), width=2)
    # ===== 驾驶室（红色平头·v2：更方正+前脸细节）=====
    d.polygon([(196, 14), (262, 14), (280, 40), (280, 120), (196, 120)],
              fill=(210, 36, 30), outline=(118, 14, 12), width=3)
    _vgrad(img, (196, 14, 280, 120), (232, 48, 42), (188, 26, 24))
    # 驾驶室顶部（导流罩+顶部黄色"大运"字样感）
    d.rounded_rectangle([200, 6, 258, 18], 4, fill=(226, 44, 38), outline=(120, 14, 12), width=2)
    d.rectangle([206, 9, 236, 15], fill=(240, 206, 66), outline=(150, 120, 30), width=1)  # 顶部"大运"黄字带
    # 前挡风玻璃（两块+黑框）
    d.rectangle([198, 30, 276, 58], fill=(70, 66, 62), outline=(30, 28, 26), width=2)
    d.rectangle([202, 34, 246, 55], fill=(92, 176, 214), outline=(40, 74, 104), width=2)
    d.rectangle([250, 34, 272, 55], fill=(108, 190, 228), outline=(40, 74, 104), width=2)
    d.line([248, 30, 248, 58], fill=(40, 40, 42), width=2)  # 中柱
    d.line([204, 40, 216, 55], fill=(24, 36, 46), width=3)  # 雨刷
    d.line([256, 40, 268, 55], fill=(24, 36, 46), width=3)
    # 前脸：进气格栅+保险杠+双大灯
    d.rectangle([198, 68, 278, 86], fill=(104, 14, 12), outline=(70, 8, 6), width=2)
    for gx in range(204, 278, 8):
        d.line([gx, 70, gx, 84], fill=(52, 6, 6), width=3)
    # 大灯（黄色矩形，红款经典）
    d.rectangle([196, 58, 212, 72], fill=(255, 236, 140), outline=(170, 140, 40), width=2)
    d.rectangle([264, 58, 282, 72], fill=(255, 240, 150), outline=(170, 140, 40), width=2)
    d.rectangle([196, 92, 212, 104], fill=(255, 232, 130), outline=(170, 140, 40), width=2)
    d.rectangle([264, 92, 282, 104], fill=(255, 232, 130), outline=(170, 140, 40), width=2)
    # 保险杠
    d.rounded_rectangle([190, 108, 284, 120], 6, fill=(66, 58, 52), outline=(26, 22, 20), width=2)
    d.rounded_rectangle([196, 102, 282, 112], 4, fill=(56, 50, 46), outline=(22, 20, 18), width=2)
    # 车门线/踏板
    d.line([236, 60, 236, 120], fill=(150, 18, 16), width=2)
    d.line([232, 88, 244, 88], fill=(150, 18, 16), width=2)
    # 后视镜
    d.rectangle([188, 44, 196, 60], fill=(60, 56, 52), outline=(26, 24, 22), width=2)
    d.rectangle([282, 44, 290, 60], fill=(60, 56, 52), outline=(26, 24, 22), width=2)
    # ===== 阴影（柔和）=====
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    return img


def make_tank():
    """99A主战坦克（俯视·v2）：楔形炮塔+长身管125滑膛炮+数码迷彩+侧裙+6负重轮"""
    img = Image.new("RGBA", (340, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # ===== 履带（左右，带履带板+6负重轮）=====
    for x0, x1 in ((34, 176), (164, 306)):
        d.rounded_rectangle([x0, 142, x1, 186], 24, fill=(54, 60, 48), outline=(22, 26, 20), width=4)
        for i in range(6):
            wx = x0 + 20 + i * 26
            d.ellipse([wx - 11, 146, wx + 11, 182], fill=(80, 88, 70), outline=(26, 30, 24), width=3)
            d.ellipse([wx - 4, 154, wx + 4, 170], fill=(154, 162, 142))
        for i in range(7):
            lx = x0 + 8 + i * 20
            d.line([lx, 143, lx + 7, 143], fill=(40, 46, 36), width=3)
            d.line([lx, 184, lx + 7, 184], fill=(40, 46, 36), width=3)
    # ===== 车体（首上倾斜装甲：前窄后宽的梯形 + 数码迷彩）=====
    d.polygon([(70, 70), (270, 70), (286, 144), (54, 144)], fill=(96, 122, 80), outline=(40, 54, 32), width=3)
    _camo(d, (70, 70, 286, 144), seed=11)
    # 首上装甲线
    d.line([(64, 138), (276, 138)], fill=(44, 58, 36), width=3)
    # ===== 侧裙板 =====
    d.rectangle([34, 136, 156, 146], fill=(76, 98, 64), outline=(40, 54, 32), width=2)
    d.rectangle([184, 136, 306, 146], fill=(76, 98, 64), outline=(40, 54, 32), width=2)
    # ===== 炮塔（楔形：前部尖、后部尾舱）+ 数码迷彩 =====
    d.polygon([(96, 44), (246, 44), (264, 110), (244, 128), (112, 128), (92, 110)],
              fill=(104, 132, 88), outline=(40, 54, 32), width=3)
    _camo(d, (96, 44, 264, 128), seed=23)
    # 炮塔尾舱（储物篮）
    d.rectangle([232, 96, 266, 124], fill=(88, 112, 74), outline=(40, 54, 32), width=2)
    d.line([236, 100, 262, 100], fill=(44, 58, 36), width=2)
    d.line([236, 108, 262, 108], fill=(44, 58, 36), width=2)
    d.line([236, 116, 262, 116], fill=(44, 58, 36), width=2)
    # 炮塔顶：舱盖+车长观瞄+横风传感器
    d.ellipse([150, 66, 188, 104], fill=(120, 150, 102), outline=(50, 64, 40), width=2)
    d.ellipse([156, 72, 182, 98], fill=(136, 166, 116), outline=(50, 64, 40), width=2)
    d.rectangle([128, 52, 142, 74], fill=(124, 154, 106), outline=(50, 64, 40), width=2)
    d.line([186, 30, 190, 52], fill=(140, 166, 118), width=3)  # 天线
    d.rectangle([108, 60, 118, 74], fill=(110, 140, 94), outline=(50, 64, 40), width=2)  # 炮手镜
    # ===== 主炮（长身管 125 滑膛炮：从炮塔前伸超过车身一半）=====
    # 炮管基座（炮塔前）
    d.rectangle([96, 70, 118, 102], fill=(84, 108, 70), outline=(40, 54, 32), width=2)
    # 长身管（带热护套分段）
    d.rectangle([118, 74, 330, 98], fill=(74, 96, 62), outline=(36, 48, 30), width=2)
    for seg in range(3):
        sx = 140 + seg * 62
        d.rectangle([sx, 73, sx + 6, 99], fill=(100, 124, 84), outline=(36, 48, 30), width=1)
    # 炮口制退器（十字开孔）
    d.rectangle([318, 70, 334, 102], fill=(44, 58, 42), outline=(24, 32, 24), width=2)
    d.line([322, 70, 322, 102], fill=(20, 26, 20), width=2)
    d.line([326, 70, 326, 102], fill=(20, 26, 20), width=2)
    d.line([318, 84, 334, 84], fill=(20, 26, 20), width=2)
    # 炮口朝向示意（左侧瞄准镜在炮管旁）
    d.rectangle([100, 60, 112, 70], fill=(108, 136, 92), outline=(40, 54, 32), width=1)
    # ===== 车体两侧工具箱 =====
    d.rectangle([60, 116, 110, 130], fill=(88, 112, 74), outline=(40, 54, 32), width=2)
    d.rectangle([230, 116, 280, 130], fill=(88, 112, 74), outline=(40, 54, 32), width=2)
    # ===== 柔和阴影 =====
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    return img


def make_heli():
    """武装直升机（直-10风格·v2）：细长流线机身+5片主旋翼+细长尾梁+星形尾桨+短翼挂架+机炮"""
    img = Image.new("RGBA", (340, 210), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # ===== 主旋翼（5片桨叶）=====
    hubx, huby = 140, 100
    blades = [0.55, 1.35, 0.95, 2.25, 0.35]
    for ang in blades:
        x1 = hubx + math.cos(ang) * 120
        y1 = huby + math.sin(ang) * 120
        x2 = hubx - math.cos(ang) * 120
        y2 = huby - math.sin(ang) * 120
        d.line([x1, y1, x2, y2], fill=(58, 60, 64), width=7)
        d.line([x1, y1, x2, y2], fill=(84, 86, 92), width=3)
    d.ellipse([hubx - 14, huby - 14, hubx + 14, huby + 14], fill=(44, 46, 50), outline=(22, 24, 28), width=3)
    # ===== 尾梁（细长）+ 星形尾桨 =====
    d.rectangle([220, 92, 308, 108], fill=(88, 92, 98), outline=(44, 46, 50), width=2)
    d.rectangle([228, 88, 308, 112], fill=(102, 106, 112), outline=(44, 46, 50), width=2)
    d.rectangle([286, 74, 304, 126], fill=(66, 68, 74), outline=(32, 34, 38), width=2)  # 垂直尾翼
    tp = (312, 100)
    for a in (0.0, 1.57, 3.14, 4.71):
        d.line([tp[0], tp[1], tp[0] + math.cos(a) * 22, tp[1] + math.sin(a) * 22], fill=(52, 54, 58), width=4)
    d.ellipse([tp[0] - 5, tp[1] - 5, tp[0] + 5, tp[1] + 5], fill=(40, 42, 46), width=2)
    # ===== 机身（细长流线）=====
    d.polygon([(60, 92), (150, 82), (196, 86), (232, 94), (232, 106), (196, 114), (150, 118), (60, 108)],
              fill=(104, 108, 114), outline=(46, 48, 52), width=3)
    d.polygon([(66, 95), (150, 87), (194, 90), (226, 97), (226, 103), (194, 110), (150, 113), (66, 105)],
              fill=(118, 122, 128))
    # 座舱（气泡风挡：机头处）
    d.ellipse([70, 88, 130, 112], fill=(130, 208, 236), outline=(50, 76, 96), width=2)
    d.ellipse([80, 93, 122, 107], fill=(152, 224, 246), outline=(60, 90, 110), width=1)
    d.line([100, 88, 100, 112], fill=(70, 90, 100), width=2)
    # 机头观瞄（光电转塔）
    d.rectangle([58, 96, 70, 104], fill=(60, 62, 68), outline=(30, 32, 36), width=2)
    d.ellipse([56, 98, 64, 106], fill=(40, 42, 48), outline=(24, 26, 30), width=1)
    # 发动机舱（机身中部两侧隆起）
    d.polygon([(150, 84), (184, 82), (188, 96), (152, 94)], fill=(90, 94, 100), outline=(40, 42, 46), width=2)
    d.polygon([(150, 116), (184, 118), (188, 104), (152, 106)], fill=(90, 94, 100), outline=(40, 42, 46), width=2)
    # ===== 短翼（两侧挂架）=====
    d.polygon([(132, 92), (156, 84), (196, 82), (196, 92), (156, 94), (132, 96)],
              fill=(70, 72, 78), outline=(32, 34, 38), width=2)
    d.polygon([(132, 108), (156, 116), (196, 118), (196, 108), (156, 106), (132, 104)],
              fill=(70, 72, 78), outline=(32, 34, 38), width=2)
    # 火箭巢（翼下：左4右4）
    for rx, dirx in ((122, -1), (200, 1)):
        for i in range(4):
            d.ellipse([rx + dirx * (i * 8) - 4, 88 + (i % 2) * 8, rx + dirx * (i * 8) + 4, 96 + (i % 2) * 8],
                      fill=(190, 76, 46), outline=(100, 38, 22), width=1)
    # 导弹（短翼外端：左右各2枚）
    for mx, dirx in ((118, -1), (206, 1)):
        for j in range(2):
            _ma = mx + dirx * (14 + j * 16)
            d.rectangle([min(_ma, _ma + dirx * 14), 100 + j * 8, max(_ma, _ma + dirx * 14), 106 + j * 8],
                        fill=(98, 102, 108), outline=(44, 46, 50), width=1)
    # ===== 机炮（机腹炮塔：座舱下方）=====
    d.rectangle([104, 106, 132, 112], fill=(54, 56, 62), outline=(26, 28, 32), width=2)
    d.rectangle([78, 108, 104, 112], fill=(48, 50, 56), outline=(24, 26, 30), width=2)
    # ===== 起落架 =====
    d.rectangle([120, 116, 128, 136], fill=(56, 58, 64), width=3)
    d.rectangle([170, 116, 178, 136], fill=(56, 58, 64), width=3)
    d.line([120, 130, 178, 130], fill=(52, 54, 60), width=4)
    # 柔和阴影
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    return img


def main():
    out_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "vehicles"))
    os.makedirs(out_dir, exist_ok=True)
    makers = {"truck": make_truck, "tank": make_tank, "heli": make_heli}
    for vid, fn in makers.items():
        img = fn()
        path = os.path.join(out_dir, f"{vid}.png")
        img.save(path)
        print("saved", path, img.size)


if __name__ == "__main__":
    main()
