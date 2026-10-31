# -*- coding: utf-8 -*-
"""v2.8.8 武器池：为军械库补给（抽奖）提供带品质分级的武器清单

品质按武器强度大致归类（狙击/轨道炮类归传说，霰弹/机枪类归史诗……）。
清单从 weapons.py 的 WEAPON_STATS 自动派生，新增武器无需手写两份。
"""
try:
    from gacha import (QUALITY_COMMON, QUALITY_FINE, QUALITY_RARE,
                       QUALITY_EPIC, QUALITY_LEGEND)
except Exception:                                    # pragma: no cover
    QUALITY_COMMON, QUALITY_FINE, QUALITY_RARE = "common", "fine", "rare"
    QUALITY_EPIC, QUALITY_LEGEND = "epic", "legend"

#: 手工指定的品质（未列出的按伤害自动推断）
_FORCED = {
    "FIST": QUALITY_COMMON,
    "KNIFE": QUALITY_COMMON,
    "BAT": QUALITY_COMMON,
    "PISTOL": QUALITY_COMMON,
    "SMG": QUALITY_FINE,
    "SHOTGUN": QUALITY_FINE,
    "AXE": QUALITY_FINE,
    "RIFLE": QUALITY_RARE,
    "CROSSBOW": QUALITY_RARE,
    "GRENADE": QUALITY_RARE,
    "MOLOTOV": QUALITY_RARE,
    "SNIPER": QUALITY_EPIC,
    "MACHINE_GUN": QUALITY_EPIC,
    "PLASMA_RIFLE": QUALITY_EPIC,
    "CHAINSAW": QUALITY_EPIC,
    "ROCKET_LAUNCHER": QUALITY_EPIC,
    "SCYTHE": QUALITY_LEGEND,
    "AWP": QUALITY_LEGEND,
    "RAILGUN": QUALITY_LEGEND,
    "GATLING": QUALITY_LEGEND,
    "FLAMETHROWER": QUALITY_LEGEND,
}

#: 每把武器的背景故事（抽奖页展示用；缺省给通用文案）
_STORY = {
    "FIST": "最原始的武器。当弹药耗尽，拳头是你最后的尊严。",
    "KNIFE": "食堂里顺手拿的。刃口有缺口，但足够划开皮肉。",
    "PISTOL": "校警的配枪。他没能来得及拔出它。",
    "AWP": "警用狙击枪，曾属于一位没能等到换防的射手。扣下扳机前，你会想起他。",
    "RAILGUN": "方舟科技的原型武器，本用于击穿装甲，如今用来击穿它们。",
    "SCYTHE": "收割者的遗物。持有时你会听见低语——别听。",
    "GATLING": "从军事仓库拖出来的，重得需要两个人抬。现在只有你。",
    "FLAMETHROWER": "清理街道用的。火能解决大部分问题，以及小部分你自己。",
}


def _auto_quality(dmg):
    try:
        _d = float(dmg)
    except Exception:
        return QUALITY_COMMON
    if _d >= 300:
        return QUALITY_LEGEND
    if _d >= 120:
        return QUALITY_EPIC
    if _d >= 55:
        return QUALITY_RARE
    if _d >= 22:
        return QUALITY_FINE
    return QUALITY_COMMON


def build_pool():
    """派生武器池 [{key,name,quality,damage,story,...}]

    武器数值定义在 Weapon._setup_weapon() 的局部字典里，没有模块级常量，
    所以这里**实例化一把武器**读取其属性来派生，保证与实战数值完全一致
    （新增武器无需再手写一份清单）。
    """
    try:
        from weapons import Weapon
        from config import WeaponType
    except Exception:
        return []
    _out = []
    for _wt in WeaponType:
        try:
            _w = Weapon(_wt, level=1)
        except Exception:
            continue
        _st = {
            "name": getattr(_w, "name", ""),
            "damage": getattr(_w, "damage", 0),
            "fire_rate": getattr(_w, "fire_rate", 0),
            "range": getattr(_w, "range", 0),
            "spread": getattr(_w, "spread", 0),
            "pierce": getattr(_w, "pierce", 1),
            "ammo": getattr(_w, "ammo", "-"),
            "reload": getattr(_w, "reload", "-"),
            "desc": getattr(_w, "desc", ""),
        }
        _k = getattr(_wt, "name", str(_wt))
        if _k == "NONE":
            continue
        _q = _FORCED.get(_k) or _auto_quality(_st.get("damage", 0))
        _out.append({
            "key": _k,
            "name": _st.get("name", _k),
            "quality": _q,
            "damage": _st.get("damage", 0),
            "fire_rate": _st.get("fire_rate", 0),
            "range": _st.get("range", 0),
            "ammo": _st.get("ammo", "-"),
            "reload": _st.get("reload", "-"),
            "spread": _st.get("spread", 0),
            "pierce": _st.get("pierce", 1),
            "desc": _st.get("desc", ""),
            "story": _STORY.get(_k, "从废墟里捡来的。它还能用，这就够了。"),
        })
    return _out
