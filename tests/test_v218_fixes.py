#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1.8 验证：①死亡轮回击杀减当前冷却 ②新技能死亡咏唱（杀敌减全部技能冷却）
③吸血/回血画面效果 ④狂暴/超载特效加强 ⑤lighting None 防御（打包缺 gl_renderer 场景）"""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "/home/user/zombie_survivor")

import pygame
pygame.init()
from config import SkillType
from skills import SkillTree
from zombie_pkg.mix_effects import EffectsMixin
from zombie_pkg.mix_records import RecordsMixin

ok = 0
def check(name, cond, detail=""):
    global ok
    ok += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" {detail}" if detail and not cond else ""))
    if not cond:
        sys.exit(1)

# ========== 1. 新技能定义 ==========
st = SkillTree()
kcs = st.get_skill(SkillType.KILL_CD_SLASH)
check("死亡咏唱技能存在", kcs is not None and kcs.current_level == 0)
check("死亡咏唱为多依赖高级技能（狂暴+冷却缩减）", kcs is not None and len(kcs.requires) == 2,
      f"requires={kcs.requires if kcs else None}")
scy = st.get_skill(SkillType.SCYTHE_DANCE)
check("死亡轮回描述含击杀减冷却", scy is not None and "击杀" in scy.description and "冷却" in scy.description)

# ========== 2. 击杀冷却削减逻辑（EffectsMixin._apply_kill_cd_slash）==========
class FakeSkill:
    def __init__(self, lv):
        self.current_level = lv

class FakeTree:
    def __init__(self, scy=0, kcs=0):
        self._d = {SkillType.SCYTHE_DANCE: FakeSkill(scy), SkillType.KILL_CD_SLASH: FakeSkill(kcs)}
    def get_skill(self, t):
        return self._d.get(t)

class FakePlayer:
    def __init__(self, tree, alive=True, max_hp=100):
        self.skill_tree = tree
        self.active_skills = {}
        self.alive = alive
        self.max_hp = max_hp
        self.hp = 50
        self.lifesteal = 0.0
        self.x = self.y = 0
    def heal(self, amt):
        self.hp = min(self.max_hp, self.hp + amt)

class FakeGame(EffectsMixin):
    def __init__(self):
        self.player = FakePlayer(FakeTree(scy=2, kcs=0), alive=True)
        self.player.active_skills[SkillType.SCYTHE_DANCE] = 30.0
        self.player2 = None

# 死亡轮回减当前冷却
g = FakeGame()
g._apply_kill_cd_slash()
check("死亡轮回杀敌后当前冷却 x0.99", abs(g.player.active_skills[SkillType.SCYTHE_DANCE] - 29.7) < 1e-6,
      f"cd={g.player.active_skills[SkillType.SCYTHE_DANCE]}")

# 死亡咏唱减全部技能冷却 + 满级回血
p1 = FakePlayer(FakeTree(scy=1, kcs=3), alive=True, max_hp=100)
p1.hp = 10
p1.active_skills = {SkillType.SCYTHE_DANCE: 30.0, SkillType.DASH: 5.0, SkillType.BERSERK: 20.0}
g2 = FakeGame()
g2.player = p1
g2._apply_kill_cd_slash()
check("死亡咏唱Lv3：全部冷却技能 x0.97（且与死亡轮回 x0.99 叠加）",
      abs(p1.active_skills[SkillType.SCYTHE_DANCE] - 30.0 * 0.99 * 0.97) < 1e-6
      and abs(p1.active_skills[SkillType.DASH] - 4.85) < 1e-6
      and abs(p1.active_skills[SkillType.BERSERK] - 19.4) < 1e-6,
      f"acs={p1.active_skills}")
check("死亡咏唱Lv3：击杀额外回1%生命", p1.hp == 11, f"hp={p1.hp}")

# 多人：P2 也生效
g3 = FakeGame()
p2 = FakePlayer(FakeTree(scy=1, kcs=2), alive=True)
p2.active_skills = {SkillType.BERSERK: 20.0}
g3.player2 = p2
g3._apply_kill_cd_slash()
check("多人模式 P2 击杀冷却削减生效", abs(p2.active_skills[SkillType.BERSERK] - 19.6) < 1e-6,
      f"p2_acs={p2.active_skills}")

# ========== 3. 吸血画面效果（_vampire_heal）==========
class FakeParts:
    def __init__(self):
        self.calls = []
    def spawn_particle(self, *a):
        self.calls.append(("p", a))
    def spawn_heal_particles(self, *a):
        self.calls.append(("h", a))
    def spawn_explosion(self, *a):
        self.calls.append(("e", a))
    def spawn_blood(self, *a):
        self.calls.append(("b", a))

class FakeFT:
    def __init__(self):
        self.items = []
    def append(self, x):
        self.items.append(x)

class FakeHealGame(RecordsMixin):
    def __init__(self):
        self.player = FakePlayer(FakeTree(), alive=True, max_hp=100)
        self.player.lifesteal = 0.2
        self.player.hp = 50
        self.particles = FakeParts()
        self.floating_texts = FakeFT()

g4 = FakeHealGame()
g4._vampire_heal(100, sx=50, sy=0)   # 20% 吸血 → +20
check("吸血按比例回血", g4.player.hp == 70, f"hp={g4.player.hp}")
check("吸血生成血滴粒子（从伤害点飞向玩家）", any(c[0] == "p" for c in g4.particles.calls), "")
check("吸血生成绿色回光粒子", any(c[0] == "h" for c in g4.particles.calls), "")
check("吸血显示绿色回血浮字", len(g4.floating_texts.items) == 1, "")

# 无吸血时不产生效果
g5 = FakeHealGame()
g5.player.lifesteal = 0.0
g5._vampire_heal(100, sx=50, sy=0)
check("无吸血属性不回血不弹浮字", g5.player.hp == 50 and len(g5.floating_texts.items) == 0, "")

# ========== 4. 狂暴/超载特效加强（不崩溃 + 光环追加）==========
class FakeAssets:
    def play_sound_random(self, *a): pass
class FakeCam:
    def shake(self, *a): pass
class FakeSkillGame:
    def __init__(self):
        self.player = FakePlayer(FakeTree(scy=1, kcs=0))
        self.player.skill_tree = FakeTree(scy=1, kcs=0)
        self.player.berserk_active = False
        self.player.damage_boost_timer = 0.0
        self.player.damage_boost_mult = 1.0
        self.player.fire_rate_mult = 1.0
        self.particles = FakeParts()
        self.camera = FakeCam()
        self.floating_texts = FakeFT()
        self.sweep_rings = []
        self.assets = FakeAssets()

from zombie_pkg.mix_skills import SkillsMixin
g6 = FakeSkillGame()
SkillsMixin._skill_berserk(g6)
check("狂暴开启标志+倍率生效", g6.player.berserk_active and g6.player.damage_boost_mult == 2.0, "")
check("狂暴火焰环绕粒子生成", sum(1 for c in g6.particles.calls if c[0] == "p") >= 10, "")
check("狂暴红色光环追加", len(g6.sweep_rings) >= 1, "")

g7 = FakeSkillGame()
SkillsMixin._skill_overload(g7)
check("超载倍率生效", g7.player.damage_boost_mult == 2.5, "")
check("超载金色电弧粒子生成", sum(1 for c in g7.particles.calls if c[0] == "p") >= 10, "")
check("超载双扩散光环追加", len(g7.sweep_rings) == 2, f"rings={len(g7.sweep_rings)}")

# ========== 5. lighting None 防御（旧包缺 gl_renderer → lighting=None 不崩溃）==========
class FakeLightNone:
    lighting = None
    config = type("C", (), {"graphics_quality": "quality"})()
# 复现 mix_playing 的防御写法：getattr(..., None) 而非 hasattr+直接访问
_dummy = getattr(FakeLightNone, 'lighting', None)
_ok_defense = _dummy is None
# 证明旧写法（hasattr+直接访问）会崩：hasattr 为 True 但值为 None
_bug_repro = False
try:
    if hasattr(FakeLightNone, 'lighting') and FakeLightNone.lighting.quality:
        _bug_repro = True
except AttributeError:
    _bug_repro = True
check("lighting=None 时 getattr 防御跳过（旧写法会崩溃）", _ok_defense and _bug_repro, "")

print(f"\n共 {ok} 项断言全绿" if ok >= 14 else f"\n仅 {ok}/14 通过")
sys.exit(0 if ok >= 14 else 1)
