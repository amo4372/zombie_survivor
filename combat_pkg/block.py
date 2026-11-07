# -*- coding: utf-8 -*-
"""主动格挡系统（v2.9.12）

交互
----
- **短按**：在当前方向做一次短格挡（默认 0.35s），起手 0.20s 内为完美格挡窗口
- **长按 + 拖动**：持续举盾，拖动改变格挡方向并蓄力（蓄力提升减伤）
- 键控：按住格挡键不放即长按，鼠标/方向键改变朝向；轻点即短格挡
- 触控：独立的「格挡摇杆」，按下拖动改方向，轻点即短格挡

规则
----
- 只挡**一次**攻击：命中后立即进入冷却，冷却时长随该次伤害增大
- 高伤害攻击 → 长冷却（上限 3.5s），完美格挡冷却减半
- 正常格挡按蓄力减免 65%~85%，完美格挡完全免伤并让攻击方硬直
- 格挡期间**无法攻击 / 放技能 / 肘击**（`blocks_attack`）
- 只挡来自格挡方向的攻击（±ARC 度），背袭无效
- DOT / 持续伤害不属于"一次攻击"，不触发格挡
"""
import math
from dataclasses import dataclass

TAP_THRESHOLD = 0.16      # 按下时长短于此值 = 短按
SHORT_DURATION = 0.36     # 短格挡持续
PERFECT_WINDOW = 0.20     # 起手完美窗口
HOLD_CHARGE_TIME = 0.90   # 蓄满所需时间
ARC_DEG = 80.0            # 有效格挡半角
BASE_REDUCTION = 0.65     # 正常格挡基础减伤
CHARGE_BONUS = 0.20       # 蓄满额外减伤
CD_BASE = 0.40
CD_PER_DAMAGE = 0.015
CD_MAX = 3.50
NO_BLOCK_TYPES = frozenset(("dot", "poison", "burn", "bleed", "true", "fall"))


@dataclass
class BlockResult:
    blocked: bool = False
    perfect: bool = False
    damage: float = 0.0
    reduction: float = 0.0
    cooldown: float = 0.0
    reason: str = ""


def angle_diff(a: float, b: float) -> float:
    """两个角度(度)的最小夹角"""
    return abs((a - b + 180.0) % 360.0 - 180.0)


