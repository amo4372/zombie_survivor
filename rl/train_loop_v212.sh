#!/bin/bash
# ============================================================
#  v2.1.2 稳定性强化长训脚本（奖励尺度归一化 + value clip + ent 保底）
#  特性：
#   1. 从 latest.zip 续训（当前种子档）
#   2. 短段 15 万步/段（崩溃前更早捕捉退化），每段落盘 latest.zip
#   3. 段末双类评估（boss + tank），取 boss 奖励跟踪最优档 best_v212.zip
#   4. 退化保护：连续 2 次评估奖励 < (最佳-12) → 回退最优档 + 终止
#      （奖励尺度已归一化 ±20，退化阈值 12 对应"差于最佳 60%"）
#   5. 持续训练直到退化终止/用户 touch rl/logs/stop.flag/手动 kill
#  用法：setsid nohup bash rl/train_loop_v212.sh >> rl/logs/train_v212.log 2>&1 &
# ============================================================
cd "$(dirname "$0")/.."
mkdir -p rl/logs
BEST="rl/models/best_v212.zip"
BEST_REWARD_FILE="rl/logs/best_v212_reward.txt"
FAIL_FILE="rl/logs/train_v212_fail.txt"
FAIL_LIMIT=2
SEG_STEPS=${TR_SEG_STEPS:-150000}

if [ ! -f "rl/models/latest.zip" ]; then
  echo "❌ 缺起点 latest.zip，先恢复好档再启动"; exit 1
fi

echo "===== v2.1.2 稳定性强化长训启动 $(date '+%F %T') | 起点 latest.zip ====="
rm -f "$FAIL_FILE" rl/logs/stop.flag
[ -f "$BEST_REWARD_FILE" ] || echo "-100000" > "$BEST_REWARD_FILE"

while true; do
  [ -f rl/logs/stop.flag ] && { echo "===== 用户停止标记 $(date '+%F %T') ====="; break; }
  echo "===== 段开始 $(date '+%F %T') | 本段 ${SEG_STEPS} 步 ====="

  python3 rl/train.py --steps "$SEG_STEPS" --checkpoint rl/models/latest.zip \
    --device cpu --no-tb --save-every 50000 --n-envs 2 \
    || { echo "⚠ 段训练异常（进程回收/资源），sleep 后重试"; sleep 10; continue; }

  # —— 段末双类评估 + 最优档跟踪 ——
  R_BOSS=$(python3 rl/train.py --eval-only --checkpoint rl/models/latest.zip \
      --eval-episodes 8 --eval-type boss 2>/dev/null \
      | grep -oE '\[RL\] boss\s*: 平均奖励\s+-?[0-9.]+' | grep -oE '\-?[0-9.]+$')
  R_TANK=$(python3 rl/train.py --eval-only --checkpoint rl/models/latest.zip \
      --eval-episodes 8 --eval-type tank 2>/dev/null \
      | grep -oE '\[RL\] tank\s*: 平均奖励\s+-?[0-9.]+' | grep -oE '\-?[0-9.]+$')
  R_BOSS=${R_BOSS:-0}; R_TANK=${R_TANK:-0}
  R=$(python3 -c "print(round(($R_BOSS + $R_TANK) / 2, 1))")
  BEST_R=$(cat "$BEST_REWARD_FILE")
  echo "  段末评估: boss=${R_BOSS} tank=${R_TANK} 均值=${R} | 历史最佳: ${BEST_R}"
  if python3 -c "exit(0 if $R > $BEST_R else 1)"; then
    cp -f rl/models/latest.zip "$BEST"
    echo "$R" > "$BEST_REWARD_FILE"
    echo "  🏆 新最佳档已保存: $BEST（奖励 $R）"
  fi
  THRESH=$(python3 -c "print($BEST_R - 12.0)")
  if python3 -c "exit(0 if $R < $THRESH else 1)"; then
    echo "$(( $(cat "$FAIL_FILE" 2>/dev/null || echo 0) + 1 ))" > "$FAIL_FILE"
    FAIL_N=$(cat "$FAIL_FILE")
    echo "  ⚠ 低于阈值 ${THRESH}（第 ${FAIL_N}/${FAIL_LIMIT} 次）"
    if [ "$FAIL_N" -ge "$FAIL_LIMIT" ]; then
      echo "⚠ 连续 ${FAIL_N} 次退化 —— 回退最优档并终止（保留全程最优）"
      if [ -f "$BEST" ]; then
        cp -f "$BEST" rl/models/latest.zip
        echo "  latest.zip 已回退为最优档 $BEST（奖励 $BEST_R）"
      fi
      echo "0" > rl/logs/abs_step.txt
      break
    fi
  else
    rm -f "$FAIL_FILE"
  fi
  sleep 5
done

echo "===== 收尾 $(date '+%F %T') ====="
python3 rl/train.py --eval-only --checkpoint rl/models/latest.zip --eval-episodes 8 --eval-type boss 2>&1 | grep -E "\[RL\] boss" | head -1
echo "===== 完成：最终模型 = rl/models/latest.zip（最优档） ====="
