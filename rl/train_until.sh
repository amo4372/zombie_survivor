#!/bin/bash
# RL 长训保活脚本：每段 300 万步，断点续训（latest.zip 闭环），被杀自动接力
# 用法: setsid nohup bash rl/train_until.sh >> rl/logs/train_until.log 2>&1 &
cd "$(dirname "$0")/.."
mkdir -p rl/logs
while true; do
  echo "===== 段开始 $(date '+%F %T') ====="
  python3 rl/train.py --steps 3000000 --checkpoint rl/models/latest.zip \
      --device cpu --no-tb --save-every 500000
  echo "===== 段结束 $(date '+%F %T') (latest.zip 已续存) ====="
  sleep 3
done
