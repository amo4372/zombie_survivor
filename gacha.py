# -*- coding: utf-8 -*-
"""军械库补给（武器抽奖）+ 老虎机 —— v2.8.8

## 军械库补给（武器抽奖）

花费金币抽取武器：
- **奖池必出武器**（不会空手而归）
- **奖池仅出未解锁武器**（已拥有的不再进入奖池，
  全部解锁后奖池为空 → 提示"军械库已全收集"）
- 不同品质概率不同：普通 > 精良 > 稀有 > 史诗 > 传说

## 老虎机（赌博）

消耗金币玩一局，三轴旋转：
- 三个相同符号 → 按倍率返还金币（可能回本、小赚、暴富）
- 两个相同 → 小额返还
- 全不同 → 无返还
带"庄家优势"（期望略小于 1），但保留暴富可能性。
"""
import random

# ======================================================================
# 品质定义
# ======================================================================
QUALITY_COMMON = "common"
QUALITY_FINE = "fine"
QUALITY_RARE = "rare"
QUALITY_EPIC = "epic"
QUALITY_LEGEND = "legend"

QUALITY_META = {
    QUALITY_COMMON: {"name": "普通", "color": (200, 200, 200), "weight": 60, "price": 120},
    QUALITY_FINE:   {"name": "精良", "color": (110, 220, 130), "weight": 25, "price": 200},
    QUALITY_RARE:   {"name": "稀有", "color": (90, 170, 255),  "weight": 10, "price": 320},
    QUALITY_EPIC:   {"name": "史诗", "color": (200, 120, 255), "weight": 4,  "price": 520},
    QUALITY_LEGEND: {"name": "传说", "color": (255, 200, 80),  "weight": 1,  "price": 880},
}

#: 单抽基础价；实际价格 = 该品质权重归一后按期望定价
GACHA_BASE_PRICE = 150
#: 十连保底：十连内至少出现该品质及以上
GACHA_PITY_QUALITY = QUALITY_RARE

# ======================================================================
# 老虎机
# ======================================================================
SLOT_SYMBOLS = [
    {"key": "skull",  "name": "头骨", "weight": 30, "payout": 2},
    {"key": "bullet", "name": "子弹", "weight": 26, "payout": 3},
    {"key": "medkit", "name": "医疗包", "weight": 20, "payout": 5},
    {"key": "gear",   "name": "齿轮",  "weight": 14, "payout": 10},
    {"key": "crown",  "name": "王冠",  "weight": 8,  "payout": 25},
    {"key": "virus",  "name": "病毒",  "weight": 2,  "payout": 100},
]
SLOT_BET_MIN = 50
SLOT_BET_MAX = 2000
#: 两轴相同的返还比例（相对下注额）
SLOT_PAIR_RATE = 0.4


