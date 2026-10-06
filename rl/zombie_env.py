# -*- coding: utf-8 -*-
"""ZombieSurvivorEnv v2 —— 地图感知 + 群体战术 + 个体技能

相对 v1 的升级（方案C落地）：
- 读取 .zmap 二进制地图：障碍物碰撞、八向射线感知、出生点/巡逻点
- 多僵尸群体：普通/疾速/坦克/吐酸 四类型，个体技能差异化（速度/血量/攻击）
- 共享策略多智能体：训练单僵尸策略，观测含"队友包抄角度"，部署时 N 只共享
  策略各自决策 → 集体战术涌现
- 观测 19 维：基础9 + 八向障碍物射线8 + 最近队友相对位置2
- 动作 Discrete(13)：0停 1-8八向移动 9=远程攻击 10=冲刺(boss) 11=召唤(boss) 12=范围咆哮(boss)
- 观测 21 维：原19维 + 冲刺冷却 + 范围技能冷却（boss 专用，普通类型恒 0）

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
                "spit_damage": 6.0, "spit_cd": 2.0, "spit_range": 320.0, "spit_speed": 260.0,
                "can_throw": True, "throw_type": "acid", "throw_damage": 8.0,
                "throw_cd": 4.0, "throw_range_min": 150.0, "throw_range_max": 450.0},
    "ranged": {"speed": 78.0, "hp": 45.0, "bite": 6.0, "bite_cd": 0.7, "radius": 15,
               "can_throw": True, "throw_type": "rock", "throw_damage": 10.0,
               "throw_cd": 3.5, "throw_range_min": 150.0, "throw_range_max": 450.0},
    "boss":    {"speed": 95.0, "hp": 500.0, "bite": 24.0, "bite_cd": 0.7, "radius": 22,
                "dash_cd": 3.5, "summon_cd": 8.0, "aoe_cd": 5.0,
                "dash_damage": 20.0, "aoe_damage": 12.0, "aoe_radius": 200.0, "dash_dist": 220.0,
                "can_throw": True, "throw_type": "fire", "throw_damage": 14.0,
                "throw_cd": 4.0, "throw_range_min": 150.0, "throw_range_max": 450.0},
}
TYPE_ORDER = list(ZOMBIE_TYPES)
RAYS = [0, 45, 90, 135, 180, 225, 270, 315]   # 八向射线


class ZombieEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 30}

    def __init__(self, render_mode=None, player_mode="kite", zombie_type="normal",
                 map_path=None, teammate=True, seed=None, n_zombies=1):
        super().__init__()
        self.render_mode = render_mode
        self.player_mode = player_mode
        self.ztype = zombie_type
        self.teammate = teammate          # 是否模拟侧翼队友（集体战术训练）
        self.n_zombies = max(1, int(n_zombies))   # 群体：1=单挑, 2/3=包抄群
        # map_path=None → 按 (类型,种子) 从 5 张剧情地图轮换（肉鸽泛化）
        if map_path is None:
            map_path = TRAIN_MAPS[abs(hash((zombie_type, seed or 0))) % len(TRAIN_MAPS)]
        self.map = load_map(map_path)
        self.map_path = os.path.basename(map_path)
        # 随机障碍叠加：固定剧情地图 + 随机掩体/水/刺（与游戏端"固定+随机"一致）
        self._add_random_obstacles(abs(hash((zombie_type, seed or 0))) % 100000)
        # v2.0.14.1：动作14=投掷投掷物（对齐游戏端 try_throw：rock/acid/fire）
        self.action_space = spaces.Discrete(14)
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(31,), dtype=np.float32)   # 22基础+4子弹感知+5玩家感知
        self.rz = np.random.default_rng(seed)
        self._reset_state()

    # ---------- 状态 ----------
    def _add_random_obstacles(self, seed):
        """固定剧情图 + 随机障碍叠加（掩体/水坑/尖刺），增加地图多样性；避开出生安全区(左上 8x8)与出口"""
        try:
            r = np.random.default_rng(seed)
            n = int(r.integers(2, 5))
            tiles = [2, 3, 4]   # 掩体 / 水 / 刺
            w, h = self.map["w"], self.map["h"]
            for _ in range(n):
                for _try in range(30):
                    x = int(r.integers(4, w - 4)); y = int(r.integers(4, h - 4))
                    if x < 8 and y < 8:
                        continue  # 出生安全区不挡
                    if self.map["grid"][y][x] != 0:
                        continue
                    # 避开出口与补给对象格
                    objs = [o for o in self.map["objects"] if o["type"] in (0, 3)]
                    if any(abs(o["x"] // 32 - x) < 2 and abs(o["y"] // 32 - y) < 2 for o in objs):
                        continue
                    self.map["grid"][y][x] = int(r.choice(tiles))
                    break
        except Exception:
            pass  # 随机障碍失败不影响训练

    def _update_pack(self):
        """群体脚本队友：从多方向逼近玩家 + 近身咬人（与 RL 主僵尸形成包抄）"""
        st = ZOMBIE_TYPES[self.ztype]
        for p in self.pack:
            ang = math.atan2(self.py - p["y"], self.px - p["x"]) + self.rz.uniform(-0.35, 0.35)
            nx = p["x"] + math.cos(ang) * st["speed"] * 0.9 * DT
            ny = p["y"] + math.sin(ang) * st["speed"] * 0.9 * DT
            if not is_blocked(self.map, nx, ny, st["radius"]):
                p["x"], p["y"] = float(nx), float(ny)
            if math.hypot(p["x"] - self.px, p["y"] - self.py) < st["radius"] + PLAYER_RADIUS + 6:
                self.php -= st["bite"] * 0.5
                self.ep_dmg_dealt += st["bite"] * 0.5

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
        self.throws = []               # 投掷物（抛射物）[x,y,vx,vy,dmg]
        self.attack_timer = 0.0
        self.spit_timer = 0.0
        # boss 技能冷却（普通类型恒 0）
        self.dash_cd = 0.0
        self.aoe_cd = 0.0
        self.summon_cd = 0.0
        self.throw_cd = 0.0            # 投掷物冷却（有 can_throw 的类型）
        self.is_dashing = False
        self.dash_dir = (0.0, 0.0)
        self.fire_timer = 0.0
        self.step_count = 0
        # ---- episode 游戏相关统计（测评报告用）----
        self.ep_dmg_dealt = 0.0     # 对玩家造成伤害
        self.ep_dmg_taken = 0.0     # 被玩家子弹伤害
        self.ep_kills = 0           # 击杀玩家次数
        self.ep_move_dist = 0.0     # 累计移动距离
        self.ep_bite_hits = 0       # 咬中次数
        self.ep_spit_hits = 0       # 吐酸命中次数
        self.ep_throw_hits = 0      # 投掷物命中次数
        self.ep_hazard_hits = 0     # 踩水坑/尖刺次数
        self.ep_skill_use = {"spit": 0, "dash": 0, "summon": 0, "aoe": 0, "throw": 0}  # 技能成功使用次数
        self._prev_dist = self._dist()
        self._prev_px = self.px
        self._prev_py = self.py
        self._flank_accum = 0.0
        # 群体队友（真实位置，多方向包抄）：分布在玩家另一侧/侧翼
        self.pack = []
        if self.n_zombies > 1:
            base = math.atan2(self.zy - self.py, self.zx - self.px)
            for i in range(self.n_zombies - 1):
                side = math.pi / 2 if i % 2 == 0 else -math.pi / 2
                a = base + side + self.rz.uniform(-0.5, 0.5)
                d0 = self.rz.uniform(260, 380)
                self.pack.append({
                    "x": float(np.clip(self.px + math.cos(a) * d0, 40, ARENA_W - 40)),
                    "y": float(np.clip(self.py + math.sin(a) * d0, 40, ARENA_H - 40)),
                    "hp": ZOMBIE_TYPES[self.ztype]["hp"] * 0.8,
                })

    def _dist(self):
        return math.hypot(self.zx - self.px, self.zy - self.py)

    def _teammate_pos(self):
        """队友位置：优先真实群体队友（最近者）；无 pack 时镜像侧翼"""
        if getattr(self, "pack", None):
            best = min(self.pack, key=lambda p: math.hypot(p["x"] - self.zx, p["y"] - self.zy))
            return float(best["x"]), float(best["y"])
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
        # boss 技能冷却（普通类型恒 0）
        max_cd = max(ZOMBIE_TYPES["boss"]["dash_cd"], ZOMBIE_TYPES["boss"]["aoe_cd"], 1.0) if self.ztype == "boss" else 1.0
        obs += [np.clip(self.dash_cd / max_cd, 0, 1), np.clip(self.aoe_cd / max_cd, 0, 1),
               np.clip(self.throw_cd / 5.0, 0, 1)]
        # 子弹感知（躲避子弹）：最近一发玩家子弹 方位sin/cos + 距离 + 威胁度(1=正朝僵尸飞来)
        bs, bc, bd, bt = 0.0, 0.0, 0.0, 0.0
        _best, _bd = None, float("inf")
        for b in self.bullets:
            _d = math.hypot(b[0] - self.zx, b[1] - self.zy)
            if _d < _bd:
                _bd, _best = _d, b
        if _best is not None:
            b_ang = math.atan2(_best[1] - self.zy, _best[0] - self.zx)
            threat = math.cos(math.atan2(_best[3], _best[2]) - math.atan2(self.zy - _best[1], self.zx - _best[0]))
            bs, bc, bd, bt = math.sin(b_ang), math.cos(b_ang), float(np.clip(_bd / 600.0, 0, 1)), float(np.clip(threat, -1, 1))
        obs += [bs, bc, bd, bt]
        # 玩家感知 5 维（精英/BOSS 专用 31 维）：速度差分 + 玩家朝向 + 射击冷却
        pvx = float(np.clip((self.px - self._prev_px) / (PLAYER_SPEED * DT * SUBSTEPS), -1, 1))
        pvy = float(np.clip((self.py - self._prev_py) / (PLAYER_SPEED * DT * SUBSTEPS), -1, 1))
        obs += [pvx, pvy, math.sin(self.pfacing), math.cos(self.pfacing),
                float(1.0 if self.fire_timer > 0 else 0.0)]
        return np.array(obs, dtype=np.float32)

    # ---------- 玩家脚本（行为多样化：kite风筝 / stand站桩 / strafe横向走位 / melee近战冲脸）----------
    def _player_act(self):
        self.pfacing = math.atan2(self.zy - self.py, self.zx - self.px)
        mode = self.player_mode
        d = self._dist()
        if mode == "stand":
            pass  # 站桩输出（威胁近距离目标，逼僵尸学绕后/技能压制）
        elif mode == "strafe":
            tang = self.pfacing + (math.pi / 2 if self.rz.random() < 0.5 else -math.pi / 2)
            nx = self.px + math.cos(tang) * PLAYER_SPEED * DT
            ny = self.py + math.sin(tang) * PLAYER_SPEED * DT
            if not is_blocked(self.map, nx, ny, PLAYER_RADIUS):
                self.px, self.py = float(nx), float(ny)
        elif mode == "melee":
            # 近战玩家：冲脸 + 近身高伤（逼僵尸用技能/拉开距离）
            toward = math.atan2(self.zy - self.py, self.zx - self.px)
            nx = self.px + math.cos(toward) * PLAYER_SPEED * 1.3 * DT
            ny = self.py + math.sin(toward) * PLAYER_SPEED * 1.3 * DT
            if not is_blocked(self.map, nx, ny, PLAYER_RADIUS):
                self.px, self.py = float(nx), float(ny)
            if d < 70:
                self.zhp -= 8.0 * DT
            return  # 近战玩家不射击
        else:  # kite 默认
            away = math.atan2(self.py - self.zy, self.px - self.zx)
            mv = away + self.rz.uniform(-0.5, 0.5)
            nx = self.px + math.cos(mv) * PLAYER_SPEED * DT
            ny = self.py + math.sin(mv) * PLAYER_SPEED * DT
            if not is_blocked(self.map, nx, ny, PLAYER_RADIUS):
                self.px, self.py = float(nx), float(ny)
        self.fire_timer -= DT
        if self.fire_timer <= 0:
            self.fire_timer = 0.5 if mode == "strafe" else 0.42 if mode == "stand" else 0.55
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
                self.ep_dmg_taken += BULLET_DAMAGE
        return hit

    def _boss_dash(self):
        """冲刺：向玩家突进一段距离，命中靠近奖励"""
        if self.dash_cd > 0:
            return -0.2
        self.dash_cd = ZOMBIE_TYPES["boss"]["dash_cd"]
        self.ep_skill_use["dash"] += 1
        ang = math.atan2(self.py - self.zy, self.px - self.zx)
        self.dash_dir = (math.cos(ang), math.sin(ang))
        self.is_dashing = True
        self.dash_timer = 0.45
        # 先预览冲后距离：若显著逼近玩家则奖励
        d_before = self._dist()
        d_after = math.hypot(self.zx + self.dash_dir[0] * 120 - self.px,
                             self.zy + self.dash_dir[1] * 120 - self.py)
        gain = max(0.0, d_before - d_after)
        return float(np.clip(gain / 300.0 * 10.0, 0, 10))

    def _boss_summon(self):
        """召唤：冷却内不可用，成功 +3（象征召唤小怪威慑）"""
        if self.summon_cd > 0:
            return -0.2
        self.summon_cd = ZOMBIE_TYPES["boss"]["summon_cd"]
        self.ep_skill_use["summon"] += 1
        return 3.0

    def _boss_aoe(self):
        """范围咆哮：玩家在半径内受伤害"""
        if self.aoe_cd > 0:
            return -0.2
        self.aoe_cd = ZOMBIE_TYPES["boss"]["aoe_cd"]
        self.ep_skill_use["aoe"] += 1
        if self._dist() < ZOMBIE_TYPES["boss"]["aoe_radius"]:
            self.php = max(0.0, self.php - ZOMBIE_TYPES["boss"]["aoe_damage"])
            self.ep_dmg_dealt += ZOMBIE_TYPES["boss"]["aoe_damage"]
            return 12.0
        return 0.5

    def _zombie_attack(self):
        st = ZOMBIE_TYPES[self.ztype]
        if self.attack_timer > 0:
            self.attack_timer -= DT
        if self._dist() < 34 and self.attack_timer <= 0:
            self.attack_timer = st["bite_cd"]
            self.php -= st["bite"]
            self.ep_bite_hits += 1
            self.ep_dmg_dealt += st["bite"]
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
        self.ep_skill_use["spit"] += 1
        return 0.0

    def _throw_attack(self):
        """投掷投掷物（对齐游戏端 try_throw：150-450 距离、抛物线弹道）
        rock/acid/fire 按类型；冷却内 -0.2；成功发射 +0.5；命中 +伤害奖励"""
        st = ZOMBIE_TYPES[self.ztype]
        if not st.get("can_throw"):
            return 0.0
        if self.throw_cd > 0:
            return -0.2
        d = self._dist()
        if d < st["throw_range_min"] or d > st["throw_range_max"]:
            return 0.0  # 距离不符不发射（不惩罚，学会选时机）
        self.throw_cd = st["throw_cd"]
        ang = math.atan2(self.py - self.zy, self.px - self.zx)
        spd = 280.0
        self.throws.append([self.zx, self.zy,
                            math.cos(ang) * spd, math.sin(ang) * spd,
                            st["throw_damage"]])
        self.ep_skill_use["throw"] += 1
        return 0.5  # 成功发射（压制奖励）

    def _update_throws(self):
        """投掷物飞行+命中（玩家被击中扣血）"""
        st = ZOMBIE_TYPES[self.ztype]
        dmg = 0.0
        for t in list(self.throws):
            t[0] += t[2] * DT
            t[1] += t[3] * DT
            if (t[0] < 0 or t[0] > ARENA_W or t[1] < 0 or t[1] > ARENA_H
                    or is_blocked(self.map, t[0], t[1], 4)):
                self.throws.remove(t)
                continue
            if math.hypot(t[0] - self.px, t[1] - self.py) < PLAYER_RADIUS + 6:
                self.php = max(0.0, self.php - t[4])
                self.throws.remove(t)
                dmg += t[4]
                self.ep_throw_hits += 1
                self.ep_dmg_dealt += t[4]
        return dmg

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
                self.ep_spit_hits += 1
                self.ep_dmg_dealt += st["spit_damage"]
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
            # 技能冷却
            self.dash_cd = max(0.0, self.dash_cd - DT)
            self.aoe_cd = max(0.0, self.aoe_cd - DT)
            self.summon_cd = max(0.0, self.summon_cd - DT)
            self.throw_cd = max(0.0, self.throw_cd - DT)
            # 冲刺持续状态
            if self.is_dashing:
                dx0, dy0 = self.dash_dir
                self.zx += dx0 * 340.0 * DT
                self.zy += dy0 * 340.0 * DT
                self.zx = float(np.clip(self.zx, st["radius"], ARENA_W - st["radius"]))
                self.zy = float(np.clip(self.zy, st["radius"], ARENA_H - st["radius"]))
                self.dash_timer -= DT
                if self.dash_timer <= 0:
                    self.is_dashing = False
            # 移动（1-8 向）+ 障碍物碰撞
            if 1 <= action <= 8:
                ang = (action - 1) * (math.pi / 4)
                nx = self.zx + math.cos(ang) * st["speed"] * DT
                ny = self.zy + math.sin(ang) * st["speed"] * DT
                if not is_blocked(self.map, nx, ny, st["radius"]):
                    self.ep_move_dist += math.hypot(nx - self.zx, ny - self.zy)
                    self.zx, self.zy = float(nx), float(ny)
                    # 地图元素：水坑减速 / 尖刺伤害
                    if speed_factor(self.map, self.zx, self.zy) < 1.0:
                        reward -= 0.05  # 水坑减速惩罚（学会避开）
                        self.ep_hazard_hits += 1
                    self.zhp -= hazard_dps(self.map, self.zx, self.zy) * DT
                    if hazard_dps(self.map, self.zx, self.zy) > 0:
                        reward -= 0.1  # 踩尖刺惩罚
                        self.ep_hazard_hits += 1
                else:
                    reward -= 0.1  # 撞墙小惩罚（学会绕路）
            elif action == 9:
                reward += self._spit_attack()
            elif action == 13:
                # 投掷投掷物（ranged/spitter/boss 可用；其余类型视为停止）
                if ZOMBIE_TYPES[self.ztype].get("can_throw"):
                    reward += self._throw_attack()
                else:
                    action = 0
            elif action in (10, 11, 12):
                # boss 专属技能；非 boss 类型视为停止
                if self.ztype == "boss":
                    if action == 10:
                        reward += self._boss_dash()
                    elif action == 11:
                        reward += self._boss_summon()
                    else:
                        reward += self._boss_aoe()
                else:
                    action = 0

            self._player_act()
            if self.n_zombies > 1:
                self._update_pack()
            if self._update_bullets():
                reward -= 0.8
            reward += self._zombie_attack() * 5.0
            reward += self._update_spits() * 0.8
            reward += self._update_throws() * 0.8

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
            self._prev_px = self.px
            self._prev_py = self.py

            if self.php <= 0:
                reward += 50.0
                self.ep_kills += 1
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


# 按游戏剧情章节的 5 张地图 + demo 示例（肉鸽：固定障碍叠加随机障碍，每局不同）
# 按游戏剧情章节的 5 张地图（肉鸽：固定障碍叠加随机障碍，每局不同）
TRAIN_MAPS = ["rl/maps/school.zmap", "rl/maps/street.zmap", "rl/maps/downtown.zmap",
              "rl/maps/suburb.zmap", "rl/maps/nuclear.zmap"]

def make_env_factory(zombie_type, seed_base=1000):
    def _f():
        # 地图轮换：按类型+种子选图（泛化到全部地图）
        mp = TRAIN_MAPS[abs(hash((zombie_type, seed_base))) % len(TRAIN_MAPS)]
        seed = seed_base + hash(zombie_type) % 1000
        # 玩家行为多样化：kite 为主，穿插 stand/strafe/melee（学应对不同玩家）
        modes = ["kite", "kite", "stand", "strafe", "melee"]
        mode = modes[seed % len(modes)]
        # 群体包抄：50% 单挑、30% 双僵尸、20% 三僵尸（集体战术）
        nz = 1
        r = seed % 10
        if 5 <= r < 8:
            nz = 2
        elif r >= 8:
            nz = 3
        return ZombieEnv(player_mode=mode, zombie_type=zombie_type,
                         map_path=mp, teammate=True, seed=seed, n_zombies=nz)
    return _f
