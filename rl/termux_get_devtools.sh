#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Termux 一键拉取《僵尸幸存者》完整开发者工具（gh-proxy 加速）
#  包含：游戏源码 + RL训练工具 + 地图编辑器 + 地图 + 文档
#  用法：bash rl/termux_get_devtools.sh   （或整段复制粘贴执行）
# ============================================================
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " [1/4] 安装基础依赖（unzip/curl/python/numpy）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pkg install -y python python-pip python-numpy unzip curl

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " [2/4] 安装 Python 依赖（gymnasium 纯Python；pygame 用 Termux 源）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# Termux 禁止 pip install -U pip，直接装依赖
pip install gymnasium || echo "⚠ gymnasium 安装失败请重试"
pkg install -y python-pygame || echo "⚠ python-pygame 安装失败（可后续 pkg install -y python-pygame）"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " [3/4] 通过 gh-proxy 加速下载仓库源码（含开发者工具）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd ~
ZIP="zombie_survivor_main.zip"
curl -L --retry 3 -o "$ZIP" \
  "https://gh-proxy.com/https://github.com/amo4372/zombie_survivor/archive/refs/heads/main.zip"
echo "  下载完成: $(du -h "$ZIP" | cut -f1)"
unzip -o -q "$ZIP"
rm -f "$ZIP"
DIR="zombie_survivor-main"
[ -d "$DIR" ] || DIR="zombie_survivor-main"
echo "  解压完成 → ~/$DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " [4/4] 开发者工具就绪，验证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$DIR" 2>/dev/null || exit 1
python3 -c "import numpy; print('  numpy', numpy.__version__)"
ls rl/train.py rl/train_termux.py rl/map_editor.py rl/maps/*.zmap 2>/dev/null | head -4
echo ""
echo " ✅ 工具齐备！开始训练："
echo "    cd ~/$DIR && python3 rl/train_termux.py --steps 50000"
echo " 地图编辑："
echo "    cd ~/$DIR && python3 rl/map_editor.py"
echo ""
