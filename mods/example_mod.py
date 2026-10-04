#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例 Mod - 弱鸡模式：敌人血量减半，玩家伤害翻倍"""

MOD_NAME = "弱鸡模式"
MOD_VERSION = "1.0.0"
MOD_AUTHOR = "示例作者"
MOD_DESCRIPTION = "敌人血量减半，玩家伤害翻倍，适合新手体验"


def register(hooks):
    """注册 mod 钩子（hooks 为 ModHook 实例，v2.0.11 起可通过 hooks.mod_api 使用数据存储）"""
    
    def on_enemy_spawn(enemy):
        """敌人生成时血量减半"""
        if hasattr(enemy, 'hp'):
            enemy.hp = int(enemy.hp * 0.5)
            enemy.max_hp = enemy.hp
    
    def on_player_damage(amount):
        """玩家受伤时伤害减半"""
        return int(amount * 0.5)
    
    hooks.register("on_enemy_spawn", on_enemy_spawn)
    hooks.register("on_player_damage", on_player_damage)
    
    print("[弱鸡模式] Mod 已加载 - 敌人血量减半，玩家受伤减半")

    # === v2.0.11 演示：mod 数据存储（自动存到 data/mods/example_mod/） ===
    try:
        api = hooks.mod_api
        stats = api.load_json("stats", default={"runs": 0})
        stats["runs"] = stats.get("runs", 0) + 1
        api.save_json("stats", stats)
        print(f"[弱鸡模式] 数据存储演示: 第 {stats['runs']} 次运行")
    except Exception as e:
        print(f"[弱鸡模式] 数据存储演示失败: {e}")
