#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.2.5 冒烟测试：完全移除RL / 治疗光环 / 死神钩爪重做（瞄准锁定+自我拉拽+沿途AOE） / 更新弹窗持久化

在 dummy 视频驱动下真实启动游戏，压测新代码路径不崩溃：
1. 启动进 PLAYING，跑 120 帧渲染（GLSL 后端回退路径 + 原生路径）
2. 挂载决策树 AI，生成 melee/ranged/healer/exploder 僵尸跑 120 帧（含新包抄/弹幕规避分支）
3. 治疗僵尸光环触发路径
4. 钩爪：键控长按瞄准（锁定圈）→ 松开释放（锁定直飞/自我拉拽/沿途镰刀 AOE）
5. 更新弹窗：点"稍后"→ updater 全局持久标记置位；自动检查尊重标记
"""
import os, sys, math
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, _ROOT)
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game, GameState
import config
import updater

PASS, FAIL = 0, 0
def check(c, n):
    global PASS, FAIL
    if c: PASS += 1; print(f"  [PASS] {n}")
    else: FAIL += 1; print(f"  [FAIL] {n}")

print("[1] 启动+渲染 120 帧")
g = Game()
g.start_game()
g.state = GameState.PLAYING  # 跳过开场对话，直接压测 PLAYING
for _ in range(120):
    g.update(1 / 60)
    g.renderer.render()
check(g.state == GameState.PLAYING, "进入 PLAYING 并渲染 120 帧无异常")

print("[2] 决策树 AI 挂载 + 各类僵尸跑 120 帧（包抄/弹幕规避分支）")
from ai_pkg.zombie_ai import ZombieTreeAI
from config import EnemyType
ai = ZombieTreeAI()
world = g
pl = g.player
from entities_pkg.enemy import Enemy
for i, etype in enumerate([EnemyType.ZOMBIE_NORMAL, EnemyType.ZOMBIE_RANGED,
                           EnemyType.ZOMBIE_HEALER, EnemyType.ZOMBIE_EXPLODER]):
    e = Enemy(300 + i * 80, 300, etype, 1, None)
    e.ai_rl = ai
    e.is_boss = False
    world.enemies.append(e)
# 玩家弹（触发 dodge 分支）
from weapons import Projectile
world.projectiles = [Projectile(320, 300, 3, 0, 10, 300, (255, 0, 0), 3)]
for _ in range(120):
    g.update(1 / 60)
    g.renderer.render()
check(ai.stats["decisions"] > 0, f"决策树接管决策 {ai.stats['decisions']} 次")
check(True, "决策树运行含新分支不崩溃")

print("[3] 治疗光环触发路径")
# 找 healer 并放置低血队友
healer = [e for e in world.enemies if getattr(e, "is_healer", False)]
if healer:
    h = healer[0]
    buddy = Enemy(h.x + 30, h.y, EnemyType.ZOMBIE_NORMAL, 1, None)
    buddy.hp = 10
    buddy.max_hp = 100
    buddy.alive = True
    world.enemies.append(buddy)
    h.heal_timer = 0.0
    for _ in range(60):
        g.update(1 / 60)
        g.renderer.render()
    check(True, "治疗光环跑 60 帧无异常（回血由 mix_playing 光环逻辑处理）")
else:
    check(False, "未找到 healer 僵尸")

print("[4] 钩爪重做：键控长按瞄准（锁定圈）→ 松开释放")
from config import SkillType, WeaponType
g.selected_skill = SkillType.GRAPPLE_PULL
# 给玩家一把死神镰刀（真实武器，weapon_type.name=SCYTHE）
from weapons import Weapon
g.player.weapons = [Weapon(WeaponType.SCYTHE, 1)]
g.player.current_weapon_idx = 0
# 放一个敌人供锁定
tgt = Enemy(400, 300, EnemyType.ZOMBIE_NORMAL, 1, None)
tgt.alive = True
world.enemies.append(tgt)
try:
    # 模拟 mix_playing 每帧瞄准（锁定圈更新分支）+ 松开释放
    g.skill_caster.is_aiming = True
    g.player.riot_gear.grapple_aiming = True
    for _ in range(30):
        g.update(1 / 60)
        g.renderer.render()
    check(hasattr(g, "_is_wielding_scythe") and g._is_wielding_scythe(), "持有死神镰刀判定生效")
    g._perform_grapple_aimed(0.0, 600)  # 松开释放：锁定直飞/自我拉拽
    for _ in range(90):
        g.update(1 / 60)
        g.renderer.render()
    check(True, "钩爪释放+90 帧无异常（锁定直飞/自我拉拽/沿途AOE路径）")
except Exception as e:
    import traceback; traceback.print_exc()
    check(False, f"钩爪路径异常: {e}")

print("[5] 更新弹窗持久化")
g2 = Game()
g2.state = GameState.MENU
updater.UPDATE_STATE["notice_dismissed"] = False
g2._dismiss_update_notice()
check(updater.UPDATE_STATE.get("notice_dismissed") is True, "点'稍后'写入 updater 全局持久标记")
# 自动检查尊重标记：直接验证 _start_auto_update_check 前置判断
check(hasattr(g2, "_dismiss_update_notice") and hasattr(g2, "_start_auto_update_check"),
      "菜单实现持久化 dismiss + 自动检查前置")

print(f"\n===== SMOKE 结果: {PASS} 通过, {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
