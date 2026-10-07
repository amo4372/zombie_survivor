#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arbiter.py —— 混合训练最优仲裁：统一口径评估两个 npz 权重，输出胜者
用法:
  python3 rl/arbiter.py --a /tmp/ppo.npz --b /tmp/evo.npz --ztypes boss,tank --episodes 4
输出: 各自平均奖励 + 胜者路径（--out 可复制胜者）
"""
import os
import sys
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evolve_core import vec_from_npz, evaluate_vec, ztypes_parse  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="混合训练最优仲裁（同口径评估双档）")
    p.add_argument("--a", required=True, help="模型A npz（如 PPO 档）")
    p.add_argument("--b", required=True, help="模型B npz（如进化档）")
    p.add_argument("--ztypes", default="boss,tank")
    p.add_argument("--episodes", type=int, default=4)
    p.add_argument("--seed", type=int, default=0, help="固定种子保证可比")
    p.add_argument("--out", default=None, help="胜者复制目标路径")
    args = p.parse_args()

    ztypes = ztypes_parse(args.ztypes)
    va, vb = vec_from_npz(args.a), vec_from_npz(args.b)
    ra = evaluate_vec(va, ztypes, args.episodes)
    rb = evaluate_vec(vb, ztypes, args.episodes)
    print(f"[ARB] A={os.path.basename(args.a)} 奖励 {ra['reward']:+.2f} (击杀 {ra['wins']}/{ra['n']})")
    print(f"[ARB] B={os.path.basename(args.b)} 奖励 {rb['reward']:+.2f} (击杀 {rb['wins']}/{rb['n']})")
    win, loser = (args.a, args.b) if ra["reward"] >= rb["reward"] else (args.b, args.a)
    print(f"[ARB] 胜者: {win}（奖励差 {abs(ra['reward'] - rb['reward']):.2f}）")
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        shutil.copyfile(win, args.out)
        print(f"[ARB] 已复制胜者 → {args.out}")
    return win


if __name__ == "__main__":
    main()
