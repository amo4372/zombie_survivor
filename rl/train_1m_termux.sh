#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Termux 训练 100 万步脚本（obs35 纯 NumPy PPO，零 torch）
#
#  防休眠三件套：
#    1. termux-wake-lock —— 获取 CPU 唤醒锁（锁屏/熄屏照常训练）
#    2. 分段训练（4×25万）+ 每段落盘断点 —— 进程被回收可从断点自动续
#    3. 可选后台模式：BACKGROUND=1 时 setsid+nohup 后台跑，日志进 rl/logs/
#
#  用法（在 ~/zombie_survivor-main 或仓库根）:
#    bash rl/train_1m_termux.sh          # 前台，带进度
#    BACKGROUND=1 bash rl/train_1m_termux.sh   # 后台，防误关
#  测试：TR_STEPS=300 bash rl/train_1m_termux.sh
# ============================================================
set -e
cd "$(dirname "$0")/.."

STEPS_PER_SEG=${TR_STEPS:-250000}     # 每段步数（默认 25 万，共 4 段 = 100 万）
N_SEG=${TR_SEG:-4}
EVAL_EP=${TR_EVAL_EP:-5}              # 段末评估局数
LOG=rl/logs/termux_train_1m.log

# ---------- 1) 防休眠：wake lock ----------
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock && echo "🔒 CPU 唤醒锁已获取（锁屏/熄屏不暂停训练）"
  trap 'termux-wake-unlock 2>/dev/null; echo "🔓 已释放唤醒锁"' EXIT
else
  echo "⚠ 未安装 termux-api：训练中锁屏可能被系统休眠暂停"
  echo "  安装: pkg install -y termux-api  并先装 Termux:API 应用"
fi

# ---------- 2) 后台模式 ----------
if [ "${BACKGROUND:-0}" = "1" ]; then
  echo "后台模式：setsid + nohup，日志 → $LOG"
  setsid nohup bash "$0" >> "$LOG" 2>&1 < /dev/null &
  echo "已在后台启动 PID $!；查看进度：tail -f $LOG"
  exit 0
fi

echo "===== Termux 100 万步训练（${N_SEG}×${STEPS_PER_SEG}） $(date '+%F %T') ====="
python3 -c "import numpy; print('numpy', numpy.__version__)"

# ---------- 3) 分段训练（train_termux 自动从最新断点续训） ----------
for SEG in $(seq 1 "$N_SEG"); do
  echo "===== 第 ${SEG}/${N_SEG} 段（${STEPS_PER_SEG} 步，自动续训） ====="
  python3 rl/train_termux.py --steps "$STEPS_PER_SEG" --save-every "$STEPS_PER_SEG" --n-envs 2 \
    || { echo "⚠ 本段中断（系统回收/断网），再次运行本脚本即自动从断点续训"; break; }
  # 段末快速评估（记录健康度）
  python3 rl/train_termux.py --eval-only --eval-episodes "$EVAL_EP" 2>&1 | grep -E "=====|平均奖励" | head -4
done

# ---------- 4) 收尾 ----------
echo "===== 最终评估 $(date '+%F %T') ====="
python3 rl/train_termux.py --eval-only --eval-episodes "$EVAL_EP" 2>&1 | grep -E "=====|平均奖励" | head -6
ABS=$(cat rl/logs/termux_abs_step.txt 2>/dev/null || echo 0)
echo ""
echo "✅ 训练结束（绝对步数 $ABS）"
echo "  模型: rl/models/latest_termux.npz（游戏端 numpy 回退格式，可直接用）"
echo "  断点: rl/models/termux_policy_*_steps.npz"
echo "  历史: rl/logs/termux_history.jsonl"
echo "  发布进游戏包：cp rl/models/latest_termux.npz rl/models/policy_weights.npz"
echo ""
