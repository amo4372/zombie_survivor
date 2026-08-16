#!/bin/bash
# 丧尸幸存者 - 打包脚本

echo "=== 丧尸幸存者打包脚本 ==="

# 检查 Python
python --version || { echo "需要安装 Python3"; exit 1; }

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 创建 spec 文件
echo "创建 PyInstaller spec..."
pyi-makespec --onefile --windowed \
    --add-data "assets/images:assets/images" \
    --add-data "assets/sounds:assets/sounds" \
    --add-data "assets/music:assets/music" \
    --name "ZombieSurvivor" \
    --icon "assets/images/icon.ico" \
    main.py

# 打包
echo "开始打包..."
pyinstaller ZombieSurvivor.spec

echo "=== 打包完成 ==="
echo "输出目录: dist/ZombieSurvivor"
echo ""
echo "注意: 请将资源文件放入 assets/ 目录后再运行"
