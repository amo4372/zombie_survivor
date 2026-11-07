# -*- coding: utf-8 -*-
"""战斗数据层：统一伤害/抗性、实体状态、主动格挡（v2.9.12）"""
from .damage import (
    CHANNELS, TYPE_TO_CHANNEL, DEFAULT_PROFILES, profile_for,
    ResistanceSet, get_resistance_set, attach_resistances, reload_profiles,
    DamagePacket, DamageResult, coerce_packet, resolve_damage,
    channel_of, describe,
)
from .status import (
    KINDS, STATUS_DEFS, KIND_CHANNEL, EntityStatus, StatusState,
    attach_status, status_meta,
)
from .melee_fx import (WEAPON_STYLES, style_for, MeleeSlash, SwordQi,
                       MeleeFxSystem, draw_sword_qi_projectile)
from .block import (
    BlockController, BlockResult, attach_block, angle_diff,
    TAP_THRESHOLD, SHORT_DURATION, PERFECT_WINDOW, ARC_DEG,
)

__all__ = [
    "CHANNELS", "TYPE_TO_CHANNEL", "DEFAULT_PROFILES", "profile_for",
    "ResistanceSet", "get_resistance_set", "attach_resistances", "reload_profiles",
    "DamagePacket", "DamageResult", "coerce_packet", "resolve_damage",
    "channel_of", "describe",
    "KINDS", "STATUS_DEFS", "KIND_CHANNEL", "EntityStatus", "StatusState",
    "attach_status", "status_meta",
    "BlockController", "BlockResult", "attach_block", "angle_diff",
    "TAP_THRESHOLD", "SHORT_DURATION", "PERFECT_WINDOW", "ARC_DEG",
    "WEAPON_STYLES", "style_for", "MeleeSlash", "SwordQi",
    "MeleeFxSystem", "draw_sword_qi_projectile",
]
