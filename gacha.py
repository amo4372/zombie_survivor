# -*- coding: utf-8 -*-
"""军械库补给（武器抽取）+ 老虎机 —— v2.8.9

## 武器获取方式变更（v2.8.9）

**武器不再能直接购买**，只能通过「军械库补给」抽取获得（类似米哈游抽卡）。

## 抽取机制（米哈游式）

    品质      稀有度   基础概率    保底
    ────────────────────────────────────────
    传说      5★      0.6%      90 抽硬保底（含概率提升）
    史诗      4★      5.1%      10 抽保底
    稀有      3★     20.0%      —
    精良      2★     34.3%      —
    普通      1★     40.0%      —

核心规则：
1. **概率提升（软保底）**：传说从第 74 抽开始概率线性提升，至第 89 抽
   达到 100%；期望出货约 62 抽
2. **硬保底**：累计 90 抽必出传说
3. **十连保底**：每十连内必出史诗（4★）及以上
4. **奖池仅出未解锁武器**：已拥有的不再进入奖池（全解锁后返还金币）
5. **抽取记录**：完整保留每次抽取的品质与武器，可查看统计

## 老虎机

消耗金币玩三轴老虎机，按符号倍率返还。
"""
import random

# ======================================================================
# 品质定义（weight 为内部相对权重，实际概率由 _roll_quality 精确控制）
# ======================================================================
QUALITY_COMMON = "common"
QUALITY_FINE = "fine"
QUALITY_RARE = "rare"
QUALITY_EPIC = "epic"
QUALITY_LEGEND = "legend"

QUALITY_META = {
    QUALITY_COMMON: {"name": "普通", "star": 1, "color": (200, 200, 200), "weight": 400},
    QUALITY_FINE:   {"name": "精良", "star": 2, "color": (110, 220, 130), "weight": 343},
    QUALITY_RARE:   {"name": "稀有", "star": 3, "color": (90, 170, 255),  "weight": 200},
    QUALITY_EPIC:   {"name": "史诗", "star": 4, "color": (200, 120, 255), "weight": 51},
    QUALITY_LEGEND: {"name": "传说", "star": 5, "color": (255, 200, 80),  "weight": 6},
}

#: 稀有度 → 品质
STAR_TO_QUALITY = {v["star"]: k for k, v in QUALITY_META.items()}

# ---------------- 保底参数（米哈游式） ----------------
LEGEND_BASE_RATE = 0.006       # 5★ 基础概率 0.6%
LEGEND_PITY_START = 74         # 从第 74 抽开始概率提升
LEGEND_HARD_PITY = 90          # 90 抽硬保底
LEGEND_PITY_STEP = 0.06        # 每抽提升 6%（第 74 抽起约 0.6%→100%）

EPIC_BASE_RATE = 0.051         # 4★ 基础概率 5.1%
EPIC_PITY = 10                 # 10 抽保底 4★及以上

#: 单抽价格
GACHA_COST_ONE = 160
#: 抽到已有武器（理论上不会发生）时的金币返还
DUPLICATE_REFUND = 3000

# ======================================================================
# 老虎机
# ======================================================================
#: 倍率转子符号（第 4~6 轴）
# v2.9.7：倍率档位大幅上调（原 ×2~×10 → ×5~×10000），配合"最多加 3 个
# 倍率转子"的玩法，追求"高风险高回报"。高倍率权重极低，避免期望爆炸。
SLOT_MULTIPLIERS = [
    {"key": "x5",   "name": "×5",    "payout": 5,     "weight": 40,
     "color": (120, 200, 255)},
    {"key": "x10",  "name": "×10",   "payout": 10,    "weight": 26,
     "color": (160, 230, 160)},
    {"key": "x25",  "name": "×25",   "payout": 25,    "weight": 15,
     "color": (255, 210, 120)},
    {"key": "x50",  "name": "×50",   "payout": 50,    "weight": 9,
     "color": (255, 160, 90)},
    {"key": "x100", "name": "×100",  "payout": 100,   "weight": 6,
     "color": (255, 120, 180)},
    {"key": "x500", "name": "×500",  "payout": 500,   "weight": 3,
     "color": (255, 90, 220)},
    {"key": "x1000", "name": "×1000", "payout": 1000,  "weight": 1.0,
     "color": (255, 80, 80)},
    {"key": "x10000", "name": "×10000", "payout": 10000, "weight": 0.15,
     "color": (255, 60, 40)},
]

SLOT_SYMBOLS = [
    {"key": "skull",  "name": "头骨", "weight": 30, "payout": 2},
    {"key": "bullet", "name": "子弹", "weight": 26, "payout": 3},
    {"key": "medkit", "name": "医疗包", "weight": 20, "payout": 5},
    {"key": "gear",   "name": "齿轮",  "weight": 14, "payout": 10},
    {"key": "crown",  "name": "王冠",  "weight": 8,  "payout": 25},
    {"key": "virus",  "name": "病毒",  "weight": 2,  "payout": 100},
]
#: v2.9.7：单次派彩上限，避免 ×10000 档击穿经济系统
SLOT_PAYOUT_CAP = 5_000_000
SLOT_BET_MIN = 50
SLOT_BET_MAX = 2000
SLOT_PAIR_RATE = 0.4


