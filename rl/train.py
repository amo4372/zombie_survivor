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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zombie_env import ZombieEnv, MAX_STEPS, PLAYER_HP, BITE_DAMAGE, make_env_factory, TYPE_ORDER

# 群体阵容：每种类型一个子环境（多僵尸共享策略 → 集体战术）
ROSTER = ["normal", "fast", "tank", "spitter"]


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
    from stable_baselines3.common.callbacks import CheckpointCallback

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
    ckpt = CheckpointCallback(save_freq=max(steps // 5, 1000), save_path="rl/models",
                              name_prefix="ppo_zombie_v2")
    print(f"[RL] 开始训练 {steps} 步 ...")
    t0 = time.time()
    model.learn(total_timesteps=steps, callback=ckpt, progress_bar=False)
    cost = time.time() - t0
    path = "rl/models/ppo_zombie_v2.zip"
    model.save(path)
    print(f"[RL] 训练完成: {steps} 步, 耗时 {cost/60:.1f} 分钟 → {path}")
    env.close()
    return path


def evaluate(model_path, n_episodes=8):
    """评估：对每种僵尸类型各跑若干集"""
    from stable_baselines3 import PPO
    model = PPO.load(model_path)
    for zt in TYPE_ORDER:
        rewards, wins, deaths, dists = [], 0, 0, []
        for ep in range(n_episodes):
            env = ZombieEnv(player_mode="kite", zombie_type=zt,
                            map_path="rl/maps/demo.zmap", seed=100 + ep)
            obs, _ = env.reset()
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
            dists.append(env.step_count)
        print(f"[RL] {zt:8s}: 平均奖励 {np.mean(rewards):6.1f} | "
              f"玩家死亡 {wins}/{n_episodes} | 僵尸死亡 {deaths}/{n_episodes} | "
              f"平均步数 {np.mean(dists):.0f}/{MAX_STEPS}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=200_000)
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--n-envs", type=int, default=4)
    ap.add_argument("--no-tb", action="store_true")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = ap.parse_args()

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if args.eval_only:
        evaluate(args.checkpoint or "rl/models/ppo_zombie_v2.zip")
        sys.exit(0)
    path = train(args.steps, args.checkpoint, args.n_envs,
                 tensorboard=not args.no_tb, device=args.device)
    evaluate(path)
