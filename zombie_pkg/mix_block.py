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

# 只在 PLAYING 态生效
_PLAYING_STATES = ("PLAYING",)


class BlockMixin:
    # ------------------------------------------------------------ 基础
    def _block_stick_geom(self, player=None, viewport_x=0):
        s = float(getattr(self, "scale", 1.0) or 1.0)
        p2 = getattr(self, "player2", None)
        # 同屏双人：P1 摇杆在左半屏右下，P2 在右半屏右下
        if player is not None and getattr(self, "multiplayer_mode", "") == "same_screen" \
                and p2 is not None:
            sw = float(getattr(self, "scaled_width", 1280 * s) or 1280 * s)
            _half = sw * 0.5
            # v2.9.15：以半屏右下角为基准，P1/P2 各自视口内位置完全对称。
            # 旧式 `sw*0.5 - (1280-X)*s` 在屏幕宽高比不是 16:9 时会把 P1
            # 摇杆推到屏幕中间，出现"底盘和摇杆不在一处"。
            _inset = (1280 - BLOCK_STICK_X) * s
            if player is p2:
                return (sw - _inset, BLOCK_STICK_Y * s, BLOCK_STICK_R * s)
            return (_half - _inset, BLOCK_STICK_Y * s, BLOCK_STICK_R * s)
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
        """分屏时按左右半屏决定驱动哪位玩家"""
        p2 = getattr(self, "player2", None)
        # v2.9.13：不再依赖可能不存在的 split_screen 属性 —— 只要同屏双人
        # 有 P2，就按左右半屏分配格挡摇杆（此前 P2 触控永远驱动 P1）。
        if p2 is not None and getattr(self, "multiplayer_mode", "") == "same_screen":
            try:
                return p2 if pos[0] >= self.scaled_width * 0.5 else self.player
            except Exception:
                return self.player
        return self.player

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
        elif kind == "move":
            pl = ids.get(fid)
            if pl is not None and getattr(pl, "block", None) is not None:
                # v2.9.15：cx/cy 是 down 分支的局部变量，move 里直接引用会
                # UnboundLocalError 打断整帧输入。按已绑定的玩家重新求摇杆中心。
                try:
                    cx, cy, _r = self._block_stick_geom(pl)
                except Exception:
                    cx, cy = pos[0], pos[1]
                ang = math.degrees(math.atan2(pos[1] - cy, pos[0] - cx))
                pl.block.drag(ang, dt)
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
        """HUD 上的格挡摇杆（仅触控模式显示）"""
        try:
            from config import ControlMode
            if getattr(self.config, "control_mode", None) != ControlMode.TOUCH \
                    and not getattr(self, "is_android", False):
                return
        except Exception:
            pass
        cx, cy, r = self._block_stick_geom(player)
        pl = player or getattr(self, "player", None)
        blk = getattr(pl, "block", None) if pl else None
        active = bool(blk and blk.active)
        cd = float(blk.cooldown) if blk else 0.0
        cd_tot = float(blk.cooldown_total) if blk else 1.0
        # 底盘
        pygame.draw.circle(screen, (24, 30, 40), (int(cx), int(cy)), int(r))
        pygame.draw.circle(screen, (70, 95, 125) if not active else (110, 200, 255),
                           (int(cx), int(cy)), int(r), max(2, int(3 * scale)))
        # 方向指针
        if blk is not None:
            a = math.radians(blk.angle)
            ex = cx + math.cos(a) * r * 0.82
            ey = cy + math.sin(a) * r * 0.82
            pygame.draw.line(screen, (150, 225, 255), (int(cx), int(cy)),
                             (int(ex), int(ey)), max(2, int(4 * scale)))
            pygame.draw.circle(screen, (210, 245, 255), (int(ex), int(ey)),
                               max(3, int(6 * scale)))
        # 蓄力环
        if blk is not None and blk.charge > 0:
            pygame.draw.arc(screen, (255, 205, 90),
                            pygame.Rect(cx - r * 0.72, cy - r * 0.72,
                                        r * 1.44, r * 1.44),
                            -math.pi / 2, -math.pi / 2 + math.pi * 2 * blk.charge,
                            max(2, int(4 * scale)))
        # 冷却环
        if cd > 0 and cd_tot > 0:
            pygame.draw.arc(screen, (140, 70, 70),
                            pygame.Rect(cx - r, cy - r, r * 2, r * 2),
                            -math.pi / 2, -math.pi / 2 + math.pi * 2 * (cd / cd_tot),
                            max(2, int(5 * scale)))
        if font:
            lab = font.render("格挡", True, (200, 225, 245))
            screen.blit(lab, (int(cx - lab.get_width() / 2),
                              int(cy + r * 0.30)))

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
        if blk.fx_timer > 0:
            k = blk.fx_timer / 0.45
            col = (255, 240, 150) if blk.fx_perfect else (130, 210, 255)
            pygame.draw.circle(screen, col, (px, py),
                               int(r * (1.0 + (1.0 - k) * 0.9)),
                               max(2, int(4 * scale)))
            if font and blk.fx_perfect:
                t = font.render("完美格挡!", True, col)
                screen.blit(t, (int(px - t.get_width() / 2), int(py - r - 28)))
            elif font:
                t = font.render("格挡", True, col)
                screen.blit(t, (int(px - t.get_width() / 2), int(py - r - 24)))

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