# ======================================================================
# 军械库补给
# ======================================================================
class WeaponGacha:
    """武器抽取（米哈游式保底）

    pool:     [{"key", "name", "quality", ...}, ...]
    unlocked: set(已解锁武器 key)

    保底计数需要跨会话持久化 → 用 `to_save()` / `from_save()`。
    """

    def __init__(self, pool=None, unlocked=None, rng=None,
                 pity_legend=0, pity_epic=0, history=None):
        self.pool = list(pool or [])
        self.unlocked = set(unlocked or [])
        self.rng = rng or random
        #: 传说保底计数（距离上次出 5★ 已抽多少）
        self.pity_legend = int(pity_legend or 0)
        #: 史诗保底计数（距离上次出 4★+ 已抽多少）
        self.pity_epic = int(pity_epic or 0)
        #: 抽取记录 [(key, name, quality, star, pity_legend_at)]
        self.history = list(history or [])

    # ---------------- 池 ----------------
    def available(self):
        """可用奖池（仅未解锁武器）"""
        return [_w for _w in self.pool if _w.get("key") not in self.unlocked]

    def pool_empty(self):
        return not self.available()

    def set_unlocked(self, keys):
        self.unlocked = set(keys or [])

    # ---------------- 概率 ----------------
    def legend_rate(self):
        """当前 5★ 概率（含概率提升）"""
        if self.pity_legend >= LEGEND_HARD_PITY - 1:
            return 1.0
        if self.pity_legend >= LEGEND_PITY_START - 1:
            _n = self.pity_legend - (LEGEND_PITY_START - 1) + 1
            return min(1.0, LEGEND_BASE_RATE + _n * LEGEND_PITY_STEP)
        return LEGEND_BASE_RATE

    def _legend_rate_at(self, pity):
        """指定保底位的 5★ 概率（用于绘制概率曲线）"""
        if pity >= LEGEND_HARD_PITY - 1:
            return 1.0
        if pity >= LEGEND_PITY_START - 1:
            _n = pity - (LEGEND_PITY_START - 1) + 1
            return min(1.0, LEGEND_BASE_RATE + _n * LEGEND_PITY_STEP)
        return LEGEND_BASE_RATE

    def _roll_quality(self):
        """掷一次品质（考虑保底与概率提升）"""
        _r5 = self.legend_rate()
        _r = self.rng.random()
        if _r < _r5:
            return QUALITY_LEGEND
        # 4★：保底 10 抽，或基础概率
        if self.pity_epic >= EPIC_PITY - 1:
            return QUALITY_EPIC
        if _r < _r5 + EPIC_BASE_RATE:
            return QUALITY_EPIC
        # 3★ / 2★ / 1★ 按权重
        _rest = self.rng.random() * (
            QUALITY_META[QUALITY_RARE]["weight"]
            + QUALITY_META[QUALITY_FINE]["weight"]
            + QUALITY_META[QUALITY_COMMON]["weight"])
        if _rest < QUALITY_META[QUALITY_RARE]["weight"]:
            return QUALITY_RARE
        if _rest < (QUALITY_META[QUALITY_RARE]["weight"]
                    + QUALITY_META[QUALITY_FINE]["weight"]):
            return QUALITY_FINE
        return QUALITY_COMMON

    # ---------------- 抽取 ----------------
    def _pick_of(self, quality, candidates=None):
        """从指定品质中挑一把（池内无此品质时降级取最高品质）"""
        _cand = candidates if candidates is not None else self.available()
        if not _cand:
            return None
        _same = [_w for _w in _cand if _w.get("quality") == quality]
        if _same:
            return self.rng.choice(_same)
        # 池内没有该品质 → 取池里最好的
        _order = [QUALITY_LEGEND, QUALITY_EPIC, QUALITY_RARE,
                  QUALITY_FINE, QUALITY_COMMON]
        for _q in _order:
            _s = [_w for _w in _cand if _w.get("quality") == _q]
            if _s:
                return self.rng.choice(_s)
        return self.rng.choice(_cand)

    def draw_one(self):
        """单抽：返回 dict 或 None（奖池为空）

        返回 {weapon, quality, star, name, pity, new}
        """
        _cand = self.available()
        if not _cand:
            return None
        _q = self._roll_quality()
        _w = self._pick_of(_q, _cand)
        if _w is None:
            return None
        self.pity_legend += 1
        if _q in (QUALITY_LEGEND, QUALITY_EPIC):
            self.pity_epic = 0
        else:
            self.pity_epic += 1
        if _q == QUALITY_LEGEND:
            self.pity_legend = 0
        _new = _w.get("key") not in self.unlocked
        self.unlocked.add(_w.get("key"))
        _rec = {
            "weapon": _w,
            "key": _w.get("key"),
            "name": _w.get("name", _w.get("key")),
            "quality": _q,
            "star": QUALITY_META.get(_q, {}).get("star", 1),
            "pity": self.pity_legend,
            "new": _new,
        }
        self.history.append(_rec)
        if len(self.history) > 500:
            self.history = self.history[-500:]
        return _rec

    def draw_many(self, n=10):
        """十连：返回 [记录, ...]，内含 4★ 保底"""
        _out = []
        for _i in range(max(1, int(n))):
            # 最后一发时若本轮无 4★+ 则强制
            _is_last = (_i == int(n) - 1)
            if _is_last and not any(
                    r.get("quality") in (QUALITY_EPIC, QUALITY_LEGEND)
                    for r in _out):
                _cand = self.available()
                if _cand:
                    _w = self._pick_of(QUALITY_EPIC, _cand)
                    if _w is not None:
                        self.pity_legend += 1
                        self.pity_epic = 0
                        _new = _w.get("key") not in self.unlocked
                        self.unlocked.add(_w.get("key"))
                        _rec = {"weapon": _w, "key": _w.get("key"),
                                "name": _w.get("name"), "quality": QUALITY_EPIC,
                                "star": 4, "pity": self.pity_legend, "new": _new}
                        self.history.append(_rec)
                        _out.append(_rec)
                        continue
            _r = self.draw_one()
            if _r is None:
                break
            _out.append(_r)
        return _out

    # ---------------- 价格 / 统计 ----------------
    def price(self, n=1):
        _n = max(1, int(n))
        return GACHA_COST_ONE * _n          # 十连不额外优惠（与米哈游一致）

    def stats(self):
        """抽取统计：总抽数、各品质数量、5★ 平均出货抽数"""
        _h = self.history
        _total = len(_h)
        _by = {}
        for _r in _h:
            _by[_r.get("quality")] = _by.get(_r.get("quality"), 0) + 1
        _legend_pos = [i + 1 for i, _r in enumerate(_h)
                       if _r.get("quality") == QUALITY_LEGEND]
        _avg = (sum(_legend_pos) / len(_legend_pos)) if _legend_pos else 0
        return {"total": _total, "by_quality": _by,
                "legend_count": len(_legend_pos),
                "avg_legend_pull": round(_avg, 1)}

    # ---------------- 持久化 ----------------
    def to_save(self):
        return {"pity_legend": self.pity_legend,
                "pity_epic": self.pity_epic,
                "history": [{"key": _r.get("key"), "name": _r.get("name"),
                             "quality": _r.get("quality"),
                             "pity": _r.get("pity")} for _r in self.history]}

    def from_save(self, data):
        if not isinstance(data, dict):
            return self
        self.pity_legend = int(data.get("pity_legend", 0) or 0)
        self.pity_epic = int(data.get("pity_epic", 0) or 0)
        _h = data.get("history") or []
        self.history = [dict(_r) for _r in _h][-500:]
        return self


