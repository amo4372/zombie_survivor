#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高级示例 Mod - 展示 Mod API 的各种用法
功能：
1. 每波结束生成奖励宝箱
2. 玩家低血量时触发狂暴（伤害+50%）
3. 自定义HUD显示连击数
4. 按 F 键在玩家周围生成爆炸
5. 击杀计数持久化
"""

MOD_NAME = "高级功能演示"
MOD_VERSION = "1.2.0"
MOD_AUTHOR = "Mod开发指南"
MOD_DESCRIPTION = "展示Mod API完整用法的示例Mod：波次奖励、低血量狂暴、连击HUD、按键技能、数据持久化。按F键释放范围爆炸！"

import pygame
import math
from config import EnemyType

MOD_ID = "advanced_demo"
combo_count = 0
combo_timer = 0
total_kills = 0
berserk_active = False

def register(mod_loader):
    api = mod_loader.mod_api
    
    # === 游戏开始：重置状态 + 加载数据 ===
    def on_game_start(game):
        global combo_count, combo_timer, berserk_active, total_kills
        combo_count = 0
        combo_timer = 0
        berserk_active = False
        # 游戏初始化后再加载数据
        try:
            data = api.load_mod_data(MOD_ID, {"total_kills": 0})
            total_kills = data.get("total_kills", 0)
        except Exception:
            total_kills = 0
        api.show_message(f"高级Mod已激活！历史总击杀: {total_kills}")
    
    # === 每帧更新：连击计时 ===
    def on_game_tick(game, dt):
        global combo_timer, berserk_active
        if combo_timer > 0:
            combo_timer -= dt
            if combo_timer <= 0:
                combo_count = 0
        
        # 低血量狂暴检测
        player = api.get_player()
        if player:
            if player.hp < player.max_hp * 0.3 and not berserk_active:
                berserk_active = True
                api.show_message("狂暴模式激活！伤害+50%")
                api.spawn_particles(player.x, player.y, (255, 50, 50), count=30, speed=150)
            elif player.hp >= player.max_hp * 0.3 and berserk_active:
                berserk_active = False
    
    # === 敌人死亡：连击+计数 ===
    def on_enemy_death(enemy, killer):
        global combo_count, combo_timer, total_kills
        combo_count += 1
        combo_timer = 3.0  # 3秒连击窗口
        total_kills += 1
        
        # 每50杀保存
        if total_kills % 50 == 0:
            api.save_mod_data(MOD_ID, {"total_kills": total_kills})
        
        # 高连击特效
        if combo_count >= 10:
            api.spawn_floating_text(enemy.x, enemy.y - 30, f"{combo_count} 连击!", (255, 200, 50))
    
    # === 玩家受伤：狂暴减伤 ===
    def on_player_damage(amount):
        if berserk_active:
            return int(amount * 0.7)  # 狂暴时减伤30%
        return amount
    
    # === 波次完成：生成奖励 ===
    def on_wave_complete(wave_number):
        player = api.get_player()
        if player:
            # 在玩家附近生成宝箱
            from world import ItemType
            import random
            angle = random.uniform(0, math.pi * 2)
            dist = 150
            x = player.x + math.cos(angle) * dist
            y = player.y + math.sin(angle) * dist
            api.spawn_item(x, y, ItemType.TREASURE_CHEST)
            api.show_message(f"波次 {wave_number} 完成！奖励宝箱已生成")
            api.spawn_particles(x, y, (255, 215, 0), count=25, speed=100)
    
    # === 自定义HUD：连击显示 ===
    def on_render_hud(screen, game):
        if combo_count > 0:
            font = pygame.font.SysFont("SimHei", 28, bold=True)
            color = (255, 100, 50) if combo_count >= 10 else (255, 200, 100)
            text = font.render(f"连击 x{combo_count}", True, color)
            screen.blit(text, (game.scaled_width // 2 - 60, 80))
            
            # 连击计时条
            bar_w = 100
            bar_h = 6
            bar_x = game.scaled_width // 2 - bar_w // 2
            bar_y = 115
            pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h))
            fill_w = int(bar_w * min(1, combo_timer / 3.0))
            pygame.draw.rect(screen, (255, 150, 50), (bar_x, bar_y, fill_w, bar_h))
        
        # 狂暴状态指示
        if berserk_active:
            font = pygame.font.SysFont("SimHei", 22, bold=True)
            text = font.render("狂暴中!", True, (255, 50, 50))
            screen.blit(text, (game.scaled_width // 2 - 40, 130))
    
    # === 按键技能：F键范围爆炸 ===
    def on_keydown(key):
        if key == pygame.K_f:
            player = api.get_player()
            if player:
                # 对周围敌人造成伤害
                enemies = api.get_enemies()
                hit_count = 0
                for enemy in enemies:
                    dist = math.hypot(enemy.x - player.x, enemy.y - player.y)
                    if dist < 200:
                        api.damage_enemy(enemy, 100, damage_type="aoe")
                        hit_count += 1
                
                # 特效
                api.spawn_particles(player.x, player.y, (255, 150, 50), count=50, speed=200, life=0.8)
                api.screen_shake(20, 0.4)
                api.play_sound("grenade_explode")
                api.show_message(f"范围爆炸！命中 {hit_count} 个敌人")
                return True  # 阻止默认处理
        return False
    
    # === 游戏结束：保存数据 ===
    def on_game_over(result_data):
        api.save_mod_data(MOD_ID, {"total_kills": total_kills})
        api.log(f"本局结束，总击杀: {total_kills}")
    
    # 注册所有钩子
    mod_loader.register("on_game_start", on_game_start)
    mod_loader.register("on_game_tick", on_game_tick)
    mod_loader.register("on_enemy_death", on_enemy_death)
    mod_loader.register("on_player_damage", on_player_damage)
    mod_loader.register("on_wave_complete", on_wave_complete)
    mod_loader.register("on_render_hud", on_render_hud)
    mod_loader.register("on_keydown", on_keydown)
    mod_loader.register("on_game_over", on_game_over)
    
    api.log("高级功能演示Mod 加载完成")
