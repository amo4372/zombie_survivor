# -*- coding: utf-8 -*-
"""导出 PPO 策略为 ONNX + 推理一致性验证

导出"观测 → 动作 logits"的纯前向网络（绕过 torch 2.x dynamo 对分布对象的限制），
onnxruntime 侧 softmax+argmax 即得动作。

用法：
    python3 rl/export_onnx.py [--model rl/models/ppo_zombie_v2.zip]
    输出: rl/models/zombie_policy.onnx
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def export(model_path, out_path=None):
    import torch
    import torch.nn as nn
    import numpy as np

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from stable_baselines3 import PPO

    model = PPO.load(model_path)
    policy = model.policy
    policy.eval()

    class PolicyNet(nn.Module):
        """观测 → 各动作 logits（纯前向，可 ONNX）"""

        def __init__(self, pol):
            super().__init__()
            self.mlp = pol.mlp_extractor
            self.action_net = pol.action_net

        def forward(self, obs):
            latent_pi, _ = self.mlp(obs)
            return self.action_net(latent_pi)  # SB3 2.9: 直接输出 logits 张量

    net = PolicyNet(policy)
    obs_dim = policy.observation_space.shape[0]
    dummy = torch.zeros((1, obs_dim), dtype=torch.float32)

    onnx_path = out_path or os.path.join(os.path.dirname(model_path), "zombie_policy.onnx")
    with torch.no_grad():
        torch.onnx.export(
            net, dummy, onnx_path,
            input_names=["obs"], output_names=["logits"],
            opset_version=12, dynamo=False,
        )
    print(f"[ONNX] 导出成功 → {onnx_path}")

    # ---- 推理一致性验证：onnxruntime vs PyTorch ----
    import onnxruntime as ort
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    ok = 0
    N = 200
    for i in range(N):
        obs = np.random.uniform(-1, 1, (1, obs_dim)).astype(np.float32)
        with torch.no_grad():
            logits = net(torch.from_numpy(obs)).detach().numpy()[0]
            pt_act = int(np.argmax(logits))
        onnx_logits = sess.run(None, {"obs": obs})[0][0]
        onnx_act = int(np.argmax(onnx_logits))
        # 数值接近性
        assert np.allclose(logits, onnx_logits, atol=1e-3), "logits 数值不一致！"
        if pt_act == onnx_act:
            ok += 1
    print(f"[ONNX] 一致性验证: {ok}/{N} 动作一致 + logits 数值一致")
    assert ok == N, "ONNX 与 PyTorch 动作不一致，导出有问题！"
    return onnx_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="rl/models/ppo_zombie_v2.zip")
    ap.add_argument("-o", "--out", default=None, help="输出 onnx 路径（默认模型同目录 zombie_policy.onnx）")
    args = ap.parse_args()
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    export(args.model, args.out)
