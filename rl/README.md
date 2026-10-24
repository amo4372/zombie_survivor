# 僵尸AI 强化学习原型（方案C · 本地模拟器训练）

> ⚠️ 本目录为研究性原型，**不参与游戏发布/更新包**（build_release.py 显式白名单排除；模型产物已 gitignore）。
> 目的：让之后游戏里的僵尸更聪明——包抄、躲弹幕、集体夹击、个体技能差异化。

## 目录结构
```
rl/
├── map_format.py     # .zmap 二进制大地图格式（障碍物/出生点/巡逻点/出口/补给，CRC 校验）
├── map_editor.py     # GUI 地图编辑器（pygame，真机用）+ --dummy 无头链路测试
├── maps/demo.zmap    # 示例地图（田字障碍+掩体+巡逻点）
├── zombie_env.py     # Gymnasium 环境 v2：读地图+群体+个体技能
├── train.py          # PPO 训练（CPU/GPU 双模式，阵容：普通/疾速/坦克/吐酸）
├── export_onnx.py    # 导出 ONNX + 一致性验证
├── inference.py      # onnxruntime 推理（游戏内接入，零 torch 依赖）
└── README.md
```

## 地图（二进制 .zmap）
- Header `ZMAP` | 版本 | 宽高 → Tiles（0空地/1障碍/2掩体）→ 对象表（类型+x+y+半径）→ `ZEND`+CRC32
- 对象：0玩家出生点 1僵尸出生点 2巡逻点 3出口 4补给点
- 编辑器：左键画障碍、右键擦、X切换掩体、数字键0-4放对象、S保存 L加载
- RL 环境直接读取：障碍碰撞、八向射线感知、出生点/巡逻点参与

## 观测空间（19维向量，归一化）
| 段 | 含义 |
|---|---|
| 0-8 | 相对玩家 dx/dy、距离、玩家朝向 sin/cos、玩家血、自己血、横/纵墙距 |
| 9-16 | 八向障碍物射线距离（学会绕障碍） |
| 17-18 | 队友相对位置（集体包抄） |

## 动作空间（Discrete 10）
`0=停` `1-8=八向移动` `9=远程攻击`（仅吐酸有效，射程320px 投射物）

## 个体技能（类型差异化）
| 类型 | 速度 | 血量 | 咬伤 | 特性 |
|---|---|---|---|---|
| 普通 | 90 | 50 | 8 | 均衡 |
| 疾速 | 145 | 30 | 6 | 高机动绕侧 |
| 坦克 | 58 | 250 | 20 | 正面抗线 |
| 吐酸 | 82 | 40 | 5 | 远程攻击(动作9) |

## 群体战术（共享策略多智能体）
- 训练单僵尸策略；观测含"队友包抄角度"，奖励含**与队友夹角≈90° 集体夹击**
- 部署：游戏内 N 只僵尸共享同一 ONNX 策略各自决策 → 群体行为涌现

## 奖励设计（防无脑直线冲锋）
距离缩短 ±1.5 / 侧面(玩家朝向角差≈90°)持续+ / 队友夹击+ / 咬中+5 / 被击中-0.8 /
击杀玩家+50 / 自己死亡-50 / 撞墙-0.1 / 时间-0.01

## 训练（CPU/GPU 双模式）
```bash
python3 rl/train.py --steps 30000            # CPU 快速验证（3万步 ~0.4分钟）
python3 rl/train.py --device cuda --steps 500000   # GPU 正式训练（RTX3050 需 CUDA 版 PyTorch）
python3 rl/train.py --device cpu --steps 500000    # CPU 正式训练
python3 rl/train.py --eval-only              # 评估（按类型分项）
```
- `--device auto` 自动检测（有 GPU 用 cuda，无则 cpu 并提示）
- 3万步 CPU 已见类型分化：坦克 4/8 击杀率（抗线）、疾速高机动

## 导出与部署
```bash
python3 rl/export_onnx.py                    # → rl/models/zombie_policy.onnx（200/200 一致性）
```
```python
from rl.inference import ZombieAI
ai = ZombieAI("rl/models/zombie_policy.onnx")   # onnxruntime，零 torch 依赖
vx, vy, atk = ai.move_vector(obs, temperature=1.2)   # 拟人采样；atk=True 触发远程攻击
```

## TensorBoard
```bash
python3 rl/train.py --steps 200000          # 默认开启
tensorboard --logdir rl/logs
```

## 后续路线
1. 玩家脚本策略升级（掩体规避+交叉火力），逼出更高级僵尸战术
2. 接入真实游戏实体（真实障碍/武器/技能）做 sim2real 微调
3. 多僵尸同场真多智能体（Ray RLlib）或 IMPALA
4. 巡逻点引导：出生点→巡逻点→搜索玩家的行为链
