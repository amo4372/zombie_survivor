# -*- coding: utf-8 -*-
"""决策树通用原语（轻量、零依赖、纯 Python）

节点约定：
- tick(ctx) -> 状态：SUCCESS / FAILURE / RUNNING
- 本游戏场景中行为节点直接在 tick 内写入 ctx["vx"]/ctx["vy"]/ctx["skill"]，
  决策树顶层只关心最终取哪个行为节点执行。
"""

SUCCESS = "SUCCESS"
FAILURE = "FAILURE"
RUNNING = "RUNNING"


class Node:
    """节点基类"""
    def tick(self, ctx):
        return FAILURE

    def _child(self, cond, action, ctx):
        return action if cond(ctx) else None


class Condition(Node):
    """条件节点：满足返回 SUCCESS，否则 FAILURE（不改变动作输出）"""
    def __init__(self, name, fn):
        self.name = name
        self.fn = fn

    def tick(self, ctx):
        try:
            return SUCCESS if self.fn(ctx) else FAILURE
        except Exception:
            return FAILURE


class Action(Node):
    """行为节点：执行动作函数，返回 SUCCESS"""
    def __init__(self, name, fn):
        self.name = name
        self.fn = fn

    def tick(self, ctx):
        try:
            self.fn(ctx)
        except Exception:
            return FAILURE
        return SUCCESS


class Inverter(Node):
    """取反节点"""
    def __init__(self, child):
        self.child = child

    def tick(self, ctx):
        r = self.child.tick(ctx)
        if r == SUCCESS:
            return FAILURE
        if r == FAILURE:
            return SUCCESS
        return RUNNING


class Selector(Node):
    """优先级选择器：按顺序尝试子节点，第一个 SUCCESS 即返回（短路）"""
    def __init__(self, name, children):
        self.name = name
        self.children = children

    def tick(self, ctx):
        for c in self.children:
            r = c.tick(ctx)
            if r == SUCCESS:
                return SUCCESS
        return FAILURE


class Sequence(Node):
    """序列器：全部子节点 SUCCESS 才 SUCCESS（任一失败即短路）"""
    def __init__(self, name, children):
        self.name = name
        self.children = children

    def tick(self, ctx):
        for c in self.children:
            r = c.tick(ctx)
            if r != SUCCESS:
                return r
        return SUCCESS
