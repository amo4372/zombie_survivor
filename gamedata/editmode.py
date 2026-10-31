# -*- coding: utf-8 -*-
"""数据编辑模式（后门开关）—— v2.8.5

用途
----
游戏正常启动时会做一次"数据库自动更新"：把新版本新增的表/行补进
`game_data.db`（用 INSERT OR IGNORE，只补不覆盖，你调过的数值不会丢）。

但当你想**自己改数据做测试**时，这个行为很碍事：
刚删掉一行想看缺失时的表现，下次启动又被补回来了。

开启"数据编辑模式"后，游戏**完全不碰数据库**（只读取），你可以自由改、删、测试。
确认无误后关掉开关，下次启动恢复正常自动更新。

三种开启方式（优先级从高到低）
------------------------------
1. 命令行参数：`python main.py --no-db-sync`
2. 环境变量：`ZS_DB_NO_SYNC=1 python main.py`
3. 开关文件：游戏根目录放一个 `.db_edit_mode` 文件
   （可用 `python -m gamedata edit on|off|status` 切换，或手动创建/删除）

注意
----
- 数据库文件不存在时**无论如何都会建库**（否则游戏没法跑），
  编辑模式只影响"已存在数据库的补种"。
- 编辑模式下**热重载依然生效**：改库后重新开局即看到新数值。
"""

import os
import sys

ENV_VAR = "ZS_DB_NO_SYNC"
ARGV_FLAGS = ("--no-db-sync", "--db-edit", "--no-db-update")
FLAG_FILE = ".db_edit_mode"


def game_root():
    """工程根目录（本文件的上上级）"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def flag_path(root=None):
    return os.path.join(root or game_root(), FLAG_FILE)


def from_argv(argv=None):
    """命令行参数是否开启"""
    try:
        _a = list(sys.argv if argv is None else argv)
        return any(_x in _a for _x in ARGV_FLAGS)
    except Exception:
        return False


def from_env():
    """环境变量是否开启"""
    return str(os.environ.get(ENV_VAR, "")).strip().lower() in ("1", "true", "yes", "on")


def from_file(root=None):
    """开关文件是否开启"""
    try:
        return os.path.exists(flag_path(root))
    except Exception:
        return False


def enabled(argv=None, root=None):
    """是否处于数据编辑模式（不触发数据库自动更新）"""
    return from_argv(argv) or from_env() or from_file(root)


def source(argv=None, root=None):
    """返回开启来源，未开启返回 None"""
    if from_argv(argv):
        return "命令行参数"
    if from_env():
        return f"环境变量 {ENV_VAR}"
    if from_file(root):
        return f"开关文件 {FLAG_FILE}"
    return None


def set_enabled(on, root=None):
    """写入/删除开关文件，返回操作后的状态"""
    _p = flag_path(root)
    try:
        if on:
            with open(_p, "w", encoding="utf-8") as _f:
                _f.write("# 数据编辑模式：游戏不会自动更新数据库，可自由改数据测试\n"
                         "# 关闭：python -m gamedata edit off（或删除本文件）\n")
            return True
        if os.path.exists(_p):
            os.remove(_p)
        return False
    except Exception:
        return from_file(root)


def banner():
    """启动时的提示文字"""
    _s = source()
    if not _s:
        return None
    return (f"[数据编辑模式] 已通过{_s}开启 —— 游戏不会自动更新数据库，"
            f"可自由编辑 game_data.db 测试。关闭：python -m gamedata edit off")
