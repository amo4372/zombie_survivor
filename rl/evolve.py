#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evolve.py —— 进化算法训练器（PyTorch 版）
- 与 evolve_termux.py 同核心，额外支持 PyTorch 张量前向 + GPU 批量加速
- 用法：
    python3 rl/evolve.py --generations 50 --population 24 --init-npz rl/models/policy_weights.npz --device cuda
    python3 rl/evolve.py --eval-only --checkpoint rl/models/best_evolved.npz   # 只测评
"""
import os
import sys
import time
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evolve_core import (OBS_DIM, ACT_DIM, Evolver, evaluate_vec, build_eval_report,
                         vec_from_npz, npz_from_vec, add_common_args, ztypes_parse,
                         load_start_vec, Progress, _run_episode)  # noqa: E402


def make_torch_policy(vec, device):
    """基因 → torch MLP（obs35→128→128→18 tanh），GPU 可用"""
    import torch
    import torch.nn as nn
    v = vec.astype("float32")
    off = 0
    shapes = [(128, OBS_DIM), (128,), (128, 128), (128,), (ACT_DIM, 128), (ACT_DIM,)]
    keys = ["w0", "b0", "w2", "b2", "wa", "ba"]
    layers = {}
    for k, shp in zip(keys, shapes):
        n = int(__import__("numpy").prod(shp))
        layers[k] = torch.tensor(v[off:off + n].reshape(shp), device=device)
        off += n

    def forward(obs):
        x = torch.as_tensor(obs, dtype=torch.float32, device=device)
        h = torch.tanh(x @ layers["w0"].T + layers["b0"])
        h = torch.tanh(h @ layers["w2"].T + layers["b2"])
        return h @ layers["wa"].T + layers["ba"]
    return forward


def main():
    p = argparse.ArgumentParser(description="僵尸AI 进化算法训练器 (PyTorch版)")
    add_common_args(p)
    p.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda", "auto"],
                   help="计算设备（进化无需梯度，cuda 用于批量前向加速）")
    args = p.parse_args()

    device = args.device
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    torch_ok = False
    try:
        import torch  # noqa: F401
        torch_ok = True
    except Exception:
        pass
    if args.device != "cpu" and not torch_ok:
        print("[EVO] PyTorch 不可用，回退 CPU NumPy 前向（建议 pip install torch）")
        device = "cpu"

    ztypes = ztypes_parse(args.ztypes)

    # ---------- eval-only ----------
    if args.eval_only:
        vec, src = load_start_vec(args)
        if vec is None:
            raise SystemExit("--eval-only 需要 --checkpoint/--init-npz 权重")
        print(f"[EVO] 评估来源: {src} | 类型: {ztypes}")
        r = evaluate_vec(vec, ztypes, args.episodes)
        print(f"[EVO] 平均奖励 {r['reward']:+.1f} | 击杀玩家 {r['wins']}/{r['n']} | "
              f"伤害 {r['dmg']:.1f} | 移动 {r['move']:.0f}px | 技能 {r['skills']:.1f}次")
        if args.export:
            npz_from_vec(vec, args.export)
            print(f"[EVO] 权重已写出: {args.export}")
        return

    # ---------- 训练 ----------
    start_vec, src = load_start_vec(args)
    ev = Evolver(pop_size=args.population, elites=args.elites, mutate=args.mutate,
                 sigma=args.sigma, cross_prob=args.cross_prob, init_vec=start_vec,
                 seed=args.seed, ztypes=ztypes, episodes=args.episodes, workers=args.workers)
    print(f"[EVO] 进化训练启动 | 种群 {args.population} | 精英 {args.elites} | σ {args.sigma} | "
          f"类型 {ztypes} | 起点: {src} | 设备 {device} | 并行 {args.workers}")
    os.makedirs(os.path.dirname(args.export), exist_ok=True)
    prog = Progress(args.log_every_sec)
    t0 = time.time()
    stop_reason = "达到代数上限"

    for g in range(args.generations):
        gb, improved = ev.step()
        prog.tick(ev.log_line(gb, improved))
        if args.target_reward is not None and ev.best_reward >= args.target_reward:
            stop_reason = f"达标(≥{args.target_reward})"
            break
        if args.timeout_min and (time.time() - t0) / 60.0 >= args.timeout_min:
            stop_reason = f"超时({args.timeout_min}分钟)"
            break
        # 每 5 代自动落盘断点
        if (g + 1) % 5 == 0 and ev.best_vec is not None:
            npz_from_vec(ev.best_vec, args.export)
            prog.tick(f"  ↳ 断点已保存: {args.export} (第{g + 1}代, 奖励 {ev.best_reward:+.1f})")

    # ---------- 收尾 ----------
    if ev.best_vec is None:
        raise SystemExit("训练异常：无有效个体")
    npz_from_vec(ev.best_vec, args.export)
    cost_min = round((time.time() - t0) / 60.0, 1)
    prog.finish(f"[EVO] 完成（{stop_reason}）| {ev.gen} 代 | {cost_min} 分钟 | 最优 {ev.best_reward:+.1f} → {args.export}")
    # 全 6 类测评报告
    try:
        build_eval_report(ev.best_vec, args.export, device, n_episodes=args.episodes)
    except Exception as e:
        print(f"[EVO] 报告生成跳过: {e}")


if __name__ == "__main__":
    main()
