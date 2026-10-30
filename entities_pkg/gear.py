#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏实体模块 - 玩家、敌人(含新机制僵尸)、经验球、防爆套装等"""

import pygame
import math
import random
from config import *
from weapons import Weapon, Projectile
from skills import SkillTree
from buff import BuffManager, BuffType


class RiotGear:
    def __init__(self):
        self.equipped = False
        self.shield_hp = 500
        self.max_shield_hp = 500
        self.shield_broken = False
        self.viewing_window_hp = 400
        self.max_viewing_window_hp = 400
        self.facing_angle = 0
        self.stamina = 100
        self.max_stamina = 100
        self.base_max_stamina = 100
        self.stamina_regen = 8
        self.base_stamina_regen = 8
        self.adrenaline_level = 0  # 肾上腺素技能等级，装备时提升体力
        self.bash_cooldown = 0
        self.bash_max_cooldown = 0.5
        self.grapple_cooldown = 0
        self.grapple_max_cooldown = 8.0  # v2.6.4: 全模式统一8秒CD
        self.melee_reduction = 0.5
        self.ranged_reduction = 0.7
        self.magic_immunity = True
        self.shield_width = 60
        self.shield_height = 80
        self.shield_offset = 25
        self.grapple_active = False
        self.grapple_target = None
        self.grapple_target_pos = None
        self.grapple_head_pos = None
        self.grapple_state = "idle"
        # v2.7.2 数据层完整：这两个字段此前只在 _reset_grapple 里创建，
        # 新建实例拿不到（各处只能靠 getattr 兜底）。构造时即初始化，
        # 保证每位玩家的钩爪状态机字段一致。
        self.grapple_direct_pull = False
        self._collision_prev_head = None
        self.grapple_speed = 150
        self.grapple_pull_speed = 55
        self.grapple_hit_stun_timer = 0
        self.grapple_hit_stun_duration = 0.6
        self.grapple_max_range = 800
        self.grapple_stamina_cost = 0
        # ===== v2.2.5 钩爪重做（死神钩爪 / 自我拉拽 / 锁定圈） =====
        self.grapple_is_scythe = False        # 本次发射是否为死神钩爪（持死神镰刀时）
        self.grapple_scythe_max_cooldown = 3.0  # 死神钩爪 CD（普通 0.8）
        self.grapple_aiming = False           # 长按瞄准中（显示预瞄线+锁定圈）
        self.grapple_locked_target = None     # 瞄准圈锁定的僵尸（松开后直飞目标）
        self.grapple_lock_radius = 200        # 锁定圈半径（世界单位，v2.2.6 拉远便于锁定远处目标）
        self.self_pull_active = False         # 自我拉拽中（未命中目标 → 把自己拉向目标点）
        self.self_pull_speed = 560            # v2.2.7 自我拉拽速度（提速；期间禁用玩家额外位移）
        self.self_pull_immune = False         # 自我拉拽期间免伤标记
        self.self_pull_start = (0, 0)         # 自我拉拽起点（世界坐标）
        self.self_pull_end = (0, 0)           # 自我拉拽终点（世界坐标）
        self.grapple_swing_timer = 0.0        # 死神自我拉拽沿途镰刀旋转伤害间隔
        self.grapple_swing_interval = 0.12    # 沿途伤害间隔（秒）
        self.grapple_pull_impact_hit = set()  # 拉敌过程中已撞击过的敌人 id（避免重复伤害）
        self.bash_auto = False
        self.bash_direction = 0
        self.bash_stamina_cost = 14
        self.bash_anim_timer = 0
        self.bash_anim_duration = 0.2
        self.bash_hit_pos = None
        # === 盾牌冲撞系统 ===
        self.charge_active = False
        self.charge_timer = 0
        self.charge_duration = 0.45
        self.charge_speed = 680
        self.charge_direction = 0
        self.charge_hit_ids = set()  # 已命中的敌人id，避免重复伤害
        self.charge_damage = 160
        self.charge_stun_duration = 1.2
        self.charge_knockback = 150
        # === v2.7.0 无畏冲锋（FEARLESS_CHARGE 限时状态） ===
        self.fearless_active = False       # 是否为无畏冲锋（而非普通盾冲）
        self.fearless_level = 0            # 释放时的技能等级（影响时长/撞击特效）
        self.equip_time = 0
        self.debuff_threshold = 60.0
        self.has_debuff = False
        self.debuff_speed_penalty = 0.3
        self.aim_line_active = False
        self.aim_line_angle = 0
        self.aim_line_press_time = 0
        self.aim_threshold = 0.25

        # =========【新增冷却】卸下防爆套装才开始CD =========
        self.riot_gear_cd_timer = 0.0
        self.riot_gear_base_cd = 30.0

    def equip(self):
        """装备防爆套装：不启动冷却，冷却在unequip时触发"""
        if self.riot_gear_cd_timer > 0:
            return False
        self.equipped = True
        self.shield_hp = self.max_shield_hp
        self.shield_broken = False
        self.viewing_window_hp = self.max_viewing_window_hp
        self.equip_time = 0
        self.has_debuff = False
        return True

    def unequip(self, cd_reduction_mult=1.0):
        """卸下防爆套装，立刻启动冷却，受冷却缩减倍率"""
        if not self.equipped:
            return
        self.equipped = False
        self.grapple_active = False
        self.grapple_target = None
        self.grapple_target_pos = None
        self.grapple_head_pos = None
        self.grapple_state = "idle"
        self.bash_auto = False
        self.charge_active = False
        self.charge_hit_ids = set()
        self.fearless_active = False
        self.fearless_level = 0
        self.has_debuff = False
        self.aim_line_active = False
        # 卸下瞬间开启冷却
        self.riot_gear_cd_timer = self.riot_gear_base_cd * cd_reduction_mult

    def update(self, dt, player_x, player_y, facing_angle, move_speed_mult=1.0, cd_reduction_mult=1.0, player=None):
        self.facing_angle = facing_angle
        # 冷却计时
        if self.riot_gear_cd_timer > 0:
            self.riot_gear_cd_timer -= dt

        # 体力由Player统一管理（与玩家疾跑共用同一体力池）
        # self.stamina 和 self.max_stamina 由 Player.update 同步
        if self.bash_cooldown > 0:
            self.bash_cooldown -= dt
        if self.grapple_cooldown > 0:
            self.grapple_cooldown -= dt
        if self.bash_anim_timer > 0:
            self.bash_anim_timer -= dt

        self._update_grapple(dt, player_x, player_y, player)

        if self.equipped:
            self.equip_time += dt
            if self.equip_time > self.debuff_threshold and not self.has_debuff:
                self.has_debuff = True
            # 装备超时自动卸下
            if self.equip_time >= self.debuff_threshold + 10.0:
                self.unequip(cd_reduction_mult)

    def get_debuff_speed_mult(self):
        if self.has_debuff:
            return 1.0 - self.debuff_speed_penalty
        return 1.0

    def _update_grapple(self, dt, player_x, player_y, player=None):
        """更新钩爪状态 - 修复秒断勾：追踪目标、稳定拉回、最小拉回时间
        v2.2.5：新增 self_pull（自我拉拽）状态 + 锁定目标直飞"""
        if not self.grapple_active:
            return

        if self.grapple_state == "shooting":
            # 如果有目标，追踪目标当前位置（而非固定的发射位置）
            if self.grapple_target and hasattr(self.grapple_target, 'alive') and self.grapple_target.alive:
                self.grapple_target_pos = (self.grapple_target.x, self.grapple_target.y)

            # 钩爪头飞向目标
            dx = self.grapple_target_pos[0] - self.grapple_head_pos[0]
            dy = self.grapple_target_pos[1] - self.grapple_head_pos[1]
            dist = math.hypot(dx, dy)

            move_dist = min(dist, self.grapple_speed * dt * 60)
            if dist > 0:
                self.grapple_head_pos[0] += (dx / dist) * move_dist
                self.grapple_head_pos[1] += (dy / dist) * move_dist

            # 检查是否到达目标或超出射程
            new_dist = math.hypot(
                self.grapple_target_pos[0] - self.grapple_head_pos[0],
                self.grapple_target_pos[1] - self.grapple_head_pos[1]
            )
            total_dist = math.hypot(
                self.grapple_head_pos[0] - player_x,
                self.grapple_head_pos[1] - player_y
            )

            if new_dist < 10:  # 到达目标位置（放宽阈值，避免速度快时越过）
                if self.grapple_target:
                    # Boss免控：只能命中产生僵直，不能勾取
                    if getattr(self.grapple_target, 'is_boss', False):
                        self.grapple_hit_stun_timer = self.grapple_hit_stun_duration * 0.5
                        if hasattr(self.grapple_target, 'grappled'):
                            self.grapple_target.grappled = False
                        self.grapple_target = None
                        self.grapple_state = "retracting"
                    else:
                        # 勾中普通目标，立即设置grappled=True防止敌人移动
                        if hasattr(self.grapple_target, 'grappled'):
                            self.grapple_target.grappled = True
                        self.grapple_head_pos = [self.grapple_target.x, self.grapple_target.y]
                        self.grapple_state = "hit"
                        self.grapple_hit_stun_timer = self.grapple_hit_stun_duration
                        self._pulling_timer = 0.0  # 初始化拉回计时器
                else:
                    # v2.2.5：钩爪头到达目标点但未勾中任何物体 →
                    # 自我拉拽（把自己拉向目标点），普通/死神钩爪均适用
                    self._begin_self_pull(player_x, player_y, player)
            elif total_dist >= self.grapple_max_range:
                # v2.2.5：超出射程同样触发自我拉拽（拉向最远点），而非空收回
                self._begin_self_pull(player_x, player_y, player)

        elif self.grapple_state == "hit":
            # 僵直阶段 - 钩爪绷紧
            self.grapple_hit_stun_timer -= dt
            # v2.6.3 修复：QTE 判定从 hit 状态开始（而非 pulling 状态）
            # 被勾玩家应在命中瞬间就能尝试打断，而非等到拉回阶段
            if self.grapple_target and hasattr(self.grapple_target, 'qte_window'):
                try:
                    self.grapple_target.qte_rope_from = (player_x, player_y)
                    self.grapple_target.qte_rope_to = (self.grapple_target.x, self.grapple_target.y)
                    if self.grapple_target.qte_window > 0:
                        self.grapple_target.qte_window -= dt
                        self.grapple_target.qte_break_hint = 1.0
                        _tap = self.grapple_target.qte_break_tap
                        if _tap is not None:
                            self.grapple_target.qte_break_tap = None
                            if self._qte_tap_in_sector(self.grapple_target, _tap):
                                # 打断成功：解除勾取
                                self.grapple_target.grappled = False
                                self.grapple_target.qte_window = 0.0
                                self.grapple_target.qte_break_hint = 0.0
                                self.grapple_target.qte_success_timer = 1.2
                                self.grapple_target.qte_immune_timer = 0.6
                                self.grapple_target.qte_hit_flash = 0.18
                                self._reset_grapple()
                                return
                        if self.grapple_target.qte_window <= 0:
                            # 超时未打断
                            self.grapple_target.qte_break_hint = 0.0
                            self.grapple_target.qte_fail_timer = 1.0
                    else:
                        self.grapple_target.qte_break_tap = None
                except Exception:
                    pass
            if self.grapple_hit_stun_timer <= 0:
                self.grapple_state = "pulling"
                self._pulling_timer = 0.0
            # 同步更新目标位置到钩爪头
            if self.grapple_target and hasattr(self.grapple_target, 'alive') and self.grapple_target.alive:
                self.grapple_head_pos = [self.grapple_target.x, self.grapple_target.y]
                # 确保目标保持被勾状态
                if hasattr(self.grapple_target, 'grappled'):
                    self.grapple_target.grappled = True
            else:
                # 目标死亡，收回钩爪
                self.grapple_state = "retracting"

        elif self.grapple_state == "pulling":
            if not hasattr(self, '_pulling_timer'):
                self._pulling_timer = 0.0
            self._pulling_timer += dt

            if self.grapple_target and hasattr(self.grapple_target, 'alive') and self.grapple_target.alive:
                dx = player_x - self.grapple_target.x
                dy = player_y - self.grapple_target.y
                dist = math.hypot(dx, dy)
                # v2.5.0/v2.5.5 PvP 勾取玩家：打断绳索 QTE（记录绳索几何，0.8s 内单击绳索对称轴扇形即打断）
                if hasattr(self.grapple_target, 'qte_window'):
                    try:
                        self.grapple_target.qte_rope_from = (player_x, player_y)
                        self.grapple_target.qte_rope_to = (self.grapple_target.x, self.grapple_target.y)
                        if self.grapple_target.qte_window > 0:
                            self.grapple_target.qte_window -= dt
                            self.grapple_target.qte_break_hint = 1.0
                            _tap = self.grapple_target.qte_break_tap
                            if _tap is not None:
                                self.grapple_target.qte_break_tap = None
                                if self._qte_tap_in_sector(self.grapple_target, _tap):
                                    # 打断成功：解除勾取，不再拉取 + 成功反馈与短暂免疫
                                    self.grapple_target.grappled = False
                                    self.grapple_target.qte_window = 0.0
                                    self.grapple_target.qte_break_hint = 0.0
                                    self.grapple_target.qte_success_timer = 1.2
                                    self.grapple_target.qte_immune_timer = 0.6
                                    self.grapple_target.qte_hit_flash = 0.18
                                    self._reset_grapple()
                                    return
                            if self.grapple_target.qte_window <= 0:
                                # 超时未打断 → 失败反馈，继续被拉（到达后眩晕）
                                self.grapple_target.qte_break_hint = 0.0
                                self.grapple_target.qte_fail_timer = 1.0
                        else:
                            self.grapple_target.qte_break_tap = None
                    except Exception:
                        pass

                # v2.2.5 词条应用：被拉回的敌人沿途撞击其他敌人（造成撞击伤害）
                # 撞击伤害=钩爪基础伤害量级（由 mix_playing 传入，默认走 buff 判定）
                try:
                    if hasattr(self.grapple_target, 'knockback_x'):
                        _impact_dmg = getattr(self, '_grapple_impact_damage', 25)
                        _impact_r = getattr(self.grapple_target, 'size', 20) + 30
                        _gt_id = id(self.grapple_target)
                        # 在全局敌人列表由 mix_playing 执行（gear 无 enemies 引用），
                        # 这里只记录轨迹：mix_playing 每帧在 pulling 状态做撞击检测
                        self._grapple_impact_damage = _impact_dmg
                        self._grapple_impact_radius = _impact_r
                        self._grapple_pulling_target = self.grapple_target
                except Exception:
                    pass

                # 最小拉回时间0.2秒，确保不会秒断
                min_pull_time = 0.2
                if dist > 90 or self._pulling_timer < min_pull_time:
                    pull_speed = self.grapple_pull_speed * dt * 60
                    # 距离越远拉得越快（倍率1.5而非2.0，更稳定）
                    if dist > 200:
                        pull_speed *= 1.5
                    if dist > 0:
                        self.grapple_target.x += (dx / dist) * pull_speed
                        self.grapple_target.y += (dy / dist) * pull_speed
                    self.grapple_head_pos = [self.grapple_target.x, self.grapple_target.y]
                    # 确保敌人保持被勾状态
                    if hasattr(self.grapple_target, 'grappled'):
                        self.grapple_target.grappled = True
                else:
                    # 到达玩家90像素外且超过最小拉回时间，释放
                    if hasattr(self.grapple_target, 'grappled'):
                        self.grapple_target.grappled = False
                    # 拉回完成：给予长僵直，使目标短时间内无法移动/攻击玩家
                    try:
                        if hasattr(self.grapple_target, 'apply_buff'):
                            self.grapple_target.apply_buff(BuffType.STUN, duration=1.5)
                        elif hasattr(self.grapple_target, 'buff_manager'):
                            # v2.5.0/v2.5.3 玩家目标：强制眩晕（无 QTE 挣脱成功）+ 失败反馈
                            self.grapple_target.buff_manager.add_buff(BuffType.STUN, duration=1.5)
                            self.grapple_target.grappled = False
                            self.grapple_target.qte_window = 0.0
                            self.grapple_target.qte_fail_timer = 1.2
                        if hasattr(self.grapple_target, 'knockdown'):
                            self.grapple_target.knockdown(1.0)
                    except Exception:
                        pass
                    # 释放时给敌人一个短暂的击退，让它停在玩家面前
                    if hasattr(self.grapple_target, 'knockback_x'):
                        kb_dir_x = (self.grapple_target.x - player_x) / max(1, dist)
                        kb_dir_y = (self.grapple_target.y - player_y) / max(1, dist)
                        self.grapple_target.knockback_x = kb_dir_x * 50
                        self.grapple_target.knockback_y = kb_dir_y * 50
                    self._reset_grapple()
            else:
                self.grapple_state = "retracting"

        elif self.grapple_state == "retracting":
            dx = player_x - self.grapple_head_pos[0]
            dy = player_y - self.grapple_head_pos[1]
            dist = math.hypot(dx, dy)

            if dist < self.grapple_speed * 1.5 * dt * 60:
                self._reset_grapple()
            else:
                move_dist = self.grapple_speed * 1.5 * dt * 60
                if dist > 0:
                    self.grapple_head_pos[0] += (dx / dist) * move_dist
                    self.grapple_head_pos[1] += (dy / dist) * move_dist

        elif self.grapple_state == "self_pull":
            # ===== v2.2.5：自我拉拽——把自己拉向目标点 =====
            # v2.2.7：禁用玩家本帧位移叠加（防"故意不走蹭无敌"），提速拉回
            if player is None:
                self._reset_grapple()
                return
            tx, ty = self.grapple_target_pos
            dx = tx - player.x
            dy = ty - player.y
            dist = math.hypot(dx, dy)
            # v2.5.0 停滞断勾：0.5s 内距离未减少 ≥4px（被墙卡住）→ 断勾
            if not hasattr(self, '_pull_stall_timer'):
                self._pull_stall_timer = 0.0
                self._pull_stall_dist = dist
            if self._pull_stall_dist - dist < 4.0:
                self._pull_stall_timer += dt
            else:
                self._pull_stall_timer = 0.0
                self._pull_stall_dist = dist
            if self._pull_stall_timer >= 0.5:
                self._reset_grapple()
                return
            move_dist = self.self_pull_speed * dt
            if dist <= move_dist + 2:
                # 到达目标点：结束自我拉拽
                player.x, player.y = tx, ty
                self._reset_grapple()
            else:
                player.x += (dx / dist) * move_dist
                player.y += (dy / dist) * move_dist
            # 自我拉拽期间全程免伤（刷新无敌计时；恢复后由 mix_playing 关闭）
            if self.self_pull_immune and player is not None:
                player.invincible_timer = max(getattr(player, "invincible_timer", 0), 0.1)
            # 钩爪线跟随玩家
            self.grapple_head_pos = [player.x, player.y]

    def _qte_tap_in_sector(self, target, tap):
        """v2.5.5 打断绳索：单击点是否落在以绳索为对称轴的扇形内
        扇形：顶点在被勾玩家，以绳索方向为对称轴，半角80°，半径160 世界单位
        """
        try:
            fx, fy = getattr(target, 'qte_rope_from', (0, 0))
            tx, ty = getattr(target, 'qte_rope_to', (target.x, target.y))
            base = math.atan2(fy - ty, fx - tx)          # 绳索方向（指向钩爪源）
            dx, dy = tap[0] - tx, tap[1] - ty
            dist = math.hypot(dx, dy)
            if dist > 160:
                return False
            ang = math.atan2(dy, dx)
            diff = (ang - base + math.pi * 3) % (math.pi * 2) - math.pi
            return abs(diff) <= math.radians(80)
        except Exception:
            return False

    def _begin_self_pull(self, player_x, player_y, player=None):
        """进入自我拉拽状态：钩爪头到目标点后把自己拉过去。
        普通钩爪：拉自己过程中免伤且可操控枪械/技能（无范围伤害）。
        死神钩爪：沿途旋转挥舞镰刀造成范围伤害 + 全程免伤。"""
        if player is None:
            self.grapple_state = "retracting"
            return
        self.grapple_state = "self_pull"
        self.self_pull_active = True
        self.self_pull_immune = True
        self.self_pull_start = (player_x, player_y)
        self.self_pull_end = self.grapple_target_pos
        self.grapple_swing_timer = 0.0
        # v2.5.0 停滞断勾检测：被墙卡住长时间拉不动 → 断勾（防永远无敌）
        self._pull_stall_timer = 0.0
        self._pull_stall_dist = math.hypot(player_x - self.grapple_target_pos[0],
                                           player_y - self.grapple_target_pos[1])
        if player is not None:
            player.invincible_timer = max(getattr(player, "invincible_timer", 0), 0.1)

    def update_grapple_lock(self, player_x, player_y, enemies, items=None,
                            aim_angle=None, aim_dist=None,
                            players_down=None, players_enemy=None, players_teammate=None):
        """v2.2.11 瞄准期间更新锁定圈：蓄力圈由小到大 + 优先锁定特殊道具 + 圈内最近敌人
        锚点=预瞄终点（随瞄准方向/距离实时移动），aim_angle（度）/aim_dist 由触控瞄准传入，
        未传时回退 aim_line_angle 方向 max_range 处。
        v2.5.2 锁定优先级：倒地队友 > 异阵营玩家 > 特殊道具 > 僵尸"""
        if not self.grapple_aiming:
            self.grapple_locked_target = None
            self.grapple_aim_anchor = None
            return None
        # 蓄力计时：0.6s 内锁定圈从 18% 扩到 100%（v2.2.12 初始圈缩小）
        import time as _t
        if getattr(self, '_grapple_aim_charge', None) is None or getattr(self, '_grapple_aim_start', None) is None:
            self._grapple_aim_charge = 0.0
            self._grapple_aim_start = _t.time()
        self._grapple_aim_charge = min(1.0, (_t.time() - self._grapple_aim_start) / 0.6)
        cur_radius = self.grapple_lock_radius * max(0.18, self._grapple_aim_charge)
        # 锁定圈中心 = 锚点（预瞄终点，随瞄准移动）
        _a = math.radians(aim_angle if aim_angle is not None else self.aim_line_angle)
        _ad = aim_dist if aim_dist is not None else self.grapple_max_range
        _ax = player_x + math.cos(_a) * _ad
        _ay = player_y + math.sin(_a) * _ad
        self.grapple_aim_anchor = (_ax, _ay)
        best = None
        best_d = cur_radius
        # v2.5.2 1) 最高优先级：倒地队友（可勾取救援，拉回身边）
        if players_down:
            for _pd in players_down:
                if not getattr(_pd, 'alive', True):
                    continue
                if not getattr(_pd, 'downed', False):
                    continue
                d = math.hypot(_pd.x - _ax, _pd.y - _ay)
                if d < best_d:
                    best_d = d
                    best = _pd
        # v2.5.2 2) 异阵营玩家（可勾取+QTE）
        if best is None and players_enemy:
            for _pe in players_enemy:
                if not getattr(_pe, 'alive', True):
                    continue
                if getattr(_pe, 'downed', False):
                    continue
                d = math.hypot(_pe.x - _ax, _pe.y - _ay)
                if d < best_d:
                    best_d = d
                    best = _pe
        # v2.5.8 3) 同阵营存活玩家（可勾取救援/自拉）
        if best is None and players_teammate:
            for _pt in players_teammate:
                if not getattr(_pt, 'alive', True):
                    continue
                if getattr(_pt, 'downed', False):
                    continue
                d = math.hypot(_pt.x - _ax, _pt.y - _ay)
                if d < best_d:
                    best_d = d
                    best = _pt
        # 4) 特殊道具（宝箱/武器箱/加时道具等）
        if best is None and items:
            for it in items:
                if not getattr(it, "alive", False):
                    continue
                d = math.hypot(it.x - _ax, it.y - _ay)
                if d < best_d:
                    best_d = d
                    best = it
        # 5) 圈内最近敌人（Boss 不可锁定）
        if best is None:
            for e in enemies:
                if not getattr(e, "alive", False):
                    continue
                if getattr(e, "is_boss", False):
                    continue
                d = math.hypot(e.x - _ax, e.y - _ay)
                if d < best_d:
                    best_d = d
                    best = e
        # v2.2.9 极点自动锁定：蓄力满后圈内若无目标，自动扩到满半径再搜一次
        # （"直至极点自动锁定"——满蓄力即锁定最近的可锁定对象，无需手动对准）
        if best is None and self._grapple_aim_charge >= 0.95:
            full_r = self.grapple_lock_radius
            # v2.5.8: 极点也搜索存活队友
            if players_teammate:
                for _pt in players_teammate:
                    if not getattr(_pt, 'alive', True):
                        continue
                    if getattr(_pt, 'downed', False):
                        continue
                    d = math.hypot(_pt.x - _ax, _pt.y - _ay)
                    if d < full_r:
                        full_r = d
                        best = _pt
            if best is None and items:
                for it in items:
                    if not getattr(it, "alive", False):
                        continue
                    d = math.hypot(it.x - _ax, it.y - _ay)
                    if d < full_r:
                        full_r = d
                        best = it
            if best is None:
                full_r = self.grapple_lock_radius
                for e in enemies:
                    if not getattr(e, "alive", False):
                        continue
                    if getattr(e, "is_boss", False):
                        continue
                    d = math.hypot(e.x - _ax, e.y - _ay)
                    if d < full_r:
                        full_r = d
                        best = e
        self.grapple_locked_target = best
        return best

    def _reset_grapple(self):
        """重置钩爪状态"""
        self.grapple_active = False
        if self.grapple_target and hasattr(self.grapple_target, 'grappled'):
            self.grapple_target.grappled = False
        self.grapple_target = None
        self.grapple_target_pos = None
        self.grapple_head_pos = None
        self.grapple_state = "idle"
        # v2.7.2 数据层完整：直拉标志此前只在 _reset_grapple 里创建，
        # 新建的 RiotGear 实例拿不到这个属性（各处只能靠 getattr 兜底）。
        # 这里在构造时就初始化，保证每位玩家的钩爪状态机字段一致。
        self.grapple_direct_pull = False
        self._collision_prev_head = None
        # v2.2.5：清理自我拉拽/锁定状态
        self.self_pull_active = False
        self.self_pull_immune = False
        self.grapple_locked_target = None
        self.grapple_aiming = False
        self._grapple_aim_charge = None
        self.grapple_direct_pull = False
        self.grapple_pull_impact_hit = set()

    def get_shield_rect(self, player_x, player_y):
        if not self.equipped:
            return None
        angle_rad = math.radians(self.facing_angle)
        shield_cx = player_x + math.cos(angle_rad) * self.shield_offset
        shield_cy = player_y + math.sin(angle_rad) * self.shield_offset
        return pygame.Rect(
            shield_cx - self.shield_width // 2,
            shield_cy - self.shield_height // 2,
            self.shield_width,
            self.shield_height
        )

    def get_shield_front_arc(self, player_x, player_y):
        if not self.equipped:
            return None
        angle_rad = math.radians(self.facing_angle)
        shield_cx = player_x + math.cos(angle_rad) * self.shield_offset
        shield_cy = player_y + math.sin(angle_rad) * self.shield_offset
        return (shield_cx, shield_cy, self.facing_angle, 60)

    def check_shield_block(self, player_x, player_y, attack_x, attack_y):
        if not self.equipped or self.shield_broken:
            return False
        shield_rect = self.get_shield_rect(player_x, player_y)
        if shield_rect and shield_rect.collidepoint(attack_x, attack_y):
            return True
        dx = attack_x - player_x
        dy = attack_y - player_y
        attack_angle = math.degrees(math.atan2(dy, dx))
        angle_diff = abs((attack_angle - self.facing_angle + 180) % 360 - 180)
        return angle_diff < 60

    def take_damage(self, damage, damage_type="melee", from_front=True, attack_x=None, attack_y=None, blocked=None):
        """v2.2.0 优化格挡判定：blocked（盾牌几何命中）优先，其次 from_front 方向判定；
        抗性在盾碎后按伤害类型精确应用"""
        if not self.equipped:
            return damage
        if blocked is None:
            blocked = from_front
        if blocked and not self.shield_broken:
            if damage_type == "magic" or damage_type == "aoe":
                return 0
            self.viewing_window_hp -= damage
            if self.viewing_window_hp <= 0:
                self.viewing_window_hp = 0
                self.shield_broken = True
                self.shield_hp -= damage * 2
                if self.shield_hp <= 0:
                    self.shield_hp = 0
            return 0
        else:
            if self.shield_broken:
                if damage_type == "melee":
                    return damage * (1 - self.melee_reduction)
                elif damage_type == "ranged":
                    return damage * (1 - self.ranged_reduction)
                elif damage_type == "magic":
                    return 0 if self.magic_immunity else damage
                return damage
            else:
                return damage * 0.5

    def can_bash(self):
        return self.equipped and self.bash_cooldown <= 0 and self.stamina >= self.bash_stamina_cost and not self.charge_active

    def bash(self, direction_angle=None, is_sprint=False):
        """盾牌肘击（v2.2.0 改为原地肘击：不再启动冲撞位移，范围伤害由 mix_skills 一次性结算）"""
        if not self.can_bash():
            return False
        self.stamina -= self.bash_stamina_cost
        self.bash_cooldown = self.bash_max_cooldown
        if direction_angle is not None:
            self.charge_direction = direction_angle
        else:
            self.charge_direction = self.facing_angle
        self.charge_active = False
        self.charge_hit_ids = set()
        self.bash_anim_timer = self.bash_anim_duration
        return True

    def can_grapple(self):
        # 钩爪为独立技能，无需装备防爆套装
        return self.grapple_cooldown <= 0

    def use_grapple(self, target_x, target_y, player_x, player_y, target=None, scythe=False,
                    direct_pull=False):
        """使用钩爪 - 新逻辑：直接发射
        v2.2.5：scythe=True 时启用死神钩爪（CD 3s，锁定直飞）
        v2.2.12：direct_pull=True 直拉模式——发射后不碰撞勾取路径上任何僵尸/道具，
        钩爪头到达锚点即自我拉拽（长按未锁定钩爪的默认行为）"""
        if not self.can_grapple():
            return False

        dx = target_x - player_x
        dy = target_y - player_y
        dist = math.hypot(dx, dy)

        if dist > self.grapple_max_range:
            ratio = self.grapple_max_range / dist
            dx *= ratio
            dy *= ratio
            target_x = player_x + dx
            target_y = player_y + dy
            dist = self.grapple_max_range

        # 只消耗CD，不消耗体力（死神钩爪 3s / 普通 0.8s）
        self.grapple_is_scythe = bool(scythe)
        self.grapple_cooldown = self.grapple_scythe_max_cooldown if scythe else self.grapple_max_cooldown
        self.grapple_active = True
        self.grapple_target_pos = (target_x, target_y)
        self.grapple_head_pos = [player_x, player_y]
        self.grapple_state = "shooting"
        self.grapple_target = target
        # v2.5.0/v2.5.5 PvP 勾取玩家：初始化打断绳索 QTE（0.8s 内单击绳索对称轴扇形即打断）
        # v2.6.5 修复：恢复0.8s反应时间
        if target is not None and hasattr(target, 'qte_window'):
            if getattr(target, 'qte_immune_timer', 0) > 0:
                return False
            target.grappled = True
            target.qte_window = 0.8  # v2.6.5: 恢复0.8s反应时间
            target.qte_break_tap = None
            target.qte_break_hint = 1.0
            target.qte_hit_flash = 0.0
            target.qte_success_timer = 0.0
            target.qte_fail_timer = 0.0
        self.grapple_pull_impact_hit = set()
        self.grapple_direct_pull = bool(direct_pull)
        # v2.7.1 抗穿透：新一次发射清掉上一发的钩爪头轨迹缓存，
        # 否则新钩爪首帧会拿上一发的终点当起点，扫出一条不存在的超长线段。
        self._collision_prev_head = None
        return True

    def start_aim(self, angle):
        """开始瞄准（长按）"""
        self.aim_line_active = True
        self.aim_line_angle = angle
        self.aim_line_press_time = 0

    def update_aim(self, angle, dt):
        """更新瞄准方向"""
        if self.aim_line_active:
            self.aim_line_angle = angle
            self.aim_line_press_time += dt

    def is_long_press(self):
        """检查是否长按"""
        return self.aim_line_active and self.aim_line_press_time >= self.aim_threshold

    def end_aim(self):
        """结束瞄准"""
        was_long = self.is_long_press()
        self.aim_line_active = False
        self.aim_line_press_time = 0
        return was_long

    def set_grapple_target(self, enemy):
        self.grapple_target = enemy
        if enemy:
            self.grapple_target_pos = (enemy.x, enemy.y)

    def draw(self, screen, player_x, player_y, camera_x, camera_y, scale=1.0):
        px = int((player_x - camera_x) * scale)
        py = int((player_y - camera_y) * scale)

        # 钩爪始终绘制（独立技能，无需防爆套装）
        if self.grapple_active and self.grapple_head_pos:
            hx = int((self.grapple_head_pos[0] - camera_x) * scale)
            hy = int((self.grapple_head_pos[1] - camera_y) * scale)
            # 绳索（自我拉拽状态画粗一点 + 发光色）
            if self.grapple_state == "self_pull":
                pygame.draw.line(screen, (40, 120, 60), (px, py), (hx, hy), max(2, int(4 * scale)))
                pygame.draw.line(screen, (120, 230, 140), (px, py), (hx, hy), max(1, int(2 * scale)))
            else:
                pygame.draw.line(screen, (80, 80, 80), (px, py), (hx, hy), max(2, int(3 * scale)))
                pygame.draw.line(screen, (160, 160, 160), (px, py), (hx, hy), max(1, int(1 * scale)))
            # 钩爪头
            head_size = max(4, int(8 * scale))
            _hc = (200, 80, 90) if self.grapple_is_scythe else (60, 60, 60)
            pygame.draw.circle(screen, _hc, (hx, hy), head_size)
            pygame.draw.circle(screen, (180, 180, 180), (hx, hy), head_size - 2)
            # 钩子三叉
            hook_len = int(6 * scale)
            for ha in (-0.5, 0, 0.5):
                angle = math.atan2(hy - py, hx - px) + ha
                ex = hx + math.cos(angle) * hook_len
                ey = hy + math.sin(angle) * hook_len
                pygame.draw.line(screen, (200, 200, 200), (hx, hy), (ex, ey), max(1, int(2 * scale)))
            # 命中僵直火花
            if self.grapple_state == "hit":
                for _ in range(6):
                    sx = hx + random.randint(-10, 10)
                    sy = hy + random.randint(-10, 10)
                    pygame.draw.circle(screen, YELLOW, (sx, sy), max(1, int(2 * scale)))
            # 拉回火花
            if self.grapple_state == "pulling":
                for _ in range(4):
                    sx = hx + random.randint(-6, 6)
                    sy = hy + random.randint(-6, 6)
                    pygame.draw.circle(screen, ORANGE, (sx, sy), max(1, int(2 * scale)))
            # 自我拉拽：目标点标记
            if self.grapple_state == "self_pull" and self.self_pull_end:
                ex = int((self.self_pull_end[0] - camera_x) * scale)
                ey = int((self.self_pull_end[1] - camera_y) * scale)
                pygame.draw.circle(screen, (120, 230, 140), (ex, ey), max(3, int(6 * scale)), max(1, int(2 * scale)))
                pygame.draw.circle(screen, (*((120, 230, 140))[:3], 60), (ex, ey), max(5, int(10 * scale)))

        # v2.2.7/11 瞄准锁定圈：中心=锚点（预瞄终点，随瞄准实时移动），半径随蓄力由小到大
        if self.grapple_aiming and not self.grapple_active:
            _anch = getattr(self, 'grapple_aim_anchor', None)
            if _anch is not None:
                _ax, _ay = _anch
            else:
                _a = math.radians(self.aim_line_angle)
                _ax = player_x + math.cos(_a) * self.grapple_max_range
                _ay = player_y + math.sin(_a) * self.grapple_max_range
            _charge = getattr(self, '_grapple_aim_charge', 1.0) or 1.0
            _r = self.grapple_lock_radius * max(0.18, _charge)
            axp = int((_ax - camera_x) * scale)
            ayp = int((_ay - camera_y) * scale)
            lr = int(_r * scale)
            # v2.2.11 预瞄锚点（中心准星标记，随瞄准移动）
            _as = max(4, int(7 * scale))
            pygame.draw.line(screen, (120, 230, 140), (axp - _as, ayp), (axp + _as, ayp), max(1, int(2 * scale)))
            pygame.draw.line(screen, (120, 230, 140), (axp, ayp - _as), (axp, ayp + _as), max(1, int(2 * scale)))
            pygame.draw.circle(screen, (120, 230, 140), (axp, ayp), max(2, int(3 * scale)))
            # 锁定圈：由小到大扩至极点
            pygame.draw.circle(screen, (60, 200, 90), (axp, ayp), lr, max(1, int(2 * scale)))
            pygame.draw.circle(screen, (60, 200, 90), (axp, ayp), lr + int(4 * scale), max(1, int(1 * scale)))
            # 蓄力进度弧（18%→100%）
            try:
                _ch = max(0.0, min(1.0, _charge))
                _sa = -math.pi / 2
                _ea = _sa + (0.35 + 0.65 * _ch) * 2 * math.pi
                pygame.draw.arc(screen, (120, 255, 150), (axp - lr - 4, ayp - lr - 4, (lr + 4) * 2, (lr + 4) * 2),
                                _sa, _ea, max(1, int(2 * scale)))
            except Exception:
                pass
            if self.grapple_locked_target is not None and getattr(self.grapple_locked_target, "alive", False):
                lx = int((self.grapple_locked_target.x - camera_x) * scale)
                ly = int((self.grapple_locked_target.y - camera_y) * scale)
                # v2.2.6：锁定显示为圈（不再画红色连线），锁定目标用高亮红圈标注
                pygame.draw.circle(screen, (255, 80, 80), (lx, ly), max(4, int(10 * scale)), max(1, int(2 * scale)))
                pygame.draw.circle(screen, (255, 140, 120), (lx, ly), max(7, int(14 * scale)), max(1, int(1 * scale)))

        if not self.equipped:
            return

        shield_width = int(self.shield_width * scale)
        shield_height = int(self.shield_height * scale)

        angle_rad = math.radians(self.facing_angle)
        shield_offset_x = math.cos(angle_rad) * self.shield_offset * scale
        shield_offset_y = math.sin(angle_rad) * self.shield_offset * scale

        shield_rect = pygame.Rect(
            px + shield_offset_x - shield_width // 2,
            py + shield_offset_y - shield_height // 2,
            shield_width, shield_height
        )

        # 盾牌颜色根据状态变化
        if self.shield_broken:
            color = DARK_GRAY
        elif self.viewing_window_hp < self.max_viewing_window_hp * 0.3:
            color = (*RED[:3], 180)
        elif self.viewing_window_hp < self.max_viewing_window_hp * 0.6:
            color = (*ORANGE[:3], 200)
        else:
            color = BLUE

        pygame.draw.rect(screen, color, shield_rect, border_radius=max(1, int(5 * scale)))
        pygame.draw.rect(screen, WHITE, shield_rect, max(1, int(2 * scale)), border_radius=max(1, int(5 * scale)))

        # 观察窗
        if not self.shield_broken:
            ww = max(2, int(20 * scale))
            wh = max(2, int(30 * scale))
            window_rect = pygame.Rect(
                px + shield_offset_x - ww // 2,
                py + shield_offset_y - wh // 2,
                ww, wh
            )
            if self.viewing_window_hp > 50:
                window_color = CYAN
            elif self.viewing_window_hp > 20:
                window_color = YELLOW
            else:
                window_color = RED
            pygame.draw.rect(screen, window_color, window_rect)
            pygame.draw.rect(screen, WHITE, window_rect, max(1, int(scale)))

            # 观察窗HP条
            if self.viewing_window_hp < self.max_viewing_window_hp:
                bar_w = ww
                bar_h = max(2, int(3 * scale))
                bar_y = window_rect.bottom + 2
                hp_ratio = self.viewing_window_hp / self.max_viewing_window_hp
                pygame.draw.rect(screen, RED, (window_rect.x, bar_y, bar_w, bar_h))
                pygame.draw.rect(screen, GREEN, (window_rect.x, bar_y, int(bar_w * hp_ratio), bar_h))

        # DEBUFF警告
        if self.has_debuff:
            if int(pygame.time.get_ticks() / 500) % 2 == 0:
                pygame.draw.rect(screen, RED, shield_rect, max(2, int(3 * scale)), border_radius=max(1, int(5 * scale)))

        # 绘制预瞄线
        if self.aim_line_active:
            aim_dist = self.grapple_max_range * scale
            aim_end_x = px + math.cos(self.aim_line_angle) * aim_dist
            aim_end_y = py + math.sin(self.aim_line_angle) * aim_dist
            # 虚线预瞄
            dash_len = 15
            gap_len = 8
            total_dist = aim_dist
            current = 0
            while current < total_dist:
                ratio_start = current / total_dist
                ratio_end = min((current + dash_len) / total_dist, 1.0)
                sx = px + (aim_end_x - px) * ratio_start
                sy = py + (aim_end_y - py) * ratio_start
                ex = px + (aim_end_x - px) * ratio_end
                ey = py + (aim_end_y - py) * ratio_end
                pygame.draw.line(screen, (*GREEN[:3], 120), (sx, sy), (ex, ey), max(1, int(2 * scale)))
                current += dash_len + gap_len
            # 终点标记
            pygame.draw.circle(screen, (*GREEN[:3], 80), (int(aim_end_x), int(aim_end_y)), int(8 * scale))
            pygame.draw.circle(screen, GREEN, (int(aim_end_x), int(aim_end_y)), int(8 * scale), max(1, int(2 * scale)))

        # 绘制肘击动画
        if self.bash_anim_timer > 0:
            progress = 1 - (self.bash_anim_timer / self.bash_anim_duration)
            bash_dist = 40 * progress * scale
            angle_rad = math.radians(self.bash_direction)
            bx = px + math.cos(angle_rad) * bash_dist
            by = py + math.sin(angle_rad) * bash_dist

            wave_size = int(25 * scale * (1 - progress))
            pygame.draw.circle(screen, (*CYAN[:3], 150), (int(bx), int(by)), wave_size, 2)
            pygame.draw.circle(screen, CYAN, (int(bx), int(by)), max(2, int(10 * scale)))
            line_len = 30 * scale
            for offset in [-20, 0, 20]:
                off_rad = math.radians(self.bash_direction + offset)
                sx = bx + math.cos(off_rad) * line_len * 0.5
                sy = by + math.sin(off_rad) * line_len * 0.5
                ex = bx + math.cos(off_rad) * line_len
                ey = by + math.sin(off_rad) * line_len
                pygame.draw.line(screen, WHITE, (sx, sy), (ex, ey), max(1, int(2 * scale)))

        # 绘制体力条
        sw = int(50 * scale)
        sh = max(2, int(6 * scale))
        sx = px - sw // 2
        sy = py + int(45 * scale)
        pygame.draw.rect(screen, DARK_GRAY, (sx, sy, sw, sh))
        pygame.draw.rect(screen, GREEN, (sx, sy, int(sw * (self.stamina / self.max_stamina)), sh))
        pygame.draw.rect(screen, WHITE, (sx, sy, sw, sh), max(1, int(scale)))

        if self.stamina < self.bash_stamina_cost:
            pygame.draw.rect(screen, (*RED[:3], 100), (sx, sy, sw, sh))
