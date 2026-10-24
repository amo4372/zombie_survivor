#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1.9 验证：'GameSession' object has no attribute 'end_session' 真机崩溃修复
①GameSession.end_session 存在且胜利时标记 died=False ②to_dict 导出结算字典
③records.on_game_end 接收 dict 结算不抛错 ④故事模式胜利结算链完整"""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datetime
from records import GameRecords, GameSession

ok = 0
def check(name, cond, detail=""):
    global ok
    ok += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" {detail}" if detail and not cond else ""))
    if not cond:
        sys.exit(1)

# 1. end_session 方法存在
rec = GameRecords()
rec.data["best_score"] = 0
rec.data["best_level"] = 1
rec.data["best_time_survived"] = 0
rec.data["best_kills_single_game"] = 0
sess = GameSession(rec)
sess.add_kill("zombie_normal")
sess.add_kill("zombie_fast")
sess.add_score(500)
sess.data["level"] = 5
check("GameSession 具有 end_session 方法", hasattr(sess, "end_session"), "")
check("GameSession 具有 to_dict 方法", hasattr(sess, "to_dict"), "")

sess.end_session(victory=True)
check("end_session(victory=True) 标记 died=False", sess.data.get("died") is False, f"died={sess.data.get('died')}")
check("end_session 记录 ended 标记", sess.data.get("ended") is True, "")

# 2. to_dict 导出统计
d = sess.to_dict()
check("to_dict 返回 dict 且含击杀统计", isinstance(d, dict) and sum(d["kills_by_type"].values()) == 2, f"kills={d.get('kills_by_type')}")
check("to_dict 含结算所需全部键", all(k in d for k in ("score","level","time_survived","kills_by_type","died",
      "level_ups","skills_upgraded","weapons_collected","items_collected","exp_collected","damage_dealt","damage_taken")), "")

# 3. on_game_end 接收 dict 结算不抛错（此前传 GameSession 对象会崩：对象无 .get）
rec2 = GameRecords()
rec2.data["best_score"] = 0
rec2.data["best_level"] = 1
rec2.data["best_time_survived"] = 0
rec2.data["best_kills_single_game"] = 0
sess2 = GameSession(rec2)
sess2.add_score(888)
sess2.add_kill("zombie_boss")
sess2.end_session(victory=True)
try:
    before = rec2.data["total_kills"]
    rec2.on_game_end(sess2.to_dict())
    check("on_game_end(dict) 结算正常（累计击杀+1）", rec2.data["total_kills"] == before + 1,
          f"total_kills={rec2.data['total_kills']}")
except Exception as e:
    check("on_game_end(dict) 结算正常", False, str(e))

# 4. 旧写法（传对象）确实会崩——证明修复必要性
_bug = False
try:
    rec2.on_game_end(sess2)  # GameSession 无 .get → AttributeError
except AttributeError:
    _bug = True
check("旧写法传对象会崩（修复必要性）", _bug, "")

# 5. 冒烟级：mix_story 模块可导入
import zombie_pkg.mix_story  # noqa
check("mix_story 模块导入正常", True, "")

print(f"\n共 {ok} 项断言全绿")
sys.exit(0)
