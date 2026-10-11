#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.0 错误可忽略静默运行机制

首次出现某类错误时展示日志并询问用户是否忽略；选择忽略后，同类错误
再次出现则静默跳过（不打断游戏）；未选择忽略的错误按原逻辑处理。
"""
import traceback


class ErrorSilencer:
    """按 (异常类型, 文件, 行号) 指纹归类错误的静默器"""

    def __init__(self):
        # 已忽略指纹 -> 静默
        self.ignored = set()
        # 已知但未忽略指纹 -> 按原逻辑报错（只询问一次）
        self.known = set()
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
    def short_trace(exc, max_lines=4):
        try:
            tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
            lines = [l.rstrip() for l in tb_lines if l.strip()]
            return "\n".join(lines[-max_lines:])
        except Exception:
            return str(exc)

    def handle(self, exc):
        """返回动作：'ignore' 静默继续 / 'ask' 需要用户决策 / 'raise' 原逻辑处理"""
        fp = self.fingerprint(exc)
        if fp in self.ignored:
            return "ignore"
        if fp in self.known:
            return "raise"
        # 首次出现：进入待决策
        if fp != self.pending_ask:
            self.pending_ask = fp
            self.pending_info = {
                "message": str(exc),
                "trace": self.short_trace(exc),
                "fp": fp,
            }
        return "ask"

    def decide(self, ignore: bool):
        """用户决策：True=忽略并静默，False=不忽略按原逻辑"""
        if self.pending_ask is None:
            return
        if ignore:
            self.ignored.add(self.pending_ask)
        else:
            self.known.add(self.pending_ask)
        self.pending_ask = None
        self.pending_info = None
