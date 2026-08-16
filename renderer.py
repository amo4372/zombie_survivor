#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染系统模块 - 黑暗色调版：技能卡选择、防爆套装动画、半透明范围圈"""

import pygame
import math
import random
from config import (GameState, ControlMode, GameMode, 
                   WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, 
                   GRAY, DARK_GRAY, CYAN, DARK_RED, PURPLE, LIGHT_GRAY,
                   GOLD, AMBER, CRIMSON, CHARCOAL, VOID_BLACK, DARK_BLUE)

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

    def render(self):
        state = self.game.state

        if state == GameState.MENU:
            self._draw_menu()
        elif state == GameState.SETTINGS:
            self._draw_settings()
        elif state == GameState.TUTORIAL:
            self._draw_tutorial()
        elif state == GameState.PLAYING:
            self._draw_playing()
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
        elif state == GameState.ENDING:
            self._draw_ending()
        elif state == GameState.RECORDS:
            self._draw_records()
        elif state == GameState.ACHIEVEMENTS:
            self._draw_achievements()

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
            btn.base_y = (240 + i * 60)
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                self.game.logger.info(f"菜单按钮 '{btn.text}' 被点击")
                if i == 0:
                    self.game.start_game()
                elif i == 1:
                    self.game.state = GameState.RECORDS
                elif i ==2:
                    self.game.state = GameState.ACHIEVEMENTS
                elif i ==3:
                    self.game.state = GameState.SETTINGS
                elif i ==4:
                    self.game.state = GameState.TUTORIAL
                elif i ==5:
                    self.game.running = False
            btn.draw(self.screen, self.game.font_large, scale)

        version = self.game.font_small.render("v4.0 - 黑暗尸潮", True, GRAY)
        self.screen.blit(version, (10, self.game.scaled_height - 30))

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
            btn.base_y = (180 + i * 65)
            if i == 0:
                btn.text = f"控制: {'触控' if self.game.config.control_mode == ControlMode.TOUCH else '键控'}"
            elif i == 1:
                btn.text = f"模式: {'无尽' if self.game.config.game_mode == GameMode.ENDLESS else '限时'}"
            elif i == 2:
                btn.text = f"难度: {self.game.config.difficulty}"

            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, scale):
                self.game.logger.info(f"设置按钮 '{btn.text}' 被点击")
                if i == 0:
                    self.game.config.control_mode = ControlMode.TOUCH if self.game.config.control_mode == ControlMode.KEYBOARD else ControlMode.KEYBOARD
                elif i == 1:
                    self.game.config.game_mode = GameMode.ENDLESS if self.game.config.game_mode == GameMode.TIMED else GameMode.TIMED
                elif i == 2:
                    difficulties = ["简单", "普通", "困难", "地狱"]
                    idx = difficulties.index(self.game.config.difficulty) if self.game.config.difficulty in difficulties else 1
                    self.game.config.difficulty = difficulties[(idx + 1) % len(difficulties)]
                elif i == 3:
                    self.game.config.save()
                    self.game.state = GameState.MENU

            btn.draw(self.screen, self.game.font_large, scale)

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
            hint = self.game.font_small.render("↑ 继续上滑", True, GRAY)
            self.screen.blit(hint, (sw // 2 - 40, 10))
        if max_scroll > 0 and self.game.tutorial_scroll_offset < max_scroll:
            hint = self.game.font_small.render("↓ 继续下滑", True, GRAY)
            self.screen.blit(hint, (sw // 2 - 40, self.game.scaled_height - 30))

    def _draw_playing(self):
        if not self.game.world or not self.game.player:
            return

        scale = self.game.scale
        camera = self.game.camera
        player = self.game.player

        # 计算带抖动的相机偏移
        shake_x = camera.shake_x
        shake_y = camera.shake_y
        cam_x = camera.x - shake_x
        cam_y = camera.y - shake_y

        # 绘制世界
        self.game.world.draw(self.screen, cam_x, cam_y, scale)

        # 绘制经验球
        for orb in self.game.exp_orbs:
            orb.draw(self.screen, cam_x, cam_y, scale)

        # 绘制敌人
        for enemy in self.game.enemies:
            enemy.draw(self.screen, cam_x, cam_y, self.game.font, scale)

        # 绘制玩家
        player.draw(self.screen, cam_x, cam_y, self.game.font, scale)

        # 绘制投射物
        for proj in self.game.projectiles:
            proj.draw(self.screen, cam_x, cam_y, scale)

        for proj in self.game.enemy_projectiles:
            proj.draw(self.screen, cam_x, cam_y, scale)

        # 绘制粒子
        self.game.particles.draw(self.screen, cam_x, cam_y, scale)

        # 绘制伤害数字
        for dn in self.game.damage_numbers:
            dn.draw(self.screen, self.game.font, cam_x, cam_y, scale)

        # 绘制浮动文字
        for ft in self.game.floating_texts:
            ft.draw(self.screen, self.game.font, cam_x, cam_y, scale)

        # 绘制创伤效果（屏幕边缘血溅）
        self._draw_trauma_effect()

        # 绘制枪口闪光
        self._draw_muzzle_flash()

        # 绘制HUD
        self._draw_hud()

        # 绘制触控控件
        if self.game.config.control_mode == ControlMode.TOUCH or self.game.is_android:
            self.game.joystick.draw(self.screen, scale)

            if hasattr(self.game, 'aim_button') and self.game.aim_button:
                self.game.aim_button.draw(self.screen, self.game.font_small, scale)

            for name, btn in self.game.touch_buttons.items():
                if name == "shoot" and player.riot_gear.equipped:
                    original_label = btn.label
                    original_color = btn.color
                    btn.label = "击"
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
            if self.game.skill_wheel_active:
                self.game.skill_wheel.draw(self.screen, self.game.font, self.game.font_large, scale)
            if self.game.weapon_wheel_active:
                self.game.weapon_wheel.draw(self.screen, self.game.font, self.game.font_large, scale)

        # ==========键鼠长按G瞄准预览（复用SkillCaster原生绘制逻辑） ==========
        if self.game.config.control_mode == ControlMode.KEYBOARD and self.game.skill_caster.is_aiming:
            self.game.skill_caster._draw_aim_preview(self.screen, self.game.selected_skill, self.game.scale)
            
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

    def _draw_hud(self):
        scale = self.game.scale
        sw = self.game.scaled_width
        player = self.game.player

        # === 屏幕上方中央显示时间（紧迫感） ===
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
            # 错误效果闪烁，下移，给尸潮UI留出空间
            glitch_text_surf = self.game.font_small.render("SYSTEM ERROR: TIME_OVERFLOW", True, RED)
            glitch_rect = glitch_text_surf.get_rect(center=(sw // 2, int(52 * scale)))
        else:
            if is_countdown:
                # 解析 mm:ss 格式，按剩余总秒数判断是否紧急变红
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
        if glitch_text_surf and glitch_rect:
            if int(pygame.time.get_ticks() / 800) % 2 == 0:
                self.screen.blit(glitch_text_surf, glitch_rect)

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

        # HP条 - 左上方
        hp_ratio = player.hp / player.max_hp
        bar_w = int(180 * scale)
        bar_h = max(3, int(16 * scale))
        pygame.draw.rect(self.screen, DARK_RED, (15, 15, bar_w, bar_h))
        pygame.draw.rect(self.screen, RED if hp_ratio > 0.3 else CRIMSON, (15, 15, int(bar_w * hp_ratio), bar_h))
        pygame.draw.rect(self.screen, WHITE, (15, 15, bar_w, bar_h), max(1, int(scale)))
        hp_text = self.game.font.render(f"{int(player.hp)}/{int(player.max_hp)}", True, WHITE)
        self.screen.blit(hp_text, (20, 16))

        # 经验条
        exp_ratio = player.exp / player.exp_to_level
        exp_h = max(2, int(10 * scale))
        pygame.draw.rect(self.screen, DARK_GRAY, (15, 15 + bar_h + 5, bar_w, exp_h))
        pygame.draw.rect(self.screen, CYAN, (15, 15 + bar_h + 5, int(bar_w * exp_ratio), exp_h))
        pygame.draw.rect(self.screen, WHITE, (15, 15 + bar_h + 5, bar_w, exp_h), max(1, int(scale)))

        # 等级和分数
        level_text = self.game.font.render(f"Lv.{player.level}  分:{player.score}", True, GOLD)
        self.screen.blit(level_text, (15, 15 + bar_h + exp_h + 10))

        # 武器显示
        weapon = player.get_current_weapon()
        weapon_text = self.game.font.render(f"{weapon.name} Lv.{weapon.level}", True, WHITE)
        self.screen.blit(weapon_text, (15, 15 + bar_h + exp_h + 35))

        # 弹药显示
        if hasattr(weapon, 'get_ammo_text'):
            ammo_text = self.game.font_small.render(weapon.get_ammo_text(), True, GRAY)
            self.screen.blit(ammo_text, (15, 15 + bar_h + exp_h + 58))

        # 武器切换提示
        if len(player.weapons) > 1:
            switch_text = self.game.font_small.render(f"按R切换 ({len(player.weapons)}种)", True, GRAY)
            self.screen.blit(switch_text, (15, 15 + bar_h + exp_h + 75))

        # 当前技能显示
        skill = player.skill_tree.get_skill(self.game.selected_skill)
        if skill:
            skill_text = self.game.font.render(f"技能: {skill.name} (G)", True, GOLD)
            self.screen.blit(skill_text, (15, 15 + bar_h + exp_h + 95))

        # ==========【仅键控模式】显示：下一个技能 / 下一把武器 ==========
        if self.game.config.control_mode == ControlMode.KEYBOARD:
            # 下一个技能
            unlocked_skills = self.game._get_unlocked_skills()
            if len(unlocked_skills) > 0:
                curr_idx = unlocked_skills.index(self.game.selected_skill) if self.game.selected_skill in unlocked_skills else -1
                next_skill_idx = (curr_idx + 1) % len(unlocked_skills)
                next_skill_type = unlocked_skills[next_skill_idx]
                next_skill = player.skill_tree.get_skill(next_skill_type)
                next_skill_name = next_skill.name if next_skill else "?"
                next_skill_text = self.game.font_small.render(f"下技能(Tab): {next_skill_name}", True, AMBER)
                self.screen.blit(next_skill_text, (15, 15 + bar_h + exp_h + 118))

            # 下一把武器
            if len(player.weapons) > 1:
                curr_w_idx = player.current_weapon_idx
                next_w_idx = (curr_w_idx + 1) % len(player.weapons)
                next_weapon = player.weapons[next_w_idx]
                next_weapon_text = self.game.font_small.render(f"下武器(R): {next_weapon.name}", True, PURPLE)
                self.screen.blit(next_weapon_text, (15, 15 + bar_h + exp_h + 140))
                
        status_lines = []
        riot = player.riot_gear
        weapon = player.get_current_weapon()

        # 防爆套装相关状态
        if self.game.riot_anim_state == "equipping":
            progress = 1 - (self.game.riot_anim_timer / self.game.riot_anim_duration)
            status_lines.append(f"防爆装备中... {int(progress*100)}%")
        elif self.game.riot_anim_state == "unequipping":
            progress = 1 - (self.game.riot_anim_timer / self.game.riot_anim_duration)
            status_lines.append(f"防爆卸下中... {int(progress*100)}%")
        elif riot.equipped:
            status_lines.append("✅ 防爆套装已装备")
            if riot.shield_broken:
                status_lines.append("⚠ 观察窗已破碎")
            else:
                vw_ratio = riot.viewing_window_hp / riot.max_viewing_window_hp
                status_lines.append(f"观察窗: {int(vw_ratio*100)}%")
            if riot.has_debuff:
                status_lines.append("❗装备超时，移动减速")
            status_lines.append(f"盾牌体力: {int(riot.stamina)}")
        elif riot.riot_gear_cd_timer > 0:
            status_lines.append(f"防爆套装冷却: {riot.riot_gear_cd_timer:.1f}s")

        # --------【仅键控模式：追加武器、主动技能冷却信息】 --------
        if self.game.config.control_mode == ControlMode.KEYBOARD:
            # 武器射击冷却、换弹CD
            if hasattr(weapon,"shoot_cd_timer") and weapon.shoot_cd_timer > 0:
                status_lines.append(f"射击冷却: {weapon.shoot_cd_timer:.2f}s")
            if hasattr(weapon,"reload_timer") and weapon.reload_timer > 0:
                status_lines.append(f"换弹: {weapon.reload_timer:.1f}s")

            # 玩家active_skills字典：存放正在冷却的主动技能
            for sk_type, cd_left in player.active_skills.items():
                sk_obj = player.skill_tree.get_skill(sk_type)
                sk_name = sk_obj.name if sk_obj else str(sk_type)
                status_lines.append(f"[{sk_name}] CD: {cd_left:.1f}s")

        # 循环绘制全部状态行，自动向下偏移，杜绝重叠
        stat_start_y = int(15 + bar_h + exp_h + 120)
        stat_line_h = int(24 * scale)
        draw_y = stat_start_y
        for line_txt in status_lines:
            surf = self.game.font_small.render(line_txt, True, WHITE)
            self.screen.blit(surf, (int(15*scale), draw_y))
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
            if btn.update(mouse_pos, mouse_pressed, self.game.touch_events, self.game.scale):
                self.game.logger.info(f"暂停按钮 '{btn.text}' 被点击")
                if i == 0:
                    self.game.state = GameState.PLAYING
                elif i == 1:
                    self.game.state = GameState.MENU
            btn.draw(self.screen, self.game.font_large, self.game.scale)

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

    def _draw_trauma_effect(self):
        """绘制摄像机创伤效果 - 超增强屏幕边缘血红色渐变"""
        player = self.game.player
        if not player or player.trauma <= 0:
            return

        scale = self.game.scale
        sw = self.game.scaled_width
        sh = self.game.scaled_height
        trauma = player.trauma

        # 增强边缘宽度
        edge_width = int(120 * scale * trauma)
        alpha = int(220 * trauma)

        # 上边缘 - 更宽更浓
        top_surf = pygame.Surface((sw, edge_width), pygame.SRCALPHA)
        for y in range(edge_width):
            a = int(alpha * (1 - y / edge_width) ** 0.7)
            pygame.draw.line(top_surf, (200, 10, 10, a), (0, y), (sw, y))
        self.game.screen.blit(top_surf, (0, 0))

        # 下边缘
        bottom_surf = pygame.Surface((sw, edge_width), pygame.SRCALPHA)
        for y in range(edge_width):
            a = int(alpha * (1 - y / edge_width) ** 0.7)
            pygame.draw.line(bottom_surf, (200, 10, 10, a), (0, edge_width - y - 1), (sw, edge_width - y - 1))
        self.game.screen.blit(bottom_surf, (0, sh - edge_width))

        # 左边缘
        left_surf = pygame.Surface((edge_width, sh), pygame.SRCALPHA)
        for x in range(edge_width):
            a = int(alpha * (1 - x / edge_width) ** 0.7)
            pygame.draw.line(left_surf, (200, 10, 10, a), (x, 0), (x, sh))
        self.game.screen.blit(left_surf, (0, 0))

        # 右边缘
        right_surf = pygame.Surface((edge_width, sh), pygame.SRCALPHA)
        for x in range(edge_width):
            a = int(alpha * (1 - x / edge_width) ** 0.7)
            pygame.draw.line(right_surf, (200, 10, 10, a), (edge_width - x - 1, 0), (edge_width - x - 1, sh))
        self.game.screen.blit(right_surf, (sw - edge_width, 0))

        # 四角强化
        corner_size = int(60 * scale * trauma)
        for cx, cy in [(0, 0), (sw, 0), (0, sh), (sw, sh)]:
            corner_surf = pygame.Surface((corner_size * 2, corner_size * 2), pygame.SRCALPHA)
            for r in range(corner_size, 0, -2):
                a = int(alpha * (r / corner_size))
                pygame.draw.circle(corner_surf, (220, 20, 20, a), (corner_size, corner_size), r)
            dx = -corner_size if cx == 0 else -corner_size
            dy = -corner_size if cy == 0 else -corner_size
            self.game.screen.blit(corner_surf, (cx + dx, cy + dy))

        # 随机血溅点 - 更多更大
        if trauma > 0.2:
            num_splatters = int(trauma * 15)
            for _ in range(num_splatters):
                sx = random.randint(0, sw)
                sy = random.randint(0, sh)
                max_val = max(8, int(35 * scale * trauma))
                sr = random.randint(8, max_val)
                sa = int(random.randint(80, 200) * trauma)
                splatter_surf = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
                pygame.draw.circle(splatter_surf, (180, 15, 15, sa), (sr, sr), sr)
                self.game.screen.blit(splatter_surf, (sx - sr, sy - sr))

        # 心跳效果（低血量时）- 更强
        if player.hp / player.max_hp < 0.3:
            heartbeat = abs(math.sin(pygame.time.get_ticks() / 180)) * trauma * 0.5
            overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            overlay.fill((200, 10, 10, int(50 * heartbeat)))
            self.game.screen.blit(overlay, (0, 0))
            # 心跳震动
            if heartbeat > 0.7:
                self.game.camera.shake_intensity = max(self.game.camera.shake_intensity, 3)

        # 屏幕暗角
        if trauma > 0.5:
            vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for r in range(int(min(sw, sh) // 2), int(min(sw, sh) // 2 * 0.3), -10):
                a = int((trauma - 0.5) * 2 * 30 * (1 - r / (min(sw, sh) // 2)))
                pygame.draw.rect(vignette, (0, 0, 0, a), (0, 0, sw, sh), border_radius=r)
            self.game.screen.blit(vignette, (0, 0))

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
            status = "✓" if ach_data["unlocked"] else "○"
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

        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)
        y = view_top - self.game.ach_scroll_offset

        group_order = ["战斗","生存","技能武器","结局挑战","隐藏","其他"]
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
                    prefix = "✓ "
                else:
                    col = DARK_GRAY
                    prefix = "○ "
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

        #简易滚动条
        total_content_height = y - (view_top - self.game.ach_scroll_offset)
        view_height = view_bottom - view_top
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
