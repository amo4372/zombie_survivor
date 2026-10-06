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
    ACT_SKILL = {9: 1, 10: 2, 11: 3, 12: 4, 13: 5}   # 13=投掷投掷物（v2.0.14.1）

    def __init__(self, model_path, enable=True):
        self.model_path = model_path
        self.enabled = False
        self.sess = None
        self._cache = {}            # id(enemy) -> (下次决策时间, vx, vy, skill)：决策节流缓存
        self._dirty = set()         # 待批量重算的敌人 id（主循环每帧 flush 一次批前向）
        self._DECIDE_INTERVAL = 0.2   # 决策节流：同怪 0.2s 内复用上次动作
        self._input_name = None
        self.obs_dim = 22   # 默认旧模型维度；加载后按权重自动适配（22 或 26 子弹感知）
        # 遥测统计（开发者面板/数据导出用）
        self.stats = {"decisions": 0, "action_hist": {}, "skill_hist": {},
                      "total_ms": 0.0, "last_obs": None, "last_act": None,
                      "model_status": "disabled", "load_error": ""}
        self._npz = None          # 纯 numpy 推理权重（onnxruntime 不可用时的回退）
        self._ppos = {}           # 玩家位置缓存（感知增强：速度差分）
        self._np_mod = None
        if enable and model_path and os.path.exists(model_path):
            try:
                import onnxruntime as ort
                import numpy as np
                self._np = np
                self.sess = ort.InferenceSession(
                    model_path, providers=["CPUExecutionProvider"])
                self._input_name = self.sess.get_inputs()[0].name
                self.obs_dim = int(self.sess.get_inputs()[0].shape[1])
                self.enabled = True
            except Exception as e:
                # v2.0.15：onnxruntime 不可用（如 Pydroid3 无 wheel）→ 纯 numpy 推理回退
                self.stats["load_error"] = str(e)[:120]
                self.sess = None
                try:
                    _npz_path = os.path.join(os.path.dirname(model_path), "policy_weights.npz")
                    if os.path.exists(_npz_path):
                        import numpy as _np2
                        self._np = _np2
                        self._np_mod = _np2
                        self._npz = _np2.load(_npz_path)
                        self.obs_dim = int(self._npz["mlp.policy_net.0.weight"].shape[1])
                        self.enabled = True
                except Exception as e2:
                    self.stats["load_error"] = (self.stats["load_error"] + " | " + str(e2)[:80])
                    self._npz = None
        if self.sess is not None:
            self.stats["model_status"] = "ready"
        elif self._npz is not None:
            self.stats["model_status"] = "ready-numpy"   # 纯 numpy 推理模式

    @property
    def ready(self):
        return self.enabled and (self.sess is not None or self._npz is not None)

    # ---------- 观测构造（与 RL 环境 19 维同规格） ----------
    def make_obs(self, enemy, player, world=None, teammate=None):
        np = self._np
        ARENA_W, ARENA_H = 1280.0, 960.0
        dx = (enemy.x - player.x) / ARENA_W
        dy = (enemy.y - player.y) / ARENA_H
        dist = math.hypot(enemy.x - player.x, enemy.y - player.y) / math.hypot(ARENA_W, ARENA_H)
        facing = getattr(player, "facing_angle", 0.0)
        # 与训练端一致：到最近墙距离 / 半宽（0=贴墙，1=场中央）
        side_w = min(enemy.x, ARENA_W - enemy.x) / (ARENA_W / 2)
        side_h = min(enemy.y, ARENA_H - enemy.y) / (ARENA_H / 2)
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
        throw_cd = getattr(enemy, "throw_cd", 0.0) or 0.0
        max_cd = 5.0
        obs = [
            float(np.clip(dx * 2, -1, 1)), float(np.clip(dy * 2, -1, 1)),
            float(np.clip(dist, 0, 1)),
            math.sin(facing), math.cos(facing),
            player.hp / 100.0, enemy.hp / max(getattr(enemy, "max_hp", 50), 1),
            float(np.clip(side_w, 0, 1)), float(np.clip(side_h, 0, 1)),
        ] + rays + [float(np.clip(tdx * 2, -1, 1)), float(np.clip(tdy * 2, -1, 1)),
                    float(np.clip(dash_cd / max_cd, 0, 1)),
                    float(np.clip(aoe_cd / max_cd, 0, 1)),
                    float(np.clip(throw_cd / max_cd, 0, 1))]
        # 子弹感知 4 维（新模型 26 维；旧模型 22 维补零保持兼容）
        bs = bc = bd = bt = 0.0
        if self.obs_dim >= 26 and world is not None:
            try:
                _best, _bd = None, float("inf")
                for b in getattr(world, "projectiles", None) or []:
                    if not getattr(b, "alive", True):
                        continue
                    _d = math.hypot(b.x - enemy.x, b.y - enemy.y)
                    if _d < _bd:
                        _bd, _best = _d, b
                if _best is not None:
                    b_ang = math.atan2(_best.y - enemy.y, _best.x - enemy.x)
                    threat = math.cos(math.atan2(_best.vy, _best.vx)
                                      - math.atan2(enemy.y - _best.y, enemy.x - _best.x))
                    bs, bc, bd, bt = (math.sin(b_ang), math.cos(b_ang),
                                      float(np.clip(_bd / 600.0, 0, 1)), float(np.clip(threat, -1, 1)))
            except Exception:
                pass
        if self.obs_dim >= 26:
            obs += [bs, bc, bd, bt]
        # 玩家感知 5 维（精英/BOSS 专用新模型 31 维）：速度差分 + 朝向 + 射击冷却
        if self.obs_dim >= 31 and player is not None:
            try:
                pfx = math.sin(math.radians(getattr(player, "facing_angle", 0.0)))
                pfy = math.cos(math.radians(getattr(player, "facing_angle", 0.0)))
                _k = id(player)
                _pp = self._ppos.get(_k)
                if _pp is not None:
                    pvx = float(np.clip((player.x - _pp[0]) / 8.0, -1, 1))
                    pvy = float(np.clip((player.y - _pp[1]) / 8.0, -1, 1))
                else:
                    pvx = pvy = 0.0
                self._ppos[_k] = (player.x, player.y)
                _w = getattr(player, "current_weapon", None) or getattr(player, "weapon", None)
                _ft = getattr(_w, "cooldown", 0) if _w is not None else 0
                if not _ft:
                    _ft = getattr(_w, "fire_timer", 0) if _w is not None else 0
                pfire = float(np.clip(_ft / 3.0, 0, 1))
                obs += [pvx, pvy, pfx, pfy, pfire]
            except Exception:
                obs += [0.0, 0.0, 0.0, 0.0, 0.0]
        return np.array(obs, dtype=np.float32)

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
        """返回 (vx, vy, attack)；缓存命中直接返回；过期则标记待批处理并返回上次动作。
        真正的推理由主循环每帧 flush_batch() 批量执行（一帧一次矩阵前向，argmax 确定性）。
        不可用/首帧无缓存 → (None, None, False) 回退原 AI。"""
        if not self.ready or not getattr(enemy, "rl_eligible", True):
            return None, None, False
        now = _now()
        key = id(enemy)
        hit = self._cache.get(key)
        if hit is not None and now < hit[0]:
            return hit[1], hit[2], hit[3]
        self._dirty.add(key)          # 过期 → 待批处理
        if hit is not None:
            return hit[1], hit[2], hit[3]   # 沿用上次动作直到批处理刷新
        return None, None, False

    def flush_batch(self, world=None, enemies=None, players=None):
        """主循环每帧调用：对过期敌人一次批量前向（numpy/onnx 矩阵批），argmax 确定性决策。
        - 每怪以其最近玩家为参照（单机=唯一玩家；同屏双人=各自就近）
        - 队友取同批内最近的其他存活敌人（排除自身）"""
        if not self.ready or not self._dirty:
            return
        now = _now()
        ps = list(players or [])
        ents = [e for e in (enemies or []) if id(e) in self._dirty and getattr(e, "alive", True)
                and getattr(e, "rl_eligible", True)]
        if not ents:
            self._dirty.clear()
            return
        rows = []
        for e in ents:
            p = None
            if ps:
                p = min(ps, key=lambda pl: (pl.x - e.x) ** 2 + (pl.y - e.y) ** 2)
            tm, best = None, float("inf")
            for o in ents:
                if o is e:
                    continue
                d = (o.x - e.x) ** 2 + (o.y - e.y) ** 2
                if d < best:
                    best, tm = d, o
            rows.append(self.make_obs(e, p, world, tm))
        X = self._np.vstack(rows).astype(self._np.float32)
        t0 = _now()
        try:
            if self.sess is not None:
                logits = self.sess.run(None, {self._input_name: X})[0]
            else:
                npz = self._npz
                h = self._np.tanh(X @ npz["mlp.policy_net.0.weight"].T + npz["mlp.policy_net.0.bias"])
                h = self._np.tanh(h @ npz["mlp.policy_net.2.weight"].T + npz["mlp.policy_net.2.bias"])
                logits = h @ npz["action_net.weight"].T + npz["action_net.bias"]
            acts = self._np.argmax(logits, axis=1)   # 部署标准：确定性 argmax（训练采样/部署argmax）
        except Exception:
            self._dirty.clear()
            return
        ms = (_now() - t0) * 1000.0
        for e, act in zip(ents, acts):
            act = int(act)
            # 接近保底（当前模型缺少"靠近玩家"梯度奖励，易保守原地放技能）：
            # 1) 距离>320px 且动作非移动（停止/远程技能）→ 强制朝玩家移动（有目的接近）
            # 2) 移动类动作明显背离玩家（夹角>120°）→ 纠正为朝玩家
            # 近身(<320px) 完全交给模型自由发挥（技能/走位），模型学好后自然主导
            if ps:
                p = min(ps, key=lambda pl: (pl.x - e.x) ** 2 + (pl.y - e.y) ** 2)
                pa = math.atan2(p.y - e.y, p.x - e.x)
                far = ((p.x - e.x) ** 2 + (p.y - e.y) ** 2) > 320.0 ** 2
                if far and (act == 0 or act >= 9):
                    act = int(round(pa / (math.pi / 4))) % 8 + 1
                elif 1 <= act <= 8:
                    ang = (act - 1) * (math.pi / 4)
                    dot = math.cos(ang) * math.cos(pa) + math.sin(ang) * math.sin(pa)
                    if dot < -0.5:
                        act = int(round(pa / (math.pi / 4))) % 8 + 1
            skill = self.ACT_SKILL.get(act, 0)
            if act == 0 or act >= 10:
                res = (0.0, 0.0, skill if act != 0 else 0)
            elif act == 9:
                res = (0.0, 0.0, skill)
            else:
                ang = (act - 1) * (math.pi / 4)
                res = (math.cos(ang), math.sin(ang), skill)
            self._cache[id(e)] = (now + self._DECIDE_INTERVAL, res[0], res[1], res[2])
            self.stats["decisions"] += 1
            self.stats["action_hist"][act] = self.stats["action_hist"].get(act, 0) + 1
            self.stats["total_ms"] += ms / max(len(ents), 1)
            self.stats["last_act"] = act
            if skill:
                self.stats["skill_hist"][skill] = self.stats["skill_hist"].get(skill, 0) + 1
        self._dirty.clear()
        if len(self._cache) > 1024:
            self._cache.clear()

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
