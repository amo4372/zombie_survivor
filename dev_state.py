#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.5.8 开发者状态（每玩家独立面板 + 多人/PvP 能力）

设计要点
--------
- 每个玩家一份独立状态：无敌、抗尸、面板开关、传送目标、按钮列表
- 「无敌」= 全能无敌（僵尸 + 玩家都不掉血）
- 「抗尸」= 只免疫僵尸造成的伤害，**玩家造成的伤害照吃**（PvP 调试核心需求）
- 面板按钮列表由各面板自己维护，互不干扰（P1 打开面板不影响 P2）
"""

DEV_PLAYER_COUNT = 4  # P1~P4（PvPvE 最多 4 名玩家）


class DevPlayerState:
    """单个玩家的开发者状态（v2.5.8）"""

    __slots__ = ("index", "label", "god", "zombie_immune", "panel_open",
                 "buttons", "tp_target", "disable_zombie_spawn")

    def __init__(self, index=1, label="P1"):
        self.index = index
        self.label = label
        self.god = False            # 全能无敌（僵尸 + 玩家都不掉血）
        self.zombie_immune = False  # 免疫僵尸伤害（玩家伤害照吃）
        self.panel_open = False     # 该玩家自己的面板是否打开
        self.buttons = []           # 该玩家面板按钮（互不共享）
        self.tp_target = 0          # 传送目标玩家序号（0=未选择）
        self.disable_zombie_spawn = False  # v2.6.0：禁用僵尸刷新

    # ---------- 显示 ----------
    @property
    def tp_target_label(self):
        return "关" if not self.tp_target else f"P{self.tp_target}"

    def status_text(self):
        """面板头部状态摘要"""
        bits = []
        bits.append("无敌" if self.god else "可受伤")
        if self.zombie_immune:
            bits.append("抗尸")
        if self.tp_target:
            bits.append(f"TP→P{self.tp_target}")
        return " · ".join(bits)

    # ---------- 应用到玩家实体 ----------
    def apply_to(self, player):
        """把开发者状态同步到玩家实体（Player.take_damage 会读这两个字段）"""
        if player is None:
            return
        try:
            player.dev_god = bool(self.god)
            player.dev_zombie_immune = bool(self.zombie_immune)
        except Exception:
            pass

    def reset(self):
        """重置（开局/切场景时调用）"""
        self.god = False
        self.zombie_immune = False
        self.panel_open = False
        self.tp_target = 0
        self.disable_zombie_spawn = False
        self.buttons = []


def build_dev_states():
    """构造 P1~P4 的开发者状态表"""
    return {i: DevPlayerState(i, f"P{i}") for i in range(1, DEV_PLAYER_COUNT + 1)}
