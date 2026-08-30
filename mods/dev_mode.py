#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开发者模式 Mod - 自由调试工具
================================
功能键位（游戏中按）：
  F1  无敌模式（God Mode）
  F2  一击必杀（One Hit Kill）
  F3  技能无冷却（No Cooldown）
  F4  调试信息面板（Debug HUD）
  F5  清除全场敌人（Kill All）
  F6  回满血（Full Heal）
  F7  +1000 经验
  F8  解锁全部技能
  F9  穿墙/自由移动（Noclip）
  F10 切换游戏速度（0.5x / 1x / 2x / 4x）
  F11 在鼠标位置生成 10 只僵尸
  F12 传送到鼠标位置

注意：此 mod 仅用于开发调试，正式发布时请移除或禁用。
"""

import math
import random

MOD_NAME = "开发者模式"
MOD_VERSION = "1.0.0"
MOD_AUTHOR = "Developer"
MOD_DESCRIPTION = "内置调试工具：无敌、一击必杀、无冷却、生成怪物、传送、调速等。按 F1-F12 使用。"

# ========== 状态 ==========
_state = {
    "god_mode": False,
    "one_hit_kill": False,
    "no_cooldown": False,
    "debug_hud": True,       # 默认开启调试面板
    "noclip": False,
    "time_scale_index": 1,   # 0=0.5x, 1=1x, 2=2x, 3=4x
    "game_ref": None,
    "fps_frames": 0,
    "fps_time": 0,
    "fps": 0,
}

_time_scales = [0.5, 1.0, 2.0, 4.0]


def _toggle(name):
    _state[name] = not _state[name]
    return _state[name]


def _notify(game, text, color=(255, 255, 100)):
    """在玩家头顶显示提示文字"""
    if game and game.player:
        try:
            game.floating_texts.append(FloatingText(
                game.player.x, game.player.y - 60, text, color=color, lifetime=2.0
            ))
        except Exception:
            pass
    print(f"[DevMode] {text}")


def register(api):
    """注册 mod 钩子"""
    api.register("on_game_start", on_game_start)
    api.register("on_game_tick", on_game_tick)
    api.register("on_keydown", on_keydown)
    api.register("on_render_hud", on_render_hud)
    api.register("on_enemy_spawn", on_enemy_spawn)
    api.register("on_player_damage", on_player_damage)
    print(f"[DevMode] {MOD_NAME} v{MOD_VERSION} 已加载，按 F1-F12 使用调试功能")


# ========== 钩子实现 ==========

def on_game_start(game):
    _state["game_ref"] = game
    _state["god_mode"] = False
    _state["one_hit_kill"] = False
    _state["no_cooldown"] = False
    _state["noclip"] = False
    _state["time_scale_index"] = 1
    print("[DevMode] 新游戏开始，调试状态已重置")


def on_game_tick(game, dt):
    _state["game_ref"] = game

    # FPS 计算
    _state["fps_frames"] += 1
    _state["fps_time"] += dt
    if _state["fps_time"] >= 1.0:
        _state["fps"] = int(_state["fps_frames"] / _state["fps_time"])
        _state["fps_frames"] = 0
        _state["fps_time"] = 0

    # 无冷却：重置所有技能冷却
    if _state["no_cooldown"] and game.player:
        try:
            for skill in game.player.skill_tree.skills.values():
                if hasattr(skill, 'cooldown_timer'):
                    skill.cooldown_timer = 0
        except Exception:
            pass

    # 无敌模式：锁血
    if _state["god_mode"] and game.player:
        try:
            game.player.hp = game.player.max_hp
        except Exception:
            pass

    # 穿墙：忽略碰撞（通过直接设置速度实现）
    if _state["noclip"] and game.player:
        try:
            game.player.noclip = True
        except Exception:
            pass
    elif game.player and hasattr(game.player, 'noclip'):
        try:
            game.player.noclip = False
        except Exception:
            pass


def on_keydown(key):
    """按键处理，返回 True 阻止默认行为"""
    game = _state["game_ref"]
    if game is None:
        return False

    # 只在游戏中响应
    try:
        from game import GameState
        if game.state != GameState.PLAYING:
            return False
    except Exception:
        pass

    import pygame

    if key == pygame.K_F1:
        on = _toggle("god_mode")
        _notify(game, f"无敌模式: {'开' if on else '关'}", (255, 100, 100) if on else (200, 200, 200))
        return True

    elif key == pygame.K_F2:
        on = _toggle("one_hit_kill")
        _notify(game, f"一击必杀: {'开' if on else '关'}", (255, 200, 50) if on else (200, 200, 200))
        return True

    elif key == pygame.K_F3:
        on = _toggle("no_cooldown")
        _notify(game, f"无冷却: {'开' if on else '关'}", (100, 200, 255) if on else (200, 200, 200))
        return True

    elif key == pygame.K_F4:
        on = _toggle("debug_hud")
        _notify(game, f"调试面板: {'开' if on else '关'}", (180, 255, 180) if on else (200, 200, 200))
        return True

    elif key == pygame.K_F5:
        count = _kill_all_enemies(game)
        _notify(game, f"已清除 {count} 只敌人", (255, 150, 50))
        return True

    elif key == pygame.K_F6:
        if game.player:
            game.player.hp = game.player.max_hp
            _notify(game, "血量已满", (100, 255, 100))
        return True

    elif key == pygame.K_F7:
        if game.player:
            try:
                game.player.exp += 1000
                game.player.check_level_up()
                _notify(game, "+1000 经验", (100, 200, 255))
            except Exception as e:
                _notify(game, f"经验增加失败: {e}", (255, 100, 100))
        return True

    elif key == pygame.K_F8:
        count = _unlock_all_skills(game)
        _notify(game, f"已解锁 {count} 个技能", (200, 100, 255))
        return True

    elif key == pygame.K_F9:
        on = _toggle("noclip")
        _notify(game, f"穿墙模式: {'开' if on else '关'}", (150, 255, 200) if on else (200, 200, 200))
        return True

    elif key == pygame.K_F10:
        _state["time_scale_index"] = (_state["time_scale_index"] + 1) % len(_time_scales)
        ts = _time_scales[_state["time_scale_index"]]
        # 影响游戏速度（通过修改 dt 倍率）
        try:
            game.dev_time_scale = ts
        except Exception:
            pass
        _notify(game, f"游戏速度: {ts}x", (255, 255, 100))
        return True

    elif key == pygame.K_F11:
        count = _spawn_zombies_at_mouse(game, 10)
        _notify(game, f"已生成 {count} 只僵尸", (255, 150, 150))
        return True

    elif key == pygame.K_F12:
        _teleport_to_mouse(game)
        _notify(game, "已传送", (150, 200, 255))
        return True

    return False


def on_enemy_spawn(enemy):
    """一击必杀：设置敌人血量为1"""
    if _state["one_hit_kill"]:
        try:
            enemy.max_hp = 1
            enemy.hp = 1
        except Exception:
            pass


def on_player_damage(amount):
    """无敌模式：伤害归零"""
    if _state["god_mode"]:
        return 0
    return amount


def on_render_hud(screen, game):
    """渲染调试面板"""
    if not _state["debug_hud"]:
        return

    import pygame

    try:
        scale = game.scale
    except Exception:
        scale = 1.0

    # 调试信息
    lines = []
    lines.append(f"=== 开发者模式 ===")
    lines.append(f"FPS: {_state['fps']}")

    if game.player:
        p = game.player
        lines.append(f"位置: ({int(p.x)}, {int(p.y)})")
        try:
            lines.append(f"血量: {int(p.hp)}/{int(p.max_hp)}")
        except Exception:
            pass
        try:
            lines.append(f"经验: {int(p.exp)}/{int(p.exp_to_next)}  Lv.{p.level}")
        except Exception:
            pass
        try:
            lines.append(f"武器: {p.current_weapon.name if p.current_weapon else 'None'}")
        except Exception:
            pass
        try:
            lines.append(f"Buff: {', '.join(b.name for b in p.buff_manager.buffs.values()) if p.buff_manager and p.buff_manager.buffs else '无'}")
        except Exception:
            pass

    try:
        lines.append(f"敌人: {len(game.enemies)}")
    except Exception:
        pass
    try:
        lines.append(f"粒子: {len(game.particles.particles)}")
    except Exception:
        pass
    try:
        lines.append(f"投射物: {len(game.projectiles)}")
    except Exception:
        pass
    try:
        lines.append(f"分数: {game.score}")
    except Exception:
        pass
    try:
        lines.append(f"时间: {int(game.game_time)}s")
    except Exception:
        pass

    # 开关状态
    lines.append("---")
    lines.append(f"F1无敌: {'ON' if _state['god_mode'] else 'off'}")
    lines.append(f"F2必杀: {'ON' if _state['one_hit_kill'] else 'off'}")
    lines.append(f"F3无CD: {'ON' if _state['no_cooldown'] else 'off'}")
    lines.append(f"F9穿墙: {'ON' if _state['noclip'] else 'off'}")
    lines.append(f"F10速度: {_time_scales[_state['time_scale_index']]}x")

    # 渲染
    try:
        font = game.font_small
    except Exception:
        font = pygame.font.SysFont("arial", 14)

    line_height = int(16 * scale)
    padding = int(8 * scale)
    panel_x = int(10 * scale)
    panel_y = int(10 * scale)

    # 计算面板尺寸
    max_w = 0
    surfaces = []
    for line in lines:
        surf = font.render(line, True, (0, 255, 100))
        surfaces.append(surf)
        max_w = max(max_w, surf.get_width())

    panel_w = max_w + padding * 2
    panel_h = len(surfaces) * line_height + padding * 2

    # 背景
    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 180))
    screen.blit(bg, (panel_x, panel_y))
    pygame.draw.rect(screen, (0, 255, 100), (panel_x, panel_y, panel_w, panel_h), 1)

    # 文字
    for i, surf in enumerate(surfaces):
        screen.blit(surf, (panel_x + padding, panel_y + padding + i * line_height))


# ========== 工具函数 ==========

def _kill_all_enemies(game):
    count = 0
    try:
        for enemy in list(game.enemies):
            try:
                enemy.hp = 0
                enemy.alive = False
                game._on_enemy_death(enemy)
                count += 1
            except Exception:
                pass
    except Exception:
        pass
    return count


def _unlock_all_skills(game):
    count = 0
    try:
        for skill_type, skill in game.player.skill_tree.skills.items():
            try:
                skill.current_level = skill.max_level
                skill.unlocked = True
                count += 1
            except Exception:
                pass
    except Exception:
        pass
    return count


def _spawn_zombies_at_mouse(game, count=10):
    import pygame
    try:
        mouse_pos = pygame.mouse.get_pos()
        wx = mouse_pos[0] / game.scale + game.camera.x
        wy = mouse_pos[1] / game.scale + game.camera.y
    except Exception:
        wx, wy = game.player.x, game.player.y

    spawned = 0
    try:
        from entities import Enemy
        from config import EnemyType
        for i in range(count):
            angle = (i / count) * math.pi * 2
            r = 50 + random.uniform(0, 30)
            ex = wx + math.cos(angle) * r
            ey = wy + math.sin(angle) * r
            try:
                enemy = Enemy(ex, ey, EnemyType.ZOMBIE, 1, game.config.difficulty)
                game.enemies.append(enemy)
                spawned += 1
            except Exception:
                pass
    except Exception as e:
        print(f"[DevMode] 生成怪物失败: {e}")
    return spawned


def _teleport_to_mouse(game):
    import pygame
    try:
        mouse_pos = pygame.mouse.get_pos()
        wx = mouse_pos[0] / game.scale + game.camera.x
        wy = mouse_pos[1] / game.scale + game.camera.y
        game.player.x = wx
        game.player.y = wy
    except Exception as e:
        print(f"[DevMode] 传送失败: {e}")
