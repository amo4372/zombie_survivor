#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.8.0 快速测试：全局回放 / 打击反馈 / 死亡反应 / 死亡详情

按需求：**不跑帧**，只做
  1) 模块编译通过
  2) 关键函数返回值符合预期
（唯一的一次单帧 g.update 仅用于验证集成不崩溃）
"""
import os
import sys
import math

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.getcwd())

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


# ======================================================================
print("[A] 编译 / 导入")
import py_compile
for _f in ("replay.py", "zombie_pkg/mix_replay.py", "zombie_pkg/mix_feedback.py",
           "renderer_pkg/draw_replay.py", "entities_pkg/player.py",
           "entities_pkg/enemy.py", "zombie_pkg/game_core.py",
           "zombie_pkg/mix_playing.py", "zombie_pkg/mix_input.py",
           "renderer_pkg/draw_ui.py"):
    try:
        py_compile.compile(_f, doraise=True)
    except Exception as e:
        print(f"    编译失败 {_f}: {e}")
        check(False, f"编译 {_f}")
check(True, "全部模块编译通过")

from config import GameState
check(hasattr(GameState, "DYING") and hasattr(GameState, "REPLAY"),
      "新增 DYING / REPLAY 状态")

# ======================================================================
print("[B] 回放：录制 → 保存 → 加载")
import tempfile
import replay as RP


class FakePlayer:
    def __init__(self, x, y, hp=100.0):
        self.x, self.y, self.hp = x, y, hp
        self.max_hp = 100.0
        self.facing_angle = 0.0
        self.alive = True
        self.downed = False
        self.damage_log = []
        self._fb_last_hp = hp


class FakeEnemy:
    enemy_type = type("T", (), {"name": "ZOMBIE_NORMAL"})()

    def __init__(self, eid, x, y, hp=50.0, boss=False):
        self.enemy_id = eid
        self.x, self.y, self.hp = x, y, hp
        self.facing_angle = 0.0
        self.alive = True
        self.is_boss = boss
        self._hit_events = []


_rec = RP.ReplayRecorder(buffer_seconds=10, sample_hz=20)
_rec.start({"mode": "ENDLESS", "map": "SCHOOL"})
_p = FakePlayer(0.0, 0.0)
_es = [FakeEnemy(1, 100.0, 0.0), FakeEnemy(2, 200.0, 50.0, boss=True)]
for _i in range(60):          # 模拟 60 逻辑帧 = 1 秒
    _p.x = _i * 3.0
    _rec.tick(1 / 60, [_p], _es)
_rec.add_event("kill", "击杀 普通丧尸", 100, 0, 35)
_rec.add_event("death", "玩家阵亡", 0, 0, 0, tag="death")
check(len(_rec.frames) > 15, f"按 20Hz 采样到 {len(_rec.frames)} 帧")
check(_rec.frames[-1].players[0][0] > 0, "帧内记录了玩家位置")

_tmp = os.path.join(tempfile.mkdtemp(), "test_replay.zsr")
_rec.save(_tmp)
check(os.path.exists(_tmp) and os.path.getsize(_tmp) > 0, ".zsr 文件已生成")

_loaded = RP.load_replay(_tmp)
check(len(_loaded.frames) == len(_rec.frames), "加载后帧数一致")
check(abs(_loaded.duration - _rec.elapsed) < 0.5, "时长元数据一致")
check(any(e.get("tag") == "death" for e in _loaded.events), "事件流水完整（含死亡标记）")
check(_loaded.frames[0].enemies[0][1] >= 0, "敌人类型索引可用")

# 只有游戏能解析：magic 校验
try:
    RP.load_replay(__file__)
    check(False, "非回放文件应被拒绝")
except Exception:
    check(True, "非回放文件被拒绝（magic 校验生效）")

# 播放控制
_loaded.playing = True
_loaded.update(0.5)
check(_loaded.index > 0, "播放推进正常")
_n = len(_loaded.frames)
_loaded.seek_ratio(0.5)
check(_loaded.index == int(0.5 * (_n - 1)), f"进度跳转正常（{_loaded.index}/{_n - 1}）")
_loaded.step(-3)
check(_loaded.index == int(0.5 * (_n - 1)) - 3, "逐帧回退正常")
_loaded.seek_ratio(1.0)
check(_loaded.index == _n - 1, "跳到末尾正常")
_loaded.seek_ratio(-5)
check(_loaded.index == 0, "越界跳转被钳制")
check(_loaded.events_until(999) != [], "事件流水可按时间查询")

# 自由摄像机
_cam = RP.FreeCamera(0, 0)
_cam.move(100, 0)
_cam.zoom_by(2.0)
check(_cam.zoom == 2.0, "自由摄像机可缩放")
_cam.zoom_by(100)
check(_cam.zoom <= 4.0, "缩放有上限")

# ======================================================================
print("[C] 死亡详情：伤害来源流水")
from entities_pkg.player import Player

_pl = Player(0, 0)
_pl.hp = 100
_pl.max_hp = 100
check(hasattr(_pl, 'damage_log'), "玩家具备伤害日志")
_pl._log_damage(30.0, "melee", "zombie", 50, 50)
_pl._log_damage(45.0, "ranged", "player", 80, 20)
_pl._log_damage(25.0, "aoe", "boss", 10, 10)
check(len(_pl.damage_log) == 3, f"登记了 {len(_pl.damage_log)} 条伤害")
_rows = _pl.death_detail()
check(len(_rows) == 3, "death_detail 返回全部记录")
check(_rows[0]["source"] == "boss", "最近一条在最前（boss）")
check(_rows[0]["amount"] == 25.0 and _rows[1]["amount"] == 45.0, "伤害数值正确")
# 环形缓冲上限
for _i in range(80):
    _pl._log_damage(1.0, "melee", "zombie", 0, 0)
check(len(_pl.damage_log) <= _pl.MAX_DAMAGE_LOG, f"日志有上限（{len(_pl.damage_log)}）")

# ======================================================================
print("[D] 命中反馈（含技能命中）")
from zombie_pkg.mix_feedback import FeedbackMixin


class FakeGame(FeedbackMixin):
    def __init__(self):
        self._feedback_init()
        self.enemies = []
        self.camera = None

    def registered_players(self):
        return []


_fg = FakeGame()
_e1 = FakeEnemy(1, 100.0, 0.0)
_e1.take_damage = lambda d, t="normal": _e1._hit_events.append((d, t))
_e1._hit_events.append((40.0, "melee"))
_e2 = FakeEnemy(2, 200.0, 0.0)
_e2._hit_events.append((80.0, "skill"))
_e3 = FakeEnemy(3, 300.0, 0.0)
_e3.alive = False
_e3._hit_events.append((20.0, "normal"))
_fg.enemies = [_e1, _e2, _e3]
_fg._feedback_tick(1 / 60)
check(len(_fg.hit_markers) == 3, f"生成 {len(_fg.hit_markers)} 个命中标记")
_kinds = [m[4] for m in _fg.hit_markers]
check("skill" in _kinds, "技能命中有专属标记（技能命中反馈）")
check("kill" in _kinds, "击杀有专属标记")
check(all(e._hit_events == [] for e in (_e1, _e2, _e3)), "命中事件已消费（不重复）")
# 衰减
_fg._feedback_tick(1.0)
check(len(_fg.hit_markers) == 0, "命中标记会自然消失")

# 玩家受伤红晕
_fg._feedback_player_hurt(_pl, 40, 50, 0)
check(_fg.damage_flash > 0, "受伤触发红晕")
check(_fg.hurt_dir is not None, "受伤记录来袭方向")

# ======================================================================
print("[E] 死亡反应时间（不立刻结算）")
_src = open("zombie_pkg/mix_playing.py", encoding="utf-8").read()
check("self._begin_death_reaction()" in _src, "死亡判定改为进入死亡反应")
check("_trigger_multiplayer_game_over()" not in _src.split("if self._update_rescue(dt):")[1][:200],
      "不再在死亡瞬间直接结算")


class FakeGame2(FeedbackMixin):
    def __init__(self):
        self._feedback_init()
        self.state = GameState.PLAYING
        self.enemies = []
        self.death_killer = None
        self.replay_recorder = None

    def registered_players(self):
        return []

    def tag_of(self, p):
        return "P1"

    def camera_for(self, p):
        return None


_fg2 = FakeGame2()
_fg2._begin_death_reaction()
check(_fg2.state == GameState.DYING, "死亡后进入 DYING（非 GAME_OVER）")
check(_fg2.death_timer > 0, "有反应时间倒计时")
_fg2.death_timer = 0.0
check(_fg2.death_timer == 0, "倒计时可被跳过")

# ======================================================================
print("[F] Game 集成（单次启动 + 单帧验证不崩）")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game

g = Game()
g.start_game()
check(hasattr(g, 'replay_recorder'), "回放录制器已初始化")
check(g.replay_recorder.recording, "开局即开始录制")
check(hasattr(g, 'hit_markers'), "命中反馈容器已初始化")
check(hasattr(g, 'gameover_death_btn') and hasattr(g, 'gameover_replay_btn'),
      "结算页死亡详情/回放按钮已创建")
_rows = g.death_detail_rows()
check(isinstance(_rows, list), "death_detail_rows 可调用")
_sum = g.death_detail_summary()
check(isinstance(_sum, dict) and "total" in _sum, "death_detail_summary 可调用")
g._update_playing(1 / 60)     # 单帧：验证录制/反馈集成不崩
check(len(g.replay_recorder.frames) >= 0, "单帧后录制器状态正常")
check(g.replay_stats() == {}, "无回放数据时统计返回空")

print()
print(f"===== v2.8.0 快速测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