# ======================================================================
# 军械库补给
# ======================================================================
class WeaponGacha:
    """武器抽奖

    pool: [{"key", "name", "quality", ...}, ...] 武器池
    unlocked: set(已解锁的武器 key)
    """

    def __init__(self, pool=None, unlocked=None, rng=None):
        self.pool = list(pool or [])
        self.unlocked = set(unlocked or [])
        self.rng = rng or random
        #: 保底计数：连续未出稀有及以上
        self.pity_count = 0

    # ---------------- 池 ----------------
    def available(self):
        """可用奖池（仅**未解锁**武器）"""
        return [_w for _w in self.pool
                if _w.get("key") not in self.unlocked]

    def pool_empty(self):
        return not self.available()

    def set_unlocked(self, keys):
        self.unlocked = set(keys or [])

    # ---------------- 抽 ----------------
    def _pick_quality(self):
        """按品质权重抽取（带保底）"""
        _cand = self.available()
        if not _cand:
            return None
        # 池内实际存在的品质（避免抽到一个池里没有的品质）
        _qs = {}
        for _w in _cand:
            _q = _w.get("quality", QUALITY_COMMON)
            _qs[_q] = _qs.get(_q, 0) + 1
        if not _qs:
            return None
        # 保底：连续 9 次未出稀有及以上 → 本次强制稀有及以上
        _force = self.pity_count >= 9
        _items = []
        for _q, _n in _qs.items():
            if _force and _q not in (QUALITY_RARE, QUALITY_EPIC, QUALITY_LEGEND):
                continue
            _items.append((_q, QUALITY_META.get(_q, {}).get("weight", 1)))
        if not _items:
            _items = [(_q, 1) for _q in _qs.keys()]
        _total = sum(_w for _, _w in _items) or 1
        _r = self.rng.random() * _total
        for _q, _w in _items:
            _r -= _w
            if _r <= 0:
                return _q
        return _items[0][0]

    def draw_one(self):
        """单抽：返回 (武器dict, 品质) 或 (None, None)（奖池为空）"""
        _cand = self.available()
        if not _cand:
            return None, None
        _q = self._pick_quality() or QUALITY_COMMON
        _same = [_w for _w in _cand if _w.get("quality", QUALITY_COMMON) == _q]
        if not _same:
            _same = _cand
        _pick = self.rng.choice(_same)
        # 保底计数
        if _q in (QUALITY_RARE, QUALITY_EPIC, QUALITY_LEGEND):
            self.pity_count = 0
        else:
            self.pity_count += 1
        self.unlocked.add(_pick.get("key"))
        return _pick, _q

    def draw_many(self, n=10):
        """十连（含保底）：返回 [(武器, 品质), ...]"""
        _out = []
        for _i in range(max(1, int(n))):
            _w, _q = self.draw_one()
            if _w is None:
                break
            _out.append((_w, _q))
        # 十连保底：若全为普通/精良，把最后一发换成稀有及以上
        if _out and not any(_q in (QUALITY_RARE, QUALITY_EPIC, QUALITY_LEGEND)
                            for _, _q in _out):
            _cand = [_w for _w in self.available()
                     if _w.get("quality", QUALITY_COMMON)
                     in (QUALITY_RARE, QUALITY_EPIC, QUALITY_LEGEND)]
            if _cand:
                _pick = self.rng.choice(_cand)
                self.unlocked.add(_pick.get("key"))
                _out[-1] = (_pick, _pick.get("quality", QUALITY_RARE))
        return _out

    # ---------------- 价格 ----------------
    def price(self, n=1):
        """抽奖价格（十连略优惠）"""
        _n = max(1, int(n))
        _base = GACHA_BASE_PRICE * _n
        if _n >= 10:
            return int(_base * 0.9)
        return _base


# ======================================================================
# 老虎机
# ======================================================================
class SlotMachine:
    """老虎机：三轴旋转，按符号倍率返还"""

    def __init__(self, rng=None):
        self.rng = rng or random
        self.last_spin = None
        self.last_payout = 0

    def _roll_symbol(self):
        _total = sum(_s["weight"] for _s in SLOT_SYMBOLS) or 1
        _r = self.rng.random() * _total
        for _s in SLOT_SYMBOLS:
            _r -= _s["weight"]
            if _r <= 0:
                return _s
        return SLOT_SYMBOLS[0]

    def spin(self, bet):
        """下注并旋转一次

        返回 {bet, reels:[symbol...], payout, win, kind}
        kind: "jackpot"(三同) / "pair"(两同) / "none"
        """
        try:
            _bet = int(bet)
        except Exception:
            _bet = 0
        _bet = max(0, min(SLOT_BET_MAX, _bet))
        _reels = [self._roll_symbol() for _ in range(3)]
        _keys = [_s["key"] for _s in _reels]
        if _keys[0] == _keys[1] == _keys[2]:
            _payout = _bet * _reels[0]["payout"]
            _kind = "jackpot"
        elif _keys[0] == _keys[1] or _keys[1] == _keys[2] or _keys[0] == _keys[2]:
            _payout = int(_bet * SLOT_PAIR_RATE)
            _kind = "pair"
        else:
            _payout = 0
            _kind = "none"
        _res = {
            "bet": _bet,
            "reels": _reels,
            "reel_names": [_s["name"] for _s in _reels],
            "payout": _payout,
            "win": _payout > 0,
            "kind": _kind,
            "net": _payout - _bet,
        }
        self.last_spin = _res
        self.last_payout = _payout
        return _res

    def clamp_bet(self, bet):
        try:
            return max(SLOT_BET_MIN, min(SLOT_BET_MAX, int(bet)))
        except Exception:
            return SLOT_BET_MIN
