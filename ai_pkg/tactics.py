# -*- coding: utf-8 -*-
"""战术 AI 增强层（v2.9.13）

在原有决策树之上叠加四件"群体智能"，全部纯函数、异常安全：
1. 多玩家目标选择：距离 + 残血加权 + 威胁（玩家火力）+ 仇恨记忆
2. 群体分离：同伙之间互斥，避免所有僵尸叠在一个点上
3. 包围扇区：按 id 派生稳定扇区，天然形成合围而不是排队
4. 弹幕规避：预测来袭投射物，侧向闪避
5. Boss 阶段：血量阶段提升攻击性、缩短间距

接口：apply_tactics(ctx) -> ctx（原地修改 vx/vy，并写入 tactical_target）
      select_target(enemy, players, ...) -> player
"""
import math

SEPARATION_RADIUS = 34.0
DODGE_RANGE = 150.0
THREAT_WINDOW = 1.2


def _hp_ratio(p):
    try:
        return max(0.0, min(1.0, float(getattr(p, "hp", 100)) /
                            max(1.0, float(getattr(p, "max_hp", 100)))))
    except Exception:
        return 1.0


def _firepower(p):
    """粗略威胁：伤害倍率 + 武器射速倒数"""
    try:
        w = p.get_current_weapon()
        rate = float(getattr(w, "fire_rate", 0.3) or 0.3)
        dmg = float(getattr(w, "damage", 10) or 10)
        mult = float(getattr(p, "damage_mult", 1.0) or 1.0)
        return (dmg / max(0.05, rate)) * mult
    except Exception:
        return 0.0


def select_target(enemy, players, mode="nearest", memory=None):
    """统一目标选择。players 为可迭代的玩家对象（可能含 None / 阵亡）。"""
    alive = [p for p in (players or [])
             if p is not None and getattr(p, "alive", True)
             and not getattr(p, "downed", False)]
    if not alive:
        return None
    ex, ey = float(getattr(enemy, "x", 0)), float(getattr(enemy, "y", 0))
    best, best_score = None, -1e18
    for p in alive:
        d = math.hypot(float(p.x) - ex, float(p.y) - ey)
        hp = _hp_ratio(p)
        score = -d
        if mode == "weakest":
            score += (1.0 - hp) * 260.0          # 残血优先
        elif mode == "threat":
            score += min(220.0, _firepower(p) * 0.55)
            score += (1.0 - hp) * 90.0
        elif mode == "ally_cluster":
            score += (1.0 - hp) * 40.0
        # 仇恨记忆：最近打过自己的玩家加权
        if memory and id(p) in memory:
            score += 90.0
        if score > best_score:
            best, best_score = p, score
    return best


def _separation(ctx):
    """同伙分离力：避免叠罗汉中"""
    e = ctx["enemy"]
    mates = ctx.get("teammates") or []
    sx = sy = 0.0
    ex, ey = float(e.x), float(e.y)
    n = 0
    for m in mates:
        if m is e or not getattr(m, "alive", True):
            continue
        dx = ex - float(getattr(m, "x", ex))
        dy = ey - float(getattr(m, "y", ey))
        d2 = dx * dx + dy * dy
        if d2 < 1e-4 or d2 > SEPARATION_RADIUS ** 2:
            continue
        d = math.sqrt(d2)
        w = (SEPARATION_RADIUS - d) / SEPARATION_RADIUS
        sx += dx / d * w
        sy += dy / d * w
        n += 1
        if n >= 6:
            break
    return sx * 0.55, sy * 0.55


def _projectile_dodge(ctx):
    """预测来袭弹丸 → 垂直方向侧移"""
    e = ctx["enemy"]
    pz = ctx.get("pz") or []
    ex, ey = float(e.x), float(e.y)
    sx = sy = 0.0
    for pr in pz[:12]:
        vx = float(getattr(pr, "vx", 0) or 0)
        vy = float(getattr(pr, "vy", 0) or 0)
        sp = math.hypot(vx, vy)
        if sp < 1e-3:
            continue
        px, py = float(getattr(pr, "x", 0)), float(getattr(pr, "y", 0))
        # 弹丸到僵尸的最近接近时间
        rx, ry = ex - px, ey - py
        t = (rx * vx + ry * vy) / (sp * sp)
        if t < 0 or t > THREAT_WINDOW:
            continue
        cx, cy = px + vx * t, py + vy * t
        miss = math.hypot(ex - cx, ey - cy)
        if miss > DODGE_RANGE * 0.45:
            continue
        # 垂直于弹道闪开
        sx += -vy / sp
        sy += vx / sp
    return sx, sy


def apply_tactics(ctx):
    """在决策树输出后叠加战术修正。异常时原样返回。"""
    try:
        e = ctx["enemy"]
        beh = getattr(e, "behavior", None)
        hp_ratio = _hp_ratio(e)
        phase = beh.phase(hp_ratio) if beh else 0
        aggression = float(getattr(beh, "aggression", 0.7) or 0.7)
        flank = float(getattr(beh, "flank", 0.4) or 0.4)
        dodge_w = float(getattr(beh, "dodge", 0.2) or 0.2)
        spacing = float(getattr(beh, "spacing", 40) or 40)
        move_mode = getattr(beh, "move", "surround")

        ctx["tactical_phase"] = phase
        ctx["tactical_target"] = None

        # 多玩家目标选择（world 里带 all_players 时生效）
        players = ctx.get("players") or None
        w = ctx.get("world")
        if not players and w is not None:
            players = getattr(w, "all_players", None) or getattr(w, "players", None)
        if players:
            mode = getattr(beh, "target", "nearest")
            ctx["tactical_target"] = select_target(e, players, mode)

        vx, vy = float(ctx.get("vx", 0.0)), float(ctx.get("vy", 0.0))

        # 稳定包围扇区：同一只怪方向恒定，群体自然散开
        if flank > 0 and ctx.get("dist", 0) < 320:
            pid = ctx.get("pid", 0)
            off = ((pid / 8.0) * 2.0 - 1.0) * math.pi * 0.75
            nx, ny = ctx.get("nx", 0.0), ctx.get("ny", 0.0)
            fx = nx * math.cos(off) - ny * math.sin(off)
            fy = nx * math.sin(off) + ny * math.cos(off)
            vx += fx * flank * 0.45
            vy += fy * flank * 0.45

        # 间距控制：太近后撤，太远压上（风筝型尤为明显）
        d = float(ctx.get("dist", 0.0))
        nx, ny = ctx.get("nx", 0.0), ctx.get("ny", 0.0)
        if spacing > 0:
            if d < spacing * 0.65:
                vx -= nx * 0.55
                vy -= ny * 0.55
            elif d > spacing * 1.6 and move_mode == "kite":
                vx += nx * 0.35
                vy += ny * 0.35

        sx, sy = _separation(ctx)
        vx += sx
        vy += sy

        if dodge_w > 0:
            dx, dy = _projectile_dodge(ctx)
            vx += dx * dodge_w
            vy += dy * dodge_w

        # Boss 阶段：越残血越猛
        if phase:
            k = 1.0 + 0.18 * phase
            vx *= k
            vy *= k
        else:
            k = 0.75 + 0.35 * aggression
            vx *= k
            vy *= k

        n = math.hypot(vx, vy)
        if n > 1.0:
            vx, vy = vx / n, vy / n
        ctx["vx"], ctx["vy"] = vx, vy
    except Exception:
        pass
    return ctx


__all__ = ["apply_tactics", "select_target", "SEPARATION_RADIUS"]
