#!/bin/bash
# ============================================================
# train_mixed.sh —— v2.1.3 混合训练线：PPO 段 + 进化段交替 + 最优仲裁
# 每轮：PPO 15万步 → 转 npz → 进化 8 代 → 仲裁 → 升级/退化回退
# 特性：同尺度最优跟踪、退化自动回退、新纪录标记 release_flag
# 用法：bash rl/train_mixed.sh   （stop.flag 手动停；Ctrl-C 安全落盘）
# ============================================================
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
MODEL_DIR="$ROOT/rl/models"
LOG_DIR="$ROOT/rl/logs"
mkdir -p "$MODEL_DIR" "$LOG_DIR"

SEG_STEPS="${TR_SEG_STEPS:-150000}"      # PPO 段步数
EVO_GENS="${TR_EVO_GENS:-8}"             # 进化代数/段
EVO_POP="${TR_EVO_POP:-16}"
EVO_EPISODES="${TR_EVO_EPISODES:-3}"
EVO_WORKERS="${TR_EVO_WORKERS:-4}"
ZTYPES="${TR_ZTYPES:-boss,tank}"
RELEASE_THRESHOLD="${TR_RELEASE_THRESHOLD:-97.0}"   # 新纪录触发发布阈值（同口径评估，发布档基线 +96.9）
FAIL_LIMIT="${TR_FAIL_LIMIT:-2}"

ABS_FILE="$LOG_DIR/abs_step.txt"
BEST_FILE="$LOG_DIR/best_mixed_reward.txt"
FAIL_FILE="$LOG_DIR/train_mixed_fail.txt"
FLAG_FILE="$LOG_DIR/release_flag.txt"
STOP_FILE="$LOG_DIR/stop.flag"
SEG_LOG="$LOG_DIR/train_mixed.log"

abs_step() { cat "$ABS_FILE" 2>/dev/null || echo 0; }
best_reward() { cat "$BEST_FILE" 2>/dev/null || echo -1e9; }
fail_count() { cat "$FAIL_FILE" 2>/dev/null || echo 0; }

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(ts) $*" >> "$SEG_LOG"; }

log "===== v2.1.3 混合训练线启动 | PPO ${SEG_STEPS}步/段 + 进化 ${EVO_GENS}代/段 | 类型 ${ZTYPES} ====="
log "起点 latest.zip | abs=$(abs_step) | 最佳=$(best_reward)"

# 初始档保证：latest.zip 存在（缺失则从好档恢复链）
if [ ! -f "$MODEL_DIR/latest.zip" ]; then
  log "latest.zip 缺失 → 从 best_v212/发布档恢复"
  if [ -f "$MODEL_DIR/best_v212.zip" ]; then cp -f "$MODEL_DIR/best_v212.zip" "$MODEL_DIR/latest.zip";
  elif [ -f "$MODEL_DIR/best_8am.zip" ]; then cp -f "$MODEL_DIR/best_8am.zip" "$MODEL_DIR/latest.zip";
  elif [ -f "$MODEL_DIR/policy_weights.npz" ]; then python3 rl/rebuild_sb3_from_npz.py --npz "$MODEL_DIR/policy_weights.npz" -o "$MODEL_DIR/latest.zip";
  fi
fi

ROUND=0
while :; do
  [ -f "$STOP_FILE" ] && { log "手动停止 stop.flag 存在 → 退出"; break; }
  ROUND=$((ROUND + 1))
  log "===== 第 ${ROUND} 轮开始 ====="

  # 0) 备份当前档（退化回退用）
  cp -f "$MODEL_DIR/latest.zip" "$MODEL_DIR/latest_pre_mixed.zip" 2>/dev/null

  # 1) PPO 段训练（从 latest.zip 续训）
  log "--- PPO 段: ${SEG_STEPS} 步 ---"
  python3 rl/train.py --steps "$SEG_STEPS" --checkpoint "$MODEL_DIR/latest.zip" \
      --device cpu --no-tb --save-every 50000 --n-envs 2 --log-every-sec 2 \
      --ztypes "$ZTYPES" >> "$SEG_LOG" 2>&1
  ABS=$(( $(abs_step) + SEG_STEPS )); echo "$ABS" > "$ABS_FILE"
  log "PPO 段完成 → abs=${ABS}"

  # 2) PPO 档 → npz（临时 onnx → 提取权重，不碰发布档）
  python3 rl/export_onnx.py --model "$MODEL_DIR/latest.zip" -o "/tmp/mixed_ppo.onnx" >> "$SEG_LOG" 2>&1 || { log "ONNX 导出失败，跳过本轮进化，仅保留 PPO"; ABS_FILE=$ABS_FILE; }
  if [ -f /tmp/mixed_ppo.onnx ]; then
    python3 - <<'PY' >> "$SEG_LOG" 2>&1
