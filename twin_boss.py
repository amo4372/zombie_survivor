# -*- coding: utf-8 -*-
"""v2.8.8 双子 Boss：郑某（空间） / 惠某（时间）

两人**成对刷新**：同生同死，一方血量低时触发组合技。

## 郑某 —— 空间
- 周期性释放多个**范围圈**，形状各异（圆 / 三角 / 矩形 / 爱心）
- 圈会**持续移动与旋转**
- 圈有多类型：
    * 伤害圈：圈内持续掉血
    * 安全圈：**圈内免伤，圈外持续掉血**（反转判定）
    * 恢复圈：圈内持续回血
- 玩家血量偏低时：强行把玩家**限制**在一个圈内，并发射弹幕

## 惠某 —— 时间
- **时间回溯**：只针对玩家及其相关物（子弹）倒流；
  玩家有利的是**血量等状态也回到从前**（等于复活/回血）
- **时间快进**：区域内一切加速
- **区域时停**：一定区域内完全静止

## 组合技 · 王车易位
一方血量低于阈值 → 前摇 → **交换两 Boss 位置** → 以 Boss 为中心的范围圈
释放技能：随机**禁用玩家全部主动技能或全部被动技能**一段时间。
"""
import math
import random

# ======================================================================
# 范围圈
# ======================================================================
ZONE_DAMAGE = "damage"      # 圈内掉血
ZONE_SAFE = "safe"          # 圈内免伤，圈外掉血
ZONE_HEAL = "heal"          # 圈内回血

SHAPE_CIRCLE = "circle"
SHAPE_TRIANGLE = "triangle"
SHAPE_RECT = "rect"
SHAPE_HEART = "heart"

ZONE_META = {
    ZONE_DAMAGE: {"name": "伤害圈", "color": (230, 70, 60)},
    ZONE_SAFE:   {"name": "安全圈", "color": (90, 200, 255)},
    ZONE_HEAL:   {"name": "恢复圈", "color": (110, 240, 140)},
}


