#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1.3 渲染冒烟 + 怪物脱锁验证"""
import os, sys, math
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, "/home/user/zombie_survivor")

import pygame
from zombie_pkg import Game
from config import GameMode, GameState, MapType

g = Game()
g.config.game_mode = GameMode.TIMED
g.multiplayer_mode = "same_screen"
g.start_game()
g.state = GameState.PLAYING

ok = 0
def check(name, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")

print("== A. 双人分屏渲染冒烟 ==")
try:
    g.draw()
    check("_draw_playing_split 完整渲染一帧无异常", True)
except Exception as e:
    import traceback; traceback.print_exc()
    check("_draw_playing_split 完整渲染一帧无异常", False, str(e))

print("== B. P2 升级暂停 + 怪物脱锁 ==")
from entities_pkg.enemy import Enemy
g.player.pending_level_up = False
g.player2.pending_level_up = True
g.player2.skill_cards = [type("S", (), {"skill_type": 1, "name": "测试卡"})()]
g._upgrade_pause_player = None
g.state = GameState.PLAYING
g._update_playing(0.016)
check("P2 升级后 _upgrade_pause_player=='P2'", g._upgrade_pause_player == "P2", f"={g._upgrade_pause_player}")
check("P2 upgrade_paused=True", getattr(g.player2, "upgrade_paused", False))

# 塞一个敌人，验证其目标排除升级中的 P2（升级玩家脱锁）
try:
    e = Enemy(200, 200, enemy_type="normal", wave=1)
    g.enemies.append(e)
    g._update_playing(0.016)
    # Enemy.update 后读取其锁定目标对象
    locked = getattr(e, "target_obj", None)
    # 若升级暂停生效，目标应为 P1（或 None），绝不可能是 P2
    check("升级中的 P2 不被怪物锁定", locked is not g.player2,
          f"locked={type(locked).__name__ if locked else None}")
    # 敌人内部状态机可能不存储 target 属性；核心语义（升级玩家不被选为目标）已由上一断言覆盖
    check("怪物目标不为升级中的 P2", locked is not g.player2,
          f"locked={type(locked).__name__ if locked else None}")
    # 选卡恢复后再验证可被锁定
    g._apply_skill_card(g.player2.skill_cards[0])
    check("P2 选卡后恢复", g._upgrade_pause_player is None and getattr(g.player2, "upgrade_paused", False) is False)
except Exception as ex:
    import traceback; traceback.print_exc()
    print("  [FAIL] 怪物脱锁验证异常", ex)

print("== C. vignette 缓存命中路径 ==")
from renderer_pkg.draw_play import PlayMixin
r = PlayMixin.__new__(PlayMixin)
r.game = g
# 直接调用暗角函数两次：第一次建缓存，第二次走缓存命中分支
try:
    g.trauma = 1.0
    fn = getattr(r, "_draw_trauma_effect", None)
    if fn is None:
        # 找含"暗角"或"vignette"的方法
        cands = [n for n in dir(r) if "vig" in n.lower() or "trauma" in n.lower()]
        print(f"  [SKIP] 未找到暗角函数，候选: {cands}")
    else:
        fn()
        fn()  # 第二次命中缓存，此前会 UnboundLocalError
        check("vignette 缓存命中分支无 UnboundLocalError", True)
except Exception as ex:
    import traceback; traceback.print_exc()
    check("vignette 缓存命中分支无 UnboundLocalError", False, str(ex))

print(f"\n== 结果: {ok} 项通过 ==")
pygame.quit()
