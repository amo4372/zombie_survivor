#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 main 分支代码同步到当前 version.txt 版本（只更新代码/文档，assets 保留仓库原样）。

用 Git Data API：blob → tree(base_tree) → commit → update ref，
无需 clone 整个仓库，也不会动 assets（图片/音效/音乐在仓库里本来就有）。
"""
import os
import sys
import json
import base64
import zipfile
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
VER = open(os.path.join(ROOT, "version.txt"), encoding="utf-8").read().strip()
ZIP = os.path.join(ROOT, "releases", "zombie_survivor_v%s_update.zip" % VER)
PREFIX = "zombie_survivor_v%s/" % VER
TOKEN = os.environ.get("GH_TOKEN", "")
BASE = "https://api.github.com/repos/amo4372/zombie_survivor/git"

SKIP_FILES = {"config.json", "game_data.db", "game_data.json", "game_records.json",
              "broken_versions.json", ".db_edit_mode", "codex_unlocks.json",
              "mods_config.json", "skill_tree_unlock.json", "savegame.json",
              "savegame.zss", "game_log.txt"}
SKIP_PREFIX = ("_update_cache", "_update_backup", "__pycache__", "releases",
               "dist_encrypted", "replays", "_vendor")


def req(path, method="GET", payload=None, timeout=60):
    url = path if path.startswith("http") else BASE + path
    h = {"Authorization": "Bearer " + TOKEN,
         "Accept": "application/vnd.github+json",
         "User-Agent": "zombie-survivor-sync/" + VER,
         "Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def main():
    if not TOKEN:
        print("缺少 GH_TOKEN"); return 1
    # 1) main 当前 commit / tree
    ref = req("/ref/heads/main")
    old_commit = ref["object"]["sha"]
    c = req("/commits/" + old_commit)
    old_tree = c["tree"]["sha"]
    print("[main] commit=%s tree=%s" % (old_commit[:8], old_tree[:8]))

    # 2) 收集要同步的本地代码文件（来自已校验的发布包，去掉前缀）
    z = zipfile.ZipFile(ZIP)
    todo = []
    for name in z.namelist():
        if not name.startswith(PREFIX) or name.endswith("/"):
            continue
        rel = name[len(PREFIX):]
        # v2.9.18：按项目原画风重画的 8 张新增类别贴图需要进仓库
        # （v2.9.17 的 assets/images/zombies/ 子目录已废弃并删除）
        _new_sprites = {
            "assets/images/zombie_hunter.png", "assets/images/zombie_bomber.png",
            "assets/images/zombie_frost.png", "assets/images/zombie_venom.png",
            "assets/images/zombie_berserker.png", "assets/images/zombie_ghoul.png",
            "assets/images/zombie_shaman.png", "assets/images/zombie_juggernaut.png",
        }
        if (rel.startswith("assets/") and rel not in _new_sprites) \
                or rel in SKIP_FILES or rel.startswith(SKIP_PREFIX):
            continue
        todo.append((rel, z.read(name)))
    print("[收集] %d 个代码/文档文件（assets 保留仓库原样）" % len(todo))

    # 3) 创建 blobs
    entries = []
    for i, (rel, data) in enumerate(todo):
        try:
            b = req("/blobs", "POST",
                    {"content": base64.b64encode(data).decode("ascii"),
                     "encoding": "base64"})
            entries.append({"path": rel, "mode": "100644",
                            "type": "blob", "sha": b["sha"]})
        except Exception as e:
            print("  [WARN] blob 失败 %s: %s" % (rel, e))
        if (i + 1) % 40 == 0:
            print("  ... %d/%d" % (i + 1, len(todo)))
    print("[blob] 成功 %d/%d" % (len(entries), len(todo)))
    if not entries:
        return 1

    # 3.5) v2.9.22：网络联机代码已完全移除，同步删除 main 上残留的历史联机文件。
    # Git Trees API 中 sha=null 表示删除该 blob；只对发布包里已不存在的旧路径生效。
    import re as _re
    _stale_re = _re.compile(
        r"(^|/)(net\.py(\.bak_\w+)?|net_[a-z0-9_]+\.py|"
        r"mix_net[a-z0-9_]*\.py|draw_net[a-z0-9_]*\.py|"
        r"NETWORK_[A-Z_]+\.md|lan_selftest\.py|"
        r"smoke_v\d+_net[a-z0-9_]*\.py)$", _re.I)
    # v2.9.23：游戏内编辑器已删除；rl/map_editor.py 是独立旧工具，必须保留
    _removed_editors = {"zombie_pkg/map_editor.py",
                        "renderer_pkg/draw_map_editor.py"}
    try:
        _ot = req("/trees/%s?recursive=1" % old_tree)
        _local = {_r for _r, _ in todo}
        for _it in _ot.get("tree", []):
            _p = _it.get("path", "")
            if _it.get("type") != "blob" or _p in _local:
                continue
            if not (_p in _removed_editors or _stale_re.search(_p)):
                continue
            entries.append({"path": _p, "mode": "100644", "type": "blob", "sha": None})
            print("  [删除残留联机文件] " + _p)
    except Exception as _e:
        print("  [WARN] 残留联机文件检查失败:", _e)

    # 4) 新 tree（基于旧 tree，覆盖同名、新增新文件）
    t = req("/trees", "POST", {"base_tree": old_tree, "tree": entries})
    print("[tree] 新 tree=%s" % t["sha"][:8])

    # 5) 新 commit（说明从本版更新日志标题自动生成，不再写死上一版内容）
    _msg = "v%s 源码同步" % VER
    try:
        _cl = os.path.join(ROOT, "releases", "changelog_v%s.md" % VER)
        if os.path.isfile(_cl):
            _title = open(_cl, encoding="utf-8").readline().strip().lstrip("# ").strip()
            if _title:
                _msg = "v%s 源码同步：%s" % (VER, _title[:80])
    except Exception:
        pass
    nc = req("/commits", "POST", {
        "message": _msg,
        "tree": t["sha"], "parents": [old_commit]})
    print("[commit] %s" % nc["sha"][:8])

    # 6) 推进 main
    req("/refs/heads/main", "PATCH", {"sha": nc["sha"], "force": False})
    chk = req("/ref/heads/main")
    print("[校验] main ->", chk["object"]["sha"][:8])
    ok = chk["object"]["sha"] == nc["sha"]
    print("[结果]", "OK" if ok else "异常")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
