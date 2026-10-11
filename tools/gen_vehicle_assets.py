#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.3 程序化生成载具俯视图 PNG（参考真实外观，俯视视角）
- 大运重卡：网上流行经典款——红色车头+红色货箱（平头卡车，前脸红、驾驶室挡风、货箱带竖条纹）
- 99A主战坦克：楔形炮塔、长身管125滑膛炮、首上倾斜装甲、侧裙板、6对负重轮、尾部储物篮
- 武装直升机（直-10/阿帕奇风格）：流线机身、主旋翼+尾桨、短翼挂载火箭巢/导弹、机炮、尾梁
输出到 assets/vehicles/*.png，游戏启动时导入（PIL 非游戏运行时依赖）
"""
import os

from PIL import Image, ImageDraw, ImageFilter


def _rr(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def make_truck():
    """大运重卡（红色经典款）：平头驾驶室+红色货箱+底盘+10轮"""
    img = Image.new("RGBA", (240, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 底盘纵梁
    d.rectangle([20, 116, 224, 126], fill=(52, 46, 42), outline=(20, 18, 16), width=2)
    # 轮胎（前2+后6，双轴双胎）
    for tx in (34, 66, 118, 148, 178, 208):
        d.ellipse([tx - 18, 100, tx + 18, 140], fill=(24, 24, 28), outline=(8, 8, 10), width=3)
        d.ellipse([tx - 5, 112, tx + 5, 128], fill=(90, 92, 100))
    # 货箱（红色，带竖纹）
    d.rectangle([24, 30, 172, 112], fill=(196, 30, 26), outline=(120, 14, 12), width=3)
    for i in range(5):
        x0 = 34 + i * 29
        d.rectangle([x0, 34, x0 + 3, 108], fill=(230, 40, 34))
        d.rectangle([x0 + 8, 34, x0 + 11, 108], fill=(170, 22, 20))
    # 货箱顶部横梁
    d.rectangle([24, 30, 172, 38], fill=(226, 36, 32), outline=(120, 14, 12), width=2)
    # 驾驶室（红色平头）
    _rr(d, [170, 14, 224, 116], 12, fill=(206, 34, 28), outline=(120, 14, 12), width=3)
    # 前挡风玻璃（两块）
    d.rectangle([174, 26, 219, 52], fill=(84, 168, 208), outline=(40, 70, 100), width=2)
    d.rectangle([198, 26, 219, 52], fill=(100, 182, 220), outline=(40, 70, 100), width=2)
    # 雨刷
    d.line([190, 30, 198, 52], fill=(20, 30, 40), width=3)
    # 前脸进气格栅
    d.rectangle([174, 66, 219, 82], fill=(120, 20, 18), outline=(80, 10, 8), width=2)
    for gx in range(178, 220, 9):
        d.line([gx, 68, gx, 80], fill=(60, 8, 8), width=2)
    # 大灯（红色款经典：车头两侧）
    d.rectangle([218, 58, 224, 72], fill=(255, 238, 150), outline=(160, 130, 40), width=2)
    d.rectangle([218, 84, 224, 98], fill=(255, 240, 160), outline=(160, 130, 40), width=2)
    # 保险杠
    _rr(d, [168, 102, 226, 116], 6, fill=(60, 54, 50), outline=(25, 22, 20), width=2)
    # 驾驶室顶部空调/气喇叭
    _rr(d, [182, 6, 206, 18], 4, fill=(150, 30, 26), outline=(90, 14, 12), width=2)
    d.rectangle([176, 10, 182, 16], fill=(60, 50, 46), width=2)  # 气喇叭
    d.rectangle([206, 12, 212, 18], fill=(60, 50, 46), width=2)
    # 货箱后部尾灯
    d.rectangle([20, 60, 24, 76], fill=(255, 200, 60), outline=(150, 110, 30), width=2)
    d.rectangle([20, 82, 24, 96], fill=(255, 60, 50), outline=(150, 30, 24), width=2)
    # 阴影
    return img.filter(ImageFilter.GaussianBlur(0.4)) if False else img


def make_tank():
    """99A主战坦克（俯视）：楔形炮塔+长管125滑膛炮+首上倾斜装甲+侧裙+6负重轮"""
    img = Image.new("RGBA", (270, 190), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 履带（左右两侧，带履带板纹）
    for side, (x0, x1) in (("L", (24, 116)), ("R", (152, 244))):
        d.rounded_rectangle([x0, 132, x1, 172], 20, fill=(52, 58, 48), outline=(22, 26, 20), width=4)
        for i in range(7):
            wx = x0 + 16 + i * 20
            d.ellipse([wx - 10, 136, wx + 10, 168], fill=(78, 86, 70), outline=(26, 30, 24), width=3)
            d.ellipse([wx - 3, 144, wx + 3, 156], fill=(150, 158, 140))
        for i in range(8):
            lx = x0 + 6 + i * 16
            d.line([lx, 134, lx + 6, 134], fill=(40, 46, 36), width=3)
            d.line([lx, 168, lx + 6, 168], fill=(40, 46, 36), width=3)
    # 车体（首上倾斜+首下，前窄后宽梯形）
    d.polygon([(58, 66), (214, 66), (228, 134), (44, 134)], fill=(88, 112, 74), outline=(40, 54, 32), width=3)
    # 车体顶面细节：炮塔座圈、首上装甲线
    d.polygon([(60, 70), (210, 70), (222, 130), (50, 130)], fill=(96, 122, 80))
    d.line([(52, 128), (220, 128)], fill=(40, 54, 32), width=2)
    # 侧裙板（两侧）
    d.rectangle([24, 128, 118, 138], fill=(70, 92, 60), outline=(40, 54, 32), width=2)
    d.rectangle([152, 128, 246, 138], fill=(70, 92, 60), outline=(40, 54, 32), width=2)
    # 炮塔（99A 楔形：前部倾斜、后部方形弹药架舱）
    d.polygon([(78, 40), (200, 40), (216, 100), (196, 118), (84, 118), (66, 100)],
              fill=(104, 132, 88), outline=(40, 54, 32), width=3)
    # 炮塔顶部细节：舱盖/观瞄
    d.ellipse([118, 66, 148, 96], fill=(116, 146, 98), outline=(50, 64, 40), width=2)
    d.ellipse([124, 72, 142, 90], fill=(132, 162, 112), outline=(50, 64, 40), width=2)
    d.rectangle([96, 52, 108, 70], fill=(120, 150, 102), outline=(50, 64, 40), width=2)  # 车长观瞄
    d.rectangle([186, 96, 210, 118], fill=(92, 118, 78), outline=(40, 54, 32), width=2)  # 尾部储物篮
    # 主炮（长身管125滑膛炮，炮口制退器+热护套）
    d.rectangle([216, 66, 264, 82], fill=(74, 96, 62), outline=(36, 48, 30), width=2)
    d.rectangle([240, 64, 264, 84], fill=(60, 78, 50))
    d.rectangle([258, 60, 266, 88], fill=(40, 54, 38), outline=(24, 32, 22), width=2)  # 炮口制退器
    # 车体侧工具箱/储物
    d.rectangle([48, 108, 96, 122], fill=(84, 108, 70), outline=(40, 54, 32), width=2)
    d.rectangle([174, 108, 222, 122], fill=(84, 108, 70), outline=(40, 54, 32), width=2)
    # 天线
    d.line([96, 14, 96, 44], fill=(130, 156, 108), width=3)
    return img


def make_heli():
    """武装直升机（直-10/阿帕奇风格俯视）：流线机身+主旋翼+尾桨+短翼挂载+机炮"""
    img = Image.new("RGBA", (290, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 主旋翼（细长桨叶，双叶）
    d.rectangle([30, 58, 262, 64], fill=(58, 60, 64), outline=(28, 30, 32), width=2)
    d.rectangle([30, 70, 262, 76], fill=(58, 60, 64), outline=(28, 30, 32), width=2)
    d.ellipse([128, 56, 164, 78], fill=(40, 42, 46), outline=(22, 24, 26), width=3)  # 桨毂
    # 机身（流线型：前窄后收）
    d.polygon([(62, 62), (152, 52), (196, 56), (226, 74), (226, 84), (196, 102), (152, 106), (62, 96)],
              fill=(104, 108, 114), outline=(46, 48, 52), width=3)
    d.polygon([(70, 66), (150, 58), (192, 62), (218, 76), (218, 82), (192, 96), (150, 100), (70, 92)],
              fill=(118, 122, 128))
    # 座舱（气泡式风挡+顶窗）
    d.ellipse([86, 62, 136, 92], fill=(130, 208, 236), outline=(50, 76, 96), width=2)
    d.ellipse([96, 68, 126, 86], fill=(150, 222, 246), outline=(60, 90, 110), width=2)
    # 发动机进气道（机身两侧）
    d.polygon([(150, 56), (176, 54), (178, 70), (152, 68)], fill=(88, 92, 98), outline=(40, 42, 46), width=2)
    d.polygon([(150, 102), (176, 104), (178, 88), (152, 90)], fill=(88, 92, 98), outline=(40, 42, 46), width=2)
    # 短翼（挂载火箭巢+导弹）
    for sy in (62, 78):
        d.polygon([(128, sy), (150, sy - 6), (176, sy - 4), (176, sy + 4), (150, sy + 6), (128, sy)],
                  fill=(70, 72, 78), outline=(32, 34, 38), width=2)
    # 火箭巢（左4发右4发）
    for rx, dirx in ((120, -1), (176, 1)):
        for i in range(4):
            d.ellipse([rx + dirx * (i * 7) - 3, 66 + (i % 2) * 8, rx + dirx * (i * 7) + 3, 74 + (i % 2) * 8],
                      fill=(188, 74, 44), outline=(100, 36, 20), width=1)
    # 导弹（短翼外挂2枚）
    for mx, dirx in ((118, -1), (178, 1)):
        _ma, _mb = mx + dirx * 16, mx + dirx * 30
        d.rectangle([min(_ma, _mb), 72, max(_ma, _mb), 78], fill=(96, 100, 106), outline=(44, 46, 50), width=1)
    # 尾梁
    d.rectangle([226, 70, 268, 88], fill=(92, 96, 102), outline=(44, 46, 50), width=2)
    d.rectangle([236, 64, 268, 94], fill=(102, 106, 112), outline=(44, 46, 50), width=2)
    # 尾桨（垂直尾翼+桨叶）
    d.rectangle([262, 48, 270, 110], fill=(64, 66, 72), outline=(30, 32, 36), width=2)
    d.rectangle([270, 60, 286, 68], fill=(56, 58, 62), outline=(26, 28, 32), width=2)
    d.rectangle([270, 90, 286, 98], fill=(56, 58, 62), outline=(26, 28, 32), width=2)
    # 机炮（机腹前下方，俯视可见于座舱下方）
    d.rectangle([74, 92, 130, 100], fill=(56, 58, 64), outline=(28, 30, 34), width=2)
    d.rectangle([92, 88, 130, 104], fill=(48, 50, 56), outline=(24, 26, 30), width=2)
    # 起落架
    d.rectangle([90, 104, 98, 122], fill=(56, 58, 64), width=3)
    d.rectangle([168, 104, 176, 122], fill=(56, 58, 64), width=3)
    d.line([90, 118, 176, 118], fill=(52, 54, 60), width=4)  # 起落架横梁
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
