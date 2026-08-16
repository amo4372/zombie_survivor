#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日志系统模块"""

import traceback
import datetime
import os

class GameLogger:
    def __init__(self, log_file="game_log.txt"):
        self.log_file = log_file
        self._write("=" * 60)
        self._write(f"游戏启动时间: {datetime.datetime.now()}")
        self._write("=" * 60)

    def _write(self, msg):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except:
            pass

    def info(self, msg):
        line = f"[INFO] {msg}"
        self._write(line)
        print(line)

    def error(self, msg):
        line = f"[ERROR] {msg}"
        self._write(line)
        print(line)

    def debug(self, msg):
        line = f"[DEBUG] {msg}"
        self._write(line)
        print(line)

    def log_exception(self, e):
        self._write(f"[EXCEPTION] {str(e)}")
        self._write(traceback.format_exc())
        print(f"[EXCEPTION] {str(e)}")
        print(traceback.format_exc())
