#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动更新模块 - 从GitHub获取最新版本并热更新
支持：版本检查、下载进度条、增量更新、自动重启
"""

import os
import sys
import json
import time
import shutil
import zipfile
import tempfile
import threading
import urllib.request
import urllib.error
from pathlib import Path

# ============ 配置 ============
GITHUB_USER = "amo4372"
GITHUB_REPO = "zombie_survivor"  # 仓库名，可根据实际修改
GH_PROXY = "https://gh-proxy.com/"
# v2.5.8：备用镜像节点（国内网络直连 GitHub 慢/断时自动测速切换）
GH_MIRRORS = [
    "https://ghfast.top/",
    "https://gh-proxy.com/",
    "https://gh-proxy.net/",
    "https://mirror.ghproxy.com/",
    "https://github.moeyy.xyz/",
]
# v2.5.8：自动测速选最快节点
# ==================== v2.7.0 下载超时参数（失败要快，不要干等） ====================
# 更新包主体是代码（几 MB 量级），没必要容忍长时间的半死不活连接：
#   - 单次 read 超时 15s：15 秒一个字节都读不到，基本可以判定该节点已断
#   - 停滞超时 20s：连接还在但不再有数据推进，直接放弃换下一个节点
#   - 单次节点总时长 180s：单个节点拖过 3 分钟就换节点（断点续传会从已下载处继续）
#   - 整体下载上限 900s：极端弱网兜底，超时抛出由上层提示重试
DOWNLOAD_READ_TIMEOUT = 15.0
DOWNLOAD_STALL_TIMEOUT = 20.0
DOWNLOAD_NODE_TIMEOUT = 180.0
DOWNLOAD_TOTAL_TIMEOUT = 900.0


def _ping_mirror(mirror_url, timeout=3.0):
    """ping 单个镜像节点，返回延迟秒数；失败返回 timeout+1"""
    import socket
    try:
        # 从 URL 提取主机名
        host = mirror_url.replace("https://", "").replace("http://", "").split("/")[0]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.time()
        sock.connect((host, 443))
        sock.close()
        return time.time() - start
    except Exception:
        return timeout + 1.0


def _select_fastest_mirror():
    """测速所有镜像节点，返回最快的节点 URL 和延迟
    v2.5.8：每次更新时自动测速，选择延迟最低的节点"""
    global UPDATE_STATE
    fastest = None
    fastest_latency = float("inf")
    for mirror in GH_MIRRORS:
        latency = _ping_mirror(mirror)
        if latency < fastest_latency:
            fastest_latency = latency
            fastest = mirror
    UPDATE_STATE["mirror"] = fastest or GH_PROXY
    UPDATE_STATE["mirror_latency"] = fastest_latency
    print(f"[Updater] 最快节点: {fastest} (延迟 {fastest_latency:.2f}s)")
    return fastest or GH_PROXY
VERSION_FILE = "version.txt"
_UPDATER_DIR = os.path.dirname(os.path.abspath(__file__))
UPDATE_CACHE_DIR = os.path.join(_UPDATER_DIR, "_update_cache")
BACKUP_DIR = os.path.join(_UPDATER_DIR, "_update_backup")

# 更新状态
UPDATE_STATE = {
    "checking": False,
    "downloading": False,
    "extracting": False,
    "restarting": False,
    "latest_version": None,
    "current_version": None,
    "update_available": False,
    "download_progress": 0.0,  # 0.0 - 1.0
    "download_speed": 0,  # bytes/s
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "apply_progress": 0.0,   # 应用阶段进度 0-1
    "apply_phase": "",       # 应用阶段文字（解压/写入/校验）
    "applied_count": 0,
    "pending_count": 0,      # 延迟替换文件数（被占用，重启后生效）
    "notice_dismissed": False,  # v2.2.5：用户点过"稍后"→整个程序生命周期忽略版本更新
    "cache_reused": False,   # 是否复用了已下载的缓存包
    "error": None,
    "changelog": "",
    "download_url": "",
    "mirror": "",          # v2.2.13 实际选中的下载节点（自动测速）
    "mirror_latency": 0.0, # 测速延迟（秒）
}

# 回调函数（游戏中注册）
_progress_callback = None
_status_callback = None


def register_callbacks(progress_cb=None, status_cb=None):
    """注册进度回调和状态回调（游戏UI用）"""
    global _progress_callback, _status_callback
    _progress_callback = progress_cb
    _status_callback = status_cb


def get_current_version():
    """获取当前版本号"""
    try:
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except:
        pass
    return "0.0.0"


def _parse_version(v):
    """解析版本号为元组，用于比较"""
    try:
        parts = v.strip().lstrip('v').split('.')
        return tuple(int(p) for p in parts[:3])
    except:
        return (0, 0, 0)


def is_newer_version(latest, current):
    """比较版本号，latest是否比current新"""
    return _parse_version(latest) > _parse_version(current)


def _gh_proxy_url(url, mirror=None):
    """给所有GitHub相关URL加gh-proxy前缀（统一代理）
    v2.5.8: 支持指定镜像节点"""
    _mirror = mirror or GH_PROXY
    github_domains = [
        "https://github.com",
        "https://api.github.com",
        "https://raw.githubusercontent.com",
        "https://objects.githubusercontent.com",
        "https://codeload.github.com",
        "https://releases.github.com",
        "https://gist.github.com",
        "https://user-images.githubusercontent.com",
        "https://avatars.githubusercontent.com",
    ]
    for domain in github_domains:
        if url.startswith(domain):
            return _mirror + url
    return url


def check_for_updates(timeout=6):
    """
    检查GitHub最新版本
    返回: (latest_version, download_url, changelog) 或 None
    """
    global UPDATE_STATE
    UPDATE_STATE["checking"] = True
    UPDATE_STATE["error"] = None

    try:
        # v2.5.8：自动测速选最快节点
        _selected_mirror = _select_fastest_mirror()
        # GitHub API 获取最新release
        api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
        # API也走代理（使用测速选中的节点）
        api_url_proxied = _gh_proxy_url(api_url, mirror=_selected_mirror)

        req = urllib.request.Request(api_url_proxied, headers={
            "User-Agent": "ZombieSurvivor-Updater/1.0",
            "Accept": "application/vnd.github.v3+json",
        })

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        latest_version = data.get("tag_name", "").lstrip('v')
        changelog = data.get("body", "") or ""
        assets = data.get("assets", [])

        # 找到zip包（优先选择包含游戏包名的）
        download_url = None
        _asset_size = 0
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith('.zip') and ('zombie' in name or 'survivor' in name or 'game' in name or 'update' in name):
                download_url = _gh_proxy_url(asset.get("browser_download_url"), mirror=UPDATE_STATE.get("mirror"))
                _asset_size = int(asset.get("size", 0) or 0)
                break
        # 如果没找到特定名称的，取第一个zip
        if not download_url:
            for asset in assets:
                if asset.get("name", "").lower().endswith('.zip'):
                    download_url = _gh_proxy_url(asset.get("browser_download_url"), mirror=UPDATE_STATE.get("mirror"))
                    _asset_size = int(asset.get("size", 0) or 0)
                    break

        # 如果release没有assets，尝试源码包
        if not download_url:
            download_url = data.get("zipball_url")

        # v2.8.2：若最新版被标记为"错误版本"（曾导致游戏打不开），则改用
        # 次新的可用版本，避免反复更新到同一个坏版本。
        try:
            if is_version_broken(latest_version):
                _alt = find_latest_good_version(get_current_version())
                if _alt and _alt[1] != data.get("tag_name"):
                    _alt_data = _release_api(f"/releases/tags/{_alt[1]}")
                    latest_version = _alt[0]
                    changelog = _alt_data.get("body", "") or changelog
                    _assets2 = _alt_data.get("assets", [])
                    for _a2 in _assets2:
                        _n2 = str(_a2.get("name", "")).lower()
                        if _n2.endswith(".zip"):
                            download_url = _gh_proxy_url(_a2.get("browser_download_url"),
                                                         mirror=UPDATE_STATE.get("mirror"))
                            _asset_size = int(_a2.get("size", 0) or 0)
                            break
                        if _n2 == "manifest.json":
                            UPDATE_STATE["manifest_url"] = _gh_proxy_url(
                                _a2.get("browser_download_url"), mirror=UPDATE_STATE.get("mirror"))
                    changelog = "（已跳过标记为异常的旧版本）\n" + changelog
        except Exception:
            pass

        # v2.5.8：下载URL也走最快节点
        if download_url:
            download_url = _gh_proxy_url(download_url, mirror=UPDATE_STATE.get("mirror"))

        # v2.8.1 增量更新：记录 manifest.json 资产地址（用于只下载变化的文件）
        _manifest_url = None
        for asset in assets:
            if asset.get("name", "").lower() == "manifest.json":
                _manifest_url = _gh_proxy_url(asset.get("browser_download_url"),
                                              mirror=UPDATE_STATE.get("mirror"))
                break
        UPDATE_STATE["manifest_url"] = _manifest_url

        if not download_url:
            UPDATE_STATE["error"] = "未找到更新包"
            return None

        UPDATE_STATE["latest_version"] = latest_version
        UPDATE_STATE["changelog"] = changelog
        UPDATE_STATE["download_url"] = download_url
        UPDATE_STATE["checking"] = False

        if _asset_size > 0:
            _mb = _asset_size / 1048576.0
            changelog = f"[更新包大小 {_mb:.1f} MB]\n" + changelog
        return (latest_version, download_url, changelog)

    except urllib.error.URLError as e:
        UPDATE_STATE["error"] = f"网络错误: {e.reason}"
    except json.JSONDecodeError:
        UPDATE_STATE["error"] = "解析版本信息失败"
    except Exception as e:
        UPDATE_STATE["error"] = f"检查更新失败: {str(e)}"

    UPDATE_STATE["checking"] = False
    return None


USER_DATA_FILES = {
    "config.json", "game_records.json", "game_records.zss", "savegame.json", "savegame.zss",
    "codex_unlocks.json", "mods_config.json", "skill_tree_unlock.json",
    "game_log.txt", "_update_cache", "_update_backup", "releases", "dist_encrypted",
    "__pycache__", ".git",
}


# ==================== v2.8.2 致命错误自愈 ====================
# 场景：某次更新后游戏**根本打不开**（如 ModuleNotFoundError / SyntaxError / NameError）。
# 处理：尝试更新到更新的版本 → 若无更新版本，则回退到上一个可用版本，
#       并把当前版本标记为"错误版本"，以后检查更新时自动跳过它。
BROKEN_VERSIONS_FILE = "broken_versions.json"


def _broken_file_path(game_dir=None):
    if game_dir is None:
        game_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(game_dir, BROKEN_VERSIONS_FILE)


def load_broken_versions(game_dir=None):
    """读取被标记为错误的版本集合"""
    try:
        _p = _broken_file_path(game_dir)
        if not os.path.exists(_p):
            return set()
        with open(_p, "r", encoding="utf-8") as _f:
            _d = json.load(_f)
        _lst = _d.get("broken", []) if isinstance(_d, dict) else list(_d)
        return set(str(x) for x in _lst)
    except Exception:
        return set()


def mark_version_broken(version, reason="", game_dir=None):
    """把指定版本标记为错误版本（后续检查更新时跳过）"""
    try:
        _p = _broken_file_path(game_dir)
        _d = {"broken": [], "history": []}
        if os.path.exists(_p):
            try:
                with open(_p, "r", encoding="utf-8") as _f:
                    _d = json.load(_f)
            except Exception:
                pass
        _broken = set(str(x) for x in (_d.get("broken", []) if isinstance(_d, dict) else []))
        _broken.add(str(version))
        _d["broken"] = sorted(_broken)
        _hist = _d.get("history", []) if isinstance(_d, dict) else []
        _hist.append({"version": str(version), "reason": str(reason)[:300],
                      "time": time.strftime("%Y-%m-%d %H:%M:%S")})
        _d["history"] = _hist[-30:]
        with open(_p, "w", encoding="utf-8") as _f:
            json.dump(_d, _f, ensure_ascii=False, indent=2)
        UPDATE_STATE["broken_versions"] = _broken
        return True
    except Exception:
        return False


def is_version_broken(version):
    return str(version) in load_broken_versions()


def _release_api(path, timeout=8):
    """调用 GitHub Releases API（经代理）"""
    _url = _gh_proxy_url(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}{path}",
                         mirror=UPDATE_STATE.get("mirror"))
    _req = urllib.request.Request(_url, headers={
        "User-Agent": "ZombieSurvivor-Updater/1.0",
        "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(_req, timeout=timeout) as _r:
        return json.loads(_r.read().decode('utf-8'))


def list_available_versions(limit=25):
    """列出远端版本（新→旧），返回 [(version, tag)]"""
    try:
        _data = _release_api(f"/releases?per_page={int(limit)}")
        _out = []
        for _r in _data:
            if not isinstance(_r, dict):
                continue
            _tag = str(_r.get("tag_name", "")).lstrip('v')
            if _tag:
                _out.append((_tag, _r.get("tag_name")))
        return _out
    except Exception:
        return []


def find_latest_good_version(current_version=None):
    """找出**不是错误版本**的最新版本；没有则返回 None

    current_version 提供时，只考虑比它更高的版本（正常升级路径）。
    """
    _broken = load_broken_versions()
    _cur = str(current_version or get_current_version())
    try:
        _curt = tuple(int(x) for x in _cur.split(".") if x.isdigit())
    except Exception:
        _curt = ()
    _best = None
    for _ver, _tag in list_available_versions():
        if _ver in _broken:
            continue
        try:
            _vt = tuple(int(x) for x in _ver.split(".") if x.isdigit())
        except Exception:
            continue
        if current_version is not None and _vt <= _curt:
            continue
        if _best is None or _vt > _best[0]:
            _best = (_vt, _ver, _tag)
    return (_best[1], _best[2]) if _best else None


def find_rollback_version(current_version=None):
    """找出可回退的版本：低于当前版本的、非错误版本中最高的那个"""
    _broken = load_broken_versions()
    _cur = str(current_version or get_current_version())
    try:
        _curt = tuple(int(x) for x in _cur.split(".") if x.isdigit())
    except Exception:
        return None
    _best = None
    for _ver, _tag in list_available_versions():
        if _ver in _broken:
            continue
        try:
            _vt = tuple(int(x) for x in _ver.split(".") if x.isdigit())
        except Exception:
            continue
        if _vt >= _curt:
            continue
        if _best is None or _vt > _best[0]:
            _best = (_vt, _ver, _tag)
    return (_best[1], _best[2]) if _best else None


def download_version_zip(version, progress_cb=None):
    """下载指定版本的全量更新包，返回本地路径或 None"""
    try:
        _r = _release_api(f"/releases/tags/{version if str(version).startswith('v') else 'v' + str(version)}")
        _url = None
        for _a in _r.get("assets", []):
            if str(_a.get("name", "")).lower().endswith(".zip"):
                _url = _gh_proxy_url(_a.get("browser_download_url"),
                                     mirror=UPDATE_STATE.get("mirror"))
                break
        if not _url:
            return None
        return download_update(_url, progress_callback=progress_cb, version=version)
    except Exception:
        return None


def handle_boot_failure(error_text="", status_cb=None, progress_cb=None):
    """启动致命错误自愈（游戏打不开时调用）

    流程：
      1) 有更高且非错误版本 → 正常更新过去
      2) 没有 → 回退上一个非错误版本，并把当前版本标记为错误版本
      3) 都没有 → 返回 False（只能提示用户）
    返回 True 表示已安排修复（调用方应重启）
    """
    global UPDATE_STATE
    _cur = get_current_version()
    _err = str(error_text)[:400]

    # 先排除"当前版本已被标记为错误"的死循环：若已是错误版本则直接尝试其它版本
    _already_broken = is_version_broken(_cur)

    if status_cb:
        status_cb(f"检测到启动失败（v{_cur}），尝试自动修复...")

    # 1) 尝试更新到更高版本
    _upd = find_latest_good_version(_cur)
    if _upd and _upd[0] != _cur:
        _ver, _tag = _upd
        if status_cb:
            status_cb(f"发现可用新版本 v{_ver}，正在更新...")
        _zip = download_version_zip(_tag, progress_cb)
        if _zip:
            _ok, _n, _p = extract_and_apply_update(_zip)
            if _ok:
                if status_cb:
                    status_cb(f"已修复到 v{_ver}，即将重启")
                return True
        # 新版本也装不上 → 标记它为错误版本，继续尝试回退
        mark_version_broken(_ver, f"更新后仍无法启动: {_err}")
        if status_cb:
            status_cb(f"v{_ver} 也存在问题，已标记，尝试回退...")

    # 2) 回退上一个版本
    if not _already_broken:
        mark_version_broken(_cur, f"启动失败: {_err}")
    _rb = find_rollback_version(_cur)
    if _rb:
        _ver, _tag = _rb
        if status_cb:
            status_cb(f"正在回退到 v{_ver}...")
        # 优先增量（差异文件少），失败再全量
        try:
            UPDATE_STATE["manifest_url"] = None
            _r = _release_api(f"/releases/tags/{_tag}")
            for _a in _r.get("assets", []):
                if str(_a.get("name", "")).lower() == "manifest.json":
                    UPDATE_STATE["manifest_url"] = _gh_proxy_url(
                        _a.get("browser_download_url"), mirror=UPDATE_STATE.get("mirror"))
                    break
            _inc_ok, _ic, _ip = try_incremental_update(_ver, progress_cb=progress_cb, status_cb=None)
            if _inc_ok:
                if status_cb:
                    status_cb(f"已回退到 v{_ver}，即将重启")
                return True
        except Exception:
            pass
        _zip = download_version_zip(_tag, progress_cb)
        if _zip:
            try:
                _ok, _n, _p = extract_and_apply_update(_zip)
                if _ok:
                    if status_cb:
                        status_cb(f"已回退到 v{_ver}，即将重启")
                    return True
            except Exception:
                pass

    if status_cb:
        status_cb("自动修复失败，请手动重新安装")
    return False


def _compute_md5(file_path, chunk=65536):
    """计算文件 MD5（十六进制小写）"""
    import hashlib
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def apply_pending_updates(game_dir=None):
    """启动时把被占用而延迟替换的文件（*.pending_update）替换到位。

    游戏主进程在加载字体/音频等资产前调用；返回替换成功的文件数。
    """
    if game_dir is None:
        game_dir = os.path.dirname(os.path.abspath(__file__))
    replaced = 0
    for root, dirs, files in os.walk(game_dir):
        dirs[:] = [d for d in dirs if d not in ("_update_cache", "_update_backup", "__pycache__", ".git")]
        for fname in files:
            if fname.endswith(".pending_update"):
                pending_path = os.path.join(root, fname)
                target_path = pending_path[: -len(".pending_update")]
                try:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    os.replace(pending_path, target_path)
                    replaced += 1
                except Exception:
                    try:
                        os.remove(pending_path)
                    except Exception:
                        pass
    return replaced


def _write_retry(dst, data, retries=3):
    """写文件，遇占用/权限错误重试；仍失败则写 *.pending_update 延迟替换（Windows 字体/音频占用兜底）。

    返回 "ok" 或 "pending"。
    """
    last_err = None
    for attempt in range(retries):
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = dst + ".tmp_write"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dst)
            return "ok"
        except (PermissionError, OSError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(0.5)
    # 仍失败：写延迟替换文件（不抛错，重启后生效）
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        pending = dst + ".pending_update"
        with open(pending, "wb") as f:
            f.write(data)
        return "pending"
    except Exception:
        raise PermissionError(
            f"无法写入文件: {dst}\n原因: {last_err}\n"
            f"请尝试：1.完全退出游戏后重新更新 2.以管理员身份运行 3.关闭杀毒软件实时保护/添加白名单"
        )


def _zip_entry_rel(name, prefix):
    """把 zip 内条目名转换为相对游戏目录路径（剥掉顶层版本目录前缀）"""
    rel = name
    if prefix and rel.startswith(prefix):
        rel = rel[len(prefix):]
    return rel.lstrip("/\\")


def _detect_zip_prefix(names):
    """探测 zip 顶层目录前缀（如 zombie_survivor_v2.0.8/），无则返回空串"""
    for name in names:
        if name.endswith("/"):
            continue
        first_seg = name.split("/", 1)[0]
        if "/" in name and (("zombie" in first_seg.lower()) or ("_v" in first_seg.lower()) or first_seg.endswith("_v")):
            return first_seg + "/"
    return ""


def verify_assets(game_dir=None, manifest_rel="assets/manifest.json"):
    """资源完整性校验：读 manifest.json（相对路径→md5），返回 (缺失列表, 损坏列表)"""
    if game_dir is None:
        game_dir = os.path.dirname(os.path.abspath(__file__))
    manifest_path = os.path.join(game_dir, manifest_rel)
    missing, corrupted = [], []
    if not os.path.exists(manifest_path):
        return missing, corrupted, "no_manifest"
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return missing, corrupted, "bad_manifest"
    entries = manifest.get("files", manifest)
    for rel, info in entries.items():
        # v2.0.11：_pkg_compat.zip 是发布期"旧版更新器兼容自愈包"，仅存在于发布 zip，
        # 本地/运行环境缺失属正常（游戏运行时包目录已存在），不计入完整性校验
        if rel == "assets/_pkg_compat.zip":
            continue
        fp = os.path.join(game_dir, rel)
        if not os.path.isfile(fp):
            missing.append(rel)
            continue
        if isinstance(info, dict) and info.get("md5"):
            try:
                if _compute_md5(fp) != info["md5"]:
                    corrupted.append(rel)
            except Exception:
                corrupted.append(rel)
    return missing, corrupted, "ok"


def _zip_is_complete(zip_path, expect_version=None):
    """校验缓存 zip 完整可用（结构 + 版本匹配）。返回 bool"""
    try:
        if not os.path.isfile(zip_path):
            return False
        if not zipfile.is_zipfile(zip_path):
            return False
        with zipfile.ZipFile(zip_path, "r") as zf:
            if zf.testzip() is not None:
                return False
            if expect_version is not None:
                prefix = _detect_zip_prefix(zf.namelist())
                for name in zf.namelist():
                    if name.endswith("version.txt"):
                        try:
                            content = zf.read(name).decode("utf-8", "ignore").strip()
                            if content.lstrip("v") == expect_version.lstrip("v"):
                                return True
                        except Exception:
                            return False
                        break
                return False
        return True
    except Exception:
        return False


def _mirror_candidates(url):
    """v2.5.8 生成候选下载节点：原始 GitHub + 全部代理前缀（去重）

    网络不好（直连 GitHub 很慢/超时）时，下载会自动改走镜像节点，
    测速后选最快的那个；全部失败则回退原始 URL。
    """
    out = [url]
    prox = _gh_proxy_url(url)
    if prox != url and prox not in out:
        out.append(prox)
    for _p in GH_MIRRORS:
        _c = _p + url if not url.startswith(_p) else url
        if _c not in out:
            out.append(_c)
    return out


def pick_fastest_mirror(download_url, timeout=3, sample_bytes=65536):
    """v2.2.13 自动测速选择最快下载节点/代理：
    对每个候选节点下载 sample_bytes 字节计时，选最快；全部失败回退原始 URL。
    返回 (fastest_url, latency_seconds) 或 (download_url, 0) """
    best_url = download_url
    best_t = None
    for _u in _mirror_candidates(download_url):
        try:
            _req = urllib.request.Request(_u, headers={"User-Agent": "ZombieSurvivor-Updater/1.0"})
            _t0 = time.time()
            with urllib.request.urlopen(_req, timeout=timeout) as _resp:
                _got = 0
                while _got < sample_bytes:
                    _ch = _resp.read(min(8192, sample_bytes - _got))
                    if not _ch:
                        break
                    _got += len(_ch)
            _lat = time.time() - _t0
            if best_t is None or _lat < best_t:
                best_t = _lat
                best_url = _u
        except Exception:
            continue
    return (best_url, best_t or 0.0)


def download_update(download_url, progress_callback=None, version=None):
    """
    下载更新包，带进度条；支持复用已下载缓存、断点续传（.part）。
    v2.2.13：下载前自动测速选择最快节点/代理。
    返回: 下载的文件路径 或 None
    """
    global UPDATE_STATE
    UPDATE_STATE["downloading"] = True
    UPDATE_STATE["download_progress"] = 0.0
    UPDATE_STATE["cache_reused"] = False
    UPDATE_STATE["error"] = None

    try:
        os.makedirs(UPDATE_CACHE_DIR, exist_ok=True)
        ver_suffix = version or get_current_version()
        output_path = os.path.join(UPDATE_CACHE_DIR, f"update_package_v{ver_suffix}.zip")
        part_path = output_path + ".part"

        # 1) 缓存复用：已有完整且版本匹配的包 → 直接返回，不重复下载
        if _zip_is_complete(output_path, expect_version=ver_suffix):
            UPDATE_STATE["downloading"] = False
            UPDATE_STATE["download_progress"] = 1.0
            UPDATE_STATE["cache_reused"] = True
            UPDATE_STATE["total_bytes"] = os.path.getsize(output_path)
            UPDATE_STATE["downloaded_bytes"] = UPDATE_STATE["total_bytes"]
            return output_path

        # 2) v2.5.8 节点容错：测速选最快节点，失败自动换下一个镜像重试
        #    （国内网络直连 GitHub 常超时/龟速 → 依次尝试 ghfast/gh-proxy 等镜像）
        try:
            _fast, _lat = pick_fastest_mirror(download_url)
        except Exception:
            _fast, _lat = _gh_proxy_url(download_url), 0.0
        _cands = [u for u in _mirror_candidates(download_url)]
        if _fast in _cands:
            _cands.remove(_fast)
        _cands.insert(0, _fast)          # 测速最快的排最前
        proxied_url = _fast
        UPDATE_STATE["mirror"] = _fast
        UPDATE_STATE["mirror_latency"] = round(_lat, 2) if _lat else 0
        headers = {"User-Agent": "ZombieSurvivor-Updater/1.0"}
        resume_from = 0
        if os.path.exists(part_path) and os.path.getsize(part_path) > 0:
            resume_from = os.path.getsize(part_path)
            headers["Range"] = f"bytes={resume_from}-"
            # 目标为最终 zip 时直接续写 part
        _last_err = None
        _resp = None
        for _try_url in _cands:
            try:
                _h = dict(headers)
                if resume_from > 0:
                    _h["Range"] = f"bytes={resume_from}-"
                _req = urllib.request.Request(_try_url, headers=_h)
                UPDATE_STATE["mirror"] = _try_url
                # v2.7.0：单次 read 超时由 60s 缩短到 15s（几 MB 的代码包，
                # 15s 读不到任何字节就该换节点，不要原地干等）
                _resp = urllib.request.urlopen(_req, timeout=DOWNLOAD_READ_TIMEOUT)
                proxied_url = _try_url
                break
            except Exception as _e:
                _last_err = _e
                _resp = None
                continue
        if _resp is None:
            raise Exception(f"所有下载节点均失败（最后错误: {_last_err}）")
        with _resp as resp:
            total_size = int(resp.headers.get('Content-Length', 0))
            if resp.status == 206:
                total_size = resume_from + total_size
            elif resp.status == 200 and resume_from > 0:
                # 服务端不支持 Range，重下
                resume_from = 0
                total_size = int(resp.headers.get('Content-Length', 0))
            UPDATE_STATE["total_bytes"] = total_size
            downloaded = resume_from
            start_time = time.time()
            last_update = start_time
            chunk_size = 8192

            mode = "ab" if (resume_from > 0 and resp.status == 206) else "wb"
            # v2.7.0 停滞检测：连接还活着但不再推进数据时，果断中止换下一个节点。
            # 旧逻辑只有「单字节读不到」的 socket 超时，遇到「每秒挤几个字节」的
            # 假活连接会一直卡在进度条上，表现为下载永远结束不了。
            _node_start = time.time()
            _last_bytes = downloaded
            _last_progress_at = time.time()
            _stalled = False
            with open(part_path, mode) as f:
                while True:
                    chunk = resp.read(chunk_size)
                    _now = time.time()
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        _last_progress_at = _now
                    else:
                        break
                    UPDATE_STATE["downloaded_bytes"] = downloaded
                    if total_size > 0:
                        progress = downloaded / total_size
                        UPDATE_STATE["download_progress"] = progress
                        now = time.time()
                        if now - last_update >= 0.5:
                            elapsed = now - start_time
                            if elapsed > 0:
                                UPDATE_STATE["download_speed"] = int(downloaded / elapsed)
                            last_update = now
                        if progress_callback:
                            try:
                                progress_callback(progress, downloaded, total_size)
                            except Exception:
                                pass
                        if _progress_callback:
                            try:
                                _progress_callback(progress, downloaded, total_size)
                            except Exception:
                                pass
                    # 停滞 / 单节点超时 / 整体超时 → 中止，交由上层换节点或重试
                    if _now - _last_progress_at > DOWNLOAD_STALL_TIMEOUT:
                        _stalled = True
                        break
                    if _now - _node_start > DOWNLOAD_NODE_TIMEOUT:
                        _stalled = True
                        break
                    if time.time() - start_time > DOWNLOAD_TOTAL_TIMEOUT:
                        _stalled = True
                        break
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            if _stalled:
                # 已写入的字节保留在 .part 里，下次走断点续传继续，不浪费流量
                raise Exception(
                    f"下载停滞/超时（已下载 {downloaded} 字节），将更换节点续传")

        # 3) 完整性校验后重命名
        if not _zip_is_complete(part_path):
            raise Exception("下载的更新包不完整（MD5/结构校验失败），将重新下载")
        os.replace(part_path, output_path)

        UPDATE_STATE["downloading"] = False
        UPDATE_STATE["download_progress"] = 1.0
        return output_path

    except Exception as e:
        UPDATE_STATE["error"] = f"下载失败: {str(e)}"
        UPDATE_STATE["downloading"] = False
        return None

def extract_and_apply_update(zip_path, game_dir=None, progress_cb=None):
    """
    解压更新包并全量镜像应用（热更新）
    - 全量镜像：zip 内全部文件（除用户数据）逐文件写入，任何目录/文件类型都覆盖
    - 占用兜底：字体/音频等被进程占用时写入 *.pending_update，重启后替换
    - 清理旧 .py：删除新版 zip 中已不存在的旧版顶层 .py（避免旧逻辑更新不全的残留）
    - 进度：apply_progress（0-1）+ 阶段文字
    """
    global UPDATE_STATE
    UPDATE_STATE["extracting"] = True
    UPDATE_STATE["apply_progress"] = 0.0
    UPDATE_STATE["apply_phase"] = "正在解压更新包..."
    UPDATE_STATE["error"] = None
    UPDATE_STATE["pending_count"] = 0

    if game_dir is None:
        game_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            prefix = _detect_zip_prefix(names)
            file_entries = [(n, _zip_entry_rel(n, prefix)) for n in names if not n.endswith("/")]
            # 过滤用户数据
            file_entries = [(n, rel) for n, rel in file_entries
                            if rel not in USER_DATA_FILES
                            and not rel.startswith("_update_cache")
                            and not rel.startswith("_update_backup")
                            and not rel.startswith("__pycache__")
                            and not rel.startswith("releases")
                            and not rel.startswith("dist_encrypted")
                            and not rel.startswith(".git")]
            total = max(1, len(file_entries))
            applied_count = 0
            pending_count = 0

            # 阶段1：解压校验（读取所有条目，快速校验 zip 完整）
            UPDATE_STATE["apply_phase"] = "正在校验更新包..."
            for i, (name, rel) in enumerate(file_entries):
                try:
                    zf.read(name)
                except Exception as e:
                    raise Exception(f"更新包损坏: {name} ({e})")
                if i % 40 == 0:
                    UPDATE_STATE["apply_progress"] = 0.15 * (i / total)

            # 阶段2前：备份小文件（.py/version.txt/manifest）供异常回滚
            backup_path = os.path.join(game_dir, BACKUP_DIR)
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path, ignore_errors=True)
            os.makedirs(backup_path, exist_ok=True)
            for _name, _rel in file_entries:
                if _rel.endswith((".py",)) or _rel == "version.txt" or _rel == "manifest.json":
                    _src = os.path.join(game_dir, _rel)
                    if os.path.isfile(_src):
                        try:
                            os.makedirs(os.path.join(backup_path, os.path.dirname(_rel)), exist_ok=True)
                            shutil.copy2(_src, os.path.join(backup_path, _rel))
                        except Exception:
                            pass

            # 阶段2：全量镜像写入
            UPDATE_STATE["apply_phase"] = "正在写入文件..."
            new_rel_set = set()
            for i, (name, rel) in enumerate(file_entries):
                data = zf.read(name)
                dst = os.path.join(game_dir, rel)
                res = _write_retry(dst, data)
                if res == "pending":
                    pending_count += 1
                else:
                    applied_count += 1
                new_rel_set.add(rel)
                UPDATE_STATE["applied_count"] = applied_count
                UPDATE_STATE["pending_count"] = pending_count
                UPDATE_STATE["apply_progress"] = 0.15 + 0.75 * ((i + 1) / total)
                if progress_cb:
                    try:
                        progress_cb(0.15 + 0.75 * ((i + 1) / total), applied_count, total)
                    except Exception:
                        pass

            # 阶段3：清理旧版遗留的顶层 .py（不在新包内的旧文件，防止旧逻辑更新不全残留）
            UPDATE_STATE["apply_phase"] = "正在清理旧版残留文件..."
            removed = 0
            for f in os.listdir(game_dir):
                fpath = os.path.join(game_dir, f)
                if os.path.isfile(fpath) and (f.endswith('.py') or f in ('README.md', 'requirements.txt')):
                    if f not in new_rel_set:
                        try:
                            os.remove(fpath)
                            removed += 1
                        except Exception:
                            pass
            UPDATE_STATE["apply_progress"] = 0.92

            # 阶段4：资源完整性校验（manifest.json）
            UPDATE_STATE["apply_phase"] = "正在校验资源完整性..."
            missing, corrupted, status = verify_assets(game_dir)
            if status == "ok" and (missing or corrupted):
                UPDATE_STATE["apply_phase"] = f"资源校验：{len(missing)}缺失/{len(corrupted)}损坏（重启后将修复）"
            elif status == "ok":
                UPDATE_STATE["apply_phase"] = "资源完整性校验通过"
            elif status == "no_manifest":
                UPDATE_STATE["apply_phase"] = "本版本更新包无完整性清单"
            UPDATE_STATE["apply_progress"] = 1.0

        # 验证新版本号（从目标游戏目录读取）
        new_version = "0.0.0"
        try:
            with open(os.path.join(game_dir, "version.txt"), encoding="utf-8") as _vf:
                new_version = _vf.read().strip()
        except Exception:
            new_version = get_current_version()
        if new_version == "0.0.0":
            raise Exception("更新后版本号无效")

        UPDATE_STATE["current_version"] = new_version
        UPDATE_STATE["extracting"] = False
        UPDATE_STATE["update_available"] = False
        UPDATE_STATE["pending_count"] = pending_count

        return True, applied_count, new_version, pending_count

    except Exception as e:
        UPDATE_STATE["error"] = f"应用更新失败: {str(e)}"
        UPDATE_STATE["extracting"] = False
        # 回滚小文件（.py/version.txt/manifest）
        try:
            backup_path = os.path.join(game_dir, BACKUP_DIR)
            if os.path.isdir(backup_path):
                for root, dirs, files in os.walk(backup_path):
                    for fname in files:
                        bsrc = os.path.join(root, fname)
                        rel = os.path.relpath(bsrc, backup_path)
                        bdst = os.path.join(game_dir, rel)
                        os.makedirs(os.path.dirname(bdst), exist_ok=True)
                        shutil.copy2(bsrc, bdst)
        except Exception:
            pass
        return False, 0, None, 0


def cleanup_backup():
    """启动时清理上次更新的备份"""
    try:
        backup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), BACKUP_DIR)
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path, ignore_errors=True)
    except:
        pass


def cleanup_cache():
    """清理更新缓存"""
    try:
        cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), UPDATE_CACHE_DIR)
        if os.path.exists(cache_path):
            shutil.rmtree(cache_path, ignore_errors=True)
    except:
        pass


def restart_game():
    """重启游戏以应用更新（热更新）"""
    global UPDATE_STATE
    UPDATE_STATE["restarting"] = True

    try:
        # 找到主入口
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(script_dir, "main.py")

        if not os.path.exists(main_script):
            main_script = sys.argv[0]

        # 重启
        python = sys.executable
        os.execv(python, [python, main_script] + sys.argv[1:])
    except Exception as e:
        UPDATE_STATE["error"] = f"重启失败: {str(e)}"
        UPDATE_STATE["restarting"] = False


# ==================== v2.8.1 增量更新 ====================
# 不再每次都下载 76MB 全量包：先下几 KB 的 manifest.json，
# 与本地文件 MD5 比对，只下载真正变化的文件。失败自动回退全量包。
INCREMENTAL_MAX_FILES = 400      # 单次增量最多下载的文件数（超出则回退全量）
INCREMENTAL_FILE_TIMEOUT = 15    # 单文件下载超时（秒）


def _raw_file_url(rel_path, tag):
    """构造 GitHub raw 单文件地址（经代理加速）"""
    _t = tag if str(tag).startswith("v") else f"v{tag}"
    _u = ("https://raw.githubusercontent.com/"
          f"{GITHUB_USER}/{GITHUB_REPO}/{_t}/{rel_path}")
    return _gh_proxy_url(_u, mirror=UPDATE_STATE.get("mirror"))


def _http_get_bytes(url, timeout=15, retries=2):
    """带重试的 GET，返回 bytes（失败返回 None）"""
    for _i in range(retries + 1):
        try:
            _req = urllib.request.Request(url, headers={
                "User-Agent": "ZombieSurvivor-Updater/1.0"})
            with urllib.request.urlopen(_req, timeout=timeout) as _r:
                return _r.read()
        except Exception:
            if _i >= retries:
                return None
            time.sleep(1.0)
    return None


def fetch_update_manifest(manifest_url, timeout=15):
    """下载并解析远端 manifest.json，返回 {rel: {"md5":..,"size":..}} 或 None"""
    _raw = _http_get_bytes(manifest_url, timeout=timeout)
    if not _raw:
        UPDATE_STATE["error"] = "增量清单下载失败"
        return None
    try:
        _m = json.loads(_raw.decode('utf-8'))
        _files = _m.get("files", _m)
        if not isinstance(_files, dict) or not _files:
            return None
        # 过滤用户数据与运行产物
        _out = {}
        for _rel, _info in _files.items():
            if _rel in USER_DATA_FILES:
                continue
            if _rel.startswith(("_update_cache", "_update_backup", "__pycache__",
                                "releases", "dist_encrypted", "replays", "data", "mods_data")):
                continue
            if isinstance(_info, dict):
                _out[_rel] = {"md5": str(_info.get("md5", "")).lower(),
                              "size": int(_info.get("size", 0) or 0)}
            else:
                _out[_rel] = {"md5": str(_info).lower(), "size": 0}
        return _out
    except Exception:
        UPDATE_STATE["error"] = "增量清单解析失败"
        return None


def compute_changed_files(manifest, game_dir=None):
    """比对本地文件 MD5，返回需要下载的相对路径列表"""
    if game_dir is None:
        game_dir = os.path.dirname(os.path.abspath(__file__))
    _need = []
    for _rel, _info in manifest.items():
        # 双保险：即便清单里混入了用户数据/运行产物，也绝不覆盖
        if _rel in USER_DATA_FILES or _rel.startswith(
                ("_update_cache", "_update_backup", "__pycache__", "releases",
                 "dist_encrypted", "replays", "data", "mods_data")):
            continue
        _local = os.path.join(game_dir, _rel)
        if not os.path.isfile(_local):
            _need.append(_rel)
            continue
        try:
            if _compute_md5(_local) != _info["md5"]:
                _need.append(_rel)
        except Exception:
            _need.append(_rel)
    return _need


def download_incremental_files(rel_list, tag, game_dir=None, progress_cb=None):
    """逐文件下载到缓存目录，返回 {rel: 本地缓存路径}"""
    if game_dir is None:
        game_dir = os.path.dirname(os.path.abspath(__file__))
    _cache = os.path.join(game_dir, CACHE_DIR, "incremental")
    try:
        if os.path.exists(_cache):
            shutil.rmtree(_cache, ignore_errors=True)
        os.makedirs(_cache, exist_ok=True)
    except Exception:
        return None
    _got = {}
    _total = max(1, len(rel_list))
    for _i, _rel in enumerate(rel_list):
        _data = _http_get_bytes(_raw_file_url(_rel, tag), timeout=INCREMENTAL_FILE_TIMEOUT)
        if _data is None:
            UPDATE_STATE["error"] = f"增量下载失败: {_rel}"
            return None
        _dst = os.path.join(_cache, _rel)
        try:
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            with open(_dst, "wb") as _f:
                _f.write(_data)
        except Exception:
            UPDATE_STATE["error"] = f"增量写入失败: {_rel}"
            return None
        _got[_rel] = _dst
        if progress_cb:
            try:
                progress_cb((_i + 1) / _total)
            except Exception:
                pass
    return _got


def apply_incremental_files(file_map, game_dir=None):
    """把增量下载的文件应用到游戏目录（备份 .py 供回滚）"""
    global UPDATE_STATE
    if game_dir is None:
        game_dir = os.path.dirname(os.path.abspath(__file__))
    _backup = os.path.join(game_dir, BACKUP_DIR)
    try:
        if os.path.exists(_backup):
            shutil.rmtree(_backup, ignore_errors=True)
        os.makedirs(_backup, exist_ok=True)
    except Exception:
        pass
    _applied = 0
    _pending = 0
    for _rel, _src in file_map.items():
        _dst = os.path.join(game_dir, _rel)
        try:
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            # 备份旧 .py / version.txt
            if _rel.endswith(".py") or _rel in ("version.txt", "manifest.json"):
                if os.path.isfile(_dst):
                    _bk = os.path.join(_backup, _rel)
                    os.makedirs(os.path.dirname(_bk), exist_ok=True)
                    shutil.copy2(_dst, _bk)
            if not _write_retry(_dst, open(_src, "rb").read()):
                _pend = _dst + ".pending_update"
                with open(_pend, "wb") as _f:
                    _f.write(open(_src, "rb").read())
                _pending += 1
                continue
            _applied += 1
        except Exception:
            _pend = _dst + ".pending_update"
            try:
                shutil.copy2(_src, _pend)
                _pending += 1
            except Exception:
                pass
    UPDATE_STATE["pending_count"] = _pending
    return _applied, _pending


def try_incremental_update(latest_version, progress_cb=None, status_cb=None):
    """尝试增量更新。返回 (是否成功, 已应用文件数, pending数)

    失败时（拿不到 manifest / 下载异常 / 变化文件过多）返回 (False, 0, 0)，
    由调用方回退到全量包。
    """
    global UPDATE_STATE
    _murl = UPDATE_STATE.get("manifest_url")
    if not _murl:
        return False, 0, 0
    _game_dir = os.path.dirname(os.path.abspath(__file__))

    if status_cb:
        status_cb("正在获取增量清单...")
    _manifest = fetch_update_manifest(_murl)
    if not _manifest:
        return False, 0, 0

    if status_cb:
        status_cb("正在比对本地文件...")
    _need = compute_changed_files(_manifest, _game_dir)
    UPDATE_STATE["incremental_files"] = len(_need)
    UPDATE_STATE["incremental_total"] = len(_manifest)
    if not _need:
        # 没有文件变化：只更新版本号
        try:
            with open(os.path.join(_game_dir, "version.txt"), "w", encoding="utf-8") as _f:
                _f.write(str(latest_version))
        except Exception:
            pass
        return True, 0, 0
    if len(_need) > INCREMENTAL_MAX_FILES:
        # 变化太多，增量未必更快 → 回退全量
        UPDATE_STATE["error"] = None
        return False, 0, 0

    if status_cb:
        status_cb(f"仅 {len(_need)} 个文件有变化，开始下载...")
    _file_map = download_incremental_files(_need, latest_version, _game_dir, progress_cb)
    if not _file_map:
        return False, 0, 0

    if status_cb:
        status_cb("正在应用增量更新...")
    _applied, _pending = apply_incremental_files(_file_map, _game_dir)
    try:
        with open(os.path.join(_game_dir, "version.txt"), "w", encoding="utf-8") as _f:
            _f.write(str(latest_version))
    except Exception:
        pass
    return True, _applied, _pending


def perform_full_update(progress_cb=None, status_cb=None):
    """
    执行完整更新流程：检查 -> 下载 -> 应用 -> 重启
    在后台线程中运行
    """
    def _update_thread():
        global UPDATE_STATE

        if status_cb:
            status_cb("正在检查更新...")

        # 1. 检查更新
        result = check_for_updates()
        if not result:
            if status_cb:
                status_cb(UPDATE_STATE.get("error", "检查更新失败"))
            return

        latest_version, download_url, changelog = result
        current_version = get_current_version()

        if not is_newer_version(latest_version, current_version):
            if status_cb:
                status_cb(f"已是最新版本 (v{current_version})")
            UPDATE_STATE["update_available"] = False
            return

        UPDATE_STATE["update_available"] = True
        if status_cb:
            status_cb(f"发现新版本 v{latest_version}，开始下载...")

        # 2. v2.8.1：优先增量更新（只下载真正变化的文件）
        _inc_ok, _inc_applied, _inc_pending = try_incremental_update(
            latest_version, progress_cb=progress_cb, status_cb=status_cb)
        if _inc_ok:
            if status_cb:
                _n = UPDATE_STATE.get("incremental_files", 0)
                if _n == 0:
                    status_cb(f"无需下载，已是最新文件，新版本 v{latest_version}")
                else:
                    status_cb(f"增量更新成功！下载 {_n} 个文件，应用 {_inc_applied} 个，"
                              f"新版本 v{latest_version}，即将重启...")
            cleanup_cache()
            time.sleep(2)
            restart_game()
            return
        # 增量不可用 → 回退全量包
        UPDATE_STATE["error"] = None
        if status_cb:
            status_cb("增量更新不可用，改为下载完整更新包...")

        zip_path = download_update(download_url, progress_callback=progress_cb, version=latest_version)
        if not zip_path:
            if status_cb:
                status_cb(UPDATE_STATE.get("error", "下载失败"))
            return
        if UPDATE_STATE.get("cache_reused"):
            if status_cb:
                status_cb("检测到已下载的更新包，直接应用（不重复下载）...")
        elif status_cb:
            status_cb("下载完成，正在应用更新...")

        # 3. 应用更新（全量镜像 + 占用延迟替换）
        success, count, new_version, pending_count = extract_and_apply_update(zip_path)
        if not success:
            if status_cb:
                status_cb(UPDATE_STATE.get("error", "应用更新失败，已回滚"))
            return

        if pending_count > 0:
            if status_cb:
                status_cb(f"更新成功！已应用 {count} 个文件，{pending_count} 个占用文件将在重启后生效，新版本 v{new_version}，即将重启...")
        elif status_cb:
            status_cb(f"更新成功！已应用 {count} 个文件，新版本 v{new_version}，即将重启...")

        # 4. 清理缓存
        cleanup_cache()

        # 5. 延迟重启（给UI显示完成信息的时间）
        time.sleep(2)
        restart_game()

    thread = threading.Thread(target=_update_thread, daemon=True)
    thread.start()
    return thread


def repair_assets(progress_cb=None, status_cb=None):
    """v2.0.11 资源完整性自愈：校验 manifest，缺失/损坏则自动下载完整包并应用补全。
    复用下载缓存/断点续传，应用后重新校验并重启生效。在后台线程中运行。
    """
    def _repair_thread():
        global UPDATE_STATE
        try:
            if status_cb:
                status_cb("正在校验资源完整性...")
            missing, corrupted, st = verify_assets()
            if st == "ok" and not missing and not corrupted:
                if status_cb:
                    status_cb("资源完整，无需修复")
                return
            if status_cb:
                status_cb(f"检测到 {len(missing)} 个缺失 / {len(corrupted)} 个损坏，正在下载修复包...")
            # 下载最新发布包（不要求版本新于当前，仅用于补全缺失资源）
            latest = check_for_updates(timeout=10)
            if not latest:
                if status_cb:
                    status_cb(UPDATE_STATE.get("error", "获取修复包失败，请检查网络"))
                return
            _, download_url, _changelog = latest
            zip_path = download_update(download_url, progress_callback=progress_cb)
            if not zip_path:
                if status_cb:
                    status_cb(UPDATE_STATE.get("error", "下载修复包失败"))
                return
            if UPDATE_STATE.get("cache_reused"):
                if status_cb:
                    status_cb("已复用已下载的完整包，正在应用补全...")
            elif status_cb:
                status_cb("修复包下载完成，正在应用补全...")
            success, count, new_version, pending_count = extract_and_apply_update(zip_path)
            if not success:
                if status_cb:
                    status_cb(UPDATE_STATE.get("error", "应用修复失败"))
                return
            m2, c2, _st2 = verify_assets()
            if status_cb:
                status_cb(f"资源修复完成：缺失 {len(m2)} / 损坏 {len(c2)}，即将重启生效")
            cleanup_cache()
            time.sleep(2)
            restart_game()
        except Exception as e:
            UPDATE_STATE["error"] = f"修复异常: {e}"
            if status_cb:
                status_cb(UPDATE_STATE["error"])

    thread = threading.Thread(target=_repair_thread, daemon=True)
    thread.start()
    return thread


def get_update_status():
    """获取当前更新状态（游戏UI轮询用）"""
    return dict(UPDATE_STATE)


def format_size(bytes_val):
    """格式化文件大小"""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.2f} MB"


def format_speed(bytes_per_sec):
    """格式化下载速度"""
    return format_size(bytes_per_sec) + "/s"


def fetch_release_notes(timeout=6):
    """获取 GitHub 最新 release 的发布说明（版本号 + 正文），失败返回 (None, None)。

    仅公开只读接口（经 gh-proxy，无需令牌），供游戏内“更新说明”界面展示。
    结果缓存到模块级变量，避免重复请求。
    """
    global _RELEASE_NOTES_CACHE
    if _RELEASE_NOTES_CACHE is not None:
        return _RELEASE_NOTES_CACHE
    try:
        api_url = _gh_proxy_url(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest")
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "ZombieSurvivor-Updater/1.0",
            "Accept": "application/vnd.github.v3+json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        ver = (data.get("tag_name") or "").lstrip("v") or get_current_version()
        body = data.get("body", "") or ""
        _RELEASE_NOTES_CACHE = (ver, body)
        return _RELEASE_NOTES_CACHE
    except Exception:
        return (None, None)


def clear_release_notes_cache():
    """清空发布说明缓存（检查更新后调用，以便拿到最新说明）"""
    global _RELEASE_NOTES_CACHE
    _RELEASE_NOTES_CACHE = None


_RELEASE_NOTES_CACHE = None


# 启动时清理
cleanup_backup()
UPDATE_STATE["current_version"] = get_current_version()
