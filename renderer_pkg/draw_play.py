# -*- coding: utf-8 -*-
"""PlayMixin - 由 renderer.py 自动拆分，逻辑等价"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染系统模块 - 黑暗色调版：技能卡选择、防爆套装动画、半透明范围圈"""

import pygame
import mod_loader
import math
import random
from config import *
from buff import BuffType
from codex import codex_unlock_manager
from weapons import Weapon

class PlayMixin:
    def _draw_playing(self):
        if not self.game.world or not self.game.player:
            return
        if self.game.is_multiplayer_active():
            self._draw_playing_split()
            return
        self._draw_playing_core(self.game.player, self.game.camera)
        self._draw_hud()

    def _draw_playing_split(self):
        """同屏双人：左右分屏，各玩家一个视口"""
        orig_screen = self.screen
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        half = sw // 2
        pairs = [(self.game.player, self.game.camera, "P1"), (self.game.player2, self.game.camera2, "P2")]
        for idx, (player, camera, label) in enumerate(pairs):
            if player is None or camera is None:
                continue
            rect = pygame.Rect(idx * half, 0, half, sh)
            self.screen = orig_screen.subsurface(rect)
            self._draw_playing_core(player, camera)
            self.screen = orig_screen
            # P2 键控技能 U 长按预瞄（右半屏；照 P1 G 键模板）
            if idx == 1 and self.game.config.control_mode == ControlMode.KEYBOARD:
                c2 = self.game.p2_controls
                if c2 and c2["skill_caster"].is_aiming:
                    c2["skill_caster"]._draw_aim_preview(self.screen, self.game.p2_selected_skill or SkillType.GRENADE, self.game.scale)
            # 分屏 HUD
            self._draw_hud_split(player, label, rect)
        # 中线与标签
        pygame.draw.line(orig_screen, (120, 90, 140), (half, 0), (half, sh), max(2, int(2 * self.game.scale)))
        for idx, label in enumerate(["P1", "P2"]):
            tag = self.game.font_small.render(label, True, GOLD)
            orig_screen.blit(tag, (idx * half + 8, 6))
        self.screen = orig_screen

    def _draw_hud_split(self, player, label, rect):
        """双人分屏 HUD：完整迷你HUD（血条/经验/武器弹药/技能/时间/得分/键位提示/倒地救援/触控控件）"""
        g = self.game
        scale = g.scale
        half_w = rect.width
        bx = rect.x + int(half_w * 0.2)
        bar_w = int(half_w * 0.6)
        # ===== 顶部：时间/尸潮倒计时（P1）与波次（P2） =====
        hm = getattr(g, 'horde_manager', None)
        if label == "P1":
            try:
                t_text, is_cd = hm.get_time_display() if hm else ("00:00", True)
                t_color = RED if (is_cd and int(t_text.split(":")[0]) * 60 + int(t_text.split(":")[1]) < 30) else WHITE
                t_txt = g.font.render(t_text, True, t_color)
                self.screen.blit(t_txt, t_txt.get_rect(midtop=(rect.x + half_w // 2, rect.y + int(4 * scale))))
            except Exception:
                tl = max(0, int(getattr(g, 'time_left', 0)))
                t_txt = g.font.render(f"{tl // 60:02d}:{tl % 60:02d}", True, WHITE)
                self.screen.blit(t_txt, t_txt.get_rect(midtop=(rect.x + half_w // 2, rect.y + int(4 * scale))))
        else:
            if hm and getattr(hm, 'is_horde_active', lambda: False)():
                w_txt = g.font.render("尸潮!", True, RED)
            else:
                wv = getattr(g, 'wave_count', 0)
                w_txt = g.font.render(f"波次 {wv}", True, (150, 220, 255))
            self.screen.blit(w_txt, w_txt.get_rect(midtop=(rect.x + half_w // 2, rect.y + int(4 * scale))))
        # ===== 血条 =====
        hp_pct = max(0, player.hp) / max(1, player.max_hp)
        bar_h = int(14 * scale)
        by = rect.y + int(26 * scale)
        pygame.draw.rect(self.screen, (40, 40, 40), (bx, by, bar_w, bar_h))
        pygame.draw.rect(self.screen, (220, 60, 60), (bx, by, int(bar_w * hp_pct), bar_h))
        pygame.draw.rect(self.screen, (200, 200, 200), (bx, by, bar_w, bar_h), 1)
        hp_txt = g.font_small.render(f"{max(0,int(player.hp))}/{player.max_hp}", True, WHITE)
        self.screen.blit(hp_txt, (bx, by - int(16 * scale)))
        # ===== 经验条 =====
        if hasattr(player, 'exp_to_level') and player.exp_to_level:
            exp_pct = max(0.0, min(1.0, player.exp / max(1, player.exp_to_level)))
            exb = pygame.Rect(bx, rect.y + int(46 * scale), bar_w, int(5 * scale))
            pygame.draw.rect(self.screen, (40, 40, 60), exb)
            pygame.draw.rect(self.screen, (120, 200, 255), (exb.x, exb.y, int(exb.w * exp_pct), exb.h))
            lv = g.font_small.render(f"Lv.{player.level}", True, (150, 220, 255))
            self.screen.blit(lv, (rect.x + int(half_w * 0.82), rect.y + int(38 * scale)))
        # ===== 体力条 =====
        if hasattr(player, 'stamina') and player.max_stamina > 0:
            st_ratio = max(0.0, min(1.0, player.stamina / player.max_stamina))
            stb = pygame.Rect(bx, rect.y + int(53 * scale), bar_w, int(4 * scale))
            st_color = (70, 170, 255)
            if getattr(player, 'stamina_exhausted', False):
                st_color = (220, 70, 70)
            pygame.draw.rect(self.screen, (20, 25, 40), stb)
            pygame.draw.rect(self.screen, st_color, (stb.x, stb.y, int(stb.w * st_ratio), stb.h))
            st_txt = g.font_small.render(f"体力 {int(player.stamina)}/{int(player.max_stamina)}", True, st_color)
            self.screen.blit(st_txt, (bx, rect.y + int(57 * scale)))
        # ===== 武器 + 弹药 =====
        w = player.get_current_weapon() if hasattr(player, 'get_current_weapon') else None
        if w:
            wname = getattr(w, 'display_name', None) or getattr(w, 'name', '?')
            w_txt = g.font_small.render(f"{wname}", True, GOLD)
            self.screen.blit(w_txt, (bx, rect.y + int(64 * scale)))
            ammo = getattr(w, 'current_ammo', None)
            if ammo is not None and ammo != "∞":
                a_txt = g.font_small.render(f"弹药 {ammo}/{getattr(w, 'max_ammo', '?')}", True, (210, 210, 215))
                self.screen.blit(a_txt, (bx, rect.y + int(78 * scale)))
        # ===== 技能栏（当前技能 + 冷却） =====
        sk = getattr(g, 'p2_selected_skill', None) if label == "P2" else getattr(g, 'selected_skill', None)
        if sk and hasattr(player, 'skill_tree'):
            sobj = player.skill_tree.get_skill(sk)
            if sobj:
                sname = getattr(sobj, 'name', '技能')
                cd_left = player.active_skills.get(sk, 0)
                if cd_left > 0:
                    s_txt = g.font_small.render(f"技能: {sname} ({cd_left:.0f}s)", True, (180, 180, 190))
                else:
                    s_txt = g.font_small.render(f"技能: {sname}", True, (150, 230, 150))
                self.screen.blit(s_txt, (bx, rect.y + int(92 * scale)))
        # ===== Buff 简览 =====
        try:
            _buffs = player.buff_manager.get_active_buffs()
            if _buffs:
                _bnames = [getattr(b, 'name', str(b.buff_type))[:6] for b in _buffs[:3]]
                b_txt = g.font_small.render("Buff: " + "·".join(_bnames), True, (200, 160, 255))
                self.screen.blit(b_txt, (bx, rect.y + int(106 * scale)))
        except Exception:
            pass
        # ===== 得分 =====
        if hasattr(player, 'score'):
            sc = g.font_small.render(f"分数 {player.score}", True, (240, 230, 150))
            self.screen.blit(sc, (rect.x + int(half_w * 0.82), rect.y + int(64 * scale)))
        # ===== 键位提示（键盘模式） =====
        if g.config.control_mode == ControlMode.KEYBOARD:
            if label == "P1":
                hint = "WASD移动 · 鼠标射击 · E技能 · Q投掷 · Ctrl疾跑"
            else:
                hint = "方向键移动 · J射击 · U技能 · O投掷 · Shift疾跑"
            ht = g.font_small.render(hint, True, (200, 200, 215))
            self.screen.blit(ht, (rect.x + half_w // 2 - ht.get_width() // 2, rect.y + int(120 * scale)))
        # ===== 倒地状态：显示救援进度条 =====
        if getattr(player, 'downed', False):
            pygame.draw.rect(self.screen, (80, 70, 20), (bx, rect.y + int(132 * scale), bar_w, int(10 * scale)))
            prog = max(0.0, min(1.0, getattr(player, 'rescue_progress', 0) / 2.5))
            pygame.draw.rect(self.screen, (240, 220, 80), (bx, rect.y + int(132 * scale), int(bar_w * prog), int(10 * scale)))
            pygame.draw.rect(self.screen, (255, 255, 255), (bx, rect.y + int(132 * scale), bar_w, int(10 * scale)), 1)
            dtxt = g.font_small.render("倒地 · 队友靠近救援", True, (240, 230, 120))
            self.screen.blit(dtxt, (bx, rect.y + int(144 * scale)))
        # ===== 触控控件（仅触控模式） =====
        if g.config.control_mode == ControlMode.TOUCH and not g.is_network_client_render():
            if label == "P1":
                self._draw_touch_controls_split(g, left=True)
            else:
                self._draw_touch_controls_split(g, left=False)

    def _draw_touch_controls_split(self, g, left):
        """把触控控件画进对应半屏（left=True 用 P1 控件；否则 P2 控件），与单机触控 UI 同款"""
        scale = g.scale
        fs = g.font_small
        if left:
            pl = g.player
            g.joystick.draw(self.screen, scale)
            g.aim_button.draw(self.screen, fs, scale)
            # 射击（防爆套装→肘击，与单机一致）
            sb = g.touch_buttons.get("shoot")
            if sb and pl.riot_gear.equipped:
                _ol, _oc = sb.label, sb.color
                sb.label, sb.color = "肘击", PURPLE
                sb.draw(self.screen, fs, scale)
                sb.label, sb.color = _ol, _oc
            else:
                sb.draw(self.screen, fs, scale)
            g.touch_buttons.get("pause").draw(self.screen, fs, scale)
            g.touch_buttons.get("sprint").draw(self.screen, fs, scale)
            # 技能（与单机同款：显示技能名）
            _sk = g.selected_skill
            _sobj = pl.skill_tree.get_skill(_sk) if _sk else None
            g.skill_selector.draw(self.screen, fs, _sobj.name if _sobj else "空", _sobj.icon_color if _sobj else BLUE, scale)
            g.skill_caster.draw(self.screen, fs, _sk, _sobj.name if _sobj else "空", _sobj.icon_color if _sobj else ORANGE, scale)
            # 投掷（与单机同款：缩写+数量角标）
            _tt = g.selected_throwable
            _t_abbr = {"incendiary": "燃", "smoke": "烟", "cluster": "束", "emp": "E"}.get(_tt, "投")
            _t_col = g.throwable_colors.get(_tt, ORANGE)
            g.throwable_switch_btn.draw(self.screen, fs, scale)
            g.throwable_caster.draw(self.screen, fs, None, _t_abbr, _t_col, scale)
            _t_count = getattr(pl, 'throwables', {}).get(_tt, 0)
            if _t_count > 0:
                _bx, _by, _br = g.throwable_caster.get_scaled_pos(scale)
                _bt = fs.render(str(_t_count), True, WHITE)
                _bb = pygame.Surface((_bt.get_width() + 8, _bt.get_height() + 4), pygame.SRCALPHA)
                _bb.fill((0, 0, 0, 180))
                self.screen.blit(_bb, (int(_bx + _br - _bt.get_width() - 4), int(_by - _br + 2)))
                self.screen.blit(_bt, (int(_bx + _br - _bt.get_width()), int(_by - _br + 4)))
        else:
            c2 = g.p2_controls
            pl = g.player2
            c2["joystick"].draw(self.screen, scale)
            c2["aim"].draw(self.screen, fs, scale)
            sb = c2.get("shoot")
            if sb and pl.riot_gear.equipped:
                _ol, _oc = sb.label, sb.color
                sb.label, sb.color = "肘击", PURPLE
                sb.draw(self.screen, fs, scale)
                sb.label, sb.color = _ol, _oc
            else:
                sb.draw(self.screen, fs, scale)
            c2["pause"].draw(self.screen, fs, scale)
            c2["sprint"].draw(self.screen, fs, scale)
            _sk = getattr(g, 'p2_selected_skill', None)
            _sobj = pl.skill_tree.get_skill(_sk) if _sk else None
            c2["skill_selector"].draw(self.screen, fs, _sobj.name if _sobj else "空", _sobj.icon_color if _sobj else BLUE, scale)
            c2["skill_caster"].draw(self.screen, fs, _sk, _sobj.name if _sobj else "空", _sobj.icon_color if _sobj else ORANGE, scale)
            _tt = getattr(g, 'p2_selected_throwable', "incendiary")
            _t_abbr = {"incendiary": "燃", "smoke": "烟", "cluster": "束", "emp": "E"}.get(_tt, "投")
            _t_col = g.throwable_colors.get(_tt, ORANGE)
            c2["throwable_switch"].draw(self.screen, fs, scale)
            c2["throwable_caster"].draw(self.screen, fs, None, _t_abbr, _t_col, scale)
            _t_count = getattr(pl, 'throwables', {}).get(_tt, 0)
            if _t_count > 0:
                _bx, _by, _br = c2["throwable_caster"].get_scaled_pos(scale)
                _bt = fs.render(str(_t_count), True, WHITE)
                _bb = pygame.Surface((_bt.get_width() + 8, _bt.get_height() + 4), pygame.SRCALPHA)
                _bb.fill((0, 0, 0, 180))
                self.screen.blit(_bb, (int(_bx + _br - _bt.get_width() - 4), int(_by - _br + 2)))
                self.screen.blit(_bt, (int(_bx + _br - _bt.get_width()), int(_by - _br + 4)))

    def _draw_playing_core(self, player, camera):
        if not self.game.world or not player:
            return

        scale = self.game.scale
        shake_x = camera.shake_x
        shake_y = camera.shake_y
        cam_x = camera.x - shake_x
        cam_y = camera.y - shake_y

        # 绘制世界
        self.game.world.draw(self.screen, cam_x, cam_y, scale, self.game.assets)

        # 绘制可拾取文本资料
        for text_item in self.game.text_items:
            text_item.draw(self.screen, cam_x, cam_y, scale, self.game.assets)

        # 绘制剧情收集物（故事模式）
        if self.game.config.game_mode == GameMode.STORY:
            # v2.0.11 幸存者 NPC（青色标记 + 呼吸光圈）
            npc = getattr(self.game, 'survivor_npc', None)
            if npc and npc.get("active"):
                nix = int((npc["x"] - cam_x) * scale)
                niy = int((npc["y"] - cam_y) * scale)
                np_pulse = math.sin(pygame.time.get_ticks() / 180) * 0.25 + 1.0
                np_size = int(14 * scale * np_pulse)
                np_glow = pygame.Surface((np_size * 4, np_size * 4), pygame.SRCALPHA)
                pygame.draw.circle(np_glow, (120, 220, 255, 70), (np_size * 2, np_size * 2), np_size * 2)
                self.screen.blit(np_glow, (nix - np_size * 2, niy - np_size * 2))
                pygame.draw.circle(self.screen, (120, 220, 255), (nix, niy), np_size, max(1, int(scale)))
                pygame.draw.circle(self.screen, (200, 240, 255), (nix, niy), int(np_size * 0.6))
                pygame.draw.circle(self.screen, (60, 120, 160), (nix, niy), max(1, int(2 * scale)))
                # 头顶"幸存者"标签
                tag = self.game.font.render("幸存者", True, (120, 220, 255))
                self.screen.blit(tag, (nix - tag.get_width() // 2, niy - np_size - int(18 * scale)))

            for item in self.game.story_fragment_items:
                ix = int((item["x"] - cam_x) * scale)
                iy = int((item["y"] - cam_y) * scale)
                # 脉冲动画
                pulse = math.sin(pygame.time.get_ticks() / 200) * 0.3 + 1.0
                size = int(12 * scale * pulse)
                # 发光效果
                glow_surf = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*GOLD[:3], 60), (size * 2, size * 2), size * 2)
                self.screen.blit(glow_surf, (ix - size * 2, iy - size * 2))
                # 纸张图标
                pygame.draw.rect(self.screen, (240, 230, 200), (ix - size, iy - size, size * 2, size * 2.5))
                pygame.draw.rect(self.screen, GOLD, (ix - size, iy - size, size * 2, size * 2.5), max(1, int(scale)))
                # 文字线条
                for li in range(3):
                    line_y = iy - size + int(4 * scale) + li * int(4 * scale)
                    pygame.draw.line(self.screen, DARK_GRAY,
                                   (ix - size + int(3 * scale), line_y),
                                   (ix + size - int(3 * scale), line_y), max(1, int(scale)))
                # "资料"标签
                label = self.game.font_small.render("资料", True, GOLD)
                self.screen.blit(label, (ix - label.get_width() // 2, iy - size - int(15 * scale)))

        # 绘制经验球
        for orb in self.game.exp_orbs:
            orb.draw(self.screen, cam_x, cam_y, scale)

        # 绘制敌人特殊攻击前摇预警（在敌人下方）
        for enemy in self.game.enemies:
            if getattr(enemy, "special_windup_timer", 0) > 0 and getattr(enemy, "special_windup_radius", 0) > 0:
                ex = int((enemy.x - cam_x) * scale)
                ey = int((enemy.y - cam_y) * scale)
                r = int(enemy.special_windup_radius * scale)
                # 前摇进度（0到1，越接近1越危险）
                windup_config = getattr(enemy, "_get_windup_config", lambda x: None)(enemy.special_windup_type)
                total_duration = windup_config["duration"] if windup_config else 1.0
                progress = 1.0 - (enemy.special_windup_timer / total_duration)
                # 绘制半透明红色预警圆圈
                warning_surface = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                alpha = int(80 + 100 * progress)  # 透明度随进度增加
                pygame.draw.circle(warning_surface, (255, 50, 50, alpha), (r, r), r)
                pygame.draw.circle(warning_surface, (255, 100, 100, 200), (r, r), r, max(2, int(3 * scale)))
                self.screen.blit(warning_surface, (ex - r, ey - r))
                # 绘制前摇进度条
                bar_width = int(40 * scale)
                bar_height = int(4 * scale)
                bar_x = ex - bar_width // 2
                bar_y = ey - r - int(15 * scale)
                pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
                pygame.draw.rect(self.screen, (255, 100, 100), (bar_x, bar_y, int(bar_width * progress), bar_height))

        # 绘制敌人
        for enemy in self.game.enemies:
            enemy.draw(self.screen, cam_x, cam_y, self.game.font, scale, self.game.assets,
                       getattr(player, 'x', None), getattr(player, 'y', None))
            # 技能前摇预警：释放带前摇的技能时显示警示（红色闪烁圈+危险标记）
            if (getattr(enemy, 'boss_is_executing', False)
                    or getattr(enemy, 'skill_windup', 0) > 0
                    or getattr(enemy, 'skill_telegraph', 0) > 0
                    or getattr(enemy, 'special_windup_timer', 0) > 0):
                self._draw_skill_warning(enemy, cam_x, cam_y, scale)

        # 绘制玩家（双人模式两个玩家都画，彼此可见）
        if self.game.player2 is not None:
            for p in (self.game.player, self.game.player2):
                if p is None:
                    continue
                p.draw(self.screen, cam_x, cam_y, self.game.font, scale)
                if getattr(p, 'downed', False):
                    dtag = self.game.font_small.render("倒地", True, (240, 230, 120))
                    dx = int((p.x - cam_x) * scale)
                    dy = int((p.y - cam_y) * scale)
                    self.screen.blit(dtag, (dx - dtag.get_width() // 2, dy - int(24 * scale)))
        else:
            player.draw(self.screen, cam_x, cam_y, self.game.font, scale)

        # 近战挥砍动画
        if hasattr(self.game, 'melee_attack_active') and self.game.melee_attack_active:
            self._draw_melee_attack(cam_x, cam_y, scale)

        # 绘制投射物
        for proj in self.game.projectiles:
            proj.draw(self.screen, cam_x, cam_y, scale)

        for proj in self.game.enemy_projectiles:
            proj.draw(self.screen, cam_x, cam_y, scale)

        # 绘制烟雾区域
        if hasattr(self.game, 'smoke_zones'):
            for zone in self.game.smoke_zones:
                px = int((zone["x"] - cam_x) * scale)
                py = int((zone["y"] - cam_y) * scale)
                r = int(zone["radius"] * scale)
                alpha = int(100 * min(1.0, zone["timer"] / 2.0))
                smoke_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(smoke_surf, (120, 120, 120, alpha), (r, r), r)
                self.screen.blit(smoke_surf, (px - r, py - r))

        # 绘制手雷
        if hasattr(self.game, 'grenades'):
            for grenade in self.game.grenades:
                # 手雷飞行轨迹
                progress = 1 - grenade["timer"] / 1.5
                gx = grenade["x"] + (grenade["target_x"] - grenade["x"]) * progress
                gy = grenade["y"] + (grenade["target_y"] - grenade["y"]) * progress
                px = int((gx - cam_x) * scale)
                py = int((gy - cam_y) * scale)
                # 闪烁警告
                flash = abs(math.sin(pygame.time.get_ticks() / 100))
                color = (255, int(100 * flash), 0)
                pygame.draw.circle(self.screen, color, (px, py), max(3, int(6 * scale)))
                # 目标标记
                tpx = int((grenade["target_x"] - cam_x) * scale)
                tpy = int((grenade["target_y"] - cam_y) * scale)
                pygame.draw.circle(self.screen, (255, 50, 50, 100), (tpx, tpy), int(grenade["radius"] * scale), max(1, int(2 * scale)))

        # 绘制玩家投掷物（飞行中）
        if hasattr(self.game, 'grenades_in_flight'):
            for g in self.game.grenades_in_flight:
                px = int((g["x"] - cam_x) * scale)
                py = int((g["y"] - cam_y) * scale)
                color = FIRE_ORANGE if g["type"] == "incendiary" else (SMOKE_GRAY if g["type"] == "smoke" else (CYAN if g["type"] == "emp" else ORANGE))
                pygame.draw.circle(self.screen, color, (px, py), max(3, int(7 * scale)))
                # 目标标记
                tpx = int((g["target_x"] - cam_x) * scale)
                tpy = int((g["target_y"] - cam_y) * scale)
                pygame.draw.circle(self.screen, color + (80,), (tpx, tpy), int(30 * scale), max(1, int(2 * scale)))
        
        # 绘制怪物投掷物
        if hasattr(self.game, 'enemy_throwables'):
            for g in self.game.enemy_throwables:
                px = int((g["x"] - cam_x) * scale)
                py = int((g["y"] - cam_y) * scale) - int(g.get("height", 0) * scale)
                if g["type"] == "fire":
                    color = FIRE_ORANGE
                elif g["type"] == "acid":
                    color = POISON_GREEN
                elif g["type"] == "curse":
                    color = PURPLE
                else:
                    color = GRAY
                pygame.draw.circle(self.screen, color, (px, py), max(4, int(8 * scale)))
                pygame.draw.circle(self.screen, WHITE, (px, py), max(2, int(3 * scale)))
                # 阴影
                shadow_y = int((g["y"] - cam_y) * scale)
                pygame.draw.circle(self.screen, (0, 0, 0, 100), (px, shadow_y), max(3, int(5 * scale)))
                # 目标标记
                tpx = int((g["target_x"] - cam_x) * scale)
                tpy = int((g["target_y"] - cam_y) * scale)
                pygame.draw.circle(self.screen, color + (100,), (tpx, tpy), int(25 * scale), max(1, int(2 * scale)))

        # 绘制燃烧区域
        self._draw_fire_zones(cam_x, cam_y, scale)

        # 绘制烟雾区域
        self._draw_smoke_zones(cam_x, cam_y, scale)

        # 绘制空袭飞机
        self._draw_airstrike_planes(cam_x, cam_y, scale)

        # 绘制自动炮塔
        self._draw_turrets(cam_x, cam_y, scale)

        # 绘制粒子
        self.game.particles.draw(self.screen, cam_x, cam_y, scale)

        # 绘制伤害数字
        for dn in self.game.damage_numbers:
            dn.draw(self.screen, self.game.font, cam_x, cam_y, scale)

        # 绘制浮动文字
        for ft in self.game.floating_texts:
            ft.draw(self.screen, self.game.font, cam_x, cam_y, scale)

        # 绘制刀光弧斩特效（死神镰刀/枪械曳光）
        for sa in getattr(self.game, 'slash_arcs', []):
            sa.draw(self.screen, cam_x, cam_y, scale)

        # 绘制圆形横扫扩散环（死神镰刀换弹横扫）
        for sr in getattr(self.game, 'sweep_rings', []):
            prog = 1.0 - (sr["life"] / sr["max_life"])
            cr = int((sr["r"] + (sr["max_r"] - sr["r"]) * prog) * scale)
            cxp = int((sr["x"] - cam_x) * scale)
            cyp = int((sr["y"] - cam_y) * scale)
            alpha = int(180 * (1.0 - prog))
            ring_surf = pygame.Surface((cr * 2 + 12, cr * 2 + 12), pygame.SRCALPHA)
            cc = cr + 6
            col = sr["color"]
            pygame.draw.circle(ring_surf, (*col[:3], alpha // 2), (cc, cc), cr + 3, sr["width"] + 2)
            pygame.draw.circle(ring_surf, (*col[:3], alpha), (cc, cc), cr, sr["width"])
            pygame.draw.circle(ring_surf, (240, 190, 255, alpha), (cc, cc), cr - 3, max(1, sr["width"] // 3))
            self.screen.blit(ring_surf, (cxp - cc, cyp - cc))

        # 绘制创伤效果（屏幕边缘血溅）
        self._draw_trauma_effect()

        # 绘制吸血屏幕效果
        self._draw_lifesteal_effect()

        # 绘制Buff屏幕效果（回血发绿、狂暴动态模糊等）
        self._draw_buff_screen_effect()

        # 绘制枪口闪光
        self._draw_muzzle_flash()

        # 动态光照层（在世界/实体之后，HUD之前）
        if hasattr(self.game, 'lighting') and self.game.state == GameState.PLAYING:
            self.game.lighting.render(
                self.screen, camera.x, camera.y, self.game.scale,
                player=player,
                enemies=self.game.enemies,
                projectiles=getattr(self.game, 'projectiles', []),
            )

        # 绘制触控控件
        if self.game.config.control_mode == ControlMode.TOUCH or self.game.is_android:
            self.game.joystick.draw(self.screen, scale)

            if hasattr(self.game, 'aim_button') and self.game.aim_button:
                self.game.aim_button.draw(self.screen, self.game.font_small, scale)

            for name, btn in self.game.touch_buttons.items():
                if name == "shoot" and player.riot_gear.equipped:
                    original_label = btn.label
                    original_color = btn.color
                    btn.label = "肘击"
                    btn.color = PURPLE
                    btn.draw(self.screen, self.game.font_small, scale)
                    btn.label = original_label
                    btn.color = original_color
                else:
                    btn.draw(self.screen, self.game.font_small, scale)

            if hasattr(self.game, 'skill_selector') and self.game.skill_selector:
                skill = player.skill_tree.get_skill(self.game.selected_skill)
                skill_name = skill.name if skill else "空"
                skill_color = skill.icon_color if skill else BLUE
                self.game.skill_selector.draw(self.screen, self.game.font_small, skill_name, skill_color, scale)

            if hasattr(self.game, 'skill_caster') and self.game.skill_caster:
                skill = player.skill_tree.get_skill(self.game.selected_skill)
                skill_name = skill.name if skill else "空"
                skill_color = skill.icon_color if skill else ORANGE
                self.game.skill_caster.draw(self.screen, self.game.font_small, 
                    self.game.selected_skill, skill_name, skill_color, scale)

            # 投掷物释放按钮（触控端）
            if hasattr(self.game, 'throwable_caster') and self.game.throwable_caster and self.game.throwable_caster.visible:
                t_type = self.game.selected_throwable
                t_name = self.game.throwable_names.get(t_type, "投")
                t_color = self.game.throwable_colors.get(t_type, ORANGE)
                t_count = getattr(self.game.player, 'throwables', {}).get(t_type, 0)
                t_abbr = {"incendiary": "燃", "smoke": "烟", "cluster": "束", "emp": "E"}.get(t_type, "投")
                self.game.throwable_caster.draw(self.screen, self.game.font_small, 
                    None, t_abbr, t_color, scale)
                # 数量角标
                if t_count > 0:
                    bx, by, br = self.game.throwable_caster.get_scaled_pos(scale)
                    badge_text = self.game.font_small.render(str(t_count), True, WHITE)
                    badge_bg = pygame.Surface((badge_text.get_width() + 8, badge_text.get_height() + 4), pygame.SRCALPHA)
                    badge_bg.fill((0, 0, 0, 180))
                    self.screen.blit(badge_bg, (int(bx + br - badge_text.get_width() - 4), int(by - br + 2)))
                    self.screen.blit(badge_text, (int(bx + br - badge_text.get_width()), int(by - br + 4)))

            # 投掷物切换按钮（触控端）
            if hasattr(self.game, 'throwable_switch_btn') and self.game.throwable_switch_btn:
                self.game.throwable_switch_btn.draw(self.screen, self.game.font_small, scale)

            if self.game.skill_wheel_active:
                self.game.skill_wheel.draw(self.screen, self.game.font, self.game.font_large, scale)
            if self.game.weapon_wheel_active:
                self.game.weapon_wheel.draw(self.screen, self.game.font, self.game.font_large, scale)

        # ==========键鼠长按G瞄准预览（复用SkillCaster原生绘制逻辑） ==========
        if self.game.config.control_mode == ControlMode.KEYBOARD and self.game.skill_caster.is_aiming:
            self.game.skill_caster._draw_aim_preview(self.screen, self.game.selected_skill, self.game.scale)

        # ========== 投掷物瞄准预览（键鼠长按Q/触控长按投掷均显示） ==========
        if hasattr(self.game, 'throwable_caster') and self.game.throwable_caster and self.game.throwable_caster.is_aiming:
            tc = self.game.throwable_caster
            scale = self.game.scale
            px = int((tc.player_x - tc.camera_x) * scale)
            py = int((tc.player_y - tc.camera_y) * scale)
            dist = tc.max_skill_distance * tc.distance_ratio
            tx = px + math.cos(tc.angle) * dist * scale
            ty = py + math.sin(tc.angle) * dist * scale

            # 抛物线轨迹
            points = []
            for t in range(0, 21):
                ratio = t / 20.0
                arc_x = px + (tx - px) * ratio
                arc_y = py + (ty - py) * ratio - math.sin(ratio * math.pi) * 50 * scale
                points.append((arc_x, arc_y))
            if len(points) >= 2:
                pygame.draw.lines(self.screen, (255, 140, 0), False, points, max(1, int(2 * scale)))

            # 爆炸范围圈（投掷物AOE半径约80）
            aoe_r = int(80 * scale)
            range_surf = pygame.Surface((aoe_r * 2, aoe_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (255, 100, 0, 50), (aoe_r, aoe_r), aoe_r)
            self.screen.blit(range_surf, (int(tx - aoe_r), int(ty - aoe_r)))
            pygame.draw.circle(self.screen, (255, 140, 0), (int(tx), int(ty)), aoe_r, max(1, int(2 * scale)))
            # 十字标记
            cs = int(12 * scale)
            pygame.draw.line(self.screen, (255, 200, 0), (int(tx) - cs, int(ty)), (int(tx) + cs, int(ty)), 2)
            pygame.draw.line(self.screen, (255, 200, 0), (int(tx), int(ty) - cs), (int(tx), int(ty) + cs), 2)
            # 距离指示
            dist_text = f"{int(dist)}m"
            dt_surf = pygame.font.SysFont("arial", max(10, int(12 * scale))).render(dist_text, True, (255, 180, 0))
            self.screen.blit(dt_surf, (int(tx) + 10, int(ty) - 20))
            
        # =========【v2.0.11 成就/图鉴解锁 toast：徽章式 + 滑入 + 粒子光效】========
        scale = self.game.scale
        try:
            import time as _time
            _now = _time.time()
        except Exception:
            _now = 0
        toast_y = int(20 * scale)
        for toast in list(self.game.ach_toast_queue):
            born = toast.get("born", _now)
            age = _now - born
            if age < 0:
                age = 0
            remain = toast.get("timer", 4.0) - age
            if remain <= 0:
                self.game.ach_toast_queue.remove(toast)
                continue
            # 滑入动画（前 0.3s 从右滑入）+ 尾部淡出（后 25% 时间）
            slide = min(1.0, age / 0.3)
            fade = min(1.0, remain / max(0.001, toast.get("timer", 4.0) * 0.25))
            alpha = int(235 * min(slide * 1.2, 1.0) * fade)
            kind = toast.get("kind", "ach")
            name = toast.get("name", toast.get("desc", "成就"))
            sub = "成就达成！" if kind != "codex" else "图鉴收录"
            # 徽章尺寸
            bw = int(300 * scale)
            bh = int(64 * scale)
            bx = int(self.game.scaled_width - bw - 16 * scale) + int((1 - slide) * 60 * scale)
            by = toast_y
            # 阴影
            pygame.draw.rect(self.screen, (0, 0, 0, 110), (bx + 3, by + 4, bw, bh), border_radius=int(12 * scale))
            # 主体：深色渐变底（两段叠加模拟渐变）
            pygame.draw.rect(self.screen, (*CHARCOAL, alpha), (bx, by, bw, bh), border_radius=int(12 * scale))
            pygame.draw.rect(self.screen, (40, 32, 60, alpha), (bx + 2, by + 2, bw - 4, bh - 8), border_radius=int(10 * scale))
            # 金色边框 + 顶部亮线
            pygame.draw.rect(self.screen, (*GOLD, alpha), (bx, by, bw, bh), max(1, int(scale)), border_radius=int(12 * scale))
            pygame.draw.line(self.screen, (255, 230, 150, alpha), (bx + int(14 * scale), by + 2), (bx + bw - int(14 * scale), by + 2), max(1, int(scale)))
            # 左侧图标区：金色描边圆 + 星形
            ic = int(26 * scale)
            cx = bx + int(34 * scale)
            cy = by + bh // 2
            pygame.draw.circle(self.screen, (*GOLD, alpha), (cx, cy), ic, max(1, int(scale)))
            pygame.draw.circle(self.screen, (40, 30, 20, alpha), (cx, cy), ic - max(2, int(scale)))
            star_r = ic - max(5, int(scale))
            for k in range(5):
                ang1 = -1.5708 + k * 1.2566
                ang2 = ang1 + 0.6283
                p1 = (cx + int(star_r * 0.92 * math.cos(ang1)), cy + int(star_r * 0.92 * math.sin(ang1)))
                p2 = (cx + int(star_r * 0.42 * math.cos(ang2)), cy + int(star_r * 0.42 * math.sin(ang2)))
                p3 = (cx + int(star_r * 0.92 * math.cos(ang1 + 1.2566)), cy + int(star_r * 0.92 * math.sin(ang1 + 1.2566)))
                pygame.draw.polygon(self.screen, (255, 215, 90, alpha), [p1, p2, p3])
            # 文字：标题（成就名）+ 副标题
            title_s = max(14, int(17 * scale))
            sub_s = max(10, int(12 * scale))
            t_surf = self.game.font.render(name, True, (255, 230, 160))
            t_surf.set_alpha(alpha)
            self.screen.blit(t_surf, (bx + int(72 * scale), by + int(8 * scale)))
            s_surf = self.game.font.render(sub, True, (200, 200, 210))
            s_surf.set_alpha(alpha)
            self.screen.blit(s_surf, (bx + int(72 * scale), by + int(34 * scale)))
            # 粒子光效：3 颗金色光点沿边框浮动
            for k in range(3):
                ph = (_now * 2.2 + k * 2.1) % 1.0
                px = bx + int(ph * bw)
                py = by + bh // 2 + int((0.5 - abs(ph - 0.5)) * bh * 1.6)
                pygame.draw.circle(self.screen, (255, 220, 120, alpha), (px, py), max(1, int(2.2 * scale)))
            toast_y += int(bh + 10 * scale)


        # Mod 钩子：自定义HUD渲染
        try:
            import mod_loader
            mod_loader.trigger_hook("on_render_hud", self.screen, self.game)
        except Exception:
            pass

    def _draw_hud(self):
        scale = self.game.scale
        sw = self.game.scaled_width
        player = self.game.player

        # === Buff状态栏（右上角）===
        self._draw_buff_bar()

        # === 屏幕上方中央显示时间（紧迫感） ===
        if self.game.config.game_mode == GameMode.STORY:
            # 故事模式：显示当前地图和地图倒计时
            map_config = self.game.map_config
            time_limit = map_config.get("time_limit", 1200)
            remain = max(0, time_limit - self.game.map_time_elapsed)
            m = int(remain // 60)
            s = int(remain % 60)
            time_text = f"{m:02d}:{s:02d}"
            time_color = RED if remain < 60 else WHITE

            # 地图名称（上移避免与时间重叠）
            map_name_text = self.game.font_small.render(
                f"{map_config['chapter']} - {map_config['name']}", True, GOLD)
            map_name_rect = map_name_text.get_rect(center=(sw // 2, int(14 * scale)))
            self.screen.blit(map_name_text, map_name_rect)

            time_surf = self.game.font_large.render(time_text, True, time_color)
            time_rect = time_surf.get_rect(center=(sw // 2, int(40 * scale)))

            # 特殊事件激活提示
            if self.game.special_event_active:
                event_text = self.game.font_small.render("[!] 特殊事件进行中", True, RED)
                event_rect = event_text.get_rect(center=(sw // 2, int(65 * scale)))
                if int(pygame.time.get_ticks() / 300) % 2 == 0:
                    self.screen.blit(event_text, event_rect)
        else:
            time_text, is_countdown = self.game.horde_manager.get_time_display()
            glitch_text_surf = None
            glitch_rect = None

            if self.game.config.game_mode == GameMode.ENDLESS and self.game.horde_manager.endless_glitch_shown:
                # 无尽模式错误效果
                if int(pygame.time.get_ticks() / 500) % 2 == 0:
                    time_color = RED
                else:
                    time_color = DARK_RED
                time_surf = self.game.font_large.render(f"TIME: {time_text}", True, time_color)
                time_rect = time_surf.get_rect(center=(sw // 2, int(30 * scale)))
                glitch_text_surf = self.game.font_small.render("SYSTEM ERROR: TIME_OVERFLOW", True, RED)
                glitch_rect = glitch_text_surf.get_rect(center=(sw // 2, int(52 * scale)))
            else:
                if is_countdown:
                    parts = time_text.split(":")
                    remain_secs = int(parts[0]) * 60 + int(parts[1])
                    time_color = RED if remain_secs < 30 else WHITE
                else:
                    time_color = GOLD
                time_surf = self.game.font_large.render(time_text, True, time_color)
                time_rect = time_surf.get_rect(center=(sw // 2, int(30 * scale)))

        # 时间背景
        time_bg = pygame.Rect(time_rect.x - 10, time_rect.y - 5, time_rect.width + 20, time_rect.height + 10)
        pygame.draw.rect(self.screen, (*CHARCOAL[:3], 200), time_bg, border_radius=5)
        self.screen.blit(time_surf, time_rect)

        # 绘制glitch报错文本（如果存在）
        if self.game.config.game_mode != GameMode.STORY:
            try:
                if glitch_text_surf and glitch_rect:
                    if int(pygame.time.get_ticks() / 800) % 2 == 0:
                        self.screen.blit(glitch_text_surf, glitch_rect)
            except (NameError, UnboundLocalError):
                pass

        # === 尸潮警告【全部向下偏移，避开glitch文字】 ===
        horde_base_y = int(85 * scale)
        if self.game.horde_manager.is_horde_active():
            horde_text = self.game.font.render("!!! 尸潮来袭 !!!", True, RED)
            horde_rect = horde_text.get_rect(center=(sw // 2, horde_base_y))
            # 闪烁效果 + 背景
            if int(pygame.time.get_ticks() / 200) % 2 == 0:
                bg_pad = 10
                horde_bg = pygame.Rect(horde_rect.x - bg_pad, horde_rect.y - bg_pad//2,
                                        horde_rect.width + bg_pad*2, horde_rect.height + bg_pad)
                pygame.draw.rect(self.screen, (*BLACK[:3], 180), horde_bg, border_radius=5)
                pygame.draw.rect(self.screen, RED, horde_bg, 2, border_radius=5)
                self.screen.blit(horde_text, horde_rect)
        else:
            # 显示距离下次尸潮的进度
            horde_progress = self.game.horde_manager.get_horde_progress()
            if horde_progress > 0:
                bar_w = int(200 * scale)
                bar_h = max(3, int(8 * scale))
                bar_x = sw // 2 - bar_w // 2
                bar_y = horde_base_y
                pygame.draw.rect(self.screen, DARK_GRAY, (bar_x, bar_y, bar_w, bar_h), border_radius=2)
                pygame.draw.rect(self.screen, (*RED[:3], 180), (bar_x, bar_y, int(bar_w * horde_progress), bar_h), border_radius=2)
                pygame.draw.rect(self.screen, GRAY, (bar_x, bar_y, bar_w, bar_h), max(1, int(scale)), border_radius=2)
                # 显示倒计时文字
                time_to_horde = int(self.game.horde_manager.timer)
                if time_to_horde > 0:
                    countdown_text = self.game.font_small.render(f"尸潮: {time_to_horde}s", True, (*RED[:3], 150))
                    self.screen.blit(countdown_text, (bar_x + bar_w + 5, bar_y - 2))

        # ========== 底部中央状态栏（大尺寸、明显） ==========
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        bar_w = int(460 * scale)
        bar_x = (screen_w - bar_w) // 2
        bar_bottom = screen_h - int(20 * scale)

        # 经验条（最底部）
        exp_ratio = player.exp / player.exp_to_level
        exp_h = max(4, int(12 * scale))
        exp_y = bar_bottom - exp_h
        pygame.draw.rect(self.screen, (15, 25, 35), (bar_x, exp_y, bar_w, exp_h), border_radius=3)
        pygame.draw.rect(self.screen, (60, 200, 230), (bar_x, exp_y, int(bar_w * exp_ratio), exp_h), border_radius=3)
        pygame.draw.rect(self.screen, (*WHITE[:3], 160), (bar_x, exp_y, bar_w, exp_h), max(1, int(scale * 0.7)), border_radius=3)
        exp_label = self.game.font_small.render(f"EXP {int(player.exp)}/{int(player.exp_to_level)}", True, (120, 220, 240))
        # 经验条文字放在经验条右侧，避免与左侧标签重叠
        self.screen.blit(exp_label, (bar_x + bar_w + int(10*scale), exp_y - 1))

        # 体力条（中间）
        stamina_ratio = player.stamina / player.max_stamina if player.max_stamina > 0 else 0
        stamina_h = max(4, int(14 * scale))
        stamina_y = exp_y - stamina_h - int(6 * scale)
        stamina_color = (70, 170, 255)
        if player.stamina_exhausted:
            stamina_color = (220, 70, 70)
        elif player.sprinting:
            stamina_color = (255, 200, 70)
        pygame.draw.rect(self.screen, (20, 25, 40), (bar_x, stamina_y, bar_w, stamina_h), border_radius=4)
        pygame.draw.rect(self.screen, stamina_color, (bar_x, stamina_y, int(bar_w * stamina_ratio), stamina_h), border_radius=4)
        pygame.draw.rect(self.screen, (*WHITE[:3], 180), (bar_x, stamina_y, bar_w, stamina_h), max(1, int(scale * 0.8)), border_radius=4)
        sta_label = self.game.font_small.render(
            f"体力 {int(player.stamina)}/{int(player.max_stamina)}", True, (*stamina_color[:3], 220))
        # 体力标签+数字放在体力条右侧
        self.screen.blit(sta_label, (bar_x + bar_w + int(10*scale), stamina_y + 1))

        # HP条（顶部，最粗最明显）
        hp_ratio = player.hp / player.max_hp
        hp_h = max(6, int(24 * scale))
        hp_y = stamina_y - hp_h - int(6 * scale)
        pygame.draw.rect(self.screen, (35, 8, 8), (bar_x, hp_y, bar_w, hp_h), border_radius=6)
        if hp_ratio > 0.5:
            hp_color = (50, 210, 90)
        elif hp_ratio > 0.25:
            hp_color = (235, 180, 40)
        else:
            hp_color = (225, 50, 50)
        pygame.draw.rect(self.screen, hp_color, (bar_x, hp_y, int(bar_w * hp_ratio), hp_h), border_radius=6)
        # HP条高光
        if hp_ratio > 0.05:
            highlight_h = max(1, int(hp_h * 0.35))
            pygame.draw.rect(self.screen, (*WHITE[:3], 60), (bar_x + 2, hp_y + 2, int(bar_w * hp_ratio) - 4, highlight_h), border_radius=3)
        pygame.draw.rect(self.screen, (*WHITE[:3], 200), (bar_x, hp_y, bar_w, hp_h), max(1, int(scale)), border_radius=6)
        hp_text = self.game.font.render(f"{int(player.hp)}/{int(player.max_hp)}", True, WHITE)
        # HP文字放在HP条右侧
        self.screen.blit(hp_text, (bar_x + bar_w + int(10*scale), hp_y + 3))
        hp_label = self.game.font_small.render("生命", True, (*hp_color[:3], 220))
        # 生命标签放在HP条右侧
        self.screen.blit(hp_label, (bar_x + bar_w + int(10*scale), hp_y + 4))

        # 等级和分数（状态栏左侧，不与右侧文字冲突）
        level_text = self.game.font.render(f"Lv.{player.level}", True, GOLD)
        self.screen.blit(level_text, (bar_x - level_text.get_width() - int(15*scale), hp_y + 3))
        score_text = self.game.font_small.render(f"分:{player.score}", True, (*GOLD[:3], 180))
        self.screen.blit(score_text, (bar_x - score_text.get_width() - int(15*scale), hp_y + int(26*scale)))

        # ========== 左上角信息区（武器/技能/投掷物） ==========
        weapon = player.get_current_weapon()
        info_y = int(12 * scale)
        weapon_text = self.game.font_small.render(f"{weapon.name} Lv.{weapon.level}", True, WHITE)
        self.screen.blit(weapon_text, (int(12*scale), info_y))
        info_y += int(20 * scale)
        if hasattr(weapon, 'get_ammo_text'):
            ammo_text = self.game.font_small.render(weapon.get_ammo_text(), True, (180, 180, 180))
            self.screen.blit(ammo_text, (int(12*scale), info_y))
            info_y += int(18 * scale)
        if len(player.weapons) > 1:
            switch_text = self.game.font_small.render(f"R切换({len(player.weapons)})", True, (120, 120, 120))
            self.screen.blit(switch_text, (int(12*scale), info_y))
            info_y += int(18 * scale)
        skill = player.skill_tree.get_skill(self.game.selected_skill)
        if skill:
            skill_text = self.game.font_small.render(f"技能:{skill.name}(G)", True, GOLD)
            self.screen.blit(skill_text, (int(12*scale), info_y))
            info_y += int(18 * scale)
        t_type = self.game.selected_throwable
        t_name = self.game.throwable_names.get(t_type, "?")
        t_color = self.game.throwable_colors.get(t_type, ORANGE)
        t_count = getattr(player, 'throwables', {}).get(t_type, 0)
        total_throwables = sum(getattr(player, 'throwables', {}).values())
        if total_throwables > 0:
            throw_text = self.game.font_small.render(f"投掷:{t_name}x{t_count}(Q/E)", True, t_color)
        else:
            throw_text = self.game.font_small.render("投掷:无", True, (100, 100, 100))
        self.screen.blit(throw_text, (int(12*scale), info_y))

        # ========== 键控模式：下一个技能/武器提示 ==========
        if self.game.config.control_mode == ControlMode.KEYBOARD:
            hint_y = screen_h - int(120 * scale)
            unlocked_skills = self.game._get_unlocked_skills()
            if len(unlocked_skills) > 0:
                curr_idx = unlocked_skills.index(self.game.selected_skill) if self.game.selected_skill in unlocked_skills else -1
                next_skill_type = unlocked_skills[(curr_idx + 1) % len(unlocked_skills)]
                next_skill = player.skill_tree.get_skill(next_skill_type)
                next_skill_name = next_skill.name if next_skill else "空"
                ns_text = self.game.font_small.render(f"Tab切换: {next_skill_name}", True, AMBER)
                self.screen.blit(ns_text, (int(12*scale), hint_y))
                hint_y += int(18 * scale)
            if len(player.weapons) > 1:
                next_weapon = player.weapons[(player.current_weapon_idx + 1) % len(player.weapons)]
                nw_text = self.game.font_small.render(f"R切换: {next_weapon.name}", True, PURPLE)
                self.screen.blit(nw_text, (int(12*scale), hint_y))

        # ========== 状态行（防爆套装/冷却等，左上角信息区下方） ==========
        status_lines = []
        riot = player.riot_gear
        if self.game.riot_anim_state == "equipping":
            progress = 1 - (self.game.riot_anim_timer / self.game.riot_anim_duration)
            status_lines.append(f"防爆装备中... {int(progress*100)}%")
        elif self.game.riot_anim_state == "unequipping":
            progress = 1 - (self.game.riot_anim_timer / self.game.riot_anim_duration)
            status_lines.append(f"防爆卸下中... {int(progress*100)}%")
        elif riot.equipped:
            status_lines.append("[OK] 防爆套装已装备")
            if riot.shield_broken:
                status_lines.append("[!] 观察窗已破碎")
            else:
                vw_ratio = riot.viewing_window_hp / riot.max_viewing_window_hp
                status_lines.append(f"观察窗: {int(vw_ratio*100)}%")
            if riot.has_debuff:
                status_lines.append("[!]装备超时，移动减速")
            status_lines.append(f"盾牌体力: {int(riot.stamina)}")
        elif riot.riot_gear_cd_timer > 0:
            status_lines.append(f"防爆套装冷却: {riot.riot_gear_cd_timer:.1f}s")

        if self.game.config.control_mode == ControlMode.KEYBOARD:
            if hasattr(weapon, "shoot_cd_timer") and weapon.shoot_cd_timer > 0:
                status_lines.append(f"射击冷却: {weapon.shoot_cd_timer:.2f}s")
            if hasattr(weapon, "reload_timer") and weapon.reload_timer > 0:
                status_lines.append(f"换弹: {weapon.reload_timer:.1f}s")
            for sk_type, cd_left in player.active_skills.items():
                sk_obj = player.skill_tree.get_skill(sk_type)
                sk_name = sk_obj.name if sk_obj else str(sk_type)
                status_lines.append(f"[{sk_name}] CD: {cd_left:.1f}s")

        stat_start_y = info_y + int(24 * scale)
        stat_line_h = int(20 * scale)
        draw_y = stat_start_y
        for line_txt in status_lines:
            surf = self.game.font_small.render(line_txt, True, WHITE)
            self.screen.blit(surf, (int(12*scale), draw_y))
            draw_y += stat_line_h

    def _draw_skill_warning(self, enemy, cam_x, cam_y, scale):
        """技能前摇警示：红色闪烁圈 + 头顶危险标记，便于玩家躲避"""
        import time as _t
        px = int((enemy.x - cam_x) * scale)
        py = int((enemy.y - cam_y) * scale)
        pulse = (math.sin(_t.time() * 8) + 1) / 2  # 0-1 闪烁
        r = int((enemy.size + 14) * scale)
        ring_w = max(2, int(3 * scale))
        ring = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 40, 40, int(220 - 120 * pulse)), (r + 4, r + 4), r, ring_w)
        self.screen.blit(ring, (px - r - 4, py - r - 4))
        # 顶部警告文字
        warn = self.game.font_large.render("!", True, (255, 60, 60))
        self.screen.blit(warn, (px - warn.get_width() // 2, py - r - int(30 * scale)))
        label = self.game.font_small.render("危险!", True, (255, 80, 80))
        self.screen.blit(label, (px - label.get_width() // 2, py - r - int(50 * scale)))

    def _draw_buff_bar(self):
        """绘制Buff状态栏 - 右上角图标+剩余时间，悬停/触摸显示详情"""
        player = self.game.player
        if not player:
            return
        buffs = player.buff_manager.get_active_buffs()
        if not buffs:
            return

        scale = self.game.scale
        sw = self.game.scaled_width
        icon_size = int(36 * scale)
        gap = int(4 * scale)
        padding = int(8 * scale)
        start_x = sw - padding
        start_y = padding

        # 获取鼠标/触摸位置
        mouse_x, mouse_y = pygame.mouse.get_pos()
        # 触控模式下用最后触摸位置
        if hasattr(self.game, 'last_touch_pos') and self.game.last_touch_pos:
            mouse_x, mouse_y = self.game.last_touch_pos

        hovered_buff = None
        hovered_rect = None

        for i, buff in enumerate(buffs):
            # 从右向左排列
            x = start_x - (i + 1) * icon_size - i * gap
            y = start_y
            rect = pygame.Rect(x, y, icon_size, icon_size)

            # 背景
            bg_color = (*buff.color[:3], 180)
            bg_surf = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
            pygame.draw.rect(bg_surf, bg_color, (0, 0, icon_size, icon_size), border_radius=6)
            # 边框：debuff红色，buff绿色
            border_color = RED if buff.is_debuff else GREEN
            pygame.draw.rect(bg_surf, (*border_color[:3], 220), (0, 0, icon_size, icon_size), 2, border_radius=6)
            self.screen.blit(bg_surf, (x, y))

            # 图标文字：去掉[]括号，取前3个有效字符
            raw_icon = buff.icon.strip("[](){}") if buff.icon else buff.name
            icon_text = raw_icon[:3] if raw_icon else "?"
            icon_surf = self.game.font_small.render(icon_text, True, WHITE)
            icon_rect = icon_surf.get_rect(center=(x + icon_size // 2, y + icon_size // 2 - int(3 * scale)))
            self.screen.blit(icon_surf, icon_rect)

            # 剩余时间条（底部）
            if buff.duration is not None and buff.duration > 0:
                ratio = max(0, buff.remaining / buff.duration)
                bar_w = icon_size - 4
                bar_h = max(2, int(4 * scale))
                bar_x = x + 2
                bar_y = y + icon_size - bar_h - 2
                pygame.draw.rect(self.screen, (*GRAY[:3], 150), (bar_x, bar_y, bar_w, bar_h))
                bar_color = RED if buff.is_debuff else GREEN
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, int(bar_w * ratio), bar_h))

            # 层数
            if buff.stacks > 1:
                stack_text = self.game.font_small.render(str(buff.stacks), True, GOLD)
                self.screen.blit(stack_text, (x + icon_size - stack_text.get_width() - 2, y + 1))

            # 悬停检测
            if rect.collidepoint(mouse_x, mouse_y):
                hovered_buff = buff
                hovered_rect = rect

        # 绘制悬停详情
        if hovered_buff and hovered_rect:
            self._draw_buff_tooltip(hovered_buff, hovered_rect)

    def _draw_buff_tooltip(self, buff, icon_rect):
        """绘制Buff详情提示框"""
        scale = self.game.scale
        sw = self.game.scaled_width

        lines = []
        lines.append((buff.name, GOLD if not buff.is_debuff else RED))
        lines.append((buff.description, LIGHT_GRAY))
        if buff.duration is not None:
            time_str = f"剩余: {buff.remaining:.1f}s"
            lines.append((time_str, GRAY))
        if buff.stacks > 1:
            lines.append((f"层数: {buff.stacks}", GOLD))

        # 计算提示框大小
        max_w = 0
        total_h = 0
        rendered = []
        for text, color in lines:
            surf = self.game.font_small.render(text, True, color)
            rendered.append(surf)
            max_w = max(max_w, surf.get_width())
            total_h += surf.get_height() + 2

        pad = int(8 * scale)
        tip_w = max_w + pad * 2
        tip_h = total_h + pad * 2

        # 位置：图标下方，避免超出屏幕
        tip_x = icon_rect.centerx - tip_w // 2
        tip_y = icon_rect.bottom + int(4 * scale)
        if tip_x + tip_w > sw:
            tip_x = sw - tip_w - int(4 * scale)
        if tip_x < 0:
            tip_x = int(4 * scale)

        # 背景
        tip_surf = pygame.Surface((tip_w, tip_h), pygame.SRCALPHA)
        pygame.draw.rect(tip_surf, (*CHARCOAL[:3], 230), (0, 0, tip_w, tip_h), border_radius=6)
        pygame.draw.rect(tip_surf, (*GRAY[:3], 150), (0, 0, tip_w, tip_h), 1, border_radius=6)
        self.screen.blit(tip_surf, (tip_x, tip_y))

        # 文字
        cy = tip_y + pad
        for surf in rendered:
            self.screen.blit(surf, (tip_x + pad, cy))
            cy += surf.get_height() + 2

    def _draw_trauma_effect(self):
        """绘制创伤效果 - 高性能版：预渲染缓存+血渍池+简化流淌"""
        player = self.game.player
        if not player:
            return

        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        trauma = player.trauma

        # 流血debuff额外增强创伤感
        bleed_mult = 1.0
        if player.buff_manager.has_buff(BuffType.BLEED):
            bleed_mult = 1.4
        if player.buff_manager.has_buff(BuffType.BURN):
            bleed_mult = max(bleed_mult, 1.2)

        effective_trauma = min(1.0, trauma * bleed_mult)

        if effective_trauma <= 0.01 and not self.game.screen_blood:
            return

        # === 1. 缓存边缘渐变（只在trauma变化超过阈值时重建）===
        cache_key = (int(effective_trauma * 10), sw, sh)
        if not hasattr(self, '_trauma_cache_key') or self._trauma_cache_key != cache_key:
            self._trauma_cache_key = cache_key
            edge_width = max(1, int(100 * scale * effective_trauma))
            alpha = int(200 * effective_trauma)
            # 一次性创建四边渐变
            trauma_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
            # 用渐变矩形代替逐行绘制
            for i in range(edge_width):
                a = int(alpha * (1 - i / edge_width) ** 0.6)
                c = (180, 10, 10, a)
                pygame.draw.rect(trauma_surf, c, (0, i, sw, 1))
                pygame.draw.rect(trauma_surf, c, (0, sh - 1 - i, sw, 1))
                pygame.draw.rect(trauma_surf, c, (i, 0, 1, sh))
                pygame.draw.rect(trauma_surf, c, (sw - 1 - i, 0, 1, sh))
            self._trauma_edge_surf = trauma_surf

        if effective_trauma > 0.01:
            self.game.screen.blit(self._trauma_edge_surf, (0, 0))

        # === 2. 预渲染血渍模板缓存（按半径分级，避免每帧创建Surface）===
        if not hasattr(self, '_blood_template_cache'):
            self._blood_template_cache = {}
        # 血渍最大数量根据画质调整
        q = self.game.config.graphics_quality
        MAX_BLOOD = 12 if q == "performance" else 25 if q == "balanced" else 40
        drip_enabled = q != "performance"

        # 受伤时添加新血渍
        if not hasattr(self, '_last_trauma'):
            self._last_trauma = 0
        trauma_delta = trauma - self._last_trauma
        self._last_trauma = trauma
        if trauma_delta > 0.05:
            num_new = min(int(trauma_delta * 15) + 1, MAX_BLOOD - len(self.game.screen_blood))
            for _ in range(max(0, num_new)):
                sx = random.randint(0, sw)
                sy = random.randint(0, int(sh * 0.55))
                sr = random.randint(5, max(7, int(25 * scale * effective_trauma)))
                drip = random.uniform(8, 30) * scale
                self.game.screen_blood.append([sx, sy, sr, 180, drip, 0])

        # 更新和绘制血渍（使用预渲染模板）
        dt = 1 / 60
        alive_blood = []
        for bx, by, br, ba, drip, boff in self.game.screen_blood:
            boff += drip * dt
            new_y = by + boff
            ba -= 12 * dt
            if ba <= 0 or new_y > sh + br:
                continue
            # 使用缓存的血渍模板
            template_key = (br, int(ba))
            if template_key not in self._blood_template_cache:
                # 限制缓存大小
                if len(self._blood_template_cache) > 200:
                    self._blood_template_cache.clear()
                blood_surf = pygame.Surface((br * 2, br * 2), pygame.SRCALPHA)
                pygame.draw.circle(blood_surf, (150, 8, 8, int(ba)), (br, br), br)
                self._blood_template_cache[template_key] = blood_surf
            self.game.screen.blit(self._blood_template_cache[template_key], (bx - br, int(new_y) - br))
            # 流淌血柱 - 性能模式关闭
            if drip_enabled and boff > 5:
                drip_h = int(min(boff * 0.6, 60 * scale))
                drip_w = max(2, int(br * 0.25))
                drip_key = (drip_w, drip_h, int(ba))
                if drip_key not in self._blood_template_cache:
                    if len(self._blood_template_cache) > 200:
                        self._blood_template_cache.clear()
                    drip_surf = pygame.Surface((drip_w * 2, drip_h), pygame.SRCALPHA)
                    for dy in range(0, drip_h, 2):  # 步长2，减少绘制次数
                        a = int(ba * (1 - dy / drip_h) * 0.7)
                        w = int(drip_w * (1 - dy / drip_h * 0.4))
                        pygame.draw.line(drip_surf, (150, 8, 8, a),
                                         (drip_w - w, dy), (drip_w + w, dy))
                    self._blood_template_cache[drip_key] = drip_surf
                self.game.screen.blit(self._blood_template_cache[drip_key], (bx - drip_w, int(new_y)))
            alive_blood.append([bx, by, br, ba, drip, boff])
        self.game.screen_blood = alive_blood

        # === 3. 心跳效果（低血量）===
        hp_ratio = player.hp / player.max_hp if player.max_hp > 0 else 0
        if hp_ratio < 0.3:
            heartbeat = abs(math.sin(pygame.time.get_ticks() / 180)) * effective_trauma * 0.4
            if heartbeat > 0.05:
                hb_key = int(heartbeat * 20)
                if not hasattr(self, '_hb_cache') or self._hb_cache[0] != (hb_key, sw, sh):
                    hb_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
                    hb_surf.fill((180, 8, 8, int(40 * heartbeat)))
                    self._hb_cache = ((hb_key, sw, sh), hb_surf)
                self.game.screen.blit(self._hb_cache[1], (0, 0))
                if heartbeat > 0.7:
                    self.game.camera.shake_intensity = max(self.game.camera.shake_intensity, 2)

        # === 4. 屏幕暗角 ===
        if effective_trauma > 0.5:
            vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for r in range(int(min(sw, sh) // 2), int(min(sw, sh) // 2 * 0.3), -10):
                a = int((effective_trauma - 0.5) * 2 * 30 * (1 - r / (min(sw, sh) // 2)))
                pygame.draw.rect(vignette, (0, 0, 0, a), (0, 0, sw, sh), border_radius=r)
            self.game.screen.blit(vignette, (0, 0))

    def _draw_lifesteal_effect(self):
        """吸血屏幕效果：暗红色边缘向内收缩脉动"""
        if not hasattr(self.game, 'lifesteal_flash') or self.game.lifesteal_flash <= 0:
            return
        if not self.game.config.render_buff_effects:
            return
        intensity = self.game.lifesteal_flash
        # 呼吸脉动
        pulse = 0.7 + 0.3 * math.sin(pygame.time.get_ticks() * 0.012)
        intensity *= pulse
        sw, sh = self.screen.get_size()
        scale = self.game.scale
        edge_w = int(120 * scale * intensity)
        if edge_w < 2:
            return
        cache_key = (int(intensity * 20), sw, sh)
        if not hasattr(self, '_lifesteal_cache'):
            self._lifesteal_cache = {}
        if cache_key not in self._lifesteal_cache:
            if len(self._lifesteal_cache) > 30:
                self._lifesteal_cache.clear()
            surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
            # 暗红色径向边缘
            for i in range(edge_w, 0, -2):
                a = int(180 * intensity * (1 - i / edge_w) ** 1.5)
                if a <= 0:
                    continue
                pygame.draw.rect(surf, (160, 15, 15, a),
                                 (i, i, sw - i * 2, sh - i * 2), 2)
            self._lifesteal_cache[cache_key] = surf
        self.screen.blit(self._lifesteal_cache[cache_key], (0, 0))

    def _draw_buff_screen_effect(self):
        """绘制Buff屏幕效果：回血发绿、狂暴动态模糊、燃烧热浪等"""
        player = self.game.player
        if not player or not hasattr(player, 'buff_manager'):
            return
        if not self.game.config.render_buff_effects:
            return

        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        bm = player.buff_manager

        # (颜色, 基础强度, 是否呼吸, 特效类型)
        buff_effects = {
            BuffType.REGEN: (LIME, 0.4, True, "glow"),
            BuffType.BERSERK: (CRIMSON, 0.6, True, "berserk"),
            BuffType.BLOOD_FRENZY: ((180, 30, 30), 0.5, True, "berserk"),
            BuffType.BURN: (FIRE_ORANGE, 0.45, False, "heat"),
            BuffType.FREEZE: ((100, 180, 255), 0.5, False, "frost"),
            BuffType.POISON: (POISON_GREEN, 0.4, True, "glow"),
            BuffType.SPEED_BOOST: (CYAN, 0.3, False, "motion"),
            BuffType.HASTE: (CYAN, 0.35, False, "motion"),
            BuffType.SHIELD: ((100, 150, 255), 0.35, True, "glow"),
            BuffType.IRON_SKIN: ((150, 150, 160), 0.3, False, "glow"),
            BuffType.INVINCIBLE: (GOLD, 0.5, True, "glow"),
            BuffType.EMPOWER: (AMBER, 0.35, True, "glow"),
            BuffType.GHOST: ((180, 200, 255), 0.25, True, "glow"),
            BuffType.STUN: ((200, 200, 100), 0.3, False, "stun"),
            BuffType.FEAR: ((120, 50, 180), 0.4, True, "glow"),
            BuffType.CURSE: ((80, 20, 100), 0.35, True, "glow"),
        }

        active_effects = []
        for buff_type, (color, base_intensity, breathe, fx_type) in buff_effects.items():
            if bm.has_buff(buff_type):
                intensity = base_intensity
                if breathe:
                    intensity *= 0.5 + 0.5 * abs(math.sin(pygame.time.get_ticks() / 400))
                active_effects.append((color, intensity, fx_type))

        if not active_effects:
            return

        # 绘制边缘光晕（根据画质调整宽度）
        q = self.game.config.graphics_quality
        if q == "performance":
            edge_width = int(40 * scale)
            # 性能模式只取最强的一个buff效果
            if active_effects:
                active_effects = [max(active_effects, key=lambda e: e[1])]
        elif q == "balanced":
            edge_width = int(60 * scale)
        else:
            edge_width = int(90 * scale)
        for color, intensity, fx_type in active_effects:
            if intensity < 0.05:
                continue
            cache_key = (color[0], color[1], color[2], int(intensity * 20), sw, sh)
            if not hasattr(self, '_buff_edge_cache'):
                self._buff_edge_cache = {}
            if cache_key not in self._buff_edge_cache:
                if len(self._buff_edge_cache) > 50:
                    self._buff_edge_cache.clear()
                edge_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
                alpha = int(160 * intensity)
                for i in range(edge_width):
                    a = int(alpha * (1 - i / edge_width) ** 0.5)
                    c = (color[0], color[1], color[2], a)
                    pygame.draw.rect(edge_surf, c, (0, i, sw, 1))
                    pygame.draw.rect(edge_surf, c, (0, sh - 1 - i, sw, 1))
                    pygame.draw.rect(edge_surf, c, (i, 0, 1, sh))
                    pygame.draw.rect(edge_surf, c, (sw - 1 - i, 0, 1, sh))
                self._buff_edge_cache[cache_key] = edge_surf
            self.game.screen.blit(self._buff_edge_cache[cache_key], (0, 0))

        # 狂暴 - 屏幕震动增强
        berserk_intensity = sum(i for c, i, t in active_effects if t == "berserk")
        if berserk_intensity > 0.1:
            self.game.camera.shake_intensity = max(self.game.camera.shake_intensity, 1.5 * berserk_intensity)

        # 燃烧 - 底部热浪
        heat_intensity = sum(i for c, i, t in active_effects if t == "heat")
        if heat_intensity > 0.1:
            heat_offset = int(2 * heat_intensity * math.sin(pygame.time.get_ticks() / 80))
            heat_key = (int(heat_intensity * 20), sw, sh)
            if not hasattr(self, '_heat_cache') or self._heat_cache[0] != heat_key:
                heat_surf = pygame.Surface((sw, int(60 * scale)), pygame.SRCALPHA)
                for y in range(int(60 * scale)):
                    a = int(80 * heat_intensity * (1 - y / (60 * scale)))
                    pygame.draw.line(heat_surf, (255, 120, 30, a), (0, y), (sw, y))
                self._heat_cache = (heat_key, heat_surf)
            self.game.screen.blit(self._heat_cache[1], (0, sh - int(60 * scale) + heat_offset))

        # 冻结 - 冷色调覆盖
        frost_intensity = sum(i for c, i, t in active_effects if t == "frost")
        if frost_intensity > 0.1:
            frost_key = (int(frost_intensity * 20), sw, sh)
            if not hasattr(self, '_frost_cache') or self._frost_cache[0] != frost_key:
                frost_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
                frost_surf.fill((100, 160, 255, int(25 * frost_intensity)))
                self._frost_cache = (frost_key, frost_surf)
            self.game.screen.blit(self._frost_cache[1], (0, 0))

        # 眩晕 - 顶部星星
        stun_intensity = sum(i for c, i, t in active_effects if t == "stun")
        if stun_intensity > 0.1:
            star_y = int(60 * scale)
            for s in range(3):
                angle = pygame.time.get_ticks() / 200 + s * 2.1
                sx = sw // 2 + int(80 * scale * math.cos(angle))
                sy = star_y + int(20 * scale * math.sin(angle))
                star_text = self.game.font.render("*", True, (255, 255, 100))
                self.game.screen.blit(star_text, (sx, sy))

    def _draw_melee_attack(self, cam_x, cam_y, scale):
        """绘制近战挥砍动画"""
        import math as _math
        g = self.game
        px = int((g.player.x - cam_x) * scale)
        py = int((g.player.y - cam_y) * scale)
        attack_range = int(g.melee_attack_range * scale)
        progress = 1 - (g.melee_attack_timer / max(0.01, g.melee_attack_duration))
        
        # 挥砍扇形角度范围
        arc_width = _math.pi * 0.8
        start_angle = g.melee_attack_angle - arc_width / 2
        # 挥砍进度对应的当前角度
        current_angle = start_angle + arc_width * progress
        
        # 武器颜色
        weapon_color = (200, 200, 200)
        if g.melee_attack_weapon:
            weapon_color = getattr(g.melee_attack_weapon, 'color', (200, 200, 200))
        
        # 绘制挥砍轨迹（半透明扇形）
        if attack_range > 0:
            # 挥砍残影
            for i in range(3):
                trail_angle = current_angle - i * 0.15
                if trail_angle < start_angle:
                    continue
                alpha = int(120 * (1 - i * 0.3) * (1 - progress * 0.5))
                trail_surf = pygame.Surface((attack_range * 2, attack_range * 2), pygame.SRCALPHA)
                # 绘制扇形
                rect = pygame.Rect(0, 0, attack_range * 2, attack_range * 2)
                pygame.draw.arc(trail_surf, (*weapon_color, alpha), rect, 
                               start_angle, trail_angle, max(2, int(8 * scale)))
                self.screen.blit(trail_surf, (px - attack_range, py - attack_range))
            
            # 当前挥砍位置的武器线条
            end_x = px + _math.cos(current_angle) * attack_range
            end_y = py + _math.sin(current_angle) * attack_range
            pygame.draw.line(self.screen, weapon_color, (px, py), (end_x, end_y), 
                           max(2, int(4 * scale)))
            # 武器端点高光
            pygame.draw.circle(self.screen, (255, 255, 255), 
                             (int(end_x), int(end_y)), max(2, int(4 * scale)))
            
            # 电锯特殊效果：持续旋转锯齿
            if g.melee_attack_weapon and g.melee_attack_weapon.weapon_type.name == 'CHAINSAW':
                for i in range(8):
                    saw_angle = current_angle + i * _math.pi / 4 + pygame.time.get_ticks() / 50
                    saw_x = px + _math.cos(saw_angle) * attack_range * 0.7
                    saw_y = py + _math.sin(saw_angle) * attack_range * 0.7
                    pygame.draw.circle(self.screen, (255, 100, 100), 
                                     (int(saw_x), int(saw_y)), max(1, int(3 * scale)))

    def _draw_fire_zones(self, cam_x, cam_y, scale):
        """绘制燃烧区域"""
        import pygame
        if not hasattr(self.game, 'fire_zones') or not self.game.fire_zones:
            return
        for zone in self.game.fire_zones:
            sx = int((zone["x"] - cam_x) * scale)
            sy = int((zone["y"] - cam_y) * scale)
            r = int(zone["radius"] * scale)
            # 半透明红色光晕
            glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            alpha = min(120, int(80 + zone["timer"] * 5))
            pygame.draw.circle(glow, (255, 100, 20, alpha), (r, r), r)
            pygame.draw.circle(glow, (255, 200, 50, alpha // 2), (r, r), int(r * 0.7))
            self.screen.blit(glow, (sx - r, sy - r))
            # 边缘火焰圈
            pygame.draw.circle(self.screen, (255, 140, 30), (sx, sy), r, max(2, int(3 * scale)))

    def _draw_smoke_zones(self, cam_x, cam_y, scale):
        """绘制烟雾区域"""
        import pygame
        if not hasattr(self.game, 'smoke_zones') or not self.game.smoke_zones:
            return
        for zone in self.game.smoke_zones:
            sx = int((zone["x"] - cam_x) * scale)
            sy = int((zone["y"] - cam_y) * scale)
            r = int(zone["radius"] * scale)
            # 半透明灰色烟雾
            smoke = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            alpha = min(160, int(100 + zone["timer"] * 3))
            pygame.draw.circle(smoke, (150, 150, 150, alpha), (r, r), r)
            pygame.draw.circle(smoke, (180, 180, 180, alpha // 2), (r, r), int(r * 0.6))
            self.screen.blit(smoke, (sx - r, sy - r))

    def _draw_airstrike_planes(self, cam_x, cam_y, scale):
        """绘制空袭飞机"""
        import pygame
        if not hasattr(self.game, 'airstrikes') or not self.game.airstrikes:
            return
        for strike in self.game.airstrikes:
            if strike.get("type") != "plane_run":
                continue
            if strike["phase"] == "done":
                continue
            px = int((strike["plane_x"] - cam_x) * scale)
            py = int((strike["plane_y"] - cam_y) * scale)
            # 飞机机身
            plane_size = int(30 * scale)
            angle = math.atan2(strike["plane_vy"], strike["plane_vx"])
            # 绘制飞机三角形
            import math
            p1 = (px + math.cos(angle) * plane_size, py + math.sin(angle) * plane_size)
            p2 = (px + math.cos(angle + 2.5) * plane_size * 0.7, py + math.sin(angle + 2.5) * plane_size * 0.7)
            p3 = (px + math.cos(angle - 2.5) * plane_size * 0.7, py + math.sin(angle - 2.5) * plane_size * 0.7)
            pygame.draw.polygon(self.screen, (80, 80, 90), [p1, p2, p3])
            pygame.draw.polygon(self.screen, (120, 120, 130), [p1, p2, p3], max(1, int(2 * scale)))
            # 机翼
            wing_len = plane_size * 0.8
            perp_angle = angle + math.pi / 2
            wx1 = (px + math.cos(perp_angle) * wing_len, py + math.sin(perp_angle) * wing_len)
            wx2 = (px - math.cos(perp_angle) * wing_len, py - math.sin(perp_angle) * wing_len)
            pygame.draw.line(self.screen, (80, 80, 90), wx1, wx2, max(2, int(4 * scale)))
            # 轰炸目标标记线
            if strike["phase"] == "incoming":
                for bomb in strike["bombs"]:
                    bx = int((bomb["x"] - cam_x) * scale)
                    by = int((bomb["y"] - cam_y) * scale)
                    pygame.draw.circle(self.screen, (255, 50, 50, 150), (bx, by), int(15 * scale), max(1, int(2 * scale)))

    def _draw_turrets(self, cam_x, cam_y, scale):
        """绘制自动炮塔 - 炫酷科幻风格"""
        if not hasattr(self.game, 'turrets') or not self.game.turrets:
            return

        import math as _math
        for turret in self.game.turrets:
            tx = int((turret["x"] - cam_x) * scale)
            ty = int((turret["y"] - cam_y) * scale)
            timer_ratio = max(0, turret["timer"] / 10.0)

            # 部署/消失动画
            if timer_ratio > 0.9:
                deploy = (1.0 - timer_ratio) / 0.1  # 0->1
            elif timer_ratio < 0.15:
                deploy = timer_ratio / 0.15  # 1->0
            else:
                deploy = 1.0
            deploy = max(0.1, deploy)

            base_r = int(22 * scale * deploy)
            if base_r < 2:
                continue

            # === 射程范围圈 ===
            range_r = int(250 * scale)
            range_surf = pygame.Surface((range_r * 2, range_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*CYAN[:3], 15), (range_r, range_r), range_r, 2)
            self.screen.blit(range_surf, (tx - range_r, ty - range_r))

            # === 底座阴影 ===
            shadow_surf = pygame.Surface((base_r * 3, base_r * 3), pygame.SRCALPHA)
            pygame.draw.circle(shadow_surf, (0, 0, 0, 100), (base_r * 1.5, base_r * 1.5 + int(4 * scale)), base_r)
            self.screen.blit(shadow_surf, (tx - base_r * 1.5, ty - base_r * 1.5))

            # === 六边形金属底座 ===
            hex_surf = pygame.Surface((base_r * 3, base_r * 3), pygame.SRCALPHA)
            hex_pts = []
            for i in range(6):
                angle = _math.radians(60 * i - 30)
                hx = base_r * 1.5 + _math.cos(angle) * base_r
                hy = base_r * 1.5 + _math.sin(angle) * base_r
                hex_pts.append((hx, hy))
            pygame.draw.polygon(hex_surf, (50, 55, 65, 230), hex_pts)
            pygame.draw.polygon(hex_surf, (*CYAN[:3], 180), hex_pts, max(1, int(2 * scale)))
            # 底座内圈
            pygame.draw.circle(hex_surf, (35, 40, 50, 255), (base_r * 1.5, base_r * 1.5), int(base_r * 0.65))
            self.screen.blit(hex_surf, (tx - base_r * 1.5, ty - base_r * 1.5))

            # === 旋转能量环 ===
            ring_angle = pygame.time.get_ticks() / 500
            for ring_i in range(2):
                ring_r = int(base_r * (0.5 + ring_i * 0.15))
                ring_surf = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
                for seg in range(8):
                    a1 = _math.radians(ring_angle * 57.3 + seg * 45 + ring_i * 22)
                    a2 = a1 + _math.radians(25)
                    pygame.draw.arc(ring_surf, (*CYAN[:3], 120 - ring_i * 40),
                                    (0, 0, ring_r * 2, ring_r * 2), a1, a2, max(1, int(2 * scale)))
                self.screen.blit(ring_surf, (tx - ring_r, ty - ring_r))

            # === 炮管（指向最近敌人）===
            closest = None
            closest_dist = 9999
            for enemy in self.game.enemies:
                d = _math.hypot(enemy.x - turret["x"], enemy.y - turret["y"])
                if d < closest_dist:
                    closest_dist = d
                    closest = enemy
            if closest:
                barrel_angle = _math.atan2(closest.y - turret["y"], closest.x - turret["x"])
            else:
                barrel_angle = _math.radians(pygame.time.get_ticks() / 1000)

            barrel_len = int(base_r * 1.4)
            barrel_w = max(3, int(5 * scale))
            # 炮管主体
            end_x = tx + _math.cos(barrel_angle) * barrel_len
            end_y = ty + _math.sin(barrel_angle) * barrel_len
            pygame.draw.line(self.screen, (70, 75, 85), (tx, ty), (end_x, end_y), barrel_w + 2)
            pygame.draw.line(self.screen, (120, 130, 145), (tx, ty), (end_x, end_y), barrel_w)
            # 炮口
            muzzle_r = int(barrel_w * 0.8)
            pygame.draw.circle(self.screen, (40, 45, 55), (int(end_x), int(end_y)), muzzle_r)
            # 开火闪光
            if turret["fire_timer"] > 0.35:
                flash_surf = pygame.Surface((muzzle_r * 4, muzzle_r * 4), pygame.SRCALPHA)
                pygame.draw.circle(flash_surf, (*YELLOW[:3], 180), (muzzle_r * 2, muzzle_r * 2), muzzle_r * 2)
                pygame.draw.circle(flash_surf, (255, 255, 200, 120), (muzzle_r * 2, muzzle_r * 2), muzzle_r)
                self.screen.blit(flash_surf, (int(end_x) - muzzle_r * 2, int(end_y) - muzzle_r * 2))

            # === 中央核心 ===
            core_r = int(base_r * 0.3)
            core_color = CYAN if timer_ratio > 0.3 else RED
            core_surf = pygame.Surface((core_r * 2, core_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(core_surf, (*core_color[:3], 200), (core_r, core_r), core_r)
            pygame.draw.circle(core_surf, (255, 255, 255, 150), (core_r, core_r), int(core_r * 0.5))
            self.screen.blit(core_surf, (tx - core_r, ty - core_r))

            # === 剩余时间环 ===
            if timer_ratio < 1.0:
                time_r = int(base_r * 1.1)
                time_surf = pygame.Surface((time_r * 2, time_r * 2), pygame.SRCALPHA)
                pygame.draw.arc(time_surf, (*GOLD[:3], 150),
                                (0, 0, time_r * 2, time_r * 2),
                                _math.radians(-90), _math.radians(-90 + 360 * timer_ratio),
                                max(1, int(3 * scale)))
                self.screen.blit(time_surf, (tx - time_r, ty - time_r))

    def _draw_muzzle_flash(self):
        """绘制枪口闪光效果 - 增强"""
        player = self.game.player
        if not player or player.muzzle_flash_timer <= 0:
            return

        scale = self.game.scale
        camera = self.game.camera

        px = int((player.x - camera.x) * scale)
        py = int((player.y - camera.y) * scale)

        angle_rad = math.radians(player.facing_angle)
        flash_dist = int(35 * scale)
        flash_x = px + math.cos(angle_rad) * flash_dist
        flash_y = py + math.sin(angle_rad) * flash_dist

        flash_intensity = player.muzzle_flash_timer / player.muzzle_flash_duration

        # 多层发光
        for i in range(4):
            radius = int((20 + i * 10) * scale * flash_intensity)
            alpha = int((180 - i * 35) * flash_intensity)
            colors = [(255, 240, 150, alpha), (255, 200, 80, alpha), (255, 150, 50, alpha), (255, 100, 30, alpha)]
            flash_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, colors[i], (radius, radius), radius)
            self.game.screen.blit(flash_surf, (flash_x - radius, flash_y - radius))

        # 放射状光线
        for offset in [-20, -10, 0, 10, 20]:
            rad = math.radians(player.facing_angle + offset)
            line_len = int(50 * scale * flash_intensity)
            end_x = flash_x + math.cos(rad) * line_len
            end_y = flash_y + math.sin(rad) * line_len
            line_alpha = int(220 * flash_intensity)
            pygame.draw.line(self.game.screen, (255, 220, 100, line_alpha), 
                           (flash_x, flash_y), (end_x, end_y), max(2, int(4 * scale)))

        # 中心爆点
        core_size = int(8 * scale * flash_intensity)
        pygame.draw.circle(self.game.screen, WHITE, (int(flash_x), int(flash_y)), core_size)
        pygame.draw.circle(self.game.screen, (255, 255, 200), (int(flash_x), int(flash_y)), max(1, core_size - 2))
