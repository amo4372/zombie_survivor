# -*- coding: utf-8 -*-
"""实体状态数据管理（v2.9.12）

统一维护 流血 / 燃烧 / 冰冻 / 中毒 / 眩晕 / 感电 等状态的
层数、剩余时间、每跳伤害与易伤，供：
- 伤害计算（damage.py 读 `vulnerability()`）
- 渲染层（HUD 图标、实体光环、粒子颜色）
- 死亡详情 / 回放（状态快照）

不推翻原有 BuffManager：apply 时可选桥接进去，保证冻结移速、燃烧加深
等旧机制继续生效，本项目只是把它变成**结构化数据**并补齐渲染。
"""
from typing import Dict, List, Optional

KINDS = ("bleed", "burn", "freeze", "poison", "stun", "shock")

# 默认状态定义（也是 status_defs 表的播种数据；数据库权威）
STATUS_DEFS: Dict[str, dict] = {
    "bleed":  {"name": "流血", "color": (200, 40, 55), "icon": "血",
               "dps": 6.0, "duration": 5.0, "max_stacks": 3,
               "vulnerability": {"physical": 0.10}, "fx": "drip"},
    "burn":   {"name": "燃烧", "color": (255, 130, 30), "icon": "燃",
               "dps": 9.0, "duration": 4.0, "max_stacks": 3,
               "vulnerability": {"fire": 0.20, "physical": 0.08}, "fx": "flame"},
    "freeze": {"name": "冰冻", "color": (110, 200, 255), "icon": "冰",
               "dps": 0.0, "duration": 3.0, "max_stacks": 1,
               "vulnerability": {"ice": 0.15}, "fx": "crystal"},
    "poison": {"name": "中毒", "color": (120, 220, 80), "icon": "毒",
               "dps": 5.0, "duration": 6.0, "max_stacks": 5,
               "vulnerability": {"poison": 0.12}, "fx": "bubble"},
    "stun":   {"name": "眩晕", "color": (255, 225, 90), "icon": "晕",
               "dps": 0.0, "duration": 1.0, "max_stacks": 1,
               "vulnerability": {}, "fx": "stars"},
    "shock":  {"name": "感电", "color": (160, 190, 255), "icon": "电",
               "dps": 4.0, "duration": 2.5, "max_stacks": 2,
               "vulnerability": {"lightning": 0.15}, "fx": "spark"},
}

# 状态 → damage.py 的通道（DOT 走什么抗性）
KIND_CHANNEL = {
    "bleed": "physical", "burn": "fire", "freeze": "ice",
    "poison": "poison", "stun": "true", "shock": "lightning",
}

# 状态 → 旧 BuffType 名（桥接用，取不到就跳过）
KIND_BUFF = {
    "bleed": "BLEED", "burn": "BURN", "freeze": "FREEZE",
    "poison": "POISON", "stun": "STUN",
}


class StatusState:
    __slots__ = ("kind", "stacks", "time", "tick", "intensity")

    def __init__(self, kind, stacks=1, time=0.0, intensity=1.0):
        self.kind = kind
        self.stacks = max(1, int(stacks))
        self.time = max(0.0, float(time))
        self.tick = 0.0
        self.intensity = float(intensity)

    @property
    def progress(self) -> float:
        d = STATUS_DEFS.get(self.kind, {}).get("duration", 1.0)
        return max(0.0, min(1.0, self.time / d)) if d > 0 else 0.0


