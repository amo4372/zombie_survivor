#!/bin/bash
# RL 长训保活脚本 v5：起点 = latest.zip 与最新断点中较新者 > best > 从头
cd "$(dirname "$0")/.."
mkdir -p rl/logs
while true; do
  CKPT=""
  LATEST="rl/models/latest.zip"
  NEWEST_BP=$(ls -t rl/models/ppo_zombie_v2_*_steps.zip 2>/dev/null | head -1)
  if [ -n "$NEWEST_BP" ] && [ -f "$LATEST" ] && [ "$NEWEST_BP" -nt "$LATEST" ]; then
    CKPT="--checkpoint $NEWEST_BP"        # 段中被杀：断点比 latest 新
  elif [ -f "$LATEST" ]; then
    CKPT="--checkpoint $LATEST"           # 段末：latest 权威
  elif [ -n "$NEWEST_BP" ]; then
    CKPT="--checkpoint $NEWEST_BP"
  elif [ -f rl/models/best_model.zip ]; then
    CKPT="--checkpoint rl/models/best_model.zip"
  fi
  echo "===== 段开始 $(date '+%F %T') 起点:${CKPT:-从头} ====="
  python3 rl/train.py --steps 600000 $CKPT --device cpu --no-tb --save-every 200000
  echo "===== 段结束 $(date '+%F %T') ====="
  sleep 3
done
