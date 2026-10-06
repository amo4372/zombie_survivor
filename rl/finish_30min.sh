#!/bin/bash
# v2.0.19 30分钟训练收尾：终止训练 → 评估 → 导出最终模型
cd /home/user/zombie_survivor
sleep 1740   # 29分钟后开始收尾（留1分钟余量）
echo "===== 30分钟窗口到，开始收尾 $(date '+%F %T') ====="
pkill -9 -f "rl/train.py" 2>/dev/null
pkill -9 -f train_until.sh 2>/dev/null
sleep 3
echo "0" > rl/logs/stop.flag
python3 rl/train.py --eval-only --checkpoint rl/models/latest.zip --eval-episodes 12 2>&1 | tail -30 > rl/logs/final_eval_30min.log
python3 rl/export_onnx.py --model rl/models/latest.zip 2>&1 | tail -4 >> rl/logs/final_eval_30min.log
python3 rl/export_weights.py 2>&1 | tail -4 >> rl/logs/final_eval_30min.log
echo "===== 收尾完成 $(date '+%F %T') ====="
