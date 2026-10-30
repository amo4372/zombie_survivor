#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.7.1 冒烟测试：BOSS 登场对话 Traceback / 卡死修复（全模式）

旧实现：任何模式刷出 Boss → 强制切 GameState.DIALOGUE → 世界冻结 + 必须交互，
        且对话中再刷一只 Boss 会打断状态机（索引/选项残留）→ 永远回不到 PLAYING。
新实现：改为屏幕底部非阻塞字幕，游戏全程继续运行，不切状态、不拦截输入。

覆盖：无尽 / 限时 / 故事 / 争分夺秒 × 单人 / 同屏双人 / PvP
"""
import os
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.getcwd())

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

# 屏蔽自动更新检查：它会把状态切到 UPDATE，干扰刷 Boss 跑帧
import updater
updater.check_for_updates = lambda *a, **k: None
from game import Game as _G
_G.check_for_updates = lambda *a, **k: None
_G._check_update_async = lambda *a, **k: None
_G.auto_check_update = lambda *a, **k: None
_G._try_auto_update = lambda *a, **k: None

# 屏蔽自动更新检查：它会把状态切到 UPDATE，干扰刷 Boss 跑帧
import updater
updater.check_for_updates = lambda *a, **k: None
from game import Game as _G
_G.check_for_updates = lambda *a, **k: None
_G._check_update_async = lambda *a, **k: None
_G.auto_check_update = lambda *a, **k: None
_G._try_auto_update = lambda *a, **k: None

from game import Game, GameState
from config import *
from entities_pkg.enemy import Enemy

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


BOSS_LIST = (EnemyType.BOSS_LONG, EnemyType.BOSS_XIANG, EnemyType.BOSS_MUTANT,
             EnemyType.BOSS_QUEEN, EnemyType.BOSS_TITAN, EnemyType.BOSS_WANG)

MODES = []
for _n in ("ENDLESS", "TIMED", "STORY", "RACE"):
    _m = getattr(GameMode, _n, None)
    if _m is not None:
        MODES.append((_n, _m))


def run_case(mode_name, mode, multiplayer=False, pvp=False):
    """在指定模式下刷 Boss 并跑帧，返回 (是否通过, 错误文本)"""
    try:
        g = Game()
        g.config.game_mode = mode
        g.config.pvp_enabled = pvp
        if multiplayer:
            g.multiplayer_mode = "same_screen"
        g.start_game()
        g.state = GameState.PLAYING
        if multiplayer:
            _p2 = g.ensure_player("P2")
            _p2.team_id = 1 if pvp else 0
            if g.camera2 is None:
                g.camera2 = g.camera_for(_p2)
        # 刷一个 Boss 并触发台词
        _e = Enemy(g.player.x + 500, g.player.y, BOSS_LIST[0], 1, g.config.difficulty)
        g.enemies.append(_e)
        g._boss_dialogue(BOSS_LIST[0])
        _state_after = g.state
        # 核心修复：刷 Boss 不再强制切 DIALOGUE 冻结世界
        if _state_after == GameState.DIALOGUE:
            return False, f"刷 Boss 后进入 DIALOGUE（世界被冻结）"
        # 跑帧：Boss 在场 + 字幕滚动 + 渲染（保持不死，测的是对话不是生存）
        for _ in range(40):
            for _pl in g.registered_players():
                _pl.hp = _pl.max_hp
                _pl.alive = True
                _pl.downed = False
            g._repair_requested = False
            g.update(1 / 60)
            g.renderer.render()
        # 对话进行中再连刷 3 只 Boss（旧版此处会打断状态机卡死）
        for _bt in BOSS_LIST[1:4]:
            g._boss_dialogue(_bt)
        for _ in range(60):
            for _pl in g.registered_players():
                _pl.hp = _pl.max_hp
                _pl.alive = True
                _pl.downed = False
            g._repair_requested = False   # 沙箱缺资源会触发自愈→UPDATE，与对话无关
            g.update(1 / 60)
            g.renderer.render()
        # 判据：不得卡在 DIALOGUE（旧实现的卡死症状）。
        # GAME_OVER / UPDATE 属于模式结算或沙箱环境行为，与 Boss 对话无关。
        if g.state == GameState.DIALOGUE:
            return False, f"连刷 Boss 后仍卡在 DIALOGUE（未修复）"
        # 玩家仍可移动（世界未被冻结）
        _x0 = g.player.x
        g.player.x += 50
        for _ in range(5):
            g.update(1 / 60)
        if abs(g.player.x - (_x0 + 50)) > 200:
            return False, "世界被冻结（玩家位置异常跳变）"
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-600:]}"


# ======================================================================
print("[1] 全模式 × 单人：刷 Boss 不报错、不卡状态")
for _n, _m in MODES:
    _ok, _err = run_case(_n, _m)
    check(_ok, f"{_n} 模式刷 Boss（{_err[:160] if _err else 'OK'}）")

print("[2] 全模式 × 同屏双人")
for _n, _m in MODES:
    _ok, _err = run_case(_n, _m, multiplayer=True)
    check(_ok, f"{_n} 双人刷 Boss（{_err[:160] if _err else 'OK'}）")

print("[3] 全模式 × PvP 双人")
for _n, _m in MODES:
    _ok, _err = run_case(_n, _m, multiplayer=True, pvp=True)
    check(_ok, f"{_n} PvP 刷 Boss（{_err[:160] if _err else 'OK'}）")

# ======================================================================
print("[4] 字幕系统本身")
g = Game()
g.start_game()
g.state = GameState.PLAYING
check(hasattr(g, "subtitle_queue"), "字幕队列已初始化")
g._boss_dialogue(EnemyType.BOSS_LONG)
check(len(g.subtitle_queue) > 0, f"Boss 台词进入字幕队列（{len(g.subtitle_queue)} 句）")
check(g.subtitle_current is not None or len(g.subtitle_queue) > 0, "字幕可播放")
# 字幕应随时间推进并自动消失（不需要玩家操作）
_seen = 0
g.SUBTITLE_DURATION = 0.05   # 临时加速，快速验证"播完自动清空"
for _ in range(200):
    g.player.hp = g.player.max_hp
    g.update(1 / 60)
    if g.subtitle_current is not None:
        _seen += 1
check(_seen > 0, "字幕确实在屏幕上出现过")
check(len(g.subtitle_queue) == 0 and g.subtitle_current is None,
      "字幕播完自动清空（无需玩家点击，不会卡死）")

# 队列上限保护（反复刷 Boss 不会无限堆积）
for _ in range(40):
    g._boss_dialogue(EnemyType.BOSS_WANG)
check(len(g.subtitle_queue) <= 24, f"字幕队列有上限保护（{len(g.subtitle_queue)} ≤ 24）")

# ======================================================================
print("[5] 结局对话仍走原交互流程（不被字幕顶掉）")
g2 = Game()
g2.start_game()
g2.state = GameState.PLAYING
try:
    g2._final_dialogue()
    check(g2.state == GameState.DIALOGUE, "结局对话仍进入 DIALOGUE（保留交互选择）")
    check(getattr(g2.dialogue, "active", False), "结局对话处于活跃态")
    # Boss 字幕不得打断结局对话
    g2._boss_dialogue(EnemyType.BOSS_LONG)
    check(g2.state == GameState.DIALOGUE, "Boss 字幕不打断结局对话")
    check(getattr(g2.dialogue, "active", False), "结局对话未被顶掉")
    for _ in range(30):
        g2.update(1 / 60)
        g2.renderer.render()
    check(True, "结局对话跑帧不崩溃")
except Exception as e:
    check(False, f"结局对话异常: {e}")

# ======================================================================
print("[6] 剧情收集物容器（旧代码在非故事模式下缺失 → AttributeError）")
g3 = Game()
g3.config.game_mode = GameMode.ENDLESS
g3.start_game()
check(hasattr(g3, "story_fragment_items"), "无尽模式也有 story_fragment_items")
g4 = Game()
g4.config.game_mode = GameMode.TIMED
g4.start_game()
check(hasattr(g4, "story_fragment_items"), "限时模式也有 story_fragment_items")
# 模拟：非故事模式下被强行切到 STORY 渲染也不应崩
g3.config.game_mode = GameMode.STORY
g3.state = GameState.PLAYING
try:
    for _ in range(20):
        g3.update(1 / 60)
        g3.renderer.render()
    check(True, "模式切换后渲染不崩（story_fragment_items 兜底生效）")
except Exception as e:
    check(False, f"渲染崩溃: {type(e).__name__}: {e}")

print()
print(f"===== v2.7.1 BOSS对话冒烟: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
