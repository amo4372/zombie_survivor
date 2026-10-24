#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evolve_termux.py —— 进化算法训练器（Termux / Pydroid3 纯 NumPy 版）
- 零第三方依赖（仅 numpy + 项目自带 zombie_env/map_format）
- 与 evolve.py 同核心同 CLI，无 PyTorch/GPU
- 用法：
    cd ~/zombie_survivor-main && python3 rl/evolve_termux.py --generations 30 --population 16 --workers 1
    python3 rl/evolve_termux.py --eval-only --checkpoint rl/models/best_evolved.npz
"""
import os
import sys
import time
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evolve_core import (Evolver, evaluate_vec, build_eval_report,
                         vec_from_npz, npz_from_vec, add_common_args, ztypes_parse,
                         load_start_vec, Progress)  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="僵尸AI 进化算法训练器 (Termux 纯NumPy版)")
    add_common_args(p)
    p.add_argument("--device", type=str, default="cpu", help="Termux 固定 cpu（参数占位）")
    args = p.parse_args()

    ztypes = ztypes_parse(args.ztypes)
    if args.workers > 1:
        print("[EVO] Termux 建议 --workers 1（multiprocessing 兼容性），本次强制 1")
        args.workers = 1

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
                 seed=args.seed, ztypes=ztypes, episodes=args.episodes, workers=1)
    print(f"[EVO] 进化训练启动(Termux) | 种群 {args.population} | 精英 {args.elites} | σ {args.sigma} | "
          f"类型 {ztypes} | 起点: {src}")
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
        if (g + 1) % 5 == 0 and ev.best_vec is not None:
            npz_from_vec(ev.best_vec, args.export)
            prog.tick(f"  ↳ 断点已保存: {args.export} (第{g + 1}代, 奖励 {ev.best_reward:+.1f})")

    if ev.best_vec is None:
        raise SystemExit("训练异常：无有效个体")
    npz_from_vec(ev.best_vec, args.export)
    cost_min = round((time.time() - t0) / 60.0, 1)
    prog.finish(f"[EVO] 完成（{stop_reason}）| {ev.gen} 代 | {cost_min} 分钟 | 最优 {ev.best_reward:+.1f} → {args.export}")
    try:
        build_eval_report(ev.best_vec, args.export, "cpu", n_episodes=args.episodes)
    except Exception as e:
        print(f"[EVO] 报告生成跳过: {e}")


if __name__ == "__main__":
    main()
