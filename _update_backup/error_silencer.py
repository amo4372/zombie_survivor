#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.7 错误可忽略运行机制（改造）

v2.2.0 原始设计：首次出现某类错误时询问，选择忽略后同类静默。
v2.2.7 改造（用户反馈"gamelog不记录了 / 每次错误都要弹窗 / 文本可复制"）：
- 每次出现错误都弹出界面（仅用户选择"忽略"后，同类错误才静默，防刷屏）
- 不忽略 = 仅本次继续运行，同类错误下次仍会弹窗（不再走"报错退出"路径）
- 完整错误日志（完整 traceback）随弹窗展示，并强制写入 data/game_error.log
  （不受游戏日志开关影响，便于调试复制）
"""
import traceback
import os
import datetime


class ErrorSilencer:
    """按 (异常类型, 文件, 行号) 指纹归类错误的静默器"""

    # 独立错误日志路径（v2.2.7：强制记录，不受 enable_logging 开关影响）
    ERROR_LOG = os.path.join("data", "game_error.log")

    def __init__(self):
        # 已忽略指纹 -> 同类错误静默
        self.ignored = set()
        # 待用户决策的指纹（正在弹询问框）
        self.pending_ask = None
        # 当前询问中的错误信息
        self.pending_info = None

    @staticmethod
    def fingerprint(exc):
        """生成错误指纹：类型名+首个堆栈帧的文件与行号"""
        try:
            tb = exc.__traceback__
            frames = []
            while tb is not None:
                frames.append((tb.tb_frame.f_code.co_filename, tb.tb_lineno))
                tb = tb.tb_next
            if not frames:
                return (type(exc).__name__, "unknown", 0)
            f = frames[-1]  # 最内层帧（异常实际抛出点）
            return (type(exc).__name__, str(f[0]), f[1])
        except Exception:
            return (type(exc).__name__, "unknown", 0)

    @staticmethod
    def full_trace(exc, max_lines=40):
        """完整错误堆栈（v2.2.7：不再只截断 4 行，便于调试）"""
        try:
            tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
            lines = [l.rstrip() for l in tb_lines if l.strip()]
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n...（共 {len(lines)} 行，完整见日志文件）"
            return "\n".join(lines)
        except Exception:
            return str(exc)

    def record_to_file(self, exc):
        """强制写入独立错误日志文件（不受游戏日志开关影响）"""
        try:
            os.makedirs("data", exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fp = self.fingerprint(exc)
            full = traceback.format_exc()
            with open(self.ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n===== {ts} 指纹={fp} =====\n{str(exc)}\n{full}\n")
            return self.ERROR_LOG
        except Exception:
            try:
                with open("game_error.log", "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now()}: {exc}\n{traceback.format_exc()}\n")
                return "game_error.log"
            except Exception:
                return None

    def handle(self, exc):
        """返回动作：'ignore' 静默继续 / 'ask' 需要用户决策
        v2.2.7：不再有 'raise' 路径——每次错误都弹窗询问（除非同类已被忽略）"""
        fp = self.fingerprint(exc)
        if fp in self.ignored:
            return "ignore"
        # 每次出现错误都要弹出界面（不同错误/同类未忽略）
        if fp != self.pending_ask:
            self.pending_ask = fp
            log_path = self.record_to_file(exc)
            self.pending_info = {
                "message": str(exc),
                "trace": self.full_trace(exc),
                "fp": fp,
                "log_path": log_path,
            }
        return "ask"

    def decide(self, ignore: bool):
        """用户决策：True=忽略（同类静默）；False=仅本次继续（同类下次仍弹窗）"""
        if self.pending_ask is None:
            return
        if ignore:
            self.ignored.add(self.pending_ask)
        self.pending_ask = None
        self.pending_info = None
