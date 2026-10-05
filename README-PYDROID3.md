# 僵尸幸存者 · Pydroid3 运行说明（Android）

## 一、安装依赖（Pydroid3 → 终端，逐条执行）
```
pip install pygame-ce
pip install numpy
pip install onnxruntime        # 可选：RL 推理（装不了不影响游戏）
```
> 若 `pygame-ce` 安装失败，改用 `pip install pygame`（游戏代码兼容 pygame 2.x）。
> torch / stable-baselines3 体积过大无法在 Pydroid3 安装——**AI 训练仅限 PC**（见下）。

## 二、运行游戏
```
python main.py
```
- 触控/键控均支持；存档在 data/ 目录。
- 默认原玩法不受影响（AI_MODE=off、MAP_FILE 为空）。

## 三、RL 工具（全部支持 Pydroid3）
| 工具 | 命令 | 说明 |
|---|---|---|
| 地图编辑器(GUI) | `python rl/map_editor.py` | 编辑 .zmap 地图：B障碍 C掩体 W水 S尖刺 T树 V车 H建筑 F栅栏 D装饰；对象键 0出生 1僵尸点 2巡逻 3出口 4补给 |
| 剧情地图生成 | `python rl/gen_story_maps.py` | 一键生成 5 张剧情地图（校园/街区/市中心/郊区/核电站） |
| 地图格式工具 | `python rl/map_format.py` | .zmap 二进制读写/CRC 校验（纯标准库） |
| RL 环境测试 | `python rl/zombie_env.py` | 21 维观测/13 动作环境自测（numpy+pygame，无需 torch） |

## 四、RL 推理（需 onnxruntime + 模型文件）
- 模型 `rl/models/zombie_policy.onnx`（gitignored，未随包）——从 PC 仓库拷贝到该路径即可；
- 游戏内启用：main.py 或游戏内将 `AI_MODE=rl`、`RL_MODEL_PATH=rl/models/zombie_policy.onnx`；
- 模型缺失/onnxruntime 未装 → 自动回退原 AI，游戏正常运行。

## 五、AI 训练（仅限 PC，Pydroid3 不支持）
```
pip install gymnasium stable-baselines3 torch onnxruntime onnxscript
python rl/train.py --steps 300000 --device cpu --no-tb   # 自动输出测评报告 rl/reports/
python rl/export_onnx.py                                  # 导出 ONNX 覆盖游戏内模型
```
- 地图 5 张按剧情章节轮换；固定障碍 + 游戏随机障碍叠加（肉鸽每局不同）。

## 六、目录结构（包形式）
```
main.py            入口（不变）
game.py            Game 主循环
config.py          配置/剧情地图类型（校园→街区→市中心→郊区→核电站）
world.py           世界/障碍/区域生成
zombie_pkg/        核心逻辑（game_core/mix_playing/map_loader/ai_controller...）
entities_pkg/      玩家/敌人/投射物/武器/技能
ui_pkg/            HUD/菜单/图鉴/成就/弹窗
mod/                Mod 系统
rl/                RL 原型：地图+编辑器+环境+训练+推理+测评（训练仅 PC）
assets/            图片/音效/音乐（完整性校验 manifest）
data/              存档目录
updater.py         PC 端更新器（自动检查/校验/补缺/更新进度条）
```