import onnx, numpy as np
m = onnx.load("/tmp/mixed_ppo.onnx")
w = {}
for init in m.graph.initializer:
    w[init.name] = np.array(onnx.numpy_helper.to_array(init)).astype(np.float32)
np.savez("/tmp/mixed_ppo.npz", **w)
print("PPO→npz 完成:", list(w.keys())[:2], "…")
PY
  fi

  # 3) 进化段：从 PPO 档出发搜索（找更好策略）
  if [ -f /tmp/mixed_ppo.npz ]; then
    log "--- 进化段: ${EVO_GENS} 代 × ${EVO_POP} 个体 ---"
    python3 rl/evolve.py --generations "$EVO_GENS" --population "$EVO_POP" \
        --episodes "$EVO_EPISODES" --workers "$EVO_WORKERS" --sigma 0.06 \
        --init-npz /tmp/mixed_ppo.npz --ztypes "$ZTYPES" \
        --export /tmp/mixed_evo.npz --log-every-sec 2 >> "$SEG_LOG" 2>&1
    # 4) 仲裁：PPO vs 进化
    WINNER=$(python3 rl/arbiter.py --a /tmp/mixed_ppo.npz --b /tmp/mixed_evo.npz \
             --ztypes "$ZTYPES" --episodes 4 --out /tmp/mixed_win.npz 2>>"$SEG_LOG" | grep "胜者:" | awk '{print $2}')
    if [ "$WINNER" = "/tmp/mixed_evo.npz" ]; then
      log "🏆 仲裁：进化档胜出 → 重建 SB3 latest.zip"
      python3 rl/rebuild_sb3_from_npz.py --npz /tmp/mixed_win.npz -o "$MODEL_DIR/latest.zip" >> "$SEG_LOG" 2>&1
    else
      log "仲裁：PPO 档胜出（进化未超越）→ latest.zip 不变"
    fi
  fi

  # 5) 段末评估 + 最优跟踪 + 退化检测
  EVAL=$(python3 rl/evolve.py --eval-only --checkpoint /tmp/mixed_win.npz \
         --ztypes "$ZTYPES" --episodes 4 --export /dev/null 2>>"$SEG_LOG" | grep "平均奖励" | awk '{print $3}')
  if [ -z "$EVAL" ]; then EVAL="-1e9"; fi
  BEST=$(best_reward)
  log "段末评估: ${EVAL} | 历史最佳: ${BEST}"
  if python3 -c "exit(0 if float('$EVAL') > float('$BEST') else 1)"; then
    echo "$EVAL" > "$BEST_FILE"
    echo 0 > "$FAIL_FILE"
    log "🏆 新最佳 ${EVAL}（旧 ${BEST}）→ 已跟踪"
    # 新纪录显著突破 → 发布标记（供 auto_release 检测）
    if python3 -c "exit(0 if float('$EVAL') >= $RELEASE_THRESHOLD and float('$EVAL') > float('$BEST') else 1)"; then
      echo "$(ts) reward=$EVAL abs=$ABS winner=${WINNER:-ppo}" > "$FLAG_FILE"
      log "🚀 触发发布标记: $(cat "$FLAG_FILE")"
    fi
  else
    # 退化容忍：仅当明显差于最佳(>12)才计退化（评估波动正常，防止误杀）
    if python3 -c "exit(0 if float('$EVAL') < float('$BEST') - 12.0 else 1)"; then
      FAIL=$(fail_count); FAIL=$((FAIL + 1)); echo "$FAIL" > "$FAIL_FILE"
      log "退化标记 ${FAIL}/${FAIL_LIMIT}（当前 ${EVAL} vs 最佳 ${BEST}）"
      if [ "$FAIL" -ge "$FAIL_LIMIT" ]; then
        log "连续 ${FAIL} 次退化 → 回退最优档并终止"
        if [ -f "$MODEL_DIR/latest_pre_mixed.zip" ]; then
          cp -f "$MODEL_DIR/latest_pre_mixed.zip" "$MODEL_DIR/latest.zip"
        fi
        echo "连续 ${FAIL} 次退化——回退最优档并终止" > "$LOG_DIR/train_mixed_fail_done.txt"
        break
      fi
    else
      log "评估 ${EVAL} 在容忍带内（最佳 ${BEST}）→ 不计退化"
    fi
  fi

  # 6) 进程健康：本段耗时短则睡眠补足（减少回收窗口浪费）
  log "===== 第 ${ROUND} 轮完成 | abs=$(abs_step) | 最佳=$(best_reward) ====="
  sleep 10
done
log "===== 混合训练退出 | 最终 best=$(best_reward) ====="
