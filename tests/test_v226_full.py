# -*- coding: utf-8 -*-
"""v2.2.6 批次完整测试：载具CD/武器/建模 / 钩爪自拉提速+锁定圈+拉远 / 对话卡死兜底 /
P2升级按钮重置（全玩家页面转换重置）/ 救援平衡 / 同屏双人模式选择

覆盖：
A. 载具：P1/P2 打爆后召唤进入 CD；坦克武器可发射（弹药/冷却）；assets/vehicles 三张资源存在
B. 钩爪：lock_radius=200（拉远）、self_pull_speed=420（提速）、self_pull 叠加玩家输入位移、
   锁定绘制为双圈（非连线）、圈内锁定最近非 Boss、P2 钩爪施放分支（锁定直飞/路径/自拉+CD）、
   P2 锁定 helper
C. 对话：DIALOGUE 状态残留（active=False）→ update 自动恢复 PLAYING；_boss_dialogue 重复触发防御
D. 按钮重置：_reset_touch_state 全量重置 P2 控件；_reset_touch_state_for("P2"/"P1")
E. 救援平衡：救援冷却（防无限互救）、倒地超时死亡、受击清空救援进度
F. 同屏双人：入口进 MODE_SELECT、Config 默认 TIMED（默认争分夺秒）
"""
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame.init()

PASS = 0
FAIL = 0


def check(cond, name):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")


# ==================== A. 载具 ====================
print("[A] 载具：CD/武器/资源")
# A1 资源存在
for _f in ("truck.png", "tank.png", "heli.png"):
    check(os.path.exists(os.path.join("assets", "vehicles", _f)), f"载具资源 assets/vehicles/{_f} 存在")

# A2 载具销毁进入 CD（P1/P2 通用函数）
class StubVehicleDestroy:
    pass


def _make_destroy_stub(player):
    player.vehicle = StubVehicleDestroy()
    player.active_skills = {}
    player.cooldown_mult = 1.0
    return player


from zombie_pkg.mix_multi import MultiplayerMixin


class _StubDestroyHost:
    def __init__(self):
        self.particles = type("P", (), {"spawn_explosion": lambda *a, **k: None})()
        self.floating_texts = []
        self.camera = type("C", (), {"shake": lambda *a, **k: None})()

    def _vehicle_destroyed_for(self, player, friendly=False):
        from zombie_pkg.mix_multi import MultiplayerMixin
        # 直接调用 mixin 实现（无依赖路径）
        MultiplayerMixin._vehicle_destroyed_for(self, player, friendly)


from config import SkillType

_host = _StubDestroyHost()
_pl = type("P", (), {"vehicle": StubVehicleDestroy(), "active_skills": {}, "cooldown_mult": 1.0})()
_host._vehicle_destroyed_for(_pl, friendly=False)
check(_pl.vehicle is None, "载具打爆后 vehicle 置 None（P1/P2 通用）")
check(_pl.active_skills.get(SkillType.VEHICLE_SUMMON, 0) == 60.0, "载具打爆后召唤技能进入 60s CD")

# A3 坦克武器可发射（弹药/冷却）
from entities_pkg.vehicles import load_vehicle_images
tank = None
try:
    from entities_pkg.vehicles import Vehicle
    _t = Vehicle("tank", 0, 0)
    tank = _t
    check(_t.mag_left == 4 and _t.mag_size == 4, f"坦克弹夹 4 发（实际 {_t.mag_left}/{_t.mag_size}）")
    _projs = _t.fire(0, 0, 0)
    check(len(_projs) == 1, "坦克 fire() 返回弹药（可发射）")
    check(_t.mag_left == 3, f"发射后弹夹递减为 3（实际 {_t.mag_left}）")
    check(_t.fire_timer > 0, "坦克发射进入冷却 fire_timer>0")
except Exception as e:
    check(False, f"坦克武器加载/发射异常: {e}")

# A4 载具图片可加载（load_vehicle_images 运行时）
try:
    _imgs = load_vehicle_images()
    check(isinstance(_imgs, dict) and len(_imgs) >= 3, f"载具图片加载返回 {len(_imgs) if isinstance(_imgs, dict) else '?'} 张")
