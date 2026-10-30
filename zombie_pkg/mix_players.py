# -*- coding: utf-8 -*-
"""v2.7.1 多对象/多玩家通用层（PlayerRegistryMixin）

目标：让「玩家」不再是写死的 self.player / self.player2 两个全局变量，
而是可任意数量创建的一等对象。每一位玩家都拥有独立且完整的一套运行时上下文
（摄像机 / 控件 / 当前选中技能 / 钩爪状态机 / HUD 槽位），
其可用能力与单人模式下的 P1 完全一致。

本模块提供三类能力：
1) 玩家注册表：按槽位(P1..P4)登记、查找、遍历玩家；可按槽位动态创建玩家
2) 每玩家上下文：camera / controls / selected_skill 的统一读写（缺失时惰性创建）
3) 钩爪的完全通用化：候选目标收集、目标解算、飞行碰撞，全部以 player 为参数，
   P1..P4 与单人/多人共用同一份实现（此前 _update_grapple_collision 只跑 P1，
   这就是 P2 钩爪勾不到任何东西的根因）
"""

import math
from contextlib import contextmanager

try:
    from buff import BuffType
except Exception:  # pragma: no cover
    BuffType = None


def _seg_dist(px, py, ax, ay, bx, by):
    """点 (px,py) 到线段 AB 的最短距离（钩爪抗穿透用）"""
    _dx, _dy = bx - ax, by - ay
    _len2 = _dx * _dx + _dy * _dy
    if _len2 <= 0.0:
        return math.hypot(px - ax, py - ay)
    _t = ((px - ax) * _dx + (py - ay) * _dy) / _len2
    _t = 0.0 if _t < 0.0 else (1.0 if _t > 1.0 else _t)
    return math.hypot(px - (ax + _t * _dx), py - (ay + _t * _dy))


class PlayerContext:
    """每玩家运行时数据槽（v2.7.1 数据层平等的核心）

    每一位玩家在游戏里都拥有**结构完全相同**的一套数据：
    player / camera / controls / selected_skill / 升级与暂停状态 / HUD 数据。
    P1 不再享有任何特权字段——它只是槽位 0 的那个 context。

    重要：camera / controls 存的是**同一个对象引用**（不是拷贝），
    因此旧代码写 `self.camera2 = X` 与新代码读 `ctx.camera` 永远一致，
    不会出现两套数据分叉。
    """

    __slots__ = ("tag", "index", "player", "camera", "controls",
                 "selected_skill", "upgrade_paused", "pending_upgrade",
                 "pending_levels", "grace_timer", "hud", "aiming")

    def __init__(self, tag, index, player=None, camera=None, controls=None,
                 selected_skill=None):
        self.tag = tag
        self.index = index
        self.player = player
        self.camera = camera
        self.controls = controls if controls is not None else {}
        self.selected_skill = selected_skill
        # 升级 / 暂停（此前只有 P1 有完整状态，P2 靠 _upgrade_pause_player 字符串）
        self.upgrade_paused = False
        self.pending_upgrade = False
        self.pending_levels = 0
        self.grace_timer = 0.0
        self.hud = {}            # HUD 数据槽（每个玩家独立）
        self.aiming = False      # 预瞄中（用于分屏隔离预瞄线）

    def __repr__(self):
        return f"<PlayerContext {self.tag} player={self.player is not None}>"