# ======================================================================
# 老虎机
# ======================================================================
class SlotMachine:
    """老虎机：可加注 + 倍率转子，最多 6 轴

    v2.8.9 升级：
      * **倍率转子（extra reels）**：基础 3 轴，可花金币追加到最多 6 轴。
        每多一轴，全部相同（头奖）的倍率大幅提高，但中头奖也更难。
      * **加注**：每轴独立下注，总注 = 单注 × 轴数。
      * 倍率转子轴用不同符号集（×2 / ×3 / ×5 / ×10），命中即乘到派彩上。
    """

    #: 轴数范围
    MIN_REELS = 3
    MAX_REELS = 6
    #: 每追加一轴的解锁费用（一次性）
    REEL_UNLOCK_COST = {4: 800, 5: 2000, 6: 5000}
    #: 头奖倍率随轴数递增（越多轴越难但倍率越高）
    JACKPOT_SCALE = {3: 1.0, 4: 2.6, 5: 6.5, 6: 15.0}

    def __init__(self, rng=None):
        self.rng = rng or random
        self.last_spin = None
        self.last_payout = 0
        #: 已解锁的轴数（默认 3）
        self.reels = self.MIN_REELS
        self.spin_reels = [None] * self.MAX_REELS
        self.reel_angle = [0.0] * self.MAX_REELS
        self.spinning = False
        self.spin_timer = 0.0

    # ---------------- 轴数管理 ----------------
    def unlock_cost(self, target=None):
        """解锁到 target 轴的费用"""
        _t = int(target or (self.reels + 1))
        return int(self.REEL_UNLOCK_COST.get(_t, 0))

    def can_unlock(self, coins, target=None):
        _t = int(target or (self.reels + 1))
        if _t <= self.reels or _t > self.MAX_REELS:
            return False
        return int(coins) >= self.unlock_cost(_t)

    def unlock_reel(self, coins, target=None):
        """花金币解锁一轴，返回 (成功, 花费)"""
        _t = int(target or (self.reels + 1))
        if not self.can_unlock(coins, _t):
            return False, 0
        _c = self.unlock_cost(_t)
        self.reels = _t
        return True, _c

    def set_bet(self, bet):
        """设置单轴下注（自动钳制）"""
        try:
            _b = int(bet)
        except Exception:
            _b = 0
        self.bet = max(0, min(SLOT_BET_MAX, _b))
        return self.bet

    def total_bet(self, bet=None):
        """总注 = 单注 × 轴数"""
        _b = self.bet if bet is None else max(0, min(SLOT_BET_MAX, int(bet or 0)))
        return int(_b) * int(self.reels)

    def jackpot_scale(self):
        return float(self.JACKPOT_SCALE.get(self.reels, 1.0))

    def _roll_multiplier(self):
        """掷倍率轴"""
        # v2.9.7：改为按 SLOT_MULTIPLIERS 里的 weight 做加权抽取。
        # 高倍率（×1000 / ×10000）权重极低但确实存在，保证"能到 10000 倍"
        # 又不会让期望爆炸（期望倍率 ≈ 21）。
        _items = list(SLOT_MULTIPLIERS or [])
        if not _items:
            return {"key": "x1", "name": "×1", "payout": 1, "color": (200, 200, 200)}
        _ws = [float(_s.get("weight", 1) or 1) for _s in _items]
        try:
            return self.rng.choices(_items, weights=_ws, k=1)[0]
        except Exception:
            _tot = sum(_ws) or 1
            _r = self.rng.random() * _tot
            _acc = 0.0
            for _s, _w in zip(_items, _ws):
                _acc += _w
                if _r <= _acc:
                    return _s
            return _items[0]

    def _roll_symbol(self):
        _total = sum(_s["weight"] for _s in SLOT_SYMBOLS) or 1
        _r = self.rng.random() * _total
        for _s in SLOT_SYMBOLS:
            _r -= _s["weight"]
            if _r <= 0:
                return _s
        return SLOT_SYMBOLS[0]

    def spin(self, bet, reels=None):
        """旋转：前 3 轴是符号轴，第 4~6 轴是倍率轴

        派彩 = 单注 × 符号倍率 × 轴数缩放 × 倍率轴乘积
        """
        try:
            _bet = int(bet)
        except Exception:
            _bet = 0
        _bet = max(0, min(SLOT_BET_MAX, _bet))
        self.bet = _bet
        _n = int(reels or self.reels)
        _n = max(self.MIN_REELS, min(self.MAX_REELS, _n))

        # 符号轴（前 3）
        _sym = [self._roll_symbol() for _ in range(self.MIN_REELS)]
        _keys = [_s["key"] for _s in _sym]
        self.spin_reels = list(_sym) + [None] * (self.MAX_REELS - len(_sym))

        # 倍率轴（第 4~6）
        _mult = 1.0
        for _i in range(self.MIN_REELS, _n):
            _m = self._roll_multiplier()
            self.spin_reels[_i] = _m
            # 几何平均削弱：每个倍率轴贡献 = payout^(1/轴数)，
            # 保证"轴越多越刺激"但期望不会指数爆炸
            # v2.9.7：削弱指数 0.28 → 0.42，让高倍率（×1000/×10000）真正
            # 在派彩上"看得见"，同时期望仍受控（6 轴 RTP ≈ 80%）。
            _mult *= float(_m.get("payout", 1)) ** (0.32 / max(1, _n - self.MIN_REELS))

        if _keys[0] == _keys[1] == _keys[2]:
            _payout = int(_bet * _sym[0]["payout"] * self.jackpot_scale() * _mult)
            _payout = min(_payout, SLOT_PAYOUT_CAP)
            _kind = "jackpot"
        elif (_keys[0] == _keys[1] or _keys[1] == _keys[2]
              or _keys[0] == _keys[2]):
            _payout = min(int(_bet * SLOT_PAIR_RATE * _mult), SLOT_PAYOUT_CAP)
            _kind = "pair"
        else:
            _payout = 0
            _kind = "none"
        _all = [x for x in self.spin_reels if x is not None]
        _res = {"bet": _bet, "reels": _all,
                "reel_names": [_s["name"] for _s in _all],
                "payout": _payout, "win": _payout > 0,
                "kind": _kind, "net": _payout - _bet}
        self.last_spin = _res
        self.last_payout = _payout
        return _res

    def clamp_bet(self, bet):
        try:
            return max(SLOT_BET_MIN, min(SLOT_BET_MAX, int(bet)))
        except Exception:
            return SLOT_BET_MIN


