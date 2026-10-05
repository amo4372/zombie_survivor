# -*- coding: utf-8 -*-
"""ZombieSurvivorEnv v2 —— 地图感知 + 群体战术 + 个体技能

相对 v1 的升级（方案C落地）：
- 读取 .zmap 二进制地图：障碍物碰撞、八向射线感知、出生点/巡逻点
- 多僵尸群体：普通/疾速/坦克/吐酸 四类型，个体技能差异化（速度/血量/攻击）
- 共享策略多智能体：训练单僵尸策略，观测含"队友包抄角度"，部署时 N 只共享
  策略各自决策 → 集体战术涌现
- 观测 19 维：基础9 + 八向障碍物射线8 + 最近队友相对位置2
- 动作 Discrete(10)：0停 1-8八向移动 9=远程攻击（仅吐酸有效）

奖励设计（防无脑直线冲锋）：
  距离变化 / 侧面包抄(与玩家朝向角差) / 队友夹角包抄(≈90°集体夹击)
  咬中/命中 / 被击中惩罚 / 击杀+50 被杀-50 / 时间罚
"""
import os
import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from map_format import (load_map, is_blocked, raycast_free, TILE_BLOCK,
                       speed_factor, hazard_dps)

ARENA_W, ARENA_H = 1280.0, 960.0   # 与 40x30 格 * 32px 地图对应
DT = 1.0 / 30.0
PLAYER_SPEED = 130.0
PLAYER_RADIUS = 14.0
PLAYER_HP = 100
BULLET_SPEED = 420.0
BULLET_RADIUS = 4.0
BULLET_DAMAGE = 12.0
BITE_DAMAGE = 8.0
MAX_STEPS = 900
SUBSTEPS = 3

# 个体技能配置（类型差异化）
ZOMBIE_TYPES = {
    "normal": {"speed": 90.0, "hp": 50.0, "bite": 8.0, "bite_cd": 0.5, "radius": 16},
    "fast":   {"speed": 145.0, "hp": 30.0, "bite": 6.0, "bite_cd": 0.35, "radius": 13},
    "tank":   {"speed": 58.0, "hp": 250.0, "bite": 20.0, "bite_cd": 0.8, "radius": 22},
    "spitter": {"speed": 82.0, "hp": 40.0, "bite": 5.0, "bite_cd": 0.6, "radius": 15,
                "spit_damage": 6.0, "spit_cd": 2.0, "spit_range": 320.0, "spit_speed": 260.0},
}
TYPE_ORDER = list(ZOMBIE_TYPES)
RAYS = [0, 45, 90, 135, 180, 225, 270, 315]   # 八向射线


class ZombieEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 30}

    def __init__(self, render_mode=None, player_mode="kite", zombie_type="normal",
                 map_path="rl/maps/demo.zmap", teammate=True, seed=None):
        super().__init__()
        self.render_mode = render_mode
        self.player_mode = player_mode
        self.ztype = zombie_type
        self.teammate = teammate          # 是否模拟侧翼队友（集体战术训练）
        self.map = load_map(map_path)
        self.action_space = spaces.Discrete(10)
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(19,), dtype=np.float32)
        self.rz = np.random.default_rng(seed)
        self._reset_state()

    # ---------- 状态 ----------
    def _reset_state(self):
        st = ZOMBIE_TYPES[self.ztype]
        # 出生点：优先用地图僵尸出生点，没有则随机
        zspawns = [o for o in self.map["objects"] if o["type"] == 1]
        if zspawns:
            o = self.rz.choice(zspawns)
            self.zx, self.zy = float(o["x"]), float(o["y"])
        else:
            self.zx = float(self.rz.uniform(80, ARENA_W - 80))
            self.zy = float(self.rz.uniform(80, ARENA_H * 0.3))
        pspawns = [o for o in self.map["objects"] if o["type"] == 0]
        if pspawns:
            o = self.rz.choice(pspawns)
            self.px, self.py = float(o["x"]), float(o["y"])
        else:
            self.px = float(self.rz.uniform(80, ARENA_W - 80))
            self.py = float(self.rz.uniform(ARENA_H * 0.7, ARENA_H - 80))
        self.zhp = st["hp"]
        self.php = PLAYER_HP
        self.pfacing = math.atan2(self.zy - self.py, self.zx - self.px)
        self.bullets = []
        self.spits = []                # 吐酸投射物 [x,y,vx,vy]
        self.attack_timer = 0.0
        self.spit_timer = 0.0
        self.fire_timer = 0.0
        self.step_count = 0
        self._prev_dist = self._dist()
        self._flank_accum = 0.0
        # 队友（脚本模拟侧翼包抄）：与玩家保持镜像夹击
        self._tm_ang = self.rz.uniform(0, 2 * math.pi)
        self._tm_speed = ZOMBIE_TYPES["fast"]["speed"]

    def _dist(self):
        return math.hypot(self.zx - self.px, self.zy - self.py)

    def _teammate_pos(self):
        """队友位置：从玩家另一侧包抄（与 RL 僵尸大致成 90° 夹角）"""
        ang_to_z = math.atan2(self.zy - self.py, self.zx - self.px)
        t_ang = ang_to_z + math.pi / 2 if self.rz.random() < 0.5 else ang_to_z - math.pi / 2
        d = 260.0
        tx = self.px + math.cos(t_ang) * d
        ty = self.py + math.sin(t_ang) * d
        return float(np.clip(tx, 0, ARENA_W)), float(np.clip(ty, 0, ARENA_H))

    def _get_obs(self):
        dx = (self.zx - self.px) / ARENA_W
        dy = (self.zy - self.py) / ARENA_H
        d = self._dist() / math.hypot(ARENA_W, ARENA_H)
        side_w = min(self.zx, ARENA_W - self.zx) / (ARENA_W / 2)
        side_h = min(self.zy, ARENA_H - self.zy) / (ARENA_H / 2)
        # 八向障碍物射线（0~1，1=通畅；撞墙=距离占比）
        rays = []
        for r in RAYS:
            rad = math.radians(r)
            rv, _hit = raycast_free(self.map, self.zx, self.zy, rad, 400.0)
            rays.append(rv)
        # 队友信息
        if self.teammate:
            tx, ty = self._teammate_pos()
            tdx = (tx - self.zx) / ARENA_W
            tdy = (ty - self.zy) / ARENA_H
        else:
            tdx, tdy = 0.0, 0.0
        obs = [np.clip(dx * 2, -1, 1), np.clip(dy * 2, -1, 1), np.clip(d, 0, 1),
               math.sin(self.pfacing), math.cos(self.pfacing),
               self.php / PLAYER_HP, self.zhp / ZOMBIE_TYPES[self.ztype]["hp"],
               np.clip(side_w, 0, 1), np.clip(side_h, 0, 1)]
        obs += rays
        obs += [np.clip(tdx * 2, -1, 1), np.clip(tdy * 2, -1, 1)]
        return np.array(obs, dtype=np.float32)

    # ---------- 玩家脚本 ----------
    def _player_act(self):
        self.pfacing = math.atan2(self.zy - self.py, self.zx - self.px)
        if self.player_mode == "kite":
            away = math.atan2(self.py - self.zy, self.px - self.zx)
            mv = away + self.rz.uniform(-0.5, 0.5)
            nx = self.px + math.cos(mv) * PLAYER_SPEED * DT
            ny = self.py + math.sin(mv) * PLAYER_SPEED * DT
            if not is_blocked(self.map, nx, ny, PLAYER_RADIUS):
                self.px, self.py = float(nx), float(ny)
        self.fire_timer -= DT
        if self.fire_timer <= 0:
            self.fire_timer = 0.55
            spread = self.rz.uniform(-0.35, 0.35)
            ang = self.pfacing + spread
            self.bullets.append([self.px, self.py,
                                 math.cos(ang) * BULLET_SPEED, math.sin(ang) * BULLET_SPEED])

    def _update_bullets(self):
        hit = False
        for b in list(self.bullets):
            b[0] += b[2] * DT
            b[1] += b[3] * DT
            if (b[0] < 0 or b[0] > ARENA_W or b[1] < 0 or b[1] > ARENA_H
                    or is_blocked(self.map, b[0], b[1], 2)):
                self.bullets.remove(b)
                continue
            if math.hypot(b[0] - self.zx, b[1] - self.zy) < ZOMBIE_TYPES[self.ztype]["radius"] + BULLET_RADIUS:
                self.zhp -= BULLET_DAMAGE
                self.bullets.remove(b)
                hit = True
        return hit

    def _zombie_attack(self):
        st = ZOMBIE_TYPES[self.ztype]
        if self.attack_timer > 0:
            self.attack_timer -= DT
        if self._dist() < 34 and self.attack_timer <= 0:
            self.attack_timer = st["bite_cd"]
            self.php -= st["bite"]
            return 1.0
        return 0.0

    def _spit_attack(self):
        """远程吐酸（动作9，仅 spitter 生效）"""
        st = ZOMBIE_TYPES[self.ztype]
        if "spit_damage" not in st or self.spit_timer > 0:
            return 0.0
        if self._dist() > st["spit_range"]:
            return 0.0
        self.spit_timer = st["spit_cd"]
        ang = math.atan2(self.py - self.zy, self.px - self.zx)
        self.spits.append([self.zx, self.zy,
                           math.cos(ang) * st["spit_speed"], math.sin(ang) * st["spit_speed"]])
        return 0.0

    def _update_spits(self):
        st = ZOMBIE_TYPES[self.ztype]
        if "spit_damage" not in st:
            return 0.0
        dmg = 0.0
        for s in list(self.spits):
            s[0] += s[2] * DT
            s[1] += s[3] * DT
            if (s[0] < 0 or s[0] > ARENA_W or s[1] < 0 or s[1] > ARENA_H
                    or is_blocked(self.map, s[0], s[1], 3)):
                self.spits.remove(s)
                continue
            if math.hypot(s[0] - self.px, s[1] - self.py) < PLAYER_RADIUS + 5:
                self.php -= st["spit_damage"]
                self.spits.remove(s)
                dmg += st["spit_damage"]
        return dmg

    # ---------- Gymnasium ----------
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self.rz = np.random.default_rng(seed)
        self._reset_state()
        return self._get_obs(), {}

    def step(self, action):
        reward = 0.0
        terminated = truncated = False
        st = ZOMBIE_TYPES[self.ztype]
        for _ in range(SUBSTEPS):
            self.step_count += 1
            # 移动（1-8 向）+ 障碍物碰撞
            if 1 <= action <= 8:
                ang = (action - 1) * (math.pi / 4)
                nx = self.zx + math.cos(ang) * st["speed"] * DT
                ny = self.zy + math.sin(ang) * st["speed"] * DT
                if not is_blocked(self.map, nx, ny, st["radius"]):
                    self.zx, self.zy = float(nx), float(ny)
                    # 地图元素：水坑减速 / 尖刺伤害
                    if speed_factor(self.map, self.zx, self.zy) < 1.0:
                        reward -= 0.05  # 水坑减速惩罚（学会避开）
                    self.zhp -= hazard_dps(self.map, self.zx, self.zy) * DT
                    if hazard_dps(self.map, self.zx, self.zy) > 0:
                        reward -= 0.1  # 踩尖刺惩罚
                else:
                    reward -= 0.1  # 撞墙小惩罚（学会绕路）
            elif action == 9:
                reward += self._spit_attack()

            self._player_act()
            if self._update_bullets():
                reward -= 0.8
            reward += self._zombie_attack() * 5.0
            reward += self._update_spits() * 0.8

            d_now = self._dist()
            r_close = (self._prev_dist - d_now) / (st["speed"] * DT * SUBSTEPS) * 1.5
            reward += float(np.clip(r_close, -1.5, 1.5))

            # 侧面包抄（玩家朝向角差≈90°）
            ang_to_z = math.atan2(self.zy - self.py, self.zx - self.px)
            diff = abs(ang_to_z - self.pfacing)
            diff = min(diff, 2 * math.pi - diff)
            side = abs(math.sin(diff))
            prox = 1.0 - np.clip(d_now / 500.0, 0, 1)
            self._flank_accum += side * prox * DT
            reward += 0.25 * side * prox * DT * 30 * 0.02
            if self._flank_accum >= 1.2 and d_now < 250:
                self._flank_accum = 0.0
                reward += 2.0

            # 集体包抄：与队友夹角接近 90° 且都近身 → 奖励（学夹击）
            if self.teammate:
                tx, ty = self._teammate_pos()
                a1 = math.atan2(self.py - ty, self.px - tx)
                a2 = math.atan2(self.py - self.zy, self.px - self.zx)
                da = abs(a1 - a2)
                da = min(da, 2 * math.pi - da)
                team_side = abs(math.sin(da))
                reward += 0.15 * team_side * prox * DT * 30 * 0.02

            self._prev_dist = d_now

            if self.php <= 0:
                reward += 50.0
                terminated = True
                break
            if self.zhp <= 0:
                reward -= 50.0
                terminated = True
                break
            if self.step_count >= MAX_STEPS:
                truncated = True
                break

        reward -= 0.01
        return self._get_obs(), float(reward), terminated, truncated, {}

    def render(self):
        if self.render_mode == "rgb_array":
            return np.zeros((240, 320, 3), dtype=np.uint8)
        return None


def make_env_factory(zombie_type, seed_base=1000):
    def _f():
        return ZombieEnv(player_mode="kite", zombie_type=zombie_type,
                         map_path="rl/maps/demo.zmap", teammate=True,
                         seed=seed_base + hash(zombie_type) % 1000)
    return _f
