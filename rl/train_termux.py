#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Termux 兼容 RL 训练器 —— 纯 NumPy PPO（零 torch / stable-baselines3 依赖）

为什么存在：云端/PC 用 SB3+torch 训练（rl/train.py）；但 Android Termux 上
torch/SB3 体积大、安装难、内存吃紧。本训练器只依赖 numpy + gymnasium（纯 Python），
用 NumPy 手写 PPO（GAE + clip + entropy 退火 + 解析反向传播），手机 CPU 即可跑。

产物格式：与游戏端 numpy 回退推理完全一致（mlp.policy_net.0.weight 等 key，
见 export_weights.py）——训练出的 npz 可直接放入发布包，游戏端自动加载。

用法（Android Termux）:
    pkg update && pkg install python python-pip -y
    pip install numpy gymnasium
    # 训练 5 万步（从零）
    python3 rl/train_termux.py --steps 50000
    # 断点续训（自动从最新断点恢复）
    python3 rl/train_termux.py --steps 50000
    # 指定断点续训
    python3 rl/train_termux.py --steps 50000 --checkpoint rl/models/latest_termux.npz
    # 只评估
    python3 rl/train_termux.py --eval-only --checkpoint rl/models/latest_termux.npz

产物:
    rl/models/latest_termux.npz            # 最新策略（游戏端兼容格式）
    rl/models/termux_policy_<steps>_steps.npz
    rl/logs/termux_history.jsonl           # step/mean_reward 训练曲线
