#!/bin/bash
# ============================================================
#  通宵训练至 08:00 脚本（obs35 稳定性修复版）
#  特性：
#   1. 从好档 latest.zip 出发（abs 已重置 0，lr/ent 重新退火）
#   2. 分段训练（每段 30 万步，每 10 万落盘断点），循环至 2026-10-07 08:00
#   3. 段末 BOSS 评估 + 最佳档跟踪：奖励超过历史最佳 → 保存 best_8am.zip
#   4. 退化保护：连续 2 次评估奖励 < (最佳 - 15) → 回退最佳档 + 终止
#      （obs35 实测越过峰值后必崩，此机制保证"训练全程最佳档"可用）
#   5. 双保险保活：自身 while 循环 + cron 每小时巡检（train_until_8am 进程）
#  用法：setsid nohup bash rl/train_until_8am.sh >> rl/logs/train_8am.log 2>&1 &
# ============================================================
cd "$(dirname "$0")/.."
mkdir -p rl/logs
TARGET_TS=$(date -d "2026-10-07 08:00" +%s)
BEST="rl/models/best_8am.zip"
BEST_REWARD_FILE="rl/logs/best_8am_reward.txt"
FAIL_FILE="rl/logs/train_8am_fail.txt"
BASELINE=30.0      # 好档基线（发布档评估奖励 ~+30~+120）
FAIL_LIMIT=2
SEG_STEPS=${TR_SEG_STEPS:-300000}

if [ ! -f "rl/models/latest.zip" ]; then
  echo "❌ 缺起点 latest.zip，先恢复好档再启动"; exit 1
fi

echo "===== 通宵训练启动 $(date '+%F %T') | 目标 2026-10-07 08:00 | 起点 latest.zip（好档） ====="
rm -f "$FAIL_FILE"
[ -f "$BEST_REWARD_FILE" ] || echo "-100000" > "$BEST_REWARD_FILE"

while true; do
  NOW=$(date +%s)
  [ "$NOW" -ge "$TARGET_TS" ] && { echo "===== 已到 08:00 截止 $(date '+%F %T') ====="; break; }
  LEFT_MIN=$(( (TARGET_TS - NOW) / 60 ))
  echo "===== 段开始 $(date '+%F %T') | 剩余 ${LEFT_MIN} 分钟 | 本段 ${SEG_STEPS} 步 ====="

  python3 rl/train.py --steps "$SEG_STEPS" --checkpoint rl/models/latest.zip \
    --device cpu --no-tb --save-every 100000 --n-envs 2 \
    || { echo "⚠ 段训练异常（进程回收/资源），sleep 后重试"; sleep 10; continue; }

  # —— 段末评估 + 最佳档跟踪 ——
  R=$(python3 rl/train.py --eval-only --checkpoint rl/models/latest.zip \
      --eval-episodes 8 --eval-type boss 2>/dev/null \
      | grep -oE '平均奖励\s+-?[0-9.]+' | head -1 | grep -oE '\-?[0-9.]+$')
  R=${R:-0}
  BEST_R=$(cat "$BEST_REWARD_FILE")
  echo "  段末 BOSS 评估奖励: ${R} | 历史最佳: ${BEST_R}"
  if python3 -c "exit(0 if $R > $BEST_R else 1)"; then
    cp -f rl/models/latest.zip "$BEST"
    echo "$R" > "$BEST_REWARD_FILE"
    echo "  🏆 新最佳档已保存: $BEST（奖励 $R）"
  fi
  # 退化判定：连续 2 次 < (最佳 - 15) → 回退 + 终止
  THRESH=$(python3 -c "print($BEST_R - 15.0)")
  if python3 -c "exit(0 if $R < $THRESH else 1)"; then
    echo "$(( $(cat "$FAIL_FILE" 2>/dev/null || echo 0) + 1 ))" > "$FAIL_FILE"
    FAIL_N=$(cat "$FAIL_FILE")
    echo "  ⚠ 低于阈值 ${THRESH}（第 ${FAIL_N}/${FAIL_LIMIT} 次）"
    if [ "$FAIL_N" -ge "$FAIL_LIMIT" ]; then
      echo "⚠ 连续 ${FAIL_N} 次退化 —— 回退最佳档并终止（保留全程最优）"
      if [ -f "$BEST" ]; then
        cp -f "$BEST" rl/models/latest.zip
        echo "  latest.zip 已回退为最佳档 $BEST（奖励 $BEST_R）"
      fi
      echo "0" > rl/logs/abs_step.txt   # 回退后退火从头，便于下次续训
      break
    fi
  else
    rm -f "$FAIL_FILE"
  fi
  sleep 5
done

# —— 收尾：最终评估 + 导出（若截止退出且 latest 非最佳，回退最佳） ——
if [ -f "$BEST" ] && ! cmp -s "$BEST" rl/models/latest.zip; then
  echo "[收尾] 回退为最佳档（训练后期低于峰值）"
  cp -f "$BEST" rl/models/latest.zip
  echo "0" > rl/logs/abs_step.txt
fi
echo "===== 收尾评估与导出 $(date '+%F %T') ====="
python3 rl/train.py --eval-only --checkpoint rl/models/latest.zip --eval-episodes 8 --eval-type boss 2>&1 | grep -E "\[RL\] (boss|tank)" | head -2
python3 rl/export_onnx.py --model rl/models/latest.zip 2>&1 | grep -E "ONNX|一致性" | head -2
python3 rl/export_weights.py 2>&1 | tail -1
echo "===== 完成：最终模型 = rl/models/latest.zip（好档）+ onnx/npz 已导出 ====="
