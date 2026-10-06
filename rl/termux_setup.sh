#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Termux 一键配置：清华镜像源 + 安装 RL 僵尸AI训练环境
#  用法：bash rl/termux_setup.sh   （在 Termux 里执行）
#  或整段复制到 Termux 终端直接粘贴执行
# ============================================================
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " [1/4] 配置清华 Termux 镜像源"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# 兼容新旧版源的配置文件路径；域名级替换（兼容 deb [arch=all,arm] 前缀）
LIST="$PREFIX/etc/apt/sources.list"
LSTD="$PREFIX/etc/apt/sources.list.d/termux.list"
[ -f "$LSTD" ] && LIST="$LSTD"
sed -i 's@packages\.termux\.org@mirrors.tuna.tsinghua.edu.cn/termux@g' "$LIST"
# 校验是否替换成功
if grep -q "mirrors.tuna.tsinghua.edu.cn/termux" "$LIST"; then
  echo "  镜像源已就绪: $(grep -m1 '^deb' "$LIST")"
else
  echo "  ⚠ 未检测到替换，请手动执行: termux-change-repo 并选择清华源"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " [2/4] 更新软件源 & 升级系统包"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pkg update -y
pkg upgrade -y

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " [3/4] 安装 Python + pip + NumPy（官方源预编译，比 pip 快）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pkg install -y python python-pip python-numpy

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " [4/4] 安装 gymnasium（纯 Python，RL 环境标准接口）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pip install -U pip
pip install gymnasium

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✅ 全部安装完成！验证："
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -c "import numpy, gymnasium; print('  numpy    ', numpy.__version__); print('  gymnasium', gymnasium.__version__)"

echo ""
echo " 🎯 开始训练僵尸AI（示例 5 万步）："
echo "     cd <游戏目录>"
echo "     python3 rl/train_termux.py --steps 50000"
echo " 🧪 评估模型："
echo "     python3 rl/train_termux.py --eval-only --eval-episodes 8"
echo ""
