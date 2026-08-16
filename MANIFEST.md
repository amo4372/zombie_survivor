# 丧尸幸存者 v4.1 - 完整文件清单

## 核心文件 (必须)

| 文件 | 说明 |
|------|------|
| main.py | 程序入口，含打包资源路径支持 |
| game.py | 主游戏逻辑，集成资源管理和记录系统 |
| renderer.py | 渲染系统，含记录查看界面 |
| config.py | 配置常量，含RECORDS状态 |
| assets.py | 资源管理器（图片/音效/音乐） |
| records.py | 全局游戏记录系统 |

## 游戏模块

| 文件 | 说明 |
|------|------|
| entities.py | 玩家、敌人、经验球实体 |
| weapons.py | 武器系统（13种武器） |
| skills.py | 技能系统（18种技能） |
| ui.py | UI组件（按钮、摇杆、粒子等） |
| world.py | 游戏世界、尸潮管理 |
| dialogue.py | 对话系统 |
| skill_wheel.py | 技能/武器轮盘 |
| logger.py | 日志系统 |

## 资源目录

```
assets/
├── images/          # 68个图片槽位（详见ASSETS.md）
│   ├── menu_bg.png
│   ├── player.png
│   ├── zombie_*.png (12种)
│   ├── item_*.png (6种)
│   ├── weapon_*.png (13种)
│   ├── skill_*.png (17种)
│   ├── ui_*.png (6个)
│   ├── tile_*.png (5个)
│   └── fx_*.png (8个)
├── sounds/          # 63个音效槽位
│   ├── shoot_*.wav (11种武器)
│   ├── skill_*.wav (17种技能)
│   ├── zombie_*.wav (4种)
│   ├── boss_*.wav (2种)
│   ├── ui_*.wav (4种)
│   ├── player_*.wav (4种)
│   └── *.wav (其他交互音效)
└── music/           # 7首背景音乐
    ├── menu_theme.ogg
    ├── gameplay_theme.ogg
    ├── horde_theme.ogg
    ├── boss_theme.ogg
    ├── victory_theme.ogg
    ├── gameover_theme.ogg
    └── ending_theme.ogg
```

## 打包文件

| 文件 | 说明 |
|------|------|
| build.sh | Linux/macOS 打包脚本 |
| build.bat | Windows 打包脚本 |
| ZombieSurvivor.spec | PyInstaller 配置文件 |
| requirements.txt | Python 依赖 |

## 文档

| 文件 | 说明 |
|------|------|
| README.md | 原始说明文档 |
| README_UPDATE.md | v4.1 更新说明 |
| ASSETS.md | 完整资源清单 |

## 数据文件（运行时生成）

| 文件 | 说明 |
|------|------|
| config.json | 游戏配置 |
| game_records.json | 全局游戏记录 |
| game_log.txt | 运行日志 |

## 打包步骤

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 放置资源（可选）
将图片/音效/音乐文件放入 `assets/` 对应目录。
缺失资源将自动使用占位图或静默运行。

### 3. 执行打包

**Windows:**
```bash
build.bat
```

**Linux/macOS:**
```bash
./build.sh
```

**手动:**
```bash
pyinstaller ZombieSurvivor.spec
```

### 4. 输出
打包后的可执行文件位于 `dist/` 目录：
- Windows: `dist/ZombieSurvivor.exe`
- Linux/macOS: `dist/ZombieSurvivor`

## 资源缺失处理

- **图片缺失**: 自动生成彩色占位图，带文字标识
- **音效缺失**: 静默跳过，不影响游戏
- **音乐缺失**: 静默跳过，不影响游戏
- 启动时自动检测并报告资源加载状态

## 全局记录系统

### 记录内容
- 总游戏次数、总时长
- 最高分数/等级/存活时间
- 总击杀/死亡/升级/技能使用
- 12种敌人击杀统计
- 13种武器使用统计
- 18种技能使用统计
- 6种结局达成统计
- 最近50局详细历史
- 20项成就系统

### 查看记录
主菜单点击"记录"按钮进入记录查看界面，可查看：
- 基础统计
- 成就列表
- 最近游戏历史
