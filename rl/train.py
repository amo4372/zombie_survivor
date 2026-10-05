# -*- coding: utf-8 -*-
"""PPO 训练脚本 —— 僵尸AI 强化学习（CPU / GPU 双模式）

用法：
    python3 rl/train.py --steps 30000          # 快速验证（CPU 默认）
    python3 rl/train.py --device cpu           # 强制 CPU
    python3 rl/train.py --device cuda          # 强制 GPU（有 CUDA 时；RTX3050 可用）
    python3 rl/train.py --device auto          # 自动：有 GPU 用 GPU，否则 CPU
    python3 rl/train.py --eval-only            # 只评估已存模型

有 GPU 的机器（RTX3050）：device=cuda 训练显著加速。
"""
import os
import sys
import argparse
import time
import numpy as np
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zombie_env import ZombieEnv, MAX_STEPS, PLAYER_HP, BITE_DAMAGE, make_env_factory, TYPE_ORDER, ARENA_W, ARENA_H

# 群体阵容：每种类型一个子环境（多僵尸共享策略 → 集体战术）
ROSTER = ["normal", "fast", "tank", "spitter", "ranged", "boss"]   # v4：全部僵尸含boss+投掷怪


def build_envs(n_envs=4):
    # 手动构造 SubprocVecEnv（兼容 sb3 2.9 + gymnasium 1.0）
    from stable_baselines3.common.vec_env import SubprocVecEnv
    factories = []
    for i in range(n_envs):
        zt = ROSTER[i % len(ROSTER)]
        factories.append(make_env_factory(zt, seed_base=1000 + i * 97))
    return SubprocVecEnv(factories)


def pick_device(device):
    """auto/cpu/cuda → sb3 可用设备字符串（GPU 模式需 CUDA 可用）"""
    import torch
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        print("[RL] ⚠️ 未检测到 CUDA/GPU，回退 CPU（本机 RTX3050 需装 CUDA 版 PyTorch）")
        return "cpu"
    return device


