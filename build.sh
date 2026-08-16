#!/bin/bash
# 丧尸幸存者 - Linux/macOS 打包脚本（不内嵌资源，仅打包二进制）
set -e
echo "=== 丧尸幸存者打包脚本 ==="
# 检查 Python
python3 --version || { echo "需要安装 Python3"; exit 1; }
# 安装依赖
echo "安装依赖..."
pip3 install -r requirements.txt
# 安装 PyInstaller
pip3 install pyinstaller
# 清理旧的构建文件
rm -rf build dist ZombieSurvivor.spec
# 打包（仅二进制，资源文件放在可执行文件同级的assets目录）
echo "开始打包..."
pyinstaller --onefile --windowed --name "ZombieSurvivor" main.py
echo "=== 打包完成 ==="
echo "输出目录: dist/ZombieSurvivor"
echo ""
echo "重要: 请将 assets/ 目录复制到 dist/ 下，与可执行文件同级"
echo "目录结构:"
echo "  dist/"
echo "    ZombieSurvivor"
echo "    assets/"
echo "      images/"
echo "      sounds/"
echo "      music/"