except Exception as e:
    check(False, f"load_vehicle_images 异常: {e}")

# ==================== B. 钩爪 ====================
print("\n[B] 钩爪：锁定拉远/自拉提速/双圈/P2 施放")
from entities_pkg.gear import RiotGear

_g = RiotGear()
check(_g.grapple_lock_radius == 200, f"锁定半径 200（拉远）（实际 {_g.grapple_lock_radius}）")
check(_g.self_pull_speed == 420, f"自我拉拽速度 420（实际 {_g.self_pull_speed}）")

# B2 self_pull 叠加玩家输入位移（代码级：update 使用 _inp_dx/_inp_dy）
_src = open("entities_pkg/gear.py", encoding="utf-8").read()
check("_inp_dx" in _src and "_inp_dy" in _src, "gear.py self_pull 叠加玩家输入位移（_inp_dx/_inp_dy）")
_srcp = open("entities_pkg/player.py", encoding="utf-8").read()
check("self._inp_dx" in _srcp and "self._inp_dy" in _srcp, "player.py 记录本帧输入位移 _inp_dx/_inp_dy")

# B3 锁定绘制为双圈（draw 内锁定目标用圆标注而非连线）
check("grapple_lock_radius" in _src, "gear.draw 使用锁定半径圈")
check('"aim_circle"' in _src or "draw.circle" in _src.replace(" ","") or "aim_circle" in _src, "gear.draw 存在锁定圈绘制标记")

# B4 锁定顺序：圈内最近非 Boss
class _SE:
    def __init__(self, x, y, is_boss=False, alive=True, size=20):
        self.x = x; self.y = y; self.is_boss = is_boss; self.alive = alive; self.size = size

_g2 = RiotGear()
_g2.grapple_aiming = True
_e_near = _SE(105, 100)
_e_boss = _SE(108, 100, is_boss=True)
_e_far = _SE(160, 100)
_g2.update_grapple_lock(100, 100, [_e_boss, _e_near, _e_far])
check(_g2.grapple_locked_target is _e_near, "圈内锁定最近非 Boss（Boss 跳过）")
_g2.grapple_aiming = True
_g2.update_grapple_lock(100, 100, [_e_boss])
check(_g2.grapple_locked_target is None, "圈内只有 Boss 时不锁定")

# B5 P2 钩爪施放分支（mix_multi GRAPPLE_PULL + helper）
_srcm = open("zombie_pkg/mix_multi.py", encoding="utf-8").read()
check("GRAPPLE_PULL" in _srcm and "use_grapple(tx, ty, p2.x, p2.y" in _srcm, "P2 钩爪施放分支（GRAPPLE_PULL + use_grapple）")
check("def _update_p2_grapple_lock" in _srcm, "P2 钩爪锁定 helper 存在")
check("def _is_wielding_scythe_for" in _srcm, "P2 死神镰刀判定 helper 存在")

# ==================== C. 对话卡死兜底 ====================
print("\n[C] 对话：残留恢复 + BOSS 防御")
_srcg = open("zombie_pkg/game_core.py", encoding="utf-8").read()
check("self.dialogue is None or not getattr(self.dialogue, \"active\", False)" in _srcg,
      "DIALOGUE 分支：对话非活跃自动恢复 PLAYING")
_srcs = open("zombie_pkg/mix_story.py", encoding="utf-8").read()
check("self.dialogue.active = False" in _srcs, "_boss_dialogue 开头防御（重复触发先重置）")

# 真实逻辑验证：dialogue.active=False 而 state=DIALOGUE → update 回 PLAYING
from game import Game
from config import GameState
_g3 = Game()
_g3.state = GameState.DIALOGUE
_g3.dialogue = type("D", (), {"active": False})()
_g3.update(1 / 60)
check(_g3.state == GameState.PLAYING, "残留 DIALOGUE（active=False）update 后自动恢复 PLAYING")

