# -*- coding: utf-8 -*-
"""gamedata 命令行工具

    python -m gamedata rebuild    # 用代码默认值重建（会清空手工修改！）
    python -m gamedata sync       # 只补缺失行，保留手工修改（推荐）
    python -m gamedata export     # 导出 game_data.json（便于对比/版本管理）
    python -m gamedata verify     # 校验完整性
    python -m gamedata show 表名   # 打印某张表
"""

import json
import os
import sqlite3
import sys

from .schema import create_all, TABLES
from . import seed as S
from .db import connect
from . import defaults as D


def _path():
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(_root, "game_data.db")


def cmd_sync():
    _p = _path()
    _new = not os.path.exists(_p)
    _conn = connect(_p)
    create_all(_conn)
    S.seed_tuning(_conn)
    S.seed_difficulty(_conn)
    _r = S.seed_all(_conn)
    _conn.close()
    print(f"数据库: {_p}（{'新建' if _new else '已存在，仅补缺失行'}）")
    print(f"补种行数: {_r}")
    return 0


def cmd_rebuild():
    _p = _path()
    if os.path.exists(_p):
        print("警告：将清空并重建，手工修改的数值会丢失。")
    _conn = connect(_p)
    create_all(_conn)
    _r = S.rebuild(_conn)
    _conn.close()
    print(f"已重建: {_p}，行数 {_r}")
    return 0


def cmd_export():
    _p = _path()
    if not os.path.exists(_p):
        print("数据库不存在，先运行 sync")
        return 1
    _conn = connect(_p)
    _conn.row_factory = sqlite3.Row
    _out = {}
    for _t in TABLES:
        try:
            _out[_t] = [dict(_r) for _r in _conn.execute(f"SELECT * FROM {_t}")]
        except Exception:
            _out[_t] = []
    _conn.close()
    _dst = os.path.join(os.path.dirname(_p), "game_data.json")
    with open(_dst, "w", encoding="utf-8") as _f:
        json.dump(_out, _f, ensure_ascii=False, indent=2)
    print(f"已导出: {_dst}（{ {k: len(v) for k, v in _out.items()} }）")
    return 0


def cmd_verify():
    _p = _path()
    print(f"数据库: {_p}")
    print(f"  存在: {os.path.exists(_p)}")
    if not os.path.exists(_p):
        return 1
    _conn = connect(_p)
    _conn.row_factory = sqlite3.Row
    _bad = 0
    for _t in TABLES:
        try:
            _n = _conn.execute(f"SELECT COUNT(*) FROM {_t}").fetchone()[0]
            print(f"  {_t}: {_n} 行")
        except Exception as _e:
            print(f"  {_t}: 缺失/损坏 ({_e})")
            _bad += 1
    # 关键行检查
    _w = D.extract_weapons()
    _have = {_r["key"] for _r in _conn.execute("SELECT key FROM weapons")}
    _miss = [k for k in _w if k not in _have]
    print(f"  武器缺失: {len(_miss)} {_miss[:5]}")
    _sk = D.extract_skills()
    _have_s = {_r["key"] for _r in _conn.execute("SELECT key FROM skills")}
    _miss_s = [k for k in _sk if k not in _have_s]
    print(f"  技能缺失: {len(_miss_s)} {_miss_s[:5]}")
    _e = D.extract_enemies()
    _have_e = {_r["key"] for _r in _conn.execute("SELECT key FROM enemies")}
    _miss_e = [k for k in _e if k not in _have_e]
    print(f"  敌人缺失: {len(_miss_e)} {_miss_e[:5]}")
    _conn.close()
    print("结论:", "完整" if (_bad == 0 and not _miss and not _miss_e) else "有缺失（运行 sync 补全）")
    return 0


def cmd_show(table):
    _p = _path()
    if not os.path.exists(_p):
        print("数据库不存在")
        return 1
    _conn = connect(_p)
    _conn.row_factory = sqlite3.Row
    try:
        _rows = [dict(_r) for _r in _conn.execute(f"SELECT * FROM {table}")]
    except Exception as _e:
        print(f"读取失败: {_e}")
        return 1
    _conn.close()
    for _r in _rows:
        print(json.dumps(_r, ensure_ascii=False))
    print(f"（{len(_rows)} 行）")
    return 0


def main(argv=None):
    _argv = list(sys.argv[1:] if argv is None else argv)
    if not _argv:
        print(__doc__)
        return 0
    _c = _argv[0]
    if _c == "sync":
        return cmd_sync()
    if _c == "rebuild":
        return cmd_rebuild()
    if _c == "export":
        return cmd_export()
    if _c == "verify":
        return cmd_verify()
    if _c == "show":
        return cmd_show(_argv[1] if len(_argv) > 1 else "weapons")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
