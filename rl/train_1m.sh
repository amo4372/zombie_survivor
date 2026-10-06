#!/bin/bash
# ============================================================
#  训练 100 万步脚本（obs35，从好档续训）
#  特性：
#   1. 4 段 × 25 万步，每段结束自动落盘断点（防中断）
#   2. 训练前自动备份好档 latest_good.zip（防覆盖）
#   3. 退化保护：每段末 BOSS 评估，连续 2 次奖励 < 30 则判定训练退化，
#      自动回退好档 + 导出最终模型并止损（obs35 已知 60 万步后易崩溃）
#   4. 强制训满：FORCE=1 bash rl/train_1m.sh（跳过退化保护）
#  用法：bash rl/train_1m.sh
# ============================================================
set -e
cd "$(dirname "$0")/.."

STEPS_PER_SEG=${TR_STEPS:-250000}     # 每段步数（测试时可 TR_STEPS=500）
N_SEG=${TR_SEG:-4}                    # 段数（100 万 = 4×25 万）
GOOD="rl/models/latest_good.zip"
CKPT="rl/models/latest.zip"
BASELINE=${TR_BASELINE:-30.0}         # 好档基线：评估奖励低于此视为退化
FAIL_LIMIT=2
FAIL_FILE="rl/logs/train_1m_fail.txt"

# 1) 备份好档（仅首次）
if [ -f "$CKPT" ] && [ ! -f "$GOOD" ]; then
  cp -f "$CKPT" "$GOOD"
  echo "✅ 好档已备份: $GOOD（后续可随时回退）"
fi
if [ ! -f "$CKPT" ]; then
  echo "❌ 缺 $CKPT，请先从发布档重建（python3 rl/rebuild_sb3_from_npz.py）"
  exit 1
fi
rm -f "$FAIL_FILE"

# 2) 分 N 段训练
echo "===== 开始训练 ${N_SEG}×${STEPS_PER_SEG} 步（目标 100 万步） $(date '+%F %T') ====="
for SEG in $(seq 1 "$N_SEG"); do
  echo "===== 第 ${SEG}/${N_SEG} 段（${STEPS_PER_SEG} 步）起点: $CKPT ====="
  python3 rl/train.py --steps "$STEPS_PER_SEG" --checkpoint "$CKPT" \
    --device cpu --no-tb --save-every "$STEPS_PER_SEG" --n-envs 2 \
    || { echo "⚠ 本段训练异常退出（网络/资源回收），保活脚本可接力续训"; break; }

  # 3) 段末 BOSS 评估（退化检测）
  if [ "${FORCE:-0}" = "1" ]; then echo "  [FORCE] 跳过退化检测"; continue; fi
  R=$(python3 rl/train.py --eval-only --checkpoint "$CKPT" --eval-episodes 8 --eval-type boss 2>/dev/null \
      | grep -oE '平均奖励\s+-?[0-9.]+' | head -1 | grep -oE '\-?[0-9.]+$')
  R=${R:-0}
  echo "  段末 BOSS 评估奖励: ${R}（基线 ${BASELINE}）"
  if python3 -c "exit(0 if $R >= $BASELINE else 1)"; then
    rm -f "$FAIL_FILE"; echo "  ✓ 健康，继续下一段"
  else
    echo "$(( $(cat "$FAIL_FILE" 2>/dev/null || echo 0) + 1 ))" > "$FAIL_FILE"
    FAIL_N=$(cat "$FAIL_FILE")
    if [ "$FAIL_N" -ge "$FAIL_LIMIT" ]; then
      echo "⚠ 连续 ${FAIL_N} 次评估低于基线 —— 训练退化，止损回退好档"
      cp -f "$GOOD" "$CKPT"
      echo "  latest.zip 已回退为好档"
      break
    fi
    echo "  ⚠ 第 ${FAIL_N} 次低于基线（${FAIL_LIMIT} 次触发止损），继续观察"
  fi
done

# 4) 收尾：评估 + 导出最终模型
echo "===== 收尾评估与导出 $(date '+%F %T') ====="
python3 rl/train.py --eval-only --checkpoint "$CKPT" --eval-episodes 8 --eval-type boss 2>&1 | grep -E "boss|tank" | head -3
python3 rl/export_onnx.py --model "$CKPT" 2>&1 | grep -E "ONNX|一致性" | head -2
python3 rl/export_weights.py 2>&1 | tail -1
echo "===== 完成：活动模型 = $CKPT（如需发布请用 build_release.py 打包）====="
