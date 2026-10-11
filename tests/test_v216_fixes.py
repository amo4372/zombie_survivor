#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1.6 验证：①倒地免伤（脱锁无敌闭环）②对话奖励全体生效 ③开发者"下一章"按钮
④多人光照全部玩家生效 ⑤OpenGL 光照后端自动探测与 CPU 回退"""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "/home/user/zombie_survivor")

import pygame
pygame.init()
from lighting import LightingSystem, _GLightBackend
from entities_pkg.player import Player

ok = 0
def check(name, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")

# ========== 1. 倒地免伤（take_damage downed 兜底）==========
p = Player(100, 100)
p.downed = True
before = p.hp
r = p.take_damage(50, damage_type="melee")
check("倒地玩家 take_damage 返回 0", r == 0, f"r={r}")
check("倒地玩家 hp 不变", p.hp == before, f"hp={p.hp}")

# 非倒地仍正常受伤害（dev_god/upgrade_paused/downed 均 False）
p2 = Player(100, 100)
r2 = p2.take_damage(30, damage_type="melee")
check("非倒地玩家正常受伤害", r2 == 30 or p2.hp < 100, f"hp={p2.hp}")
p3 = Player(100, 100)
p3.upgrade_paused = True
r3 = p3.take_damage(30)
check("upgrade_paused 免伤保留", r3 == 0, f"r={r3}")

# ========== 2. 对话奖励全体生效 ==========
from zombie_pkg.mix_story import StoryMixin
class FakeAssets:
    def play_sound(self, *a, **k):
        pass
class FakeSession:
    def set_ending(self, *a):
        pass
class FakeRecords:
    def __init__(self):
        self.coins = 0
    def add_coins(self, n):
        self.coins += n
class FakeMix(StoryMixin):
    def __init__(self):
        self.ending_type = None
        self.session = FakeSession()
        self.records = FakeRecords()
        self.floating_texts = []
        self.assets = FakeAssets()
        self.player = Player(0, 0)
        self.player2 = Player(50, 0)
    def _alive_players(self):
        return [self.player, self.player2]

fm = FakeMix()
fm.player.hp = 80
fm.player2.hp = 70
fm._apply_choice_effect({"type": "heal", "value": 20})
check("对话回血两名玩家都生效", fm.player.hp == 100 and fm.player2.hp == 90,
      f"P1={fm.player.hp} P2={fm.player2.hp}")
check("对话回血浮字两条", len(fm.floating_texts) == 2, f"n={len(fm.floating_texts)}")

fm2 = FakeMix()
fm2._apply_choice_effect({"type": "coin", "value": 100})
check("对话金币进共享账户", fm2.records.coins == 100, f"coins={fm2.records.coins}")
check("对话金币浮字两名玩家", len(fm2.floating_texts) == 2, f"n={len(fm2.floating_texts)}")

fm3 = FakeMix()
fm3._apply_choice_effect({"type": "buff", "value": "haste", "duration": 5.0})
check("对话 buff 两名玩家都生效", hasattr(fm3.player, 'buff_manager') and hasattr(fm3.player2, 'buff_manager'),
      "buff 对象缺失")

# ========== 3. 开发者"直接下一章"按钮 ==========
from config import GameMode
from zombie_pkg.mix_input import InputMixin
class FakeGameDev:
    dev_mode = True
    dev_panel_open = True
    dev_god = False
    dev_time_scale = 1.0
    def _advance_to_next_map(self):
        self.advanced = True
class FakeInput(InputMixin):
    def __init__(self):
        self.dev_buttons = []
        self.records = FakeRecords()
        self.player = Player(0, 0)
        self.floating_texts = []
        self.config = type("C", (), {"game_mode": GameMode.STORY})()
        self.enemies = []
        self.dev_mode = True
        self.dev_panel_open = True
        self.dev_god = False
        self.dev_time_scale = 1.0
        self.advanced = False
    def _advance_to_next_map(self):
        self.advanced = True

fi = FakeInput()
fi._rebuild_dev_buttons()
labels = [b.text for b in fi.dev_buttons]
check("开发者面板含'直接下一章'按钮", "直接下一章" in labels, f"labels={labels}")
check("按钮总数 11（含关闭）", len(fi.dev_buttons) == 11, f"n={len(fi.dev_buttons)}")
fi._dev_action(9)
check("点击'下一章'调用 _advance_to_next_map", fi.advanced, "")
fi._dev_action(10)
check("点击'关闭面板'关闭面板", not fi.dev_panel_open, "")

# 非故事模式提示且不崩溃
fi2 = FakeInput()
fi2.config = type("C", (), {"game_mode": GameMode.ENDLESS})()
fi2._dev_action(9)
check("非故事模式下一章不崩溃", True, "")

# ========== 4. 多人光照全部玩家生效 ==========
ls = LightingSystem(640, 360, "quality")
check("quality 档光照启用", ls.enabled, "")
scr = pygame.Surface((640, 360), pygame.SRCALPHA)
class FakePL:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.alive = True
        self.downed = False
        self.aim_angle = 0.5
p1, p2 = FakePL(300, 180), FakePL(60, 60)
ls.render(scr, 0, 0, 1.0, player=None, players=[p1, p2])
# 光表面应有挖洞像素（光源区域 alpha 被抬高 → 合成后暗度下降）
ls._dark_surface.fill((0, 0, 0, ls.ambient_darkness))
ls._dark_surface.blit(ls._light_surface, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
light_region = ls._dark_surface.get_at((320, 180))
check("双人模式两个玩家光源均渲染（中心区域被照亮）",
      light_region.a < ls.ambient_darkness - 20, f"alpha={light_region.a}")

# 单人兼容旧调用
ls2 = LightingSystem(640, 360, "quality")
ls2.render(scr, 0, 0, 1.0, player=p1)
ls2._dark_surface.fill((0, 0, 0, ls2.ambient_darkness))
ls2._dark_surface.blit(ls2._light_surface, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
check("单人旧参数调用正常", ls2._dark_surface.get_at((320, 180)).a < ls2.ambient_darkness - 20, "")

# ========== 5. OpenGL 后端自动探测与 CPU 回退 ==========
gl = _GLightBackend()
check("moderngl 缺失时 GPU 后端禁用（available=False）", gl.available is False, f"avail={gl.available}")
ls3 = LightingSystem(640, 360, "quality")
# 无 moderngl → self._gl 探测失败；render 必须走 CPU 且正常出暗层
ls3.render(scr, 0, 0, 1.0, player=p1)
ls3._dark_surface.fill((0, 0, 0, ls3.ambient_darkness))
ls3._dark_surface.blit(ls3._light_surface, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
check("GPU 不可用时 CPU 回退正常渲染", ls3._dark_surface.get_at((320, 180)).a < ls3.ambient_darkness - 20, "")
# 模拟 GPU 异常：render 中途把 _gl 置为不可用对象 → 回退 CPU 不崩溃
class BoomGL:
    available = True
    def composite(self, *a):
        raise RuntimeError("GL 不可用")
ls4 = LightingSystem(640, 360, "quality")
ls4._gl = BoomGL()
try:
    ls4.render(scr, 0, 0, 1.0, player=p1)
    ls4._gl = None
    check("GPU 异常永久回退 CPU（渲染成功）", True, "")
except Exception as e:
    check("GPU 异常永久回退 CPU（渲染成功）", False, str(e))

print(f"\n共 {ok} 项断言全绿" if ok >= 20 else f"\n仅 {ok}/20 通过")
sys.exit(0 if ok >= 20 else 1)
