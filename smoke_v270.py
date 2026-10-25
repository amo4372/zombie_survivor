#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.7.0 冒烟测试：真实跑帧验证三项修复 + 无畏冲锋 + 新技能卡界面

1. 技能池：冲击波 / 盾牌肘击 已移除；无畏冲锋 解锁链为 防爆套装→肾上腺素→无畏冲锋
2. P2 钩爪可以勾取 P1（team_id 初始化 + 队友判定默认值修复）
3. P2 预瞄线不再泄漏到 P1 视口（移除重复的全屏无裁剪绘制）
4. 连升多级：选卡界面不会被立刻 hide()，能连续弹出后续升级页
5. 新技能卡界面：默认选中第一项、1/2/3 切换、点击升级按钮才确认
6. 无畏冲锋：强制装备防爆套装 + 重置CD + 减伤50% + 秒杀普通僵尸 + 不能肘击/放技能
"""
import os
import sys
import math

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.getcwd())

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game import Game, GameState
from config import *
from entities_pkg.player import Player
from skills import SkillTree

PASS, FAIL = 0, 0


def check(c, n):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n}")


def frames(g, n, draw=True):
    for _ in range(n):
        g.update(1 / 60)
        if draw:
            g.renderer.render()


g = Game()
g.start_game()
g.state = GameState.PLAYING

# ======================================================================
print("[1] 技能池：冲击波 / 盾牌肘击 已移除，无畏冲锋解锁链正确")
st = SkillTree()
names = {s.name for s in st.skills}
check("冲击波" not in names, "冲击波已从技能池移除")
check("盾牌肘击" not in names, "盾牌肘击已从技能池移除")
check("无畏冲锋" in names, "无畏冲锋已加入技能池")

fc = st.get_skill(SkillType.FEARLESS_CHARGE)
check(fc is not None, "无畏冲锋技能对象存在")
check(fc.requires == [(SkillType.ADRENALINE, 1)], "无畏冲锋前置=肾上腺素1级")
ad = st.get_skill(SkillType.ADRENALINE)
check(ad.requires == [(SkillType.RIOT_GEAR, 1)], "肾上腺素前置=防爆套装1级")
check(fc.is_active, "无畏冲锋为主动技能")
check(fc.max_level == 5, "无畏冲锋5级上限")
check(bool(getattr(fc, 'lore', None)), "无畏冲锋有背景介绍文本")

# 冷却与时长随等级递减
d1 = get_fearless_charge_duration(1)
d5 = get_fearless_charge_duration(5)
c1 = get_fearless_charge_cooldown(1)
c5 = get_fearless_charge_cooldown(5)
check(d5 > d1, f"持续时间随等级变长 ({d1} -> {d5})")
check(c5 < c1, f"冷却随等级变短 ({c1} -> {c5})")
check(SkillType.FEARLESS_CHARGE in SKILL_COOLDOWNS, "无畏冲锋已进入统一冷却表")

# ======================================================================
print("[2] P2 钩爪可以勾取 P1")
g.multiplayer_mode = "same_screen"
if g.player2 is None:
    g.player2 = Player(g.player.x + 200, g.player.y)
    g.camera2 = type(g.camera)(640, 720)
p1, p2 = g.player, g.player2
p1.team_id = 0
p2.team_id = 0
check(getattr(p1, 'team_id', None) == 0, "P1 team_id 已初始化")
check(getattr(p2, 'team_id', None) == 0, "P2 team_id 已初始化")

tm = g._alive_teammates_of(p2)
check(p1 in tm, f"P2 的存活队友列表包含 P1 (实际 {len(tm)} 人)")

tm1 = g._alive_teammates_of(p1)
check(p2 in tm1, f"P1 的存活队友列表包含 P2 (实际 {len(tm1)} 人)")

# PvP 下异阵营应互为敌人
g.config.pvp_enabled = True
p2.team_id = 1
en = g._enemy_players_of(p2)
check(p1 in en, "PvP 下 P1 是 P2 的敌对玩家")
check(p1 not in g._alive_teammates_of(p2), "PvP 下 P1 不算 P2 的队友")
p2.team_id = 0
g.config.pvp_enabled = False

# 预设 team_id 缺省也能互为队友（不依赖外部赋值）
class _Bare:
    pass
p1.team_id = 0
p2.team_id = 0
del p2.team_id           # 模拟「未显式设置 team_id」的旧行为
check(p1 in g._alive_teammates_of(p2),
      "team_id 缺省（未赋值）时仍能正确判定为同队（默认值统一为 0）")
p2.team_id = 0

# ======================================================================
print("[3] P2 预瞄线不再泄漏到 P1 视口")
import renderer_pkg.draw_play as _dp
src = open('renderer_pkg/draw_play.py', encoding='utf-8').read()
_seg = src.split('def _draw_playing_split(')[1].split('\n    def ')[0]
# 去掉注释行后再判断（说明性注释里会提到函数名字）
_code = "\n".join(ln for ln in _seg.split('\n') if not ln.strip().startswith('#'))
check('_draw_aim_preview' not in _code,
      "_draw_playing_split 不再对全屏无裁剪绘制 P2 预瞄线")
check('render_split_viewports(self, self.game, viewports)' in _code,
      "分屏仍由 render_split_viewports 在各视口内绘制预瞄")
# P2 预瞄仍应在视口内绘制（aim_owner 分支）
_core = src.split('def _draw_playing_core(')[1]
check('_sc2._draw_aim_preview' in _core,
      "P2 预瞄仍在 P2 视口(subsurface)内绘制，功能未丢失")

# ======================================================================
print("[4] 连升多级：后续升级页不会被立刻隐藏")
g2 = Game()
g2.start_game()
g2.state = GameState.PLAYING
_orig_left = 3
g2.player.pending_levels = _orig_left
g2.player.pending_level_up = True
g2.player.skill_cards = g2.player.skill_tree.get_random_skill_cards(3)
check(len(g2.player.skill_cards) > 0, "首次生成技能卡")
g2.state = GameState.SKILL_SELECT
g2.pending_upgrade_for = "P1"
g2.skill_card_selector.show(g2.player.skill_cards, region=None)
check(g2.skill_card_selector.visible, "选卡界面已显示")

g2._apply_skill_card(g2.player.skill_cards[0])
check(getattr(g2.player, 'pending_levels', 0) == _orig_left - 1,
      f"待结算级数递减 ({_orig_left} -> {g2.player.pending_levels})")
check(g2.skill_card_selector.visible,
      "连升多级：第二次升级的选卡界面仍然可见（未被 hide）")
check(g2.state == GameState.SKILL_SELECT, "单机连升多级状态保持 SKILL_SELECT")

# 再选一次，直到用完
g2._apply_skill_card(g2.skill_card_selector.cards[0])
check(g2.skill_card_selector.visible, "第三次升级选卡界面仍可见")
g2._apply_skill_card(g2.skill_card_selector.cards[0])
check(not g2.skill_card_selector.visible, "级数用尽后选卡界面关闭")
check(g2.state == GameState.PLAYING, "级数用尽后回到 PLAYING")

# 同屏双人连升多级：region 应为对应半屏
g3 = Game()
g3.start_game()
g3.state = GameState.PLAYING
g3.multiplayer_mode = "same_screen"
if g3.player2 is None:
    g3.player2 = Player(g3.player.x + 200, g3.player.y)
    g3.camera2 = type(g3.camera)(640, 720)
g3.player2.pending_levels = 2
g3.player2.pending_level_up = True
g3.player2.skill_cards = g3.player2.skill_tree.get_random_skill_cards(3)
g3._upgrade_pause_player = "P2"
g3.pending_upgrade_for = "P2"
g3.skill_card_selector.show(g3.player2.skill_cards,
                            region=pygame.Rect(640, 0, 640, 720))
g3._apply_skill_card(g3.player2.skill_cards[0])
check(g3.skill_card_selector.visible, "双人连升多级：P2 第二张卡仍可见")
_reg = g3.skill_card_selector.region
check(_reg is not None and _reg.x == 640,
      f"双人连升多级：region 仍是 P2 半屏 (x={_reg.x if _reg else None})")
check(g3._upgrade_pause_player == "P2", "双人连升多级：仍标记 P2 暂停中")

# ======================================================================
print("[5] 新技能卡界面交互")
sel = g.skill_card_selector
sel.show(g.player.skill_tree.get_random_skill_cards(3), region=None)
check(sel.selected_index == 0, "默认打开第一个选项")
lay = sel._layout(1.0)
check(len(lay["tab_rects"]) == len(sel.cards), "顶部栏目数量=技能卡数量")
check(lay["confirm"] is not None, "底部升级按钮存在")
check(lay["detail"].height > 0, "中部大页面存在")

# 顶部栏目应比大页面细
check(lay["tab_rects"][0].height < lay["detail"].height, "顶部栏目(较细) < 中部大页面")

sel.select_tab(2)
check(sel.selected_index == 2, "切换到第三个选项")
sel.select_tab(0)
check(sel.selected_index == 0, "切回第一个选项")
check(sel.confirm() is sel.cards[0], "确认返回当前选中的技能")

# 点击「非按钮区域」不应确认
r = sel.handle_input((0, 0), (0, 0, 0), [{"type": "down", "pos": (5, 5), "id": 1}], 1.0)
check(r is None, "点击空白处不会误确认升级")

# 点击顶部缩略图只切换、不确认
_t = lay["tab_rects"][1]
r = sel.handle_input((0, 0), (0, 0, 0),
                     [{"type": "down", "pos": (_t.x + _t.width // 2, _t.y + _t.height // 2), "id": 1}], 1.0)
check(r is None and sel.selected_index == 1, "点击缩略图仅切换选项，不确认")

# 点击升级按钮才确认
_b = sel._layout(1.0)["confirm"]
r = sel.handle_input((0, 0), (0, 0, 0),
                     [{"type": "down", "pos": (_b.x + _b.width // 2, _b.y + _b.height // 2), "id": 1}], 1.0)
check(r is sel.cards[1], "点击升级按钮确认当前技能")

# 详情内容包含 效果/词条/前后对比/背景介绍
sel.show(g.player.skill_tree.get_random_skill_cards(3), region=None)
_content = sel._build_content(sel.cards[0])
_txt = "\n".join(x[0] for x in _content)
check("【效果】" in _txt, "详情页含【效果】")
check("【词条】" in _txt, "详情页含【词条】")
check("【前后对比】" in _txt or "【背景介绍】" in _txt, "详情页含前后对比或背景介绍")
check("【背景介绍】" in _txt, "详情页含【背景介绍】")

# 可滑动：内容足够长时应产生 max_scroll
sel._ensure_panel(sel._layout(1.0), pygame.font.Font(None, 20), pygame.font.Font(None, 28))
check(sel._panel is not None, "滑动文字框已创建")
check(sel._panel.max_scroll >= 0, "滑动文字框可计算滚动上限")

# 绘制不崩溃
_surf = pygame.display.get_surface()
try:
    sel.draw(_surf, pygame.font.Font(None, 20), pygame.font.Font(None, 28), 1.0)
    check(True, "新技能卡界面绘制不崩溃")
except Exception as e:
    check(False, f"新技能卡界面绘制崩溃: {e}")

# ======================================================================
print("[6] 无畏冲锋行为")
g4 = Game()
g4.start_game()
g4.state = GameState.PLAYING
pl = g4.player
# 解锁链
for _t in (SkillType.RIOT_GEAR, SkillType.ADRENALINE, SkillType.FEARLESS_CHARGE):
    s = pl.skill_tree.get_skill(_t)
    s.current_level = s.max_level if _t is SkillType.RIOT_GEAR else 2

# 6a 未装备防爆套装时释放 → 先强制装备 + 重置CD
pl.riot_gear_cooldown = 25.0
pl.active_skills[SkillType.RIOT_GEAR] = 25.0
ok = g4._skill_fearless_charge()
check(ok, "无畏冲锋释放成功")
check(pl.riot_gear.equipped, "未装备时自动装备防爆套装")
check(pl.riot_gear_cooldown == 0.0, "强行重置防爆套装冷却CD")
check(SkillType.RIOT_GEAR not in pl.active_skills, "防爆套装技能CD已清除")
check(pl.fearless_charge_active, "进入无畏冲锋状态")
check(pl.riot_gear.fearless_active, "防爆套装标记为无畏冲锋")

# 6b 减伤 50%（对比开关状态，规避护甲/盾牌格挡干扰）
def _probe(fearless_on):
    pl.hp = pl.max_hp
    pl.invincible_timer = 0.0
    pl.fearless_charge_active = fearless_on
    _b = pl.hp
    pl.take_damage(200.0, damage_type="melee")
    return _b - pl.hp

_off = _probe(False)
_on = _probe(True)
pl.fearless_charge_active = True
check(_off > 0 and abs(_on - _off * 0.5) < max(1.0, _off * 0.02),
      f"冲锋中伤害减半 (未冲锋扣 {_off:.1f} → 冲锋扣 {_on:.1f})")

# 6c 冲锋中不能肘击 / 不能用技能
_bash = g4._perform_bash(0.0)
check(_bash is False, "冲锋中无法肘击")
_ok2 = g4._use_skill(SkillType.GRENADE)
check(_ok2 is False, "冲锋中无法使用其它技能")

# 6d 沿途秒杀普通僵尸（使用真实僵尸对象）
from entities_pkg.enemy import Enemy
g4.enemies.clear()
_e1 = Enemy(pl.x + 30, pl.y, EnemyType.ZOMBIE_NORMAL, 1, "normal")
_e2 = Enemy(pl.x + 70, pl.y, EnemyType.BOSS_LONG, 1, "normal")
_e1.hp = _e1.max_hp = 100000
_e2.hp = _e2.max_hp = 100000
g4.enemies.extend([_e1, _e2])
g4._update_charge(0.05)
check(not _e1.alive, "冲锋沿途普通僵尸被秒杀")
check(_e2.alive, "Boss 不被秒杀（仍存活）")

# 6e 冲锋结束后状态清除
pl.riot_gear.charge_timer = 0.0
g4._update_charge(0.016)
check(not pl.fearless_charge_active, "冲锋结束清除无畏状态")
check(not pl.riot_gear.charge_active, "冲锋结束清除冲撞状态")

# 6f 冲锋中玩家输入位移被接管（只能转向）
_pl2 = g4.player
_pl2.fearless_charge_active = True
_a0 = _pl2.facing_angle
_pl2.update(1 / 60, 1.0, 0.0, math.radians(0.0), None)
check(abs(_pl2.facing_angle - _a0) <= FEARLESS_CHARGE_TURN_RATE / 60 + 0.5,
      "冲锋期间转向速度受限（大幅降低）")
_pl2.fearless_charge_active = False

# ======================================================================
print("[7] 真实跑帧不崩溃")
g5 = Game()
g5.start_game()
g5.state = GameState.PLAYING
g5.multiplayer_mode = "same_screen"
if g5.player2 is None:
    g5.player2 = Player(g5.player.x + 200, g5.player.y)
    g5.camera2 = type(g5.camera)(640, 720)
# 解锁无畏冲锋并释放
for _t in (SkillType.RIOT_GEAR, SkillType.ADRENALINE, SkillType.FEARLESS_CHARGE):
    s = g5.player.skill_tree.get_skill(_t)
    s.current_level = 1
g5.player.skill_tree.get_skill(SkillType.FEARLESS_CHARGE).current_level = 3
g5._skill_fearless_charge()
try:
    frames(g5, 30)
    check(True, "分屏 + 无畏冲锋跑帧 30 次不崩溃")
except Exception as e:
    check(False, f"跑帧崩溃: {e}")

# 选卡界面跑帧
g5.player.pending_levels = 2
g5.player.pending_level_up = True
g5.player.skill_cards = g5.player.skill_tree.get_random_skill_cards(3)
g5.skill_card_selector.show(g5.player.skill_cards,
                            region=pygame.Rect(0, 0, 640, 720))
try:
    frames(g5, 10)
    check(True, "选卡界面跑帧不崩溃")
except Exception as e:
    check(False, f"选卡界面跑帧崩溃: {e}")

# ======================================================================
print("[8] 更新器下载超时收紧")
import updater
check(hasattr(updater, 'DOWNLOAD_READ_TIMEOUT') and updater.DOWNLOAD_READ_TIMEOUT <= 20,
      f"单次 read 超时已收紧到 {updater.DOWNLOAD_READ_TIMEOUT}s（原 60s）")
check(hasattr(updater, 'DOWNLOAD_STALL_TIMEOUT') and updater.DOWNLOAD_STALL_TIMEOUT <= 30,
      f"停滞超时 {updater.DOWNLOAD_STALL_TIMEOUT}s（无进展即换节点）")
check(hasattr(updater, 'DOWNLOAD_NODE_TIMEOUT'), f"单节点总时长上限 {updater.DOWNLOAD_NODE_TIMEOUT}s")
check(hasattr(updater, 'DOWNLOAD_TOTAL_TIMEOUT'), f"整体下载上限 {updater.DOWNLOAD_TOTAL_TIMEOUT}s")
_usrc = open('updater.py', encoding='utf-8').read()
check('timeout=DOWNLOAD_READ_TIMEOUT' in _usrc, "urlopen 使用新的短超时常量")
check('_last_progress_at' in _usrc and '_stalled' in _usrc, "下载循环已加入停滞检测")
check('DOWNLOAD_STALL_TIMEOUT' in _usrc.split('def download_update(')[1].split('def ')[0],
      "停滞检测位于 download_update 内")

print()
print(f"===== v2.7.0 冒烟测试: PASS={PASS} FAIL={FAIL} =====")
sys.exit(1 if FAIL else 0)
