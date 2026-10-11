#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.0 程序化生成载具俯视图 PNG（大运重卡 / 99A坦克 / 武装直升机）
输出到 assets/vehicles/*.png，游戏启动时导入（PIL 非游戏运行时依赖）"""
import os

from PIL import Image, ImageDraw


def _rounded_rect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def make_truck():
    """大运重卡：橙红车头+货箱+轮胎"""
    img = Image.new("RGBA", (220, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 货箱
    d.rectangle([30, 25, 170, 105], fill=(150, 90, 40), outline=(90, 50, 20), width=3)
    for i in range(4):
        d.rectangle([40 + i * 34, 33, 60 + i * 34, 97], outline=(110, 65, 30), width=2)
    # 车头
    _rounded_rect(d, [170, 20, 215, 110], 10, fill=(210, 110, 40), outline=(120, 55, 15), width=3)
    d.rectangle([178, 28, 207, 55], fill=(90, 180, 220))  # 挡风玻璃
    d.rectangle([178, 62, 207, 80], fill=(70, 50, 30))   # 进气格栅
    # 车灯
    d.rectangle([207, 30, 214, 44], fill=(255, 230, 100))
    d.rectangle([207, 84, 214, 98], fill=(255, 90, 60))
    # 底盘与轮胎
    d.rectangle([35, 112, 195, 120], fill=(60, 45, 30))
    for tx in (55, 95, 145, 185):
        d.ellipse([tx - 16, 104, tx + 16, 136], fill=(30, 30, 32), outline=(10, 10, 10), width=3)
        d.ellipse([tx - 5, 113, tx + 5, 127], fill=(120, 120, 125))
    return img


def make_tank():
    """99A坦克：橄榄绿车身+炮塔+主炮"""
    img = Image.new("RGBA", (240, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 履带
    d.rounded_rectangle([18, 120, 222, 158], 18, fill=(40, 48, 38), outline=(15, 18, 14), width=4)
    for i in range(7):
        wx = 34 + i * 30
        d.ellipse([wx - 12, 126, wx + 12, 152], fill=(70, 80, 66), outline=(20, 24, 18), width=3)
        d.ellipse([wx - 4, 134, wx + 4, 144], fill=(140, 150, 135))
    # 车体
    d.rounded_rectangle([30, 55, 210, 122], 8, fill=(80, 105, 70), outline=(35, 50, 30), width=3)
    d.rectangle([30, 95, 210, 118], fill=(60, 82, 55))
    # 炮塔
    d.rounded_rectangle([70, 28, 175, 70], 12, fill=(90, 118, 78), outline=(35, 50, 30), width=3)
    d.ellipse([135, 30, 168, 63], fill=(110, 140, 95), outline=(35, 50, 30), width=2)
    # 主炮
    d.rectangle([175, 38, 235, 50], fill=(70, 92, 62), outline=(30, 42, 26), width=2)
    d.rectangle([205, 33, 232, 55], fill=(55, 72, 50))
    d.rectangle([222, 36, 238, 52], fill=(40, 54, 38))  # 炮口制退器
    # 天线与舱盖
    d.rectangle([92, 12, 100, 30], fill=(120, 150, 105))
    d.ellipse([100, 40, 120, 60], fill=(105, 135, 90), outline=(35, 50, 30), width=2)
    return img


def make_heli():
    """武装直升机：深灰机身+尾梁+旋翼+机炮/火箭巢"""
    img = Image.new("RGBA", (260, 180), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 主旋翼
    d.rectangle([30, 62, 230, 72], fill=(70, 72, 76), outline=(30, 30, 34), width=2)
    d.rectangle([125, 22, 135, 118], fill=(90, 92, 98))
    d.ellipse([115, 58, 145, 86], fill=(40, 42, 46))
    # 机身
    d.rounded_rectangle([55, 48, 170, 116], 24, fill=(95, 98, 104), outline=(40, 42, 46), width=3)
    d.rounded_rectangle([60, 55, 165, 110], 20, fill=(105, 108, 114))
    d.rounded_rectangle([95, 60, 140, 82], 10, fill=(120, 200, 230), outline=(60, 70, 90), width=2)  # 座舱
    # 尾梁与尾桨
    d.rectangle([165, 70, 235, 94], fill=(85, 88, 94), outline=(40, 42, 46), width=2)
    d.rectangle([232, 62, 242, 102], fill=(60, 62, 68), outline=(25, 25, 28), width=2)
    # 短翼挂架（火箭巢）
    d.rectangle([80, 116, 120, 128], fill=(60, 62, 68), outline=(25, 25, 28), width=2)
    d.rectangle([140, 116, 180, 128], fill=(60, 62, 68), outline=(25, 25, 28), width=2)
    for i in range(3):
        d.ellipse([84 + i * 12, 118, 94 + i * 12, 126], fill=(200, 80, 40))
        d.ellipse([144 + i * 12, 118, 154 + i * 12, 126], fill=(200, 80, 40))
    # 机炮（腹下）
    d.rectangle([95, 128, 170, 134], fill=(55, 57, 62), outline=(20, 20, 24), width=2)
    d.rectangle([160, 122, 176, 140], fill=(45, 47, 52))
    # 起落架
    d.rectangle([70, 138, 78, 158], fill=(60, 62, 68), width=2)
    d.rectangle([148, 138, 156, 158], fill=(60, 62, 68), width=2)
    return img


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "vehicles")
    out_dir = os.path.normpath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    makers = {"truck": make_truck, "tank": make_tank, "heli": make_heli}
    for vid, fn in makers.items():
        img = fn()
        path = os.path.join(out_dir, f"{vid}.png")
        img.save(path)
        print("saved", path, img.size)


if __name__ == "__main__":
    main()
