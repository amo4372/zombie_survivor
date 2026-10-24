#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建 GitHub Release 并上传更新包（沙箱内 gh 不可用，走 REST API）"""
import json
import os
import ssl
import sys
import urllib.request
import urllib.error

REPO = "amo4372/zombie_survivor"
TOKEN = open("/workspace/.gh_token").read().strip()
CTX = ssl.create_default_context(cafile="/etc/ssl/certs/agent-identity/sandbox-gateway-ca.crt")
REPO_DIR = "/workspace/zombie_survivor"


def api(path, method="GET", data=None, url=None, raw=None, ctype=None, timeout=600):
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
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            txt = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[HTTP {e.code}] {method} {url}\n{e.read().decode('utf-8','replace')[:800]}")
    return json.loads(txt) if txt.strip() else {}


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "2.5.7"
    tag = f"v{version}"
    zip_name = f"zombie_survivor_v{version}_update.zip"
    zip_path = os.path.join(REPO_DIR, "releases", zip_name)
    body = open(os.path.join(REPO_DIR, "releases", f"changelog_{tag}.md"), encoding="utf-8").read()

    rel = None
    try:
        rel = api(f"/repos/{REPO}/releases/tags/{tag}")
    except SystemExit:
        rel = None
    if rel and rel.get("id"):
        print(f"release 已存在: id={rel['id']} url={rel['html_url']}")
    else:
        rel = api(f"/repos/{REPO}/releases", "POST", {
            "tag_name": tag,
            "target_commitish": "main",
            "name": f"僵尸幸存者 v{version}",
            "body": body,
            "draft": False,
            "prerelease": False,
        })
        print(f"release 已创建: id={rel['id']} url={rel['html_url']}")

    # 上传资产（已存在同名资产则先删）
    for a in rel.get("assets", []):
        if a["name"] == zip_name:
            api(f"/repos/{REPO}/releases/assets/{a['id']}", "DELETE")
            print("已删除同名旧资产:", a["name"])

    size = os.path.getsize(zip_path)
    print(f"上传 {zip_name} ({size/1024/1024:.2f} MB) ...")
    upload_url = (f"https://uploads.github.com/repos/{REPO}/releases/{rel['id']}/assets"
                  f"?name={zip_name}")
    with open(zip_path, "rb") as f:
        data = f.read()
    asset = api(None, "POST", url=upload_url, raw=data,
                ctype="application/zip", timeout=1800)
    print("资产上传完成:", asset.get("name"), asset.get("size"), "字节")
    print("下载:", asset.get("browser_download_url"))
    print("release:", rel["html_url"])


if __name__ == "__main__":
    main()
