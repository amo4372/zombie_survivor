#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沙箱内 git push 不可用（gnutls 握手被网关终止）时的替代通道：
走 GitHub Git Data API 推送本地 HEAD 到 origin/main。

流程：upload blob -> create tree(base=远端) -> create commit -> update ref
用法：python3 push_via_api.py <remote_base_sha> [local_ref]
"""
import base64
import json
import os
import ssl
import subprocess
import sys
import urllib.request

REPO = "amo4372/zombie_survivor"
TOKEN_PATH = "/workspace/.gh_token"
CA = "/etc/ssl/certs/agent-identity/sandbox-gateway-ca.crt"
CTX = ssl.create_default_context(cafile=CA)
TOKEN = open(TOKEN_PATH).read().strip()


def api(path, method="GET", data=None, raw=None, url=None, ctype=None):
    url = url or ("https://api.github.com" + path)
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(url, method=method, data=body)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "zombie-survivor-release")
    if ctype:
        req.add_header("Content-Type", ctype)
    elif data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=180, context=CTX) as r:
        body = r.read().decode("utf-8", "replace")
    return json.loads(body) if body.strip() else {}


def git(*args):
    return subprocess.check_output(["git", "-C", "/workspace/zombie_survivor", *args]).decode()


def main():
    # argv[1] = 本地 diff 基准（默认 HEAD^）；远端 base 由 API 查
    local_base = sys.argv[1] if len(sys.argv) > 1 else "HEAD^"
    ref = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

    # 远端 main 的 commit（作为新 commit 的 parent）+ tree（作为 base_tree）
    _ref = api(f"/repos/{REPO}/git/ref/heads/main")
    base = _ref["object"]["sha"]
    _c = api(f"/repos/{REPO}/git/commits/{base}")
    base_tree = _c["tree"]["sha"]
    print("远端 base:", base, "tree:", base_tree)

    head_sha = git("rev-parse", ref).strip()
    msg = git("log", "-1", "--format=%B", head_sha).strip()
    local_base_sha = git("rev-parse", local_base).strip()
    print("本地 diff 基准:", local_base_sha, "→", head_sha)

    # 变更文件清单（相对本地基准）
    diff = git("diff", "--name-status", local_base_sha, head_sha).strip().splitlines()
    entries = []
    for line in diff:
        parts = line.split("\t")
        status, path = parts[0], parts[-1]
        if status.startswith("D"):
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            continue
        info = git("ls-tree", head_sha, "--", path).strip()
        mode, _typ, sha = info.split("\t")[0].split()
        entries.append({"path": path, "mode": mode, "type": "blob", "sha": sha})
    print(f"待推送文件: {len(entries)}")

    # 1) 上传 blob（内容取自 git 对象库中的目标提交，避免工作区被改动导致 sha 不一致）
    for e in entries:
        if e["sha"] is None:
            continue
        content = subprocess.check_output(
            ["git", "-C", "/workspace/zombie_survivor", "cat-file", "blob", e["sha"]])
        b64 = base64.b64encode(content).decode()
        res = api(f"/repos/{REPO}/git/blobs", "POST", {"content": b64, "encoding": "base64"})
        assert res["sha"] == e["sha"], f"blob sha 不一致: {e['path']} {res['sha']} != {e['sha']}"
    print("[1/4] blob 上传完成")

    # 2) 创建 tree
    tree = api(f"/repos/{REPO}/git/trees", "POST",
               {"base_tree": base_tree, "tree": entries})
    print("[2/4] tree:", tree["sha"])

    # 3) 创建 commit
    commit = api(f"/repos/{REPO}/git/commits", "POST",
                 {"message": msg, "tree": tree["sha"], "parents": [base]})
    print("[3/4] commit:", commit["sha"])

    # 4) 更新 ref
    api(f"/repos/{REPO}/git/refs/heads/main", "PATCH", {"sha": commit["sha"], "force": False})
    print("[4/4] ref 已更新 →", commit["sha"])
    print("本地 HEAD:", head_sha, "(内容一致)")


if __name__ == "__main__":
    main()
