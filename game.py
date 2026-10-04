#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主游戏模块壳（v2.0.9 起逻辑拆分至 zombie_pkg 包，保持 import 兼容）"""
from zombie_pkg import Game, Config, logger, _save_encrypt, _save_decrypt  # noqa: F401
from config import GameState  # noqa: F401  （兼容 from game import GameState）

if __name__ == "__main__":
    try:
        game = Game()
        game.run()
    except Exception as e:
        logger.log_exception(e)
        raise