class PlayerRegistryMixin:
    """玩家注册表 + 每玩家运行时上下文 + 通用钩爪"""

    # ==================================================================
    # 1) 玩家注册表
    # ==================================================================
    PLAYER_ATTRS = ("player", "player2", "player3", "player4")
    CAMERA_ATTRS = ("camera", "camera2", "camera3", "camera4")
    CONTROLS_ATTRS = ("controls", "p2_controls", "p3_controls", "p4_controls")
    SKILL_ATTRS = ("selected_skill", "p2_selected_skill",
                   "p3_selected_skill", "p4_selected_skill")

    # ------------------------------------------------------------------
    # 数据层平等：散落在 self 上的 P1..P4 属性 ↔ PlayerContext 双向同步
    # 旧代码 `self.camera2 = X` 会镜像进 ctx；新代码 `ctx.camera` 读到同一对象。
    # 这样历史代码不用改也能受益于统一数据层，且不会再出现"只有 P1 有某字段"。
    # ------------------------------------------------------------------
    @property
    def player_ctxs(self):
        """{tag: PlayerContext}，惰性构建"""
        _c = getattr(self, "_player_ctxs_cache", None)
        if _c is None:
            _c = {}
            object.__setattr__(self, "_player_ctxs_cache", _c)
            for _i in range(len(self.PLAYER_ATTRS)):
                _c[f"P{_i + 1}"] = PlayerContext(
                    tag=f"P{_i + 1}", index=_i,
                    player=getattr(self, self.PLAYER_ATTRS[_i], None),
                    camera=getattr(self, self.CAMERA_ATTRS[_i], None),
                    controls=getattr(self, self.CONTROLS_ATTRS[_i], None),
                    selected_skill=getattr(self, self.SKILL_ATTRS[_i], None),
                )
        return _c

    def ctx_of(self, player_or_tag):
        """玩家对象 / 标签 → 其 PlayerContext"""
        _i = self._slot_i(player_or_tag)
        if _i < 0:
            return None
        return self.player_ctxs.get(f"P{_i + 1}")

    def __setattr__(self, name, value):
        """把散落的 P1..P4 属性写操作镜像回 PlayerContext"""
        object.__setattr__(self, name, value)
        _c = getattr(self, "_player_ctxs_cache", None)
        if _c is None:
            return
        try:
            if name in self.PLAYER_ATTRS:
                _c[f"P{self.PLAYER_ATTRS.index(name) + 1}"].player = value
            elif name in self.CAMERA_ATTRS:
                _c[f"P{self.CAMERA_ATTRS.index(name) + 1}"].camera = value
            elif name in self.CONTROLS_ATTRS:
                _c[f"P{self.CONTROLS_ATTRS.index(name) + 1}"].controls = value
            elif name in self.SKILL_ATTRS:
                _c[f"P{self.SKILL_ATTRS.index(name) + 1}"].selected_skill = value
        except Exception:
            pass

    def __getattr__(self, name):
        """未显式设置的 P1..P4 属性 → 从 PlayerContext 取（保证 Pn 与 P1 平等）"""
        _c = self.__dict__.get("_player_ctxs_cache")
        if _c is not None:
            try:
                if name in self.PLAYER_ATTRS:
                    return _c[f"P{self.PLAYER_ATTRS.index(name) + 1}"].player
                if name in self.CAMERA_ATTRS:
                    return _c[f"P{self.CAMERA_ATTRS.index(name) + 1}"].camera
                if name in self.CONTROLS_ATTRS:
                    return _c[f"P{self.CONTROLS_ATTRS.index(name) + 1}"].controls
                if name in self.SKILL_ATTRS:
                    return _c[f"P{self.SKILL_ATTRS.index(name) + 1}"].selected_skill
            except Exception:
                pass
        raise AttributeError(name)

    def tag_of(self, player):
        """玩家 → 槽位标签（"P1".."P4"）；未知返回 None"""
        if player is None:
            return None
        for _i, _attr in enumerate(self.PLAYER_ATTRS):
            if getattr(self, _attr, None) is player:
                return f"P{_i + 1}"
        return None

    def slot_index_of(self, player):
        """玩家 → 0-based 槽位下标；未知返回 -1"""
        if player is None:
            return -1
        for _i, _attr in enumerate(self.PLAYER_ATTRS):
            if getattr(self, _attr, None) is player:
                return _i
        return -1

    def get_player(self, tag):
        """槽位标签 → 玩家对象（"P1"/1/"player2" 均可）"""
        if tag is None:
            return getattr(self, "player", None)
        if isinstance(tag, int):
            _i = tag - 1 if tag >= 1 else tag
        else:
            _s = str(tag).upper()
            if _s.startswith("P") and _s[1:].isdigit():
                _i = int(_s[1:]) - 1
            else:
                _i = 0
        if 0 <= _i < len(self.PLAYER_ATTRS):
            return getattr(self, self.PLAYER_ATTRS[_i], None)
        return None

    def iter_player_slots(self):
        """遍历所有已创建的玩家槽位，yield (tag, player)"""
        for _i, _attr in enumerate(self.PLAYER_ATTRS):
            _p = getattr(self, _attr, None)
            if _p is not None:
                yield f"P{_i + 1}", _p

    def registered_players(self):
        """已登记玩家列表（按槽位顺序）"""
        return [p for _, p in self.iter_player_slots()]

    def ensure_player(self, tag, x=None, y=None):
        """确保指定槽位存在玩家；不存在则创建一个完整配置的玩家实例。

        这是「玩家类可直接创建多个」的入口：新玩家与 P1 一样拥有
        独立的技能树/背包/防爆套装/摄像机/控件槽位。
        """
        _p = self.get_player(tag)
        if _p is not None:
            return _p
        _i = self._slot_i(tag)
        if _i < 0 or _i >= len(self.PLAYER_ATTRS):
            return None
        try:
            from entities_pkg.player import Player
        except Exception:
            return None
        _px = x if x is not None else getattr(getattr(self, "player", None), "x", 0.0)
        _py = y if y is not None else getattr(getattr(self, "player", None), "y", 0.0)
        if _i > 0:
            _px += 120.0 * _i
        _p = Player(_px, _py)
        # 阵营：合作模式全队同阵营，PvP 下按槽位轮流分队
        try:
            _pvpm = bool(getattr(getattr(self, "config", None), "pvp_enabled", False))
            _nteams = max(1, int(getattr(getattr(self, "config", None), "pvp_teams", 2) or 2)) if _pvpm else 1
            _p.team_id = (_i % _nteams)
        except Exception:
            _p.team_id = 0
        setattr(self, self.PLAYER_ATTRS[_i], _p)   # 经 __setattr__ 镜像进 ctx
        # 配套摄像机 / 控件槽位（惰性创建，保证 UI 数据管理按玩家分离）
        self.ensure_camera(_p)
        _ctx = self.ctx_of(_p)
        if _ctx is not None:
            _ctx.player = _p
            _ctx.camera = getattr(self, self.CAMERA_ATTRS[_i], None)
        return _p

    # ==================================================================
    # 2) 每玩家运行时上下文
    # ==================================================================
    def _slot_i(self, tag_or_player):
        """标签或玩家对象 → 0-based 下标"""
        if tag_or_player is None:
            return 0
        if not isinstance(tag_or_player, str):
            return self.slot_index_of(tag_or_player)
        _s = str(tag_or_player).upper()
        if _s.startswith("P") and _s[1:].isdigit():
            return int(_s[1:]) - 1
        try:
            return self.PLAYER_ATTRS.index(tag_or_player)
        except ValueError:
            return -1

    def camera_for(self, player):
        """玩家的独立摄像机（缺失时惰性创建，保证分屏/多视口数据分离）"""
        _i = self._slot_i(player)
        if _i < 0:
            return getattr(self, "camera", None)
        _attr = self.CAMERA_ATTRS[_i]
        _cam = getattr(self, _attr, None)
        if _cam is None:
            _cam = self._make_camera()
            if _cam is not None:
                setattr(self, _attr, _cam)   # 同时镜像进 ctx
        return _cam

    def _make_camera(self):
        try:
            from renderer import Camera
            from config import BASE_WIDTH, BASE_HEIGHT
            return Camera(BASE_WIDTH, BASE_HEIGHT)
        except Exception:
            try:
                from entities import Camera
                from config import BASE_WIDTH, BASE_HEIGHT
                return Camera(BASE_WIDTH, BASE_HEIGHT)
            except Exception:
                return None

    def ensure_camera(self, player_or_tag):
        return self.camera_for(player_or_tag)

    def controls_for(self, player):
        """玩家的控件集合（P1 的控件由 UI 层装配；其余槽位惰性建空字典）"""
        _i = self._slot_i(player)
        if _i < 0:
            return getattr(self, "p2_controls", None)
        _attr = self.CONTROLS_ATTRS[_i]
        _c = getattr(self, _attr, None)
        if _c is None:
            _c = {}
            setattr(self, _attr, _c)
        return _c

    def selected_skill_of(self, player):
        """玩家当前选中的主动技能"""
        _i = self._slot_i(player)
        if _i < 0:
            return getattr(self, "selected_skill", None)
        return getattr(self, self.SKILL_ATTRS[_i], None)

    def set_selected_skill(self, player, skill_type):
        """设置玩家当前选中的主动技能"""
        _i = self._slot_i(player)
        if _i < 0:
            return False
        setattr(self, self.SKILL_ATTRS[_i], skill_type)
        return True

    def cycle_selected_skill(self, player, unlocked=None):
        """轮换玩家的当前技能（多人/单人共用；与 P1 的切换逻辑等价）"""
        try:
            if unlocked is None:
                unlocked = self._get_unlocked_skills_for(player)
            if not unlocked:
                return None
            _cur = self.selected_skill_of(player)
            if _cur not in unlocked:
                _nx = unlocked[0]
            else:
                _nx = unlocked[(unlocked.index(_cur) + 1) % len(unlocked)]
            self.set_selected_skill(player, _nx)
            return _nx
        except Exception:
            return None

    def iter_player_ctx(self):
        """遍历玩家上下文：yield (tag, player, camera, controls)"""
        for _tag, _p in self.iter_player_slots():
            yield _tag, _p, self.camera_for(_p), self.controls_for(_p)

    # ==================================================================
    # 3) 钩爪完全通用化（玩家对僵尸 / 玩家对玩家 / 玩家对物品）
    # ==================================================================
    GRAPPLE_SEARCH_RADIUS = 30

    def grapple_candidates_for(self, player):
        """收集该玩家钩爪可作用的所有候选对象。

        返回 dict，供目标解算与飞行碰撞共用；单人模式下玩家列表为空，
        行为与旧版 P1 完全一致。
        """
        c = {
            "downed_teammates": [],
            "enemy_players": [],
            "teammates": [],
            "enemies": list(getattr(self, "enemies", []) or []),
            "items": [],
            "orbs": list(getattr(self, "exp_orbs", []) or []),
            "text_items": list(getattr(self, "text_items", []) or []),
            "story_items": list(getattr(self, "story_fragment_items", []) or []),
            "special_items": list(getattr(self, "special_items", []) or []),
        }
        try:
            _w = getattr(self, "world", None)
            c["items"] = list(getattr(_w, "items", []) or [])
        except Exception:
            pass
        try:
            c["downed_teammates"] = list(self._downed_teammates_of(player))
        except Exception:
            pass
        try:
            c["enemy_players"] = list(self._enemy_players_of(player))
        except Exception:
            pass
        try:
            c["teammates"] = list(self._alive_teammates_of(player))
        except Exception:
            pass
        return c

    def resolve_grapple_target(self, player, dir_x, dir_y, dist, search_radius=None):
        """通用钩爪目标解算：沿发射方向在给定距离内按优先级挑最近目标。

        优先级：倒地队友(救援) > 异阵营玩家(PvP) > 同阵营存活玩家 > 僵尸
        （经验球/世界道具仍走飞行碰撞，与旧版 P1 行为一致）

        返回 目标对象 或 None。P1/P2/键控/触控/单人/多人共用这一份实现。
        """
        _r = self.GRAPPLE_SEARCH_RADIUS if search_radius is None else search_radius
        _c = self.grapple_candidates_for(player)
        best = None
        best_proj = dist

        def _consider(objs, pad):
            nonlocal best, best_proj
            for _o in objs:
                if _o is None:
                    continue
                if not getattr(_o, "alive", True) and not getattr(_o, "downed", False):
                    continue
                _ex = _o.x - player.x
                _ey = _o.y - player.y
                _pr = _ex * dir_x + _ey * dir_y
                if _pr < 0 or _pr > dist:
                    continue
                _px = _ex - _pr * dir_x
                _py = _ey - _pr * dir_y
                if math.hypot(_px, _py) < _r + pad and _pr < best_proj:
                    best_proj = _pr
                    best = _o

        # 1) 倒地队友（救援，优先级最高）
        _consider(_c["downed_teammates"], 26)
        # 2) 异阵营玩家（PvP）
        _consider(_c["enemy_players"], 26)
        # 3) 同阵营存活玩家（救援/自拉）
        _consider([t for t in _c["teammates"] if not getattr(t, "downed", False)], 26)
        # 4) 僵尸（含 Boss，Boss 由飞行碰撞判定免控）
        _consider([e for e in _c["enemies"] if getattr(e, "alive", False)], 0)
        return best

    def update_grapple_collisions(self):
        """为每一位玩家跑钩爪飞行碰撞（旧版只跑 P1 → P2 勾不到任何东西）"""
        for _tag, _p in self.iter_player_slots():
            try:
                self._update_grapple_collision_for(_p)
            except Exception:
                pass

    def _update_grapple_collision_for(self, player):
        """单个玩家的钩爪飞行碰撞：僵尸 / 玩家 / 经验球 / 道具 / 资料 / 宝箱

        与旧版 _update_grapple_collision 逻辑等价，但完全以 player 为参数，
        不再写死 self.player。
        """
        rg = getattr(player, "riot_gear", None)
        if rg is None or not getattr(rg, "grapple_active", False):
            return
        # 直拉模式：不勾取路径上任何东西
        if getattr(rg, "grapple_direct_pull", False):
            return

        _dt = getattr(self, "dt", 1 / 60)

        # ===== 自我拉拽沿途伤害 =====
        if rg.grapple_state == "self_pull":
            if getattr(rg, "grapple_is_scythe", False):
                rg.grapple_swing_timer -= _dt
                if rg.grapple_swing_timer <= 0:
                    rg.grapple_swing_timer = rg.grapple_swing_interval
                    _swing_r = 85
                    for e in self.enemies:
                        if not e.alive:
                            continue
                        if math.hypot(e.x - player.x, e.y - player.y) < _swing_r + getattr(e, "size", 20):
                            e.take_damage(35)
                            self.damage_numbers.append(
                                self._dmg_num(e.x, e.y, 35, (210, 130, 255)))
                            if hasattr(e, "knockback_x"):
                                _a = math.atan2(e.y - player.y, e.x - player.x)
                                e.knockback_x = math.cos(_a) * 90
                                e.knockback_y = math.sin(_a) * 90
                    try:
                        from entities import SlashArc
                    except Exception:
                        SlashArc = None
                    if SlashArc is not None:
                        self.slash_arcs.append(SlashArc(
                            player.x, player.y, player.facing_angle, _swing_r, (200, 120, 255),
                            lifetime=0.22, kind="scythe", start_radius=_swing_r * 0.6,
                            end_angle_offset=4.8))
            return

        # ===== 拉敌撞击词条 =====
        if rg.grapple_state == "pulling" and rg.grapple_target is not None \
                and getattr(rg.grapple_target, "alive", False):
            _gt = rg.grapple_target
            _impact = getattr(rg, "_grapple_impact_damage", 25)
            for e2 in self.enemies:
                if e2 is _gt or not e2.alive:
                    continue
                if id(e2) in rg.grapple_pull_impact_hit:
                    continue
                if math.hypot(e2.x - _gt.x, e2.y - _gt.y) < getattr(e2, "size", 20) + getattr(_gt, "size", 20):
                    rg.grapple_pull_impact_hit.add(id(e2))
                    e2.take_damage(_impact)
                    self.damage_numbers.append(
                        self._dmg_num(e2.x, e2.y, _impact, (255, 165, 0)))
                    if hasattr(e2, "knockback_x"):
                        _a = math.atan2(e2.y - _gt.y, e2.x - _gt.x)
                        e2.knockback_x = math.cos(_a) * 120
                        e2.knockback_y = math.sin(_a) * 120

        if rg.grapple_state != "shooting":
            return

        head_pos = rg.grapple_head_pos
        if not head_pos:
            return

        # v2.7.1 抗穿透：钩爪头单帧位移可达数十像素，若只判定「头当前点」与目标的
        # 距离，细小目标（经验球/道具/资料）会被整帧跨过而永远勾不到。
        # 改用「上一帧位置→当前位置」的线段做距离判定，P1..P4 均受益。
        _prev = getattr(rg, "_collision_prev_head", None)
        try:
            rg._collision_prev_head = [head_pos[0], head_pos[1]]
        except Exception:
            pass
        if not _prev:
            # 首帧还没有上一帧位置：钩爪是从玩家身上发射的，用玩家位置作为起点，
            # 这样「发射点→当前头位置」整段都会被判定，不会漏掉贴身的目标。
            _prev = [player.x, player.y]

        def _hit(x, y, reach):
            """目标是否落在本帧钩爪头扫过的线段 ± reach 范围内"""
            return _seg_dist(x, y, _prev[0], _prev[1], head_pos[0], head_pos[1]) <= reach

        _lvl = self._grapple_level_of(player)

        # ===== 锁定目标直飞 =====
        _locked = rg.grapple_target
        if _locked is not None and getattr(_locked, "alive", False) \
                and not getattr(_locked, "is_boss", False):
            if _hit(_locked.x, _locked.y, getattr(_locked, "size", 20) + 12):
                if hasattr(_locked, "take_damage"):
                    base_dmg = 15 + _lvl * 10
                    _locked.take_damage(base_dmg)
                    self.damage_numbers.append(self._dmg_num(_locked.x, _locked.y, base_dmg, (255, 165, 0)))
                    rg._grapple_impact_damage = base_dmg
                    if _lvl >= 4:
                        self._apply_stun(_locked, 1.0)
                    rg.set_grapple_target(_locked)
                    rg.grapple_state = "hit"
                    rg.grapple_hit_stun_timer = rg.grapple_hit_stun_duration
                    _locked.grappled = True
                    self._float_text(_locked.x, _locked.y - 30, "锁定直飞!", (200, 120, 255), 1.0)
                else:
                    rg.set_grapple_target(_locked)
                    rg.grapple_state = "pulling"
                    rg._pulling_timer = 0.0
                    self._float_text(_locked.x, _locked.y - 30, "勾取道具!", (120, 230, 140), 1.0)
                return

        # ===== 僵尸 =====
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if not _hit(enemy.x, enemy.y, enemy.size + 12):
                continue
            base_dmg = 15 + _lvl * 10
            enemy.take_damage(base_dmg)
            rg._grapple_impact_damage = base_dmg
            self.damage_numbers.append(self._dmg_num(enemy.x, enemy.y, base_dmg, (255, 165, 0)))
            if _lvl >= 5:
                for e2 in self.enemies:
                    if e2 is not enemy and e2.alive and math.hypot(e2.x - enemy.x, e2.y - enemy.y) < 120:
                        e2.take_damage(base_dmg * 2)
                        self.damage_numbers.append(self._dmg_num(e2.x, e2.y, base_dmg * 2, (255, 0, 0)))
            elif _lvl >= 3:
                for e2 in self.enemies:
                    if e2 is not enemy and e2.alive and math.hypot(e2.x - enemy.x, e2.y - enemy.y) < 60:
                        e2.take_damage(int(base_dmg * 0.5))
            if _lvl >= 4:
                self._apply_stun(enemy, 1.0)
            if getattr(enemy, "is_boss", False):
                # Boss 免控：只能僵直，不能拉回
                rg.grapple_state = "retracting"
                rg.grapple_hit_stun_timer = rg.grapple_hit_stun_duration * 0.5
                rg.grapple_target = None
                self._apply_stun(enemy, 0.8)
                self._float_text(enemy.x, enemy.y - 30, "僵直!", (255, 255, 0), 1.0)
                return
            rg.set_grapple_target(enemy)
            rg.grapple_state = "hit"
            rg.grapple_hit_stun_timer = rg.grapple_hit_stun_duration
            enemy.grappled = True
            self._float_text(enemy.x, enemy.y - 30, "勾中!", (0, 255, 0), 1.0)
            return

        # ===== 其他玩家（玩家对玩家；PvP 异阵营 / 合作同阵营救援） =====
        _hit_player = self._grapple_player_hit(player, head_pos, rg)
        if _hit_player:
            return

        # ===== 经验球 =====
        for orb in self.exp_orbs:
            if not orb.alive:
                continue
            if _hit(orb.x, orb.y, orb.size + 12):
                orb.magnetized = True
                rg._reset_grapple()
                return

        # ===== 世界道具 =====
        for item in getattr(getattr(self, "world", None), "items", []) or []:
            if not getattr(item, "alive", False):
                continue
            if _hit(item.x, item.y, item.size + 12):
                rg.set_grapple_target(item)
                rg.grapple_state = "pulling"
                rg._pulling_timer = 0.0
                return

        # ===== 文本资料 =====
        for ti in getattr(self, "text_items", []) or []:
            if not ti.alive:
                continue
            if _hit(ti.x, ti.y, 20):
                ti.magnetized = True
                rg._reset_grapple()
                return

        # ===== 剧情碎片 =====
        for si in getattr(self, "story_fragment_items", []) or []:
            if _hit(si["x"], si["y"], 20):
                si["magnetized"] = True
                rg._reset_grapple()
                return

        # ===== 特殊道具/宝箱 =====
        for si in getattr(self, "special_items", []) or []:
            if not si.alive:
                continue
            if _hit(si.x, si.y, getattr(si, "size", 15) + 12):
                si.magnetized = True
                rg._reset_grapple()
                return

    def _grapple_player_hit(self, player, head_pos, rg):
        """钩爪头命中其他玩家的处理（玩家对玩家通用）"""
        try:
            for _o in self._grapple_player_targets(player):
                if _hit(_o.x, _o.y, getattr(_o, "size", 16) + 26):
                    rg.set_grapple_target(_o)
                    rg.grapple_state = "hit"
                    rg.grapple_hit_stun_timer = rg.grapple_hit_stun_duration
                    _o.grappled = True
                    # 被打断绳索 QTE（由 gear 状态机接管）
                    if hasattr(_o, "qte_window"):
                        if getattr(_o, "qte_immune_timer", 0) > 0:
                            rg.grapple_state = "retracting"
                            rg.grapple_target = None
                            _o.grappled = False
                            return False
                        _o.qte_window = 0.8
                        _o.qte_break_tap = None
                        _o.qte_break_hint = 1.0
                        _o.qte_hit_flash = 0.0
                        _o.qte_success_timer = 0.0
                        _o.qte_fail_timer = 0.0
                    self._float_text(_o.x, _o.y - 30, "勾中玩家!", (120, 230, 140), 1.0)
                    return True
        except Exception:
            pass
        return False

    def _grapple_player_targets(self, player):
        """该玩家钩爪可勾取的其他玩家（异阵营优先，其次同阵营救援）"""
        _res = []
        try:
            _res.extend(self._enemy_players_of(player))
        except Exception:
            pass
        try:
            _res.extend([t for t in self._alive_teammates_of(player)
                         if not getattr(t, "downed", False)])
        except Exception:
            pass
        try:
            _res.extend(self._downed_teammates_of(player))
        except Exception:
            pass
        _out = []
        for _p in _res:
            if _p is player or _p in _out:
                continue
            _out.append(_p)
        return _out

    # ==================================================================
    # 4) 施法上下文切换 —— 让 P2..Pn 复用 P1 的完整技能实现
    # ==================================================================
    @contextmanager
    def acting_as(self, player):
        """临时把「当前操作玩家」切换为指定玩家（P1..Pn 通用）

        历史技能代码全部以 `self.player` 为操作对象（mix_skills 里 200+ 处）。
        与其给 P2 复制一套残缺实现（这正是 P2 少技能、钩爪短按失效的原因），
        不如临时切换上下文，让所有玩家直接复用 P1 的完整技能逻辑 ——
        能力天然平等，且不会 behaviour 分叉。

        用法：
            with self.acting_as(p2):
                self._execute_skill(SkillType.BLACK_HOLE)
        """
        if player is None:
            yield self.player
            return
        _op = getattr(self, "player", None)
        _oc = getattr(self, "camera", None)
        if player is _op:
            yield player
            return
        self.player = player
        try:
            self.camera = self.camera_for(player) or _oc
        except Exception:
            pass
        try:
            yield player
        finally:
            self.player = _op
            try:
                self.camera = _oc
            except Exception:
                pass

    def cast_skill_for(self, player, skill_type, angle=None, ratio=1.0, aimed=False):
        """统一施法入口：任意玩家（P1..Pn）共用同一套解锁/冷却/执行流程

        P1 走原有 `_use_skill` / `_use_skill_aimed`；
        其它玩家先尝试 `_use_skill_p2_aimed`（钩爪等已针对玩家参数化），
        再回落到「切上下文 + P1 执行器」，从而具备与 P1 完全一致的全部技能。
        """
        if player is None or skill_type is None:
            return False
        try:
            _unlocked = self._get_unlocked_skills_for(player)
            if _unlocked and skill_type not in _unlocked:
                self.floating_texts.append(self._float_text_obj(
                    player.x, player.y - 40, "技能未解锁", (128, 128, 128), 1.0))
                return False
        except Exception:
            pass
        try:
            if skill_type in getattr(player, "active_skills", {}):
                return False
        except Exception:
            pass

        _is_p1 = (player is getattr(self, "player", None) and not aimed)
        if _is_p1:
            try:
                return bool(self._use_skill(skill_type))
            except Exception:
                pass
        # 已针对玩家参数化的实现（钩爪/无畏冲锋等）
        try:
            _a = angle
            if _a is None:
                _a = math.radians(self.auto_aim_angle_for(player))
            if bool(self._use_skill_p2_aimed(skill_type, _a, ratio)):
                return True
        except Exception:
            pass
        # 回落：切上下文复用 P1 执行器 → P2..Pn 拥有 P1 的全部技能
        try:
            with self.acting_as(player):
                _ok = bool(self._execute_skill(skill_type))
            if _ok:
                self._apply_skill_cd(player, skill_type)
            return _ok
        except Exception:
            return False

    def _apply_skill_cd(self, player, skill_type):
        """统一写技能冷却（与 P1 同一张表）"""
        try:
            from config import get_skill_cooldown, SkillType
            _cd = get_skill_cooldown(skill_type, getattr(player, "cooldown_mult", 1.0))
            if skill_type == SkillType.RIOT_GEAR or skill_type == SkillType.VEHICLE_SUMMON:
                return
            player.active_skills[skill_type] = _cd
        except Exception:
            pass

    def auto_aim_angle_for(self, player):
        """通用自动瞄准角度：敌人 + 可勾取玩家（P1..Pn 同一份）

        旧版 P2 的自动瞄准只看敌人，所以 P2 永远锁不到 P1 —— 这是
        "P2 不能自动锁定 P1" 的直接原因。现在所有玩家共用这一份。
        """
        best = None
        best_d = 1e18
        try:
            for _e in getattr(self, "enemies", []) or []:
                if not getattr(_e, "alive", True):
                    continue
                _d = (_e.x - player.x) ** 2 + (_e.y - player.y) ** 2
                if _d < best_d:
                    best_d, best = _d, _e
        except Exception:
            pass
        try:
            for _p in self._grapple_player_targets(player):
                _d = (_p.x - player.x) ** 2 + (_p.y - player.y) ** 2
                if _d < best_d:
                    best_d, best = _d, _p
        except Exception:
            pass
        if best is not None:
            return math.degrees(math.atan2(best.y - player.y, best.x - player.x))
        return getattr(player, "facing_angle", 0.0)

    def _float_text_obj(self, x, y, text, color, lifetime=1.0):
        try:
            from entities import FloatingText
            return FloatingText(x, y, text, color=color, lifetime=lifetime)
        except Exception:
            return None

    # ---------------- 小工具（避免各处重复 import） ----------------
    def _grapple_level_of(self, player):
        try:
            from config import SkillType
            _sk = player.skill_tree.get_skill(SkillType.GRAPPLE_PULL)
            return _sk.current_level if _sk else 1
        except Exception:
            return 1

    def _apply_stun(self, target, duration):
        try:
            target.apply_buff(BuffType.STUN, duration=duration)
        except Exception:
            pass

    def _float_text(self, x, y, text, color, lifetime=1.0):
        try:
            from entities import FloatingText
            self.floating_texts.append(FloatingText(x, y, text, color=color, lifetime=lifetime))
        except Exception:
            pass

    def _dmg_num(self, x, y, dmg, color):
        try:
            from entities import DamageNumber
            return DamageNumber(x, y, dmg, color=color)
        except Exception:
            return None
