# -*- coding: utf-8 -*-
"""gamedata 命令行工具

    python -m gamedata rebuild    # 用代码默认值重建（会清空手工修改！）
    python -m gamedata sync       # 只补缺失行，保留手工修改（推荐）
    python -m gamedata export     # 导出 game_data.json（便于对比/版本管理）
    python -m gamedata verify     # 校验完整性
    python -m gamedata show 表名   # 打印某张表
    python -m gamedata edit on|off # 数据编辑模式开关（开启后游戏不自动更新数据库）
    python -m gamedata diff        # 对比数据库与内置默认值的差异
    python -m gamedata sync --force  # 以代码为准覆盖数据库数值
"""

import json
import os
import sqlite3
import sys

from .schema import create_all, TABLES
from . import seed as S
from .db import connect
from . import defaults as D
from . import editmode


def _path():
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(_root, "game_data.db")


def cmd_lock():
    """锁定某行：本地数值永不随版本更新被覆盖"""
    _argv = list(sys.argv[1:])
    from . import db as _db
    _p = _path()
    _conn = connect(_p)
    from .seed import ensure_dataver_columns
    ensure_dataver_columns(_conn)
    _args = [a for a in _argv[1:] if not a.startswith("-")]
    if len(_args) < 2:
        print("用法: python -m gamedata lock <表> <key>")
        return 1
    _t, _k = _args[0], _args[1]
    try:
        _n = _conn.execute(
            f"UPDATE {_t} SET dataver=? WHERE key=?", (999999, _k)).rowcount
        _conn.commit()
        print(f"已锁定 {_t}.{_k}（{_n} 行，本地数值将不再被版本更新覆盖）")
    except Exception as e:
        print(f"锁定失败: {e}")
        return 1
    _conn.close()
    return 0


def cmd_unlock():
    """解锁某行：恢复为可随版本更新"""
    _argv = list(sys.argv[1:])
    _p = _path()
    _conn = connect(_p)
    _args = [a for a in _argv[1:] if not a.startswith("-")]
    if len(_args) < 2:
        print("用法: python -m gamedata unlock <表> <key>")
        return 1
    _t, _k = _args[0], _args[1]
    try:
        _n = _conn.execute(
            f"UPDATE {_t} SET dataver=0 WHERE key=?", (_k,)).rowcount
        _conn.commit()
        print(f"已解锁 {_t}.{_k}（{_n} 行，下次更新将同步为发布数值）")
    except Exception as e:
        print(f"解锁失败: {e}")
        return 1
    _conn.close()
    return 0


def cmd_sync():
    _argv = list(sys.argv[1:])
    _p = _path()
    _new = not os.path.exists(_p)
    _conn = connect(_p)
    create_all(_conn)
    S.seed_tuning(_conn)
    S.seed_difficulty(_conn)
    # v2.8.8：--force 以代码为准覆盖数据库数值（策划改完数值后同步）
    _forced = ("--force" in _argv or "-f" in _argv)
    _a2, _u2, _k2 = S.sync_rows_from_code(_conn, force=_forced)
    print(f"按 dataver 同步：新增 {_a2} / 更新 {_u2} / 保留本地 {_k2}"
          + ("（--force 强制覆盖）" if _forced else ""))
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


def cmd_edit(arg=None):
    """数据编辑模式开关"""
    if arg in ("on", "1", "true", "open"):
        editmode.set_enabled(True)
        print("已开启数据编辑模式（游戏不会自动更新数据库）")
        return 0
    if arg in ("off", "0", "false", "close"):
        editmode.set_enabled(False)
        print("已关闭数据编辑模式（下次启动恢复正常自动更新）")
        return 0
    _on = editmode.enabled()
    print(f"数据编辑模式: {'开启' if _on else '关闭'}"
          + (f"（来源：{editmode.source()}）" if _on else ""))
    print(f"开关文件: {editmode.flag_path()}")
    print("  开启: python -m gamedata edit on")
    print("  关闭: python -m gamedata edit off")
    print("  也可: python main.py --no-db-sync  或  ZS_DB_NO_SYNC=1 python main.py")
    return 0


def cmd_diff():
    """对比数据库当前值与代码内置默认值的差异（便于确认改了什么再发布）"""
    _p = _path()
    if not os.path.exists(_p):
        print("数据库不存在")
        return 1
    _conn = connect(_p)
    _conn.row_factory = sqlite3.Row
    _n = 0
    for _table, _rows in (("weapons", D.extract_weapons()),
                          ("enemies", D.extract_enemies()),
                          ("runes", D.extract_runes()),
                          ("buffs", D.extract_buffs()),
                          ("skills", D.extract_skills())):
        try:
            _db = {_r["key"]: dict(_r) for _r in _conn.execute(f"SELECT * FROM {_table}")}
        except Exception:
            continue
        for _k, _def in _rows.items():
            if not isinstance(_def, dict):
                continue
            _cur = _db.get(_k)
            if _cur is None:
                print(f"  [{_table}] {_k}: 数据库中缺失（将由内置默认值兜底）")
                _n += 1
                continue
            for _f, _dv in _def.items():
                _cv = _cur.get(_f)
                if _cv is None:
                    continue
                # 颜色统一比较：数据库存 hex
                if isinstance(_dv, (tuple, list)) and len(_dv) >= 3:
                    from .db import _coerce_color
                    _cv2 = _coerce_color(_cv)
                    if _cv2 is not None and tuple(_dv[:3]) != _cv2:
                        print(f"  [{_table}] {_k}.{_f}: {tuple(_dv[:3])} → {_cv2}")
                        _n += 1
                    continue
                try:
                    if isinstance(_dv, bool) or isinstance(_cv, bool):
                        _same = bool(_dv) == bool(_cv)
                    elif isinstance(_dv, (int, float)):
                        _same = abs(float(_dv) - float(_cv)) < 1e-9
                    else:
                        _same = str(_dv) == str(_cv)
                except Exception:
                    _same = True
                if not _same:
                    print(f"  [{_table}] {_k}.{_f}: {_dv} → {_cv}")
                    _n += 1
    _conn.close()
    print(f"（共 {_n} 处与内置默认值不同）")
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
    if _c == "edit":
        return cmd_edit(_argv[1] if len(_argv) > 1 else None)
    if _c in ("lock", "unlock"):
        return cmd_lock() if _c == "lock" else cmd_unlock()
    if _c == "diff":
        return cmd_diff()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