"""
import os
import sys
import json
import time
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zombie_env import ZombieEnv, MAX_STEPS, TYPE_ORDER, make_env_factory, TRAIN_MAPS

# ---------- 常量（与 SB3 版 train.py 对齐，obs35 / 动作18） ----------
OBS_DIM = 35
ACT_DIM = 18
HID = 128
GAMMA, LAMBDA, CLIP = 0.99, 0.95, 0.2
LR0, LR_MIN = 3e-4, 5e-5
ENT0, ENT_MIN = 0.01, 0.003
TOTAL_TARGET = 5_000_000          # 学习率/熵退火按绝对步数进度
EPOCHS, BATCH, N_ENVS = 3, 256, 2
SAVE_EVERY = 10000                # 手机训练默认 1 万步一存
EVAL_EPISODES = 8
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def _mkdir(p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _abs_file():
    return _mkdir(os.path.join(_LOG_DIR, "termux_abs_step.txt"))


def _hist_file():
    return _mkdir(os.path.join(_LOG_DIR, "termux_history.jsonl"))


def read_abs():
    try:
        return int(open(_abs_file()).read().strip() or "0")
    except Exception:
        return 0


def write_abs(v):
    with open(_abs_file(), "w") as f:
        f.write(str(v))


def latest_npz():
    if os.path.exists(os.path.join(_MODEL_DIR, "latest_termux.npz")):
        return os.path.join(_MODEL_DIR, "latest_termux.npz")
    cands = [os.path.join(_MODEL_DIR, f) for f in os.listdir(_MODEL_DIR)
             if f.startswith("termux_policy_") and f.endswith("_steps.npz")]
    return max(cands, key=os.path.getmtime) if cands else None


# ---------- NumPy 策略网络（前向与游戏端 numpy 回退完全一致） ----------
class NPPolicy:
    """两层 tanh MLP：obs -> [128,128] -> action logits + value"""
    def __init__(self, obs=OBS_DIM, act=ACT_DIM, hid=HID):
        self.o, self.a, self.h = obs, act, hid
        self.W0 = (np.random.randn(hid, obs) * np.sqrt(2.0 / obs)).astype(np.float32)
        self.b0 = np.zeros(hid, np.float32)
        self.W2 = (np.random.randn(hid, hid) * np.sqrt(2.0 / hid)).astype(np.float32)
        self.b2 = np.zeros(hid, np.float32)
        self.Wa = (np.random.randn(act, hid) * 0.01).astype(np.float32)
        self.ba = np.zeros(act, np.float32)
        self.Wv = (np.random.randn(hid) * 0.01).astype(np.float32)
        self.bv = np.zeros(1, np.float32)

    def forward(self, x):
        """x: (N, obs) -> (logits, value, h1, h2)"""
        h1 = np.tanh(x @ self.W0.T + self.b0)
        h2 = np.tanh(h1 @ self.W2.T + self.b2)
        logits = h2 @ self.Wa.T + self.ba
        value = h2 @ self.Wv + self.bv
        return logits, value, h1, h2

    def probs(self, logits):
        m = logits.max(axis=-1, keepdims=True)
        e = np.exp(logits - m)
        return e / e.sum(axis=-1, keepdims=True)

    def act(self, x):
        logits, _, _, _ = self.forward(x)
        p = self.probs(logits)
        acts = np.array([np.random.choice(self.a, p=pp) for pp in p])
        logp = np.log(p[np.arange(len(acts)), acts] + 1e-12)
        return acts, logp, logits, p

    def save(self, path):
        np.savez(path, **{
            "mlp.policy_net.0.weight": self.W0, "mlp.policy_net.0.bias": self.b0,
            "mlp.policy_net.2.weight": self.W2, "mlp.policy_net.2.bias": self.b2,
            "action_net.weight": self.Wa, "action_net.bias": self.ba,
            "value_net.weight": self.Wv, "value_net.bias": self.bv})

    @classmethod
    def load(cls, path, obs=OBS_DIM, act=ACT_DIM, hid=HID):
        d = np.load(path, allow_pickle=True)
        p = cls(obs, act, hid)
        p.W0 = d["mlp.policy_net.0.weight"].astype(np.float32)
        p.b0 = d["mlp.policy_net.0.bias"].astype(np.float32)
        p.W2 = d["mlp.policy_net.2.weight"].astype(np.float32)
        p.b2 = d["mlp.policy_net.2.bias"].astype(np.float32)
        p.Wa = d["action_net.weight"].astype(np.float32)
        p.ba = d["action_net.bias"].astype(np.float32)
        p.Wv = d["value_net.weight"].astype(np.float32)
        p.bv = d["value_net.bias"].astype(np.float32)
        return p


# ---------- 观测 / 动作映射（obs35 / 动作18，与 SB3 版一致） ----------
def make_obs(env):
    return env._get_obs().astype(np.float32)


def collect_rollout(envs, pol, steps):
    obs_list, act_list, logp_list, val_list, rew_list, done_list = [], [], [], [], [], []
    obs = [make_obs(e) for e in envs]
    dones = [True] * len(envs)
    total_rew = 0.0
    for _ in range(steps):
        x = np.stack(obs)
        acts, logp, _, _ = pol.act(x)
        _, vals, _, _ = pol.forward(x)
        for i, e in enumerate(envs):
            if dones[i]:
                obs[i] = e.reset()[0].astype(np.float32)
            ns, r, done, *_ = e.step(int(acts[i]))
            obs[i] = ns.astype(np.float32) if isinstance(ns, np.ndarray) else make_obs(e)
            obs_list.append(obs[i].copy())
            act_list.append(int(acts[i]))
            logp_list.append(float(logp[i]))
            val_list.append(float(vals[i]))
            rew_list.append(float(r))
            done_list.append(bool(done))
            total_rew += float(r)
            dones[i] = done
    # GAE(lambda)
    N = len(rew_list)
    adv = np.zeros(N, np.float32)
    last_adv = 0.0
    for t in range(N - 1, -1, -1):
        nval = 0.0 if done_list[t] else (val_list[t + 1] if t + 1 < N else 0.0)
        delta = rew_list[t] + GAMMA * nval - val_list[t]
        last_adv = delta + GAMMA * LAMBDA * (0.0 if done_list[t] else last_adv)
        adv[t] = last_adv
    ret = np.array(val_list, np.float32) + adv
    return (np.stack(obs_list), np.array(act_list, np.int64),
            np.array(logp_list, np.float32), adv, ret, total_rew)


def ppo_update(pol, obs, acts, old_logp, adv, ret, lr, ent_coef):
    """PPO clip 更新（3 epoch mini-batch）+ 解析反向传播"""
    adv_n = (adv - adv.mean()) / (adv.std() + 1e-8)
    n = len(obs)
    idx = np.arange(n)
    losses = []
    for _ in range(EPOCHS):
        np.random.shuffle(idx)
        for s in range(0, n, BATCH):
            b = idx[s:s + BATCH]
            xb, ab = obs[b], acts[b]
            logits, vals, h1, h2 = pol.forward(xb)
            p = pol.probs(logits)
            logp = np.log(p[np.arange(len(ab)), ab] + 1e-12)
            ratio = np.exp(logp - old_logp[b])
            surr1 = ratio * adv_n[b]
            surr2 = np.clip(ratio, 1 - CLIP, 1 + CLIP) * adv_n[b]
            p_loss = -np.minimum(surr1, surr2).mean()
            v_loss = ((vals - ret[b]) ** 2).mean()
            ent = -(p * np.log(p + 1e-12)).sum(axis=-1).mean()
            loss = p_loss + 0.5 * v_loss - ent_coef * ent

            # ---- 解析梯度 ----
            Nb = len(b)
            onehot = np.zeros((Nb, pol.a), np.float32)
            onehot[np.arange(Nb), ab] = 1.0
            # dLoss/dlogits（策略）：adv * (onehot - p)（softmax 交叉熵梯度）
            g_logits = adv_n[b][:, None] * (onehot - p) / Nb
            # dLoss/dlogits（熵）：-ent_coef * ∂ent/∂z
            lp = np.log(p + 1e-12)
            ent_g = p * (1.0 + lp) - p * ((p * (1.0 + lp)).sum(axis=-1, keepdims=True))
            g_logits = g_logits - ent_coef * ent_g / Nb
            # 值函数梯度
            dv = (vals - ret[b]) / Nb          # (Nb,)
            g_Wv = h2.T @ dv                   # (128,)
            g_bv = dv.sum()
            # 回传 logits -> h2
            g_h2 = g_logits @ pol.Wa
            g_h2 += dv[:, None] * pol.Wv[None, :]
            # 回传 h2 -> h1
            g_h1 = (g_h2 * (1.0 - h2 * h2)) @ pol.W2
            g_W2 = (g_h2 * (1.0 - h2 * h2)).T @ h1
            g_b2 = (g_h2 * (1.0 - h2 * h2)).sum(axis=0)
            # 回传 h1 -> x
            g_W0 = (g_h1 * (1.0 - h1 * h1)).T @ xb
            g_b0 = (g_h1 * (1.0 - h1 * h1)).sum(axis=0)
            g_Wa = g_logits.T @ h2
            g_ba = g_logits.sum(axis=0)

            # SGD 更新（Adam-lite：简单动量）
            for prm, g in [(pol.W0, g_W0), (pol.b0, g_b0), (pol.W2, g_W2), (pol.b2, g_b2),
                           (pol.Wa, g_Wa), (pol.ba, g_ba), (pol.Wv, g_Wv), (pol.bv, g_bv)]:
                prm -= lr * g.astype(np.float32)
            losses.append((p_loss, v_loss, ent))
    pl = np.mean([x[0] for x in losses])
    vl = np.mean([x[1] for x in losses])
    en = np.mean([x[2] for x in losses])
    return float(pl), float(vl), float(en)


def eval_policy(pol, episodes=EVAL_EPISODES):
    """评估：每类型跑 episodes 局，输出击杀/伤害/技能/奖励（与 SB3 eval 同口径）"""
    out = {}
    for ti, t in enumerate(TYPE_ORDER):
        e = ZombieEnv(player_mode="kite", zombie_type=t,
                      map_path=TRAIN_MAPS[ti % len(TRAIN_MAPS)],
                      teammate=False, n_zombies=1)
        kills = deaths = dmg = moves = skills = rews = 0.0
        for _ in range(episodes):
            obs, _ = e.reset()
            ep_r = 0.0
            for _ in range(MAX_STEPS):
                acts, _, _, _ = pol.act(np.expand_dims(obs.astype(np.float32), 0))
                act0 = int(acts[0])
                obs, r, done, *_ = e.step(act0)
                ep_r += r
                skills += (1 if act0 >= 9 else 0)
                if done:
                    break
            stats = getattr(e, "ep_stats", None) or {}
            kills += (stats.get("kills", 0) if isinstance(stats, dict) else 0)
            deaths += (1 if (stats.get("player_dead", False) if isinstance(stats, dict) else False) else 0)
            dmg += getattr(e, "ep_dmg_dealt", 0.0)
            moves += getattr(e, "ep_move", 0.0)
            rews += ep_r
        out[t] = {"avg_reward": rews / episodes, "player_dead": deaths / episodes,
                  "kills": kills / episodes, "dmg": dmg / episodes,
                  "move": moves / episodes, "skills": skills / episodes}
    return out


def main():
    ap = argparse.ArgumentParser(description="Termux 兼容纯 NumPy PPO-lite 训练器")
    ap.add_argument("--steps", type=int, default=50000)
    ap.add_argument("--checkpoint", type=str, default=None)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--eval-episodes", type=int, default=EVAL_EPISODES)
    ap.add_argument("--n-envs", type=int, default=N_ENVS)
    ap.add_argument("--save-every", type=int, default=SAVE_EVERY)
    args = ap.parse_args()

    if args.eval_only:
        ck = args.checkpoint or latest_npz()
        if not ck or not os.path.exists(ck):
            raise SystemExit(f"缺模型: {ck}")
        pol = NPPolicy.load(ck)
        res = eval_policy(pol, args.eval_episodes)
        print("===== Termux 训练器评估 =====")
        for t, v in res.items():
            print(f"{t:8s}: 平均奖励 {v['avg_reward']:7.1f} | 玩家死亡 {v['player_dead']:.0%} | "
                  f"击杀 {v['kills']:.2f}/局 | 伤害 {v['dmg']:.1f} | 移动 {v['move']:.0f}px | 技能 {v['skills']:.1f}次")
        return

    abs0 = read_abs()
    ck = args.checkpoint or latest_npz()
    if ck and os.path.exists(ck):
        pol = NPPolicy.load(ck)
        print(f"[续训] 从 {ck} 恢复（绝对步数 {abs0}）")
    else:
        pol = NPPolicy()
        print("[新训] 从零初始化策略")

    envs = []
    for i, t in enumerate(TYPE_ORDER[:args.n_envs]):
        envs.append(make_env_factory(t, seed_base=1000 + i * 97)())
    print(f"环境 {len(envs)} 个（类型: {[e.ztype for e in envs]}）")

    start = time.time()
    step_abs = abs0
    target = abs0 + args.steps
    print(f"[训练] 目标 {args.steps} 步（绝对 {abs0} -> {target}）")
    while step_abs < target:
        progress = min(1.0, step_abs / TOTAL_TARGET)
        lr = max(LR0 * (1 - progress), LR_MIN)
        ent = max(ENT0 * progress, ENT_MIN)
        roll = min(args.save_every, target - step_abs)
        obs, acts, old_logp, adv, ret, total_rew = collect_rollout(envs, pol, roll)
        pl, vl, en = ppo_update(pol, obs, acts, old_logp, adv, ret, lr, ent)
        step_abs += roll
        mean_rew = total_rew / roll
        with open(_hist_file(), "a") as f:
            f.write(json.dumps({"step": step_abs, "mean_reward": round(mean_rew, 2),
                                "lr": round(lr, 6), "ent": round(ent, 5)}) + "\n")
        if step_abs % args.save_every == 0 or step_abs >= target:
            p = os.path.join(_MODEL_DIR, f"termux_policy_{step_abs}_steps.npz")
            pol.save(p)
            pol.save(os.path.join(_MODEL_DIR, "latest_termux.npz"))
            write_abs(step_abs)
            el = (time.time() - start) / 60.0
            fps = step_abs / max(el * 60, 1e-6)
            print(f"[{step_abs}] 平均奖励 {mean_rew:7.1f} | {el:.1f}min | {fps:.0f}步/秒 | "
                  f"lr {lr:.1e} | ent {ent:.4f} | ploss {pl:.2f} | vloss {vl:.2f}")
    print(f"===== 训练完成（{target} 绝对步数）=====")
    pol.save(os.path.join(_MODEL_DIR, "latest_termux.npz"))
    write_abs(target)


if __name__ == "__main__":
    main()
