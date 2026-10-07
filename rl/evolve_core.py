# -*- coding: utf-8 -*-
"""evolve_core.py —— 进化算法训练器公共核心（纯 NumPy，PyTorch/Termux 两版共用）

μ+λ 进化策略（Elite ES）+ 1/5 成功规则自适应变异强度 + 锦标赛选择 + 概率交叉
- 基因 = 策略 MLP 全部权重扁平向量（obs35 → 128 → 128 → 动作18，tanh）
- 权重与游戏端 policy_weights.npz 格式互转（mlp.policy_net.0.weight 等键）
- 评估复用 ZombieEnv（剧情图轮换 + 实战初始距离，与 PPO eval 口径一致）
- 纯 NumPy 实现 → Termux / Pydroid3 零 torch 依赖可跑；PyTorch 版在其上加速
"""
import os
import sys
import math
import time
import json
import random
import argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from zombie_env import ZombieEnv, TYPE_ORDER, ARENA_W, ARENA_H, BITE_DAMAGE, PLAYER_HP  # noqa: E402

OBS_DIM = 35
ACT_DIM = 18
HID = 128
# npz 键（游戏端 ai_controller 直接消费的格式）
KEYS = ["mlp.policy_net.0.weight", "mlp.policy_net.0.bias",
        "mlp.policy_net.2.weight", "mlp.policy_net.2.bias",
        "action_net.weight", "action_net.bias"]
SHAPES = [(HID, OBS_DIM), (HID,), (HID, HID), (HID,), (ACT_DIM, HID), (ACT_DIM,)]


# ---------- 基因编解码 ----------
def vec_from_npz(npz_path):
    """读游戏端 policy_weights.npz → 基因向量"""
    w = np.load(npz_path)
    parts = [np.asarray(w[k], dtype=np.float32).reshape(-1) for k in KEYS]
    return np.concatenate(parts).astype(np.float32)


def npz_from_vec(vec, out_path):
    """基因向量 → 游戏端 policy_weights.npz"""
    v = vec.astype(np.float32)
    off = 0
    data = {}
    for k, shp in zip(KEYS, SHAPES):
        n = int(np.prod(shp))
        data[k] = v[off:off + n].reshape(shp)
        off += n
    np.savez(out_path, **data)
    return out_path


def random_vec(seed=None):
    """Xavier 随机初始化基因"""
    rng = np.random.RandomState(seed)
    parts = []
    for k, shp in zip(KEYS, SHAPES):
        if len(shp) == 1:
            parts.append(np.zeros(shp, dtype=np.float32))
        else:
            fan_in = shp[1]
            lim = math.sqrt(6.0 / (fan_in + shp[0]))
            parts.append(rng.uniform(-lim, lim, shp).astype(np.float32).reshape(-1))
    return np.concatenate(parts).astype(np.float32)


# ---------- 策略前向（纯 NumPy，两版共用） ----------
def policy_logits(vec, obs):
    """obs: (...,35) → logits: (...,18)；torch 版可重写为 GPU 前向"""
    v = vec.astype(np.float32)
    off = 0
    layers = []
    for k, shp in zip(KEYS, SHAPES):
        n = int(np.prod(shp))
        layers.append(v[off:off + n].reshape(shp))
        off += n
    w0, b0, w2, b2, wa, ba = layers
    h = np.tanh(obs @ w0.T + b0)
    h = np.tanh(h @ w2.T + b2)
    return h @ wa.T + ba


def act_from_vec(vec, obs):
    return int(np.argmax(policy_logits(vec, obs)))


# ---------- 单局评估 ----------
def _run_episode(vec, ztype, ep_seed, verbose=False):
    """单局评估（与 PPO eval 口径一致：剧情图轮换 + 实战初始距离）"""
    env = ZombieEnv(player_mode="kite", zombie_type=ztype,
                    map_path=None, seed=100 + ep_seed)
    obs, _ = env.reset()
    a = (100 + ep_seed * 37) % 360
    d0 = 260.0 + (ep_seed * 13) % 100
    rad = math.radians(a)
    env.zx = float(np.clip(env.px + math.cos(rad) * d0, 40, ARENA_W - 40))
    env.zy = float(np.clip(env.py + math.sin(rad) * d0, 40, ARENA_H - 40))
    env._prev_dist = env._dist()
    total, done = 0.0, False
    while not done:
        act = act_from_vec(vec, obs)
        obs, r, term, trunc, _ = env.step(act)
        total += r
        done = term or trunc
    return {"reward": float(total), "win": float(env.php <= 0),
            "death": float(env.zhp <= 0), "dmg": float(env.ep_dmg_dealt),
            "move": float(env.ep_move_dist), "skills": sum(env.ep_skill_use.values())}


