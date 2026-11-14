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
        """v2.9.19：按用户要求**删除**那枚蓝色圆环 + 「格挡 / 挡」文字。

        格挡状态改由世界层的护盾扇形与常驻盾牌标记表达（举盾蓝色填充、
        完美金色、冷却暗红），HUD 上不再叠一个会与按钮混淆的圆按钮。
        保留函数签名，避免各处调用点出错。
        """
        return

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
            # v2.9.19：不再在摇杆上写「格挡 / 挡」文字
        except Exception:
            pass

    # ------------------------------------------------------------ 渲染：世界层
    def draw_block_fx(self, screen, player, cam_x, cam_y, scale,
                      viewport_x=0, font=None):
        """v2.9.18 玩家身前的格挡表现（常驻标记 + 醒目护盾 + 成功反馈）。

        旧版只在 blk.active 的 0.36s 内画一层淡蓝多边形描边，颜色
        (120,200,255) 在暗色地表上几乎看不见，短按更是一闪而过 ——
        这就是"格挡还是看不见"的原因。现在：
          ① 常驻：玩家身侧一枚小盾牌标记，可格挡=亮蓝 / 冷却=暗红带秒数
          ② 举盾：半透明蓝填充 + 双层亮边 + 外圈光晕，完美窗口改金色
          ③ 命中：0.45s 金色扩散弧 + 文字，不再只认完美格挡
        """
        try:
            blk = getattr(player, "block", None)
            px = int((float(getattr(player, 'x', 0)) - cam_x) * scale) + viewport_x
            py = int((float(getattr(player, 'y', 0)) - cam_y) * scale)
            _sc = max(0.6, float(scale or 1.0))
            r = max(22, int((float(getattr(player, "size", 16) or 16) + 34) * _sc))

            # ---- ① 常驻状态标记（画在玩家右上角，绝不遮挡身体）----
            _bx = px + int(20 * _sc)
            _by = py - int(30 * _sc)
            _br = max(7, int(10 * _sc))
            if blk is not None:
                _cd = float(getattr(blk, "cooldown", 0.0) or 0.0)
                _active = bool(getattr(blk, "active", False))
                if _cd > 0:
                    _c, _edge = (70, 34, 38), (190, 95, 95)
                elif _active:
                    _c, _edge = (235, 215, 110), (255, 245, 180)
                else:
                    _c, _edge = (34, 62, 92), (120, 200, 255)
            else:
                _cd, _active = 0.0, False
                _c, _edge = (40, 46, 58), (110, 125, 145)
            pygame.draw.polygon(screen, _c, [
                (_bx, _by - _br), (_bx + _br, _by - _br // 2),
                (_bx + _br, _by + _br // 3), (_bx, _by + _br),
                (_bx - _br, _by + _br // 3), (_bx - _br, _by - _br // 2)])
            pygame.draw.polygon(screen, _edge, [
                (_bx, _by - _br), (_bx + _br, _by - _br // 2),
                (_bx + _br, _by + _br // 3), (_bx, _by + _br),
                (_bx - _br, _by + _br // 3), (_bx - _br, _by - _br // 2)],
                max(1, int(2 * _sc)))
            if font is not None and _cd > 0:
                _t = font.render("%.1f" % _cd, True, (235, 170, 165))
                screen.blit(_t, (_bx - _t.get_width() // 2, _by + _br + 1))

            if blk is None:
                return

            # ---- ② 举盾中的护盾扇形 ----
            if _active:
                a = math.radians(float(getattr(blk, "angle", 0.0) or 0.0))
                half = math.radians(ARC_DEG)
                pts = [(px, py)]
                for i in range(19):
                    aa = a - half + (2 * half) * i / 18
                    pts.append((px + math.cos(aa) * r, py + math.sin(aa) * r))
                perfect = float(getattr(blk, "active_time", 9.0) or 9.0) <= PERFECT_WINDOW
                col = (255, 235, 130) if perfect else (150, 220, 255)
                fill = (70, 58, 26) if perfect else (26, 58, 84)
                # 半透明填充（局部 Surface，尺寸小、不整屏）
                try:
                    _x0 = min(p[0] for p in pts); _y0 = min(p[1] for p in pts)
                    _w = max(2, int(max(p[0] for p in pts) - _x0) + 4)
                    _h = max(2, int(max(p[1] for p in pts) - _y0) + 4)
                    if 0 < _w < 1400 and 0 < _h < 1400:
                        _surf = pygame.Surface((_w, _h), pygame.SRCALPHA)
                        _loc = [(int(p[0] - _x0 + 2), int(p[1] - _y0 + 2)) for p in pts]
                        pygame.draw.polygon(_surf, (*fill, 150), _loc)
                        pygame.draw.polygon(_surf, (*col, 235), _loc, max(2, int(3 * _sc)))
                        screen.blit(_surf, (int(_x0 - 2), int(_y0 - 2)))
                except Exception:
                    pass
                # 外圈光晕弧（双层）
                pygame.draw.arc(screen, col,
                                pygame.Rect(px - r, py - r, r * 2, r * 2),
                                a - half, a + half, max(2, int(5 * _sc)))
                pygame.draw.arc(screen, (255, 255, 235),
                                pygame.Rect(px - r - 5, py - r - 5,
                                            (r + 5) * 2, (r + 5) * 2),
                                a - half * 0.7, a + half * 0.7, max(1, int(2 * _sc)))
                # 蓄力小星
                if float(getattr(blk, "charge", 0.0) or 0.0) > 0.02:
                    pygame.draw.circle(screen, (255, 215, 100),
                                       (int(px + math.cos(a) * r), int(py + math.sin(a) * r)),
                                       max(2, int(3 + 7 * float(blk.charge) * _sc)))
                if font is not None and perfect:
                    _pt = font.render("完美窗口", True, (255, 240, 160))
                    screen.blit(_pt, (px - _pt.get_width() // 2,
                                      py - r - int(20 * _sc)))

            # ---- ③ 成功格挡反馈（普通/完美都给，0.45s）----
            _fx = float(getattr(blk, "fx_timer", 0.0) or 0.0)
            if _fx > 0:
                k = max(0.0, min(1.0, _fx / 0.45))
                _is_perfect = bool(getattr(blk, "fx_perfect", False))
                _col = (255, 235, 150) if _is_perfect else (150, 220, 255)
                _r2 = int(r * (1.0 + (1.0 - k) * 0.55))
                _a0 = math.radians(float(getattr(blk, "angle", 0.0) or 0.0) - ARC_DEG / 2)
                pygame.draw.arc(screen, _col,
                                pygame.Rect(px - _r2, py - _r2, _r2 * 2, _r2 * 2),
                                _a0, _a0 + math.radians(ARC_DEG), max(2, int(6 * _sc * k)))
                if font is not None:
                    _t = font.render("完美格挡!" if _is_perfect else "格挡!", True, _col)
                    screen.blit(_t, (px - _t.get_width() // 2, py - _r2 - int(18 * _sc)))
        except Exception:
            pass

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
