# -*- coding: utf-8 -*-
"""主动格挡的输入 / 更新 / 渲染（v2.9.12）

- 键控：P1 `B`、P2 `M`（轻点=短格挡，按住=长按蓄力，鼠标改方向）
- 触控：右下角独立「格挡摇杆」（按下拖动改方向 + 蓄力，轻点=短格挡）
- 同屏双人分屏时，触摸落在左半屏驱动 P1、右半屏驱动 P2
"""
import math
import pygame
from config import BASE_WIDTH, BASE_HEIGHT
from combat_pkg import ARC_DEG, PERFECT_WINDOW

# 摇杆逻辑坐标（BASE_WIDTH/HEIGHT 坐标系），避开已有按钮
BLOCK_STICK_X = BASE_WIDTH - 120
BLOCK_STICK_Y = BASE_HEIGHT - 265
BLOCK_STICK_R = 52
# v2.9.16 多人半屏内的默认位置（避开射击/技能按钮），由 BlockStick 控件使用
BLOCK_STICK_MP_X = 330
BLOCK_STICK_MP_Y = BASE_HEIGHT - 250

# 只在 PLAYING 态生效
_PLAYING_STATES = ("PLAYING",)


class BlockMixin:
    # ------------------------------------------------------------ 基础
    def block_stick_ctrl(self, player=None):
        """返回该玩家对应的格挡摇杆**控件对象**（P1: game.block_stick / P2: p2_controls["block"]）"""
        p2 = getattr(self, "player2", None)
        if player is not None and player is p2:
            _c2 = getattr(self, "p2_controls", None) or {}
            return _c2.get("block") or getattr(self, "block_stick", None)
        return getattr(self, "block_stick", None)

    def _block_stick_geom(self, player=None, viewport_x=0):
        """v2.9.16：位置**唯一来源**是控件对象，输入判定与渲染不再各算一套。"""
        s = float(getattr(self, "scale", 1.0) or 1.0)
        ctrl = self.block_stick_ctrl(player)
        if ctrl is not None:
            ss = float(getattr(ctrl, "size_scale", 1.0) or 1.0)
            return (float(ctrl.base_x) * s + viewport_x,
                    float(ctrl.base_y) * s,
                    float(ctrl.base_radius) * s * ss)
        # 控件尚未创建（初始化顺序 / 旧存档）→ 回退到默认常量
        p2 = getattr(self, "player2", None)
        if player is not None and player is p2 and p2 is not None:
            sw = float(getattr(self, "scaled_width", 1280 * s) or 1280 * s)
            return (sw - (1280 - BLOCK_STICK_X) * s + viewport_x,
                    BLOCK_STICK_Y * s, BLOCK_STICK_R * s)
        return (BLOCK_STICK_X * s + viewport_x, BLOCK_STICK_Y * s, BLOCK_STICK_R * s)

    # ---------- 常驻格挡 CD（键控也能看见） ----------
    def draw_block_cd(self, screen, player, x, y, scale=1.0, font=None):
        """血条旁的格挡冷却圆环 + 剩余秒数。每位玩家各画一份。"""
        blk = getattr(player, "block", None) if player else None
        if blk is None:
            return
        try:
            r = max(14, int(22 * scale))
            cx, cy = int(x), int(y)
            cd = float(getattr(blk, "cooldown", 0.0) or 0.0)
            tot = max(0.01, float(getattr(blk, "cooldown_total", 1.0) or 1.0))
            active = bool(getattr(blk, "active", False))
            col = (110, 200, 255) if active else ((140, 80, 80) if cd > 0 else (80, 110, 140))
            pygame.draw.circle(screen, (18, 24, 34), (cx, cy), r)
            pygame.draw.circle(screen, col, (cx, cy), r, max(2, int(3 * scale)))
            if cd > 0:
                frac = min(1.0, cd / tot)
                pygame.draw.arc(screen, (255, 120, 90),
                                pygame.Rect(cx - r, cy - r, r * 2, r * 2),
                                -math.pi / 2, -math.pi / 2 + math.pi * 2 * frac,
                                max(2, int(4 * scale)))
            if font:
                txt = f"{cd:.1f}s" if cd > 0 else ("挡" if active else "格挡")
                lab = font.render(txt, True, (225, 235, 250))
                screen.blit(lab, (cx - lab.get_width() // 2, cy + r + 2))
        except Exception:
            pass

    def _block_owner_for_pos(self, pos):
        """v2.9.16：按**控件实际位置**判定归属，不再靠半屏硬切。
        这样 HUD 编辑器把 P2 格挡摇杆拖到任意位置后，触控依然驱动正确的玩家。"""
        p2 = getattr(self, "player2", None)
        if p2 is None or not getattr(self, "is_multiplayer_active", lambda: False)():
            return getattr(self, "player", None)
        _c1 = getattr(self, "block_stick", None)
        _c2 = (getattr(self, "p2_controls", None) or {}).get("block")
        s = float(getattr(self, "scale", 1.0) or 1.0)
        _d1 = math.hypot(pos[0] - _c1.base_x * s, pos[1] - _c1.base_y * s) \
            if _c1 is not None else 1e9
        _d2 = math.hypot(pos[0] - _c2.base_x * s, pos[1] - _c2.base_y * s) \
            if _c2 is not None else 1e9
        return p2 if _d2 < _d1 else getattr(self, "player", None)

    def _is_playing(self):
        try:
            return getattr(self, "state", None) is not None and \
                self.state.name in _PLAYING_STATES
        except Exception:
            return False

    # ------------------------------------------------------------ 触控
    def on_block_touch(self, kind, pos, fid, dt=1.0 / 60.0):
        """从统一事件流调用（down / move / up）"""
        if not self._is_playing():
            return
        ids = getattr(self, "_block_touch_ids", None)
        if ids is None:
            ids = self._block_touch_ids = {}
        if kind == "down":
            pl = self._block_owner_for_pos(pos)
            if pl is None or getattr(pl, "block", None) is None:
                return
            try:
                cx, cy, r = self._block_stick_geom(pl)
                if math.hypot(pos[0] - cx, pos[1] - cy) > r:
                    return
            except Exception:
                return
            ids[fid] = pl
            ang = math.degrees(math.atan2(pos[1] - cy, pos[0] - cx))
            pl.block.press(ang)
            _c = self.block_stick_ctrl(pl)
            if _c is not None:
                _c.sync_block(pl.block)
        elif kind == "move":
            pl = ids.get(fid)
            if pl is not None and getattr(pl, "block", None) is not None:
                # v2.9.15：cx/cy 是 down 分支的局部变量，move 里直接引用会
                # UnboundLocalError 打断整帧输入。按已绑定的玩家重新求摇杆中心。
                try:
                    cx, cy, _r = self._block_stick_geom(pl)
                except Exception:
                    cx, cy = pos[0], pos[1]
                # 拖到圈外也保持方向（不因超出半径而丢失蓄力）
                ang = math.degrees(math.atan2(pos[1] - cy, pos[0] - cx))
                pl.block.drag(ang, dt)
                _c = self.block_stick_ctrl(pl)
                if _c is not None:
                    _c.sync_block(pl.block)
        elif kind == "up":
            pl = ids.pop(fid, None)
            if pl is not None and getattr(pl, "block", None) is not None:
                pl.block.release()

    # ------------------------------------------------------------ 键控
    def on_block_key(self, key, down):
        if not self._is_playing():
            return
        mp = getattr(self, "multiplayer_mode", "")
        mapping = {pygame.K_b: self.player}
        if mp == "same_screen" and getattr(self, "player2", None) is not None:
            mapping[pygame.K_m] = self.player2
        pl = mapping.get(key)
        if pl is None or getattr(pl, "block", None) is None:
            return
        held = getattr(self, "_block_key_held", None)
        if held is None:
            held = self._block_key_held = set()
        if down:
            ang = float(getattr(pl, "facing_angle", 0.0) or 0.0)
            try:
                mx, my = pygame.mouse.get_pos()
                ang = math.degrees(math.atan2(
                    my - getattr(self, "scaled_height", 720) / 2.0,
                    mx - getattr(self, "scaled_width", 1280) / 2.0))
            except Exception:
                pass
            if pl.block.press(ang):
                held.add(key)
        else:
            held.discard(key)
            pl.block.release()

    # ------------------------------------------------------------ 每帧
    def update_block(self, dt):
        """主循环每帧调用：推进 P1/P2 格挡状态机 + 键控长按方向"""
        for pl in (getattr(self, "player", None), getattr(self, "player2", None)):
            if pl is None:
                continue
            blk = getattr(pl, "block", None)
            if blk is None:
                continue
            blk.update(dt)
        held = getattr(self, "_block_key_held", None)
        if held:
            for key in list(held):
                pl = self.player if key == pygame.K_b else getattr(self, "player2", None)
                if pl is None or getattr(pl, "block", None) is None:
                    held.discard(key)
                    continue
                try:
                    mx, my = pygame.mouse.get_pos()
                    ang = math.degrees(math.atan2(
                        my - getattr(self, "scaled_height", 720) / 2.0,
                        mx - getattr(self, "scaled_width", 1280) / 2.0))
                    pl.block.drag(ang, dt)
                except Exception:
                    pl.block.drag(float(getattr(pl, "facing_angle", 0.0)), dt)

    def reset_block_input(self):
        """切场景/开局时清理跨帧状态，避免按钮卡住"""
        self._block_touch_ids = {}
        self._block_key_held = set()

    # ------------------------------------------------------------ 渲染：摇杆
    def draw_block_stick(self, screen, font, scale=1.0, player=None):
        """v2.9.16：格挡摇杆 = 真正的 VirtualJoystick 控件，复用其它摇杆的
        底盘/摇杆头配色与绘制；只额外叠加格挡专属的蓄力环与冷却环。

        旧版手写深蓝圆盘 + 亮蓝指针，配色和其它摇杆不一致，且没有控件
        对象 → HUD 编辑器看不见、改不了。现在它就是一个普通摇杆控件，
        base_x/base_y/size_scale/alpha 全部走通用体系。
        """
        try:
            from config import ControlMode
            if getattr(self.config, "control_mode", None) != ControlMode.TOUCH \
                    and not getattr(self, "is_android", False):
                return
        except Exception:
            pass
        ctrl = self.block_stick_ctrl(player)
        if ctrl is None or not getattr(ctrl, "visible", True):
            return
        pl = player or getattr(self, "player", None)
        blk = getattr(pl, "block", None) if pl else None
        try:
            cx, cy, r = self._block_stick_geom(player)
            # 底盘与摇杆头：完全复用 VirtualJoystick.draw（GRAY/WHITE/LIGHT_GRAY）
            ctrl.sync_block(blk)
            ctrl.draw(screen, scale)
            if blk is None:
                return
            active = bool(blk.active)
            cd = float(blk.cooldown)
            cd_tot = max(0.01, float(blk.cooldown_total or 1.0))
            # 蓄力环（金黄色，与其它摇杆的进度环同一画法）
            if blk.charge > 0:
                pygame.draw.arc(screen, (255, 205, 90),
                                pygame.Rect(cx - r * 0.72, cy - r * 0.72,
                                            r * 1.44, r * 1.44),
                                -math.pi / 2,
                                -math.pi / 2 + math.pi * 2 * float(blk.charge),
                                max(2, int(4 * scale)))
            # 冷却环（暗红，覆盖整个底盘外圈）
            if cd > 0:
                pygame.draw.arc(screen, (200, 90, 90),
                                pygame.Rect(cx - r, cy - r, r * 2, r * 2),
                                -math.pi / 2,
                                -math.pi / 2 + math.pi * 2 * min(1.0, cd / cd_tot),
                                max(2, int(5 * scale)))
            # 激活时底盘描边提亮（不改配色，只是加一圈）
            if active:
                pygame.draw.circle(screen, (235, 235, 235), (int(cx), int(cy)),
                                   int(r), max(2, int(3 * scale)))
            if font:
                _lab = f"{cd:.1f}s" if cd > 0 else ("挡" if active else ctrl.label)
                _t = font.render(_lab, True, (225, 230, 235))
                screen.blit(_t, (int(cx - _t.get_width() / 2),
                                 int(cy + r * 0.34)))
        except Exception:
            pass

    # ------------------------------------------------------------ 渲染：世界层
    def draw_block_fx(self, screen, player, cam_x, cam_y, scale,
                      viewport_x=0, font=None):
        """玩家身前的格挡弧 / 完美窗口 / 格挡成功闪光"""
        blk = getattr(player, "block", None)
        if blk is None:
            return
        px = int((player.x - cam_x) * scale) + viewport_x
        py = int((player.y - cam_y) * scale)
        r = max(18, int((getattr(player, "size", 16) + 26) * scale))
        if blk.active:
            a = math.radians(blk.angle)
            half = math.radians(ARC_DEG)
            pts = [(px, py)]
            for i in range(13):
                aa = a - half + (2 * half) * i / 12
                pts.append((px + math.cos(aa) * r, py + math.sin(aa) * r))
            perfect = blk.active_time <= PERFECT_WINDOW
            col = (255, 245, 170) if perfect else (120, 200, 255)
            pygame.draw.polygon(screen, (36, 52, 70), pts)
            pygame.draw.polygon(screen, col, pts, max(1, int(3 * scale)))
            # 蓄力小星
            if blk.charge > 0.02:
                pygame.draw.circle(screen, (255, 205, 90),
                                   (int(px + math.cos(a) * r), int(py + math.sin(a) * r)),
                                   max(2, int(2 + 6 * blk.charge)))
        # v2.9.17：删除用户反馈的"神秘蓝色圆形（文字为格挡）"。
        # 旧实现在这里画一个淡蓝扩散圆环 +「格挡」浮字，格挡反馈和
        # HUD 上的 CD 圆环重复，多人分屏下更显得突兀。
        # 现在只保留一层极淡的金色弧闪（完美格挡时），不画圆、不写字。
        if blk.fx_timer > 0 and blk.fx_perfect:
            k = max(0.0, min(1.0, blk.fx_timer / 0.45))
            _r2 = int(r * (1.0 + (1.0 - k) * 0.35))
            _a0 = math.radians(float(getattr(blk, "angle", 0.0) or 0.0) - 40)
            pygame.draw.arc(screen, (255, 235, 150),
                            pygame.Rect(px - _r2, py - _r2, _r2 * 2, _r2 * 2),
                            _a0, _a0 + math.radians(80), max(2, int(3 * scale)))

    # ------------------------------------------------------------ 渲染：状态图标
    def draw_status_icons(self, screen, x, y, entity, font, scale=1.0):
        """实体状态条（流血/燃烧/冰冻/中毒…），供玩家 HUD 与敌人头顶复用"""
        st = getattr(entity, "status", None)
        if st is None:
            return
        from combat_pkg import status_meta
        states = st.active_states()
        if not states:
            return
        sx = int(x)
        for s in states:
            m = status_meta(s.kind)
            col = tuple(m.get("color", (200, 200, 200)))
            pygame.draw.circle(screen, col, (sx + 6, int(y)), max(3, int(5 * scale)))
            if font:
                t = font.render(f"{m.get('icon','?')}{s.stacks}", True, col)
                screen.blit(t, (sx + 13, int(y) - 7))
            sx += max(22, int(30 * scale))