def train(steps=200_000, checkpoint=None, n_envs=4, tensorboard=True, device="auto"):
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback

    env = build_envs(n_envs)
    dev = pick_device(device)
    print(f"[RL] 设备: {dev} | 阵容: {ROSTER}")
    tb_log = "rl/logs" if tensorboard else None
    if checkpoint and os.path.exists(checkpoint):
        print(f"[RL] 从断点续训: {checkpoint}")
        model = PPO.load(checkpoint, env=env, device=dev)
    else:
        model = PPO(
            "MlpPolicy", env,
            n_steps=512, batch_size=128, gamma=0.99, gae_lambda=0.95,
            clip_range=0.2, ent_coef=0.01, learning_rate=3e-4,
            vf_coef=0.5, max_grad_norm=0.5,
            policy_kwargs=dict(net_arch=dict(pi=[128, 128], vf=[128, 128])),
            tensorboard_log=tb_log, verbose=1, device=dev,
        )
    os.makedirs("rl/models", exist_ok=True)
    os.makedirs("rl/eval_envs", exist_ok=True)
    ckpt = CheckpointCallback(save_freq=args.save_every, save_path="rl/models",
                              name_prefix="ppo_zombie_v2")
    # eval_freq 按 update 次数计：每约 25 万 timesteps 评估一次（曲线多点，避免两点直线）
    eval_freq = max(steps // n_envs // 20, 100)
    eval_env = ZombieEnv(player_mode="kite", zombie_type="normal",
                         map_path=None, seed=42)
    eval_cb = EvalCallback(eval_env, best_model_save_path="rl/models",
                           log_path="rl/logs", eval_freq=eval_freq,
                           n_eval_episodes=3, deterministic=True)
    print(f"[RL] 开始训练 {steps} 步（每 {eval_freq} 步测评一次）...")
    t0 = time.time()
    model.learn(total_timesteps=steps, callback=[ckpt, eval_cb], progress_bar=False)
    cost = time.time() - t0
    # 保存到断点路径（续训闭环：wrapper 每次以 checkpoint 路径续跑，被杀后自动接力）
    path = checkpoint if (checkpoint and os.path.exists(os.path.dirname(checkpoint))) else "rl/models/ppo_zombie_v2.zip"
    model.save(path)
    print(f"[RL] 训练完成: {steps} 步, 耗时 {cost/60:.1f} 分钟 → {path}")
    env.close()

    # 训练过程历史 → 测评报告
    history = []
    if getattr(eval_cb, "evaluations_timesteps", None) is not None and len(eval_cb.evaluations_timesteps) > 0:
        for ts, ev in zip(eval_cb.evaluations_timesteps, eval_cb.evaluations_results):
            history.append({"step": int(ts), "mean_reward": float(np.mean(ev))})
    _gen_report(path, dev, steps, cost, history)
    return path


def _gen_report(model_path, device, steps, cost, history, n_episodes=8):
    """评估各类型 + 生成 HTML 数据报告"""
    from stable_baselines3 import PPO
    from report import build_report
    model = PPO.load(model_path)
    eval_data = {}
    for zt in TYPE_ORDER:
        rewards, wins, deaths, bites, dists = [], 0, 0, [], []
        dmg_d, dmg_t, move, bh, sh, hz = [], [], [], [], [], []
        skills = {"spit": [], "dash": [], "summon": [], "aoe": []}
        for ep in range(n_episodes):
            # 剧情图轮换（5 张随机一张），测地图泛化
            env = ZombieEnv(player_mode="kite", zombie_type=zt,
                            map_path=None, seed=100 + ep)
            obs, _ = env.reset()
            # 实战初始距离：僵尸从玩家 260~360px 随机角度出发（贴近真实战斗，
            # 避免出生点过远导致咬/吐酸/投掷全测不出）
            _a = (100 + ep * 37) % 360
            _d0 = 260.0 + (ep * 13) % 100
            _rad = math.radians(_a)
            env.zx = float(np.clip(env.px + math.cos(_rad) * _d0, 40, ARENA_W - 40))
            env.zy = float(np.clip(env.py + math.sin(_rad) * _d0, 40, ARENA_H - 40))
            env._prev_dist = env._dist()
            total, done = 0.0, False
            while not done:
                act, _ = model.predict(obs, deterministic=True)
                obs, r, term, trunc, _ = env.step(int(act))
                total += r
                done = term or trunc
            rewards.append(total)
            if env.php <= 0:
                wins += 1
            if env.zhp <= 0:
                deaths += 1
            bites.append(max(0.0, (PLAYER_HP - max(env.php, 0)) / BITE_DAMAGE))
            dists.append(env.step_count)
            dmg_d.append(env.ep_dmg_dealt); dmg_t.append(env.ep_dmg_taken)
            move.append(env.ep_move_dist); bh.append(env.ep_bite_hits)
            sh.append(env.ep_spit_hits); hz.append(env.ep_hazard_hits)
            for k in skills:
                skills[k].append(env.ep_skill_use.get(k, 0))
        eval_data[zt] = {"rewards": rewards, "wins": wins, "deaths": deaths,
                         "episodes": n_episodes, "avg_bites": float(np.mean(bites)),
                         "avg_steps": float(np.mean(dists)),
                         "avg_dmg_dealt": float(np.mean(dmg_d)),
                         "avg_dmg_taken": float(np.mean(dmg_t)),
                         "avg_move": float(np.mean(move)),
                         "avg_bite_hits": float(np.mean(bh)),
                         "avg_spit_hits": float(np.mean(sh)),
                         "avg_hazard": float(np.mean(hz)),
                         "skills": {k: float(np.mean(v)) for k, v in skills.items()}}
        print(f"[RL] {zt:8s}: 平均奖励 {np.mean(rewards):6.1f} | "
              f"玩家死亡 {wins}/{n_episodes} | 僵尸死亡 {deaths}/{n_episodes} | "
              f"伤害输出 {np.mean(dmg_d):5.1f} | 移动 {np.mean(move):6.0f}px | "
              f"技能 {sum(float(np.mean(v)) for v in skills.values()):.1f}次")
    data = {"model": model_path, "device": device,
            "total_timesteps": int(steps), "train_time_min": round(cost / 60, 1),
            "history": history, "eval": eval_data}
    return build_report(data)


def evaluate(model_path, n_episodes=8):
    """只评估（--eval-only）：跑各类型并生成报告"""
    import glob
    _gen_report(model_path, "eval", 0, 0, [], n_episodes)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=200_000)
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--n-envs", type=int, default=4)
    ap.add_argument("--no-tb", action="store_true")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--save-every", type=int, default=500_000,
                    help="CheckpointCallback 保存频率（默认每50万步，防长训中断丢失）")
    args = ap.parse_args()

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if args.eval_only:
        evaluate(args.checkpoint or "rl/models/ppo_zombie_v2.zip")
        sys.exit(0)
    path = train(args.steps, args.checkpoint, args.n_envs,
                 tensorboard=not args.no_tb, device=args.device)
    # 训练已完成（train 内部自动生成测评报告），无需重复评估