# ======================================================================
# v2.8.9 军械库补给 · 米哈游式抽卡（Genshin-style）
# ----------------------------------------------------------------------
# 与原 draw_one 的区别：
#   * 引入**保底（pity）**：连续未出高星 → 概率递增 → 硬保底必出
#   * 引入**UP 限定**与**大保底**：歪了下次必出 UP
#   * 十连必出 4 星及以上
#   * 赌博性更强：单抽价格固定，**出货率上调但不出就等于金币全没**（不返还）
# ======================================================================

STAR_5 = 5
STAR_4 = 4
STAR_3 = 3

#: 星级品质映射（武器按品质映射到星级）
QUALITY_TO_STAR = {
    "legend": STAR_5,
    "epic": STAR_4,
    "rare": STAR_3,
    "fine": STAR_3,
    "common": STAR_3,
}

#: 米哈游式参数
PITY_5_HARD = 80          # 5 星硬保底（原神 90，这里调低更爽快）
PITY_5_SOFT = 62          # 5 星软保底起点（之后概率线性飙升）
PITY_4_HARD = 10          # 4 星十连保底
RATE_5_BASE = 0.030       # 5 星基础概率 3%（**上调**，原神 0.6%）
RATE_4_BASE = 0.13        # 4 星基础概率 13%
RATE_5_SOFT_STEP = 0.06   # 软保底后每抽递增 6%
UP_RATE = 0.5             # 出 5 星时是 UP 的概率（50%，歪了下次大保底）

#: 同一把武器最多叠加到几级（抽满即出池）
MAX_LEVEL = 5

GACHA_COST_SINGLE = 160   # 单抽花费
GACHA_COST_TEN = 1600     # 十连（= 10 抽，不打折但保底更稳）


class GachaBanner:
    """一期卡池：UP 武器 + 常驻池

    pity5 / pity4         当前保底计数
    guarantee_up          大保底标记（上次歪了 → 本次必出 UP）
    """

    #: 单武器叠加上限（类级，便于外部引用）
    MAX_LEVEL = 5

    def __init__(self, pool, up_keys=None, unlocked=None, rng=None):
        self.pool = list(pool or [])
        self.up_keys = list(up_keys or [])
        self.unlocked = set(unlocked or [])
        self.rng = rng or random
        #: 每把武器的叠加等级（重复抽中 +1，上限 MAX_LEVEL）
        self.levels = {}
        self.pity5 = 0
        self.pity4 = 0
        self.guarantee_up = False
        #: 历史记录（供保底展示/统计）
        self.history = []

    # ---------------- 池 ----------------
    def available(self):
        """可出货武器：未解锁的，或已解锁但未满级（重复抽取叠加等级）

        v2.8.9：同一把武器最多被抽到 5 次（1 级 + 4 次叠加 = Lv.5），
        满级后不再进入奖池；全部满级/解锁后奖池为空。
        """
        _out = []
        for _w in self.pool:
            _k = _w.get("key")
            if _k not in self.unlocked:
                _out.append(_w)
            elif (self.levels.get(_k, 1) or 1) < self.MAX_LEVEL:
                _out.append(_w)
        return _out

    def pool_empty(self):
        return not self.available()

    def _star_of(self, w):
        return QUALITY_TO_STAR.get(w.get("quality", "common"), STAR_3)

    def _pick_by_star(self, star, candidates):
        """从候选里挑指定星级的武器"""
        _same = [_w for _w in candidates if self._star_of(_w) == star]
        return _same or list(candidates)

    # ---------------- 单抽 ----------------
    def _roll_star(self):
        """按保底规则掷星级"""
        # 硬保底
        if self.pity5 + 1 >= PITY_5_HARD:
            return STAR_5
        if self.pity4 + 1 >= PITY_4_HARD:
            # 十连保底：至少 4 星（不触发 5 星硬保底时）
            pass
        # 软保底递增
        _r5 = RATE_5_BASE
        if self.pity5 + 1 > PITY_5_SOFT:
            _r5 += (self.pity5 + 1 - PITY_5_SOFT) * RATE_5_SOFT_STEP
        _r = self.rng.random()
        if _r < _r5:
            return STAR_5
        # 4 星（含十连保底）
        _r4 = RATE_4_BASE
        if self.pity4 + 1 >= PITY_4_HARD:
            _r4 = 1.0
        if _r < _r5 + _r4:
            return STAR_4
        return STAR_3

    def draw_one(self):
        """单抽：返回 dict {weapon, star, is_up, pity5, pity4, new}

        赌博性：无论出什么，**花费的金币都不返还**；
        出货率已上调，但"没出想要的就是全没"。
        """
        _cand = self.available()
        if not _cand:
            return None
        _star = self._roll_star()

        _is_up = False
        if _star == STAR_5:
            # UP 判定：大保底必 UP，否则 50%
            _up_pool = [_w for _w in _cand if _w.get("key") in self.up_keys]
            if self.guarantee_up and _up_pool:
                _pick = self.rng.choice(_up_pool)
                _is_up = True
                self.guarantee_up = False
            elif _up_pool and self.rng.random() < UP_RATE:
                _pick = self.rng.choice(_up_pool)
                _is_up = True
            else:
                _non_up = [_w for _w in _cand if _w.get("key") not in self.up_keys]
                _pick = self.rng.choice(_non_up or _cand)
                _is_up = False
                # 歪了 → 下次大保底
                self.guarantee_up = True
            self.pity5 = 0
            self.pity4 += 0
        elif _star == STAR_4:
            _pick = self.rng.choice(self._pick_by_star(STAR_4, _cand))
            self.pity4 = 0
            self.pity5 += 1
        else:
            _pick = self.rng.choice(self._pick_by_star(STAR_3, _cand))
            self.pity4 += 1
            self.pity5 += 1

        _key = _pick.get("key")
        _dup = _key in self.unlocked
        if _dup:
            _lv = min(MAX_LEVEL, int(self.levels.get(_key, 1) or 1) + 1)
            self.levels[_key] = _lv
        else:
            self.unlocked.add(_key)
            self.levels[_key] = 1
            _lv = 1
        _res = {
            "level": _lv,
            "dup": _dup,
            "maxed": _lv >= MAX_LEVEL,
            "weapon": _pick,
            "star": _star,
            "is_up": _is_up,
            "pity5": self.pity5,
            "pity4": self.pity4,
            "guarantee": self.guarantee_up,
            "new": True,
        }
        self.history.append(_res)
        return _res

    def draw_many(self, n=10):
        """十连：返回 [result, ...]，并保证至少 4 星"""
        _out = []
        for _ in range(max(1, int(n))):
            _r = self.draw_one()
            if _r is None:
                break
            _out.append(_r)
        # 十连保底：全 3 星则把最后一发改 4 星
        if _out and all(_x["star"] == STAR_3 for _x in _out):
            _cand4 = [_w for _w in self.available()
                      if self._star_of(_w) == STAR_4]
            if _cand4:
                _pick = self.rng.choice(_cand4)
                self.unlocked.add(_pick.get("key"))
                _k2 = _pick.get("key")
                _dup2 = _k2 in self.unlocked
                if _dup2:
                    _lv2 = min(MAX_LEVEL, int(self.levels.get(_k2, 1) or 1) + 1)
                    self.levels[_k2] = _lv2
                else:
                    self.unlocked.add(_k2); self.levels[_k2] = 1; _lv2 = 1
                _out[-1] = {"weapon": _pick, "star": STAR_4, "is_up": False,
                            "pity5": self.pity5, "pity4": 0,
                            "guarantee": self.guarantee_up, "new": True,
                            "level": _lv2, "dup": _dup2,
                            "maxed": _lv2 >= MAX_LEVEL}
        return _out

    # ---------------- 价格 ----------------
    @staticmethod
    def cost(n=1):
        return GACHA_COST_TEN if int(n) >= 10 else GACHA_COST_SINGLE * max(1, int(n))

    # ---------------- 存档 / 价格 ----------------
    def to_save(self):
        """保底计数必须跨会话保留，否则玩家读档后保底清零"""
        return {"pity5": self.pity5, "pity4": self.pity4,
                "guarantee_up": self.guarantee_up,
                "levels": dict(self.levels),
                "unlocked": sorted(self.unlocked)}

    def from_save(self, d):
        try:
            self.pity5 = int((d or {}).get("pity5", 0) or 0)
            self.pity4 = int((d or {}).get("pity4", 0) or 0)
            self.guarantee_up = bool((d or {}).get("guarantee_up", False))
            self.levels = dict((d or {}).get("levels", {}) or {})
            self.unlocked = set((d or {}).get("unlocked", []) or [])
        except Exception:
            pass

    def price(self, n=1):
        """兼容旧调用：单抽 / 十连价格"""
        return self.cost(n)

    # ---------------- 保底展示 ----------------
    def pity_info(self):
        """保底进度（供 UI 显示）"""
        return {
            "pity5": self.pity5,
            "pity4": self.pity4,
            "to_hard5": max(0, PITY_5_HARD - self.pity5),
            "to_hard4": max(0, PITY_4_HARD - self.pity4),
            "guarantee_up": self.guarantee_up,
            "soft": self.pity5 >= PITY_5_SOFT,
        }


