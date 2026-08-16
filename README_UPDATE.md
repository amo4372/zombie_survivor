
## v4.1 更新内容

### 资源系统
- 完整的图片/音效/音乐资源支持
- 缺失资源自动使用彩色占位图或静默运行
- 启动时自动检测并报告资源加载状态

### 全局游戏记录
- 持久化存储所有游戏数据
- 详细统计：击杀、伤害、技能使用、武器收集等
- 20项成就系统
- 最近50局历史记录
- 记录查看界面（主菜单"记录"按钮）

### 音乐系统
- 菜单/游戏/尸潮/Boss/胜利/失败/结局 场景音乐
- 音量控制
- 缺失时静默运行

### 打包支持
- PyInstaller 一键打包
- 支持 Windows/Linux/macOS
- 资源文件自动打包

## 打包方法

### Windows
```bash
build.bat
```

### Linux/macOS
```bash
chmod +x build.sh
./build.sh
```

### 手动打包
```bash
pip install -r requirements.txt
pyinstaller ZombieSurvivor.spec
```

## 资源放置

将资源文件放入对应目录：
```
assets/
├── images/    # 图片文件 (.png)
├── sounds/    # 音效文件 (.wav)
└── music/     # 音乐文件 (.ogg)
```

缺失资源将自动生成占位图或静默跳过。
