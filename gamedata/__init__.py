# -*- coding: utf-8 -*-
"""gamedata —— 数据与代码行为分离层（v2.8.3）

设计目标
--------
1. **策划只需改数据库**：游戏机制数值全部落在 `game_data.db`（SQLite），
   用任意 SQLite 工具（DB Browser / Navicat / sqlite3）打开即可编辑，改完存盘生效。
2. **代码只负责行为**：代码从 `gamedata` 读数值，不再内联写死数值。
3. **绝不因数据库损坏而崩溃**：任何读取失败 / 缺表 / 缺行，都回退到代码内
   置默认值（`defaults.py`），游戏照常运行。
4. **数据库不被更新覆盖**：`game_data.db` 列入用户数据，自动更新与打包都不会覆盖它。
   缺失时才由代码默认值自动重建。

用法（游戏内）
--------------
    from gamedata import db
    cfg = db.weapon(WeaponType.PISTOL)      # → dict，含 damage/fire_rate/...
    cfg = db.enemy(EnemyType.ZOMBIE_NORMAL) # → dict
    cfg = db.difficulty("普通")              # → dict
    rows = db.table("runes")                # → [dict, ...]

用法（命令行）
--------------
    python -m gamedata rebuild     # 用代码默认值重建数据库（保留不存在的表数据）
    python -m gamedata export      # 导出为 game_data.json（便于对比/版本管理）
    python -m gamedata verify      # 校验数据库完整性（缺表/缺行/类型异常）
"""

import os

DB_FILENAME = "game_data.db"

def db_path(game_dir=None):
    """数据库文件路径（游戏根目录）"""
    if game_dir is None:
        game_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(game_dir, DB_FILENAME)

from .db import GameDatabase

_db = None


def get_db():
    """全局单例"""
    global _db
    if _db is None:
        _db = GameDatabase(db_path())
    return _db


class _Proxy:
    """延迟初始化代理：db.xxx 等价于 get_db().xxx"""

    def __getattr__(self, name):
        return getattr(get_db(), name)

    def __call__(self, *a, **k):
        return get_db()(*a, **k)


db = _Proxy()

__all__ = ["db", "get_db", "GameDatabase", "db_path", "DB_FILENAME"]