class SpaceZone:
    """郑某的空间范围圈：会移动、会旋转"""

    def __init__(self, x, y, radius, kind=ZONE_DAMAGE,
                 shape=SHAPE_CIRCLE, life=6.0,
                 move_dir=None, move_speed=40.0, spin=0.6,
                 dps=18.0, heal=10.0):
        self.x = x
        self.y = y
        self.radius = float(radius)
        self.kind = kind
        self.shape = shape
        self.life = float(life)
        self.max_life = float(life)
        self.move_dir = move_dir or (0.0, 0.0)
        self.move_speed = float(move_speed)
        self.spin = float(spin)
        self.angle = 0.0
        self.dps = float(dps)
        self.heal = float(heal)
        self.alive = True
        #: 形态参数（矩形半高比等）
        self.aspect = 0.62

    def update(self, dt):
        if not self.alive:
            return
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return
        _dx, _dy = self.move_dir
        self.x += _dx * self.move_speed * dt
        self.y += _dy * self.move_speed * dt
        self.angle += self.spin * dt

    def contains(self, px, py):
        """点是否落在圈内（按形状判定，考虑旋转）"""
        _dx = px - self.x
        _dy = py - self.y
        _d = math.hypot(_dx, _dy)
        if self.shape == SHAPE_CIRCLE:
            return _d <= self.radius
        # 旋转到圈的本地坐标系
        _a = -self.angle
        _lx = _dx * math.cos(_a) - _dy * math.sin(_a)
        _ly = _dx * math.sin(_a) + _dy * math.cos(_a)
        _r = self.radius
        if self.shape == SHAPE_RECT:
            return abs(_lx) <= _r and abs(_ly) <= _r * self.aspect
        if self.shape == SHAPE_TRIANGLE:
            # 正三角形内切
            _h = _r
            if _ly > _h * 0.5 or _ly < -_h:
                return False
            _half_w = (_h * 0.5 - _ly * 0.0) * (1.0 - (_ly + _r) / (1.5 * _r)) * 0.9
            _half_w = max(0.0, (_r * 1.5 - (_ly + _r)) / 1.5 * 0.95)
            return abs(_lx) <= _half_w
        if self.shape == SHAPE_HEART:
            # 心形隐函数：(x²+y²-r²)³ - x²y³ <= 0（缩放后）
            _s = 1.0 / max(1.0, _r * _r * _r)
            _X = _lx / max(1.0, _r * 0.62)
            _Y = -_ly / max(1.0, _r * 0.62)
            _v = (_X * _X + _Y * _Y - 1.0)
            return (_v ** 3 - _X * _X * (_Y ** 3)) <= 0.35
        return _d <= self.radius

    def effect_on(self, player, dt):
        """对玩家施加本圈效果，返回 (伤害, 治疗)"""
        _inside = self.contains(player.x, player.y)
        if self.kind == ZONE_SAFE:
            # 安全圈：圈**外**才受伤
            if _inside:
                return 0.0, 0.0
            return self.dps * dt, 0.0
        if not _inside:
            return 0.0, 0.0
        if self.kind == ZONE_HEAL:
            return 0.0, self.heal * dt
        return self.dps * dt, 0.0

    def polygon(self, steps=28):
        """绘制用多边形顶点（世界坐标）"""
        _pts = []
        for _i in range(steps):
            _t = _i / steps * math.tau
            if self.shape == SHAPE_CIRCLE:
                _x = self.x + math.cos(_t) * self.radius
                _y = self.y + math.sin(_t) * self.radius
            elif self.shape == SHAPE_RECT:
                _a = _t
                _lx = math.copysign(self.radius, math.cos(_a)) if abs(math.cos(_a)) > 1e-6 else self.radius
                _ly = math.copysign(self.radius * self.aspect, math.sin(_a)) if abs(math.sin(_a)) > 1e-6 else self.radius * self.aspect
                # 取矩形边界上的点
                _k = max(abs(math.cos(_a)) / max(1e-6, self.radius),
                         abs(math.sin(_a)) / max(1e-6, self.radius * self.aspect))
                _lx = math.cos(_a) / _k
                _ly = math.sin(_a) / _k
                _x = self.x + _lx * math.cos(self.angle) - _ly * math.sin(self.angle)
                _y = self.y + _lx * math.sin(self.angle) + _ly * math.cos(self.angle)
            elif self.shape == SHAPE_TRIANGLE:
                _a = self.angle + _i / steps * math.tau * 1.0
                _k = (_i % 3) / 3.0
                _rr = self.radius * (0.86 + 0.14 * math.cos(_k * math.tau))
                _x = self.x + math.cos(_a) * _rr
                _y = self.y + math.sin(_a) * _rr
            else:   # heart
                _a = self.angle + _t
                _rr = self.radius * (0.78 + 0.22 * abs(math.sin(_t * 1.5)))
                _x = self.x + math.cos(_a) * _rr
                _y = self.y - math.sin(_a) * _rr
            _pts.append((_x, _y))
        return _pts