class EntityStatus:
    """挂在 player / enemy 上的 `status` 组件。"""

    def __init__(self, owner=None, defs: Optional[Dict[str, dict]] = None):
        self.owner = owner
        self.defs = defs or STATUS_DEFS
        self.states: Dict[str, StatusState] = {}
        self._flash = 0.0          # 新状态命中的闪光，渲染层读

    # ------------------------------------------------------------ 写入
    def apply(self, kind: str, stacks: int = 1, duration: Optional[float] = None,
              intensity: float = 1.0, bridge: bool = True):
        kind = str(kind).lower()
        d = self.defs.get(kind)
        if not d:
            return None
        dur = float(duration if duration is not None else d.get("duration", 3.0))
        cap = int(d.get("max_stacks", 3))
        st = self.states.get(kind)
        if st is None:
            # 首次施加：stacks 参数直接就是层数（而非"再叠加 stacks 次"）
            st = StatusState(kind, stacks=max(1, int(stacks)),
                             time=dur, intensity=intensity)
            self.states[kind] = st
        else:
            st.stacks = min(cap, st.stacks + max(1, int(stacks)))
            st.time = max(st.time, dur)
            st.intensity = max(st.intensity, float(intensity))
        self._flash = 0.25
        if bridge:
            self._bridge(kind, st.time)
        return st

    def clear(self, kind: str = None):
        if kind is None:
            self.states.clear()
        else:
            self.states.pop(str(kind).lower(), None)

    # ------------------------------------------------------------ 查询
    def has(self, kind: str) -> bool:
        return str(kind).lower() in self.states

    def get(self, kind: str) -> Optional[StatusState]:
        return self.states.get(str(kind).lower())

    def active_states(self) -> List[StatusState]:
        return [s for s in self.states.values() if s.time > 0]

    def vulnerability(self, channel: str) -> float:
        """该通道的额外易伤（燃烧提高火伤、流血提高物伤…）"""
        total = 0.0
        for s in self.states.values():
            if s.time <= 0:
                continue
            d = self.defs.get(s.kind, {})
            v = (d.get("vulnerability") or {}).get(channel, 0.0)
            if v:
                total += float(v) * s.stacks * s.intensity
        return min(1.5, total)

    def movement_mult(self) -> float:
        """冰冻/眩晕对移速的影响（渲染与逻辑都可读）"""
        m = 1.0
        if self.has("freeze"):
            m *= 0.25
        if self.has("stun"):
            m *= 0.0
        return m

    # ------------------------------------------------------------ 每帧
    def update(self, dt: float):
        """推进计时，返回本帧应结算的 DOT 列表 [(amount, damage_type), ...]"""
        out = []
        self._flash = max(0.0, self._flash - dt)
        for kind, st in list(self.states.items()):
            if st.time <= 0:
                del self.states[kind]
                continue
            st.time -= dt
            d = self.defs.get(kind, {})
            dps = float(d.get("dps", 0.0) or 0.0)
            if dps > 0:
                st.tick += dt
                # 每 0.5s 一跳，层数线性叠加
                while st.tick >= 0.5:
                    st.tick -= 0.5
                    out.append((dps * 0.5 * st.stacks * st.intensity,
                                KIND_CHANNEL.get(kind, "physical")))
            if st.time <= 0:
                del self.states[kind]
        return out

    def flash(self) -> float:
        return self._flash

    # ------------------------------------------------------------ 桥接旧系统
    def _bridge(self, kind: str, duration: float):
        try:
            buff_name = KIND_BUFF.get(kind)
            if not buff_name or self.owner is None:
                return
            bm = getattr(self.owner, "buff_manager", None)
            if bm is None:
                return
            from buff import BuffType
            bt = getattr(BuffType, buff_name, None)
            if bt is None:
                return
            if hasattr(bm, "add_buff"):
                bm.add_buff(bt, duration=duration)
        except Exception:
            pass

    # ------------------------------------------------------------ 快照
    def snapshot(self) -> dict:
        return {k: {"stacks": s.stacks, "time": round(s.time, 2),
                    "intensity": s.intensity}
                for k, s in self.states.items() if s.time > 0}


def attach_status(owner, defs=None) -> EntityStatus:
    st = EntityStatus(owner, defs)
    owner.status = st
    return st


def status_meta(kind: str) -> dict:
    return STATUS_DEFS.get(kind, {"name": kind, "color": (200, 200, 200),
                                  "icon": "?", "fx": "none"})


__all__ = ["KINDS", "STATUS_DEFS", "KIND_CHANNEL", "EntityStatus",
           "StatusState", "attach_status", "status_meta"]
