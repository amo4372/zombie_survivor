# -*- coding: utf-8 -*-
"""ZombieTreeAI —— 无训练硬编程僵尸 AI（决策树实现）

与旧 RLEnemyAI 完全同构的接入接口：
    decide(enemy, player, world, teammates) -> (vx, vy, skill)
    ready 恒为 True（无需模型/无需训练）
    flush_batch() 空实现（决策树即时决策，无批推理）

设计要点（仔细阅读 entities_pkg/enemy.py 僵尸逻辑后编写）：
- 技能码语义与 _rl_cast_skill 完全一致：
    1=远程开火  2=冲刺  3=召唤  4=范围咆哮/镰刀  5=投掷
    6=锁定必中  7=恶心控制  8=特种召唤  9=回血
- Boss 技能 CD 由本模块自洽递减（RL 时代 CD 只设不降，本模块修复）
- 任何异常 → (None, None, False)，游戏回退原生规则 AI（保底不崩）
"""
import math
import time

from .decision_tree import (Selector, Sequence, Condition, Action)


def _now():
    return time.perf_counter()


class ZombieTreeAI:
    def __init__(self, **kwargs):
        self.stats = {"decisions": 0, "skill_hist": {}, "tree_hits": {}}
        self._last_tick = {}   # id(enemy) -> 上次决策时间（boss CD 递减用）
        self._trees = {}       # 惰性构建：id(enemy) -> 决策树

    @property
    def ready(self):
        return True

    # ==================== 上下文构建 ====================
    def _build_ctx(self, enemy, player, world, teammates):
        dx = player.x - enemy.x
        dy = player.y - enemy.y
        dist = math.hypot(dx, dy)
        if dist > 1e-6:
            nx, ny = dx / dist, dy / dist
        else:
            nx, ny = 0.0, 0.0
        # v2.2.5 强化：稳定包抄扇区（按 id 派生，同一只怪方向恒定）+ 玩家弹幕感知
        pid = (id(enemy) >> 4) & 7
        pz = []
        try:
            if world is not None:
                _projs = getattr(world, "projectiles", None) or []
                for _pr in _projs:
                    if getattr(_pr, "alive", False):
                        pz.append(_pr)
        except Exception:
            pass
        return {
            "enemy": enemy, "player": player, "world": world,
            "teammates": teammates or [],
            "dist": dist, "nx": nx, "ny": ny,
            "pid": pid, "pz": pz,
            "vx": 0.0, "vy": 0.0, "skill": 0,
            "_tree": "unknown",
            # v2.5.4 强化：玩家状态感知（血量比/残血）
            "player_hp_ratio": max(0.0, min(1.0, getattr(player, 'hp', 100) / max(1, getattr(player, 'max_hp', 100)))),
        }

    # ==================== 决策入口（与 RLEnemyAI.decide 同构） ====================
    def decide(self, enemy, player, world=None, teammates=None):
        """返回 (vx, vy, skill)；异常/不可用 → (None, None, False) 回退原 AI"""
        try:
            if enemy is None or player is None:
                return None, None, False
            if not getattr(enemy, "alive", True):
                return None, None, False
            ctx = self._build_ctx(enemy, player, world, teammates)
            # Boss 技能 CD 递减（自洽，不等原生状态机）
            self._tick_boss_cds(enemy)
            tree = self._get_tree(enemy)
            ctx["_tree"] = tree["name"]
            tree["root"].tick(ctx)
            self.stats["decisions"] += 1
            self.stats["tree_hits"][tree["name"]] = self.stats["tree_hits"].get(tree["name"], 0) + 1
            if ctx["skill"]:
                self.stats["skill_hist"][ctx["skill"]] = self.stats["skill_hist"].get(ctx["skill"], 0) + 1
            return ctx["vx"], ctx["vy"], ctx["skill"]
        except Exception:
            return None, None, False

    def flush_batch(self, world=None, enemies=None, players=None):
        """决策树即时决策，无需批处理（保持接口兼容）"""
        return None

    # ==================== Boss CD 递减（时间差自洽） ====================
    def _tick_boss_cds(self, enemy):
        now = _now()
        last = self._last_tick.get(id(enemy))
        self._last_tick[id(enemy)] = now
        if last is None:
            return
        dt = min(max(now - last, 0.0), 0.1)
        if dt <= 0:
            return
        for attr in ("boss_dash_cd", "boss_aoe_cd", "boss_lock_cd", "boss_debuff_cd",
                     "boss_elite_cd", "boss_heal_cd", "boss_summon_cd", "boss_shoot_cd",
                     "boss_grenade_cd", "boss_shield_cd", "boss_execution_cd", "boss_salvo_cd",
                     "boss_backstep_cd", "boss_charge_cd", "boss_regen_cd", "boss_ground_slam_cd",
                     "boss_barrage_cd", "boss_smoke_cd", "boss_teleport_cd", "throw_cd",
                     "skill_windup"):
            try:
                cur = getattr(enemy, attr, 0.0) or 0.0
                if cur > 0:
                    setattr(enemy, attr, max(0.0, cur - dt))
            except Exception:
                pass

    # ==================== 行为动作 ====================
    @staticmethod
    def _move_toward(ctx, k=1.0):
        ctx["vx"] = ctx["nx"] * k
        ctx["vy"] = ctx["ny"] * k

    @staticmethod
    def _move_away(ctx, k=1.0):
        ctx["vx"] = -ctx["nx"] * k
        ctx["vy"] = -ctx["ny"] * k

    @staticmethod
    def _move_strafe(ctx, k=0.75):
        """垂直环绕走位（绕玩家画圈，降低被弹率）"""
        ctx["vx"] = -ctx["ny"] * k
        ctx["vy"] = ctx["nx"] * k

    @staticmethod
    def _move_flank(ctx, k=0.9):
        """v2.2.5 包抄协同：按稳定扇区 id 向玩家侧前方包围，
        多怪各自取不同侧向 → 分散站位、从多方向夹击，避免挤成一堆被 AOE 清场"""
        side = 1.0 if (ctx["pid"] % 2 == 0) else -1.0
        blend = 0.55  # 侧向占比
        ctx["vx"] = (ctx["nx"] - ctx["ny"] * side * blend) * k
        ctx["vy"] = (ctx["ny"] + ctx["nx"] * side * blend) * k

    @staticmethod
    def _stay(ctx):
        ctx["vx"] = 0.0
        ctx["vy"] = 0.0

    @staticmethod
    def _cast(ctx, skill, move=None, k=0.0):
        ctx["skill"] = int(skill)
        if move == "toward":
            ctx["vx"] = ctx["nx"] * k
            ctx["vy"] = ctx["ny"] * k
        elif move == "away":
            ctx["vx"] = -ctx["nx"] * k
            ctx["vy"] = -ctx["ny"] * k
        elif move == "strafe":
            ctx["vx"] = -ctx["ny"] * k
            ctx["vy"] = ctx["nx"] * k
        else:
            ctx["vx"] = 0.0
            ctx["vy"] = 0.0

    # ==================== 条件 ====================
    def _c_near(self, ctx, r):
        return ctx["dist"] < r

    def _c_far(self, ctx, r):
        return ctx["dist"] > r

    def _c_cd_ready(self, ctx, attr):
        return (getattr(ctx["enemy"], attr, 0.0) or 0.0) <= 0.0

    def _c_hp_low(self, ctx, ratio):
        e = ctx["enemy"]
        return (e.hp / max(getattr(e, "max_hp", 50), 1)) < ratio

    def _c_throw_window(self, ctx):
        d = ctx["dist"]
        return 150 <= d <= 450 and (getattr(ctx["enemy"], "throw_cd", 0.0) or 0.0) <= 0.0

    def _c_few_minions(self, ctx, limit):
        return len([e for e in ctx["teammates"] if getattr(e, "alive", True)]) < limit

    def _c_injured_teammate(self, ctx):
        for t in ctx["teammates"]:
            if getattr(t, "alive", True) and not getattr(t, "is_boss", False):
                if getattr(t, "hp", 0) < getattr(t, "max_hp", 1) * 0.7:
                    return True
        return False

    def _c_hunt(self, ctx, ratio=0.35):
        """v2.5.4 狩猎：玩家残血（血量<35%）→ 僵尸进入追击/围杀模式"""
        return ctx["player_hp_ratio"] < ratio

    def _c_packed(self, ctx, n=3):
        """v2.5.4 成堆：存活队友≥n（群体协同，围堵更紧）"""
        return len([t for t in ctx["teammates"] if getattr(t, "alive", True)]) >= n

    def _c_lone(self, ctx, n=2):
        """v2.5.4 孤立：存活队友<n（落单僵尸更凶，直接贴脸）"""
        return len([t for t in ctx["teammates"] if getattr(t, "alive", True)]) < n

    def _c_ally_near(self, ctx, r=140):
        """v2.5.4 队友在身边（治疗/协同用）"""
        e = ctx["enemy"]
        for t in ctx["teammates"]:
            if getattr(t, "alive", True):
                if math.hypot(t.x - e.x, t.y - e.y) < r:
                    return True
        return False

    def _c_self_hurt(self, ctx, ratio=0.4):
        """v2.5.4 治疗僵尸自保：自己残血且无伤队友可奶"""
        e = ctx["enemy"]
        if (e.hp / max(getattr(e, "max_hp", 50), 1)) < ratio:
            for t in ctx["teammates"]:
                if getattr(t, "alive", True) and not getattr(t, "is_boss", False):
                    if getattr(t, "hp", 0) < getattr(t, "max_hp", 1) * 0.7:
                        return False
            return True
        return False

    def _c_dodge(self, ctx, r=150):
        """v2.2.5 弹幕规避：玩家弹在 r 内且朝自己飞来 → 触发横向闪避"""
        e = ctx["enemy"]
        for pr in ctx["pz"]:
            if not getattr(pr, "alive", True):
                continue
            dx = e.x - pr.x
            dy = e.y - pr.y
            d = math.hypot(dx, dy)
            if d > r:
                continue
            # 相对速度是否逼近（弹速点积 敌人方向 > 0）
            vdot = pr.vx * dx + pr.vy * dy
            if vdot > 0:
                return True
        return False

    # ==================== 决策树构建（按敌人类型） ====================
    def _get_tree(self, enemy):
        tid = id(enemy)
        t = self._trees.get(tid)
        if t is not None:
            return t
        # 防内存增长：决策树按敌人 id 缓存，大量尸体时定期清空重建
        if len(self._trees) > 4096:
            self._trees.clear()
        if getattr(enemy, "is_boss", False):
            tree = self._build_boss_tree(enemy)
        elif getattr(enemy, "is_exploder", False):
            tree = self._build_exploder_tree(enemy)
        elif getattr(enemy, "is_healer", False):
            tree = self._build_healer_tree(enemy)
        elif getattr(enemy, "can_throw", False) or getattr(enemy, "attack_range", 0) > 0:
            tree = self._build_ranged_tree(enemy)
        else:
            tree = self._build_melee_tree(enemy)
        self._trees[tid] = tree
        return tree

    def _build_melee_tree(self, enemy):
        """普通僵尸：弹幕规避 → 近身停止（接触伤害由碰撞判定）→ 中距包抄围堵 → 远距追击"""
        melee_r = getattr(enemy, "size", 20) + 22
        return {
            "name": "melee",
            "root": Selector("melee", [
                Sequence("dodge", [
                    Condition("bullet", self._c_dodge),
                    Action("strafe_dodge", lambda c: self._move_strafe(c, 1.25)),
                ]),
                # v2.5.4 狩猎：玩家残血 → 全力冲杀
                Sequence("hunt", [
                    Condition("hunt", self._c_hunt),
                    Action("hunt_charge", lambda c: self._move_toward(c, 1.35)),
                ]),
                Sequence("attack", [
                    Condition("near", lambda c, r=melee_r: self._c_near(c, r)),
                    Action("stand_fight", lambda c: self._stay(c)),
                ]),
                # v2.5.4 孤立：落单僵尸直接贴脸，攻击半径放宽
                Sequence("lone_rush", [
                    Condition("lone", self._c_lone),
                    Condition("mid", lambda c, r=melee_r: c["dist"] < max(r * 1.5, 160)),
                    Action("rush_in", lambda c: self._move_toward(c, 1.2)),
                ]),
                Sequence("flank", [
                    Condition("mid", lambda c: 0 < c["dist"] < 170),
                    Action("flank_in", lambda c: self._move_flank(c, 1.1 if not self._c_packed(c, 3) else 1.3)),
                ]),
                Action("chase", lambda c: self._move_toward(c)),
            ]),
        }

    def _build_ranged_tree(self, enemy):
        """远程/投掷：弹幕规避 → 保持中距开火/投掷，过近后撤，过远追击"""
        r = getattr(enemy, "attack_range", 300)
        melee_r = getattr(enemy, "size", 20) + 22
        children = []
        # v2.2.5：弹幕规避（远程僵尸最怕被玩家点射压制）
        children.append(Sequence("dodge", [
            Condition("bullet", self._c_dodge),
            Action("strafe_dodge", lambda c: self._move_strafe(c, 1.0)),
        ]))
        if getattr(enemy, "can_throw", False):
            # 投掷优先：中距投掷
            children.append(Sequence("throw", [
                Condition("window", self._c_throw_window),
                Action("throw_cast", lambda c: self._cast(c, 5, move="strafe", k=0.4)),
            ]))
        if r > 0:
            children.append(Sequence("retreat", [
                # v2.5.4 狩猎时更敢贴脸输出（后撤阈值从 0.45 降到 0.35）
                Condition("too_close", lambda c, rr=r: c["dist"] < rr * (0.35 if self._c_hunt(c) else 0.45)),
                Action("fallback", lambda c: self._move_away(c, 0.85)),
            ]))
            children.append(Sequence("fire", [
                Condition("in_range", lambda c, rr=r: c["dist"] < rr * 0.96),
                Action("shoot", lambda c: self._cast(c, 1, move="strafe", k=0.35)),
            ]))
        children.append(Sequence("melee_def", [
            Condition("cornered", lambda c, rr=r: c["dist"] < max(melee_r, rr * 0.3)),
            Action("break_off", lambda c: self._move_away(c, 1.0)),
        ]))
        children.append(Action("chase", lambda c: self._move_toward(c)))
        return {"name": "ranged", "root": Selector("ranged", children)}

    def _build_exploder_tree(self, enemy):
        """爆炸僵尸：冲进人群引爆（自爆判定由原生处理）"""
        return {
            "name": "exploder",
            "root": Selector("exploder", [
                Sequence("rush", [
                    Condition("nearish", lambda c: c["dist"] < 180),
                    Action("charge", lambda c: self._move_toward(c, 1.25 if not self._c_hunt(c) else 1.5)),
                ]),
                Action("chase", lambda c: self._move_toward(c)),
            ]),
        }

    def _build_healer_tree(self, enemy):
        """v2.5.4 治疗僵尸：队友受伤→靠到治疗半径内停住持续奶（不贴脸送死）；
        自己残血且无伤队友→后撤自保；否则随众追击"""
        heal_r = max(getattr(enemy, "heal_radius", 100), 100)
        return {
            "name": "healer",
            "root": Selector("healer", [
                # 自己残血且没有可奶的队友 → 后撤保命（活着才能奶）
                Sequence("flee", [
                    Condition("self_hurt", self._c_self_hurt),
                    Action("fallback", lambda c: self._move_away(c, 1.0)),
                ]),
                # 有伤队友：靠到治疗圈内停住（保持 80%~圈内），持续光环回血
                Sequence("heal_ally", [
                    Condition("injured", self._c_injured_teammate),
                    Condition("far", lambda c, r=heal_r: c["dist"] > r * 0.8),
                    Action("approach_ally", lambda c: self._move_toward(c, 1.0)),
                ]),
                Sequence("heal_stay", [
                    Condition("injured", self._c_injured_teammate),
                    Condition("near", lambda c, r=heal_r: c["dist"] <= r * 0.8),
                    Action("stand_heal", lambda c: self._stay(c)),
                ]),
                Action("chase", lambda c: self._move_toward(c, 0.8)),
            ]),
        }

    def _build_boss_tree(self, enemy):
        """Boss 决策树：低血回血 → 特种召唤 → 锁定必中 → 恶心 → 近战爆发 → 冲刺 → 召唤 → 投掷 → 远程压制 → 追击"""
        r = getattr(enemy, "attack_range", 0)
        melee_r = getattr(enemy, "size", 30) + 26
        children = [
            # 1. 低血回血（boss_heal_cd<=0 且血量<30%）
            Sequence("heal_self", [
                Condition("hp_low", lambda c: self._c_hp_low(c, 0.3)),
                Condition("cd", lambda c: self._c_cd_ready(c, "boss_heal_cd")),
                Action("cast_heal", lambda c: self._cast(c, 9)),
            ]),
            # 2. 特种召唤（精英怪数量不足）
            Sequence("summon_elite", [
                Condition("cd", lambda c: self._c_cd_ready(c, "boss_elite_cd")),
                Condition("few", lambda c: self._c_few_minions(c, 4)),
                Action("cast_elite", lambda c: self._cast(c, 8)),
            ]),
            # 3. 锁定必中（中远距高威胁）
            Sequence("lockon", [
                Condition("cd", lambda c: self._c_cd_ready(c, "boss_lock_cd")),
                Condition("in_los", lambda c: c["dist"] < 500),
                Action("cast_lock", lambda c: self._cast(c, 6, move="strafe", k=0.3)),
            ]),
            # 4. 恶心控制（近身）
            Sequence("debuff", [
                Condition("cd", lambda c: self._c_cd_ready(c, "boss_debuff_cd")),
                Condition("close", lambda c: c["dist"] < 270),
                Action("cast_debuff", lambda c: self._cast(c, 7, move="strafe", k=0.3)),
            ]),
        ]
        # 5. 近战爆发（范围咆哮/镰刀横扫）
        children.append(Sequence("aoe", [
            Condition("cd", lambda c: self._c_cd_ready(c, "boss_aoe_cd")),
            Condition("close", lambda c, r=melee_r: c["dist"] < max(r + 40, 230)),
            Action("cast_aoe", lambda c: self._cast(c, 4)),
        ]))
        # 6. 冲刺（贴脸突袭 / 远处拉近距离）
        children.append(Sequence("dash", [
            Condition("cd", lambda c: self._c_cd_ready(c, "boss_dash_cd")),
            Condition("range", lambda c: c["dist"] < 170 or c["dist"] > 330),
            Action("cast_dash", lambda c: self._cast(c, 2, move="toward", k=0.5)),
        ]))
        # 7. 常规召唤
        children.append(Sequence("summon", [
            Condition("cd", lambda c: self._c_cd_ready(c, "boss_summon_cd")),
            Action("cast_summon", lambda c: self._cast(c, 3)),
        ]))
        # 8. 投掷
        if getattr(enemy, "can_throw", False):
            children.append(Sequence("throw", [
                Condition("window", self._c_throw_window),
                Action("cast_throw", lambda c: self._cast(c, 5, move="strafe", k=0.3)),
            ]))
        # 9. 远程压制
        if r > 0:
            children.append(Sequence("retreat", [
                Condition("too_close", lambda c, rr=r: c["dist"] < rr * 0.45),
                Action("fallback", lambda c: self._move_away(c, 0.8)),
            ]))
            children.append(Sequence("fire", [
                Condition("in_range", lambda c, rr=r: c["dist"] < rr * 0.96),
                Action("shoot", lambda c: self._cast(c, 1, move="strafe", k=0.3)),
            ]))
        # 10. 追击
        children.append(Action("chase", lambda c: self._move_toward(c, 0.9)))
        return {"name": "boss", "root": Selector("boss", children)}


    def save_stats(self, path):
        """导出遥测数据（与旧 RLEnemyAI 同接口，供开发者面板/离线分析）"""
        try:
            import json
            s = dict(self.stats)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
