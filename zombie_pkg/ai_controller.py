# -*- coding: utf-8 -*-
"""游戏端 RL 推理控制器 —— 强化学习僵尸 AI 接入

- 惰性加载 ONNX 模型（onnxruntime 缺失 / 模型缺失 → disabled，游戏回退原 AI）
- 观测构造与 RL 训练环境（rl/zombie_env.py）同规格 19 维
- 输出 (vx, vy, attack) 方向向量；速度仍用敌人自身 speed × buff（与训练一致）
- 集体：取世界内最近的其他敌人作为"队友"（共享策略 → 群体行为）
"""
import os
import math
import time

def _now():
    return time.perf_counter()


class RLEnemyAI:
    # 动作→技能映射：9远程 10冲刺 11召唤 12范围咆哮
    ACT_SKILL = {9: 1, 10: 2, 11: 3, 12: 4}

    def __init__(self, model_path, enable=True):
        self.model_path = model_path
        self.enabled = False
        self.sess = None
        self._input_name = None
        self.obs_dim = 21
        # 遥测统计（开发者面板/数据导出用）
        self.stats = {"decisions": 0, "action_hist": {}, "skill_hist": {},
                      "total_ms": 0.0, "last_obs": None, "last_act": None,
                      "model_status": "disabled", "load_error": ""}
        if enable and model_path and os.path.exists(model_path):
            try:
                import onnxruntime as ort
                import numpy as np
                self._np = np
                self.sess = ort.InferenceSession(
                    model_path, providers=["CPUExecutionProvider"])
                self._input_name = self.sess.get_inputs()[0].name
                self.enabled = True
            except Exception as e:
                self.stats["load_error"] = str(e)[:120]
                self.sess = None
        if self.sess is not None:
            self.stats["model_status"] = "ready"

    @property
    def ready(self):
        return self.enabled and self.sess is not None

    # ---------- 观测构造（与 RL 环境 19 维同规格） ----------
    def make_obs(self, enemy, player, world=None, teammate=None):
        np = self._np
        ARENA_W, ARENA_H = 1280.0, 960.0
        dx = (enemy.x - player.x) / ARENA_W
        dy = (enemy.y - player.y) / ARENA_H
        dist = math.hypot(enemy.x - player.x, enemy.y - player.y) / math.hypot(ARENA_W, ARENA_H)
        facing = getattr(player, "facing_angle", 0.0)
        side_w = min(abs(enemy.x), 400.0) / 200.0
        side_h = min(abs(enemy.y), 400.0) / 200.0
        rays = []
        for deg in (0, 45, 90, 135, 180, 225, 270, 315):
            rays.append(self._ray_dist(enemy, world, math.radians(deg), 400.0))
        if teammate is not None:
            tdx = (teammate.x - enemy.x) / ARENA_W
            tdy = (teammate.y - enemy.y) / ARENA_H
        else:
            tdx = tdy = 0.0
        # boss 技能冷却（与训练环境同规格；普通敌人无属性→0）
        dash_cd = getattr(enemy, "boss_dash_cd", 0.0) or 0.0
        aoe_cd = getattr(enemy, "boss_aoe_cd", 0.0) or 0.0
        max_cd = 5.0
        return np.array([
            float(np.clip(dx * 2, -1, 1)), float(np.clip(dy * 2, -1, 1)),
            float(np.clip(dist, 0, 1)),
            math.sin(facing), math.cos(facing),
            player.hp / 100.0, enemy.hp / max(getattr(enemy, "max_hp", 50), 1),
            float(np.clip(side_w, 0, 1)), float(np.clip(side_h, 0, 1)),
        ] + rays + [float(np.clip(tdx * 2, -1, 1)), float(np.clip(tdy * 2, -1, 1)),
                    float(np.clip(dash_cd / max_cd, 0, 1)),
                    float(np.clip(aoe_cd / max_cd, 0, 1))],
            dtype=np.float32)

    def _ray_dist(self, enemy, world, ang, max_dist=400.0):
        """沿方向采样世界障碍（rects），返回首个碰撞距离归一化 0~1；无碰撞=1.0"""
        if not world or not getattr(world, "obstacles", None):
            return 1.0
        step = 12.0
        d = 0.0
        ex, ey = enemy.x, enemy.y
        cos_a, sin_a = math.cos(ang), math.sin(ang)
        while d < max_dist:
            d += step
            px, py = ex + cos_a * d, ey + sin_a * d
            for o in world.obstacles:
                if o["rect"].collidepoint(px, py):
                    return min(d / max_dist, 1.0)
        return 1.0

    # ---------- 决策 ----------
    def decide(self, enemy, player, world=None, teammates=None):
        """返回 (vx, vy, attack)；不可用时返回 (None, None, False) 表示回退原 AI"""
        if not self.ready:
            return None, None, False
        try:
            tm = None
            if teammates:
                tm = min(teammates, key=lambda e: math.hypot(e.x - enemy.x, e.y - enemy.y))
            t0 = _now()
            obs = self.make_obs(enemy, player, world, tm)
            probs = self.sess.run(None, {self._input_name: obs.reshape(1, -1)})[0][0]
            # 拟人采样（温度 1.2）
            p = self._np.clip(probs.astype(float), 1e-9, None)
            p = p ** (1.0 / 1.2)
            p /= p.sum()
            act = int(self._np.random.choice(len(p), p=p))
            self.stats["decisions"] += 1
            self.stats["action_hist"][act] = self.stats["action_hist"].get(act, 0) + 1
            self.stats["total_ms"] += (_now() - t0) * 1000.0
            self.stats["last_obs"] = [round(float(x), 3) for x in obs]
            self.stats["last_act"] = act
            skill = self.ACT_SKILL.get(act, 0)
            if skill:
                self.stats["skill_hist"][skill] = self.stats["skill_hist"].get(skill, 0) + 1
            if act == 0 or act >= 10:
                return 0.0, 0.0, skill if act != 0 else 0
            if act == 9:
                return 0.0, 0.0, skill
            ang = (act - 1) * (math.pi / 4)
            return math.cos(ang), math.sin(ang), skill
        except Exception:
            return None, None, False

    def save_stats(self, path):
        """导出遥测数据（决策/技能/延迟），供开发者面板与离线分析"""
        try:
            import json
            s = dict(self.stats)
            s["last_obs"] = None  # 不落盘完整观测（占空间）
            s["avg_ms"] = round(self.stats["total_ms"] / max(self.stats["decisions"], 1), 3)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


# 全局单例（惰性初始化）
_CTRL = None


def get_controller(model_path=None, enable=True):
    global _CTRL
    if _CTRL is None:
        _CTRL = RLEnemyAI(model_path, enable)
    return _CTRL
