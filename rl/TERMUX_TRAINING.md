# Termux 部署 RL 训练方案（手机训练僵尸 AI）

> 适用：Android 手机 Termux。**不依赖 PyTorch / stable-baselines3**（Termux 为 bionic libc，装不了 glibc 的 torch wheel，且无 aarch64 轮子）。
> 方案：纯 NumPy 手写 PPO（GAE + clip + entropy 退火 + 解析反向传播），只依赖 numpy + gymnasium。

## 一、安装（Termux 终端）

```bash
pkg update && pkg upgrade -y
pkg install python python-pip -y
pip install numpy gymnasium        # gymnasium 为纯 Python，无编译
```

可选（加速游戏端推理，非训练必需）：
```bash
pkg install python-onnxruntime     # Termux 源有 arm64 编译好的 onnxruntime
```

## 二、训练命令

```bash
cd <游戏目录>
# 1) 从零训 5 万步（手机约 1-2 小时，视芯片而定）
python3 rl/train_termux.py --steps 50000

# 2) 断点续训（自动从最新断点恢复绝对步数）
python3 rl/train_termux.py --steps 50000

# 3) 指定模型续训
python3 rl/train_termux.py --steps 20000 --checkpoint rl/models/latest_termux.npz

# 4) 只评估（观察击杀/伤害/技能/移动，与云端测评同口径）
python3 rl/train_termux.py --eval-only --eval-episodes 8
```

## 三、产物与游戏端衔接

| 文件 | 说明 |
|---|---|
| `rl/models/latest_termux.npz` | 最新策略，**格式与游戏端 numpy 回退完全一致** |
| `rl/models/termux_policy_<步数>_steps.npz` | 每 1 万步存档 |
| `rl/logs/termux_history.jsonl` | 训练曲线（step/mean_reward/lr/ent） |

**进游戏包**：把 `latest_termux.npz` 复制为游戏根目录 `models/policy_weights.npz`，
游戏端会自动用 numpy 推理加载（无需 onnxruntime）。
若手机装了 onnxruntime，也可以先把 npz 转成 onnx（用云端的 export_onnx.py 在 PC 上转一次）。

## 四、性能预期（参考）

| 设备 | 预估步速 |
|---|---|
| 中端手机（骁龙 7 系） | 300-600 步/秒 |
| 旗舰手机（骁龙 8 系 / 天玑 9000+） | 600-1200 步/秒 |
| 云环境 2 核 CPU | ~1000 步/秒 |

1 万步 ≈ 手机 20-40 分钟。建议手机训 5-20 万步做「增量微调」，
大模型（百万级）仍推荐云端/PC 训练。

## 五、超参（与云端 SB3 版对齐）

```python
OBS_DIM=35, ACT_DIM=18, HID=128
GAMMA=0.99, LAMBDA=0.95, CLIP=0.2
LR 3e-4→5e-5 退火（按绝对 500 万步进度）
ENT 0.01→0.003 退火
EPOCHS=3, BATCH=256, N_ENVS=2
```

## 六、注意事项

1. **后台训练**：Termux 用 `tmux` 或 `termux-wake-lock` 保持屏幕常亮：
   ```bash
   pkg install tmux termux-api -y
   termux-wake-lock && tmux new -s train 'python3 rl/train_termux.py --steps 50000'
   ```
2. **内存**：策略网络仅 ~2 万参数，rollout buffer 1 万步 × 35 维 ≈ 几 MB，手机内存无压力。
3. **不要装 torch**：浪费流量且装不上（除非 proot-distro 装 Ubuntu 手动编译，不推荐）。
4. **地图文件**：训练需要 `maps/*.zmap`（已随仓库分发），缺失时自动回退随机障碍。
5. **断点**：绝对步数记录在 `rl/logs/termux_abs_step.txt`，删掉它则从零重训。