# ======================================================================
# 郑某（空间）
# ======================================================================
class BossZheng:
    """郑某 —— 空间系"""

    #: 圈生成周期
    ZONE_INTERVAL = 4.2
    #: 低血量阈值（触发限制圈 + 弹幕）
    LOW_HP_RATIO = 0.35

    def __init__(self, x=0.0, y=0.0, hp=6000.0, rng=None):
        self.name = "郑某"
        self.title = "空间"
        self.x = x
        self.y = y
        self.hp = float(hp)
        self.max_hp = float(hp)
        self.alive = True
        self.rng = rng or random
        self.zones = []
        self.zone_timer = 1.5
        self.barrage_timer = 0.0
        self.cage_zone = None
        self.bullets = []

    # ---------------- 圈生成 ----------------
    def _random_shape(self):
        return self.rng.choice([SHAPE_CIRCLE, SHAPE_TRIANGLE, SHAPE_RECT, SHAPE_HEART])

    def spawn_zones(self, players, count=None):
        """周期性生成一批范围圈"""
        _n = count or self.rng.randint(2, 3)
        for _ in range(_n):
            _kind = self.rng.choices(
                [ZONE_DAMAGE, ZONE_SAFE, ZONE_HEAL],
                weights=[52, 28, 20], k=1)[0]
            # 圈尽量落在玩家附近，保证有交互
            _px, _py = self.x, self.y
            if players:
                _t = self.rng.choice(players)
                _px = getattr(_t, 'x', self.x) + self.rng.uniform(-160, 160)
                _py = getattr(_t, 'y', self.y) + self.rng.uniform(-160, 160)
            _a = self.rng.random() * math.tau
            _z = SpaceZone(
                _px, _py,
                radius=self.rng.uniform(150, 260),
                kind=_kind,
                shape=self._random_shape(),
                life=self.rng.uniform(5.0, 8.5),
                move_dir=(math.cos(_a), math.sin(_a)),
                move_speed=self.rng.uniform(20, 55),
                spin=self.rng.uniform(-1.1, 1.1),
                dps=self.rng.uniform(14, 26),
                heal=self.rng.uniform(8, 16),
            )
            self.zones.append(_z)
        # 保持圈数量可控
        if len(self.zones) > 9:
            self.zones = self.zones[-9:]

    # ---------------- 限制圈 + 弹幕 ----------------
    def _try_cage(self, players):
        """玩家血量偏低 → 强行限制到圈内并发射弹幕"""
        for _p in players or []:
            try:
                _ratio = getattr(_p, 'hp', 1) / max(1.0, getattr(_p, 'max_hp', 100))
            except Exception:
                continue
            if _ratio > self.LOW_HP_RATIO:
                continue
            if self.cage_zone is not None and self.cage_zone.alive:
                continue
            # 把玩家限制在原地的一个圈里
            self.cage_zone = SpaceZone(
                getattr(_p, 'x', self.x), getattr(_p, 'y', self.y),
                radius=230.0, kind=ZONE_SAFE, shape=SHAPE_CIRCLE,
                life=5.0, move_dir=(0.0, 0.0), move_speed=0.0, spin=0.0,
                dps=30.0)
            self.zones.append(self.cage_zone)
            self.barrage_timer = 5.0
            return _p

    def _fire_barrage(self, dt, players):
        """限制期间发射弹幕"""
        if self.barrage_timer <= 0 or self.cage_zone is None:
            return
        self.barrage_timer -= dt
        if self.rng.random() < dt * 8.0:
            _a = self.rng.random() * math.tau
            self.bullets.append({
                "x": self.x, "y": self.y,
                "vx": math.cos(_a) * 260.0, "vy": math.sin(_a) * 260.0,
                "life": 3.0, "damage": 16.0,
            })

    def update(self, dt, players=None):
        if not self.alive:
            return
        players = players or []
        # 生成圈
        self.zone_timer -= dt
        if self.zone_timer <= 0:
            self.zone_timer = self.ZONE_INTERVAL
            self.spawn_zones(players)
        # 更新圈
        for _z in self.zones:
            _z.update(dt)
        self.zones = [_z for _z in self.zones if _z.alive]
        # 低血量限制
        self._try_cage(players)
        self._fire_barrage(dt, players)
        # 弹幕推进
        for _b in self.bullets:
            _b["x"] += _b["vx"] * dt
            _b["y"] += _b["vy"] * dt
            _b["life"] -= dt
        self.bullets = [_b for _b in self.bullets if _b["life"] > 0]

    def apply_zones(self, players, dt):
        """对每位玩家结算所有圈的效果 → [(player, 伤害, 治疗), ...]"""
        _out = []
        for _p in players or []:
            _dmg = 0.0
            _heal = 0.0
            for _z in self.zones:
                _d, _h = _z.effect_on(_p, dt)
                _dmg += _d
                _heal += _h
            _out.append((_p, _dmg, _heal))
        return _out


