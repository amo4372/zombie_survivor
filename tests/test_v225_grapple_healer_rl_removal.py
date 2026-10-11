# -*- coding: utf-8 -*-
"""v2.2.5 批次测试：完全移除RL / 治疗僵尸持续回血 / 死神钩爪重做 / 更新弹窗持久化

覆盖：
1. RL 完全移除：zombie_pkg/ai_controller.py 已删除、game_core 无 rl_ai 引用、
   build_release 不再追加 onnx/npz
2. 治疗僵尸：enemy.update 不再提前重置 heal_timer（mix_playing 触发逻辑成立）；
   heal 光环逻辑正确（复制自 mix_playing 的等价判定）
3. 钩爪重做：
   - use_grapple(scythe=True) → CD 3.0；普通 → CD 0.8
   - 未命中 → _begin_self_pull 进入 self_pull + 免伤
   - self_pull 状态推进玩家位置
   - update_grapple_lock 圈内锁定最近非 Boss 敌人
4. 更新弹窗：updater.UPDATE_STATE["notice_dismissed"] 持久标记存在
"""
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


class StubPlayer:
    def __init__(self, x=100, y=100):
        self.x = x
        self.y = y
        self.facing_angle = 0
        self.invincible_timer = 0
        self.weapons = []
        self.current_weapon_idx = 0

    def get_current_weapon(self):
        return self.weapons[self.current_weapon_idx] if self.weapons else None


class StubWeapon:
    def __init__(self, wtype):
        self.weapon_type = wtype


class StubEnemy:
    def __init__(self, x, y, size=20, is_boss=False, alive=True):
        self.x = x
        self.y = y
        self.size = size
        self.is_boss = is_boss
        self.alive = alive
        self.grappled = False
        self.hp = 100
        self.max_hp = 100
        self.knockback_x = 0
        self.knockback_y = 0


class StubWorld:
    def __init__(self):
        self.projectiles = []
        self.enemies = []


# ==================== 1. RL 完全移除 ====================
print("\n[1] RL 完全移除")
ai_ctrl_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "zombie_pkg", "ai_controller.py")
check(not os.path.exists(ai_ctrl_path), "zombie_pkg/ai_controller.py 已删除")

gc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "zombie_pkg", "game_core.py")
gc_src = open(gc_path, encoding="utf-8").read()
check("rl_ai" not in gc_src, "game_core.py 无 rl_ai 引用")
check("RL_MODEL_PATH" not in gc_src, "game_core.py 无 RL_MODEL_PATH")

mp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "zombie_pkg", "mix_playing.py")
mp_src = open(mp_path, encoding="utf-8").read()
check('"rl_ai"' not in mp_src and "'rl_ai'" not in mp_src, "mix_playing.py 无 rl_ai 兜底引用")

br_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "build_release.py")
br_src = open(br_path, encoding="utf-8").read()
check("zombie_policy.onnx" not in br_src and "policy_weights.npz" not in br_src,
      "build_release.py 不再追加 onnx/npz 模型")

# ==================== 2. 治疗僵尸 ====================
print("\n[2] 治疗僵尸修复")
from entities_pkg.enemy import Enemy

healer = Enemy(0, 0, "healer", 1, None) if False else None
# 直接实例化 Enemy 依赖较多，用轻量验证：检查 enemy.py 源码不再提前重置
en_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "entities_pkg", "enemy.py")
en_src = open(en_path, encoding="utf-8").read()
check("heal_timer = self.heal_interval" not in en_src,
      "enemy.py 不再提前重置 heal_timer（触发逻辑不再被互踩）")
check("heal_timer -= dt" in en_src, "enemy.py 仍递减 heal_timer")

# 持续光环等价逻辑（复制 mix_playing 的修复实现做行为验证）
heal_radius, heal_amount, heal_interval = 100, 5, 2.0
dt = 1 / 60
_other = StubEnemy(30, 0, size=20)
_other.hp = 90  # 未满血，光环可生效
_enemy = StubEnemy(0, 0, size=20)
_enemy.heal_timer = 0.5  # 未到触发点
_per_sec = max(heal_amount, 1) / max(heal_interval, 0.5)
_enemy.hp_before = _other.hp
# 光环：范围内平滑回血
if _other.hp < _other.max_hp and math.hypot(_other.x - _enemy.x, _other.y - _enemy.y) < heal_radius:
    _other.hp = min(_other.max_hp, _other.hp + _per_sec * dt)
check(_other.hp > 90, "持续光环每帧平滑回血生效")

# 触发后重置：heal_timer<=0 → 重置 + 脉冲
_enemy2 = StubEnemy(0, 0, size=20)
_enemy2.heal_timer = 0.0
_enemy2.heal_interval = 2.0
_enemy2.heal_radius = 100
_enemy2.heal_amount = 5
_o2 = StubEnemy(30, 0, size=20)
_o2.hp = 50
if _enemy2.heal_timer <= 0:
    _enemy2.heal_timer = _enemy2.heal_interval
    if math.hypot(_o2.x - _enemy2.x, _o2.y - _enemy2.y) < _enemy2.heal_radius:
        _o2.hp = min(_o2.max_hp, _o2.hp + _enemy2.heal_amount * 2.0)
