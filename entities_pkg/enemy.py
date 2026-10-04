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


class Enemy:
    def __init__(self, x, y, enemy_type, wave, difficulty="normal"):
        self.x = x
        self.y = y
        self.enemy_type = enemy_type
        self.wave = wave
        self.difficulty = difficulty
        self.alive = True
        self.knockdown_timer = 0
        self.frozen_timer = 0
        self.grappled = False
        self._collision_skip = 0

        # 特殊状态
        self.invisible = False
        self.invisible_timer = 0
        self.invisible_cooldown = 0
        self.split_count = 0  # 分裂次数
        self.heal_radius = 100  # 治疗半径
        self.heal_timer = 0
        self.explode_timer = 0  # 爆炸倒计时
        self.is_exploding = False
        self.phantom_flicker = 0  # 幻影闪烁
        # Buff系统
        self.buff_manager = BuffManager()
        # 控制抗性：Boss对控制类debuff有高抗性/免疫
        self.control_resistance = 0.0  # 0=无抗性, 1=完全免疫
        self.can_throw = False  # 是否能投掷道具
        self.throw_cd = random.uniform(3.0, 6.0)  # 投掷道具CD
        self.buff_damage_events = []
        self._setup_enemy()
        # Boss控制抗性设置（在_setup_enemy后设置is_boss）
        if getattr(self, 'is_boss', False):
            self.control_resistance = 0.85  # Boss 85%概率免疫控制
            self.can_throw = True  # Boss具备投掷能力（fire/rock/acid）
        elif getattr(self, 'is_elite', False):
            self.control_resistance = 0.4   # 精英 40%免疫

        # =========【新增Boss技能计时器】=========
        self.boss_dash_cd = 0.0
        self.boss_aoe_cd = 0.0
        self.boss_shoot_cd = 0.0
        self.boss_shield_cd = 0.0
        self.is_dashing = False
        self.dash_target_x = 0.0
        self.dash_target_y = 0.0
        self.dash_speed = 0.0
        self.dash_timer = 0.0
        self.boss_hold_shield = False

        self.boss_execution_cd = 0.0       # 处决大招CD
        self.boss_execution_windup = 0.0  # 处决前摇时间（提示阶段）
        self.boss_is_executing = False     # 是否正在处决前摇
        self.boss_salvo_cd = 0.0          # 向某连射CD
        self.boss_backstep_cd = 0.0       # 向某后撤滑步CD
        # === 新增Boss技能计时器 ===
        self.boss_summon_cd = 0.0         # 召唤小怪CD
        self.boss_charge_cd = 0.0         # 狂暴冲锋CD
        self.boss_regen_cd = 0.0          # 护盾再生/回血CD
        self.boss_ground_slam_cd = 0.0    # 地震波CD
        self.boss_barrage_cd = 0.0        # 弹幕扫射CD
        self.boss_smoke_cd = 0.0          # 烟雾弹CD
        self.boss_teleport_cd = 0.0       # 闪现CD
        self.boss_grenade_cd = 0.0        # 手雷CD
        self.skill_windup = 0.0           # 技能前摇计时（预警系统使用）
        self.boss_is_charging = False     # 是否正在冲锋
        self.boss_charge_timer = 0.0      # 冲锋持续时间
        self.boss_charge_dir = (0, 0)     # 冲锋方向
        # === 特种僵尸能力计时器 ===
        self.special_ability_cd = 0.0     # 通用特种能力CD
        self.fast_dash_ready = True       # 快速僵尸冲刺就绪
        self.tank_slam_cd = 0.0           # 坦克重击CD
        self.ranged_burst_cd = 0.0        # 远程连射CD
        self.phantom_teleport_cd = 0.0    # 幻影瞬移CD
        self.shield_charge_cd = 0.0       # 盾兵冲锋CD
        self.healer_wave_cd = 0.0         # 治疗波CD

        # === 特殊攻击前摇系统 ===
        self.special_windup_timer = 0.0   # 特殊攻击前摇剩余时间
        self.special_windup_type = None   # 正在前摇的特殊攻击类型
        self.special_windup_radius = 0    # 特殊攻击范围（用于预警显示）
        self.special_windup_target_x = 0  # 特殊攻击目标X
        self.special_windup_target_y = 0  # 特殊攻击目标Y

    def _setup_enemy(self):
        base_configs = {
            EnemyType.ZOMBIE_NORMAL: {
                "hp": 35, "speed": 1.8, "damage": 12, "size": 15,
                "color": DARK_GREEN, "exp": 10, "score": 10
            },
            EnemyType.ZOMBIE_FAST: {
                "hp": 20, "speed": 3.5, "damage": 10, "size": 12,
                "color": POISON_GREEN, "exp": 15, "score": 15
            },
            EnemyType.ZOMBIE_TANK: {
                "hp": 120, "speed": 1.0, "damage": 25, "size": 22,
                "color": GRAY, "exp": 30, "score": 30
            },
            EnemyType.ZOMBIE_RANGED: {
                "hp": 30, "speed": 1.5, "damage": 18, "size": 14,
                "color": PURPLE, "exp": 20, "score": 20,
                "attack_range": 300, "attack_cooldown": 2.0,
                "can_throw": True, "throw_type": "rock",
            },
            # === 新机制僵尸 ===
            EnemyType.ZOMBIE_EXPLODER: {
                "hp": 40, "speed": 2.5, "damage": 8, "size": 16,
                "color": RUST, "exp": 25, "score": 25,
                "is_exploder": True, "explode_radius": 100, "explode_damage": 100
            },
            EnemyType.ZOMBIE_CRAWLER: {
                "hp": 15, "speed": 4.0, "damage": 8, "size": 8,
                "color": SLATE, "exp": 12, "score": 12,
                "is_crawler": True, "dodge_chance": 0.3
            },
            EnemyType.ZOMBIE_SPLITTER: {
                "hp": 80, "speed": 1.3, "damage": 15, "size": 18,
                "color": BLOOD_RED, "exp": 35, "score": 35,
                "is_splitter": True, "split_into": 2
            },
            EnemyType.ZOMBIE_SHIELD: {
                "hp": 60, "speed": 1.2, "damage": 15, "size": 17,
                "color": CHARCOAL, "exp": 22, "score": 22,
                "is_shield": True, "front_reduction": 0.6
            },
            EnemyType.ZOMBIE_HEALER: {
                "hp": 35, "speed": 1.0, "damage": 10, "size": 14,
                "color": GREEN, "exp": 30, "score": 30,
                "is_healer": True, "heal_amount": 5, "heal_interval": 2.0
            },
            EnemyType.ZOMBIE_PHANTOM: {
                "hp": 45, "speed": 2.0, "damage": 20, "size": 15,
                "color": PURPLE, "exp": 28, "score": 28,
                "is_phantom": True, "invisible_duration": 2.0, "visible_duration": 3.0
            },
            EnemyType.BOSS_LONG: {
                "hp": 6000, "speed": 1.5, "damage": 75, "size": 35,
                "color": BLOOD_RED, "exp": 500, "score": 1000,
                "is_boss": True, "name": "龙某"
            },
            EnemyType.BOSS_XIANG: {
                "hp": 5000, "speed": 1.8, "damage": 55, "size": 32,
                "color": RUST, "exp": 500, "score": 1000,
                "is_boss": True, "name": "向某"
            },
            # === 新Boss ===
            EnemyType.BOSS_MUTANT: {
                "hp": 8000, "speed": 2.2, "damage": 70, "size": 38,
                "color": BLOOD_RED, "exp": 800, "score": 1500,
                "is_boss": True, "name": "变异体-深渊",
                "has_combo": True, "combo_damage_mult": 3.0,
            },
            EnemyType.BOSS_QUEEN: {
                "hp": 7000, "speed": 1.3, "damage": 45, "size": 40,
                "color": PURPLE, "exp": 800, "score": 1500,
                "is_boss": True, "name": "尸潮女王",
                "summons_minions": True, "summon_interval": 8.0,
            },
            EnemyType.BOSS_TITAN: {
                "hp": 12000, "speed": 0.9, "damage": 110, "size": 50,
                "color": CHARCOAL, "exp": 1000, "score": 2000,
                "is_boss": True, "name": "泰坦",
                "is_titan": True, "stomp_damage": 200, "stomp_radius": 150,
            },
            EnemyType.BOSS_WANG: {
                "hp": 10000, "speed": 1.6, "damage": 70, "size": 36,
                "color": (70, 70, 80), "exp": 1200, "score": 2500,
                "is_boss": True, "name": "王某",
                "has_gunfire": True, "has_scythe": True,
                "scythe_damage_mult": 3.6,
            },
            # === 精英怪 ===
            EnemyType.ELITE_BRUTE: {
                "hp": 300, "speed": 1.4, "damage": 35, "size": 24,
                "color": DARK_RED, "exp": 80, "score": 80,
                "is_elite": True, "name": "精英蛮兵",
                "heavy_attack_chance": 0.3, "heavy_damage_mult": 2.5,
            },
            EnemyType.ELITE_ASSASSIN: {
                "hp": 150, "speed": 4.5, "damage": 40, "size": 14,
                "color": CYAN, "exp": 80, "score": 80,
                "is_elite": True, "name": "精英刺客",
                "dash_chance": 0.25, "dash_damage_mult": 3.0,
            },
            EnemyType.ELITE_SORCERER: {
                "hp": 180, "speed": 1.2, "damage": 25, "size": 16,
                "color": PURPLE, "exp": 90, "score": 90,
                "is_elite": True, "name": "精英术士",
                "is_ranged": True, "projectile_damage": 30, "attack_range": 350,
                "applies_curse": True,
                "can_throw": True, "throw_type": "fire",
            },
            EnemyType.ELITE_GUARDIAN: {
                "hp": 400, "speed": 1.0, "damage": 20, "size": 22,
                "color": GOLD, "exp": 100, "score": 100,
                "is_elite": True, "name": "精英守卫",
                "aura_heal": True, "aura_radius": 120, "aura_heal_amount": 3,
                "shield_reduction": 0.5,
            },
            # === 新普通僵尸 ===
            EnemyType.ZOMBIE_SPITTER: {
                "hp": 30, "speed": 1.5, "damage": 10, "size": 14,
                "color": LIME, "exp": 18, "score": 18,
                "is_ranged": True, "projectile_damage": 12, "attack_range": 250,
                "applies_corrosion": True,
                "can_throw": True, "throw_type": "acid",
            },
            EnemyType.ZOMBIE_LEAPER: {
                "hp": 25, "speed": 2.0, "damage": 18, "size": 13,
                "color": ORANGE, "exp": 20, "score": 20,
                "leap_chance": 0.15, "leap_range": 200, "leap_damage_mult": 2.0,
            },
            EnemyType.ZOMBIE_CORPSE_EATER: {
                "hp": 50, "speed": 1.3, "damage": 15, "size": 17,
                "color": BROWN, "exp": 25, "score": 25,
                "eats_corpses": True, "grow_per_corpse": 1.2,
            },
            EnemyType.ZOMBIE_WRAITH: {
                "hp": 35, "speed": 2.5, "damage": 15, "size": 15,
                "color": PURPLE, "exp": 30, "score": 30,
                "is_wraith": True, "phase_through": True,
                "applies_fear": True, "fear_chance": 0.2,
            },
            # === 新增僵尸类型 ===
            EnemyType.ZOMBIE_BOMBER: {
                "hp": 40, "speed": 2.0, "damage": 20, "size": 16,
                "color": ORANGE, "exp": 28, "score": 28,
                "can_throw": True, "throw_type": "bomb",
                "is_bomber": True,
            },
            EnemyType.ZOMBIE_FROST: {
                "hp": 45, "speed": 1.5, "damage": 12, "size": 16,
                "color": CYAN, "exp": 25, "score": 25,
                "is_frost": True, "applies_slow": True,
                "slow_duration": 2.0, "slow_amount": 0.5,
            },
            EnemyType.ZOMBIE_VENOM: {
                "hp": 30, "speed": 2.2, "damage": 8, "size": 14,
                "color": POISON_GREEN, "exp": 26, "score": 26,
                "is_venom": True, "applies_poison": True,
                "poison_damage": 5, "poison_duration": 4.0,
            },
            EnemyType.ZOMBIE_BERSERKER: {
                "hp": 80, "speed": 1.8, "damage": 18, "size": 18,
                "color": CRIMSON, "exp": 35, "score": 35,
                "is_berserker": True, "enrage_below_hp": 0.4,
                "enrage_speed_mult": 2.0, "enrage_damage_mult": 1.5,
            },
            EnemyType.ZOMBIE_GHOUL: {
                "hp": 50, "speed": 2.0, "damage": 10, "size": 15,
                "color": BLOOD_RED, "exp": 28, "score": 28,
                "is_ghoul": True, "bleed_chance": 0.4,
                "bleed_damage": 3, "bleed_duration": 3.0,
            },
            EnemyType.ZOMBIE_SHAMAN: {
                "hp": 35, "speed": 1.2, "damage": 8, "size": 15,
                "color": MAGENTA, "exp": 32, "score": 32,
                "is_shaman": True, "buff_radius": 120,
                "buff_damage_mult": 1.3, "buff_speed_mult": 1.2,
            },
            EnemyType.ZOMBIE_HUNTER: {
                "hp": 35, "speed": 1.8, "damage": 25, "size": 14,
                "color": DARK_BLUE, "exp": 30, "score": 30,
                "is_hunter": True, "attack_range": 350,
                "attack_cooldown": 3.0, "is_ranged": True,
            },
            EnemyType.ZOMBIE_JUGGERNAUT: {
                "hp": 200, "speed": 0.8, "damage": 30, "size": 25,
                "color": DARK_GRAY, "exp": 50, "score": 50,
                "is_juggernaut": True, "armor": 0.5,
                "knockback_resist": 0.8,
            },
        }

        config = base_configs.get(self.enemy_type, base_configs[EnemyType.ZOMBIE_NORMAL])
        for k, v in config.items():
            setattr(self, k, v)

        diff_mult = {"简单": 0.7, "普通": 1.0, "困难": 1.5, "地狱": 2.2}
        dm = diff_mult.get(self.difficulty, 1.0)

        # 区分：普通敌人wave=波次数字，Boss wave=horde_manager实例
        if isinstance(self.wave, (int, float)):
            wave_mult = 1 + (self.wave - 1) * 0.3
            wave_num = self.wave
        else:
            # Boss，wave是horde_manager，波次取固定1
            wave_mult = 1.0
            wave_num = 1

        time_scale = 1.0
        if hasattr(self.wave, "total_time"):
            time_scale = min(1.8, 1.0 + self.wave.total_time / 300.0)

        self.max_hp = self.hp = int(config["hp"] * wave_mult * dm * time_scale)
        self.speed = config["speed"] * (1 + (wave_num - 1) * 0.1)
        self.damage = int(config["damage"] * wave_mult * dm * time_scale)
        self.attack_timer = 0
        self.anim_frame = 0
        self.anim_timer = 0

    def update(self, dt, player_x, player_y, player, world=None):
        # 更新Buff系统（持续伤害/治疗等）
        _, self.buff_damage_events = self.buff_manager.update(dt, self)
        # DOT致死安全检查：确保持续伤害能杀死怪物
        if self.hp <= 0 and self.alive:
            self.alive = False
        self._buff_speed_mult = self.buff_manager.get_speed_mult()
        # Buff冻结/眩晕优先
        if self.buff_manager.is_stunned() or self.buff_manager.is_frozen():
            return
        if self.knockdown_timer > 0:
            self.knockdown_timer -= dt
            return
        if self.frozen_timer > 0:
            self.frozen_timer -= dt
            return
        if self.grappled:
            # 被钩爪勾中：完全由RiotGear控制位置，敌人不做任何自主行动
            return

        # ========== Boss智能AI增强 ==========
        if getattr(self, "is_boss", False) and self.alive:
            self._update_boss_ai(dt, player_x, player_y, player)

        # 幻影僵尸隐身逻辑
        if getattr(self, "is_phantom", False):
            self.invisible_timer -= dt
            self.invisible_cooldown -= dt
            if self.invisible_timer > 0:
                self.invisible = True
            else:
                self.invisible = False
                if self.invisible_cooldown <= 0:
                    self.invisible_timer = self.invisible_duration
                    self.invisible_cooldown = self.visible_duration

        # 治疗僵尸逻辑
        if getattr(self, "is_healer", False):
            self.heal_timer -= dt
            if self.heal_timer <= 0:
                self.heal_timer = self.heal_interval
                # 治疗周围僵尸
                # 这个在 game.py 中处理

        # 爆炸僵尸逻辑
        if getattr(self, "is_exploder", False):
            dist_to_player = math.hypot(player_x - self.x, player_y - self.y)
            if dist_to_player < 60 and not self.is_exploding:
                self.is_exploding = True
                self.explode_timer = 1.5  # 1.5秒后爆炸
            if self.is_exploding:
                self.explode_timer -= dt
                if self.explode_timer <= 0:
                    self.alive = False  # 自爆死亡
                    return "explode"

        dx = player_x - self.x
        dy = player_y - self.y
        dist = math.hypot(dx, dy)

        # === 特殊攻击前摇处理 ===
        if self.special_windup_timer > 0:
            self.special_windup_timer -= dt
            # 前摇期间缓慢移动或不移动
            if self.special_windup_timer <= 0:
                # 前摇结束，执行特殊攻击
                windup_type = self.special_windup_type
                self.special_windup_type = None
                self.special_windup_radius = 0
                return windup_type
            return None

        if dist > 0:
            if getattr(self, "is_boss", False):
                self._boss_behavior(dt, player_x, player_y, dist, player)
            else:
                # === 特种僵尸特色能力 ===
                special_result = self._special_ability(dt, player_x, player_y, dist)
                if special_result:
                    # 检查是否需要前摇
                    windup_config = self._get_windup_config(special_result)
                    if windup_config:
                        # 设置前摇状态
                        self.special_windup_timer = windup_config["duration"]
                        self.special_windup_type = special_result
                        self.special_windup_radius = windup_config.get("radius", 0)
                        self.special_windup_target_x = player_x
                        self.special_windup_target_y = player_y
                        return None
                    return special_result

                if getattr(self, "attack_range", 0) > 0 and dist < self.attack_range:
                    if dist < self.attack_range * 0.5:
                        mdx = -(dx / dist) * self.speed * self._buff_speed_mult * dt * 60
                        mdy = -(dy / dist) * self.speed * self._buff_speed_mult * dt * 60
                        self._move_with_obstacle_collision(mdx, mdy, world)
                    else:
                        self._ranged_attack(dt, player_x, player_y, dist)
                else:
                    mdx = (dx / dist) * self.speed * self._buff_speed_mult * dt * 60
                    mdy = (dy / dist) * self.speed * self._buff_speed_mult * dt * 60
                    self._move_with_obstacle_collision(mdx, mdy, world)

        self.anim_timer += dt
        if self.anim_timer > 0.2:
            self.anim_timer = 0
            self.anim_frame = (self.anim_frame + 1) % 4

    def _move_with_obstacle_collision(self, move_dx, move_dy, world):
        """带障碍物碰撞的移动：普通怪物被阻挡，特殊怪物可穿越"""
        can_phase = (getattr(self, "is_crawler", False) or
                      getattr(self, "is_phantom", False) or
                      getattr(self, "is_wraith", False) or
                      getattr(self, "is_leaper", False) or
                      getattr(self, "is_boss", False))
        if can_phase or world is None or not hasattr(world, 'obstacles'):
            self.x += move_dx
            self.y += move_dy
            return
        enemy_rect = pygame.Rect(self.x - self.size, self.y - self.size,
                                  self.size * 2, self.size * 2)
        new_rect_x = enemy_rect.copy()
        new_rect_x.x += move_dx
        if not any(new_rect_x.colliderect(obs['rect']) for obs in world.obstacles):
            self.x += move_dx
        new_rect_y = enemy_rect.copy()
        new_rect_y.y += move_dy
        if not any(new_rect_y.colliderect(obs['rect']) for obs in world.obstacles):
            self.y += move_dy

    def _wang_behavior(self, dt, player_x, player_y, dist, player, hp_ratio, can_execution):
        """王某：枪械+死神镰刀双形态（极强Boss）
        血量>50%：枪械形态——远程连续射击弹幕 + 枪榴弹
        血量<=50%：死神镰刀形态——高速突进 + 大范围镰刀横扫 + 处决斩击
        返回: None / "wang_gunfire" / "wang_grenade" / "wang_scythe_sweep" / dict(子弹)
        """
        if hp_ratio > 0.5:
            # ===== 枪械形态（远程压制）【Utility AI】=====
            pick, _ps = self._utility_pick([
                ("gunfire", lambda: (66 if (dist > 150 and self.boss_shoot_cd <= 0) else 0)),
                ("grenade", lambda: (52 if (self.boss_grenade_cd <= 0) else 0)),
                ("move", lambda: 26),
            ])
            if pick == "gunfire":
                self.boss_shoot_cd = 1.2
                self.skill_windup = 0.5
                return "wang_gunfire"
            elif pick == "grenade":
                self.boss_grenade_cd = 6.0
                self.skill_windup = 0.8
                return "wang_grenade"
        else:
            # ===== 死神镰刀形态（近战爆发）【Utility AI】=====
            pick, _ps = self._utility_pick([
                ("execution", lambda: (78 if (can_execution and dist < 200) else 0)),
                ("sweep", lambda: (66 if (dist < 230 and self.boss_aoe_cd <= 0) else 0)),
                ("dash", lambda: (60 if (dist > 120 and self.boss_dash_cd <= 0) else 0)),
                ("move", lambda: 32),
            ])
            if pick == "execution":
                self.boss_is_executing = True
                self.boss_execution_windup = 1.2
                self.boss_execution_cd = 12.0
                return None
            elif pick == "sweep":
                self.boss_aoe_cd = 4.0
                self.skill_windup = 0.6
                return "wang_scythe_sweep"
            elif pick == "dash":
                self.is_dashing = True
                self.dash_target_x = player_x
                self.dash_target_y = player_y
                self.dash_speed = 9.0
                self.dash_timer = 0.4
                self.boss_dash_cd = 3.0
                return None
        # 移动（镰刀形态移速提升）
        move_speed = self.speed * (1.4 if hp_ratio <= 0.5 else 1.0)
        bsm = getattr(self, '_buff_speed_mult', 1.0)
        if dist > 0:
            self.x += (player_x - self.x) / dist * move_speed * bsm * dt * 60
            self.y += (player_y - self.y) / dist * move_speed * bsm * dt * 60
        return None

    def _utility_pick(self, actions):
        """Utility AI 决策核心：评估所有就绪行为，实时打分，返回分数最高的行为key与分数。

        actions: list[ (key, score_func) ]，score_func 计算 0~100 分；就绪性由各行为打分内判断。
        返回: (best_key, best_score)，best_score<=0 时返回 (None, 0) 表示无行为触发。
        """
        best_key = None
        best_score = 0.0
        for key, score_func in actions:
            try:
                s = float(score_func())
            except Exception:
                s = 0.0
            if s > best_score:
                best_score = s
                best_key = key
        return best_key, best_score

    def _boss_behavior(self, dt, player_x, player_y, dist, player):
        """
        BOSS_LONG(龙某):近战盾Boss，血量低释放重劈处决
        BOSS_XIANG(向某):远程Boss，新增后撤滑步、连射，低血量霰弹处决爆发
        返回: None / "boss_aoe" / "boss_execution_slash" / "boss_execution_salvo" / dict(子弹)
        """
        # 更新全部技能CD
        if self.boss_dash_cd > 0:
            self.boss_dash_cd -= dt
        if self.boss_aoe_cd > 0:
            self.boss_aoe_cd -= dt
        if self.boss_shoot_cd > 0:
            self.boss_shoot_cd -= dt
        if self.boss_shield_cd > 0:
            self.boss_shield_cd -= dt
        if self.boss_execution_cd > 0:
            self.boss_execution_cd -= dt
        if self.boss_salvo_cd > 0:
            self.boss_salvo_cd -= dt
        if self.boss_backstep_cd > 0:
            self.boss_backstep_cd -= dt
        if self.boss_summon_cd > 0:
            self.boss_summon_cd -= dt
        if self.boss_charge_cd > 0:
            self.boss_charge_cd -= dt
        if self.boss_regen_cd > 0:
            self.boss_regen_cd -= dt
        if self.boss_ground_slam_cd > 0:
            self.boss_ground_slam_cd -= dt
        if self.boss_barrage_cd > 0:
            self.boss_barrage_cd -= dt
        if self.boss_smoke_cd > 0:
            self.boss_smoke_cd -= dt
        if self.boss_teleport_cd > 0:
            self.boss_teleport_cd -= dt
        if self.boss_grenade_cd > 0:
            self.boss_grenade_cd -= dt
        # 技能前摇计时（预警用）
        if self.skill_windup > 0:
            self.skill_windup -= dt

        # ========= 狂暴冲锋处理 =========
        if self.boss_is_charging:
            self.boss_charge_timer -= dt
            if self.boss_charge_timer <= 0:
                self.boss_is_charging = False
            else:
                dx, dy = self.boss_charge_dir
                self.x += dx * 12.0 * dt * 60
                self.y += dy * 12.0 * dt * 60
                return "boss_charge_trail"

        # ========= 处决前摇处理 =========
        if self.boss_is_executing:
            self.boss_execution_windup -= dt
            # 处决前摇期间Boss缓慢追踪玩家，避免处决落空
            if self.boss_execution_windup > 0:
                _dd = math.hypot(player_x - self.x, player_y - self.y)
                if _dd > 0:
                    self.x += (player_x - self.x) / _dd * self.speed * 1.7 * dt * 60
                    self.y += (player_y - self.y) / _dd * self.speed * 1.7 * dt * 60
            if self.boss_execution_windup <= 0:
                self.boss_is_executing = False
                # 根据boss类型返回处决攻击标记
                if self.enemy_type == EnemyType.BOSS_LONG:
                    return "boss_execution_slash"
                elif self.enemy_type == EnemyType.BOSS_XIANG:
                    return "boss_execution_salvo"
                elif self.enemy_type == EnemyType.BOSS_MUTANT:
                    return "boss_execution_mutant"
                elif self.enemy_type == EnemyType.BOSS_QUEEN:
                    return "boss_execution_queen"
                elif self.enemy_type == EnemyType.BOSS_TITAN:
                    return "boss_execution_titan"
                elif self.enemy_type == EnemyType.BOSS_WANG:
                    return "wang_execution_scythe"
            return None

        # 冲刺移动逻辑
        if self.is_dashing:
            self.dash_timer -= dt
            dx = self.dash_target_x - self.x
            dy = self.dash_target_y - self.y
            d = math.hypot(dx, dy)
            if d < 12 or self.dash_timer <= 0:
                self.is_dashing = False
            else:
                self.x += (dx / d) * self.dash_speed * dt * 60
                self.y += (dy / d) * self.dash_speed * dt * 60
            return None

        hp_ratio = self.hp / self.max_hp
        # 血量低于30%，可以释放处决大招，有冷却
        can_execution = (hp_ratio <= 0.30) and (self.boss_execution_cd <= 0)

        # ========= 王某：枪械+死神镰刀双形态（极强Boss）=========
        if self.enemy_type == EnemyType.BOSS_WANG:
            return self._wang_behavior(dt, player_x, player_y, dist, player, hp_ratio, can_execution)

        if self.enemy_type == EnemyType.BOSS_LONG:
            # ----龙某：近战盾Boss----
            # 举盾：距离远时概率举盾，减少受到远程伤害
            if dist > 220 and self.boss_shield_cd <= 0 and random.random() < 0.02:
                self.boss_hold_shield = True
                self.boss_shield_cd = 7.0
            if dist < 160:
                self.boss_hold_shield = False

            # 【Utility AI 决策】龙某所有就绪行为实时打分，选最高分执行
            pick, _ps = self._utility_pick([
                ("execution", lambda: (65 if (can_execution and dist < 170) else 0)),
                ("dash", lambda: (70 if (dist > 110 and self.boss_dash_cd <= 0) else 0)),
                ("aoe", lambda: (68 if (dist < 140 and self.boss_aoe_cd <= 0) else 0)),
                ("slam", lambda: (55 + (25 if hp_ratio <= 0.5 else 0)) if (dist < 200 and self.boss_ground_slam_cd <= 0) else 0),
                ("charge", lambda: (62 if (150 < dist < 400 and self.boss_charge_cd <= 0) else 0)),
                ("summon", lambda: (45 if (hp_ratio < 0.5 and self.boss_summon_cd <= 0) else 0)),
                ("regen", lambda: (40 if (hp_ratio < 0.4 and self.boss_regen_cd <= 0) else 0)),
                ("move", lambda: 28),
            ])
            if pick == "execution":
                self.boss_is_executing = True
                self.boss_execution_windup = 1.1   # 1.1秒红色前摇警告
                self.boss_execution_cd = 14.0
                return None
            elif pick == "dash":
                self.is_dashing = True
                self.dash_target_x = player_x
                self.dash_target_y = player_y
                self.dash_speed = 7.5
                self.dash_timer = 0.45
                self.boss_dash_cd = 4.5
                return None
            elif pick == "aoe":
                self.boss_aoe_cd = 5.0
                return "boss_aoe"
            elif pick == "slam":
                self.boss_ground_slam_cd = 8.0
                return "boss_ground_slam"
            elif pick == "charge":
                self.boss_charge_cd = 6.0
                self.boss_is_charging = True
                self.boss_charge_timer = 0.5
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.boss_charge_dir = ((player_x - self.x) / d, (player_y - self.y) / d)
                return None
            elif pick == "summon":
                self.boss_summon_cd = 15.0
                return "boss_summon_melee"
            elif pick == "regen":
                self.boss_regen_cd = 20.0
                self.hp = min(self.max_hp, self.hp + self.max_hp * 0.15)
                return "boss_regen"

            # 普通向玩家移动
            if dist > 0:
                self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        elif self.enemy_type == EnemyType.BOSS_XIANG:
            # ----向某：远程Boss【Utility AI 决策】----
            pick, _ps = self._utility_pick([
                ("execution", lambda: (72 if (can_execution and dist < 160) else 0)),
                ("backstep", lambda: (66 if (dist < 140 and self.boss_backstep_cd <= 0) else 0)),
                ("salvo", lambda: (62 if (dist > 130 and self.boss_salvo_cd <= 0) else 0)),
                ("shoot", lambda: (55 if (dist > 130 and self.boss_shoot_cd <= 0) else 0)),
                ("barrage", lambda: (45 + (22 if hp_ratio <= 0.5 else 0)) if self.boss_barrage_cd <= 0 else 0),
                ("smoke", lambda: (34 if (dist > 100 and self.boss_smoke_cd <= 0) else 0)),
                ("grenade", lambda: (40 if (120 < dist < 350 and self.boss_grenade_cd <= 0) else 0)),
                ("teleport", lambda: (30 if (hp_ratio < 0.6 and self.boss_teleport_cd <= 0) else 0)),
                ("summon", lambda: (38 if (hp_ratio < 0.5 and self.boss_summon_cd <= 0) else 0)),
                ("dash", lambda: (36 if (90 < dist < 240 and self.boss_dash_cd <= 0) else 0)),
                ("move", lambda: 24),
            ])
            if pick == "execution":
                self.boss_is_executing = True
                self.boss_execution_windup = 1.0
                self.boss_execution_cd = 13.0
                return None
            elif pick == "backstep":
                self.boss_backstep_cd = 6.0
                back_dx = self.x - player_x
                back_dy = self.y - player_y
                b_dist = math.hypot(back_dx, back_dy)
                if b_dist > 0:
                    self.x += (back_dx / b_dist) * 90
                    self.y += (back_dy / b_dist) * 90
                return None
            elif pick == "salvo":
                self.boss_salvo_cd = 2.8
                # 连续3发子弹
                for _ in range(3):
                    return {
                        "x": self.x, "y": self.y,
                        "target_x": player_x, "target_y": player_y,
                        "damage": int(self.damage * 0.55)
                    }
            elif pick == "shoot":
                self.boss_shoot_cd = 1.6
                return {
                    "x": self.x, "y": self.y,
                    "target_x": player_x, "target_y": player_y,
                    "damage": int(self.damage * 0.65)
                }
            elif pick == "barrage":
                self.boss_barrage_cd = 7.0
                return "boss_barrage"
            elif pick == "smoke":
                self.boss_smoke_cd = 10.0
                return "boss_smoke"
            elif pick == "grenade":
                self.boss_grenade_cd = 6.0
                return "boss_grenade"
            elif pick == "teleport":
                self.boss_teleport_cd = 12.0
                angle = math.atan2(player_y - self.y, player_x - self.x) + math.radians(random.choice([120, -120]))
                teleport_dist = 150
                self.x = player_x + math.cos(angle) * teleport_dist
                self.y = player_y + math.sin(angle) * teleport_dist
                return "boss_teleport"
            elif pick == "summon":
                self.boss_summon_cd = 18.0
                return "boss_summon_ranged"
            elif pick == "dash":
                self.is_dashing = True
                self.dash_target_x = player_x
                self.dash_target_y = player_y
                self.dash_speed = 8.2
                self.dash_timer = 0.42
                self.boss_dash_cd = 5.0
                return None

            # 普通移动
            if dist > 0:
                self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        elif self.enemy_type == EnemyType.BOSS_MUTANT:
            # ----变异体-深渊：高伤害连招Boss----
            # 连招状态机
            if not hasattr(self, 'combo_state'):
                self.combo_state = 0
                self.combo_timer = 0
            if self.combo_timer > 0:
                self.combo_timer -= dt

            # 连招进行中：连续高伤害攻击（优先于新决策）
            if self.combo_state > 0 and self.combo_timer > 0:
                if self.combo_state == 1 and self.combo_timer < 2.0:
                    self.combo_state = 2
                    return "mutant_combo_hit"  # 第一击：上挑
                elif self.combo_state == 2 and self.combo_timer < 1.5:
                    self.combo_state = 3
                    d = math.hypot(player_x - self.x, player_y - self.y)
                    if d > 0:
                        self.x += (player_x - self.x) / d * 60
                        self.y += (player_y - self.y) / d * 60
                    return "mutant_combo_hit"  # 第二击：横斩
                elif self.combo_state == 3 and self.combo_timer < 0.8:
                    self.combo_state = 0
                    return "mutant_combo_finisher"  # 终结：下砸AOE
                return None

            # 【Utility AI 决策】变异体：处决连招/冲刺/酸液/追击
            pick, _ps = self._utility_pick([
                ("execution", lambda: (75 if (can_execution and dist < 180) else 0)),
                ("dash", lambda: (63 if (dist > 150 and self.boss_dash_cd <= 0) else 0)),
                ("acid", lambda: (58 if (dist < 300 and self.boss_shoot_cd <= 0) else 0)),
                ("move", lambda: 28),
            ])
            if pick == "execution":
                self.boss_is_executing = True
                self.boss_execution_windup = 0.8
                self.boss_execution_cd = 15.0
                self.combo_state = 1
                self.combo_timer = 2.5
                return None
            elif pick == "dash":
                self.is_dashing = True
                self.dash_target_x = player_x
                self.dash_target_y = player_y
                self.dash_speed = 10.0
                self.dash_timer = 0.35
                self.boss_dash_cd = 4.0
                return None
            elif pick == "acid":
                self.boss_shoot_cd = 3.0
                results = []
                base_angle = math.atan2(player_y - self.y, player_x - self.x)
                for offset in [-0.3, -0.15, 0, 0.15, 0.3]:
                    angle = base_angle + offset
                    results.append({
                        "x": self.x, "y": self.y,
                        "target_x": self.x + math.cos(angle) * 300,
                        "target_y": self.y + math.sin(angle) * 300,
                        "damage": int(self.damage * 0.5),
                        "applies_corrosion": True,
                    })
                return results

            # 【狂暴】血量低于50%时攻速移速提升
            if hp_ratio < 0.5:
                self.speed = getattr(self, 'base_speed', self.speed) * 1.3
                if not hasattr(self, 'base_speed'):
                    self.base_speed = self.speed / 1.3

            # 普通移动
            if dist > 0:
                self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        elif self.enemy_type == EnemyType.BOSS_QUEEN:
            # ----尸潮女王：召唤+控制Boss【Utility AI 决策】----
            pick, _ps = self._utility_pick([
                ("summon", lambda: (58 if (self.boss_summon_cd <= 0) else 0)),
                ("mind", lambda: (50 if (dist < 250 and self.boss_smoke_cd <= 0) else 0)),
                ("tentacle", lambda: (46 if (dist < 200 and self.boss_ground_slam_cd <= 0) else 0)),
                ("poison", lambda: (40 if (dist > 100 and self.boss_grenade_cd <= 0) else 0)),
                ("execution", lambda: (74 if (can_execution and dist < 200) else 0)),
                ("move", lambda: 26),
            ])
            if pick == "summon":
                self.boss_summon_cd = getattr(self, "summon_interval", 8.0)
                return "queen_summon"
            elif pick == "mind":
                self.boss_smoke_cd = 12.0
                return "queen_mind_control"
            elif pick == "tentacle":
                self.boss_ground_slam_cd = 5.0
                return "queen_tentacle"
            elif pick == "poison":
                self.boss_grenade_cd = 7.0
                return "queen_poison_cloud"
            elif pick == "execution":
                self.boss_is_executing = True
                self.boss_execution_windup = 1.2
                self.boss_execution_cd = 18.0
                return None

            # 女王移动较慢，保持中距离
            if dist < 150:
                if dist > 0:
                    self.x -= (player_x - self.x) / dist * self.speed * 0.5 * self._buff_speed_mult * dt * 60
                    self.y -= (player_y - self.y) / dist * self.speed * 0.5 * self._buff_speed_mult * dt * 60
            elif dist > 300:
                if dist > 0:
                    self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                    self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        elif self.enemy_type == EnemyType.BOSS_TITAN:
            # ----泰坦：巨型坦克Boss【Utility AI 决策】----
            pick, _ps = self._utility_pick([
                ("stomp", lambda: (62 if (dist < 150 and self.boss_ground_slam_cd <= 0) else 0)),
                ("boulder", lambda: (52 if (dist > 200 and self.boss_shoot_cd <= 0) else 0)),
                ("charge", lambda: (57 if (dist > 250 and self.boss_charge_cd <= 0) else 0)),
                ("execution", lambda: (76 if (can_execution and dist < 200) else 0)),
                ("move", lambda: 28),
            ])
            if pick == "stomp":
                self.boss_ground_slam_cd = 6.0
                return "titan_stomp"
            elif pick == "boulder":
                self.boss_shoot_cd = 4.0
                return {
                    "x": self.x, "y": self.y,
                    "target_x": player_x, "target_y": player_y,
                    "damage": int(self.damage * 0.8),
                    "is_boulder": True,
                }
            elif pick == "charge":
                self.boss_charge_cd = 10.0
                self.boss_is_charging = True
                self.boss_charge_timer = 1.2
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.boss_charge_dir = ((player_x - self.x) / d, (player_y - self.y) / d)
                return None
            elif pick == "execution":
                self.boss_is_executing = True
                self.boss_execution_windup = 1.5
                self.boss_execution_cd = 20.0
                return None

            # 普通移动（缓慢但坚定）
            if dist > 0:
                self.x += (player_x - self.x) / dist * self.speed * self._buff_speed_mult * dt * 60
                self.y += (player_y - self.y) / dist * self.speed * self._buff_speed_mult * dt * 60

        return None

    def _special_ability(self, dt, player_x, player_y, dist):
        """特种僵尸特色能力，返回None表示继续普通逻辑，返回字符串/dict表示触发技能"""
        # 更新通用CD
        if self.special_ability_cd > 0:
            self.special_ability_cd -= dt
        if self.tank_slam_cd > 0:
            self.tank_slam_cd -= dt
        if self.ranged_burst_cd > 0:
            self.ranged_burst_cd -= dt
        if self.phantom_teleport_cd > 0:
            self.phantom_teleport_cd -= dt
        if self.shield_charge_cd > 0:
            self.shield_charge_cd -= dt
        if self.healer_wave_cd > 0:
            self.healer_wave_cd -= dt

        # 快速僵尸：冲刺攻击（前摇后突然加速冲刺，位移由game.py在前摇结束后执行）
        if self.enemy_type == EnemyType.ZOMBIE_FAST:
            if 60 < dist < 200 and self.fast_dash_ready and random.random() < 0.03:
                self.fast_dash_ready = False
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.fast_dash_dir = ((player_x - self.x) / d, (player_y - self.y) / d)
                else:
                    self.fast_dash_dir = (1, 0)
                return "fast_dash"
            if dist > 250:
                self.fast_dash_ready = True

        # 坦克僵尸：重击AOE（近身时范围伤害）
        elif self.enemy_type == EnemyType.ZOMBIE_TANK:
            if dist < 80 and self.tank_slam_cd <= 0 and random.random() < 0.025:
                self.tank_slam_cd = 4.0
                return "tank_slam"

        # 远程僵尸：散射连射
        elif self.enemy_type == EnemyType.ZOMBIE_RANGED:
            if dist < 280 and self.ranged_burst_cd <= 0 and random.random() < 0.015:
                self.ranged_burst_cd = 5.0
                # 三连发散射
                results = []
                base_angle = math.atan2(player_y - self.y, player_x - self.x)
                for offset in [-0.2, 0, 0.2]:
                    angle = base_angle + offset
                    results.append({
                        "x": self.x, "y": self.y,
                        "target_x": self.x + math.cos(angle) * 300,
                        "target_y": self.y + math.sin(angle) * 300,
                        "damage": int(self.damage * 0.6)
                    })
                return results

        # 分裂僵尸：死亡时溅射（在take_damage中处理，这里添加分裂前兆）
        elif self.enemy_type == EnemyType.ZOMBIE_SPLITTER:
            if self.hp < self.max_hp * 0.3 and self.special_ability_cd <= 0:
                self.special_ability_cd = 3.0
                # 分裂前兆：加速
                pass

        # 治疗僵尸：治疗波（范围大量治疗）
        elif self.enemy_type == EnemyType.ZOMBIE_HEALER:
            if self.healer_wave_cd <= 0 and random.random() < 0.01:
                self.healer_wave_cd = 8.0
                return "healer_wave"

        # 幻影僵尸：瞬移到玩家附近
        elif self.enemy_type == EnemyType.ZOMBIE_PHANTOM:
            if dist > 200 and self.phantom_teleport_cd <= 0 and random.random() < 0.015:
                self.phantom_teleport_cd = 10.0
                angle = random.uniform(0, math.pi * 2)
                teleport_dist = random.randint(80, 150)
                self.x = player_x + math.cos(angle) * teleport_dist
                self.y = player_y + math.sin(angle) * teleport_dist
                return "phantom_teleport"

        # 盾兵：冲锋盾击
        elif self.enemy_type == EnemyType.ZOMBIE_SHIELD:
            if 100 < dist < 300 and self.shield_charge_cd <= 0 and random.random() < 0.02:
                self.shield_charge_cd = 6.0
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.x += (player_x - self.x) / d * 100
                    self.y += (player_y - self.y) / d * 100
                return "shield_charge"

        # 吐酸僵尸：远程酸液弹（已通过is_ranged处理，这里添加腐蚀溅射）
        elif self.enemy_type == EnemyType.ZOMBIE_SPITTER:
            pass  # 腐蚀效果在命中时由game.py处理

        # 跳跃僵尸：远距离扑击
        elif self.enemy_type == EnemyType.ZOMBIE_LEAPER:
            if 100 < dist < 250 and self.special_ability_cd <= 0 and random.random() < getattr(self, "leap_chance", 0.15):
                self.special_ability_cd = 4.0
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.leap_dir = ((player_x - self.x) / d, (player_y - self.y) / d)
                else:
                    self.leap_dir = (1, 0)
                return "leaper_strike"

        # 食尸者：吞噬尸体变强（在game.py中检测尸体）
        elif self.enemy_type == EnemyType.ZOMBIE_CORPSE_EATER:
            pass

        # 怨灵：穿墙+恐惧光环
        elif self.enemy_type == EnemyType.ZOMBIE_WRAITH:
            if dist < 100 and self.special_ability_cd <= 0 and random.random() < getattr(self, "fear_chance", 0.2):
                self.special_ability_cd = 6.0
                return "wraith_fear"

        # === 精英怪 ===
        # 精英蛮兵：重击
        elif self.enemy_type == EnemyType.ELITE_BRUTE:
            if dist < 80 and self.special_ability_cd <= 0 and random.random() < getattr(self, "heavy_attack_chance", 0.3):
                self.special_ability_cd = 3.5
                return "elite_heavy_slam"

        # 精英刺客：高速冲刺
        elif self.enemy_type == EnemyType.ELITE_ASSASSIN:
            if 80 < dist < 300 and self.special_ability_cd <= 0 and random.random() < getattr(self, "dash_chance", 0.25):
                self.special_ability_cd = 4.0
                d = math.hypot(player_x - self.x, player_y - self.y)
                if d > 0:
                    self.x += (player_x - self.x) / d * 150
                    self.y += (player_y - self.y) / d * 150
                return "elite_assassin_dash"

        # 精英术士：诅咒弹（已通过is_ranged处理）
        elif self.enemy_type == EnemyType.ELITE_SORCERER:
            pass

        # 精英守卫：治疗光环（在game.py中范围处理）
        elif self.enemy_type == EnemyType.ELITE_GUARDIAN:
            pass

        return None

    def _get_windup_config(self, attack_type):
        """获取特殊攻击的前摇配置，返回None表示不需要前摇"""
        # 只处理字符串类型的攻击类型，列表等不可哈希类型直接返回None
        if not isinstance(attack_type, str):
            return None
        windup_configs = {
            "tank_slam": {"duration": 0.8, "radius": 80},
            "elite_heavy_slam": {"duration": 1.0, "radius": 80},
            "wraith_fear": {"duration": 0.6, "radius": 120},
            "healer_wave": {"duration": 1.0, "radius": 100},
            "leaper_strike": {"duration": 0.5, "radius": 30},
            "fast_dash": {"duration": 0.4, "radius": 40},
        }
        return windup_configs.get(attack_type)

    def _ranged_attack(self, dt, player_x, player_y, dist):
        if self.attack_timer > 0:
            self.attack_timer -= dt
            return None
        self.attack_timer = getattr(self, "attack_cooldown", 2.0)
        return {
            "x": self.x, "y": self.y,
            "target_x": player_x, "target_y": player_y,
            "damage": self.damage
        }

    def try_throw(self, dt, player_x, player_y, dist):
        """尝试投掷道具，返回投掷物数据或None"""
        if not self.can_throw:
            return None
        if self.throw_cd > 0:
            self.throw_cd -= dt
            return None
        # 距离在150-400之间才投掷
        if dist < 150 or dist > 450:
            return None
        # 投掷概率
        if random.random() > 0.5:
            self.throw_cd = random.uniform(2.0, 3.5)
            return None
        self.throw_cd = random.uniform(3.0, 6.0)
        
        # 根据怪物类型选择投掷物
        throw_type = "rock"  # 默认石块
        if self.enemy_type == EnemyType.ZOMBIE_SPITTER:
            throw_type = "acid"  # 酸液瓶
        elif self.enemy_type == EnemyType.ELITE_SORCERER:
            throw_type = random.choice(["fire", "acid", "curse"])
        elif getattr(self, "is_boss", False):
            throw_type = random.choice(["fire", "rock", "acid"])
        elif self.enemy_type == EnemyType.ZOMBIE_RANGED:
            throw_type = random.choice(["rock", "fire"])
        
        return {
            "type": throw_type,
            "x": self.x, "y": self.y,
            "target_x": player_x, "target_y": player_y,
            "damage": self.damage * 1.5,
            "owner": "boss" if getattr(self, "is_boss", False) else "enemy_minion",
        }

    def apply_buff(self, buff_type, duration=None, stacks=1):
        """应用buff，考虑控制抗性"""
        from buff import BuffType
        # 控制类debuff列表
        control_debuffs = {
            BuffType.FREEZE, BuffType.STUN, BuffType.FEAR,
            BuffType.SLOW, BuffType.FRACTURE, BuffType.WEAKEN,
        }
        if buff_type in control_debuffs and self.control_resistance > 0:
            if random.random() < self.control_resistance:
                return False  # 免疫
            # 非免疫时缩短持续时间
            if duration is not None:
                duration = duration * (1 - self.control_resistance * 0.5)
        self.buff_manager.add_buff(buff_type, duration, stacks)
        return True

    def _update_boss_ai(self, dt, player_x, player_y, player):
        """Boss智能AI：根据血量/距离/玩家状态选择行为"""
        if not self.alive:
            return
        dx = player_x - self.x
        dy = player_y - self.y
        dist = math.hypot(dx, dy)
        hp_ratio = self.hp / self.max_hp if self.max_hp > 0 else 1

        # 初始化Boss AI状态
        if not hasattr(self, 'boss_ai_state'):
            self.boss_ai_state = 'chase'  # chase / flank / rage / retreat
            self.boss_ai_timer = 0
            self.boss_rage_triggered = False

        self.boss_ai_timer -= dt

        # 低血量狂暴模式
        if hp_ratio < 0.3 and not self.boss_rage_triggered:
            self.boss_rage_triggered = True
            self.boss_ai_state = 'rage'
            self.speed *= 1.3
            self.damage *= 1.5
            if hasattr(self, 'color'):
                self.original_color = self.color
                self.color = (200, 30, 30)

        # 状态切换逻辑
        if self.boss_ai_timer <= 0:
            if self.boss_ai_state == 'rage':
                # 狂暴模式：持续追击，偶尔冲撞
                self.boss_ai_state = 'rage'
                self.boss_ai_timer = random.uniform(1.5, 3.0)
                if random.random() < 0.4 and dist > 100:
                    # 冲撞准备
                    self.boss_dash_cd = 0.1  # 即将冲撞
            elif dist < 60:
                # 近身：后退拉开距离
                self.boss_ai_state = 'retreat'
                self.boss_ai_timer = random.uniform(0.5, 1.2)
            elif dist > 300:
                # 远距离：快速追击
                self.boss_ai_state = 'chase'
                self.boss_ai_timer = random.uniform(2.0, 4.0)
            else:
                # 中距离：随机选择侧翼包抄或远程攻击
                choice = random.random()
                if choice < 0.4:
                    self.boss_ai_state = 'flank'
                    self.boss_ai_timer = random.uniform(1.5, 3.0)
                    self.flank_direction = random.choice([-1, 1])
                elif choice < 0.7:
                    self.boss_ai_state = 'chase'
                    self.boss_ai_timer = random.uniform(1.5, 3.0)
                else:
                    self.boss_ai_state = 'ranged'
                    self.boss_ai_timer = random.uniform(1.0, 2.0)
                    self.boss_shoot_cd = 0.1  # 即将远程攻击

        # 执行AI状态
        if self.boss_ai_state == 'retreat' and dist < 100:
            # 后退：向玩家反方向移动
            if dist > 0:
                self.x -= (dx / dist) * self.speed * 1.2 * dt * 60
                self.y -= (dy / dist) * self.speed * 1.2 * dt * 60
        elif self.boss_ai_state == 'flank':
            # 侧翼包抄：垂直于玩家方向移动
            if dist > 0:
                perp_x = -dy / dist
                perp_y = dx / dist
                self.x += perp_x * self.flank_direction * self.speed * 0.9 * dt * 60
                self.y += perp_y * self.flank_direction * self.speed * 0.9 * dt * 60
                # 同时缓慢接近
                self.x += (dx / dist) * self.speed * 0.3 * dt * 60
                self.y += (dy / dist) * self.speed * 0.3 * dt * 60
        # chase/rage/ranged 状态由正常的Enemy.update移动逻辑处理

    def take_damage(self, damage, damage_type="normal"):
        # DOT伤害跳过特殊防御机制
        if damage_type != "dot":
            # 盾兵正面减伤
            if getattr(self, "is_shield", False) and getattr(self, "front_reduction", 0) > 0:
                # 简化：50%几率触发正面减伤
                if random.random() < 0.5:
                    damage *= (1 - self.front_reduction)

            # 爬行者闪避
            if getattr(self, "is_crawler", False) and getattr(self, "dodge_chance", 0) > 0:
                if random.random() < self.dodge_chance:
                    return False  # 闪避了

        # Buff系统受伤倍率（燃烧加深伤害等）
        damage *= self.buff_manager.get_damage_taken_mult()
        # Mod 钩子：伤害结算，可修改最终伤害
        try:
            import mod_loader
            for _v in reversed(mod_loader.trigger_hook("on_damage_dealt", self, damage, damage_type, None)):
                if isinstance(_v, (int, float)):
                    damage = _v
                    break
        except Exception:
            pass
        self.hp -= damage
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def knockdown(self, duration=2.0):
        self.knockdown_timer = duration

    def get_rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size, 
                          self.size * 2, self.size * 2)

    def draw(self, screen, camera_x, camera_y, font, scale=1.0, assets=None, player_x=None, player_y=None):
        px = int((self.x - camera_x) * scale)
        py = int((self.y - camera_y) * scale)
        s = max(2, int(self.size * scale))

        # 特殊僵尸散发幽光
        special_glow = None
        if getattr(self, "is_exploder", False):
            special_glow = (255, 100, 30)  # 爆炸僵尸 - 橙红幽光
        elif getattr(self, "is_healer", False):
            special_glow = (80, 255, 120)  # 治疗僵尸 - 绿色幽光
        elif getattr(self, "is_phantom", False):
            special_glow = (180, 100, 255)  # 幻影僵尸 - 紫色幽光
        elif getattr(self, "is_shield", False):
            special_glow = (150, 150, 170)  # 盾兵 - 灰蓝幽光
        elif getattr(self, "is_splitter", False):
            special_glow = (255, 80, 80)  # 分裂者 - 红色幽光
        elif getattr(self, "is_crawler", False):
            special_glow = (100, 200, 100)  # 爬行者 - 暗绿幽光
        elif getattr(self, "is_boss", False):
            special_glow = (200, 50, 200)  # Boss - 紫红幽光
        if special_glow:
            pulse = abs(math.sin(pygame.time.get_ticks() / 400.0)) * 0.4 + 0.6
            glow_r = s + 12
            glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*special_glow[:3], int(50 * pulse)), (glow_r, glow_r), glow_r)
            pygame.draw.circle(glow_surf, (*special_glow[:3], int(25 * pulse)), (glow_r, glow_r), glow_r + 5)
            screen.blit(glow_surf, (px - glow_r, py - glow_r))

        # 幻影僵尸隐身效果
        alpha = 255
        if getattr(self, "is_phantom", False) and self.invisible:
            alpha = 60
            if random.random() < 0.3:  # 偶尔闪烁可见
                alpha = 180

        # 爆炸僵尸倒计时闪烁
        if getattr(self, "is_exploder", False) and self.is_exploding:
            flash = abs(math.sin(pygame.time.get_ticks() / 100))
            if flash > 0.5:
                color = RED
            else:
                color = YELLOW
        else:
            color = self.color

        # === 优先使用assets图片绘制 ===
        img_key = None
        if hasattr(self, 'enemy_type'):
            et = self.enemy_type
            type_map = {
                EnemyType.ZOMBIE_NORMAL: "zombie_normal",
                EnemyType.ZOMBIE_FAST: "zombie_fast",
                EnemyType.ZOMBIE_TANK: "zombie_tank",
                EnemyType.ZOMBIE_RANGED: "zombie_ranged",
                EnemyType.ZOMBIE_EXPLODER: "zombie_exploder",
                EnemyType.ZOMBIE_CRAWLER: "zombie_crawler",
                EnemyType.ZOMBIE_SPLITTER: "zombie_splitter",
                EnemyType.ZOMBIE_SHIELD: "zombie_shield",
                EnemyType.ZOMBIE_HEALER: "zombie_healer",
                EnemyType.ZOMBIE_PHANTOM: "zombie_phantom",
                EnemyType.ZOMBIE_SPITTER: "zombie_spitter",
                EnemyType.ZOMBIE_LEAPER: "zombie_leaper",
                EnemyType.ZOMBIE_CORPSE_EATER: "zombie_corpse_eater",
                EnemyType.ZOMBIE_WRAITH: "zombie_wraith",
                EnemyType.BOSS_LONG: "boss_long",
                EnemyType.BOSS_XIANG: "boss_xiang",
                EnemyType.BOSS_MUTANT: "boss_mutant",
                EnemyType.BOSS_QUEEN: "boss_queen",
                EnemyType.BOSS_TITAN: "boss_titan",
                EnemyType.BOSS_WANG: "boss_wang",
                EnemyType.ELITE_BRUTE: "elite_brute",
                EnemyType.ELITE_ASSASSIN: "elite_assassin",
                EnemyType.ELITE_SORCERER: "elite_sorcerer",
                EnemyType.ELITE_GUARDIAN: "elite_guardian",
            }
            img_key = type_map.get(et)

        use_image = assets is not None and img_key is not None and assets.has_image(img_key)

        if self.knockdown_timer > 0:
            pygame.draw.ellipse(screen, DARK_GRAY, 
                              (px - s, py - s // 2, s * 2, s))
        elif use_image:
            # 使用assets图片绘制
            img = assets.get_image(img_key, s * 2, s * 2)
            if alpha < 255:
                img.set_alpha(alpha)
            screen.blit(img, (px - s, py - s))
        else:
            # 绘制身体（几何占位）
            body_surf = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
            pygame.draw.circle(body_surf, (*color[:3], alpha), (s, s), s)
            screen.blit(body_surf, (px - s, py - s))

            # 眼睛
            if alpha > 100:
                eye_offset = max(2, int(5 * scale))
                pygame.draw.circle(screen, RED, (px - eye_offset, py - max(1, int(3 * scale))), max(1, int(3 * scale)))
                pygame.draw.circle(screen, RED, (px + eye_offset, py - max(1, int(3 * scale))), max(1, int(3 * scale)))

        # 特殊标识
        if getattr(self, "is_exploder", False) and not self.is_exploding:
            # 爆炸标识
            pygame.draw.circle(screen, RUST, (px, py - s - 5), max(2, int(3 * scale)))
        if getattr(self, "is_healer", False):
            # 治疗光环
            heal_pulse = abs(math.sin(pygame.time.get_ticks() / 300)) * 0.5 + 0.5
            heal_surf = pygame.Surface((int(self.heal_radius * 2 * scale), int(self.heal_radius * 2 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(heal_surf, (*GREEN[:3], int(30 * heal_pulse)), 
                             (int(self.heal_radius * scale), int(self.heal_radius * scale)), 
                             int(self.heal_radius * scale))
            screen.blit(heal_surf, (px - int(self.heal_radius * scale), py - int(self.heal_radius * scale)))
        if getattr(self, "is_shield", False):
            # 盾牌标识
            pygame.draw.rect(screen, CHARCOAL, (px - s - 2, py - s - 2, s * 2 + 4, s * 2 + 4), max(1, int(2 * scale)))
        if getattr(self, "is_crawler", False):
            # 爬行者更小
            pass  # 已经在size中体现
        if getattr(self, "is_splitter", False):
            # 分裂标识
            pygame.draw.circle(screen, BLOOD_RED, (px, py + s + 5), max(2, int(3 * scale)))

        if self.hp < self.max_hp:
            bar_width = s * 2
            bar_height = max(2, int(4 * scale))
            hp_ratio = self.hp / self.max_hp
            pygame.draw.rect(screen, RED, (px - bar_width // 2, py - s - max(4, int(8 * scale)), 
                                         bar_width, bar_height))
            pygame.draw.rect(screen, GREEN, (px - bar_width // 2, py - s - max(4, int(8 * scale)), 
                                           int(bar_width * hp_ratio), bar_height))

        if getattr(self, "is_boss", False):
            name_text = font.render(self.name, True, YELLOW)
            name_rect = name_text.get_rect(center=(px, py - s - max(10, int(20 * scale))))
            screen.blit(name_text, name_rect)
        if getattr(self, "is_boss", False) and self.enemy_type == EnemyType.BOSS_LONG and self.boss_hold_shield:
            # 龙某举盾特效
            shield_s = int(35 * scale)
            pygame.draw.circle(screen, BLUE, (px, py), shield_s, max(2,int(3*scale)))
        # ===== 王某：手持武器（枪械形态 / 死神镰刀形态，双形态可见）=====
        if getattr(self, "enemy_type", None) == EnemyType.BOSS_WANG and self.max_hp > 0:
            self._draw_wang_weapon(screen, px, py, s, scale, player_x, player_y)
        # =========处决前摇红色闪烁警告【新增】=========
        if getattr(self,"boss_is_executing",False):
            flash = abs(math.sin(pygame.time.get_ticks() / 80))
            r = int(220*flash)
            g = int(30*flash)
            b = int(30*flash)
            pygame.draw.circle(screen,(r,g,b),(px,py),int((s+25)*scale),max(3,int(4*scale)))

    def _draw_wang_weapon(self, screen, px, py, s, scale, player_x=None, player_y=None):
        """王某手持武器渲染：血量>50% 枪械形态；<=50% 死神镰刀形态（均朝玩家方向）"""
        import math as _m
        _ang = 0.0
        if player_x is not None and player_y is not None and (player_x != self.x or player_y != self.y):
            _ang = _m.atan2(player_y - self.y, player_x - self.x)
        _scythe_form = (self.hp / self.max_hp) <= 0.5
        _ticks = pygame.time.get_ticks()

        if _scythe_form:
            # ===== 死神镰刀形态：紫刃大弧 + 长柄，幽光脉动 =====
            _pulse = abs(_m.sin(_ticks / 300.0)) * 0.5 + 0.5
            _blade_r = int((s * 1.9 + 10) * scale)
            _g = pygame.Surface((_blade_r * 2 + 16, _blade_r * 2 + 16), pygame.SRCALPHA)
            _gc = _blade_r + 8
            # 刀刃弧（指向玩家方向）
            pygame.draw.arc(_g, (216, 140, 250, 200), (6, 6, _blade_r * 2, _blade_r * 2),
                            _ang - 2.1, _ang + 0.9, max(3, int(7 * scale)))
            pygame.draw.arc(_g, (150, 60, 210, 240), (6, 6, _blade_r * 2, _blade_r * 2),
                            _ang - 1.9, _ang + 0.7, max(2, int(4 * scale)))
            # 外发光
            pygame.draw.arc(_g, (120, 40, 190, int(70 * _pulse)), (2, 2, _blade_r * 2 + 8, _blade_r * 2 + 8),
                            _ang - 2.2, _ang + 1.0, max(4, int(10 * scale)))
            screen.blit(_g, (px - _gc, py - _gc))
            # 镰刀柄（从王某朝玩家方向延伸）
            _hl = int((s + 16) * scale)
            _hx = px + _m.cos(_ang) * _hl
            _hy = py + _m.sin(_ang) * _hl
            pygame.draw.line(screen, (92, 74, 54), (px, py), (_hx, _hy), max(3, int(5 * scale)))
            pygame.draw.line(screen, (128, 104, 74), (px, py), (_hx, _hy), max(1, int(2 * scale)))
            # 柄端银环
            pygame.draw.circle(screen, (170, 174, 190), (int(_hx), int(_hy)), max(3, int(5 * scale)))
        else:
            # ===== 枪械形态：暗色步枪指向玩家 =====
            _gl = int((s + 20) * scale)
            _gx = px + _m.cos(_ang) * _gl
            _gy = py + _m.sin(_ang) * _gl
            # 枪身
            _bw = max(3, int(5 * scale))
            pygame.draw.line(screen, (58, 60, 74), (px, py), (_gx, _gy), _bw)
            # 枪管（细长）
            _bx = px + _m.cos(_ang) * (_gl + int(10 * scale))
            _by = py + _m.sin(_ang) * (_gl + int(10 * scale))
            pygame.draw.line(screen, (36, 38, 50), (_gx, _gy), (_bx, _by), max(2, int(3 * scale)))
            # 金饰
            pygame.draw.line(screen, (206, 168, 78), (px, py), (_gx, _gy), max(1, int(2 * scale)))
            # 枪口火光（开火时闪烁）
            _flash = abs(_m.sin(_ticks / 120.0))
            if _flash > 0.55:
                _fglow = pygame.Surface((int(26 * scale) * 2, int(26 * scale) * 2), pygame.SRCALPHA)
                _fc = int(26 * scale)
                pygame.draw.circle(_fglow, (255, 170, 60, int(120 * _flash)), (_fc, _fc), _fc)
                pygame.draw.circle(_fglow, (255, 230, 140, int(200 * _flash)), (_fc, _fc), int(10 * scale))
                screen.blit(_fglow, (int(_bx) - _fc, int(_by) - _fc))
            # 瞄具小点
            pygame.draw.circle(screen, (120, 200, 220), (int((px + _gx) / 2), int((py + _gy) / 2)), max(1, int(2 * scale)))