# ======================================================================
# 惠某（时间）
# ======================================================================
class BossHui:
    """惠某 —— 时间系

    时间回溯只作用于**玩家及其相关物**（子弹）。
    对玩家的好处：血量/状态一起回到从前（等于回血、清负面）。
    """

    REWIND_INTERVAL = 11.0
    REWIND_SECONDS = 3.0        # 回溯多少秒
    FAST_FORWARD_INTERVAL = 8.0
    FREEZE_INTERVAL = 14.0

    def __init__(self, x=0.0, y=0.0, hp=6000.0, rng=None):
        self.name = "惠某"
        self.title = "时间"
        self.x = x
        self.y = y
        self.hp = float(hp)
        self.max_hp = float(hp)
        self.alive = True
        self.rng = rng or random

        #: 玩家状态历史（用于回溯）：{id(player): [(t, x, y, hp, ...)]}
        self.history = {}
        self.hist_t = 0.0

        self.rewind_cd = self.REWIND_INTERVAL
        self.ff_cd = self.FAST_FORWARD_INTERVAL
        self.freeze_cd = self.FREEZE_INTERVAL
        #: 当前生效的时间效果
        self.rewind_active = 0.0
        self.fast_forward_active = 0.0
        self.freeze_active = 0.0
        self.freeze_center = None
        self.freeze_radius = 300.0
        self.last_action = ""

    # ---------------- 历史记录 ----------------
    def record(self, players, dt, now):
        """持续记录玩家状态（供回溯使用）"""
        self.hist_t += dt
        for _p in players or []:
            _key = id(_p)
            _buf = self.history.setdefault(_key, [])
            _buf.append((now,
                         getattr(_p, 'x', 0.0), getattr(_p, 'y', 0.0),
                         getattr(_p, 'hp', 0.0)))
            # 只保留最近 12 秒
            if len(_buf) > 720:
                self.history[_key] = _buf[-720:]

    def _find_snapshot(self, player, now, seconds):
        """找到 seconds 秒前的快照"""
        _buf = self.history.get(id(player))
        if not _buf:
            return None
        _target = now - seconds
        # 二分/线性找最接近的
        _best = _buf[0]
        for _row in _buf:
            if _row[0] >= _target:
                _best = _row
                break
            _best = _row
        return _best

    # ---------------- 时间能力 ----------------
    def cast_rewind(self, players, now, player_bullets=None):
        """时间回溯：玩家位置/血量回到从前，其子弹也被收回"""
        _moved = []
        for _p in players or []:
            _snap = self._find_snapshot(_p, now, self.REWIND_SECONDS)
            if _snap is None:
                continue
            _, _x, _y, _hp = _snap
            _old_hp = getattr(_p, 'hp', 0.0)
            _p.x = _x
            _p.y = _y
            # 血量回到从前（若当时更健康则回血）
            if _hp > _old_hp:
                _p.hp = min(getattr(_p, 'max_hp', _hp), _hp)
            _moved.append(_p)
        # 玩家的子弹一起倒流：直接清空（视觉上"收回去"）
        if player_bullets is not None:
            try:
                player_bullets.clear()
            except Exception:
                pass
        self.rewind_active = 1.2
        self.last_action = "时间回溯"
        return _moved

    def cast_fast_forward(self, players):
        """时间快进：区域内玩家动作加速（这里体现为短暂加速 BUFF 标记）"""
        self.fast_forward_active = 3.5
        self.last_action = "时间快进"
        for _p in players or []:
            try:
                _p._hui_fast_forward = self.fast_forward_active
            except Exception:
                pass
        return True

    def cast_freeze(self, x, y, radius=None):
        """区域时停"""
        self.freeze_active = 2.5
        self.freeze_center = (x, y)
        self.freeze_radius = float(radius or self.freeze_radius)
        self.last_action = "区域时停"
        return True

    def is_frozen(self, x, y):
        if self.freeze_active <= 0 or self.freeze_center is None:
            return False
        return math.hypot(x - self.freeze_center[0],
                          y - self.freeze_center[1]) <= self.freeze_radius

    def update(self, dt, players=None, now=0.0, player_bullets=None):
        if not self.alive:
            return None
        players = players or []
        self.record(players, dt, now)
        self.rewind_cd -= dt
        self.ff_cd -= dt
        self.freeze_cd -= dt
        self.rewind_active = max(0.0, self.rewind_active - dt)
        self.fast_forward_active = max(0.0, self.fast_forward_active - dt)
        self.freeze_active = max(0.0, self.freeze_active - dt)

        # 队友（郑某）血量低时优先回溯保命 —— 组合技前摇里会用到
        if self.rewind_cd <= 0:
            self.rewind_cd = self.REWIND_INTERVAL
            return ("rewind", self.cast_rewind(players, now, player_bullets))
        if self.ff_cd <= 0:
            self.ff_cd = self.FAST_FORWARD_INTERVAL
            return ("fast_forward", self.cast_fast_forward(players))
        if self.freeze_cd <= 0 and players:
            self.freeze_cd = self.FREEZE_INTERVAL
            _t = self.rng.choice(players)
            return ("freeze", self.cast_freeze(getattr(_t, 'x', self.x),
                                               getattr(_t, 'y', self.y)))
        return None


# ======================================================================
# 组合技 · 王车易位
# ======================================================================
CASTLE_VARIANT = "王车易位"