# ======================================================================
# v2.9.0 UP 卡池轮换
# ----------------------------------------------------------------------
# 每期 UP 由「期数」决定，期数按 UTC 天数推进（也可手动指定或由数据库配置）。
# 策划只需在数据库 gacha_banners 表里配置每期 UP，或让代码自动轮换。
# ======================================================================

#: 每期持续天数
BANNER_PERIOD_DAYS = 14
#: 每期 UP 数量
BANNER_UP_COUNT = 4


def banner_index(now_ts=None, period_days=BANNER_PERIOD_DAYS):
    """当前期数（按 UTC 天数）"""
    try:
        import time as _t
        _ts = float(now_ts if now_ts is not None else _t.time())
        return int(_ts // 86400) // max(1, int(period_days))
    except Exception:
        return 0


def build_up_keys(pool, index=None, count=BANNER_UP_COUNT):
    """按期数轮换 UP：把池按稀有度分层，每期取不同的一批

    保证：同一把武器不会连续两期都是 UP（增加新鲜感）。
    """
    _rank = {"legend": 5, "epic": 4, "rare": 3, "fine": 2, "common": 1}
    _srt = sorted(pool or [],
                  key=lambda w: (-_rank.get(w.get("quality", "common"), 1),
                                 str(w.get("key", ""))))
    if not _srt:
        return []
    _n = max(1, int(count))
    _i = int(index or 0)
    _out = []
    # 从高稀有度段里按期数偏移取，形成轮换
    _offset = (_i * _n) % max(1, len(_srt))
    for _k in range(_n):
        _out.append(str(_srt[(_offset + _k) % len(_srt)].get("key")))
    return _out


def load_up_keys_from_db(db, pool, index=None):
    """从数据库读本期 UP（表不存在则回退自动轮换）"""
    try:
        _row = db.row("gacha_banners", str(int(index or 0)))
        if _row:
            import json as _j
            _v = _row.get("up_keys")
            if isinstance(_v, str):
                _v = _j.loads(_v)
            if _v:
                return list(_v)
    except Exception:
        pass
    return build_up_keys(pool, index)


# ======================================================================
# v2.8.9 抽卡画面效果（GachaFx）
# ----------------------------------------------------------------------
# 参考米哈游的出货演出：
#   * 抽卡时屏幕渐暗 + 光柱升起
#   * 3 星蓝光 / 4 星紫光 / 5 星金光（5 星额外有流星与光晕脉冲）
#   * 出货后卡片由小放大弹出 + 星级逐颗点亮
# 纯绘制，不跑帧也可单步调用；游戏内由 UI 层驱动。
# ======================================================================

class SlotSpinAnim:
    """v2.9.6 老虎机转子动画

    此前 do_slot() 一调用就瞬间出结果 —— 转子从不转动，完全没有赌博的
    紧张感。现在改为：

    1. 每个轴**独立**旋转，并按顺序逐个停下（左 → 右）
    2. 停止前有减速过程（先快后慢），最后"咔"一下对齐
    3. 全部停下后才结算派彩 —— 中奖瞬间才有反馈

    动画由渲染层用真实时间推进（不依赖主循环 update，菜单态也能跑）。
    """

    #: 每个轴的基础转动时长（秒），越靠后停得越晚
    BASE_SPIN = 0.75
    #: 轴与轴之间的停止间隔（秒）
    STAGGER = 0.42
    #: 静止前最后的减速对齐时长（秒）
    SLOWDOWN = 0.35
    #: 滚动速度：每秒滚过多少个符号格
    SYMBOL_SPEED = 13.0

    def __init__(self):
        self.active = False
        self.reels = []          # 最终结果的符号列表
        self.count = 0
        self.t = 0.0             # 已进行时长（秒）
        self.stop_at = []        # 每轴停止时刻（秒）
        self.just_finished = False
        self.payout = 0
        self.kind = "none"

    # ---------------- 控制 ----------------
    def start(self, reels, now=None):
        """开始旋转。reels 为已算好的结果列表"""
        self.reels = list(reels or [])
        self.count = len(self.reels)
        self.t = 0.0
        self.active = self.count > 0
        self.just_finished = False
        self.stop_at = [self.BASE_SPIN + i * self.STAGGER
                        for i in range(self.count)]
        return self.active

    def update(self, dt):
        """推进动画，返回 True 表示**本帧刚好全部停下**"""
        if not self.active:
            return False
        self.t += max(0.0, float(dt))
        _last = self.stop_at[-1] if self.stop_at else 0.0
        if self.t >= _last + self.SLOWDOWN:
            self.active = False
            self.just_finished = True
            return True
        return False

    def skip(self):
        """跳过：立即全部停下"""
        if not self.active:
            return False
        self.t = self.stop_at[-1] + self.SLOWDOWN + 0.01 if self.stop_at else 0.0
        self.active = False
        self.just_finished = True
        return True

    # ---------------- 查询 ----------------
    def is_stopped(self, i):
        """第 i 轴是否已停稳"""
        if i >= len(self.stop_at):
            return True
        return self.t >= self.stop_at[i] + self.SLOWDOWN

    def progress_of(self, i):
        """第 i 轴的停止进度 0~1（用于减速对齐）"""
        if i >= len(self.stop_at):
            return 1.0
        _st = self.stop_at[i]
        if self.t <= _st:
            return 0.0
        return min(1.0, (self.t - _st) / self.SLOWDOWN)

    def offset_of(self, i):
        """第 i 轴当前的滚动偏移（单位：格），用于绘制连续滚动"""
        if self.is_stopped(i):
            return 0.0
        _p = self.progress_of(i)
        # 匀速滚动，进入减速段后用 ease-out 收敛到 0
        _t = max(0.0, self.t)
        _raw = _t * self.SYMBOL_SPEED
        if _p > 0.0:
            # 减速：把剩余滚动量按 (1-p)^2 衰减
            _ease = (1.0 - _p) ** 2
            _raw = _t * self.SYMBOL_SPEED * _ease
        return _raw - int(_raw)   # 只保留小数部分做循环偏移

    def symbol_index_of(self, i, pool):
        """第 i 轴当前应显示的符号在 pool 中的下标"""
        if not pool:
            return 0
        if self.is_stopped(i):
            try:
                _k = self.reels[i].get("key")
            except Exception:
                _k = None
            for _j, _s in enumerate(pool):
                if _s.get("key") == _k:
                    return _j
            return 0
        _t = max(0.0, self.t)
        return int(_t * self.SYMBOL_SPEED + i * 3) % len(pool)

    def flash_of(self, i):
        """刚停下时的闪光强度 0~1（用于"咔"一下的高亮）"""
        if i >= len(self.stop_at):
            return 0.0
        _st = self.stop_at[i]
        if self.t < _st:
            return 0.0
        _d = self.t - _st
        if _d > 0.45:
            return 0.0
        return 1.0 - _d / 0.45


class GachaFx:
    """v2.9.7 抽卡演出状态机（铺垫 → 闪光 → 分层揭示）

    v2.9.6 的问题是"铺垫不足、一下就知道是什么"：
      - 蓄力只有 0.85 秒，还没酝酿就出结果
      - REVEAL 一开始就把武器名完整画出来

    现在拆成三段：
      CHARGE (1.5s) 星尘汇聚、光束旋转、光柱蓄力 —— 只透露"品质光色"趋势
      FLASH  (0.4s) 闪光爆发，全屏被品质色吞没，仍**不显示名字**
      REVEAL (2.8s) 分层揭示：先星级逐颗点亮 → 再剪影 → 最后名字淡入
    """

    STAR_COLOR = {
        3: (90, 170, 255),     # 蓝
        4: (190, 120, 255),    # 紫
        5: (255, 200, 70),     # 金
    }
    STAR_NAME = {3: "3★", 4: "4★", 5: "5★"}
    QUALITY_NAME = {3: "精良", 4: "史诗", 5: "传说"}

    PHASE_IDLE = "idle"
    PHASE_CHARGE = "charge"     # 铺垫：星尘汇聚
    PHASE_FLASH = "flash"       # 闪光爆发（仍不揭示）
    PHASE_REVEAL = "reveal"     # 分层揭示

    def __init__(self):
        self.phase = self.PHASE_IDLE
        self.timer = 0.0
        self.global_t = 0.0
        self.results = []
        self.shown = 0
        self.charge_dur = 1.5      # v2.9.7：0.85 → 1.5，铺垫更足
        self.flash_dur = 0.40
        self.reveal_dur = 2.8
        self.shake = 0.0

    # ---------------- 控制 ----------------
    def play(self, results):
        """开始演出"""
        self.results = list(results or [])
        self.shown = 0
        self.phase = self.PHASE_CHARGE if self.results else self.PHASE_IDLE
        self.timer = 0.0
        self.global_t = 0.0
        return self.phase

    def skip(self):
        """跳过演出：直接跳到下一个阶段末尾"""
        if self.phase == self.PHASE_IDLE:
            return None
        self.timer = 0.0
        if self.phase == self.PHASE_CHARGE:
            self.phase = self.PHASE_FLASH
        elif self.phase == self.PHASE_FLASH:
            self.phase = self.PHASE_REVEAL
        elif self.phase == self.PHASE_REVEAL:
            # 多结果时逐个跳过，全部看完才结束
            self.shown += 1
            if self.shown >= len(self.results):
                self.phase = self.PHASE_IDLE
        return self.phase

    @property
    def active(self):
        return self.phase != self.PHASE_IDLE

    @property
    def cur(self):
        try:
            return self.results[self.shown]
        except Exception:
            return None

    def update(self, dt):
        if not self.active:
            return None
        dt = max(0.0, float(dt))
        self.timer += dt
        self.global_t += dt
        # 震动衰减
        self.shake = max(0.0, self.shake - dt * 3.2)
        if self.phase == self.PHASE_CHARGE:
            # 蓄力末段开始轻微震动，制造"要炸了"的预感
            _p = min(1.0, self.timer / self.charge_dur)
            if _p > 0.72:
                self.shake = max(self.shake, (_p - 0.72) / 0.28 * 0.55)
            if self.timer >= self.charge_dur:
                self.phase = self.PHASE_FLASH
                self.timer = 0.0
                self.shake = 1.0        # 闪光瞬间强震
        elif self.phase == self.PHASE_FLASH:
            if self.timer >= self.flash_dur:
                self.phase = self.PHASE_REVEAL
                self.timer = 0.0
        elif self.phase == self.PHASE_REVEAL:
            _per = self.reveal_dur / max(1, len(self.results))
            _idx = min(len(self.results) - 1, int(self.timer / _per))
            self.shown = _idx
            if self.timer >= self.reveal_dur:
                self.phase = self.PHASE_IDLE
                self.timer = 0.0
                return "done"
        return None

    # ---------------- 绘制 ----------------
    def draw(self, screen, font, font_small, scale=1.0):
        """在当前画面上叠加抽卡演出"""
        if not self.active:
            return
        try:
            import pygame
            import math
        except Exception:
            return
        _w, _h = screen.get_size()
        _res = self.cur
        _star = int((_res or {}).get("star", 3) or 3)
        _col = self.STAR_COLOR.get(_star, (200, 200, 200))

        if self.phase == self.PHASE_CHARGE:
            self._draw_charge(screen, _w, _h, scale, pygame, math, _col)
            return
        if self.phase == self.PHASE_FLASH:
            self._draw_flash(screen, _w, _h, scale, pygame, math, _col)
            return
        # ---- REVEAL：分层揭示 ----
        if _res is None:
            return
        _cx, _cy = _w // 2, _h // 2
        _t = self.timer
        _wn = ((_res.get("weapon") or {}).get("name") or "?")

        # 背景染色（随揭示推进变淡）
        _fade = max(0.0, 1.0 - _t / self.reveal_dur)
        _ov = pygame.Surface((_w, _h), pygame.SRCALPHA)
        _ov.fill((*_col[:3], int(90 * _fade)))
        screen.blit(_ov, (0, 0))

        # 光晕脉冲
        _pulse = 1.0 + 0.12 * math.sin(_t * 8.0)
        for _k in range(3):
            _r = int((90 + _k * 55) * scale * _pulse)
            _s2 = pygame.Surface((_w, _h), pygame.SRCALPHA)
            pygame.draw.circle(_s2, (*_col[:3], 30 - _k * 8), (_cx, _cy), _r)
            screen.blit(_s2, (0, 0))

        # 5 星流星
        if _star == 5:
            for _k in range(6):
                _ang = _t * 2.2 + _k * (math.tau / 6)
                _rr = (150 + 60 * math.sin(_t * 3 + _k)) * scale
                _sx = _cx + math.cos(_ang) * _rr
                _sy = _cy + math.sin(_ang) * _rr
                pygame.draw.circle(screen, _col, (int(_sx), int(_sy)),
                                   max(2, int(4 * scale)))

        # 卡片弹出
        _prog = min(1.0, _t / 0.35)
        _cw = int(300 * scale * (0.6 + 0.4 * _prog))
        _ch = int(400 * scale * (0.6 + 0.4 * _prog))
        _card = pygame.Rect(_cx - _cw // 2, _cy - _ch // 2, _cw, _ch)
        pygame.draw.rect(screen, (24, 22, 32), _card, border_radius=14)
        pygame.draw.rect(screen, _col, _card, max(2, int(4 * scale)),
                         border_radius=14)

        # ① 品质文字先出（0.15s 后）
        if _t > 0.15 and font is not None:
            _qn = self.QUALITY_NAME.get(_star, "")
            _qs = font.render(_qn, True, _col)
            screen.blit(_qs, (_cx - _qs.get_width() // 2,
                              _card.y + int(26 * scale)))

        # ② 星级逐颗点亮（每颗 0.18s）
        if font is not None:
            _star_t = max(0.0, _t - 0.35)
            _lit = int(_star_t / 0.18) + (1 if _star_t > 0 else 0)
            _lit = max(0, min(_star, _lit))
            _sy2 = _card.y + int(78 * scale)
            _ssz = int(22 * scale)
            for _k in range(_star):
                _gx = _cx - (_star - 1) * _ssz // 2 + _k * _ssz
                _on = _k < _lit
                _c2 = _col if _on else (80, 80, 95)
                pygame.draw.circle(screen, _c2, (_gx, _sy2),
                                   max(2, int(9 * scale)))
                if _on:
                    pygame.draw.circle(screen, (255, 255, 255), (_gx, _sy2),
                                       max(2, int(9 * scale)), 1)

        # ③ 剪影（0.6~1.1s）：只画一个暗色武器轮廓，看不出是什么
        if 0.6 < _t < 1.25:
            _a = 1.0 - abs(_t - 0.92) / 0.33
            _sr = pygame.Rect(_cx - int(70 * scale),
                              _card.y + int(120 * scale),
                              int(140 * scale), int(150 * scale))
            pygame.draw.rect(screen, (int(50 * _a) + 20, int(50 * _a) + 20,
                                      int(60 * _a) + 26), _sr, border_radius=8)

        # ④ 名字淡入（1.1s 后）
        if _t > 1.1 and font is not None:
            _na = min(1.0, (_t - 1.1) / 0.45)
            try:
                _ns = font.render(str(_wn), True, (245, 245, 255))
                _ns.set_alpha(int(255 * _na))
                screen.blit(_ns, (_cx - _ns.get_width() // 2,
                                  _card.y + int(150 * scale)))
            except Exception:
                pass

        # ⑤ 附加信息（等级 / 是否 UP）
        if _t > 1.5 and font_small is not None:
            _lv = int(_res.get("level", 1) or 1)
            _tag = ("重复 +1  Lv.%d" % _lv) if _res.get("dup") else "新获得"
            if _res.get("maxed"):
                _tag = "已满级"
            _ts = font_small.render(_tag, True, (210, 210, 225))
            screen.blit(_ts, (_cx - _ts.get_width() // 2,
                              _card.y + int(196 * scale)))
            if _res.get("is_up"):
                _us = font_small.render("UP!", True, (255, 150, 180))
                screen.blit(_us, (_cx - _us.get_width() // 2,
                                  _card.y + int(220 * scale)))

    # ---------------- 阶段绘制 ----------------
    def _draw_charge(self, screen, _w, _h, scale, pygame, math, _col):
        """铺垫：星尘汇聚 + 光束旋转 + 收缩光环"""
        _cx, _cy = _w // 2, _h // 2
        _t = self.timer
        _p = min(1.0, _t / self.charge_dur)

        # 逐渐变亮的暗幕
        _ov = pygame.Surface((_w, _h), pygame.SRCALPHA)
        _ov.fill((6, 5, 12, int(150 * _p)))
        screen.blit(_ov, (0, 0))

        # 8 道旋转光束
        _beam = pygame.Surface((_w, _h), pygame.SRCALPHA)
        for _k in range(8):
            _a = _t * 3.2 + _k * (math.tau / 8)
            _r0 = int((40 + 30 * math.sin(_t * 5 + _k)) * scale)
            _r1 = int(560 * scale)
            pygame.draw.line(_beam, (*_col[:3], int(46 * _p)),
                             (int(_cx + math.cos(_a) * _r0),
                              int(_cy + math.sin(_a) * _r0)),
                             (int(_cx + math.cos(_a) * _r1),
                              int(_cy + math.sin(_a) * _r1)),
                             max(2, int(5 * scale)))
        screen.blit(_beam, (0, 0))

        # 向中心汇聚的星尘
        for _k in range(26):
            _pk = (_k * 41) % 100 / 100.0
            _ph = (_pk * 6.0 + _t * 1.5) % 1.0        # 0→1 向内
            _rad = (380 * (1.0 - _ph) + 30) * scale
            _ang = _pk * math.tau * 3 + _t * 0.8
            _px = _cx + math.cos(_ang) * _rad
            _py = _cy + math.sin(_ang) * _rad
            _al = int(230 * _ph * _p)
            if _al > 8:
                pygame.draw.circle(screen, (*_col[:3], min(235, _al)),
                                   (int(_px), int(_py)),
                                   max(1, int((1.5 + 2.2 * _ph) * scale)))

        # 收缩光环（越到后面越紧）
        for _k in range(3):
            _rr = int((150 + _k * 70) * (1.0 - _p * 0.75) * scale)
            if _rr > 4:
                pygame.draw.circle(screen, _col, (_cx, _cy), _rr,
                                   max(1, int(2.5 * scale)))

    def _draw_flash(self, screen, _w, _h, scale, pygame, math, _col):
        """闪光爆发：品质色吞没全屏，仍不揭示内容"""
        _t = self.timer
        _p = min(1.0, _t / self.flash_dur)
        # 白闪 → 品质色
        if _p < 0.35:
            _a = int(255 * (1.0 - _p / 0.35))
            _ov = pygame.Surface((_w, _h), pygame.SRCALPHA)
            _ov.fill((255, 255, 255, _a))
            screen.blit(_ov, (0, 0))
        else:
            _q = (_p - 0.35) / 0.65
            _ov = pygame.Surface((_w, _h), pygame.SRCALPHA)
            _ov.fill((*_col[:3], int(190 * (1.0 - _q))))
            screen.blit(_ov, (0, 0))
        # 放射线
        _cx, _cy = _w // 2, _h // 2
        for _k in range(14):
            _a = _k * (math.tau / 14) + _t * 0.8
            _r1 = int(700 * scale)
            pygame.draw.line(screen, (255, 255, 255),
                             (int(_cx), int(_cy)),
                             (int(_cx + math.cos(_a) * _r1),
                              int(_cy + math.sin(_a) * _r1)),
                             max(1, int(3 * scale)))

    # ---------------- v2.9.7 增强 ----------------
    def draw_extra(self, screen, font_small, scale=1.0):
        """叠加：跳过提示 + 多结果进度 + 震动"""
        if not self.active:
            return
        try:
            import pygame
        except Exception:
            return
        _w, _h = screen.get_size()
        if font_small is not None:
            try:
                _tip = font_small.render("点击画面继续", True, (215, 215, 230))
                screen.blit(_tip, (_w // 2 - _tip.get_width() // 2,
                                   _h - int(38 * scale)))
            except Exception:
                pass
            if len(self.results) > 1:
                try:
                    _pg = font_small.render(
                        f"{min(len(self.results), self.shown + 1)} / {len(self.results)}",
                        True, (200, 200, 215))
                    screen.blit(_pg, (_w - _pg.get_width() - int(24 * scale),
                                      int(24 * scale)))
                except Exception:
                    pass

    def shake_offset(self, scale=1.0):
        """返回本帧震动偏移 (dx, dy)，供渲染层叠加"""
        if self.shake <= 0.001:
            return (0, 0)
        try:
            import math, time
            _a = time.time() * 60.0
            _m = self.shake * 9.0 * scale
            return (int(math.cos(_a) * _m), int(math.sin(_a * 1.7) * _m))
        except Exception:
            return (0, 0)

