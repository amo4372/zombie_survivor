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

class Camera:
    def __init__(self, width, height):
        self.x = 0
        self.y = 0
        self.width = width
        self.height = height
        self.shake_x = 0
        self.shake_y = 0
        self.shake_duration = 0
        self.shake_intensity = 0
        self.shake_enabled = True

    def shake(self, intensity=5, duration=0.3):
        if not self.shake_enabled:
            return
        self.shake_intensity = intensity
        self.shake_duration = duration

    def follow(self, target_x, target_y, dt, smooth=0.1):
        target_cam_x = target_x - self.width // 2
        target_cam_y = target_y - self.height // 2
        self.x += (target_cam_x - self.x) * smooth
        self.y += (target_cam_y - self.y) * smooth

        if self.shake_duration > 0:
            self.shake_x = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_y = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_duration -= dt
            self.shake_intensity *= 0.9
        else:
            self.shake_x = 0
            self.shake_y = 0

    def shake(self, intensity=5, duration=0.3):
        self.shake_intensity = intensity
        self.shake_duration = duration

    def apply(self, x, y):
        return x - self.x + self.shake_x, y - self.y + self.shake_y

class Renderer:
    def __init__(self, screen, game):
        self.screen = screen
        self.game = game
        self._touch_clicks = {}  # 符文界面等：跨帧触控按下状态（key -> bool）

    def _clicked(self, rect, mouse_pos, mouse_pressed, touch_events, key):
        """统一鼠标+触控点击检测（带跨帧触控状态）。
        rect 为已缩放的屏幕坐标矩形。
        鼠标：按下且在 rect 内即触发（保持原有即时反馈）。
        触控：down 在 rect 内记录，手指抬起仍在 rect 内时触发。"""
        if rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            return True
        if touch_events:
            for e in touch_events:
                if e["type"] == "down" and rect.collidepoint(e["pos"]):
                    self._touch_clicks[key] = True
                elif e["type"] == "up":
                    was = self._touch_clicks.pop(key, False)
                    if was and rect.collidepoint(e["pos"]):
                        return True
        return False

    def render(self):
        state = self.game.state

        if state == GameState.MENU:
            self._draw_menu()
        elif state == GameState.SETTINGS:
            self._draw_settings()
        elif state == GameState.HUD_EDIT:
            self._draw_hud_edit()
        elif state == GameState.PLAY_SELECT:
            self._draw_play_select()
        elif state == GameState.MULTIPLAYER_SELECT:
            self._draw_multiplayer_select()
        elif state == GameState.NET_MULTIPLAYER:
            self._draw_net_multiplayer()
        elif state == GameState.NET_WAIT:
            self._draw_net_wait()
        elif state == GameState.NET_CLIENT_PLAY:
            self._draw_net_client()
        elif state == GameState.TUTORIAL:
            self._draw_tutorial()
        elif state == GameState.PLAYING:
            self._draw_playing()
            if getattr(self.game, 'dev_mode', False) and getattr(self.game, 'dev_panel_open', False):
                self._draw_dev_panel()
        elif state == GameState.PAUSED:
            self._draw_playing()
            self._draw_pause()
        elif state == GameState.SKILL_SELECT:
            self._draw_playing()
            self._draw_skill_select()
        elif state == GameState.DIALOGUE:
            self._draw_playing()
            self._draw_dialogue()
        elif state == GameState.GAME_OVER:
            self._draw_game_over()
        elif state == GameState.VICTORY:
            self._draw_victory()
        elif state == GameState.ENDING:
            self._draw_ending()
        elif state == GameState.RECORDS:
            self._draw_records()
        elif state == GameState.ACHIEVEMENTS:
            self._draw_achievements()
        elif state == GameState.MODE_SELECT:
            self._draw_mode_select()
        elif state == GameState.DIFFICULTY_SELECT:
            self._draw_difficulty_select()
        elif state == GameState.EQUIP_SELECT:
            self._draw_equip_select()
        elif state == GameState.STORY_ARCHIVE:
            self._draw_story_archive()
        elif state == GameState.CODEX:
            self._draw_codex()
        elif state == GameState.SKILL_TREE:
            self._draw_playing()
            self._draw_skill_tree()
        elif state == GameState.TEXT_VIEWER:
            self._draw_playing()
            self._draw_text_viewer()
        elif state == GameState.MOD_MANAGER:
            self._draw_mod_manager()
        elif state == GameState.UPDATE:
            self._draw_update()
        elif state == GameState.UPDATE_NOTES:
            self._draw_update_notes()
        elif state == GameState.RUNE_VIEW:
            self._draw_playing()
            self._draw_rune_view()

        pygame.display.flip()

    def _draw_menu(self):
        # 播放菜单音乐
        self.game.assets.play_music("menu")
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width

        # 绘制菜单背景图（如有）
        bg_img = self.game.assets.get_image("menu_bg", sw, self.game.scaled_height)
        if bg_img:
            self.screen.blit(bg_img, (0, 0))

        # 标题带血红色效果
        title = self.game.font_title.render("丧尸幸存者", True, RED)
        title_rect = title.get_rect(center=(sw // 2, int(150 * scale)))
        # 标题阴影
        shadow = self.game.font_title.render("丧尸幸存者", True, DARK_RED)
        self.screen.blit(shadow, (title_rect.x + 3, title_rect.y + 3))
        self.screen.blit(title, title_rect)

        subtitle = self.game.font.render("Zombie Survivor", True, GRAY)
        subtitle_rect = subtitle.get_rect(center=(sw // 2, int(200 * scale)))
        self.screen.blit(subtitle, subtitle_rect)

        # 副标题下方添加氛围描述
        desc = self.game.font_small.render("在无尽的黑暗中，唯有生存才是真理", True, DARK_GRAY)
        desc_rect = desc.get_rect(center=(sw // 2, int(230 * scale)))
        self.screen.blit(desc, desc_rect)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        for i, btn in enumerate(self.game.menu_buttons):
            # 两列布局：左列 i=0..5，右列 i=6..10，避免11个按钮单列溢出720逻辑高
            if i < 6:
                btn.base_x = 360
                btn.base_y = 260 + i * 68
            else:
                btn.base_x = 720
                btn.base_y = 260 + (i - 6) * 68
            # 继续游戏按钮：无存档时禁用
            if i == 0:
                btn.enabled = self.game.has_saved_game()
                if not btn.enabled:
                    btn.color = (80, 80, 80)
                else:
                    btn.color = CYAN
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                self.game.logger.info(f"菜单按钮 '{btn.text}' 被点击")
                if i == 0:
                    # 继续游戏
                    if self.game.has_saved_game():
                        self.game.load_game_state()
                elif i == 1:
                    self.game.state = GameState.PLAY_SELECT
                elif i == 2:
                    self.game.state = GameState.STORY_ARCHIVE
                    self.game.story_archive_scroll = 0
                    self.game.story_archive_selected = None
                elif i == 3:
                    # 图鉴
                    self.game.state = GameState.CODEX
                    self.game.codex_tab = "monster"
                    self.game.codex_category = "全部"
                    self.game.codex_scroll = 0
                    self.game.codex_selected = None
                elif i == 4:
                    self.game.state = GameState.RECORDS
                elif i == 5:
                    self.game.state = GameState.ACHIEVEMENTS
                elif i == 6:
                    # Mod管理
                    self.game.state = GameState.MOD_MANAGER
                    self.game.mod_manager_scroll = 0
                    self.game.mod_selected = None
                    self.game.mod_list_cache = mod_loader.get_all_available_mods()
                elif i == 7:
                    # 检查更新
                    self.game.state = GameState.UPDATE
                    self.game.update_status_text = '点击"检查更新"按钮查看最新版本'
                    self.game.update_progress = 0.0
                elif i == 8:
                    self.game.state = GameState.SETTINGS
                elif i == 9:
                    self.game.state = GameState.TUTORIAL
                elif i == 10:
                    self.game.running = False
                elif i == 11:
                    # 更新说明
                    self.game.state = GameState.UPDATE_NOTES
                    self.game._open_update_notes()
            btn.draw(self.screen, self.game.font_large, scale)

        # 开发者模式入口：版本号连点5次弹出密码框
        dev_rect = pygame.Rect(10, self.game.scaled_height - 34, 300, 30)
        dev_hit = False
        for te in self.game.touch_events:
            if te["type"] == "down" and dev_rect.collidepoint(te["pos"]):
                dev_hit = True
        if dev_rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            dev_hit = True
        if dev_hit:
            self.game.dev_click_count += 1
            self.game.dev_click_timer = 2.0
            if self.game.dev_click_count >= 5:
                self.game.dev_click_count = 0
                if not self.game.dev_mode:
                    self.game.dev_input_active = True
                    self.game.dev_input_str = ""
                    self.game.dev_input_focused = False
                    try:
                        pygame.key.stop_text_input()  # 未点击输入框前不唤起输入法
                    except Exception:
                        pass
                    self.game.update_status_text = "输入开发者密码（连点版本号取消）"
        if self.game.dev_click_timer > 0:
            self.game.dev_click_timer -= (1.0 / 60.0)
            if self.game.dev_click_timer <= 0:
                self.game.dev_click_count = 0

        version = self.game.font_small.render(f"v{getattr(self.game, 'current_version_str', '1.0.0')} - 黑暗尸潮", True, GRAY)
        self.screen.blit(version, (10, self.game.scaled_height - 30))
        if self.game.dev_mode:
            dev_tag = self.game.font_small.render("[开发者模式:ON]", True, (60, 220, 60))
            self.screen.blit(dev_tag, (300, self.game.scaled_height - 30))

        # 开发者密码输入框
        if self.game.dev_input_active:
            self._draw_dev_password()

    def _dev_confirm(self, g):
        """确认开发者密码（触控/鼠标按钮兜底，键盘用回车）"""
        if g.dev_input_str == g._DEV_PASSWORD:
            g.dev_mode = True
            g.dev_input_active = False
            g.dev_input_str = ""
            g._blur_dev_input()
            g.update_status_text = "开发者模式已开启！局内按 F9 键打开调试面板"
        else:
            g.dev_input_active = False
            g.dev_input_str = ""
            g._blur_dev_input()
            g.update_status_text = "密码错误，请重试（连点版本号重新输入）"

    def _draw_dev_password(self):
        """绘制开发者密码文本输入框：点击（触控/鼠标/键盘）聚焦后接受系统输入法输入"""
        g = self.game
        scale = g.scale
        sw = g.scaled_width
        sh = g.scaled_height
        # 半透明遮罩
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        self.screen.blit(ov, (0, 0))
        # 文本输入框
        box_w, box_h = int(420 * scale), int(56 * scale)
        box_x = sw // 2 - box_w // 2
        box_y = int(140 * scale)
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        focused = g.dev_input_focused
        pygame.draw.rect(self.screen, (40, 40, 52), box_rect, border_radius=6)
        border_col = (120, 210, 130) if focused else (100, 100, 130)
        pygame.draw.rect(self.screen, border_col, box_rect, 3 if focused else 2, border_radius=6)
        title = g.font.render("开发者密码", True, (240, 220, 120))
        self.screen.blit(title, (sw // 2 - title.get_width() // 2, int(92 * scale)))
        # 密码文本 + 光标（聚焦时闪烁）
        pw_txt = g.font.render("*" * len(g.dev_input_str), True, (255, 255, 255))
        self.screen.blit(pw_txt, (box_x + 18, box_y + box_h // 2 - pw_txt.get_height() // 2))
        if focused:
            cx = box_x + 18 + pw_txt.get_width() + 6
            if int(pygame.time.get_ticks() / 500) % 2 == 0:
                pygame.draw.line(self.screen, (255, 255, 255),
                                 (cx, box_y + 14), (cx, box_y + box_h - 14), 2)
        # 提示文字
        if focused:
            hint = g.font_small.render("系统输入法中… 回车确认 · 退格删除 · ESC 失焦", True, (180, 225, 185))
        else:
            hint = g.font_small.render("点击输入框唤起系统输入法 · 回车/空格聚焦 · ESC 关闭", True, GRAY)
        self.screen.blit(hint, (sw // 2 - hint.get_width() // 2, box_y + box_h + 10))
        status = g.font_small.render(g.update_status_text or "", True, (255, 180, 120))
        self.screen.blit(status, (sw // 2 - status.get_width() // 2, box_y + box_h + 44))

        # 底部操作按钮：确认 / 取消（触控兜底；键盘可用回车确认）
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        btn_w, btn_h = int(150 * scale), int(42 * scale)
        btn_y = box_y + box_h + 86
        ok_rect = pygame.Rect(sw // 2 - btn_w - 10, btn_y, btn_w, btn_h)
        cancel_rect = pygame.Rect(sw // 2 + 10, btn_y, btn_w, btn_h)
        # 确认
        hover = ok_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, (60, 130, 70) if not hover else (85, 165, 95), ok_rect, border_radius=5)
        pygame.draw.rect(self.screen, (160, 160, 180), ok_rect, 1, border_radius=5)
        t = g.font.render("确认", True, (255, 255, 255))
        self.screen.blit(t, (ok_rect.centerx - t.get_width() // 2, ok_rect.centery - t.get_height() // 2))
        # 取消
        hover = cancel_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, (120, 70, 70) if not hover else (150, 90, 90), cancel_rect, border_radius=5)
        pygame.draw.rect(self.screen, (160, 160, 180), cancel_rect, 1, border_radius=5)
        t = g.font.render("取消", True, (255, 255, 255))
        self.screen.blit(t, (cancel_rect.centerx - t.get_width() // 2, cancel_rect.centery - t.get_height() // 2))

        # ===== 点击交互（顺序：按钮 → 输入框聚焦 → 外部失焦）=====
        # 1) 按钮点击（鼠标按下 / 触控抬起）
        if ok_rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            self._dev_confirm(g)
        for te in g.touch_events:
            if te["type"] == "up" and ok_rect.collidepoint(te["pos"]):
                self._dev_confirm(g)
        if cancel_rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            g.dev_input_active = False
            g.dev_input_str = ""
            g._blur_dev_input()
        for te in g.touch_events:
            if te["type"] == "up" and cancel_rect.collidepoint(te["pos"]):
                g.dev_input_active = False
                g.dev_input_str = ""
                g._blur_dev_input()
        # 2) 点击输入框 → 聚焦（接受系统输入法输入）
        if box_rect.collidepoint(mouse_pos) and mouse_pressed[0]:
            g._focus_dev_input()
        for te in g.touch_events:
            if te["type"] == "up" and box_rect.collidepoint(te["pos"]):
                g._focus_dev_input()
        # 3) 点击输入框/按钮之外的区域 → 失焦（关闭系统输入法）
        outside = not (box_rect.collidepoint(mouse_pos) or ok_rect.collidepoint(mouse_pos)
                       or cancel_rect.collidepoint(mouse_pos))
        if outside and mouse_pressed[0]:
            g._blur_dev_input()
        for te in g.touch_events:
            if te["type"] == "up" and not (box_rect.collidepoint(te["pos"]) or ok_rect.collidepoint(te["pos"])
                                           or cancel_rect.collidepoint(te["pos"])):
                g._blur_dev_input()

    def _draw_dev_panel(self):
        """绘制局内开发者调试面板"""
        g = self.game
        scale = g.scale
        sw = g.scaled_width
        ov = pygame.Surface((sw, g.scaled_height), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 120))
        self.screen.blit(ov, (0, 0))
        head = g.font.render("开发者调试面板", True, (60, 220, 60))
        self.screen.blit(head, (sw - 210, 40))
        tip = g.font_small.render("F9 键 关闭面板 · 无敌/倍率等", True, (200, 200, 210))
        self.screen.blit(tip, (sw - 250, 66))
        bx, by = sw - 190, 90
        for btn in g.dev_buttons:
            btn.base_x = bx
            btn.base_y = by
            # 注意：bx/by 已是屏幕像素坐标，Button 内部不再缩放（传 scale=1.0）
            btn.draw(self.screen, g.font_large, 1.0)
            by += 42

    def _draw_mode_select(self):
        """模式选择界面"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width

        title = self.game.font_title.render("选择模式", True, WHITE)
        title_rect = title.get_rect(center=(sw // 2, int(120 * scale)))
        self.screen.blit(title, title_rect)

        desc = self.game.font_small.render("每种模式都有独特的玩法体验", True, DARK_GRAY)
        desc_rect = desc.get_rect(center=(sw // 2, int(170 * scale)))
        self.screen.blit(desc, desc_rect)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        # 模式描述
        mode_descs = [
            "5张地图，20分钟/张，剧情收集，特殊事件",
            "无限生存，倒计时出错后变为正向计时",
            "限时20分钟，尽可能存活并击败Boss",
        ]

        for i, btn in enumerate(self.game.mode_select_buttons):
            btn.base_y = (250 + i * 80) if i < 3 else 520
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                if i == 0:
                    self.game.config.game_mode = GameMode.STORY
                    self.game.state = GameState.DIFFICULTY_SELECT
                elif i == 1:
                    self.game.config.game_mode = GameMode.ENDLESS
                    self.game.state = GameState.DIFFICULTY_SELECT
                elif i == 2:
                    self.game.config.game_mode = GameMode.TIMED
                    self.game.state = GameState.DIFFICULTY_SELECT
                elif i == 3:
                    self.game.state = GameState.MENU
            btn.draw(self.screen, self.game.font_large, scale)
            # 显示模式描述
            if i < 3:
                desc_text = self.game.font_small.render(mode_descs[i], True, LIGHT_GRAY)
                desc_rect = desc_text.get_rect(center=(sw // 2, int((290 + i * 80) * scale)))
                self.screen.blit(desc_text, desc_rect)

    def _draw_difficulty_select(self):
        """难度选择界面"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width

        title = self.game.font_title.render("选择难度", True, WHITE)
        title_rect = title.get_rect(center=(sw // 2, int(100 * scale)))
        self.screen.blit(title, title_rect)

        mode_name = {"STORY": "故事模式", "ENDLESS": "无尽模式", "TIMED": "限时模式"}
        mode_text = self.game.font.render(f"当前模式: {mode_name.get(self.game.config.game_mode.name, '未知')}", True, GOLD)
        mode_rect = mode_text.get_rect(center=(sw // 2, int(150 * scale)))
        self.screen.blit(mode_text, mode_rect)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        diff_descs = [
            "僵尸较弱，刷新较慢，适合新手体验剧情",
            "标准难度，平衡的挑战与体验",
            "僵尸更强更快，资源稀缺，考验操作",
            "极限挑战，Boss伤害极高，一命通关",
        ]
        diff_colors = [GREEN, GOLD, ORANGE, CRIMSON]

        for i, btn in enumerate(self.game.difficulty_select_buttons):
            if i < 4:
                btn.base_y = (200 + i * 75)
                btn.color = diff_colors[i]
            else:
                btn.base_y = 540
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                if i < 4:
                    difficulties = ["简单", "普通", "困难", "地狱"]
                    self.game.config.difficulty = difficulties[i]
                    self.game.config.save()
                    # 进入局外装备选择（武器+角色）界面，确认后开始游戏
                    self.game.state = GameState.EQUIP_SELECT
                elif i == 4:
                    self.game.state = GameState.MODE_SELECT
            btn.draw(self.screen, self.game.font_large, scale)
            if i < 4:
                desc_text = self.game.font_small.render(diff_descs[i], True, LIGHT_GRAY)
                desc_rect = desc_text.get_rect(center=(sw // 2, int((240 + i * 75) * scale)))
                self.screen.blit(desc_text, desc_rect)


    def _draw_equip_select(self):
        """局外装备选择界面：两栏列表（点击仅选中）+ 每栏底部独立'解锁/升级'大按钮，避免误触"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        g = self.game

        title_txt = "玩家2 · 选择装备" if g.equip_p2_phase else "选择装备"
        title = self.game.font_title.render(title_txt, True, WHITE)
        self.screen.blit(title, title.get_rect(center=(sw // 2, int(30 * scale))))

        # 金币余额
        coin_txt = self.game.font.render(f"金币: {g.records.get_coins()}", True, GOLD)
        self.screen.blit(coin_txt, coin_txt.get_rect(topright=(sw - 40, int(16 * scale))))

        # 当前选择
        cur_weapon_name = Weapon(g.selected_weapon).name if g.selected_weapon else "-"
        cur_char = g.selected_character or "幸存者"
        sel_txt = self.game.font.render(f"当前武器: {cur_weapon_name} Lv.{g.selected_weapon_level}    角色: {cur_char} Lv.{g.records.get_character_level(cur_char)}", True, GREEN)
        self.screen.blit(sel_txt, sel_txt.get_rect(center=(sw // 2, int(58 * scale))))

        mouse_pos = pygame.mouse.get_pos()
        clicked = None
        for ev in g.touch_events:
            if ev["type"] == "up":
                clicked = ev["pos"]
                break

        # ================== 武器栏 ==================
        wx, wy, ww, wh = int(40 * scale), int(88 * scale), int(600 * scale), int(330 * scale)
        pygame.draw.rect(self.screen, (20, 20, 28), (wx, wy, ww, wh), border_radius=10)
        pygame.draw.rect(self.screen, (70, 70, 95), (wx, wy, ww, wh), 2, border_radius=10)
        w_title = self.game.font.render("武器 (点击选中)", True, WHITE)
        self.screen.blit(w_title, (wx + 12, wy + 6))
        rows = g.get_weapon_shop_rows()
        row_h = int(58 * scale)
        header_h = int(30 * scale)
        list_top = wy + header_h
        list_h = wh - header_h
        visible = max(1, int(list_h // row_h))
        max_scroll = max(0, len(rows) - visible)
        scroll_i = max(0, int(g.equip_weapon_scroll))
        scroll_i = min(scroll_i, max_scroll)
        g.equip_weapon_scroll = scroll_i
        rows_vis = rows[scroll_i: scroll_i + visible]
        for i, (wt, name, price, owned, level, locked, desc) in enumerate(rows_vis):
            ry = list_top + i * row_h
            rect = pygame.Rect(wx + 6, ry + 3, ww - 12, row_h - 8)
            is_sel = (g.selected_weapon == wt)
            color = (38, 45, 70) if is_sel else (30, 30, 42)
            pygame.draw.rect(self.screen, color, rect, border_radius=8)
            if is_sel:
                pygame.draw.rect(self.screen, GOLD, rect, 2, border_radius=8)
            ncol = LIGHT_GRAY if locked else WHITE
            n_txt = self.game.font_small.render(name, True, ncol)
            self.screen.blit(n_txt, (rect.x + 10, rect.y + 8))
            if locked:
                st = self.game.font_small.render(locked, True, CRIMSON)
            elif owned:
                st = self.game.font_small.render(f"Lv.{level}", True, GREEN)
            else:
                st = self.game.font_small.render(f"{price}金币", True, GOLD)
            self.screen.blit(st, (rect.x + 10, rect.y + 28))
            if is_sel and not locked:
                d = self.game.font_small.render(desc if len(desc) <= 20 else desc[:20] + "…", True, LIGHT_GRAY)
                self.screen.blit(d, (rect.x + 110, rect.y + 8))
            # 行点击仅选中（解锁/升级在下方独立按钮）
            if clicked and rect.collidepoint(clicked):
                g.selected_weapon = wt
                g.selected_weapon_level = level if owned else 1
            if rect.collidepoint(mouse_pos) and not is_sel:
                pygame.draw.rect(self.screen, (75, 75, 100), rect, 2, border_radius=8)
        if max_scroll > 0:
            hint = self.game.font_small.render(f"↑↓滚动 {scroll_i + 1}/{len(rows)}", True, LIGHT_GRAY)
            self.screen.blit(hint, (wx + 12, wy + wh - 18))
            # 滚动条（图鉴式）
            bar_x = wx + ww - 10
            bar_y = list_top
            bar_h = list_h
            thumb_h = max(18, int(bar_h * (visible / len(rows))))
            thumb_y = bar_y + int((bar_h - thumb_h) * (scroll_i / max_scroll)) if max_scroll > 0 else bar_y
            pygame.draw.rect(self.screen, (60, 60, 90), (bar_x, bar_y, 5, bar_h))
            pygame.draw.rect(self.screen, (150, 150, 200), (bar_x, thumb_y, 5, thumb_h))

        # 武器操作按钮（独立大按钮，针对当前选中武器）
        sel_w_row = next((r for r in rows if r[0] == g.selected_weapon), None)
        w_op = None
        if sel_w_row:
            _wname, _wprice, _wowned, _wlevel, _wlocked = sel_w_row[1], sel_w_row[2], sel_w_row[3], sel_w_row[4], sel_w_row[5]
            if _wlocked:
                w_op = ("disabled", f"未解锁: {_wlocked}")
            elif not _wowned:
                w_op = ("unlock", f"解锁 {_wname}  {_wprice}金币")
            elif _wlevel < 5:
                _up_p = g.get_weapon_upgrade_price(g.selected_weapon)
                w_op = ("upgrade", f"升级 {_wname} 至Lv.{_wlevel + 1}  {_up_p}金币")
            else:
                w_op = ("disabled", f"{_wname} 已满级 Lv.5")
        w_op_rect = pygame.Rect(wx + 6, wy + wh + 8, ww - 12, int(54 * scale))
        w_op_enabled = w_op and w_op[0] != "disabled"
        if w_op_enabled:
            pygame.draw.rect(self.screen, (45, 80, 45), w_op_rect, border_radius=10)
            pygame.draw.rect(self.screen, GREEN, w_op_rect, 2, border_radius=10)
        else:
            pygame.draw.rect(self.screen, (50, 50, 55), w_op_rect, border_radius=10)
            pygame.draw.rect(self.screen, GRAY, w_op_rect, 2, border_radius=10)
        w_otxt = self.game.font.render(w_op[1] if w_op else "请选择武器", True, WHITE if w_op_enabled else LIGHT_GRAY)
        self.screen.blit(w_otxt, w_otxt.get_rect(center=w_op_rect.center))
        if clicked and w_op_enabled and w_op_rect.collidepoint(clicked):
            if w_op[0] == "unlock":
                res = g.equip_buy_weapon(g.selected_weapon)
                g.equip_hover = {"ok": f"已解锁 {_wname}", "no_coin": "金币不足",
                                 "locked_wang": "需先击败王某", "owned": "已拥有"}.get(res, "")
            else:
                res = g.upgrade_weapon_shop(g.selected_weapon)
                g.equip_hover = {"ok": f"{_wname} 升至 Lv.{g.records.get_weapon_level(g.selected_weapon.name)}",
                                 "no_coin": "金币不足", "max": "已满级"}.get(res, "")

        # ================== 角色栏 ==================
        cx, cy, cw, ch = int(660 * scale), int(88 * scale), int(580 * scale), int(330 * scale)
        pygame.draw.rect(self.screen, (20, 20, 28), (cx, cy, cw, ch), border_radius=10)
        pygame.draw.rect(self.screen, (70, 70, 95), (cx, cy, cw, ch), 2, border_radius=10)
        c_title = self.game.font.render("角色 (点击选中)", True, WHITE)
        self.screen.blit(c_title, (cx + 12, cy + 6))
        crows = g.get_character_shop_rows()
        c_row_h = int(78 * scale)
        c_visible = max(1, int((ch - header_h) // c_row_h))
        c_max_scroll = max(0, len(crows) - c_visible)
        c_scroll = max(0, int(g.equip_character_scroll))
        c_scroll = min(c_scroll, c_max_scroll)
        g.equip_character_scroll = c_scroll
        crows_vis = crows[c_scroll: c_scroll + c_visible]
        for i, (cname, cprice, cowned, clevel, cdesc, cability, clocked) in enumerate(crows_vis):
            ry = cy + header_h + i * c_row_h
            rect = pygame.Rect(cx + 6, ry + 3, cw - 12, c_row_h - 10)
            is_sel = (g.selected_character == cname or (g.selected_character is None and cname == "幸存者"))
            color = (38, 45, 70) if is_sel else (30, 30, 42)
            pygame.draw.rect(self.screen, color, rect, border_radius=8)
            if is_sel:
                pygame.draw.rect(self.screen, GOLD, rect, 2, border_radius=8)
            ncol = LIGHT_GRAY if clocked else WHITE
            n_txt = self.game.font_small.render(cname, True, ncol)
            self.screen.blit(n_txt, (rect.x + 10, rect.y + 6))
            ab = self.game.font_small.render(cability, True, LIGHT_GRAY)
            self.screen.blit(ab, (rect.x + 10, rect.y + 24))
            if clocked:
                st = self.game.font_small.render(clocked, True, CRIMSON)
            elif cowned:
                st = self.game.font_small.render(f"Lv.{clevel}", True, GREEN)
            else:
                st = self.game.font_small.render(f"{cprice}金币", True, GOLD)
            self.screen.blit(st, (rect.x + 10, rect.y + 46))
            # 行点击仅选中
            if clicked and rect.collidepoint(clicked):
                g.selected_character = cname
            if rect.collidepoint(mouse_pos) and not is_sel:
                pygame.draw.rect(self.screen, (75, 75, 100), rect, 2, border_radius=8)
        if c_max_scroll > 0:
            c_hint = self.game.font_small.render(f"↑↓滚动 {c_scroll + 1}/{len(crows)}", True, LIGHT_GRAY)
            self.screen.blit(c_hint, (cx + 12, cy + ch - 18))
            # 滚动条（图鉴式）
            c_bar_x = cx + cw - 10
            c_bar_y = cy + header_h
            c_bar_h = ch - header_h
            c_thumb_h = max(18, int(c_bar_h * (c_visible / len(crows))))
            c_thumb_y = c_bar_y + int((c_bar_h - c_thumb_h) * (c_scroll / c_max_scroll)) if c_max_scroll > 0 else c_bar_y
            pygame.draw.rect(self.screen, (60, 60, 90), (c_bar_x, c_bar_y, 5, c_bar_h))
            pygame.draw.rect(self.screen, (150, 150, 200), (c_bar_x, c_thumb_y, 5, c_thumb_h))

        # 角色操作按钮（独立大按钮，针对当前选中角色）
        sel_c = g.selected_character or "幸存者"
        sel_c_row = next((r for r in crows if r[0] == sel_c), None)
        c_op = None
        if sel_c_row:
            _cname, _cprice, _cowned, _clevel, _clocked = sel_c_row[0], sel_c_row[1], sel_c_row[2], sel_c_row[3], sel_c_row[6]
            if _clocked:
                c_op = ("disabled", f"未解锁: {_clocked}")
            elif not _cowned:
                c_op = ("unlock", f"解锁 {_cname}  {_cprice}金币")
            elif _clevel < 5:
                _cup = g.get_character_upgrade_price(_cname)
                c_op = ("upgrade", f"升级 {_cname} 至Lv.{_clevel + 1}  {_cup}金币")
            else:
                c_op = ("disabled", f"{_cname} 已满级 Lv.5")
        c_op_rect = pygame.Rect(cx + 6, cy + ch + 8, cw - 12, int(54 * scale))
        c_op_enabled = c_op and c_op[0] != "disabled"
        if c_op_enabled:
            pygame.draw.rect(self.screen, (45, 80, 45), c_op_rect, border_radius=10)
            pygame.draw.rect(self.screen, GREEN, c_op_rect, 2, border_radius=10)
        else:
            pygame.draw.rect(self.screen, (50, 50, 55), c_op_rect, border_radius=10)
            pygame.draw.rect(self.screen, GRAY, c_op_rect, 2, border_radius=10)
        c_otxt = self.game.font.render(c_op[1] if c_op else "请选择角色", True, WHITE if c_op_enabled else LIGHT_GRAY)
        self.screen.blit(c_otxt, c_otxt.get_rect(center=c_op_rect.center))
        if clicked and c_op_enabled and c_op_rect.collidepoint(clicked):
            if c_op[0] == "unlock":
                res = g.equip_buy_character(_cname)
                g.equip_hover = {"ok": f"已解锁 {_cname}", "no_coin": "金币不足",
                                 "locked_wang": "需先击败王某", "owned": "已拥有"}.get(res, "")
            else:
                res = g.upgrade_character_shop(_cname)
                g.equip_hover = {"ok": f"{_cname} 升至 Lv.{g.records.get_character_level(_cname)}",
                                 "no_coin": "金币不足", "max": "已满级"}.get(res, "")

        # ================== 地图选择（故事模式） ==================
        if g.config.game_mode == GameMode.STORY:
            map_label = self.game.font.render("故事地图:", True, WHITE)
            self.screen.blit(map_label, map_label.get_rect(center=(sw // 2 - int(230 * scale), int(505 * scale))))
            mx = sw // 2 - int(150 * scale)
            for mi, m in enumerate(STORY_MAP_ORDER):
                unlocked = g.records.is_map_unlocked(m.name)
                mrect = pygame.Rect(mx + mi * 105, int(490 * scale), 95, 32)
                mcol = (30, 70, 35) if unlocked else (45, 45, 55)
                pygame.draw.rect(self.screen, mcol, mrect, border_radius=8)
                mname = MAP_CONFIGS[m]["name"]
                mtxt = self.game.font_small.render(mname if len(mname) <= 3 else mname[:3], True, WHITE if unlocked else (90, 90, 100))
                self.screen.blit(mtxt, mtxt.get_rect(center=mrect.center))
                if g.selected_map_for_story == m:
                    pygame.draw.rect(self.screen, GOLD, mrect, 2, border_radius=8)
                if clicked and mrect.collidepoint(clicked) and unlocked:
                    g.selected_map_for_story = m

        # 悬停/反馈信息
        if g.equip_hover:
            ht = self.game.font_small.render(g.equip_hover, True, ORANGE)
            self.screen.blit(ht, ht.get_rect(center=(sw // 2, int(82 * scale))))
            g.equip_hover = None

        # ================== 底部按钮：开始 / 返回 ==================
        start_rect = pygame.Rect(sw // 2 - int(175 * scale), int(545 * scale), int(350 * scale), int(56 * scale))
        pygame.draw.rect(self.screen, (40, 90, 40), start_rect, border_radius=12)
        pygame.draw.rect(self.screen, GREEN, start_rect, 2, border_radius=12)
        stxt = self.game.font.render("开始游戏", True, WHITE)
        self.screen.blit(stxt, stxt.get_rect(center=start_rect.center))
        back_rect = pygame.Rect(sw // 2 - int(175 * scale), int(612 * scale), int(350 * scale), int(44 * scale))
        pygame.draw.rect(self.screen, (60, 50, 50), back_rect, border_radius=10)
        pygame.draw.rect(self.screen, GRAY, back_rect, 2, border_radius=10)
        btxt = self.game.font_small.render("返回难度选择", True, LIGHT_GRAY)
        self.screen.blit(btxt, btxt.get_rect(center=back_rect.center))

        if clicked:
            if start_rect.collidepoint(clicked):
                g.equip_confirm()
            elif back_rect.collidepoint(clicked):
                g.state = GameState.DIFFICULTY_SELECT


    def _draw_text_viewer(self):
        """渲染可拾取文本查看界面"""
        from codex import PICKABLE_TEXTS
        from ui import ScrollablePanel
        
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        
        # 半透明遮罩
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        # 面板
        panel_w = int(sw * 0.7)
        panel_h = int(sh * 0.8)
        panel_x = (sw - panel_w) // 2
        panel_y = (sh - panel_h) // 2
        
        pygame.draw.rect(self.screen, (25, 25, 35), (panel_x, panel_y, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(self.screen, (180, 160, 100), (panel_x, panel_y, panel_w, panel_h), 3, border_radius=8)
        
        # 获取文本数据
        text_id = self.game.current_viewing_text
        text_data = PICKABLE_TEXTS.get(text_id, {})
        title = text_data.get("title", "未知文本")
        category = text_data.get("category", "")
        content_text = text_data.get("content", "")
        
        # 标题
        title_surf = self.game.font_large.render(title, True, (255, 230, 150))
        self.screen.blit(title_surf, (panel_x + 30, panel_y + 25))
        
        # 分类标签
        if category:
            cat_surf = self.game.font_small.render(f"[{category}]", True, (180, 160, 100))
            self.screen.blit(cat_surf, (panel_x + 30, panel_y + 65))
        
        # 使用 ScrollablePanel 显示内容
        content_x = panel_x + 30
        content_y = panel_y + 100
        content_w = panel_w - 60
        content_h = panel_h - 160
        
        if not hasattr(self.game, '_text_viewer_panel') or self.game._text_viewer_panel is None:
            self.game._text_viewer_panel = ScrollablePanel(
                content_x, content_y, content_w, content_h,
                title="", font=self.game.font_small, title_font=self.game.font_large
            )
        
        panel = self.game._text_viewer_panel
        panel.x = content_x
        panel.y = content_y
        panel.width = content_w
        panel.height = content_h
        panel.title = ""
        panel.set_content(content_text)
        
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        panel.handle_mouse(mouse_pos, mouse_pressed)
        if hasattr(self.game, 'touch_events'):
            panel.handle_touch(self.game.touch_events)
        panel.draw(self.screen)
        
        # 关闭按钮
        btn_w = int(120 * scale)
        btn_h = int(40 * scale)
        btn_x = panel_x + panel_w - btn_w - 30
        btn_y = panel_y + panel_h - btn_h - 20
        
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        
        btn_color = (80, 60, 30) if btn_rect.collidepoint(mouse_pos) else (60, 45, 20)
        pygame.draw.rect(self.screen, btn_color, btn_rect, border_radius=4)
        pygame.draw.rect(self.screen, (180, 160, 100), btn_rect, 2, border_radius=4)
        
        btn_text = self.game.font_small.render("关闭 (E)", True, (255, 230, 150))
        text_rect = btn_text.get_rect(center=btn_rect.center)
        self.screen.blit(btn_text, text_rect)
        
        # 点击关闭
        was_pressed = getattr(self.game, '_text_close_was_pressed', False)
        if mouse_pressed[0] and btn_rect.collidepoint(mouse_pos) and not was_pressed:
            self.game.state = getattr(self.game, 'prev_state', __import__('config').GameState.PLAYING)
            self.game.current_viewing_text = None
        self.game._text_close_was_pressed = mouse_pressed[0]
        
        # 提示文字
        hint = "按 E / ESC / 空格 关闭"
        hint_surf = self.game.font_small.render(hint, True, (150, 150, 150))
        self.screen.blit(hint_surf, (panel_x + 30, panel_y + panel_h - 35))


    def _draw_update(self):
        """渲染自动更新界面"""
        import updater
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height

        self.screen.fill(VOID_BLACK)

        # 标题
        title = self.game.font_title.render("自动更新", True, GREEN)
        title_rect = title.get_rect(center=(sw // 2, int(80 * scale)))
        self.screen.blit(title, title_rect)

        # 当前版本
        current_ver = getattr(self.game, 'current_version_str', '1.0.0')
        ver_text = self.game.font.render(f"当前版本: v{current_ver}", True, GRAY)
        ver_rect = ver_text.get_rect(center=(sw // 2, int(130 * scale)))
        self.screen.blit(ver_text, ver_rect)

        # 获取更新状态
        status = updater.get_update_status()
        latest_ver = status.get("latest_version")
        is_checking = status.get("checking", False)
        is_downloading = status.get("downloading", False)
        is_extracting = status.get("extracting", False)
        progress = status.get("download_progress", 0.0)
        error = status.get("error")
        changelog = status.get("changelog", "")
        update_available = status.get("update_available", False)
        downloaded = status.get("downloaded_bytes", 0)
        total = status.get("total_bytes", 0)
        speed = status.get("download_speed", 0)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        # 状态文本
        status_y = int(170 * scale)
        if error:
            status_text = self.game.font.render(f"错误: {error}", True, RED)
        elif is_checking:
            status_text = self.game.font.render("正在检查更新...", True, YELLOW)
        elif is_downloading:
            pct = int(progress * 100)
            status_text = self.game.font.render(
                f"下载中... {pct}% ({updater.format_size(downloaded)}/{updater.format_size(total)})",
                True, CYAN
            )
        elif is_extracting:
            status_text = self.game.font.render("正在应用更新...", True, YELLOW)
        elif update_available and latest_ver:
            status_text = self.game.font.render(f"发现新版本: v{latest_ver}", True, GREEN)
        elif latest_ver and not update_available:
            status_text = self.game.font.render("已是最新版本", True, GREEN)
        else:
            status_text = self.game.font.render(getattr(self.game, 'update_status_text', ''), True, GRAY)

        status_rect = status_text.get_rect(center=(sw // 2, status_y))
        self.screen.blit(status_text, status_rect)

        # 下载速度
        if is_downloading and speed > 0:
            speed_text = self.game.font_small.render(f"速度: {updater.format_speed(speed)}", True, LIGHT_GRAY)
            speed_rect = speed_text.get_rect(center=(sw // 2, status_y + 30))
            self.screen.blit(speed_text, speed_rect)

        # 进度条
        if is_downloading or (progress > 0 and progress < 1):
            bar_width = int(400 * scale)
            bar_height = int(25 * scale)
            bar_x = (sw - bar_width) // 2
            bar_y = int(220 * scale)

            pygame.draw.rect(self.screen, DARK_GRAY, (bar_x, bar_y, bar_width, bar_height), border_radius=5)
            fill_width = int(bar_width * progress)
            if fill_width > 0:
                pygame.draw.rect(self.screen, CYAN, (bar_x, bar_y, fill_width, bar_height), border_radius=5)
            pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 2, border_radius=5)
            pct_text = self.game.font_small.render(f"{int(progress * 100)}%", True, WHITE)
            pct_rect = pct_text.get_rect(center=(sw // 2, bar_y + bar_height // 2))
            self.screen.blit(pct_text, pct_rect)

        # 更新日志
        if changelog and update_available:
            log_y = int(270 * scale)
            log_title = self.game.font.render("更新日志:", True, GOLD)
            self.screen.blit(log_title, (int(100 * scale), log_y))

            log_lines = []
            for line in changelog.split('\n'):
                if not line.strip():
                    continue  # 跳过空行，避免渲染空串崩溃
                if len(line) > 60:
                    log_lines.append(line[:60])
                    log_lines.append(line[60:])
                else:
                    log_lines.append(line)

            for i, line in enumerate(log_lines[:10]):
                line_surf = self.game.font_small.render(line, True, LIGHT_GRAY)
                self.screen.blit(line_surf, (int(100 * scale), log_y + 30 + i * 22))

        # 按钮
        btn_y = 450  # BASE 坐标，Button.get_scaled_rect 内部乘 scale
        if not is_downloading and not is_extracting:
            check_btn = getattr(self.game, 'update_check_btn', None)
            if check_btn:
                check_btn.base_y = btn_y
                if check_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                    self.game.update_status_text = "正在检查更新..."
                    import threading
                    def _check():
                        result = updater.check_for_updates()
                        if result:
                            latest, url, log = result
                            current = updater.get_current_version()
                            if updater.is_newer_version(latest, current):
                                updater.UPDATE_STATE["update_available"] = True
                                self.game.update_status_text = f"发现新版本 v{latest}"
                            else:
                                self.game.update_status_text = "已是最新版本"
                        else:
                            self.game.update_status_text = updater.UPDATE_STATE.get("error", "检查失败")
                    threading.Thread(target=_check, daemon=True).start()
                check_btn.draw(self.screen, self.game.font_large, scale)

            if update_available and not is_checking:
                dl_btn = getattr(self.game, 'update_download_btn', None)
                if dl_btn:
                    dl_btn.base_y = btn_y + 70
                    if dl_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                        self.game.update_status_text = "开始下载更新..."
                        updater.perform_full_update()
                    dl_btn.draw(self.screen, self.game.font_large, scale)

        # 返回按钮
        back_btn = getattr(self.game, 'update_back_btn', None)
        if back_btn:
            back_btn.base_y = 620  # BASE 坐标
            if back_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                self.game.state = GameState.MENU
            back_btn.draw(self.screen, self.game.font_large, scale)

        esc_hint = self.game.font_small.render("按 ESC 返回菜单", True, DARK_GRAY)
        esc_rect = esc_hint.get_rect(center=(sw // 2, sh - 30))
        self.screen.blit(esc_hint, esc_rect)


    def _draw_update_notes(self):
        """渲染"更新说明"界面：版本 + ScrollablePanel 可滚动正文 + 返回
        统一采用图鉴 ScrollablePanel 实现：触控拖动 + 鼠标拖动 + 滚轮 + 自动换行 + max_scroll 边界 + 滚动条"""
        from ui import ScrollablePanel
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        self.screen.fill(VOID_BLACK)

        # 标题
        title = self.game.font_title.render("更新说明", True, GOLD)
        title_rect = title.get_rect(center=(sw // 2, int(48 * scale)))
        self.screen.blit(title, title_rect)

        # 版本
        ver = getattr(self.game, 'update_notes_version', None)
        ver_txt = f"最新版本 v{ver}" if ver else f"当前版本 v{self.game.current_version_str}"
        ver_surf = self.game.font.render(ver_txt, True, CYAN)
        ver_rect = ver_surf.get_rect(center=(sw // 2, int(90 * scale)))
        self.screen.blit(ver_surf, ver_rect)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        # 正文滚动面板（统一图鉴实现）
        panel_x = int(40 * scale)
        panel_y = int(125 * scale)
        panel_w = sw - int(80 * scale)
        panel_h = sh - panel_y - int(75 * scale)

        body = getattr(self.game, 'update_notes_text', '')
        panel = getattr(self.game, '_update_notes_panel', None)
        if panel is None:
            panel = ScrollablePanel(panel_x, panel_y, panel_w, panel_h,
                                    title="", font=self.game.font_small, title_font=self.game.font_large)
            self.game._update_notes_panel = panel
        panel.x = panel_x
        panel.y = panel_y
        panel.width = panel_w
        panel.height = panel_h

        # 按行着色：# 标题金色，-/* 列表浅灰，其余白色
        colored = []
        for ln in body.split('\n'):
            stripped = ln.lstrip()
            if stripped.startswith('#'):
                colored.append((ln, GOLD, 0, False))
            elif stripped.startswith('-') or stripped.startswith('*'):
                colored.append((ln, LIGHT_GRAY, 12, False))
            else:
                colored.append((ln, (225, 225, 225), 0, False))
        panel.set_content(colored)

        # 输入处理（鼠标拖动 + 触控拖动；滚轮在 game.update 统一处理）
        panel.handle_mouse(mouse_pos, mouse_pressed)
        if hasattr(self.game, 'touch_events'):
            panel.handle_touch(self.game.touch_events)
        panel.draw(self.screen)

        # 返回按钮（BASE 坐标，Button 内部乘 scale）
        back = getattr(self.game, 'update_back_btn', None)
        if back:
            back.base_y = 660
            if back.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                self.game.state = GameState.MENU
            back.draw(self.screen, self.game.font_large, scale)

        hint = self.game.font_small.render("滚轮 / 手指滑动滚动 · ESC 返回菜单", True, DARK_GRAY)
        self.screen.blit(hint, (int(40 * scale), sh - int(22 * scale)))

    def _draw_mod_manager(self):
        """渲染 Mod 管理界面"""
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        
        self.screen.fill(VOID_BLACK)
        
        # 标题
        title = self.game.font_title.render("Mod 管理", True, PURPLE)
        title_rect = title.get_rect(center=(sw // 2, int(60 * scale)))
        self.screen.blit(title, title_rect)
        
        # 提示
        hint = self.game.font_small.render("单击 Mod 查看详情，点击启用/禁用按钮切换状态（重启游戏生效）", True, GRAY)
        hint_rect = hint.get_rect(center=(sw // 2, int(100 * scale)))
        self.screen.blit(hint, hint_rect)
        
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        
        # Mod 列表区域
        list_x = int(40 * scale)
        list_y = int(130 * scale)
        list_w = int(sw * 0.45)
        list_h = int(sh - 200 * scale)
        
        pygame.draw.rect(self.screen, (20, 20, 30), (list_x, list_y, list_w, list_h), border_radius=6)
        pygame.draw.rect(self.screen, (80, 60, 120), (list_x, list_y, list_w, list_h), 2, border_radius=6)
        
        # 获取 mod 列表
        mods = getattr(self.game, 'mod_list_cache', [])
        if not mods:
            mods = mod_loader.get_all_available_mods()
            self.game.mod_list_cache = mods
        
        # 绘制 mod 列表
        item_height = int(60 * scale)
        scroll = getattr(self.game, 'mod_manager_scroll', 0)
        
        # 裁剪区域
        clip_rect = pygame.Rect(list_x + 5, list_y + 5, list_w - 10, list_h - 10)
        self.screen.set_clip(clip_rect)
        
        was_pressed = getattr(self.game, '_mod_list_was_pressed', False)
        
        for i, mod in enumerate(mods):
            item_y = list_y + 10 + i * (item_height + 5) - scroll
            if item_y + item_height < list_y or item_y > list_y + list_h:
                continue
            
            item_rect = pygame.Rect(list_x + 10, item_y, list_w - 20, item_height)
            
            # 选中高亮
            is_selected = (self.game.mod_selected == mod.id)
            bg_color = (50, 40, 70) if is_selected else (35, 35, 45)
            pygame.draw.rect(self.screen, bg_color, item_rect, border_radius=4)
            pygame.draw.rect(self.screen, (100, 80, 140), item_rect, 1, border_radius=4)
            
            # Mod 名称
            name_color = (200, 180, 255) if mod.enabled else (120, 120, 120)
            name_surf = self.game.font_large.render(mod.name, True, name_color)
            self.screen.blit(name_surf, (item_rect.x + 15, item_rect.y + 8))
            
            # 版本和作者
            info_text = f"v{mod.version} by {mod.author}"
            info_surf = self.game.font_small.render(info_text, True, (150, 150, 150))
            self.screen.blit(info_surf, (item_rect.x + 15, item_rect.y + 32))
            
            # 启用状态标签
            status_text = "已启用" if mod.enabled else "已禁用"
            status_color = GREEN if mod.enabled else RED
            status_surf = self.game.font_small.render(status_text, True, status_color)
            status_rect = status_surf.get_rect(right=item_rect.right - 15, centery=item_rect.centery)
            self.screen.blit(status_surf, status_rect)
            
            # 点击选中
            if mouse_pressed[0] and item_rect.collidepoint(mouse_pos) and not was_pressed:
                self.game.mod_selected = mod.id
        
        self.game._mod_list_was_pressed = mouse_pressed[0]
        self.screen.set_clip(None)
        
        # 滚动条
        total_height = len(mods) * (item_height + 5)
        if total_height > list_h - 10:
            scrollbar_h = max(30, int((list_h - 10) * (list_h - 10) / total_height))
            scrollbar_y = list_y + 5 + int(scroll / total_height * (list_h - 10 - scrollbar_h))
            pygame.draw.rect(self.screen, (100, 80, 140), (list_x + list_w - 8, scrollbar_y, 6, scrollbar_h), border_radius=3)
        
        # 详情面板
        detail_x = list_x + list_w + int(20 * scale)
        detail_y = list_y
        detail_w = sw - detail_x - int(40 * scale)
        detail_h = list_h
        
        pygame.draw.rect(self.screen, (20, 20, 30), (detail_x, detail_y, detail_w, detail_h), border_radius=6)
        pygame.draw.rect(self.screen, (80, 60, 120), (detail_x, detail_y, detail_w, detail_h), 2, border_radius=6)
        
        if self.game.mod_selected:
            selected_mod = None
            for mod in mods:
                if mod.id == self.game.mod_selected:
                    selected_mod = mod
                    break
            
            if selected_mod:
                # 名称
                name_surf = self.game.font_large.render(selected_mod.name, True, (220, 200, 255))
                self.screen.blit(name_surf, (detail_x + 20, detail_y + 20))
                
                # 版本
                ver_surf = self.game.font_small.render(f"版本: {selected_mod.version}", True, (180, 180, 180))
                self.screen.blit(ver_surf, (detail_x + 20, detail_y + 55))
                
                # 作者
                auth_surf = self.game.font_small.render(f"作者: {selected_mod.author}", True, (180, 180, 180))
                self.screen.blit(auth_surf, (detail_x + 20, detail_y + 80))
                
                # 描述（自动换行）
                desc = selected_mod.description or "（无描述）"
                desc_lines = self._wrap_text(desc, detail_w - 40, self.game.font_small)
                for j, line_text in enumerate(desc_lines[:15]):
                    desc_surf = self.game.font_small.render(line_text, True, (200, 200, 200))
                    self.screen.blit(desc_surf, (detail_x + 20, detail_y + 115 + j * 22))
                
                # 启用/禁用按钮
                btn_w = int(150 * scale)
                btn_h = int(45 * scale)
                btn_x = detail_x + detail_w - btn_w - 20
                btn_y = detail_y + detail_h - btn_h - 20
                
                btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                btn_color = (60, 100, 60) if selected_mod.enabled else (100, 60, 60)
                pygame.draw.rect(self.screen, btn_color, btn_rect, border_radius=4)
                pygame.draw.rect(self.screen, (150, 150, 150), btn_rect, 2, border_radius=4)
                
                btn_text = "禁用" if selected_mod.enabled else "启用"
                btn_surf = self.game.font_large.render(btn_text, True, WHITE)
                btn_text_rect = btn_surf.get_rect(center=btn_rect.center)
                self.screen.blit(btn_surf, btn_text_rect)
                
                # 点击切换
                btn_was_pressed = getattr(self.game, '_mod_toggle_was_pressed', False)
                if mouse_pressed[0] and btn_rect.collidepoint(mouse_pos) and not btn_was_pressed:
                    new_enabled = not selected_mod.enabled
                    mod_loader.toggle_mod(selected_mod.id, new_enabled)
                    selected_mod.enabled = new_enabled
                    self.game.logger.info(f"Mod '{selected_mod.name}' 已{'启用' if new_enabled else '禁用'}（重启生效）")
                self.game._mod_toggle_was_pressed = mouse_pressed[0]
        else:
            # 未选中提示
            hint_text = "← 从左侧选择一个 Mod 查看详情"
            hint_surf = self.game.font_large.render(hint_text, True, (120, 120, 120))
            hint_rect = hint_surf.get_rect(center=(detail_x + detail_w // 2, detail_y + detail_h // 2))
            self.screen.blit(hint_surf, hint_rect)
        
        # 返回按钮
        back_btn_w = int(150 * scale)
        back_btn_h = int(45 * scale)
        back_btn_x = sw // 2 - back_btn_w // 2
        back_btn_y = sh - back_btn_h - int(20 * scale)
        
        back_btn_rect = pygame.Rect(back_btn_x, back_btn_y, back_btn_w, back_btn_h)
        back_color = (80, 40, 40) if back_btn_rect.collidepoint(mouse_pos) else (60, 30, 30)
        pygame.draw.rect(self.screen, back_color, back_btn_rect, border_radius=4)
        pygame.draw.rect(self.screen, DARK_RED, back_btn_rect, 2, border_radius=4)
        
        back_text = self.game.font_large.render("返回菜单", True, WHITE)
        back_text_rect = back_text.get_rect(center=back_btn_rect.center)
        self.screen.blit(back_text, back_text_rect)
        
        back_was_pressed = getattr(self.game, '_mod_back_was_pressed', False)
        if mouse_pressed[0] and back_btn_rect.collidepoint(mouse_pos) and not back_was_pressed:
            self.game.state = GameState.MENU
            self.game.mod_manager_scroll = 0
            self.game.mod_selected = None
        self.game._mod_back_was_pressed = mouse_pressed[0]

    def _draw_story_archive(self):
        """剧情资料库界面"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height

        title = self.game.font_title.render("剧情资料库", True, GOLD)
        title_rect = title.get_rect(center=(sw // 2, int(60 * scale)))
        self.screen.blit(title, title_rect)

        collected = set(self.game.records.get_collected_story())
        total = sum(len(frags) for frags in STORY_FRAGMENTS.values())
        progress_text = self.game.font.render(f"已收集: {len(collected)} / {total}", True, LIGHT_GRAY)
        progress_rect = progress_text.get_rect(center=(sw // 2, int(100 * scale)))
        self.screen.blit(progress_text, progress_rect)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        # 返回按钮
        back_btn = self.game.mode_select_buttons[-1]
        # sh/scale - 60 为逻辑坐标（Button 内部会再乘 scale），避免双重缩放
        back_btn.base_y = int(sh / scale - 60)
        back_btn.text = "返回"
        if back_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.state = GameState.MENU
        back_btn.draw(self.screen, self.game.font_large, scale)

        # 按地图分组显示剧情片段
        y_offset = 140 * scale - self.game.story_archive_scroll
        list_x = int(60 * scale)
        list_width = int(sw * 0.4)

        for map_type in STORY_MAP_ORDER:
            map_config = MAP_CONFIGS[map_type]
            # 地图标题
            map_title = self.game.font.render(f"{map_config['chapter']} - {map_config['name']}", True, GOLD)
            self.screen.blit(map_title, (list_x, y_offset))
            y_offset += 35 * scale

            fragments = STORY_FRAGMENTS.get(map_type, [])
            for frag in fragments:
                is_collected = frag["id"] in collected
                color = WHITE if is_collected else DARK_GRAY
                prefix = "v " if is_collected else "? "
                text = prefix + (frag["title"] if is_collected else "未发现的资料")
                frag_text = self.game.font_small.render(text, True, color)
                frag_rect = frag_text.get_rect(x=list_x + 20, y=y_offset)
                frag_rect.width = list_width
                frag_rect.height = int(28 * scale)

                # 点击查看详情
                if frag_rect.collidepoint(mouse_pos) and is_collected:
                    pygame.draw.rect(self.screen, (40, 40, 50), frag_rect)
                    if mouse_pressed[0]:
                        self.game.story_archive_selected = frag
                self.screen.blit(frag_text, (list_x + 20, y_offset))
                y_offset += 30 * scale

            y_offset += 15 * scale

        # 右侧显示选中的剧情内容
        if self.game.story_archive_selected:
            detail_x = int(sw * 0.5)
            detail_width = int(sw * 0.45)
            pygame.draw.rect(self.screen, (25, 25, 35),
                           (detail_x, int(130 * scale), detail_width, int(sh - 200 * scale)))
            pygame.draw.rect(self.screen, GOLD,
                           (detail_x, int(130 * scale), detail_width, int(sh - 200 * scale)), 2)

            frag = self.game.story_archive_selected
            frag_title = self.game.font.render(frag["title"], True, GOLD)
            self.screen.blit(frag_title, (detail_x + 15, int(145 * scale)))

            # 内容自动换行
            content = frag["content"]
            lines = []
            for paragraph in content.split("\n"):
                words = paragraph
                current_line = ""
                for char in words:
                    test_line = current_line + char
                    test_surf = self.game.font_small.render(test_line, True, WHITE)
                    if test_surf.get_width() > detail_width - 30:
                        lines.append(current_line)
                        current_line = char
                    else:
                        current_line = test_line
                lines.append(current_line)

            content_y = int(185 * scale)
            for line in lines:
                line_surf = self.game.font_small.render(line, True, LIGHT_GRAY)
                self.screen.blit(line_surf, (detail_x + 15, content_y))
                content_y += 22 * scale

        # 返回按钮
        back_btn = self.game.story_back_btn
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if back_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.logger.info("剧情资料库返回菜单")
            self.game.state = GameState.MENU
            self.game.story_archive_scroll = 0
            self.game.story_archive_selected = None
        back_btn.draw(self.screen, self.game.font_large, scale)

    def _draw_codex(self):
        """图鉴界面"""
        from ui import Button
        from codex import MONSTER_CODEX, WEAPON_CODEX, MONSTER_CATEGORIES, WEAPON_CATEGORIES, RARITY_COLORS, THREAT_COLORS, get_monster_by_category, get_weapon_by_category

        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height

        # 标题
        title = self.game.font_title.render("图鉴", True, GOLD)
        title_rect = title.get_rect(center=(sw // 2, int(40 * scale)))
        self.screen.blit(title, title_rect)

        # 标签页按钮
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        for i, btn in enumerate(self.game.codex_tab_buttons):
            if self.game.codex_tab == "monster" and i == 0:
                btn.color = CRIMSON
            elif self.game.codex_tab == "weapon" and i == 1:
                btn.color = CYAN
            elif self.game.codex_tab == "world" and i == 2:
                btn.color = PURPLE
            else:
                btn.color = DARK_GRAY
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                if i == 0:
                    self.game.codex_tab = "monster"
                    self.game.codex_category = "全部"
                    self.game.codex_scroll = 0
                    self.game.codex_selected = None
                elif i == 1:
                    self.game.codex_tab = "weapon"
                    self.game.codex_category = "全部"
                    self.game.codex_scroll = 0
                    self.game.codex_selected = None
                else:
                    self.game.codex_tab = "world"
                    self.game.codex_world_selected = "origin"
                    self.game.codex_scroll = 0
            btn.draw(self.screen, self.game.font_large, scale)
        
        # 世界观标签页
        if self.game.codex_tab == "world":
            self._draw_world_lore(mouse_pos, mouse_pressed)
            return

        # 分类按钮
        categories = MONSTER_CATEGORIES if self.game.codex_tab == "monster" else WEAPON_CATEGORIES
        cat_y = int(140 * scale)
        cat_x_start = int(20 * scale)
        cat_btn_width = int(80 * scale)
        cat_btn_height = int(35 * scale)
        cat_spacing = int(10 * scale)

        # 检测鼠标点击（使用简单的矩形碰撞检测）
        mouse_clicked = False
        if hasattr(self.game, '_codex_mouse_was_pressed') and self.game._codex_mouse_was_pressed and not mouse_pressed[0]:
            mouse_clicked = True
        self.game._codex_mouse_was_pressed = mouse_pressed[0]

        for i, cat in enumerate(categories):
            cat_x = cat_x_start + i * (cat_btn_width + cat_spacing)
            if cat_x + cat_btn_width > sw - 20:
                break
            cat_color = CYAN if self.game.codex_category == cat else DARK_GRAY
            cat_rect = pygame.Rect(cat_x, cat_y, cat_btn_width, cat_btn_height)
            
            # 绘制按钮背景
            pygame.draw.rect(self.screen, cat_color, cat_rect)
            pygame.draw.rect(self.screen, WHITE, cat_rect, 2)
            
            # 绘制按钮文字
            cat_text = self.game.font_small.render(cat, True, WHITE)
            cat_text_rect = cat_text.get_rect(center=cat_rect.center)
            self.screen.blit(cat_text, cat_text_rect)
            
            # 检测点击
            if mouse_clicked and cat_rect.collidepoint(mouse_pos):
                self.game.codex_category = cat
                self.game.codex_scroll = 0
                self.game.codex_selected = None
                self.game.logger.info(f"图鉴切换分类: {cat}")

        # 获取当前分类的条目
        if self.game.codex_tab == "monster":
            entries = get_monster_by_category(self.game.codex_category)
            codex_data = MONSTER_CODEX
        else:
            entries = get_weapon_by_category(self.game.codex_category)
            codex_data = WEAPON_CODEX

        # 左侧条目列表
        list_x = int(20 * scale)
        list_y = int(190 * scale)
        list_width = int(280 * scale)
        list_height = int(sh - 280 * scale)
        item_height = int(50 * scale)

        # 绘制列表背景
        pygame.draw.rect(self.screen, CHARCOAL, (list_x, list_y, list_width, list_height))
        pygame.draw.rect(self.screen, DARK_GRAY, (list_x, list_y, list_width, list_height), 2)

        # 拖拽滚动（支持鼠标和触摸）
        list_rect = pygame.Rect(list_x, list_y, list_width, list_height)
        is_dragging = getattr(self.game, '_codex_dragging', False)
        drag_start_y = getattr(self.game, '_codex_drag_start_y', 0)
        drag_start_scroll = getattr(self.game, '_codex_drag_start_scroll', 0)
        max_scroll = max(0, len(entries) * item_height - list_height)
        
        # 检测触摸事件（touch_events 是 dict 列表）
        touch_in_list = False
        for te in self.game.touch_events:
            te_type = te.get("type", "")
            te_pos = te.get("pos", (0, 0))
            if te_type == "down" and list_rect.collidepoint(te_pos[0], te_pos[1]):
                touch_in_list = True
                self.game._codex_dragging = True
                self.game._codex_drag_start_y = te_pos[1]
                self.game._codex_drag_start_scroll = self.game.codex_scroll
            elif te_type == "move" and is_dragging:
                current_y = te_pos[1]
                delta = drag_start_y - current_y
                self.game.codex_scroll = max(0, min(max_scroll, drag_start_scroll + delta))
            elif te_type == "up":
                self.game._codex_dragging = False
        
        # 鼠标拖拽
        if list_rect.collidepoint(mouse_pos):
            if mouse_pressed[0] and not is_dragging and not getattr(self.game, '_codex_mouse_was_pressed', False):
                self.game._codex_dragging = True
                self.game._codex_drag_start_y = mouse_pos[1]
                self.game._codex_drag_start_scroll = self.game.codex_scroll
            elif mouse_pressed[0] and is_dragging:
                delta = drag_start_y - mouse_pos[1]
                self.game.codex_scroll = max(0, min(max_scroll, drag_start_scroll + delta))
            elif not mouse_pressed[0]:
                self.game._codex_dragging = False
        
        # 滚动边界限制
        self.game.codex_scroll = min(self.game.codex_scroll, max_scroll)

        # 绘制条目
        for i, entry_key in enumerate(entries):
            item_y = list_y + i * item_height - self.game.codex_scroll
            if item_y < list_y or item_y + item_height > list_y + list_height:
                continue

            entry = codex_data.get(entry_key, {})
            name = entry.get("name", entry_key)
            
            # 检查解锁状态
            if self.game.codex_tab == "monster":
                is_unlocked = codex_unlock_manager.is_monster_unlocked(entry_key)
            else:
                is_unlocked = codex_unlock_manager.is_weapon_unlocked(entry_key)

            # 选中高亮
            if self.game.codex_selected == entry_key:
                pygame.draw.rect(self.screen, DARK_BLUE, (list_x + 2, item_y, list_width - 4, item_height - 2))
            else:
                pygame.draw.rect(self.screen, (40, 40, 40), (list_x + 2, item_y, list_width - 4, item_height - 2))

            # 名称（未解锁显示???）
            display_name = name if is_unlocked else "???"
            name_color = WHITE if is_unlocked else GRAY
            name_text = self.game.font_small.render(display_name, True, name_color)
            self.screen.blit(name_text, (list_x + 15, item_y + 10))
            
            # 锁定图标
            if not is_unlocked:
                lock_text = self.game.font_small.render("🔒", True, GRAY)
                self.screen.blit(lock_text, (list_x + list_width - 30, item_y + 12))

            # 分类/稀有度（未解锁显示未知）
            if is_unlocked:
                if self.game.codex_tab == "monster":
                    threat = entry.get("threat", "未知")
                    threat_color = THREAT_COLORS.get(threat, GRAY)
                    cat_text = self.game.font_small.render(f"威胁: {threat}", True, threat_color)
                else:
                    rarity = entry.get("rarity", "普通")
                    rarity_color = RARITY_COLORS.get(rarity, GRAY)
                    cat_text = self.game.font_small.render(f"稀有度: {rarity}", True, rarity_color)
            else:
                cat_text = self.game.font_small.render("未解锁", True, GRAY)
            self.screen.blit(cat_text, (list_x + 15, item_y + 28))

            # 点击选择
            item_rect = pygame.Rect(list_x, item_y, list_width, item_height)
            if item_rect.collidepoint(mouse_pos) and mouse_pressed[0]:
                self.game.codex_selected = entry_key

        # 滚动条
        if max_scroll > 0:
            scrollbar_height = int(list_height * (list_height / (len(entries) * item_height)))
            scrollbar_y = list_y + int(self.game.codex_scroll / max_scroll * (list_height - scrollbar_height))
            pygame.draw.rect(self.screen, GRAY, (list_x + list_width - 8, scrollbar_y, 6, scrollbar_height))

        # 右侧详情面板
        detail_x = list_x + list_width + int(20 * scale)
        detail_y = list_y
        detail_width = sw - detail_x - int(20 * scale)
        detail_height = list_height

        pygame.draw.rect(self.screen, CHARCOAL, (detail_x, detail_y, detail_width, detail_height))
        pygame.draw.rect(self.screen, DARK_GRAY, (detail_x, detail_y, detail_width, detail_height), 2)

        if self.game.codex_selected:
            entry = codex_data.get(self.game.codex_selected, {})
            # 检查解锁状态
            if self.game.codex_tab == "monster":
                is_unlocked = codex_unlock_manager.is_monster_unlocked(self.game.codex_selected)
            else:
                is_unlocked = codex_unlock_manager.is_weapon_unlocked(self.game.codex_selected)
            
            if is_unlocked:
                name = entry.get("name", "未知")
                description = entry.get("description", "")
                stats = entry.get("stats", {})
                lore = entry.get("lore", "")
            else:
                name = "???"
                description = "尚未解锁。在游戏中遇到此怪物或获得此武器后即可解锁图鉴详情。"
                stats = {}
                lore = ""

            # 名称
            name_text = self.game.font_large.render(name, True, GOLD)
            self.screen.blit(name_text, (detail_x + 20, detail_y + 20))

            # 图片预览（右上角，仅已解锁条目显示真实样子）
            if is_unlocked:
                self._draw_codex_item_preview(
                    self.game.codex_selected, self.game.codex_tab,
                    detail_x + detail_width - int(150 * scale), detail_y + int(18 * scale),
                    int(130 * scale), int(130 * scale))

            # 描述
            desc_y = detail_y + 70
            desc_lines = self._wrap_text(description, detail_width - 40, self.game.font_small)
            for line in desc_lines[:3]:
                desc_text = self.game.font_small.render(line, True, LIGHT_GRAY)
                self.screen.blit(desc_text, (detail_x + 20, desc_y))
                desc_y += 25

            # 属性
            stats_y = desc_y + 20
            stats_title = self.game.font_small.render("属性", True, CYAN)
            self.screen.blit(stats_title, (detail_x + 20, stats_y))
            stats_y += 30

            for stat_name, stat_value in stats.items():
                stat_text = self.game.font_small.render(f"  {stat_name}: {stat_value}", True, WHITE)
                self.screen.blit(stat_text, (detail_x + 20, stats_y))
                stats_y += 25

            # 弱点/稀有度
            if self.game.codex_tab == "monster":
                weakness = entry.get("weakness", "未知")
                weakness_text = self.game.font_small.render(f"弱点: {weakness}", True, YELLOW)
                self.screen.blit(weakness_text, (detail_x + 20, stats_y + 10))
            else:
                rarity = entry.get("rarity", "普通")
                rarity_color = RARITY_COLORS.get(rarity, GRAY)
                rarity_text = self.game.font_small.render(f"稀有度: {rarity}", True, rarity_color)
                self.screen.blit(rarity_text, (detail_x + 20, stats_y + 10))

            # 背景故事
            lore_y = detail_y + detail_height - 150
            lore_title = self.game.font_small.render("背景故事", True, AMBER)
            self.screen.blit(lore_title, (detail_x + 20, lore_y))
            lore_y += 30

            lore_lines = self._wrap_text(lore, detail_width - 40, self.game.font_small)
            for line in lore_lines[:5]:
                lore_text = self.game.font_small.render(line, True, LIGHT_GRAY)
                self.screen.blit(lore_text, (detail_x + 20, lore_y))
                lore_y += 25
        else:
            # 未选择时的提示
            hint = self.game.font_large.render("选择左侧条目查看详情", True, DARK_GRAY)
            hint_rect = hint.get_rect(center=(detail_x + detail_width // 2, detail_y + detail_height // 2))
            self.screen.blit(hint, hint_rect)

        # 返回按钮
        back_btn = self.game.codex_back_btn
        if back_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.logger.info("图鉴返回菜单")
            self.game.state = GameState.MENU
            self.game.codex_scroll = 0
            self.game.codex_selected = None
        back_btn.draw(self.screen, self.game.font_large, scale)

    def _draw_codex_item_preview(self, entry_key, tab, x, y, w, h):
        """图鉴条目图片预览：怪物用真实游戏贴图，武器程序化绘制"""
        try:
            from codex import THREAT_COLORS, RARITY_COLORS, MONSTER_CODEX
            pygame.draw.rect(self.screen, (30, 30, 42), (x, y, w, h))
            pygame.draw.rect(self.screen, (90, 90, 120), (x, y, w, h), 2)
            if tab == "monster":
                assets = self.game.assets
                img_key = entry_key.lower()
                if assets is not None and hasattr(assets, 'has_image') and assets.has_image(img_key):
                    img = assets.get_image(img_key, w - 4, h - 4)
                    self.screen.blit(img, (x + 2, y + 2))
                else:
                    # 程序化怪物剪影（按威胁等级配色）
                    entry = MONSTER_CODEX.get(entry_key, {})
                    col = THREAT_COLORS.get(entry.get('threat', ''), (150, 60, 60))
                    cx, cy = x + w // 2, y + h // 2
                    r = min(w, h) // 2 - 6
                    pygame.draw.circle(self.screen, (30, 30, 40), (cx, cy), r + 6)
                    pygame.draw.circle(self.screen, col, (cx, cy), r)
                    pygame.draw.circle(self.screen, (255, 45, 45), (cx - 9, cy - 4), 5)
                    pygame.draw.circle(self.screen, (255, 45, 45), (cx + 9, cy - 4), 5)
            else:
                self._draw_codex_weapon_preview(entry_key, x, y, w, h)
        except Exception:
            pass

    def _draw_codex_weapon_preview(self, entry_key, x, y, w, h):
        """图鉴武器预览：用局内同一套专属程序化贴图，缩放显示"""
        try:
            from config import WeaponType
            from weapons import render_weapon_icon
            wt = WeaponType[entry_key.upper()]
            icon = render_weapon_icon(wt)
            icon = pygame.transform.scale(icon, (w - 4, h - 4))
            self.screen.blit(icon, (x + 2, y + 2))
        except Exception:
            self._paint_weapon_icon(entry_key, x, y, w, h)

    def _paint_weapon_icon(self, entry_key, x, y, w, h):
        """程序化绘制武器图标（按武器类型画剪影）"""
        cx, cy = x + w // 2, y + h // 2
        key_u = entry_key.upper()
        body = (75, 75, 88)
        if key_u in ("KNIFE", "BAT", "CHAINSAW", "SCYTHE"):
            if key_u == "KNIFE":
                pygame.draw.polygon(self.screen, (200, 205, 215),
                                    [(cx - 6, cy - 6), (cx + 26, cy - 6), (cx + 32, cy + 2), (cx - 10, cy + 2)])
                pygame.draw.rect(self.screen, (130, 95, 60), (cx - 26, cy - 4, 24, 10))
            elif key_u == "SCYTHE":
                pygame.draw.arc(self.screen, (220, 225, 235), (cx - 30, cy - 26, 66, 56), 0, 3.3, 9)
                pygame.draw.line(self.screen, (145, 115, 80), (cx + 28, cy + 2), (cx - 26, cy + 42), 8)
                pygame.draw.circle(self.screen, (160, 130, 90), (cx + 28, cy + 2), 8)
            elif key_u == "CHAINSAW":
                pygame.draw.rect(self.screen, (120, 120, 132), (cx - 30, cy - 4, 60, 14))
                for i in range(-26, 30, 9):
                    pygame.draw.circle(self.screen, (90, 90, 100), (cx + i, cy + 3), 3)
                pygame.draw.rect(self.screen, (150, 80, 60), (cx - 4, cy + 10, 24, 16))
            else:
                pygame.draw.line(self.screen, (150, 120, 70), (cx - 30, cy + 2), (cx + 30, cy + 2), 10)
                pygame.draw.rect(self.screen, (120, 90, 60), (cx - 6, cy + 2, 22, 12))
        else:
            # 枪械：枪身+枪管+弹匣+瞄准
            pygame.draw.rect(self.screen, body, (cx - 20, cy - 6, 54, 14))
            pygame.draw.rect(self.screen, body, (cx + 28, cy - 3, 20, 8))
            pygame.draw.rect(self.screen, (70, 70, 80), (cx - 16, cy + 8, 24, 14))
            pygame.draw.rect(self.screen, (200, 60, 60), (cx - 30, cy - 3, 7, 7))

    def _draw_world_lore(self, mouse_pos, mouse_pressed):
        """渲染世界观图鉴"""
        from codex import WORLD_LORE
        from ui import ScrollablePanel
        
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        
        # 左侧条目列表
        list_x = int(20 * scale)
        list_y = int(140 * scale)
        list_w = int(200 * scale)
        list_h = int(sh - 200 * scale)
        
        # 列表背景
        pygame.draw.rect(self.screen, (30, 30, 45), (list_x, list_y, list_w, list_h))
        pygame.draw.rect(self.screen, (100, 100, 140), (list_x, list_y, list_w, list_h), 2)
        
        # 世界观条目（支持滚动）
        lore_items = list(WORLD_LORE.items())
        item_height = int(40 * scale)
        total_list_height = len(lore_items) * (item_height + 5) + 10
        max_scroll = max(0, total_list_height - list_h + 10)
        
        # 初始化滚动位置
        if not hasattr(self.game, 'codex_world_list_scroll'):
            self.game.codex_world_list_scroll = 0
        
        # 列表区域的鼠标滚轮处理（通过全局滚轮事件间接处理，这里用拖动）
        list_rect = pygame.Rect(list_x, list_y, list_w, list_h)
        
        # 触控/鼠标拖动列表滚动
        if not hasattr(self.game, '_world_list_dragging'):
            self.game._world_list_dragging = False
            self.game._world_list_drag_start_y = 0
            self.game._world_list_drag_start_scroll = 0
        
        if list_rect.collidepoint(mouse_pos):
            if mouse_pressed[0]:
                if not getattr(self.game, '_world_list_pressed', False):
                    # 刚按下，记录起始位置，暂不判定为拖动
                    self.game._world_list_pressed = True
                    self.game._world_list_drag_start_y = mouse_pos[1]
                    self.game._world_list_drag_start_scroll = self.game.codex_world_list_scroll
                    self.game._world_list_dragging = False
                else:
                    dy = mouse_pos[1] - self.game._world_list_drag_start_y
                    if abs(dy) > 5:  # 移动超过5像素才判定为拖动
                        self.game._world_list_dragging = True
                    if self.game._world_list_dragging:
                        self.game.codex_world_list_scroll = max(0, min(max_scroll, self.game._world_list_drag_start_scroll - dy))
            else:
                self.game._world_list_pressed = False
                self.game._world_list_dragging = False
        else:
            if not mouse_pressed[0]:
                self.game._world_list_pressed = False
                self.game._world_list_dragging = False

        # 触控拖动列表滚动 + 点击选择（统一图鉴实现，修复触控需点好几下的问题）
        for te in self.game.touch_events:
            te_type = te.get("type", "")
            te_pos = te.get("pos", (0, 0))
            te_id = te.get("id", 0)
            if te_type == "down" and list_rect.collidepoint(te_pos[0], te_pos[1]):
                self.game._world_touch_dragging = True
                self.game._world_touch_drag_start_y = te_pos[1]
                self.game._world_touch_drag_start_scroll = self.game.codex_world_list_scroll
                self.game._world_touch_id = te_id
                self.game._world_touch_moved = False
            elif te_type == "move" and getattr(self.game, '_world_touch_dragging', False) and te_id == getattr(self.game, '_world_touch_id', -1):
                delta = te_pos[1] - self.game._world_touch_drag_start_y
                if abs(delta) > 5:
                    self.game._world_touch_moved = True
                self.game.codex_world_list_scroll = max(0, min(max_scroll, self.game._world_touch_drag_start_scroll - delta))
            elif te_type == "up" and te_id == getattr(self.game, '_world_touch_id', -1):
                self.game._world_touch_dragging = False
                # 非拖动的抬手 = 点击选择
                if not getattr(self.game, '_world_touch_moved', False) and list_rect.collidepoint(te_pos[0], te_pos[1]):
                    for _i, (_key, _data) in enumerate(lore_items):
                        _item_y = list_y + 10 + _i * (item_height + 5) - self.game.codex_world_list_scroll
                        _item_rect = pygame.Rect(list_x + 10, _item_y, list_w - 20, item_height)
                        if _item_rect.collidepoint(te_pos[0], te_pos[1]):
                            self.game.codex_world_selected = _key
                            self.game.codex_scroll = 0
                            if hasattr(self.game, '_world_scroll_panel') and self.game._world_scroll_panel:
                                self.game._world_scroll_panel.scroll_y = 0
                            break

        # 绘制条目（使用裁剪区域）
        clip_rect = pygame.Rect(list_x + 5, list_y + 5, list_w - 10, list_h - 10)
        self.screen.set_clip(clip_rect)
        
        was_pressed = getattr(self.game, '_world_btn_was_pressed', False)
        for i, (key, data) in enumerate(lore_items):
            item_y = list_y + 10 + i * (item_height + 5) - self.game.codex_world_list_scroll
            if item_y + item_height < list_y or item_y > list_y + list_h:
                continue
            is_selected = self.game.codex_world_selected == key
            bg_color = PURPLE if is_selected else (50, 50, 70)
            pygame.draw.rect(self.screen, bg_color, (list_x + 10, item_y, list_w - 20, item_height))
            pygame.draw.rect(self.screen, WHITE, (list_x + 10, item_y, list_w - 20, item_height), 1)
            
            title_text = self.game.font_small.render(data["title"], True, WHITE)
            self.screen.blit(title_text, (list_x + 20, item_y + 10))
            
            # 点击检测（按下沿触发，且不是拖动）
            item_rect = pygame.Rect(list_x + 10, item_y, list_w - 20, item_height)
            if mouse_pressed[0] and item_rect.collidepoint(mouse_pos) and not was_pressed and not self.game._world_list_dragging:
                self.game.codex_world_selected = key
                self.game.codex_scroll = 0
                if hasattr(self.game, '_world_scroll_panel') and self.game._world_scroll_panel:
                    self.game._world_scroll_panel.scroll_y = 0
        self.game._world_btn_was_pressed = mouse_pressed[0]
        
        self.screen.set_clip(None)
        
        # 滚动条
        if max_scroll > 0:
            scrollbar_h = max(20, int(list_h * (list_h / total_list_height)))
            scrollbar_y = list_y + int((self.game.codex_world_list_scroll / max_scroll) * (list_h - scrollbar_h))
            pygame.draw.rect(self.screen, (150, 150, 180), (list_x + list_w - 8, scrollbar_y, 6, scrollbar_h), border_radius=3)
        
        # 右侧详情面板（使用 ScrollablePanel）
        detail_x = list_x + list_w + int(20 * scale)
        detail_y = list_y
        detail_w = sw - detail_x - int(20 * scale)
        detail_h = list_h
        
        selected_data = WORLD_LORE.get(self.game.codex_world_selected, {})
        title = selected_data.get("title", "")
        content_text = selected_data.get("content", "")
        
        # 创建或更新 ScrollablePanel
        if not hasattr(self.game, '_world_scroll_panel') or self.game._world_scroll_panel is None:
            self.game._world_scroll_panel = ScrollablePanel(
                detail_x, detail_y, detail_w, detail_h,
                title=title, font=self.game.font_small, title_font=self.game.font_large
            )
        
        panel = self.game._world_scroll_panel
        panel.x = detail_x
        panel.y = detail_y
        panel.width = detail_w
        panel.height = detail_h
        panel.title = title
        panel.set_content(content_text)
        
        # 处理输入
        panel.handle_mouse(mouse_pos, mouse_pressed)
        if hasattr(self.game, 'touch_events'):
            panel.handle_touch(self.game.touch_events)
        
        # 绘制
        panel.draw(self.screen)
        
        # 返回按钮
        back_btn = self.game.codex_back_btn
        if back_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.logger.info("图鉴返回菜单")
            self.game.state = GameState.MENU
            self.game.codex_scroll = 0
            self.game.codex_selected = None
        back_btn.draw(self.screen, self.game.font_large, scale)


    def _wrap_text(self, text, max_width, font):
        """简单的文本换行（按字符分割，支持中文）"""
        lines = []
        current_line = ""
        for char in text:
            if char == '\n':
                lines.append(current_line)
                current_line = ""
                continue
            test_line = current_line + char
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        return lines

    def _draw_settings(self):
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width

        title = self.game.font_title.render("设置", True, WHITE)
        title_rect = title.get_rect(center=(sw // 2, int(100 * scale)))
        self.screen.blit(title, title_rect)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        for i, btn in enumerate(self.game.settings_buttons):
            btn.base_y = (140 + i * 50)
            if i == 0:
                btn.text = f"音效音量: {int(self.game.config.sound_volume * 100)}%"
            elif i == 1:
                btn.text = f"音乐音量: {int(self.game.config.music_volume * 100)}%"
            elif i == 2:
                qn = {"performance": "性能", "balanced": "均衡", "quality": "质量"}
                btn.text = f"画质: {qn.get(self.game.config.graphics_quality, '均衡')}"
            elif i == 3:
                btn.text = f"外部图片: {'开' if self.game.config.use_external_assets else '关'}"
            elif i == 4:
                btn.text = f"Buff特效: {'开' if self.game.config.render_buff_effects else '关'}"
            elif i == 5:
                btn.text = f"伤害数字: {'开' if self.game.config.show_damage_numbers else '关'}"
            elif i == 6:
                btn.text = f"屏幕震动: {'开' if self.game.config.screen_shake else '关'}"
            elif i == 7:
                btn.text = f"控制: {'触控' if self.game.config.control_mode == ControlMode.TOUCH else '键控'}"
            elif i == 8:
                btn.text = f"日志记录: {'开' if self.game.config.enable_logging else '关'}"

            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                self.game.logger.info(f"设置按钮 '{btn.text}' 被点击")
                if i == 0:
                    vols = [0.0, 0.25, 0.5, 0.75, 1.0]
                    cur = self.game.config.sound_volume
                    idx = min(range(len(vols)), key=lambda x: abs(vols[x] - cur))
                    self.game.config.sound_volume = vols[(idx + 1) % len(vols)]
                    self.game.assets.set_sound_volume(self.game.config.sound_volume)
                elif i == 1:
                    vols = [0.0, 0.25, 0.5, 0.75, 1.0]
                    cur = self.game.config.music_volume
                    idx = min(range(len(vols)), key=lambda x: abs(vols[x] - cur))
                    self.game.config.music_volume = vols[(idx + 1) % len(vols)]
                    self.game.assets.set_music_volume(self.game.config.music_volume)
                elif i == 2:
                    qs = ["performance", "balanced", "quality"]
                    cur = self.game.config.graphics_quality
                    idx = qs.index(cur) if cur in qs else 1
                    self.game.config.graphics_quality = qs[(idx + 1) % len(qs)]
                    # 画质变化时清除缓存
                    for attr in ['_trauma_cache_key', '_blood_template_cache', '_buff_edge_cache',
                                 '_heat_cache', '_frost_cache', '_hb_cache']:
                        if hasattr(self, attr):
                            delattr(self, attr)
                elif i == 3:
                    self.game.config.use_external_assets = not self.game.config.use_external_assets
                elif i == 4:
                    self.game.config.render_buff_effects = not self.game.config.render_buff_effects
                elif i == 5:
                    self.game.config.show_damage_numbers = not self.game.config.show_damage_numbers
                elif i == 6:
                    self.game.config.screen_shake = not self.game.config.screen_shake
                    self.game.camera.shake_enabled = self.game.config.screen_shake
                elif i == 7:
                    self.game.config.control_mode = ControlMode.TOUCH if self.game.config.control_mode == ControlMode.KEYBOARD else ControlMode.KEYBOARD
                elif i == 8:
                    self.game.config.enable_logging = not self.game.config.enable_logging
                    self.game.logger.set_enabled(self.game.config.enable_logging)
                    if self.game.config.enable_logging:
                        self.game.logger.info("日志记录已开启")
                elif i == 9:
                    # 进入HUD自定义布局编辑（单机→单机布局；双人→默认编辑P1）
                    self.game.state = GameState.HUD_EDIT
                    self.game.hud_edit_dirty = False
                    self.game.hud_edit_drag = None
                    self.game.hud_edit_target = "P1" if self.game.is_multiplayer_active() else "单机"
                    self._hud_edit_load_target(self.game.hud_edit_target)
                elif i == 10:
                    self.game.config.save()
                    if getattr(self.game, 'settings_from_pause', False):
                        self.game.settings_from_pause = False
                        self.game.state = GameState.PAUSED
                    else:
                        self.game.state = GameState.MENU

            btn.draw(self.screen, self.game.font_large, scale)

    def _draw_hud_edit(self):
        """HUD触控按钮自定义布局编辑界面：拖动按钮调整位置（双人模式支持 P1/P2 独立编辑）"""
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        # 半透明暗底
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 200))
        self.screen.blit(overlay, (0, 0))

        title = self.game.font_title.render("HUD按钮布局", True, WHITE)
        title_rect = title.get_rect(center=(sw // 2, int(58 * scale)))
        self.screen.blit(title, title_rect)
        tip = self.game.font.render("拖动按钮调整位置（触控/鼠标），松手放下", True, (200, 200, 220))
        self.screen.blit(tip, tip.get_rect(center=(sw // 2, int(100 * scale))))

        # 布局目标切换：单机 / P1 / P2（三套独立布局，互不覆盖）
        mp_active = self.game.is_multiplayer_active()
        target = getattr(self.game, "hud_edit_target", "单机")
        if not mp_active:
            target = "单机"
        tabs = [("单机", "单机布局")]
        if mp_active:
            tabs = [("单机", "单机布局"), ("P1", "双人P1"), ("P2", "双人P2")]
        tab_rects = []
        tab_w = int(100 * scale)
        tab_h = int(34 * scale)
        total_w = len(tabs) * tab_w + (len(tabs) - 1) * int(8 * scale)
        x0 = sw // 2 - total_w // 2
        mouse_pos0 = pygame.mouse.get_pos()
        mp0 = pygame.mouse.get_pressed()
        for i, (tid, tlabel) in enumerate(tabs):
            tr = pygame.Rect(x0 + i * (tab_w + int(8 * scale)), int(6 * scale), tab_w, tab_h)
            tab_rects.append((tid, tr))
            for e in (self.game.touch_events or []):
                if e["type"] == "down" and tr.collidepoint(e["pos"]) and self.game.hud_edit_target != tid:
                    self.game.hud_edit_target = tid
                    self.game.hud_edit_drag = None
                    self._hud_edit_load_target(tid)
            if mp0[0] and tr.collidepoint(mouse_pos0) and self.game.hud_edit_target != tid:
                self.game.hud_edit_target = tid
                self.game.hud_edit_drag = None
                self._hud_edit_load_target(tid)
            is_on = (tid == target)
            pygame.draw.rect(self.screen, (70, 140, 220) if is_on else (50, 50, 70), tr, border_radius=8)
            pygame.draw.rect(self.screen, (255, 255, 255), tr, 2, border_radius=8)
            lbl = self.game.font_small.render(tlabel, True, WHITE)
            self.screen.blit(lbl, lbl.get_rect(center=tr.center))

        # 可编辑控件元数据：(键名, 中文名, 控件, 半径, 标签方位) —— shoot 排在 aim 前，重叠时优先选中可操作按钮
        if target == "P2" and self.game.p2_controls:
            c2 = self.game.p2_controls
            items = [
                ("joystick", "移动摇杆", c2["joystick"], 70, "above"),
                ("shoot", "射击", c2["shoot"], 62, "above"),
                ("aim", "瞄准", c2["aim"], 62, "below"),
                ("pause", "暂停", c2["pause"], 38, "above"),
                ("sprint", "疾跑", c2["sprint"], 40, "above"),
                ("skill_selector", "技能切换", c2["skill_selector"], 42, "above"),
                ("skill_caster", "技能释放", c2["skill_caster"], 52, "above"),
                ("throwable_switch", "投掷切换", c2["throwable_switch"], 42, "above"),
                ("throwable_caster", "投掷释放", c2["throwable_caster"], 48, "above"),
            ]
        else:
            items = [
                ("joystick", "移动摇杆", self.game.joystick, 70, "above"),
                ("shoot", "射击", self.game.touch_buttons.get("shoot"), 62, "above"),
                ("aim", "瞄准", self.game.aim_button, 62, "below"),
                ("pause", "暂停", self.game.touch_buttons.get("pause"), 38, "above"),
                ("sprint", "疾跑", self.game.touch_buttons.get("sprint"), 40, "above"),
                ("skill_selector", "技能切换", self.game.skill_selector, 42, "above"),
                ("skill_caster", "技能释放", self.game.skill_caster, 52, "above"),
                ("throwable_switch", "投掷切换", self.game.throwable_switch_btn, 42, "above"),
                ("throwable_caster", "投掷释放", self.game.throwable_caster, 48, "above"),
            ]
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        touches = self.game.touch_events or []

        # 拖拽状态：game.hud_edit_drag = {"key":..., "touch_id":...}
        drag = getattr(self.game, "hud_edit_drag", None)

        def _rect_for(ctrl, radius):
            r = int(radius * scale)
            bx = int(ctrl.base_x * scale)
            by = int(ctrl.base_y * scale)
            return pygame.Rect(bx - r - 12, by - r - 12, (r + 12) * 2, (r + 12) * 2), (bx, by), r

        def _find_ctrl(key):
            for k, label, ctrl, radius, side in items:
                if k == key:
                    return ctrl
            return None

        # 1) 触控事件处理（down 选中 / move 跟随 / up 放下）
        for e in touches:
            if e["type"] == "down":
                for key, label, ctrl, radius, side in items:
                    if ctrl is None:
                        continue
                    rect, (bx, by), r = _rect_for(ctrl, radius)
                    if rect.collidepoint(e["pos"]):
                        self.game.hud_edit_drag = {"key": key, "touch_id": e.get("id")}
                        break
            elif e["type"] == "move":
                _drag = getattr(self.game, "hud_edit_drag", None)
                if _drag and (_drag.get("touch_id") is None or _drag["touch_id"] == e.get("id")):
                    ctrl = _find_ctrl(_drag["key"])
                    if ctrl is not None:
                        ctrl.base_x = max(0, min(BASE_WIDTH, int(e["pos"][0] / scale)))
                        ctrl.base_y = max(0, min(BASE_HEIGHT, int(e["pos"][1] / scale)))
                        self.game.hud_edit_dirty = True
            elif e["type"] == "up":
                _drag = getattr(self.game, "hud_edit_drag", None)
                if _drag and (_drag.get("touch_id") is None or _drag["touch_id"] == e.get("id")):
                    self.game.hud_edit_drag = None

        # 2) 鼠标拖动
        drag = getattr(self.game, "hud_edit_drag", None)
        if drag and drag.get("touch_id") is None:
            if mouse_pressed[0]:
                ctrl = _find_ctrl(drag["key"])
                if ctrl is not None:
                    ctrl.base_x = max(0, min(BASE_WIDTH, int(mouse_pos[0] / scale)))
                    ctrl.base_y = max(0, min(BASE_HEIGHT, int(mouse_pos[1] / scale)))
                    self.game.hud_edit_dirty = True
            else:
                self.game.hud_edit_drag = None
        elif not drag and mouse_pressed[0]:
            for key, label, ctrl, radius, side in items:
                if ctrl is None:
                    continue
                rect, (bx, by), r = _rect_for(ctrl, radius)
                if rect.collidepoint(mouse_pos):
                    self.game.hud_edit_drag = {"key": key, "touch_id": None}
                    break

        # 3) 绘制控件（半透明框 + 名称）
        for key, label, ctrl, radius, side in items:
            if ctrl is None:
                continue
            rect, (bx, by), r = _rect_for(ctrl, radius)
            is_drag = bool(drag and drag["key"] == key)
            col = (180, 60, 220) if is_drag else (70, 140, 220)
            cell = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.circle(cell, (*col, 90), (rect.w // 2, rect.h // 2), r + 6, 3)
            pygame.draw.circle(cell, (255, 255, 255, 120), (rect.w // 2, rect.h // 2), r - 6, 1)
            self.screen.blit(cell, (rect.x, rect.y))
            pygame.draw.line(self.screen, (255, 255, 255), (bx - 6, by), (bx + 6, by), 1)
            pygame.draw.line(self.screen, (255, 255, 255), (bx, by - 6), (bx, by + 6), 1)
            lbl = self.game.font.render(label, True, (230, 230, 245))
            lbl_y = by - r - 22
            if side == "below" or lbl_y < int(20 * scale):
                lbl_y = by + r + 22
            self.screen.blit(lbl, lbl.get_rect(center=(bx, lbl_y)))

        # 4) 底部操作按钮：保存 / 重置 / 返回
        by0 = int(sh - int(70 * scale))
        save_r = pygame.Rect(int(sw // 2 - 250 * scale), by0, int(160 * scale), int(50 * scale))
        reset_r = pygame.Rect(int(sw // 2 - 80 * scale), by0, int(160 * scale), int(50 * scale))
        back_r = pygame.Rect(int(sw // 2 + 90 * scale), by0, int(160 * scale), int(50 * scale))
        for rect, txt, col in [
            (save_r, "保存布局", (80, 200, 120)),
            (reset_r, "重置默认", (220, 170, 80)),
            (back_r, "返回", (220, 90, 90)),
        ]:
            pygame.draw.rect(self.screen, (*col, 160), rect, border_radius=8)
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 2, border_radius=8)
            lbl = self.game.font_large.render(txt, True, WHITE)
            self.screen.blit(lbl, lbl.get_rect(center=rect.center))
        if self._clicked(save_r, mouse_pos, mouse_pressed, touches, "hud_save"):
            self.game._save_hud_layout(target)
            self.game.hud_edit_dirty = False
            self.game.hud_layout_feedback = {"text": f"{target} 布局已保存 ✓", "expire": pygame.time.get_ticks() + 1800}
        if self._clicked(reset_r, mouse_pos, mouse_pressed, touches, "hud_reset"):
            self.game._reset_hud_layout(target)
            self._hud_edit_load_target(target)
            self.game.hud_edit_dirty = False
            self.game.hud_layout_feedback = {"text": f"{target} 布局已重置为默认", "expire": pygame.time.get_ticks() + 1800}
        if self._clicked(back_r, mouse_pos, mouse_pressed, touches, "hud_back"):
            if getattr(self.game, "hud_edit_dirty", False):
                # 未保存返回：恢复为已保存布局（或默认）
                if self.game.is_multiplayer_active():
                    self.game._setup_multiplayer_controls()
                else:
                    self.game._setup_touch_controls()
                    self.game._apply_hud_layout()
            self.game.state = GameState.SETTINGS
        # ===== 保存/重置强反馈提示 =====
        fb = getattr(self.game, "hud_layout_feedback", None)
        if fb and pygame.time.get_ticks() < fb["expire"]:
            fb_txt = self.game.font_large.render(fb["text"], True, (80, 230, 120))
            pygame.draw.rect(self.screen, (20, 60, 30), fb_txt.get_rect(center=(sw // 2, int(sh - 70 * scale))).inflate(24, 12), border_radius=8)
            pygame.draw.rect(self.screen, (80, 230, 120), fb_txt.get_rect(center=(sw // 2, int(sh - 70 * scale))).inflate(24, 12), 2, border_radius=8)
            self.screen.blit(fb_txt, fb_txt.get_rect(center=(sw // 2, int(sh - 70 * scale))))

    def _hud_edit_load_target(self, target):
        """切换HUD编辑目标时，把对应布局载入控件（无自定义则回默认）"""
        g = self.game
        if target == "P2":
            g._setup_multiplayer_controls()
            # P2 布局已由 _setup_multiplayer_controls 应用；无需再动
        elif target == "P1":
            g._setup_multiplayer_controls()
        else:  # 单机
            if not g.is_multiplayer_active():
                g._setup_touch_controls()
                g._apply_hud_layout()
            else:
                # 双人时编辑单机布局：临时把控件恢复全屏默认
                from ui import VirtualJoystick, AimButton, TouchButton, SkillSelector, SkillCaster
                g.joystick = VirtualJoystick(120, BASE_HEIGHT - 120, 70)
                g.aim_button = AimButton(780, BASE_HEIGHT - 145, 62)
                g.touch_buttons["shoot"] = TouchButton(780, BASE_HEIGHT - 145, 62, "射击", RED)
                g.touch_buttons["pause"] = TouchButton(60, 55, 38, "II", GRAY)
                g.touch_buttons["sprint"] = TouchButton(210, BASE_HEIGHT - 130, 40, "疾跑", AMBER)
                g.skill_selector = SkillSelector(1060, BASE_HEIGHT - 320, 42)
                g.skill_caster = SkillCaster(1150, BASE_HEIGHT - 145, 52)
                g.throwable_switch_btn = TouchButton(910, BASE_HEIGHT - 320, 42, "投掷", ORANGE)
                g.throwable_caster = SkillCaster(970, BASE_HEIGHT - 145, 48)
                g._apply_layout_to(g.config.hud_layout or {})

    def _draw_play_select(self):
        """开始游戏 → 单人/多人 选择"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width
        title = self.game.font_title.render("选择游戏方式", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(sw // 2, int(100 * scale))))
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        descs = ["独自面对尸潮，体验完整剧情", "与好友同乐：同屏双人或网络联机"]
        for i, btn in enumerate(self.game.play_select_buttons):
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                if i == 0:
                    self.game.multiplayer_mode = None
                    self.game.state = GameState.MODE_SELECT
                elif i == 1:
                    self.game.state = GameState.MULTIPLAYER_SELECT
                elif i == 2:
                    self.game.state = GameState.MENU
            btn.draw(self.screen, self.game.font_large, scale)
            if i < 2:
                d = self.game.font_small.render(descs[i], True, LIGHT_GRAY)
                self.screen.blit(d, d.get_rect(center=(sw // 2, int((310 + i * 80) * scale))))

    def _draw_multiplayer_select(self):
        """多人游戏 → 同屏双人 / 网络联机 选择"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width
        title = self.game.font_title.render("多人游戏", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(sw // 2, int(100 * scale))))
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        descs = ["同一屏幕，两个游戏画面，共享战场", "局域网直连：一台做主机，另一台加入"]
        for i, btn in enumerate(self.game.multiplayer_select_buttons):
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                if i == 0:
                    self.game.multiplayer_mode = "same_screen"
                    self.game.state = GameState.DIFFICULTY_SELECT
                elif i == 1:
                    self.game.multiplayer_mode = "network"
                    self.game.net_ip_input = "127.0.0.1"
                    self.game.net_ip_focused = False
                    self.game.state = GameState.NET_MULTIPLAYER
                elif i == 2:
                    self.game.state = GameState.PLAY_SELECT
            btn.draw(self.screen, self.game.font_large, scale)
            if i < 2:
                d = self.game.font_small.render(descs[i], True, LIGHT_GRAY)
                self.screen.blit(d, d.get_rect(center=(sw // 2, int((300 + i * 80) * scale))))

    def _draw_net_multiplayer(self):
        """网络联机：创建房间 / 加入房间（IP输入框）"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        title = self.game.font_title.render("网络联机", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(sw // 2, int(70 * scale))))
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        g = self.game
        # 创建房间
        host_r = pygame.Rect(int(sw // 2 - 150 * scale), int(150 * scale), int(300 * scale), int(55 * scale))
        pygame.draw.rect(self.screen, (40, 90, 40), host_r, border_radius=10)
        pygame.draw.rect(self.screen, GREEN, host_r, 2, border_radius=10)
        ht = self.game.font.render("创建房间（主机）", True, WHITE)
        self.screen.blit(ht, ht.get_rect(center=host_r.center))
        # IP 输入框
        ip_label = self.game.font.render("加入房间 - 主机IP:", True, LIGHT_GRAY)
        self.screen.blit(ip_label, (int(sw // 2 - 150 * scale), int(270 * scale)))
        ip_r = pygame.Rect(int(sw // 2 - 150 * scale), int(305 * scale), int(300 * scale), int(48 * scale))
        border_col = (120, 220, 120) if g.net_ip_focused else (90, 90, 110)
        pygame.draw.rect(self.screen, (25, 25, 35), ip_r, border_radius=8)
        pygame.draw.rect(self.screen, border_col, ip_r, 2, border_radius=8)
        ip_txt = self.game.font.render(g.net_ip_input + ("▏" if g.net_ip_focused else ""), True, WHITE)
        self.screen.blit(ip_txt, (ip_r.x + 10, ip_r.y + 8))
        # 加入按钮
        join_r = pygame.Rect(int(sw // 2 - 150 * scale), int(370 * scale), int(300 * scale), int(55 * scale))
        pygame.draw.rect(self.screen, (60, 90, 40), join_r, border_radius=10)
        pygame.draw.rect(self.screen, GOLD, join_r, 2, border_radius=10)
        jt = self.game.font.render("加入房间", True, WHITE)
        self.screen.blit(jt, jt.get_rect(center=join_r.center))
        # 返回
        back_r = pygame.Rect(int(sw // 2 - 150 * scale), int(460 * scale), int(300 * scale), int(44 * scale))
        pygame.draw.rect(self.screen, (60, 50, 50), back_r, border_radius=10)
        pygame.draw.rect(self.screen, GRAY, back_r, 2, border_radius=10)
        bt = self.game.font_small.render("返回", True, LIGHT_GRAY)
        self.screen.blit(bt, bt.get_rect(center=back_r.center))
        # 交互：点击聚焦输入框 / 按钮
        clicked = None
        for ev in g.touch_events:
            if ev["type"] == "down":
                clicked = ev["pos"]
                break
        if mouse_pressed[0]:
            clicked = clicked or mouse_pos
        if clicked:
            if host_r.collidepoint(clicked):
                g._net_start_host()
            elif ip_r.collidepoint(clicked):
                g.net_ip_focused = True
                g.start_text_input()
            elif join_r.collidepoint(clicked):
                g.net_ip_focused = False
                g.stop_text_input()
                g._net_join()
            elif back_r.collidepoint(clicked):
                g.net_ip_focused = False
                g.stop_text_input()
                g.state = GameState.MULTIPLAYER_SELECT

    def _draw_net_wait(self):
        """网络等待：主机等待客户端 / 客户端连接中"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width
        g = self.game
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if g.net_role == "host":
            title = self.game.font_title.render("等待玩家加入...", True, WHITE)
            self.screen.blit(title, title.get_rect(center=(sw // 2, int(120 * scale))))
            host_ip = g._get_local_ip()
            info = self.game.font.render(f"主机IP: {host_ip}    端口: {g.net_port}", True, GOLD)
            self.screen.blit(info, info.get_rect(center=(sw // 2, int(200 * scale))))
            status = "已连接！点击开始游戏" if (g.net_host and g.net_host.connected) else "等待客户端连接..."
            col = GREEN if (g.net_host and g.net_host.connected) else LIGHT_GRAY
            st = self.game.font.render(status, True, col)
            self.screen.blit(st, st.get_rect(center=(sw // 2, int(260 * scale))))
            # 开始按钮（客户端已连接时可用）
            start_r = pygame.Rect(int(sw // 2 - 150 * scale), int(330 * scale), int(300 * scale), int(55 * scale))
            can_start = bool(g.net_host and g.net_host.connected)
            pygame.draw.rect(self.screen, (40, 90, 40) if can_start else (50, 50, 55), start_r, border_radius=10)
            pygame.draw.rect(self.screen, GREEN if can_start else GRAY, start_r, 2, border_radius=10)
            stxt = self.game.font.render("开始游戏", True, WHITE)
            self.screen.blit(stxt, stxt.get_rect(center=start_r.center))
            # 取消
            cancel_r = pygame.Rect(int(sw // 2 - 150 * scale), int(410 * scale), int(300 * scale), int(44 * scale))
            pygame.draw.rect(self.screen, (60, 50, 50), cancel_r, border_radius=10)
            pygame.draw.rect(self.screen, GRAY, cancel_r, 2, border_radius=10)
            ct = self.game.font_small.render("取消", True, LIGHT_GRAY)
            self.screen.blit(ct, ct.get_rect(center=cancel_r.center))
            if mouse_pressed[0]:
                if can_start and start_r.collidepoint(mouse_pos):
                    g._net_host_start_game()
                elif cancel_r.collidepoint(mouse_pos):
                    g._net_stop()
        else:
            title = self.game.font_title.render("连接中...", True, WHITE)
            self.screen.blit(title, title.get_rect(center=(sw // 2, int(120 * scale))))
            if g.net_client and g.net_client.connected:
                status = "已连接！等待主机开始游戏..."
                col = GREEN
            elif g.net_client and g.net_client.error:
                status = f"连接失败: {g.net_client.error}"
                col = CRIMSON
            else:
                status = f"正在连接 {g.net_ip_input}:{g.net_port} ..."
                col = LIGHT_GRAY
            st = self.game.font.render(status, True, col)
            self.screen.blit(st, st.get_rect(center=(sw // 2, int(220 * scale))))
            cancel_r = pygame.Rect(int(sw // 2 - 150 * scale), int(330 * scale), int(300 * scale), int(44 * scale))
            pygame.draw.rect(self.screen, (60, 50, 50), cancel_r, border_radius=10)
            pygame.draw.rect(self.screen, GRAY, cancel_r, 2, border_radius=10)
            ct = self.game.font_small.render("取消", True, LIGHT_GRAY)
            self.screen.blit(ct, ct.get_rect(center=cancel_r.center))
            if mouse_pressed[0] and cancel_r.collidepoint(mouse_pos):
                g._net_stop()
            # 客户端收到 started 快照 → 进入客户端游玩
            if g.net_client and g.net_client.get_snapshot().get("started"):
                g.state = GameState.NET_CLIENT_PLAY

    def _draw_net_client(self):
        """网络客户端游玩：渲染主机广播的世界快照"""
        self.screen.fill(VOID_BLACK)
        g = self.game
        scale = g.scale
        sw = g.scaled_width
        sh = g.scaled_height
        snap = g.net_client.get_snapshot() if g.net_client else {}
        players = snap.get("players", [])
        me = players[1] if len(players) > 1 else (players[0] if players else None)
        cam_x = (me["x"] if me else 0) - sw / (2.0 * scale)
        cam_y = (me["y"] if me else 0) - sh / (2.0 * scale)
        # 背景网格（轻量）
        grid = int(80 * scale)
        ox, oy = int(-cam_x * scale) % grid, int(-cam_y * scale) % grid
        for gx in range(ox, sw, grid):
            pygame.draw.line(self.screen, (22, 26, 22), (gx, 0), (gx, sh))
        for gy in range(oy, sh, grid):
            pygame.draw.line(self.screen, (22, 26, 22), (0, gy), (sw, gy))
        # 敌人
        for e in snap.get("enemies", []):
            px = int((e["x"] - cam_x) * scale)
            py = int((e["y"] - cam_y) * scale)
            if px < -60 or py < -60 or px > sw + 60 or py > sh + 60:
                continue
            r = max(4, int(e.get("size", 12) * scale * 0.45))
            pygame.draw.circle(self.screen, (110, 50, 50), (px, py), r)
            pygame.draw.circle(self.screen, (150, 70, 70), (px, py), r, 2)
        # 投射物
        for p in snap.get("projectiles", []):
            px = int((p["x"] - cam_x) * scale)
            py = int((p["y"] - cam_y) * scale)
            if px < -40 or py < -40 or px > sw + 40 or py > sh + 40:
                continue
            col = tuple(p.get("color", (255, 255, 255))[:3])
            pygame.draw.circle(self.screen, col, (px, py), max(3, int(p.get("size", 6) * scale * 0.6)))
        # 特效（客户端也能看到技能效果）
        for fx in snap.get("effects", []):
            if fx.get("t") == "ring":
                px = int((fx["x"] - cam_x) * scale)
                py = int((fx["y"] - cam_y) * scale)
                r = int(fx["r"] * scale)
                col = tuple(fx.get("color", (190, 80, 230))[:3])
                ring = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                alpha = int(200 * max(0, min(1, fx.get("life", 0.3) * 3)))
                pygame.draw.circle(ring, (*col, alpha), (r, r), r, max(3, int(8 * scale)))
                self.screen.blit(ring, (px - r, py - r))
            elif fx.get("t") == "arc":
                px = int((fx["x"] - cam_x) * scale)
                py = int((fx["y"] - cam_y) * scale)
                col = tuple(fx.get("color", (190, 80, 230))[:3])
                r = int(fx.get("radius", 150) * scale)
                arc_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.arc(arc_surf, (*col, 220), (0, 0, r * 2, r * 2),
                                fx.get("angle", 0), fx.get("angle", 0) + 0.8, max(4, int(10 * scale)))
                self.screen.blit(arc_surf, (px - r, py - r))
        # 玩家
        labels = ["P1", "P2"]
        cols = [GREEN, CYAN]
        for idx, p in enumerate(players):
            px = int((p["x"] - cam_x) * scale)
            py = int((p["y"] - cam_y) * scale)
            r = max(8, int(16 * scale))
            if p.get("downed"):
                pygame.draw.circle(self.screen, (200, 200, 60), (px, py), r, 3)
                tag = g.font_small.render(labels[idx] + " 倒地", True, (240, 230, 120))
            else:
                pygame.draw.circle(self.screen, cols[idx], (px, py), r)
                pygame.draw.circle(self.screen, WHITE, (px, py), r, 2)
                tag = g.font_small.render(labels[idx], True, cols[idx])
            self.screen.blit(tag, (px - tag.get_width() // 2, py - r - int(14 * scale)))
            # 武器名
            wname = p.get("weapon", "")
            if wname:
                wt = g.font_small.render(wname, True, GOLD)
                self.screen.blit(wt, (px - wt.get_width() // 2, py + r + int(4 * scale)))
        # HUD：时间与状态
        tl = max(0, int(snap.get("time_left", 0)))
        time_txt = g.font.render(f"网络联机  {tl // 60:02d}:{tl % 60:02d}", True, WHITE)
        self.screen.blit(time_txt, time_txt.get_rect(midtop=(sw // 2, int(10 * scale))))
        conn_txt = g.font_small.render("连接主机中...", True, LIGHT_GRAY)
        self.screen.blit(conn_txt, conn_txt.get_rect(midbottom=(sw // 2, sh - int(6 * scale))))
        # 客户端输入控件（触控模式）
        if g.config.control_mode == ControlMode.TOUCH:
            g.client_joystick.draw(self.screen, scale)
            g.client_aim.draw(self.screen, g.font, scale)
            g.client_shoot.draw(self.screen, g.font, scale)
            g.client_skill.draw(self.screen, g.font, scale)

    def _draw_tutorial(self):
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width

        line_height = int(35 * scale)
        control_line_height = int(28 * scale)
        content_height = int(140 * scale) + len(self.game.tutorial_texts) * line_height + int(20 * scale) + 11 * control_line_height + 80
        max_scroll = max(0, content_height - self.game.scaled_height + 100)
        scroll_y = min(self.game.tutorial_scroll_offset, max_scroll)

        title = self.game.font_title.render("教程", True, WHITE)
        title_rect = title.get_rect(center=(sw // 2, int(80 * scale) - scroll_y))
        self.screen.blit(title, title_rect)

        y = int(140 * scale) - scroll_y
        for i, text in enumerate(self.game.tutorial_texts):
            color = AMBER if i == self.game.tutorial_step else WHITE
            text_surf = self.game.font.render(f"{i+1}. {text}", True, color)
            self.screen.blit(text_surf, (int(50 * scale), y))
            y += line_height

        y += int(20 * scale)
        controls = [
            "WASD - 移动", "鼠标 - 瞄准", "左键 - 射击",
            "Tab - 切换下一个技能", "G - 短按释放 / 长按瞄准释放技能",
            "1/2/3 - 切换武器", "R - 切换下一个武器", "ESC - 暂停"
        ]
        for control in controls:
            text_surf = self.game.font.render(control, True, GRAY)
            self.screen.blit(text_surf, (int(50 * scale), y))
            y += control_line_height

        # 使用预创建的按钮，不每帧创建新对象
        back_btn = self.game.tutorial_back_btn
        back_btn.visible = True
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if back_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.logger.info("教程返回按钮被点击")
            self.game.state = GameState.MENU
            self.game.tutorial_scroll_offset = 0
        back_btn.draw(self.screen, self.game.font_large, scale)

        if self.game.tutorial_scroll_offset > 0:
            hint = self.game.font_small.render("+ 继续上滑", True, GRAY)
            self.screen.blit(hint, (sw // 2 - 40, 10))
        if max_scroll > 0 and self.game.tutorial_scroll_offset < max_scroll:
            hint = self.game.font_small.render("- 继续下滑", True, GRAY)
            self.screen.blit(hint, (sw // 2 - 40, self.game.scaled_height - 30))

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
        """把触控控件画进对应半屏（left=True 用 P1 控件；否则 P2 控件，坐标无需平移）"""
        scale = g.scale
        if left:
            g.joystick.draw(self.screen, scale)
            g.aim_button.draw(self.screen, g.font, scale)
            g.skill_selector.draw(self.screen, g.font, scale=scale)
            g.skill_caster.draw(self.screen, g.font, scale=scale)
            g.throwable_switch_btn.draw(self.screen, g.font, scale)
            g.throwable_caster.draw(self.screen, g.font, scale=scale)
            for name, b in g.touch_buttons.items():
                if name in ("shoot", "pause", "sprint"):
                    b.draw(self.screen, g.font, scale)
        else:
            c2 = g.p2_controls
            c2["joystick"].draw(self.screen, scale)
            c2["aim"].draw(self.screen, g.font, scale)
            c2["skill_selector"].draw(self.screen, g.font, scale=scale)
            c2["skill_caster"].draw(self.screen, g.font, scale=scale)
            c2["throwable_switch"].draw(self.screen, g.font, scale)
            c2["throwable_caster"].draw(self.screen, g.font, scale=scale)
            for name, b in c2.items():
                if name in ("shoot", "pause", "sprint"):
                    b.draw(self.screen, g.font, scale)

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
                skill_name = skill.name if skill else "?"
                skill_color = skill.icon_color if skill else BLUE
                self.game.skill_selector.draw(self.screen, self.game.font_small, skill_name, skill_color, scale)

            if hasattr(self.game, 'skill_caster') and self.game.skill_caster:
                skill = player.skill_tree.get_skill(self.game.selected_skill)
                skill_name = skill.name if skill else "放"
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
            
        # =========【新增】成就解锁右上角toast提示 =========
        scale = self.game.scale
        toast_y = int(20 * scale)
        for toast in self.game.ach_toast_queue:
            text = f"成就解锁：{toast['desc']}"
            surf = self.game.font.render(text, True, GOLD)
            w,h = surf.get_size()
            bg_rect = pygame.Rect(int(self.game.scaled_width - w - 20*scale), toast_y, w+20*scale, h+10*scale)
            pygame.draw.rect(self.screen, (*CHARCOAL[:3], 210), bg_rect, border_radius=6)
            pygame.draw.rect(self.screen, GOLD, bg_rect, max(1,int(scale)), border_radius=6)
            self.screen.blit(surf, (bg_rect.x + int(10*scale), bg_rect.y + int(5*scale)))
            toast_y += int(h+14*scale)

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
                next_skill_name = next_skill.name if next_skill else "?"
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

    def _draw_dialogue(self):
        self.game.dialogue.draw(self.screen, self.game.font, self.game.font_large, 
                                self.game.scaled_width, self.game.scaled_height)

    def _draw_skill_select(self):
        """绘制技能卡选择界面"""
        if hasattr(self.game, 'skill_card_selector'):
            self.game.skill_card_selector.draw(
                self.screen, self.game.font, self.game.font_large, self.game.scale
            )

    def _draw_pause(self):
        overlay = pygame.Surface((self.game.scaled_width, self.game.scaled_height), pygame.SRCALPHA)
        overlay.fill((*VOID_BLACK[:3], 200))
        self.screen.blit(overlay, (0, 0))

        title = self.game.font_title.render("暂停", True, WHITE)
        title_rect = title.get_rect(center=(self.game.scaled_width // 2, int(150 * self.game.scale)))
        self.screen.blit(title, title_rect)

        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()

        for i, btn in enumerate(self.game.pause_buttons):
            # 非开发者模式下隐藏"开发者面板"按钮
            if btn.text == "开发者面板" and not getattr(self.game, 'dev_mode', False):
                continue
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, self.game.scale):
                self.game.logger.info(f"暂停按钮 '{btn.text}' 被点击")
                if btn.text == "继续":
                    self.game.state = GameState.PLAYING
                elif btn.text == "符文":
                    self.game.prev_state = GameState.PAUSED
                    self.game.rune_view_scroll = 0
                    self.game.rune_selected = None
                    self.game.state = GameState.RUNE_VIEW
                elif btn.text == "技能树":
                    self.game.prev_state = GameState.PAUSED
                    self.game.state = GameState.SKILL_TREE
                    if hasattr(self.game, 'skill_tree_renderer'):
                        self.game.skill_tree_renderer.show()
                elif btn.text == "设置":
                    # 进入设置，标记从暂停进入
                    self.game.settings_from_pause = True
                    self.game.state = GameState.SETTINGS
                elif btn.text == "开发者面板":
                    # 开发者模式下面板开关（局内调试面板）
                    self.game.dev_panel_open = not getattr(self.game, 'dev_panel_open', False)
                    if hasattr(self.game, '_rebuild_dev_buttons'):
                        self.game._rebuild_dev_buttons()
                    self.game.state = GameState.PLAYING
                elif btn.text == "返回菜单":
                    self.game.state = GameState.MENU
            btn.draw(self.screen, self.game.font_large, self.game.scale)

    def _draw_rune_view(self):
        """符文查看界面：显示玩家拥有的符文，点击符文查看详情"""
        g = self.game
        scale = g.scale
        sw, sh = g.scaled_width, g.scaled_height
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((*VOID_BLACK[:3], 215))
        self.screen.blit(overlay, (0, 0))

        title = g.font_title.render("我的符文", True, GOLD)
        self.screen.blit(title, title.get_rect(center=(sw // 2, int(60 * scale))))

        # 返回按钮（统一鼠标+触控点击）
        back_btn = pygame.Rect(int(30 * scale), int(25 * scale), int(120 * scale), int(40 * scale))
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if self._clicked(back_btn, mouse_pos, mouse_pressed, g.touch_events, "rune_back"):
            if getattr(g, '_rune_back_cooldown', 0) <= 0:
                g._rune_back_cooldown = 0.3
                g.state = GameState.PAUSED
                g.rune_selected = None
        pygame.draw.rect(self.screen, RED, back_btn, border_radius=6)
        bt = g.font.render("返回", True, WHITE)
        self.screen.blit(bt, bt.get_rect(center=back_btn.center))

        if not hasattr(g, 'rune_manager') or not g.rune_manager or not g.rune_manager.runes:
            empty = g.font.render("尚未获得任何符文", True, GRAY)
            self.screen.blit(empty, empty.get_rect(center=(sw // 2, sh // 2)))
            return

        # 符文网格（可滚动）
        from runes import RUNE_CONFIG, RARITY_NAMES, RARITY_COLORS
        from config import RuneType
        items = list(g.rune_manager.runes.items())
        cell_w, cell_h = int(150 * scale), int(120 * scale)
        gap = int(16 * scale)
        cols = max(1, (sw - int(80 * scale)) // (cell_w + gap))
        rows_per_screen = max(1, (sh - int(160 * scale)) // (cell_h + gap))
        grid_top = int(110 * scale)
        # 滚动
        if hasattr(g, 'rune_view_scroll'):
            # 滚轮滚动
            scroll_total = max(0, (len(items) + cols - 1) // cols - rows_per_screen)
            g.rune_view_scroll = max(0, min(scroll_total, g.rune_view_scroll))
        clicked_idx = None
        for idx, (rt, stacks) in enumerate(items):
            row, col = divmod(idx, cols)
            if row < g.rune_view_scroll:
                continue
            if row >= g.rune_view_scroll + rows_per_screen:
                break
            rx = int(50 * scale) + col * (cell_w + gap)
            ry = grid_top + (row - g.rune_view_scroll) * (cell_h + gap)
            cfg = RUNE_CONFIG[rt]
            rect = pygame.Rect(rx, ry, cell_w, cell_h)
            # 选中高亮
            if g.rune_selected == rt:
                pygame.draw.rect(self.screen, GOLD, rect.inflate(6, 6), border_radius=8)
            pygame.draw.rect(self.screen, (40, 40, 45), rect, border_radius=8)
            pygame.draw.rect(self.screen, cfg["color"], rect, 2, border_radius=8)
            name = g.font.render(cfg["name"], True, cfg["color"])
            self.screen.blit(name, name.get_rect(center=(rect.centerx, ry + int(22 * scale))))
            lv = g.font_small.render(f"等级 {stacks}", True, WHITE)
            self.screen.blit(lv, lv.get_rect(center=(rect.centerx, ry + int(48 * scale))))
            rar = g.font_small.render(RARITY_NAMES.get(cfg["rarity"], "普通"), True, RARITY_COLORS.get(cfg["rarity"], GRAY))
            self.screen.blit(rar, rar.get_rect(center=(rect.centerx, ry + int(70 * scale))))
            if self._clicked(rect, mouse_pos, mouse_pressed, g.touch_events, ("rune_cell", idx)) and getattr(g, '_rune_click_cooldown', 0) <= 0:
                clicked_idx = idx

        # 点击符文 → 选中（查看详情）
        if clicked_idx is not None:
            g.rune_selected = items[clicked_idx][0]

        # 详情面板（右侧或下方）
        if g.rune_selected is not None and g.rune_selected in g.rune_manager.runes:
            rt = g.rune_selected
            cfg = RUNE_CONFIG[rt]
            stacks = g.rune_manager.runes[rt]
            # 关闭按钮（统一鼠标+触控点击）
            close_rect = pygame.Rect(int(sw - 50 * scale), int(160 * scale), int(36 * scale), int(36 * scale))
            if self._clicked(close_rect, mouse_pos, mouse_pressed, g.touch_events, "rune_close") and getattr(g, '_rune_close_cooldown', 0) <= 0:
                g.rune_selected = None
            detail_w = int(420 * scale)
            detail_h = int(300 * scale)
            detail_rect = pygame.Rect((sw - detail_w) // 2, (sh - detail_h) // 2 + int(20 * scale), detail_w, detail_h)
            panel = pygame.Surface((detail_w, detail_h), pygame.SRCALPHA)
            panel.fill((25, 25, 30, 245))
            self.screen.blit(panel, detail_rect.topleft)
            pygame.draw.rect(self.screen, cfg["color"], detail_rect, 3, border_radius=10)
            # 标题
            dtitle = g.font_large.render(cfg["name"], True, cfg["color"])
            self.screen.blit(dtitle, dtitle.get_rect(center=(detail_rect.centerx, detail_rect.y + int(35 * scale))))
            # 稀有度+等级
            dinfo = g.font.render(f"稀有度: {RARITY_NAMES.get(cfg['rarity'], '普通')}    等级: {stacks}", True, RARITY_COLORS.get(cfg["rarity"], GRAY))
            self.screen.blit(dinfo, dinfo.get_rect(center=(detail_rect.centerx, detail_rect.y + int(70 * scale))))
            # 描述（自动换行）
            desc = cfg["description"]
            words = desc
            max_w = detail_w - int(40 * scale)
            lines = []
            cur = ""
            for ch in words:
                test = cur + ch
                if g.font_small.size(test)[0] <= max_w:
                    cur = test
                else:
                    lines.append(cur)
                    cur = ch
            if cur:
                lines.append(cur)
            y = detail_rect.y + int(105 * scale)
            for line in lines:
                lt = g.font_small.render(line, True, WHITE)
                self.screen.blit(lt, (detail_rect.x + int(20 * scale), y))
                y += int(24 * scale)
            # 效果（等级相关）
            effect = self._rune_level_effect_text(rt, stacks)
            if effect:
                ef = g.font_small.render(effect, True, LIME)
                self.screen.blit(ef, (detail_rect.x + int(20 * scale), y + int(6 * scale)))

        pygame.display.flip()

    def _rune_level_effect_text(self, rt, stacks):
        """返回符文当前等级对应的效果描述文本"""
        from runes import RUNE_CONFIG
        from config import RuneType
        cfg = RUNE_CONFIG[rt]
        if rt == RuneType.POWER:
            return f"所有伤害 +{int(15 * stacks)}%"
        if rt == RuneType.VITALITY:
            return f"最大生命值 +{30 * stacks}"
        if rt == RuneType.SWIFTNESS:
            return f"移动速度 +{int(10 * stacks)}%"
        if rt == RuneType.CRITICAL:
            return f"暴击率 +{int(10 * stacks)}%"
        if rt == RuneType.VAMPIRE:
            return f"攻击回复 {int(5 * stacks)}% 生命"
        if rt == RuneType.GUARDIAN:
            return f"护甲 +{10 * stacks}"
        if rt == RuneType.FRENZY:
            return f"攻击速度 +{int(15 * stacks)}%"
        if rt == RuneType.REGEN:
            return f"每秒回复 {2 * stacks} 生命"
        if rt == RuneType.SHADOW:
            return f"暴击伤害 +{int(50 * stacks)}%"
        if rt == RuneType.LUCK:
            return f"掉落率 +{int(20 * stacks)}%"
        if rt == RuneType.TITAN:
            return f"体型 +{int(15 * stacks)}%  近战范围+20%  伤害+10%"
        if rt == RuneType.FLAME:
            return f"攻击灼烧敌人"
        if rt == RuneType.FROST:
            return f"攻击减速敌人"
        if rt == RuneType.POISON:
            return f"攻击使敌人中毒"
        if rt == RuneType.THUNDER:
            return f"攻击触发连锁闪电"
        return ""

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

    def _draw_game_over(self):
        overlay = pygame.Surface((self.game.scaled_width, self.game.scaled_height), pygame.SRCALPHA)
        overlay.fill((*VOID_BLACK[:3], 220))
        self.screen.blit(overlay, (0, 0))
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height

        title = self.game.font_title.render("游戏结束", True, RED)
        title_rect = title.get_rect(center=(sw // 2, int(200 * scale)))
        self.screen.blit(title, title_rect)

        summary = self.game.records.get_summary()
        # 【修复】统一基准y，逐行向下累加，不再写死固定坐标
        base_y = int(280 * scale)
        line_spacing = int(45 * scale)
        y = base_y

        score_text = self.game.font_large.render(f"最终得分: {self.game.player.score}", True, WHITE)
        score_rect = score_text.get_rect(center=(sw // 2, y))
        self.screen.blit(score_text, score_rect)
        y += line_spacing

        record_text = self.game.font.render(f"历史最高: {summary['best_score']}  总击杀: {summary['total_kills']}", True, GOLD)
        record_rect = record_text.get_rect(center=(sw // 2, y))
        self.screen.blit(record_text, record_rect)
        y += line_spacing

        playtime_text = self.game.font.render(f"总游戏时长: {summary['play_time']}", True, GRAY)
        playtime_rect = playtime_text.get_rect(center=(sw // 2, y))
        self.screen.blit(playtime_text, playtime_rect)
        y += line_spacing

        wave_text = self.game.font_large.render(f"存活时间: {int(self.game.horde_manager.total_time)}s", True, WHITE)
        wave_rect = wave_text.get_rect(center=(sw // 2, y))
        self.screen.blit(wave_text, wave_rect)
        y += line_spacing

        # 成就统计
        unlocked = len(self.game.records.get_unlocked_achievements())
        total_ach = len(self.game.records.get_achievements())
        ach_text = self.game.font.render(f"成就: {unlocked}/{total_ach}", True, CYAN)
        ach_rect = ach_text.get_rect(center=(sw // 2, y))
        self.screen.blit(ach_text, ach_rect)

        # 返回按钮
        btn = self.game.gameover_back_btn
        btn.visible = True
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.logger.info("游戏结束返回菜单")
            self.game.state = GameState.MENU
        btn.draw(self.screen, self.game.font_large, scale)

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

    def _draw_victory(self):
        """故事模式通关界面"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width

        title = self.game.font_title.render("通关！", True, GOLD)
        title_rect = title.get_rect(center=(sw // 2, int(180 * scale)))
        self.screen.blit(title, title_rect)

        subtitle = self.game.font.render("你成功阻止了核灾难，拯救了世界", True, WHITE)
        subtitle_rect = subtitle.get_rect(center=(sw // 2, int(240 * scale)))
        self.screen.blit(subtitle, subtitle_rect)

        # 统计信息
        if self.game.session:
            stats = [
                f"存活时间: {int(self.game.session.total_time // 60)}分{int(self.game.session.total_time % 60)}秒",
                f"击杀数: {self.game.session.total_kills}",
                f"达到等级: {self.game.session.max_level}",
                f"收集剧情: {len(self.game.story_collected_fragments)} / 20",
            ]
            for i, stat in enumerate(stats):
                stat_text = self.game.font.render(stat, True, LIGHT_GRAY)
                stat_rect = stat_text.get_rect(center=(sw // 2, int((300 + i * 35) * scale)))
                self.screen.blit(stat_text, stat_rect)

        # 返回菜单按钮
        btn = self.game.menu_buttons[0]
        # 转换为逻辑坐标（Button 内部会再乘 scale），避免双重缩放
        btn.base_x = int((sw // 2 - 100) / scale)
        btn.base_y = 480
        btn.text = "返回主菜单"
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.state = GameState.MENU
        btn.draw(self.screen, self.game.font_large, scale)

    def _draw_ending(self):
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale

        endings = {
            "perfect": {
                "title": "完美结局 - 重逢",
                "text": [
                    "你使用疫苗拯救了龙某和向某。",
                    "他们恢复了意识，虽然身体还很虚弱。",
                    "谢谢你...朋友...龙某虚弱地说道。",
                    "我们...我们还能回去吗?向某问道。",
                    "你们三人相互搀扶着，走向未知的未来...",
                    "但无论如何，你们还在一起。"
                ],
                "color": GREEN
            },
            "save_long": {
                "title": "结局 - 选择",
                "text": [
                    "你选择了拯救龙某。",
                    "向某在你眼前倒下，眼中似乎闪过一丝清明。",
                    "对不起...你低声说道。",
                    "龙某抱着向某的尸体，泪如雨下。",
                    "为什么...为什么只能救一个...",
                    "你们活下来了，但代价是什么?"
                ],
                "color": BLUE
            },
            "save_xiang": {
                "title": "结局 - 抉择",
                "text": [
                    "你选择了拯救向某。",
                    "龙某倒下了，他的嘴角似乎带着微笑。",
                    "做得好...朋友...",
                    "向某跪在地上，无法接受这个事实。",
                    "他...他本来可以...",
                    "生存，有时候意味着失去。"
                ],
                "color": ORANGE
            },
            "tragic": {
                "title": "悲剧结局 - 孤独",
                "text": [
                    "你拥有疫苗，但你选择了不使用它。",
                    "龙某和向某都倒下了。",
                    "为什么...他们的眼神中充满不解。",
                    "你独自站在废墟中，周围是死寂。",
                    "你活下来了，但你失去了所有。",
                    "这真的是你想要的吗?"
                ],
                "color": GRAY
            },
            "kill_both": {
                "title": "结局 - 终结",
                "text": [
                    "你没有找到疫苗。",
                    "你亲手结束了龙某和向某的痛苦。",
                    "谢谢你...这是他们最后的话。",
                    "学校的大火燃烧了三天三夜。",
                    "当救援队到达时，只找到了你一个人。",
                    "你活下来了，但你的心已经死了。"
                ],
                "color": RED
            },
            "let_go": {
                "title": "结局 - 放手",
                "text": [
                    "你没有找到疫苗，但你也没有杀死他们。",
                    "你放走了龙某和向某。",
                    "去找你们自己的答案吧...",
                    "他们消失在废墟中，不知去向。",
                    "也许有一天，你们会再次相遇。",
                    "也许，这就是最好的结局。"
                ],
                "color": PURPLE
            }
        }

        ending = endings.get(self.game.ending_type, endings["kill_both"])

        title = self.game.font_title.render(ending["title"], True, ending["color"])
        title_rect = title.get_rect(center=(self.game.scaled_width // 2, int(100 * scale)))
        self.screen.blit(title, title_rect)

        y = int(180 * scale)
        for line in ending["text"]:
            text_surf = self.game.font.render(line, True, WHITE)
            text_rect = text_surf.get_rect(center=(self.game.scaled_width // 2, y))
            self.screen.blit(text_surf, text_rect)
            y += int(35 * scale)

        # 显示记录摘要
        summary = self.game.records.get_summary()
        y_end = int(180 * scale) + len(ending["text"]) * int(35 * scale)
        record_text = self.game.font.render(f"本局得分: {self.game.player.score}  历史最高: {summary['best_score']}", True, GOLD)
        record_rect = record_text.get_rect(center=(self.game.scaled_width // 2, int(y_end + 20 * scale)))
        self.screen.blit(record_text, record_rect)

        # 显示已解锁成就数
        unlocked = len(self.game.records.get_unlocked_achievements())
        total_ach = len(self.game.records.get_achievements())
        ach_text = self.game.font.render(f"成就: {unlocked}/{total_ach}", True, CYAN)
        ach_rect = ach_text.get_rect(center=(self.game.scaled_width // 2, int(y_end + 50 * scale)))
        self.screen.blit(ach_text, ach_rect)

        # 使用预创建的按钮
        back_btn = self.game.gameover_back_btn
        back_btn.visible = True
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if back_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.logger.info("结局返回菜单")
            self.game.state = GameState.MENU
        back_btn.draw(self.screen, self.game.font_large, scale)

    def _draw_records(self):
        """绘制记录查看界面"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width

        # 标题
        title = self.game.font_title.render("游戏记录", True, GOLD)
        title_rect = title.get_rect(center=(sw // 2, int(60 * scale)))
        self.screen.blit(title, title_rect)

        # 获取记录数据
        data = self.game.records.get_full_report()
        summary = self.game.records.get_summary()

        # 基础统计
        y = int(120 * scale)
        line_h = int(28 * scale)

        stats = [
            ("总游戏次数", f"{summary['games']}"),
            ("总游戏时长", f"{summary['play_time']}"),
            ("最高分数", f"{summary['best_score']}"),
            ("最高等级", f"{summary['best_level']}"),
            ("最长存活", f"{summary['best_time_survived']:.1f}s"),
            ("总击杀", f"{summary['total_kills']}"),
            ("总死亡", f"{summary['total_deaths']}"),
        ]

        for label, value in stats:
            label_surf = self.game.font.render(f"{label}:", True, GRAY)
            value_surf = self.game.font.render(value, True, WHITE)
            self.screen.blit(label_surf, (int(50 * scale), y))
            self.screen.blit(value_surf, (int(200 * scale), y))
            y += line_h

        # 成就
        y += int(10 * scale)
        ach_title = self.game.font.render("成就", True, GOLD)
        self.screen.blit(ach_title, (int(50 * scale), y))
        y += line_h

        achievements = self.game.records.get_achievements()
        for ach_key, ach_data in list(achievements.items())[:8]:
            color = GREEN if ach_data["unlocked"] else DARK_GRAY
            status = "v" if ach_data["unlocked"] else "(o)"
            ach_text = self.game.font.render(f"{status} {ach_data['desc']}", True, color)
            self.screen.blit(ach_text, (int(70 * scale), y))
            y += line_h

        # 最近历史
        y = int(120 * scale)
        hist_title = self.game.font.render("最近记录", True, GOLD)
        self.screen.blit(hist_title, (sw // 2 + int(50 * scale), y))
        y += line_h

        history = self.game.records.get_game_history(5)
        for entry in history:
            died_str = "死亡" if entry.get("died", True) else "通关"
            ending = entry.get("ending", "")
            if ending:
                died_str += f"({ending})"
            hist_str = f"{entry['score']}分 Lv.{entry['level']} {died_str}"
            hist_surf = self.game.font_small.render(hist_str, True, WHITE)
            self.screen.blit(hist_surf, (sw // 2 + int(50 * scale), y))
            y += line_h

        # 返回按钮
        back_btn = self.game.gameover_back_btn
        back_btn.visible = True
        back_btn.text = "返回菜单"
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if back_btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.state = GameState.MENU
        back_btn.draw(self.screen, self.game.font_large, scale)

    def _draw_achievements(self):
        """绘制可滚动分组成就页面，兼容旧存档缺失字段；过滤未解锁隐藏成就"""
        self.screen.fill(VOID_BLACK)
        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        title = self.game.font_title.render("成就", True, GOLD)
        title_rect = title.get_rect(center=(sw//2, int(70*scale)))
        self.screen.blit(title, title_rect)

        grouped = self.game.records.get_grouped_achievements(show_hidden_unlocked_only=True)
        line_height = int(36 * scale)
        group_title_height = int(44 * scale)
        view_top = int(110 * scale)
        view_bottom = int(sh - 120 * scale)
        clip_rect = pygame.Rect(0, view_top, sw, view_bottom - view_top)

        # 鼠标拖动滚动（PC端点击拖拽）
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if not hasattr(self.game, '_ach_drag_state'):
            self.game._ach_drag_state = {"dragging": False, "start_y": 0, "start_scroll": 0, "moved": False}
        ds = self.game._ach_drag_state
        if clip_rect.collidepoint(mouse_pos):
            if mouse_pressed[0]:
                if not ds["dragging"]:
                    ds["dragging"] = True
                    ds["start_y"] = mouse_pos[1]
                    ds["start_scroll"] = self.game.ach_scroll_offset
                    ds["moved"] = False
                else:
                    dy = mouse_pos[1] - ds["start_y"]
                    if abs(dy) > 3:
                        ds["moved"] = True
                    self.game.ach_scroll_offset = max(0, ds["start_scroll"] - dy)
            else:
                ds["dragging"] = False
        else:
            if not mouse_pressed[0]:
                ds["dragging"] = False

        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)
        y = view_top - self.game.ach_scroll_offset

        # 动态遍历所有分组，使用自定义排序顺序
        custom_order = ["战斗", "生存", "技能武器", "结局挑战", "隐藏", "其他"]
        all_groups = list(grouped.keys())
        # 按自定义顺序排序，未在列表中的分组排在最后
        group_order = sorted(all_groups, key=lambda g: custom_order.index(g) if g in custom_order else len(custom_order))
        for gname in group_order:
            item_list = grouped.get(gname, [])
            if not item_list:
                continue
            title_surf = self.game.font_large.render(f"【{gname}】", True, AMBER)
            self.screen.blit(title_surf, (int(30*scale), y))
            y += group_title_height
            for ach_key, ach_data in item_list:
                unlocked = ach_data.get("unlocked", False)
                if unlocked:
                    col = GOLD
                    prefix = "v "
                else:
                    col = DARK_GRAY
                    prefix = "(o) "
                desc = ach_data.get("desc","???")
                text_str = prefix + desc
                surf = self.game.font.render(text_str, True, col)
                self.screen.blit(surf, (int(40*scale), y))
                # ===== 成就进度条 =====
                progress = self.game.records.get_achievement_progress(ach_key)
                if progress:
                    cur, tgt = progress
                    ratio = min(1.0, cur / tgt) if tgt > 0 else 1.0
                    bar_w = int(180 * scale)
                    bar_h = max(4, int(10 * scale))
                    bar_x = int(420 * scale)
                    bar_y = y + int(4 * scale)
                    # 背景
                    pygame.draw.rect(self.screen, DARK_GRAY,
                        (bar_x, bar_y, bar_w, bar_h), border_radius=3)
                    # 进度
                    prog_color = GREEN if unlocked else AMBER
                    pygame.draw.rect(self.screen, prog_color,
                        (bar_x, bar_y, int(bar_w * ratio), bar_h), border_radius=3)
                    pygame.draw.rect(self.screen, GRAY,
                        (bar_x, bar_y, bar_w, bar_h), max(1, int(scale)), border_radius=3)
                    # 进度文字
                    def fmt_num(n):
                        if n >= 10000:
                            return f"{n/10000:.1f}万"
                        return str(int(n))
                    prog_text = f"{fmt_num(cur)}/{fmt_num(tgt)}"
                    prog_surf = self.game.font_small.render(prog_text, True,
                        GOLD if unlocked else LIGHT_GRAY)
                    self.screen.blit(prog_surf, (bar_x + bar_w + int(8*scale), bar_y - int(2*scale)))
                elif unlocked and ach_data.get("date"):
                    date_surf = self.game.font_small.render(ach_data["date"], True, LIGHT_GRAY)
                    self.screen.blit(date_surf, (int(420*scale), y+4))
                y += line_height

        self.screen.set_clip(old_clip)

        # 限制滚动范围
        total_content_height = max(1, y - (view_top - self.game.ach_scroll_offset))
        view_height = view_bottom - view_top
        max_scroll = max(0, total_content_height - view_height)
        self.game.ach_scroll_offset = min(self.game.ach_scroll_offset, max_scroll)

        #简易滚动条
        if total_content_height > view_height:
            scroll_ratio = self.game.ach_scroll_offset / (total_content_height - view_height)
            bar_h = max(30, int(view_height * view_height / total_content_height))
            bar_y = view_top + scroll_ratio * (view_height - bar_h)
            bar_rect = pygame.Rect(sw - int(14*scale), bar_y, int(8*scale), bar_h)
            pygame.draw.rect(self.screen, GRAY, bar_rect, border_radius=4)

        #返回按钮
        btn = self.game.ach_back_btn
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
            self.game.logger.info("成就页返回菜单")
            self.game.state = GameState.MENU
            self.game.ach_scroll_offset = 0
        btn.draw(self.screen, self.game.font_large, scale)


    def _draw_skill_tree(self):
        """绘制技能树界面"""
        if hasattr(self.game, 'skill_tree_renderer') and self.game.skill_tree_renderer:
            # 处理鼠标和触控输入（拖动视图）
            mouse_pos = pygame.mouse.get_pos()
            mouse_pressed = pygame.mouse.get_pressed()
            self.game.skill_tree_renderer.handle_input(
                mouse_pos, mouse_pressed, self.game.touch_events, self.game.scale
            )
            player_skill_tree = self.game.player.skill_tree if self.game.player else None
            self.game.skill_tree_renderer.draw(
                self.screen, self.game.font, self.game.font_large, self.game.font_title,
                self.game.scale, player_skill_tree
            )