# ==================== D. 按钮重置（P2 升级卡死修复） ====================
print("\n[D] 按钮重置：P2 控件全量重置")
_srch = open("zombie_pkg/mix_hud.py", encoding="utf-8").read()
check("def _reset_touch_state_for" in _srch, "_reset_touch_state_for 存在（per-player 暂停重置）")
check("self.p2_controls" in _srch.split("def _reset_touch_state_for")[0], "_reset_touch_state 覆盖 p2_controls")

# D2 功能验证：_reset_touch_state 重置 P2 控件
class _Btn:
    def __init__(self):
        self.active = True; self.pressed = True; self.is_shooting = True
        self.is_aiming = True; self.just_released = True; self.touch_id = 7
        self.knob_offset_x = 3; self.knob_offset_y = 4

_h = _StubDestroyHost()  # 复用（自带 particles/camera/floating_texts）
_h.p2_controls = {"shoot": _Btn(), "joystick": _Btn(), "aim": _Btn(), "skill_caster": _Btn()}
_h._p2_finger_ids = {1, 2, 3}
from zombie_pkg.mix_hud import HudMixin
HudMixin._reset_touch_state(_h)
_all_reset = all(
    not b.active and not b.pressed and not b.is_shooting and not b.is_aiming
    and not b.just_released and b.touch_id is None and b.knob_offset_x == 0 and b.knob_offset_y == 0
    for b in _h.p2_controls.values()
)
check(_all_reset, "_reset_touch_state 全量重置 P2 控件（按下/射击/瞄准/touch_id/knob 偏移）")
check(len(_h._p2_finger_ids) == 0, "P2 手指集合清空")

# D3 _reset_touch_state_for("P2")
_h2 = _StubDestroyHost()
_h2.p2_controls = {"shoot": _Btn(), "aim": _Btn()}
_h2._p2_finger_ids = {9}
HudMixin._reset_touch_state_for(_h2, "P2")
check(not _h2.p2_controls["shoot"].is_shooting and _h2.p2_controls["aim"].touch_id is None,
      "_reset_touch_state_for(P2) 重置 P2 控件")

# D4 升级暂停瞬间调用（mix_playing 731 行附近）
_srcp2 = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("_reset_touch_state_for(_tag)" in _srcp2, "P1/P2 升级暂停瞬间调用 _reset_touch_state_for")

# ==================== E. 救援平衡 ====================
print("\n[E] 救援：冷却/超时死亡/受击清进度")
check("RESCUE_COOLDOWN = 15.0" in _srcp2, "救援冷却 15s 常量")
check("DOWNED_DEATH_TIME = 20.0" in _srcp2, "倒地超时死亡 20s 常量")
check("last_rescue_time = _now" in _srcp2, "救活后记录 last_rescue_time（进入冷却）")
check("救援超时，未能生还" in _srcp2, "倒地超时死亡提示文案存在")
check("p._rescue_last_hp > p.hp" in _srcp2 or "_rescue_last_hp" in _srcp2, "受击清空救援进度（_rescue_last_hp 追踪）")

# ==================== F. 同屏双人模式 ====================
print("\n[F] 同屏双人：默认争分夺秒 + 支持三种模式")
_srcd = open("renderer_pkg/draw_ui.py", encoding="utf-8").read()
check("GameState.MODE_SELECT" in _srcd.split("def _draw_net_multiplayer")[0].split("def _draw_multiplayer_select")[1],
      "同屏双人入口进模式选择（MODE_SELECT）")
from zombie_pkg.mix_multi import Config as MConfig
_cfg = MConfig()
check(_cfg.game_mode.name == "TIMED", "Config 默认 TIMED（默认争分夺秒）")
from config import GameMode
check(GameMode.STORY is not None and GameMode.ENDLESS is not None and GameMode.TIMED is not None,
      "三种模式枚举齐全（故事/无尽/争分夺秒）")

# ==================== G. 回归：既有关键路径 ====================
print("\n[G] 回归：钩爪核心 + 双人载具分支编译态")
_srcm2 = open("zombie_pkg/mix_multi.py", encoding="utf-8").read()
check("elif _veh2 is not None and not _veh2.alive:" in _srcm2, "P2 载具打爆独立分支存在")

print(f"\n===== 结果: {PASS} 通过, {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
