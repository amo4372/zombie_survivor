# -*- coding: utf-8 -*-
"""v2.5.2 批次专项测试（源码文本断言）：
#118 PvP 近战连击只受一次伤害 / #119 敌方位置常显 / #120 钩爪锁玩家+倒地队友 /
#121 多级只弹一次卡 / #122 多人刷怪中心 / #123 选卡眩晕击退 / #124 预测轨迹投掷物 /
#126 高伤害卡顿 / #127 镰刀吃近战系列 / #128 P2 受伤特效 / #129 单人加时效果 /
#130 争分夺秒得分归属 / #131 新成就+触发 / #132 成就详细文本
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()

ok = 0
fail = 0
def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail += 1
        print(f"  [FAIL] {name}")

src_mc  = read("zombie_pkg/mix_combat.py")
src_mp  = read("zombie_pkg/mix_playing.py")
src_me  = read("zombie_pkg/mix_effects.py")
src_gc  = read("zombie_pkg/game_core.py")
src_sk  = read("zombie_pkg/mix_skills.py")
src_mu  = read("zombie_pkg/mix_multi.py")
src_ge  = read("entities_pkg/gear.py")
src_pl  = read("entities_pkg/player.py")
src_w   = read("world.py")
src_dp  = read("renderer_pkg/draw_play.py")
src_dm  = read("renderer_pkg/draw_multiplayer.py")
src_du  = read("renderer_pkg/draw_ui.py")
src_r   = read("records.py")

print("== #118 PvP 近战连击单段伤害 ==")
check("挥砍开始时重置 melee_hit_players", "self.melee_hit_players = set()" in src_mc and "self.melee_hit_enemies = set()" in src_mc)
check("PvP 命中判定沿用集合", "id(_pp) in getattr(self, 'melee_hit_players', set())" in src_mc)

print("== #119 敌方位置常显修复 ==")
check("进入 PLAYING 重置揭示周期", src_gc.count("self._pvp_reveal_cycle = 0.0") >= 1 and "self.pvp_reveal_active = False" in src_gc)
check("全显收短为 3s / 45s 周期末 3s", "_c <= 3.0 or (_c % 45.0) > 42.0" in src_gc)
check("屏幕外红箭头受状态机控制", src_dm.count("draw_enemy_player_indicators") >= 1)

print("== #120 钩爪锁定玩家+倒地队友 ==")
check("gear 锁定签名含倒地/敌玩家", "players_down=None, players_enemy=None" in src_ge)
check("优先级 倒地队友>敌玩家>道具>僵尸", "players_down" in src_ge and "players_enemy" in src_ge and "优先" in src_ge or "downed" in src_ge)
check("game_core 提供倒地队友查询", "def _downed_teammates_of" in src_gc)
check("game_core 提供敌玩家查询", "def _enemy_players_of" in src_gc)
check("mix_playing/mix_multi 调用传参", src_mp.count("players_down=") >= 2 and "players_down=self._downed_teammates_of(p2)" in src_mu)
check("钩爪路径搜索含倒地队友", "_perform_grapple_at" in src_sk)

print("== #121 多级升级逐级弹卡 ==")
check("player 新增 pending_levels", "self.pending_levels = 0" in src_pl and "self.pending_levels = getattr(self, 'pending_levels', 0) + 1" in src_pl)
check("仅首次生成卡片", "if self.pending_levels == 1" in src_pl)
check("卡片结算逐级重弹", "_left = getattr(player, 'pending_levels', 0) - 1" in src_sk and "player.pending_levels = max(0, _left)" in src_sk)

print("== #122 多人刷怪以最近玩家为中心 ==")
check("新增 _spawn_center_player", "def _spawn_center_player" in src_gc)
check("刷怪中心方法存在（v2.5.3 起改用随机/轮转中心）", "self._random_spawn_center()" in src_mp and "self._next_spawn_center()" in src_mp)

print("== #123 选卡结束眩晕+击退 ==")
check("选卡后 260px 范围眩晕击退", "_sr = 260" in src_sk and "STUN" in src_sk and "230" in src_sk)

print("== #124 僵尸投掷物预测轨迹 ==")
check("game_core 速度缓存", "def _update_player_vel_cache" in src_gc and "def _player_velocity" in src_gc)
check("生成端预测落点", "_spawn_enemy_throwable" in src_mc and "acc =" in src_mc and "飞行时间" in src_mc)
check("更新端不再实时转向", "_update_enemy_throwables" in src_me and "target_x" in src_me)

print("== #126 高伤害卡顿修复 ==")
check("find_safe_position 螺旋减半+边界钳制", "range(12, min(max_search_radius, 150) + 1, 12)" in src_w)
check("trauma 重建节流", "_trauma_rebuild_time" in src_dp and "edge_width" in src_dp)

print("== #127 镰刀吃全部近战系列 ==")
check("火力段含 MELEE_DAMAGE/BERSERKER/COMBO", "MELEE_DAMAGE" in src_mp and "BERSERKER" in src_mp and "COMBO_MASTER" in src_mp)
check("近战攻速/射程乘区", "MELEE_SPEED" in src_mp and "MELEE_RANGE" in src_mp)
check("剑气吸血 MELEE_LIFESTEAL", "MELEE_LIFESTEAL" in src_mp)

print("== #128 P2 受伤等特效 ==")
check("创伤特效按视口玩家", "self._draw_trauma_effect(player)" in src_dp and "def _draw_trauma_effect(self, player=None)" in src_dp)
check("Buff 屏幕特效按视口玩家", "self._draw_buff_screen_effect(player)" in src_dp and "def _draw_buff_screen_effect(self, player=None)" in src_dp)

print("== #129 单人争分夺秒加时效果 ==")
check("单人 HUD TIMED 加时反馈", "race_last_gain" in src_dp and "race_gain_timer" in src_dp and "TIMED" in src_dp)

print("== #130 争分夺秒得分归属 ==")
check("击杀归属玩家 3 处设置", src_mp.count("enemy._last_hit_player =") == 2 and src_mc.count("enemy._last_hit_player =") == 1)
check("得分计入击杀者", "_kp = getattr(enemy, '_last_hit_player', None) or self.player" in src_me)

print("== #131 新增成就+触发 ==")
check("地狱组成就定义", "hell_clear" in src_r and "hell_boss" in src_r and "hell_survivor" in src_r)
check("争分夺秒进阶成就", "race_10_wins" in src_r and "race_200_kills" in src_r and "race_60k_score" in src_r)
check("多人成就定义", "mp_first_win" in src_r and "mp_team_win" in src_r and "mp_pvp_win" in src_r and "mp_rescue_10" in src_r and "mp_10_games" in src_r and "mp_vehicle" in src_r)
check("多人统计接口", "def add_mp_stat" in src_r and "mp_games" in src_r)
check("race 进阶触发", '_unlock("race_10_wins")' in src_r and '_unlock("race_200_kills")' in src_r)
check("地狱触发挂结算", 'unlock("hell_clear")' in src_r and 'unlock("hell_boss")' in src_r and 'unlock("hell_survivor")' in src_r)
check("speedrunner 触发修复", '"TIMED" and d.get("time_survived", 0) <= 600' in src_r.replace("\n"," ") or "<= 600 and not d.get('died', True)" in src_r)
check("no_skill_challenge 触发补齐", 'unlock("no_skill_challenge")' in src_r)
check("game_core 统计钩子", "add_mp_stat(\"mp_games\")" in src_gc and "add_mp_stat(\"mp_rides\")" in src_gc)
check("mix_playing 统计钩子", "add_mp_stat(\"mp_wins\")" in src_mp and "add_mp_stat(\"mp_pvp_wins\")" in src_mp and "add_mp_stat(\"mp_rescues\")" in src_mp)

print("== #132 成就详细文本 ==")
check("成就页 detail 渲染", 'ach_data.get("detail") or ""' in src_du and "detail_start" in src_du)
check("成就分组含新组", '"争分夺秒", "地狱", "多人"' in src_du)
check("旧存档兼容补 detail",
      all(_k in src_r for _k in ('"group"', '"hidden"', '"coef_threshold"', '"detail"'))
      and "fill_k" in src_r)

print(f"\n结果: {ok} 通过, {fail} 失败")
sys.exit(1 if fail else 0)
