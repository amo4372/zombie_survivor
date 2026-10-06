#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 ONNX 模型权重为 policy_weights.npz（供 Pydroid3 等无 onnxruntime 环境纯 numpy 推理）
用法: python3 rl/export_weights.py
产物: rl/models/policy_weights.npz（进发布包；游戏端 onnxruntime 不可用时自动回退 numpy 推理）"""
import os
import numpy as np
import onnx

_ONNX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "zombie_policy.onnx")
_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "policy_weights.npz")


def main():
    if not os.path.exists(_ONNX):
        raise SystemExit(f"缺模型: {_ONNX}（先跑 train.py + export_onnx.py）")
    m = onnx.load(_ONNX)
    w = {}
    for init in m.graph.initializer:
        arr = np.array(onnx.numpy_helper.to_array(init))
        # 权重按行序存储；onnx Gemm 用 W 直接乘，SB3 权重为 [out,in]，无需转置
        w[init.name] = arr.astype(np.float32)
    np.savez(_OUT, **w)
    # 自检：前向一致（numpy vs onnxruntime）
    try:
        import onnxruntime as ort
        s = ort.InferenceSession(_ONNX)
        inp = s.get_inputs()[0].name
        obs_dim = int(s.get_inputs()[0].shape[1])  # 动态取观测维度（22/26/31 自适应）
        x = np.random.RandomState(0).rand(1, obs_dim).astype(np.float32)
        ref = s.run(None, {inp: x})[0][0]
        h = np.tanh(x @ w["mlp.policy_net.0.weight"].T + w["mlp.policy_net.0.bias"])
        h = np.tanh(h @ w["mlp.policy_net.2.weight"].T + w["mlp.policy_net.2.bias"])
        logits = h @ w["action_net.weight"].T + w["action_net.bias"]
        assert np.allclose(logits, ref, atol=1e-4), f"前向不一致: {np.abs(logits-ref).max()}"
        print(f"numpy 前向与 onnxruntime 一致（最大误差 {np.abs(logits-ref).max():.2e}）")
    except ImportError:
        print("本机无 onnxruntime，跳过自检")
    print(f"权重导出完成 → {_OUT}（{os.path.getsize(_OUT)//1024} KB）")


if __name__ == "__main__":
    main()
