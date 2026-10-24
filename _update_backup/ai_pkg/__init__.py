# -*- coding: utf-8 -*-
"""ai_pkg —— 无训练硬编程 AI 抽象模块（决策树/行为原语）

v2.2.4：完全替换 RL 强化学习接管为显式可读的决策树 AI。
- decision_tree.py: 通用决策树原语（选择器/条件/行为）
- zombie_ai.py: ZombieTreeAI —— 与旧 RLEnemyAI 同签名 decide() 的僵尸控制器
"""
from .decision_tree import (Node, Selector, Sequence, Condition, Action, Inverter)
from .zombie_ai import ZombieTreeAI

__all__ = ["Node", "Selector", "Sequence", "Condition", "Action", "Inverter",
           "ZombieTreeAI"]
