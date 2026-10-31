# -*- coding: utf-8 -*-
"""v2.8.0 打击反馈 / 死亡反应时间 / 死亡详情（FeedbackMixin）

三件事：
1. **伤害命中反馈**：Enemy.take_damage 是全部伤害的统一出口（射击/近战/技能/
   AOE/DOT 都经过），本模块每帧消费敌人身上的命中事件，生成命中标记 +
   轻震屏 + 命中闪光，因此**技能命中也有与射击一致的打击感**。
   玩家受伤时给红晕 + 震屏 + 来袭方向指示。
2. **死亡反应时间**：玩家死亡不再立刻切结算页，而是进入 DYING 状态
   ——慢放、镜头拉近倒地者、显示致命一击来源，给玩家"我怎么死的"的反应时间，
   之后才进结算（按键可提前跳过）。
3. **死亡详情**：整局记录玩家承受的伤害来源流水，结算页按钮打开面板，
   可查看最近每条伤害的"来源 / 数值 / 类型 / 剩余血量 / 距死亡秒数"。
"""

import math
import time

DEATH_REACTION_TIME = 2.6      # 死亡反应时长（秒）
DEATH_SLOWMO = 0.28            # 死亡慢放系数（仅用于特效推进）
HIT_MARKER_LIFE = 0.32

# 视为"技能命中"的伤害类型（用于命中标记配色，让技能命中更醒目）
SKILL_DAMAGE_TYPES = ("skill", "magic", "aoe", "fire", "ice", "frost", "lightning",
                      "explosion", "laser", "chain", "nova", "blackhole")