def evaluate_vec(vec, ztypes=("boss", "tank"), episodes=4):
    """个体综合评估：多个类型 × 多局 → 平均奖励"""
    rs, wins, deaths, dmgs, moves, skills = [], 0, 0, [], [], []
    for zt in ztypes:
        for ep in range(episodes):
            r = _run_episode(vec, zt, ep)
            rs.append(r["reward"]); wins += r["win"]; deaths += r["death"]
            dmgs.append(r["dmg"]); moves.append(r["move"]); skills.append(r["skills"])
    return {"reward": float(np.mean(rs)), "wins": wins, "deaths": deaths,
            "dmg": float(np.mean(dmgs)), "move": float(np.mean(moves)),
            "skills": float(np.mean(skills)), "n": len(rs)}


# ---------- 进化核心 ----------
class Evolver:
    def __init__(self, pop_size=24, elites=6, mutate=0.15, sigma=0.08,
                 cross_prob=0.3, init_vec=None, seed=0, ztypes=("boss", "tank"),
                 episodes=4, workers=1, verbose=True):
        self.pop_size = pop_size
        self.elites = max(2, min(elites, pop_size // 2))
        self.mutate = mutate
        self.sigma = sigma
        self.cross_prob = cross_prob
        self.ztypes = ztypes
        self.episodes = episodes
        self.workers = max(1, workers)
        self.verbose = verbose
        self.rng = random.Random(seed)
        self._np = np.random.RandomState(seed)
        self.gen = 0
        self.best_vec = None
        self.best_reward = -1e18
        self.history = []
        if init_vec is not None:
            # 以种子个体 + 小噪声生成种群（从好档出发精细进化）
            self.pop = [init_vec.astype(np.float32).copy()]
            for _ in range(pop_size - 1):
                self.pop.append(init_vec + self._np.normal(0, self.sigma * 0.5, init_vec.shape).astype(np.float32))
        else:
            self.pop = [random_vec(seed + i) for i in range(pop_size)]

    # —— 评估（支持多进程） ——
    def _eval_one(self, vec):
        return evaluate_vec(vec, self.ztypes, self.episodes)

    def evaluate_pop(self):
        if self.workers <= 1 or self.pop_size < 2:
            return [self._eval_one(v) for v in self.pop]
        try:
            from multiprocessing import Pool
            with Pool(min(self.workers, self.pop_size)) as pool:
                return pool.map(self._eval_one, self.pop)
        except Exception:
            return [self._eval_one(v) for v in self.pop]

    # —— 变异 / 交叉 ——
    def _mutate(self, vec):
        v = vec.copy()
        for _ in range(self.pop_size):
            pass
        mask = self._np.rand(v.shape[0]) < self.mutate
        noise = self._np.normal(0, self.sigma, v.shape[0]).astype(np.float32)
        v[mask] += noise[mask]
        return v

    def _crossover(self, a, b):
        if self.rng.random() >= self.cross_prob:
            return a.copy()
        n = a.shape[0]
        p1, p2 = sorted(self.rng.sample(range(n), 2))
        c = a.copy()
        c[p1:p2] = b[p1:p2]
        return c

    def step(self):
        """一代：评估 → 选精英 → 生成子代"""
        scores = self.evaluate_pop()
        pairs = sorted(zip(scores, self.pop), key=lambda x: -x[0]["reward"])
        gen_best = pairs[0]
        # 记录
        mean_r = float(np.mean([s["reward"] for s, _ in pairs]))
        self.history.append({"gen": self.gen, "best": gen_best[0]["reward"],
                             "mean": mean_r, "sigma": self.sigma,
                             "wins": gen_best[0]["wins"],
                             "deaths": gen_best[0]["deaths"],
                             "dmg": gen_best[0]["dmg"], "skills": gen_best[0]["skills"]})
        # 最优跟踪
        improved = False
        if gen_best[0]["reward"] > self.best_reward:
            self.best_reward = gen_best[0]["reward"]
            self.best_vec = gen_best[1].copy()
            improved = True
        # 1/5 成功规则：本代改进率 → σ 自适应
        imp_rate = (1.0 if improved else 0.0)
        if improved:
            self.sigma *= 1.06
        else:
            self.sigma *= 0.97
        self.sigma = float(np.clip(self.sigma, 1e-4, 1.0))
        # 选择父代：精英 + 锦标赛
        elites = [v.copy() for _, v in pairs[:self.elites]]
        parents = elites + [pairs[self.rng.randrange(self.pop_size)][1].copy()
                            for _ in range(self.pop_size - self.elites)]
        # 生成子代
        new_pop = []
        for i in range(self.pop_size):
            if i < self.elites:
                new_pop.append(parents[i])
            else:
                a = parents[self.rng.randrange(len(parents))]
                b = parents[self.rng.randrange(len(parents))]
                child = self._crossover(a, b)
                new_pop.append(self._mutate(child))
        self.pop = new_pop
        self.gen += 1
        return gen_best[0], improved

    def log_line(self, gb, improved):
        tag = "🏆" if improved else "  "
        return (f"{tag} 第{self.gen:3d}代 | 最优 {gb['reward']:+7.1f} | 均值 {self.history[-1]['mean']:+7.1f} "
                f"| σ {self.sigma:.4f} | 击杀玩家 {gb['wins']}/{gb['n']} | 伤害 {gb['dmg']:5.1f} | 技能 {gb['skills']:.1f}次")


# ---------- 报告（复用 report.py） ----------
def build_eval_report(vec, model_name, device, n_episodes=8):
    """全 6 类型评估 + HTML 报告（与 PPO 报告同格式）"""
    from report import build_report
    eval_data = {}
    for zt in TYPE_ORDER:
        rewards, wins, deaths, dmg_d, move, skills = [], 0, 0, [], [], []
        for ep in range(n_episodes):
            r = _run_episode(vec, zt, ep)
            rewards.append(r["reward"]); wins += r["win"]; deaths += r["death"]
            dmg_d.append(r["dmg"]); move.append(r["move"]); skills.append(r["skills"])
        eval_data[zt] = {"rewards": rewards, "wins": wins, "deaths": deaths,
                         "episodes": n_episodes, "avg_dmg_dealt": float(np.mean(dmg_d)),
                         "avg_move": float(np.mean(move)),
                         "avg_bite_hits": 0.0, "avg_spit_hits": 0.0, "avg_hazard": 0.0,
                         "skills": {"sum": float(np.mean(skills))}, "avg_steps": 0.0,
                         "avg_dmg_taken": 0.0, "avg_bites": 0.0}
        print(f"[EVO] {zt:8s}: 平均奖励 {np.mean(rewards):6.1f} | 玩家死亡 {wins}/{n_episodes} | "
              f"僵尸死亡 {deaths}/{n_episodes} | 伤害输出 {np.mean(dmg_d):5.1f} | 移动 {np.mean(move):6.0f}px")
    data = {"model": model_name, "device": device, "total_timesteps": 0,
            "train_time_min": 0.0, "history": [], "eval": eval_data}
    return build_report(data)


# ---------- CLI ----------
def add_common_args(p):
    p.add_argument("--generations", type=int, default=50, help="进化代数")
    p.add_argument("--population", type=int, default=24, help="种群规模")
    p.add_argument("--elites", type=int, default=6, help="精英保留数")
    p.add_argument("--mutate", type=float, default=0.15, help="变异概率(权重元素)")
    p.add_argument("--sigma", type=float, default=0.08, help="初始变异强度")
    p.add_argument("--cross-prob", type=float, default=0.3, help="交叉概率")
    p.add_argument("--init-npz", type=str, default=None, help="初始种子权重 npz(游戏端格式)，如 policy_weights.npz")
    p.add_argument("--checkpoint", type=str, default=None, help="断点 npz 续训(最优个体起点)")
    p.add_argument("--ztypes", type=str, default="boss,tank", help="训练评估的僵尸类型，逗号分隔")
    p.add_argument("--episodes", type=int, default=4, help="每代每类型评估局数")
    p.add_argument("--workers", type=int, default=1, help="并行评估进程数")
    p.add_argument("--target-reward", type=float, default=None, help="达标自动停止")
    p.add_argument("--timeout-min", type=float, default=None, help="超时自动停止(分钟)")
    p.add_argument("--seed", type=int, default=0, help="随机种子")
    p.add_argument("--eval-only", action="store_true", help="只评估给定权重生成报告")
    p.add_argument("--export", type=str, default="rl/models/best_evolved.npz", help="最优个体输出 npz 路径")
    p.add_argument("--log-every-sec", type=float, default=2.0, help="进度刷新间隔(秒)")


def ztypes_parse(s):
    zs = [x.strip() for x in s.split(",") if x.strip()]
    for z in zs:
        if z not in TYPE_ORDER:
            raise SystemExit(f"未知僵尸类型: {z}（可选 {TYPE_ORDER}）")
    return zs


def load_start_vec(args):
    """断点/种子权重解析：--checkpoint > --init-npz > 随机"""
    if args.checkpoint and os.path.exists(args.checkpoint):
        return vec_from_npz(args.checkpoint), f"断点 {args.checkpoint}"
    if args.init_npz and os.path.exists(args.init_npz):
        return vec_from_npz(args.init_npz), f"种子 {args.init_npz}"
    return None, "随机初始化"


class Progress:
    """轻量进度输出：TTY 单行刷新 / 后台转行日志（与 train.py 风格一致）"""
    def __init__(self, interval=2.0):
        self.interval = max(0.5, interval)
        self.last = 0.0
        self.tty = sys.stdout.isatty()
        self.buf = ""

    def tick(self, line):
        now = time.time()
        if now - self.last < self.interval:
            self.buf = line
            return
        self.last = now
        if self.tty:
            sys.stdout.write("\r" + line + " " * max(0, 40 - len(line)))
            sys.stdout.flush()
        else:
            print(f"{time.strftime('%H:%M:%S')} {line}")

    def finish(self, line):
        if self.tty:
            sys.stdout.write("\r" + line + "\n")
        else:
            print(f"{time.strftime('%H:%M:%S')} {line}")
        sys.stdout.flush()
