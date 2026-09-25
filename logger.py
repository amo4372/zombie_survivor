#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日志系统模块

设计目标：
- 详细、带时间戳的日志写入游戏日志文件 game_log.txt
- 默认不打印到终端（控制台输出移除，避免刷屏干扰）
- 定期清理：日志文件超过 MAX_BYTES 时自动轮转（保留一份 .old），避免无限膨胀
- 用户可选开关：通过 GameLogger.set_enabled(flag) 或 config 的 enable_logging 控制
"""

import traceback
import datetime
import os

# 日志文件单文件最大字节数，超过则轮转清理（默认 2MB）
LOG_MAX_BYTES = 2 * 1024 * 1024
# 保留的历史日志份数（轮转出的 .old 超过该数量时删除更旧的）
LOG_KEEP_OLD = 3


class GameLogger:
    def __init__(self, log_file="game_log.txt", enabled=True, console=False):
        self.log_file = log_file
        self.enabled = enabled          # 总开关（用户可选）
        self.console = console          # 是否同时打印到终端（默认关闭）
        self._rotate_if_needed()
        self.info("游戏启动")

    # ---------- 开关与清理 ----------
    def set_enabled(self, flag):
        """用户开关：启用/停用日志记录"""
        self.enabled = bool(flag)

    def set_console(self, flag):
        """是否同时输出到终端（调试用，默认关闭）"""
        self.console = bool(flag)

    def is_enabled(self):
        return self.enabled

    def clear(self):
        """手动清空日志文件"""
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
        except Exception:
            pass

    def _rotate_if_needed(self):
        """定期清理：超过大小阈值则轮转（当前文件->.old，并删除过旧的历史）"""
        try:
            if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > LOG_MAX_BYTES:
                for i in range(LOG_KEEP_OLD, 0, -1):
                    older = self.log_file + (".old" if i == 1 else f".old{i}")
                    if os.path.exists(older):
                        os.remove(older)
                bak = self.log_file + ".old"
                if os.path.exists(bak):
                    os.remove(bak)
                os.rename(self.log_file, bak)
        except Exception:
            pass

    def _write(self, msg):
        if not self.enabled:
            return
        self._rotate_if_needed()
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def _emit(self, level, msg):
        if not self.enabled:
            return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        self._write(line)
        if self.console:
            print(line)

    # ---------- 日志级别 ----------
    def info(self, msg):
        self._emit("INFO", msg)

    def error(self, msg):
        self._emit("ERROR", msg)

    def warning(self, msg):
        self._emit("WARN", msg)

    def debug(self, msg):
        self._emit("DEBUG", msg)

    def log_exception(self, e):
        if not self.enabled:
            return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._write(f"[{ts}] [EXCEPTION] {str(e)}")
        self._write(traceback.format_exc())
        if self.console:
            print(f"[EXCEPTION] {str(e)}")
            print(traceback.format_exc())
