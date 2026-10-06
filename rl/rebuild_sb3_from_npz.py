#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 policy_weights.npz（发布档/好档）重建 SB3 PPO 训练断点
用途：训练断点 zip 意外覆盖/丢失后，用游戏端 npz 权重恢复可续训起点。
原理：SB3 MlpPolicy 默认 Tanh 激活、Linear [out,in] 权重 —— 与 onnx/npz 完全同构，
     策略权重直接拷贝，价值网络随机初始化（训练会快速学回）。
用法: python3 rl/rebuild_sb3_from_npz.py --npz rl/models/policy_weights.npz -o rl/models/ppo_zombie_v2_rebuilt.zip
"""
import os
import sys
import argparse
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stable_baselines3 import PPO
from zombie_env import make_env_factory

# 与 rl/train.py 相同的超参（查看 train.py 顶部）
N_STEPS = 2048
BATCH = 256
GAMMA = 0.99
GAE = 0.95
CLIP = 0.2
LR = 3e-4
ENT = 0.01


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="rl/models/policy_weights.npz")
    ap.add_argument("-o", "--out", default="rl/models/ppo_zombie_v2_rebuilt.zip")
    ap.add_argument("--obs-dim", type=int, default=35)
    ap.add_argument("--act-dim", type=int, default=18)
    args = ap.parse_args()

    d = np.load(args.npz, allow_pickle=True)
    env = make_env_factory("boss", seed_base=1)()
    model = PPO("MlpPolicy", env, n_steps=N_STEPS, batch_size=BATCH,
                gamma=GAMMA, gae_lambda=GAE, clip_range=CLIP,
                learning_rate=LR, ent_coef=ENT, verbose=0,
                policy_kwargs=dict(net_arch=[128, 128]))   # 与 onnx 两层 128 同构

    sd = model.policy.state_dict()
    mapping = [
        ("mlp_extractor.policy_net.0.weight", "mlp.policy_net.0.weight"),
        ("mlp_extractor.policy_net.0.bias", "mlp.policy_net.0.bias"),
        ("mlp_extractor.policy_net.2.weight", "mlp.policy_net.2.weight"),
        ("mlp_extractor.policy_net.2.bias", "mlp.policy_net.2.bias"),
        ("action_net.weight", "action_net.weight"),
        ("action_net.bias", "action_net.bias"),
    ]
    with torch.no_grad():
        for sb3_key, npz_key in mapping:
            arr = d[npz_key].astype(np.float32)
            t = torch.from_numpy(arr)
            assert sd[sb3_key].shape == t.shape, (sb3_key, sd[sb3_key].shape, t.shape)
            sd[sb3_key].copy_(t)
    # 一致性自检：同 obs 下 SB3 策略概率 vs numpy 前向（logits 允许数值稳定平移）
    x = np.random.RandomState(0).rand(4, args.obs_dim).astype(np.float32)
    with torch.no_grad():
        dist = model.policy.get_distribution(torch.from_numpy(x))
        sl = dist.distribution.logits.numpy()
    sb3_p = np.exp(sl - sl.max(-1, keepdims=True)); sb3_p = sb3_p / sb3_p.sum(-1, keepdims=True)
    h = np.tanh(x @ d["mlp.policy_net.0.weight"].T + d["mlp.policy_net.0.bias"])
    h = np.tanh(h @ d["mlp.policy_net.2.weight"].T + d["mlp.policy_net.2.bias"])
    np_logits = h @ d["action_net.weight"].T + d["action_net.bias"]
    e = np.exp(np_logits - np_logits.max(-1, keepdims=True)); np_p = e / e.sum(-1, keepdims=True)
    err = np.abs(sb3_p - np_p).max()
    print(f"SB3 策略概率 vs numpy 前向 最大误差 {err:.2e}")
    assert err < 1e-3, "权重重建不一致！"
    model.save(os.path.splitext(args.out)[0])
    print(f"重建完成 → {args.out}（策略权重来自 {args.npz}，价值网络随机，可续训）")


if __name__ == "__main__":
    main()
