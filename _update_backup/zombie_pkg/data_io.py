# -*- coding: utf-8 -*-
"""数据目录工具（v2.0.11）：所有运行期数据统一存入游戏根目录下 data/ 专门文件夹，
与代码/资源分离，更新时不会被覆盖。旧版平铺存档（游戏根同名文件）启动时自动迁移。
"""
import os

DATA_DIR_NAME = "data"


def get_base_dir():
    """仓库根（兼容 PyInstaller frozen 场景）"""
    if getattr(__import__('sys'), 'frozen', False):
        return os.path.dirname(__import__('sys').executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir(base_path=None):
    """获取（并确保存在）数据目录"""
    base = base_path if base_path is not None else get_base_dir()
    d = os.path.join(base, DATA_DIR_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def migrate_legacy(base_path, filename):
    """旧版平铺存档迁移：旧位置（游戏根/<filename>）存在时移入 data/。
    data/ 已有同名新档 → 旧档改名 <filename>.legacy_bak 保留（不再参与加载）。
    返回 True 表示发生迁移。幂等安全。"""
    if base_path is None:
        base_path = get_base_dir()
    data_dir = get_data_dir(base_path)
    old = os.path.join(base_path, filename)
    new = os.path.join(data_dir, filename)
    if os.path.exists(old):
        try:
            if not os.path.exists(new):
                os.replace(old, new)
            else:
                os.replace(old, new + ".legacy_bak")
            return True
        except Exception:
            pass
    return False
