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
    "cache_reused": False,   # 是否复用了已下载的缓存包
    "error": None,
    "changelog": "",
    "download_url": "",
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


def _gh_proxy_url(url):
    """给所有GitHub相关URL加gh-proxy前缀（统一代理）"""
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
            return GH_PROXY + url
    return url


def check_for_updates(timeout=10):
    """
    检查GitHub最新版本
    返回: (latest_version, download_url, changelog) 或 None
    """
    global UPDATE_STATE
    UPDATE_STATE["checking"] = True
    UPDATE_STATE["error"] = None

    try:
        # GitHub API 获取最新release
        api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
        # API也走代理
        api_url_proxied = _gh_proxy_url(api_url)

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
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith('.zip') and ('zombie' in name or 'survivor' in name or 'game' in name or 'update' in name):
                download_url = asset.get("browser_download_url")
                break
        # 如果没找到特定名称的，取第一个zip
        if not download_url:
            for asset in assets:
                if asset.get("name", "").lower().endswith('.zip'):
                    download_url = asset.get("browser_download_url")
                    break

        # 如果release没有assets，尝试源码包
        if not download_url:
            download_url = data.get("zipball_url")

        if not download_url:
            UPDATE_STATE["error"] = "未找到更新包"
            return None

        UPDATE_STATE["latest_version"] = latest_version
        UPDATE_STATE["changelog"] = changelog
        UPDATE_STATE["download_url"] = download_url
        UPDATE_STATE["checking"] = False

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


def download_update(download_url, progress_callback=None, version=None):
    """
    下载更新包，带进度条；支持复用已下载缓存、断点续传（.part）。
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

        # 2) 断点续传：复用已下载的部分文件
        proxied_url = _gh_proxy_url(download_url)
        headers = {"User-Agent": "ZombieSurvivor-Updater/1.0"}
        resume_from = 0
        if os.path.exists(part_path) and os.path.getsize(part_path) > 0:
            resume_from = os.path.getsize(part_path)
            headers["Range"] = f"bytes={resume_from}-"
            # 目标为最终 zip 时直接续写 part
        req = urllib.request.Request(proxied_url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
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
            with open(part_path, mode) as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
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

        # 2. 下载（复用缓存/断点续传）
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


def fetch_release_notes(timeout=10):
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