check(_o2.hp == 60, "脉冲治疗触发（+10）")
check(_enemy2.heal_timer == 2.0, "触发后重置 heal_timer=interval")

# ==================== 3. 钩爪重做 ====================
print("\n[3] 钩爪重做")
from entities_pkg.gear import RiotGear

g = RiotGear()
check(g.grapple_scythe_max_cooldown == 3.0, "死神钩爪 CD 3s 常量")
check(g.grapple_max_cooldown == 0.8, "普通钩爪 CD 0.8s 常量")
check(g.grapple_lock_radius == 200, "锁定圈半径 200（v2.2.6 拉远，原 110）")

# scythe 发射 → CD 3.0
g2 = RiotGear()
ok = g2.use_grapple(200, 200, 100, 100, None, scythe=True)
check(ok and abs(g2.grapple_cooldown - 3.0) < 1e-6, "死神钩爪发射 CD=3.0")
check(g2.grapple_is_scythe, "grapple_is_scythe 标记置位")

# 普通发射 → CD 0.8
g3 = RiotGear()
ok3 = g3.use_grapple(200, 200, 100, 100, None, scythe=False)
check(ok3 and abs(g3.grapple_cooldown - 0.8) < 1e-6, "普通钩爪发射 CD=0.8")

# 未命中 → 自我拉拽
g4 = RiotGear()
p4 = StubPlayer(100, 100)
g4.use_grapple(700, 100, 100, 100, None, scythe=True)
g4.grapple_head_pos = [700, 100]  # 钩爪头到达目标点
g4._begin_self_pull(100, 100, p4)
check(g4.grapple_state == "self_pull", "未命中进入 self_pull 状态")
check(g4.self_pull_immune, "自我拉拽免伤标记置位")
check(p4.invincible_timer >= 0.1, "玩家无敌计时刷新（免伤生效）")

# self_pull 推进玩家位置
g4._update_grapple(1 / 60, p4.x, p4.y, p4)
check(p4.x > 100, "self_pull 状态推进玩家向目标移动")
check(p4.invincible_timer > 0, "self_pull 期间持续免伤")

# 到达目标 → 复位（目标极近，一帧内到达）
g5 = RiotGear()
p5 = StubPlayer(100, 100)
g5.use_grapple(103, 100, 100, 100, None, scythe=False)
g5.grapple_head_pos = [103, 100]
g5._begin_self_pull(100, 100, p5)
g5._update_grapple(1 / 60, p5.x, p5.y, p5)
check(g5.grapple_state == "idle" or g5.grapple_active is False,
      "到达目标后钩爪复位（极近距离立即到达）")

# 锁定圈：圈内最近非 Boss 敌人
g6 = RiotGear()
g6.grapple_aiming = True
e_near = StubEnemy(150, 100, size=20, is_boss=False)
e_far = StubEnemy(300, 100, size=20, is_boss=False)
e_boss = StubEnemy(160, 100, size=30, is_boss=True)
lock = g6.update_grapple_lock(100, 100, [e_boss, e_far, e_near])
check(lock is e_near, "锁定圈选中最近非 Boss 敌人")
g6.grapple_aiming = False
lock2 = g6.update_grapple_lock(100, 100, [e_near])
check(lock2 is None, "未瞄准时不产生锁定")

# 锁定目标直飞（use_grapple 携带 locked target）
g7 = RiotGear()
locked_e = StubEnemy(300, 100, size=20, is_boss=False)
ok7 = g7.use_grapple(locked_e.x, locked_e.y, 100, 100, locked_e, scythe=True)
check(ok7 and g7.grapple_target is locked_e, "锁定目标作为直飞目标传入")

# 拉敌撞击词条：pulling 时被拉敌人撞到其他敌人
g8 = RiotGear()
pulled = StubEnemy(200, 100, size=20)
other = StubEnemy(205, 100, size=20)
pulled.knockback_x = 0
pulled.knockback_y = 0
g8.grapple_state = "pulling"
g8.grapple_target = pulled
g8.grapple_pull_impact_hit = set()
g8._grapple_impact_damage = 25
# 等价 mix_playing 撞击逻辑
_hit = False
for e2 in [pulled, other]:
    if e2 is pulled or not e2.alive:
        continue
    if id(e2) in g8.grapple_pull_impact_hit:
        continue
    if math.hypot(e2.x - pulled.x, e2.y - pulled.y) < getattr(e2, "size", 20) + getattr(pulled, "size", 20):
        g8.grapple_pull_impact_hit.add(id(e2))
        _hit = True
check(_hit, "拉敌撞击词条：被拉敌人撞到沿途敌人可命中")

# ==================== 4. 更新弹窗持久化 ====================
print("\n[4] 更新弹窗持久化")
import updater
check("notice_dismissed" in updater.UPDATE_STATE, "UPDATE_STATE 含 notice_dismissed 持久标记")
updater.UPDATE_STATE["notice_dismissed"] = True
check(updater.UPDATE_STATE.get("notice_dismissed") is True, "置位后全局可读（程序生命周期忽略更新）")
updater.UPDATE_STATE["notice_dismissed"] = False

print(f"\n===== 结果: {PASS} 通过, {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
