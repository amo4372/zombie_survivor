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
UPDATE_CACHE_DIR = "_update_cache"
BACKUP_DIR = "_update_backup"

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


def download_update(download_url, progress_callback=None):
    """
    下载更新包，带进度条
    返回: 下载的文件路径 或 None
    """
    global UPDATE_STATE
    UPDATE_STATE["downloading"] = True
    UPDATE_STATE["download_progress"] = 0.0
    UPDATE_STATE["error"] = None

    try:
        # 确保缓存目录存在
        os.makedirs(UPDATE_CACHE_DIR, exist_ok=True)
        output_path = os.path.join(UPDATE_CACHE_DIR, "update_package.zip")

        # 走代理
        proxied_url = _gh_proxy_url(download_url)

        req = urllib.request.Request(proxied_url, headers={
            "User-Agent": "ZombieSurvivor-Updater/1.0",
        })

        with urllib.request.urlopen(req, timeout=60) as resp:
            total_size = int(resp.headers.get('Content-Length', 0))
            UPDATE_STATE["total_bytes"] = total_size
            downloaded = 0
            start_time = time.time()
            last_update = start_time
            chunk_size = 8192

            with open(output_path, 'wb') as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    UPDATE_STATE["downloaded_bytes"] = downloaded

                    # 计算进度和速度
                    if total_size > 0:
                        progress = downloaded / total_size
                        UPDATE_STATE["download_progress"] = progress

                        # 每秒更新一次速度
                        now = time.time()
                        if now - last_update >= 0.5:
                            elapsed = now - start_time
                            if elapsed > 0:
                                UPDATE_STATE["download_speed"] = int(downloaded / elapsed)
                            last_update = now

                        # 调用回调
                        if progress_callback:
                            try:
                                progress_callback(progress, downloaded, total_size)
                            except:
                                pass
                        if _progress_callback:
                            try:
                                _progress_callback(progress, downloaded, total_size)
                            except:
                                pass

        UPDATE_STATE["downloading"] = False
        UPDATE_STATE["download_progress"] = 1.0
        return output_path

    except Exception as e:
        UPDATE_STATE["error"] = f"下载失败: {str(e)}"
        UPDATE_STATE["downloading"] = False
        return None


def extract_and_apply_update(zip_path, game_dir=None):
    """
    解压更新包并应用（热更新）
    策略：备份当前文件 -> 解压新文件覆盖 -> 验证 -> 删除备份
    """
    global UPDATE_STATE
    UPDATE_STATE["extracting"] = True
    UPDATE_STATE["error"] = None

    if game_dir is None:
        game_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        # 1. 备份当前关键文件
        backup_path = os.path.join(game_dir, BACKUP_DIR)
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path, ignore_errors=True)
        os.makedirs(backup_path, exist_ok=True)

        # 备份所有.py文件和version.txt
        backup_files = []
        for f in os.listdir(game_dir):
            fpath = os.path.join(game_dir, f)
            if os.path.isfile(fpath) and (f.endswith('.py') or f == 'version.txt'):
                shutil.copy2(fpath, os.path.join(backup_path, f))
                backup_files.append(f)

        # 2. 解压更新包到临时目录
        temp_dir = tempfile.mkdtemp(prefix="zombie_update_")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_dir)

        # 3. 找到更新包中的游戏文件（可能在子目录中）
        update_files_dir = temp_dir
        # 检查是否有子目录包含.py文件
        for root, dirs, files in os.walk(temp_dir):
            py_files = [f for f in files if f.endswith('.py')]
            if py_files:
                update_files_dir = root
                break

        # 4. 复制新文件覆盖
        applied_count = 0
        for f in os.listdir(update_files_dir):
            src = os.path.join(update_files_dir, f)
            dst = os.path.join(game_dir, f)
            if os.path.isfile(src):
                # 只覆盖.py、.txt、.json等文本文件，避免覆盖用户存档
                if f.endswith('.py') or f == 'version.txt' or f.endswith('.md'):
                    shutil.copy2(src, dst)
                    applied_count += 1

        # 5. 验证新版本号
        new_version = get_current_version()
        if new_version == "0.0.0":
            raise Exception("更新后版本号无效")

        # 6. 清理临时文件和备份（更新成功后）
        shutil.rmtree(temp_dir, ignore_errors=True)
        # 保留备份，下次启动时删除
        UPDATE_STATE["current_version"] = new_version
        UPDATE_STATE["extracting"] = False
        UPDATE_STATE["update_available"] = False

        return True, applied_count, new_version

    except Exception as e:
        UPDATE_STATE["error"] = f"应用更新失败: {str(e)}"
        UPDATE_STATE["extracting"] = False

        # 回滚：从备份恢复
        try:
            backup_path = os.path.join(game_dir, BACKUP_DIR)
            if os.path.exists(backup_path):
                for f in os.listdir(backup_path):
                    src = os.path.join(backup_path, f)
                    dst = os.path.join(game_dir, f)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
        except:
            pass

        return False, 0, None


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

        # 2. 下载
        zip_path = download_update(download_url, progress_callback=progress_cb)
        if not zip_path:
            if status_cb:
                status_cb(UPDATE_STATE.get("error", "下载失败"))
            return

        if status_cb:
            status_cb("下载完成，正在应用更新...")

        # 3. 应用更新
        success, count, new_version = extract_and_apply_update(zip_path)
        if not success:
            if status_cb:
                status_cb(UPDATE_STATE.get("error", "应用更新失败，已回滚"))
            return

        if status_cb:
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


# 启动时清理
cleanup_backup()
UPDATE_STATE["current_version"] = get_current_version()