class FeedbackMixin:
    """命中反馈 + 死亡反应 + 死亡详情"""

    # ==================================================================
    # 初始化
    # ==================================================================
    def _feedback_init(self):
        self.hit_markers = []        # [(x, y, life, max_life, kind, dmg)]
        self.damage_flash = 0.0      # 玩家受伤红晕 0..1
        self.hurt_dir = None         # 来袭方向 (angle, life)
        self.death_timer = 0.0
        self.death_killer = None     # 致命一击信息
        self.death_slow_t = 0.0
        self.show_death_detail = False
        self.death_detail_scroll = 0
        # v2.8.2：死亡瞬间的伤害日志快照（冻结，不再被死后伤害刷掉）
        self.death_detail_snapshot = {}
        self.death_replay_saved = False

    # ==================================================================
    # 1) 命中反馈
    # ==================================================================
    def _feedback_tick(self, dt):
        """每逻辑帧：消费命中事件 + 衰减反馈"""
        # --- 消费敌人的命中事件（覆盖射击/技能/AOE/DOT 全部来源） ---
        try:
            for _e in getattr(self, 'enemies', []):
                _ev = getattr(_e, '_hit_events', None)
                if not _ev:
                    continue
                for _dmg, _dtype in _ev:
                    self._spawn_hit_marker(_e.x, _e.y, _dmg, _dtype,
                                           killed=not getattr(_e, 'alive', True))
                try:
                    _ev.clear()
                except Exception:
                    pass
        except Exception:
            pass
        # --- 玩家受伤检测：对比上一帧血量（覆盖全部伤害来源，无需改调用点） ---
        try:
            for _p in self.registered_players():
                _hp = float(getattr(_p, 'hp', 0.0))
                _prev = getattr(_p, '_fb_last_hp', None)
                if _prev is not None and _hp < _prev - 0.01:
                    _src = None
                    _log = getattr(_p, 'damage_log', None)
                    if _log:
                        _last = _log[-1]
                        if _last.get("x") is not None:
                            _src = (_last.get("x"), _last.get("y"))
                    if _src is not None:
                        self._feedback_player_hurt(_p, _prev - _hp, _src[0], _src[1])
                    else:
                        self._feedback_player_hurt(_p, _prev - _hp)
                    # 受伤事件入回放流水
                    self.replay_event("hurt", f"{_prev - _hp:.0f}", _p.x, _p.y, _prev - _hp)
                _p._fb_last_hp = _hp
        except Exception:
            pass
        # --- 衰减 ---
        _new = []
        for _m in self.hit_markers:
            _m[2] -= dt
            if _m[2] > 0:
                _new.append(_m)
        self.hit_markers = _new
        if self.damage_flash > 0:
            self.damage_flash = max(0.0, self.damage_flash - dt * 2.2)
        if self.hurt_dir is not None:
            self.hurt_dir = (self.hurt_dir[0], self.hurt_dir[1] - dt)
            if self.hurt_dir[1] <= 0:
                self.hurt_dir = None

    def _spawn_hit_marker(self, x, y, dmg, dtype="normal", killed=False):
        """生成一个命中标记"""
        try:
            _ds = str(dtype).lower()
            if killed:
                _kind = "kill"
            elif any(k in _ds for k in SKILL_DAMAGE_TYPES):
                _kind = "skill"
            elif dmg >= 60:
                _kind = "heavy"
            else:
                _kind = "normal"
            self.hit_markers.append([float(x), float(y), HIT_MARKER_LIFE,
                                     HIT_MARKER_LIFE, _kind, float(dmg)])
            # 上限保护
            if len(self.hit_markers) > 40:
                del self.hit_markers[:len(self.hit_markers) - 40]
            # 大伤害/击杀时轻微震屏（只震主视口，多人不互相干扰）
            _cam = getattr(self, 'camera', None)
            if _cam is not None and hasattr(_cam, 'shake'):
                if _kind == "kill":
                    _cam.shake(3, 0.12)
                elif _kind in ("skill", "heavy"):
                    _cam.shake(2, 0.08)
        except Exception:
            pass

    def _feedback_player_hurt(self, player, amount, src_x=None, src_y=None):
        """玩家受伤反馈：红晕 + 震屏 + 来袭方向"""
        try:
            if amount <= 0:
                return
            _ratio = min(1.0, float(amount) / max(1.0, getattr(player, 'max_hp', 100.0)))
            self.damage_flash = min(1.0, self.damage_flash + 0.25 + _ratio * 1.2)
            _cam = self.camera_for(player) if hasattr(self, 'camera_for') else getattr(self, 'camera', None)
            if _cam is not None and hasattr(_cam, 'shake'):
                _cam.shake(3 + int(_ratio * 6), 0.12 + _ratio * 0.15)
            if src_x is not None and src_y is not None:
                self.hurt_dir = (math.atan2(src_y - player.y, src_x - player.x), 1.1)
        except Exception:
            pass

    # ==================================================================
    # 2) 死亡反应时间
    # ==================================================================
    def _begin_death_reaction(self):
        """玩家死亡 → 进入 DYING（不立刻结算）"""
        try:
            from config import GameState
            if getattr(self, 'state', None) != GameState.PLAYING:
                return
            self.death_timer = DEATH_REACTION_TIME
            self.death_slow_t = 0.0
            self.death_killer = self._find_killer()
            # 死亡瞬间：冻结每位玩家的伤害日志（保住真正的死因数据）
            try:
                self.death_detail_snapshot = {}
                for _p in self.registered_players():
                    _tag = self.tag_of(_p) if hasattr(self, 'tag_of') else "P1"
                    self.death_detail_snapshot[_tag] = _p.freeze_damage_log() \
                        if hasattr(_p, 'freeze_damage_log') else list(getattr(_p, 'damage_log', []) or [])
            except Exception:
                pass
            # 死亡瞬间：强制落一帧 + 自动保存回放（多人模式同样生效）
            try:
                if getattr(self, 'replay_recorder', None) is not None:
                    self.replay_recorder.force_capture(self.registered_players(),
                                                       getattr(self, 'enemies', []))
                    self.replay_event("death", "玩家阵亡", 0, 0, 0, tag="death")
                    _saved = self.save_replay(tag="death")
                    self.death_replay_saved = bool(_saved)
            except Exception:
                pass
            self.state = GameState.DYING
        except Exception:
            pass

    def _find_killer(self):
        """从伤害日志里找致命一击来源"""
        try:
            for _p in self.registered_players():
                _log = getattr(_p, 'damage_log', None)
                if not _log:
                    continue
                _last = _log[-1]
                return {
                    "player": self.tag_of(_p) if hasattr(self, 'tag_of') else "P1",
                    "source": _last.get("source", ""),
                    "type": _last.get("type", ""),
                    "amount": _last.get("amount", 0.0),
                }
        except Exception:
            pass
        return None

    def _update_dying(self, dt):
        """DYING 状态推进：慢放特效 + 镜头拉近 + 计时结束进结算"""
        self.death_timer -= dt
        self.death_slow_t += dt
        # 慢放推进特效（粒子/浮字），世界逻辑不再推进，避免二次判定
        try:
            _sdt = dt * DEATH_SLOWMO
            if getattr(self, 'particles', None) is not None:
                self.particles.update(_sdt)
            for _ft in getattr(self, 'floating_texts', [])[:]:
                try:
                    _ft.lifetime -= _sdt
                except Exception:
                    pass
            if getattr(self, 'damage_numbers', None) is not None:
                for _dn in self.damage_numbers[:]:
                    try:
                        _dn.update(_sdt)
                    except Exception:
                        pass
        except Exception:
            pass
        # 镜头拉近倒地/死亡玩家
        try:
            _p = self.player
            for _c in self.registered_players():
                if not getattr(_c, 'alive', True) or getattr(_c, 'downed', False):
                    _p = _c
                    break
            _cam = self.camera_for(_p)
            if _cam is not None and hasattr(_cam, 'follow'):
                _cam.follow(_p.x, _p.y, dt, bounds=None)
        except Exception:
            pass
        # 命中反馈继续衰减（让最后一击的标记可见）
        self._feedback_tick(dt * DEATH_SLOWMO)
        if self.death_timer <= 0:
            self._finish_death()

    def _finish_death(self):
        """反应时间结束 → 正常结算流程"""
        try:
            from config import GameMode, GameState
            self.state = GameState.PLAYING   # 结算函数要求当前处于 PLAYING
            if getattr(self, 'config', None) is not None and \
                    getattr(self.config, 'game_mode', None) == GameMode.TIMED:
                if hasattr(self, '_settle_race_auto'):
                    self._settle_race_auto()
            else:
                self._trigger_multiplayer_game_over()
        except Exception:
            try:
                from config import GameState
                self.state = GameState.GAME_OVER
            except Exception:
                pass

    def skip_death_reaction(self):
        """玩家主动跳过反应时间"""
        try:
            from config import GameState
            if getattr(self, 'state', None) == GameState.DYING:
                self.death_timer = 0.0
                self._finish_death()
        except Exception:
            pass

    # ==================================================================
    # 3) 死亡详情
    # ==================================================================
    def death_detail_rows(self, window=15.0, limit=24):
        """结算页「死亡详情」面板数据

        返回 [(玩家标签, 距死亡秒数, 伤害值, 类型, 来源, 剩余HP)]，最近在前。
        """
        _rows = []
        try:
            _now = time.monotonic()
            _snap = getattr(self, 'death_detail_snapshot', None) or {}
            for _p in self.registered_players():
                _tag = self.tag_of(_p) if hasattr(self, 'tag_of') else "P1"
                # v2.8.2：优先用死亡瞬间的冻结快照，没有则退回实时日志
                _log = _snap.get(_tag)
                if _log is None:
                    _log = getattr(_p, 'damage_log', []) or []
                for _r in reversed(_log):
                    _ago = _now - _r.get("t", _now)
                    if _ago > window:
                        break
                    _rows.append({
                        "tag": _tag,
                        "ago": round(_ago, 2),
                        "amount": _r.get("amount", 0.0),
                        "type": _r.get("type", ""),
                        "source": _r.get("source", ""),
                        "hp": _r.get("hp", 0),
                    })
            _rows.sort(key=lambda r: r["ago"])
            _rows = _rows[:limit]
        except Exception:
            pass
        return _rows

    def death_detail_summary(self):
        """死亡详情摘要：总承伤、最大单次、致命来源"""
        try:
            _rows = self.death_detail_rows(window=9999, limit=9999)
            if not _rows:
                return {"total": 0.0, "max": 0.0, "hits": 0, "killer": None}
            _total = sum(r["amount"] for r in _rows)
            _mx = max(_rows, key=lambda r: r["amount"])
            _killer = self.death_killer or {}
            return {
                "total": round(_total, 1),
                "max": round(_mx["amount"], 1),
                "hits": len(_rows),
                "killer": _killer.get("source") or _mx.get("source", ""),
            }
        except Exception:
            return {"total": 0.0, "max": 0.0, "hits": 0, "killer": None}

    def toggle_death_detail(self):
        self.show_death_detail = not getattr(self, 'show_death_detail', False)
        self.death_detail_scroll = 0
        return self.show_death_detail