class TwinBossPair:
    """双子 Boss 对：郑某 + 惠某，含组合技"""

    #: 一方血量低于此比例 → 触发王车易位
    SWAP_HP_RATIO = 0.40
    SWAP_WINDUP = 2.0
    #: 组合技禁用时长
    DISABLE_DURATION = 8.0

    def __init__(self, zheng=None, hui=None, rng=None):
        self.zheng = zheng or BossZheng()
        self.hui = hui or BossHui()
        self.rng = rng or random
        self.swap_windup = 0.0
        self.swap_done = False
        self.disable_timer = 0.0
        self.disable_mode = None        # "active" | "passive"
        self.last_cast = ""

    @property
    def alive(self):
        return bool(self.zheng.alive or self.hui.alive)

    def take_damage(self, amount, target=None):
        """受伤（target 为 'zheng' / 'hui' / None=均分）"""
        if target == "zheng":
            self.zheng.hp -= amount
        elif target == "hui":
            self.hui.hp -= amount
        else:
            self.zheng.hp -= amount * 0.5
            self.hui.hp -= amount * 0.5
        for _b in (self.zheng, self.hui):
            if _b.hp <= 0:
                _b.hp = 0
                _b.alive = False
        # 同生同死
        if not self.zheng.alive and self.hui.alive:
            self.hui.hp = 0
            self.hui.alive = False
        if not self.hui.alive and self.zheng.alive:
            self.zheng.hp = 0
            self.zheng.alive = False

    def update(self, dt, players=None, now=0.0, player_bullets=None):
        """返回本帧发生的大招描述（用于飘字/字幕），没有则 None"""
        players = players or []
        _event = None
        if not self.alive:
            return None

        # 组合技：王车易位
        if not self.swap_done:
            _z_low = (self.zheng.hp / max(1.0, self.zheng.max_hp)) <= self.SWAP_HP_RATIO
            _h_low = (self.hui.hp / max(1.0, self.hui.max_hp)) <= self.SWAP_HP_RATIO
            if _z_low or _h_low:
                if self.swap_windup <= 0:
                    self.swap_windup = self.SWAP_WINDUP
                    _event = ("windup", "王车易位 · 前摇")
                else:
                    self.swap_windup -= dt
                    if self.swap_windup <= 0:
                        _event = self._do_swap(players)
        # 禁用计时
        if self.disable_timer > 0:
            self.disable_timer -= dt
            if self.disable_timer <= 0:
                self.disable_mode = None

        # 各自能力
        self.zheng.update(dt, players)
        _he = self.hui.update(dt, players, now, player_bullets)
        if _he and _event is None:
            _event = _he
        return _event

    def _do_swap(self, players):
        """执行王车易位：交换位置 + 范围圈释放禁用技能"""
        self.zheng.x, self.hui.x = self.hui.x, self.zheng.x
        self.zheng.y, self.hui.y = self.hui.y, self.zheng.y
        self.swap_done = True
        self.swap_windup = 0.0
        # 以两位 Boss 为中心各放一个大范围圈
        for _b, _kind in ((self.zheng, ZONE_DAMAGE), (self.hui, ZONE_SAFE)):
            _z = SpaceZone(_b.x, _b.y, radius=420.0, kind=_kind,
                           shape=SHAPE_CIRCLE, life=4.0,
                           move_dir=(0.0, 0.0), move_speed=0.0, spin=0.4,
                           dps=22.0)
            self.zheng.zones.append(_z)
        # 随机禁用：全部主动技能 或 全部被动技能
        self.disable_mode = self.rng.choice(["active", "passive"])
        self.disable_timer = self.DISABLE_DURATION
        self.last_cast = CASTLE_VARIANT
        _txt = ("全部主动技能已禁用！" if self.disable_mode == "active"
                else "全部被动技能已禁用！")
        return ("castle", f"{CASTLE_VARIANT} · {_txt}")

    # ---------------- 供游戏查询 ----------------
    def skills_disabled(self, kind):
        """某类技能当前是否被禁用（kind: 'active' / 'passive'）"""
        return self.disable_timer > 0 and self.disable_mode == kind

    def apply_zone_effects(self, players, dt):
        return self.zheng.apply_zones(players, dt)

    def frozen_at(self, x, y):
        return self.hui.is_frozen(x, y)