class BlockController:
    """挂在 player.block 上。渲染层直接读字段画弧/蓄力/冷却。"""

    def __init__(self, player):
        self.player = player
        self.state = "idle"          # idle / active / cooldown
        self.mode = "short"          # short / hold
        self.angle = 0.0             # 格挡朝向（度，屏幕坐标）
        self.charge = 0.0            # 0..1 蓄力
        self.active_time = 0.0       # 本次举盾已持续时间
        self.press_time = 0.0        # 按下累计（区分短按/长按）
        self.cooldown = 0.0
        self.cooldown_total = 0.0
        self._pressed = False
        self.last_result = BlockResult()
        # 反馈（渲染层消费）
        self.fx_timer = 0.0
        self.fx_perfect = False
        self.blocked_count = 0

    # ------------------------------------------------------------ 属性
    @property
    def active(self) -> bool:
        return self.state == "active"

    @property
    def blocks_attack(self) -> bool:
        """格挡期间禁止攻击 / 技能 / 肘击"""
        return self.active

    @property
    def on_cooldown(self) -> bool:
        return self.cooldown > 0

    @property
    def reduction(self) -> float:
        return min(0.95, BASE_REDUCTION + CHARGE_BONUS * self.charge)

    def is_blocking(self) -> bool:
        """供 mix_playing._is_melee_blocked 的旧接口"""
        return self.active

    def default_angle(self) -> float:
        return float(getattr(self.player, "facing_angle", 0.0) or 0.0)

    # ------------------------------------------------------------ 输入
    def press(self, angle: float = None):
        """按下格挡键/摇杆"""
        if self.on_cooldown or self.active:
            return False
        self._pressed = True
        self.press_time = 0.0
        self.angle = float(angle if angle is not None else self.default_angle())
        self.charge = 0.0
        self.active_time = 0.0
        self.state = "active"
        self.mode = "short"
        return True

    def drag(self, angle: float, dt: float):
        """长按拖动：改变方向 + 蓄力"""
        if not self.active or not self._pressed:
            return
        self.angle = float(angle)
        self.press_time += max(0.0, dt)
        if self.press_time >= TAP_THRESHOLD:
            self.mode = "hold"
            self.charge = min(1.0, self.charge + dt / HOLD_CHARGE_TIME)

    def release(self):
        """松开：短按 → 保留短格挡窗口；长按 → 保留一小段收势后结束"""
        if not self._pressed:
            return
        self._pressed = False
        if self.mode == "short":
            # 短格挡：从按下起算 SHORT_DURATION
            self.active_time = max(0.0, self.press_time)
        else:
            # 长按松开：给 0.18s 收势，仍可挡一次
            self.active_time = max(self.active_time, SHORT_DURATION - 0.18)

    def cancel(self):
        self._pressed = False
        if self.state == "active":
            self.state = "idle"
        self.charge = 0.0
        self.active_time = 0.0

    # ------------------------------------------------------------ 每帧
    def update(self, dt: float):
        if self.fx_timer > 0:
            self.fx_timer = max(0.0, self.fx_timer - dt)
        if self.cooldown > 0:
            self.cooldown = max(0.0, self.cooldown - dt)
            if self.cooldown <= 0 and self.state == "cooldown":
                self.state = "idle"
        if self.state != "active":
            return
        self.active_time += dt
        if self._pressed:
            self.press_time += dt
            if self.press_time >= TAP_THRESHOLD:
                self.mode = "hold"
                self.charge = min(1.0, self.charge + dt / HOLD_CHARGE_TIME)
        # 短格挡到时 / 长按收势到时
        limit = SHORT_DURATION if self.mode == "short" else SHORT_DURATION
        if not self._pressed and self.active_time >= limit:
            self.state = "idle"
            self.charge = 0.0

    # ------------------------------------------------------------ 结算
    def try_block(self, damage: float, attack_x=None, attack_y=None,
                  damage_type: str = "melee", incoming_angle=None) -> BlockResult:
        """一次攻击到达时调用。返回是否格挡、完美与否、最终伤害与冷却。"""
        dmg = max(0.0, float(damage or 0.0))
        if str(damage_type).lower() in NO_BLOCK_TYPES:
            return BlockResult(False, damage=dmg, reason="dot")
        if not self.active or self.on_cooldown:
            return BlockResult(False, damage=dmg, reason="inactive")
        # 方向判定：攻击来源必须落在格挡弧内
        if incoming_angle is not None:
            # v2.9.13：优先用显式来向（弹丸速度反推），避免贴身坐标随机化
            try:
                if angle_diff(float(incoming_angle), self.angle) > ARC_DEG:
                    return BlockResult(False, damage=dmg, reason="behind")
            except Exception:
                pass
        elif attack_x is not None and attack_y is not None:
            try:
                src_ang = math.degrees(math.atan2(
                    float(attack_y) - float(self.player.y),
                    float(attack_x) - float(self.player.x)))
                if angle_diff(src_ang, self.angle) > ARC_DEG:
                    return BlockResult(False, damage=dmg, reason="behind")
            except Exception:
                pass
        # 完美窗口 = **起手瞬间**（短按 0.20s / 长按刚抬过短按阈值的 0.12s）。
        # 长按蓄满只提供强减伤，不自动免伤 —— 否则一直举盾就能无限完美格挡，
        # 失去时机博弈。
        perfect = ((self.mode == "short" and self.active_time <= PERFECT_WINDOW)
                   or (self.mode == "hold"
                       and self.press_time <= TAP_THRESHOLD + 0.12))
        if perfect:
            final = 0.0
            reduction = 1.0
        else:
            reduction = self.reduction
            final = dmg * (1.0 - reduction)
        cd = min(CD_MAX, CD_BASE + dmg * CD_PER_DAMAGE)
        if perfect:
            cd *= 0.5
        # 只挡一次：立即进冷却
        self.cooldown = cd
        self.cooldown_total = cd
        self.state = "cooldown"
        self._pressed = False
        self.blocked_count += 1
        self.fx_timer = 0.45
        self.fx_perfect = perfect
        self.last_result = BlockResult(True, perfect, final, reduction, cd, "ok")
        self.charge = 0.0
        return self.last_result

    def snapshot(self) -> dict:
        return {"state": self.state, "mode": self.mode,
                "angle": round(self.angle, 1), "charge": round(self.charge, 2),
                "cooldown": round(self.cooldown, 2),
                "blocks_attack": self.blocks_attack}


def attach_block(player) -> BlockController:
    bc = BlockController(player)
    player.block = bc
    return bc


__all__ = ["BlockController", "BlockResult", "attach_block", "angle_diff",
           "TAP_THRESHOLD", "SHORT_DURATION", "PERFECT_WINDOW", "ARC_DEG"]
