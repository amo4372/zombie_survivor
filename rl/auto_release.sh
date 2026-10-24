#!/bin/bash
# ============================================================
# auto_release.sh —— 混合训练新纪录自动发布
# 触发：rl/logs/release_flag.txt 存在且奖励 >= 97.0（同口径超发布档 +96.9）
# 流程：最新档导出 onnx+npz → build_release.py bump 版本 → 上传 GitHub Release
#      → 验证 updater 检测 → 清理 flag + 记录 release_done
# 用法：bash rl/auto_release.sh
# ============================================================
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
MODEL_DIR="$ROOT/rl/models"
LOG_DIR="$ROOT/rl/logs"
FLAG="$LOG_DIR/release_flag.txt"
DONE="$LOG_DIR/release_done.txt"
PAT="${ZS_RELEASE_PAT:-$(cat "$HOME/.zombie_release_pat" 2>/dev/null)}"
if [ -z "$PAT" ]; then
    log "缺少 GitHub PAT（设 ZS_RELEASE_PAT 或写 ~/.zombie_release_pat）→ 终止"
    exit 1
fi
REPO="amo4372/zombie_survivor"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(ts) $*" >> "$LOG_DIR/auto_release.log"; }

[ -f "$FLAG" ] || { log "无发布标记 → 跳过"; exit 0; }
FLAG_CONTENT=$(cat "$FLAG")
if grep -q "$FLAG_CONTENT" "$DONE" 2>/dev/null; then
    log "该标记已发布过 → 跳过: $FLAG_CONTENT"; exit 0
fi

log "===== 自动发布触发: $FLAG_CONTENT ====="
log "1/5 导出最新模型 onnx+npz（发布档更新）"
python3 rl/export_onnx.py --model "$MODEL_DIR/latest.zip" || { log "ONNX 导出失败 → 终止"; exit 1; }
python3 rl/export_weights.py || { log "npz 导出失败 → 终止"; exit 1; }

log "2/5 构建发布包（版本 bump）"
CHANGELOG=$(printf '## v2.1.2 更新内容\n1. 混合训练线：PPO+进化算法双轨并行，最优仲裁（AI 持续进化）\n2. 进化算法训练器（PyTorch/Termux 双版本）\n3. 游戏端动态决策节流（远处 AI 降频，性能优化）\n4. RL 模型更新至混合线最优档（同口径评估奖励 %.1f，超过发布档 +96.9）\n\n游戏内「检查更新」自动检测并提示升级。' "$(echo "$FLAG_CONTENT" | grep -oP 'reward=\K[0-9.+-]+')")
python3 build_release.py --bump patch --changelog "$CHANGELOG" > /tmp/auto_release_build.log 2>&1 || { log "构建失败: $(tail -3 /tmp/auto_release_build.log)"; exit 1; }
VERSION=$(cat version.txt)
ZIP="$ROOT/releases/zombie_survivor_v${VERSION}_update.zip"
[ -f "$ZIP" ] || { log "zip 缺失: $ZIP → 终止"; exit 1; }
log "构建完成: v${VERSION} ($(du -h "$ZIP" | cut -f1))"

log "3/5 上传 GitHub Release v${VERSION}"
printf '%s' "$CHANGELOG" > /tmp/auto_release_changelog.txt
BODY_JSON=$(python3 -c "import json; print(json.dumps(open('/tmp/auto_release_changelog.txt').read(), ensure_ascii=False))")
RELEASE_ID=$(curl -s -X POST "https://api.github.com/repos/$REPO/releases" \
  -H "Authorization: token $PAT" -H "Accept: application/vnd.github+json" \
  -d "{\"tag_name\":\"v${VERSION}\",\"target_commitish\":\"main\",\"name\":\"僵尸幸存者 v${VERSION}\",\"body\":$BODY_JSON,\"draft\":false,\"prerelease\":false}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))")
[ -n "$RELEASE_ID" ] || { log "Release 创建失败 → 终止"; exit 1; }
ASSET=$(curl -s -X POST "https://uploads.github.com/repos/$REPO/releases/$RELEASE_ID/assets?name=$(basename "$ZIP")" \
  -H "Authorization: token $PAT" -H "Content-Type: application/zip" \
  --data-binary @"$ZIP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('name',''))")
log "Release v${VERSION} id=${RELEASE_ID} asset=${ASSET}"

log "4/5 验证更新器检测"
CHECK=$(timeout 60 python3 -c "
import updater
r = updater.check_for_updates()
print(r[0] if r else 'NONE')" 2>/dev/null)
log "更新器检测: $CHECK（期望 v${VERSION}）"
if [ "$CHECK" != "$VERSION" ]; then
    log "⚠ 检测版本不匹配，保留 flag 待人工核查"
    exit 1
fi

log "5/5 记录完成并清理标记"
echo "$(ts) released v${VERSION} | $FLAG_CONTENT" >> "$DONE"
rm -f "$FLAG"
log "===== 自动发布完成 v${VERSION} ====="
echo "v${VERSION}" >> "$LOG_DIR/released_versions.txt"
