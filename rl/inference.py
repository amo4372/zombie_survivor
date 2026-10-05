# -*- coding: utf-8 -*-
"""ONNX 推理模块 —— 供游戏内僵尸 AI 接入

零 torch 依赖：只用 onnxruntime 加载导出模型，输入观测向量，输出动作。

用法（游戏内接入示例，见 README）：
    from rl.inference import ZombieAI
    ai = ZombieAI("rl/models/zombie_policy.onnx")
    action = ai.choose_action(obs_vector)   # 0=停, 1-8=八向
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 动作索引 → 方向角（与训练环境一致；9=远程攻击，无移动）
ACTION_ANGLES = {0: None, 1: 0, 2: 45, 3: 90, 4: 135, 5: 180, 6: 225, 7: 270, 8: 315, 9: None}


class ZombieAI:
    def __init__(self, onnx_path, use_gpu=False):
        import onnxruntime as ort
        providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                     if use_gpu and "CUDAExecutionProvider" in ort.get_available_providers()
                     else ["CPUExecutionProvider"])
        self.sess = ort.InferenceSession(onnx_path, providers=providers)
        self.input_name = self.sess.get_inputs()[0].name
        self.obs_dim = self.sess.get_inputs()[0].shape[1]
        self.last_probs = None

    def choose_action(self, obs):
        """obs: 9 维归一化向量（或 list）→ 动作 index"""
        arr = np.asarray(obs, dtype=np.float32).reshape(1, -1)
        probs = self.sess.run(None, {self.input_name: arr})[0]
        self.last_probs = probs[0]
        return int(np.argmax(probs[0]))

    def choose_action_stochastic(self, obs, temperature=1.0):
        """带温度的随机采样（游戏内更拟人，避免机械化走位）"""
        arr = np.asarray(obs, dtype=np.float32).reshape(1, -1)
        probs = self.sess.run(None, {self.input_name: arr})[0][0].astype(np.float64)
        p = np.clip(probs, 1e-9, None)
        p = p ** (1.0 / max(temperature, 0.1))
        p /= p.sum()
        self.last_probs = p
        return int(np.random.choice(len(p), p=p))

    def move_vector(self, obs, temperature=1.0):
        """动作 → (vx, vy, is_attack)。9=远程攻击（原地，游戏内触发技能）"""
        act = self.choose_action_stochastic(obs, temperature)
        ang = ACTION_ANGLES.get(act)
        if ang is None:
            return 0.0, 0.0, act == 9
        rad = np.deg2rad(ang)
        return float(np.cos(rad)), float(np.sin(rad)), False
