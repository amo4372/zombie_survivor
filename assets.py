#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资源管理器 - 音效/音乐/图片，缺失时静默运行或使用彩色占位图"""

import pygame
import os
import random
from config import *

# ============================================================
# 资源清单表（所有支持的资源）
# ============================================================
ASSET_REGISTRY = {
    # --- 图片资源 ---
    "images": {
        # 菜单背景
        "menu_bg":           "assets/images/menu_bg.png",
        "menu_title":        "assets/images/menu_title.png",
        # 游戏内
        "player":            "assets/images/player.png",
        "player_shield":     "assets/images/player_shield.png",
        "zombie_normal":     "assets/images/zombie_normal.png",
        "zombie_fast":       "assets/images/zombie_fast.png",
        "zombie_tank":       "assets/images/zombie_tank.png",
        "zombie_ranged":     "assets/images/zombie_ranged.png",
        "zombie_exploder":   "assets/images/zombie_exploder.png",
        "zombie_crawler":    "assets/images/zombie_crawler.png",
        "zombie_splitter":   "assets/images/zombie_splitter.png",
        "zombie_shield":     "assets/images/zombie_shield.png",
        "zombie_healer":     "assets/images/zombie_healer.png",
        "zombie_phantom":    "assets/images/zombie_phantom.png",
        "boss_long":         "assets/images/boss_long.png",
        "boss_xiang":        "assets/images/boss_xiang.png",
        # 道具
        "item_vaccine":      "assets/images/item_vaccine.png",
        "item_health":       "assets/images/item_health.png",
        "item_ammo":         "assets/images/item_ammo.png",
        "item_speed":        "assets/images/item_speed.png",
        "item_damage":       "assets/images/item_damage.png",
        "item_shield":       "assets/images/item_shield.png",
        # 武器图标
        "weapon_pistol":     "assets/images/weapon_pistol.png",
        "weapon_rifle":      "assets/images/weapon_rifle.png",
        "weapon_shotgun":    "assets/images/weapon_shotgun.png",
        "weapon_sniper":     "assets/images/weapon_sniper.png",
        "weapon_mg":         "assets/images/weapon_mg.png",
        "weapon_rocket":     "assets/images/weapon_rocket.png",
        "weapon_flame":      "assets/images/weapon_flame.png",
        "weapon_crossbow":   "assets/images/weapon_crossbow.png",
        "weapon_grenade":    "assets/images/weapon_grenade.png",
        "weapon_plasma":     "assets/images/weapon_plasma.png",
        "weapon_railgun":    "assets/images/weapon_railgun.png",
        "weapon_minigun":    "assets/images/weapon_minigun.png",
        "weapon_double":     "assets/images/weapon_double.png",
        # 技能图标
        "skill_dash":        "assets/images/skill_dash.png",
        "skill_grenade":     "assets/images/skill_grenade.png",
        "skill_turret":      "assets/images/skill_turret.png",
        "skill_airstrike":   "assets/images/skill_airstrike.png",
        "skill_bash":        "assets/images/skill_bash.png",
        "skill_grapple":     "assets/images/skill_grapple.png",
        "skill_time_slow":   "assets/images/skill_time_slow.png",
        "skill_overload":    "assets/images/skill_overload.png",
        "skill_riot_gear":   "assets/images/skill_riot_gear.png",
        "skill_blink":       "assets/images/skill_blink.png",
        "skill_black_hole":  "assets/images/skill_black_hole.png",
        "skill_ice_nova":    "assets/images/skill_ice_nova.png",
        "skill_chain":       "assets/images/skill_chain.png",
        "skill_berserk":     "assets/images/skill_berserk.png",
        "skill_phantom":     "assets/images/skill_phantom.png",
        "skill_medic":       "assets/images/skill_medic.png",
        "skill_shockwave":   "assets/images/skill_shockwave.png",
        # UI
        "ui_panel":          "assets/images/ui_panel.png",
        "ui_button":         "assets/images/ui_button.png",
        "ui_hp_bar":         "assets/images/ui_hp_bar.png",
        "ui_exp_bar":        "assets/images/ui_exp_bar.png",
        "ui_skill_frame":    "assets/images/ui_skill_frame.png",
        "ui_cursor":         "assets/images/ui_cursor.png",
        # 环境
        "tile_ground":       "assets/images/tile_ground.png",
        "tile_grass":        "assets/images/tile_grass.png",
        "obstacle_wall":     "assets/images/obstacle_wall.png",
        "obstacle_car":      "assets/images/obstacle_car.png",
        "obstacle_building": "assets/images/obstacle_building.png",
        # 特效
        "fx_blood":          "assets/images/fx_blood.png",
        "fx_explosion":      "assets/images/fx_explosion.png",
        "fx_muzzle":         "assets/images/fx_muzzle.png",
        "fx_smoke":          "assets/images/fx_smoke.png",
        "fx_fire":           "assets/images/fx_fire.png",
        "fx_spark":          "assets/images/fx_spark.png",
        "fx_grapple":        "assets/images/fx_grapple.png",
        "fx_shield_hit":     "assets/images/fx_shield_hit.png",
        # === 新Boss ===
        "boss_mutant":       "assets/images/boss_mutant.png",
        "boss_queen":        "assets/images/boss_queen.png",
        "boss_titan":        "assets/images/boss_titan.png",
        # === 新精英怪 ===
        "elite_brute":       "assets/images/elite_brute.png",
        "elite_assassin":    "assets/images/elite_assassin.png",
        "elite_sorcerer":    "assets/images/elite_sorcerer.png",
        "elite_guardian":    "assets/images/elite_guardian.png",
        # === 新僵尸 ===
        "zombie_spitter":    "assets/images/zombie_spitter.png",
        "zombie_leaper":     "assets/images/zombie_leaper.png",
        "zombie_corpse_eater":"assets/images/zombie_corpse_eater.png",
        "zombie_wraith":     "assets/images/zombie_wraith.png",
        # === 新武器 ===
        "weapon_semi_auto_sniper":"assets/images/weapon_semi_auto_sniper.png",
        # === 新道具 ===
        "item_weapon_box":   "assets/images/item_weapon_box.png",
        "item_treasure":     "assets/images/item_treasure.png",
        "item_skill_slot":   "assets/images/item_skill_slot.png",
        "item_buff_charm":   "assets/images/item_buff_charm.png",
        # === 新特效 ===
        "fx_acid":           "assets/images/fx_acid.png",
        "fx_fear":           "assets/images/fx_fear.png",
        "fx_curse":          "assets/images/fx_curse.png",
        "fx_tentacle":       "assets/images/fx_tentacle.png",
        "fx_boulder":        "assets/images/fx_boulder.png",
        "fx_stomp":          "assets/images/fx_stomp.png",
        "fx_freeze":         "assets/images/fx_freeze.png",
        "fx_blood_frenzy":   "assets/images/fx_blood_frenzy.png",
        # === 地图背景 ===
        "bg_school":         "assets/images/bg_school.png",
        "bg_street":         "assets/images/bg_street.png",
        "bg_downtown":       "assets/images/bg_downtown.png",
        "bg_suburb":         "assets/images/bg_suburb.png",
        "bg_nuclear_plant":  "assets/images/bg_nuclear_plant.png",
        # === Buff图标 ===
        "buff_empower":      "assets/images/buff_empower.png",
        "buff_ghost":        "assets/images/buff_ghost.png",
        "buff_thorns":       "assets/images/buff_thorns.png",
        "buff_blood_frenzy": "assets/images/buff_blood_frenzy.png",
        "buff_corrosion":    "assets/images/buff_corrosion.png",
        "buff_fear":         "assets/images/buff_fear.png",
        "buff_curse":        "assets/images/buff_curse.png",
        "buff_mark":         "assets/images/buff_mark.png",
    },
    # --- 音效资源 ---
    "sounds": {
        # 武器音效
        "shoot_pistol":      "assets/sounds/shoot_pistol.wav",
        "shoot_rifle":       "assets/sounds/shoot_rifle.wav",
        "shoot_shotgun":     "assets/sounds/shoot_shotgun.wav",
        "shoot_sniper":      "assets/sounds/shoot_sniper.wav",
        "shoot_mg":          "assets/sounds/shoot_mg.wav",
        "shoot_rocket":      "assets/sounds/shoot_rocket.wav",
        "shoot_flame":       "assets/sounds/shoot_flame.wav",
        "shoot_plasma":      "assets/sounds/shoot_plasma.wav",
        "shoot_railgun":     "assets/sounds/shoot_railgun.wav",
        "shoot_minigun":     "assets/sounds/shoot_minigun.wav",
        "reload":            "assets/sounds/reload.wav",
        "empty_click":       "assets/sounds/empty_click.wav",
        # 技能音效
        "skill_dash":        "assets/sounds/skill_dash.wav",
        "skill_grenade":     "assets/sounds/skill_grenade.wav",
        "skill_turret":      "assets/sounds/skill_turret.wav",
        "skill_airstrike":   "assets/sounds/skill_airstrike.wav",
        "skill_bash":        "assets/sounds/skill_bash.wav",
        "skill_grapple":     "assets/sounds/skill_grapple.wav",
        "skill_time_slow":   "assets/sounds/skill_time_slow.wav",
        "skill_overload":    "assets/sounds/skill_overload.wav",
        "skill_riot_gear":   "assets/sounds/skill_riot_gear.wav",
        "skill_blink":       "assets/sounds/skill_blink.wav",
        "skill_black_hole":  "assets/sounds/skill_black_hole.wav",
        "skill_ice_nova":    "assets/sounds/skill_ice_nova.wav",
        "skill_chain":       "assets/sounds/skill_chain.wav",
        "skill_berserk":     "assets/sounds/skill_berserk.wav",
        "skill_phantom":     "assets/sounds/skill_phantom.wav",
        "skill_medic":       "assets/sounds/skill_medic.wav",
        "skill_shockwave":   "assets/sounds/skill_shockwave.wav",
        # 敌人音效
        "zombie_groan":      "assets/sounds/zombie_groan.wav",
        "zombie_attack":     "assets/sounds/zombie_attack.wav",
        "zombie_death":      "assets/sounds/zombie_death.wav",
        "zombie_explode":    "assets/sounds/zombie_explode.wav",
        "boss_roar":         "assets/sounds/boss_roar.wav",
        "boss_death":        "assets/sounds/boss_death.wav",
        # 交互音效
        "hit_shield":        "assets/sounds/hit_shield.wav",
        "shield_break":      "assets/sounds/shield_break.wav",
        "grapple_hit":       "assets/sounds/grapple_hit.wav",
        "grapple_pull":      "assets/sounds/grapple_pull.wav",
        "pickup_exp":        "assets/sounds/pickup_exp.wav",
        "pickup_item":       "assets/sounds/pickup_item.wav",
        "level_up":          "assets/sounds/level_up.wav",
        "skill_select":      "assets/sounds/skill_select.wav",
        "weapon_switch":     "assets/sounds/weapon_switch.wav",
        "horde_warning":     "assets/sounds/horde_warning.wav",
        "horde_start":       "assets/sounds/horde_start.wav",
        # UI音效
        "ui_click":          "assets/sounds/ui_click.wav",
        "ui_hover":          "assets/sounds/ui_hover.wav",
        "ui_back":           "assets/sounds/ui_back.wav",
        "ui_error":          "assets/sounds/ui_error.wav",
        # 玩家音效
        "player_hurt":       "assets/sounds/player_hurt.wav",
        "player_death":      "assets/sounds/player_death.wav",
        "player_dash":       "assets/sounds/player_dash.wav",
        "footstep":          "assets/sounds/footstep.wav",
        # 环境音效
        "explosion":         "assets/sounds/explosion.wav",
        "fire_burn":         "assets/sounds/fire_burn.wav",
        "electric_spark":    "assets/sounds/electric_spark.wav",
        "glass_break":       "assets/sounds/glass_break.wav",
        # === 新Boss音效 ===
        "boss_mutant_roar":  "assets/sounds/boss_mutant_roar.wav",
        "boss_mutant_combo": "assets/sounds/boss_mutant_combo.wav",
        "boss_queen_summon": "assets/sounds/boss_queen_summon.wav",
        "boss_queen_tentacle":"assets/sounds/boss_queen_tentacle.wav",
        "boss_titan_stomp":  "assets/sounds/boss_titan_stomp.wav",
        "boss_titan_charge": "assets/sounds/boss_titan_charge.wav",
        "boss_titan_boulder":"assets/sounds/boss_titan_boulder.wav",
        # === 新敌人音效 ===
        "zombie_spit":       "assets/sounds/zombie_spit.wav",
        "zombie_leap":       "assets/sounds/zombie_leap.wav",
        "zombie_curse":      "assets/sounds/zombie_curse.wav",
        "elite_heavy_attack":"assets/sounds/elite_heavy_attack.wav",
        "elite_dash":        "assets/sounds/elite_dash.wav",
        "elite_heal":        "assets/sounds/elite_heal.wav",
        # === 新道具音效 ===
        "pickup_weapon_box": "assets/sounds/pickup_weapon_box.wav",
        "pickup_treasure":   "assets/sounds/pickup_treasure.wav",
        "pickup_skill_slot": "assets/sounds/pickup_skill_slot.wav",
        "pickup_buff_charm": "assets/sounds/pickup_buff_charm.wav",
        # === 新特效音效 ===
        "acid_splash":       "assets/sounds/acid_splash.wav",
        "fear_scream":       "assets/sounds/fear_scream.wav",
        "curse_whisper":     "assets/sounds/curse_whisper.wav",
        "tentacle_rise":     "assets/sounds/tentacle_rise.wav",
        "boulder_throw":     "assets/sounds/boulder_throw.wav",
        "stomp_shock":       "assets/sounds/stomp_shock.wav",
        "freeze_break":      "assets/sounds/freeze_break.wav",
    },
    # --- 音乐资源 ---
    "music": {
        # 界面音乐
        "menu":              "assets/music/menu.ogg",
        "victory":           "assets/music/victory.ogg",
        "gameover":          "assets/music/gameover.ogg",
        "ending":            "assets/music/gameover.ogg",
        # 地图专属音乐
        "school":            "assets/music/school.ogg",
        "street":            "assets/music/street.ogg",
        "downtown":          "assets/music/downtown.ogg",
        "suburb":            "assets/music/suburb.ogg",
        "nuclear":           "assets/music/nuclear.ogg",
        # 条件触发音乐
        "boss":              "assets/music/boss.ogg",
        "horde":             "assets/music/horde.ogg",
        "tension":           "assets/music/tension.ogg",
        # 兼容旧名称
        "gameplay":          "assets/music/school.ogg",
        # === 经典原版音乐（保留备用）===
        "menu_classic":      "assets/music/menu_theme.ogg",
        "victory_classic":   "assets/music/victory_theme.ogg",
        "gameover_classic":  "assets/music/gameover_theme.ogg",
        "gameplay_classic":  "assets/music/gameplay_theme.ogg",
        "boss_classic":      "assets/music/boss_theme.ogg",
        "horde_classic":     "assets/music/horde_theme.ogg",
        "ending_classic":    "assets/music/ending_theme.ogg",
        "ending_letgo":      "assets/music/ending_letgo.ogg",
        "ending_perfect":    "assets/music/ending_perfect.ogg",
    }
}


class AssetManager:
    """资源管理器 - 自动加载，缺失时生成彩色占位图或静默跳过"""

    def __init__(self, base_path="."):
        self.base_path = base_path
        self.images = {}
        self.sounds = {}
        self.music = {}
        self._sound_enabled = True
        self._music_enabled = True
        self._volume_sound = 0.7
        self._volume_music = 0.5
        self._current_music = None
        self._music_choice_cache = {}  # 逻辑曲名 -> 实际选择（确定性，避免每帧新旧随机切换）
        self._missing_assets = []  # 记录缺失的资源
        self._loaded_assets = []   # 记录成功加载的资源

        # 占位图缓存
        self._placeholder_cache = {}

        self._init_mixer()
        self._load_all()

    def _init_mixer(self):
        """初始化音频系统，失败时静默禁用"""
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._sound_enabled = True
            self._music_enabled = True
        except Exception as e:
            self._sound_enabled = False
            self._music_enabled = False
            self._missing_assets.append(f"mixer_init: {e}")

    def _load_all(self):
        """加载所有资源"""
        # 加载图片
        for name, path in ASSET_REGISTRY["images"].items():
            full_path = os.path.join(self.base_path, path)
            if os.path.exists(full_path):
                try:
                    img = pygame.image.load(full_path).convert_alpha()
                    self.images[name] = img
                    self._loaded_assets.append(f"[IMG] {name}")
                except Exception as e:
                    self._missing_assets.append(f"[IMG] {name}: {e}")
            else:
                self._missing_assets.append(f"[IMG] {name}: file not found")

        # 加载音效
        if self._sound_enabled:
            for name, path in ASSET_REGISTRY["sounds"].items():
                full_path = os.path.join(self.base_path, path)
                if os.path.exists(full_path):
                    try:
                        snd = pygame.mixer.Sound(full_path)
                        self.sounds[name] = snd
                        self._loaded_assets.append(f"[SND] {name}")
                    except Exception as e:
                        self._missing_assets.append(f"[SND] {name}: {e}")
                else:
                    self._missing_assets.append(f"[SND] {name}: file not found")

        # 记录音乐文件路径（流式播放，不预加载）
        for name, path in ASSET_REGISTRY["music"].items():
            full_path = os.path.join(self.base_path, path)
            if os.path.exists(full_path):
                self.music[name] = full_path
                self._loaded_assets.append(f"[MUS] {name}")
            else:
                self._missing_assets.append(f"[MUS] {name}: file not found")

    # ==================== 占位图生成 ====================

    def _generate_placeholder(self, name, width=64, height=64):
        """生成彩色占位图，带标识文字"""
        cache_key = f"{name}_{width}_{height}"
        if cache_key in self._placeholder_cache:
            return self._placeholder_cache[cache_key]

        # 根据名称哈希生成确定性颜色
        hash_val = sum(ord(c) * (i + 1) for i, c in enumerate(name))
        random.seed(hash_val)
        base_color = (
            random.randint(40, 180),
            random.randint(40, 180),
            random.randint(40, 180)
        )
        random.seed()  # 恢复随机种子

        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        # 背景
        pygame.draw.rect(surf, (*base_color, 200), (0, 0, width, height), border_radius=4)
        # 边框
        pygame.draw.rect(surf, WHITE, (0, 0, width, height), 2, border_radius=4)
        # 对角线
        pygame.draw.line(surf, (*WHITE[:3], 100), (0, 0), (width, height), 1)
        pygame.draw.line(surf, (*WHITE[:3], 100), (width, 0), (0, height), 1)
        # 文字标识
        try:
            font = pygame.font.SysFont("arial", max(8, min(16, width // 4)))
            label = name[:8]
            text = font.render(label, True, WHITE)
            text_rect = text.get_rect(center=(width // 2, height // 2))
            # 文字背景
            bg = pygame.Surface((text_rect.width + 4, text_rect.height + 2), pygame.SRCALPHA)
            bg.fill((*BLACK[:3], 150))
            surf.blit(bg, (text_rect.x - 2, text_rect.y - 1))
            surf.blit(text, text_rect)
        except:
            pass

        self._placeholder_cache[cache_key] = surf
        return surf

    def get_image(self, name, width=None, height=None):
        """获取图片，缺失时返回彩色占位图"""
        if name in self.images:
            img = self.images[name]
            if width and height:
                return pygame.transform.scale(img, (width, height))
            return img
        # 返回占位图
        w = width or 64
        h = height or 64
        return self._generate_placeholder(name, w, h)

    def has_image(self, name):
        return name in self.images

    # ==================== 音效播放 ====================

    def play_sound(self, name, volume_mult=1.0):
        """播放音效，缺失或禁用时静默跳过"""
        if not self._sound_enabled:
            return
        if name in self.sounds:
            try:
                snd = self.sounds[name]
                snd.set_volume(self._volume_sound * volume_mult)
                snd.play()
            except Exception:
                pass

    def play_sound_random(self, names, volume_mult=1.0):
        """从列表中随机播放一个音效"""
        if names:
            self.play_sound(random.choice(names), volume_mult)

    def set_sound_volume(self, volume):
        self._volume_sound = max(0.0, min(1.0, volume))
        for snd in self.sounds.values():
            try:
                snd.set_volume(self._volume_sound)
            except:
                pass

    # ==================== 音乐播放 ====================

    # 逻辑名称 -> 经典版名称的映射（经典版没有的回退到通用gameplay_classic）
    CLASSIC_NAME_MAP = {
        "menu": "menu_classic",
        "victory": "victory_classic",
        "gameover": "gameover_classic",
        "ending": "ending_classic",
        "school": "gameplay_classic",
        "street": "gameplay_classic",
        "downtown": "gameplay_classic",
        "suburb": "gameplay_classic",
        "nuclear": "gameplay_classic",
        "boss": "boss_classic",
        "horde": "horde_classic",
        "tension": "gameplay_classic",
        "gameplay": "gameplay_classic",
    }

    def _resolve_music_name(self, name):
        """确定性地选择音乐文件：优先新版，缺失回退经典版，并缓存一次选择。

        修复：原实现每次调用都用 random.choice 随机选择新版/经典版，而 _draw_menu 每帧
        都会调用 play_music("menu")，导致菜单（及地图/事件音乐）每帧在新旧两个文件之间
        反复切换，造成开头音乐异常/重叠。改为确定性选择并缓存后，同一首逻辑音乐始终
        使用同一文件，不再抖动。
        """
        if name in self._music_choice_cache:
            return self._music_choice_cache[name]
        chosen = name
        if name not in self.music:
            classic = self.CLASSIC_NAME_MAP.get(name)
            if classic and classic in self.music:
                chosen = classic
        self._music_choice_cache[name] = chosen
        return chosen

    def play_music(self, name, loops=-1, fade_ms=1000):
        """播放背景音乐，随机选择新版或经典版，缺失或禁用时静默跳过"""
        if not self._music_enabled:
            return
        actual_name = self._resolve_music_name(name)
        if actual_name in self.music:
            try:
                if self._current_music != actual_name:
                    pygame.mixer.music.load(self.music[actual_name])
                    pygame.mixer.music.set_volume(self._volume_music)
                    pygame.mixer.music.play(loops, fade_ms=fade_ms)
                    self._current_music = actual_name
            except Exception:
                pass

    def stop_music(self, fade_ms=500):
        if self._music_enabled:
            try:
                pygame.mixer.music.fadeout(fade_ms)
                self._current_music = None
            except:
                pass

    def pause_music(self):
        if self._music_enabled:
            try:
                pygame.mixer.music.pause()
            except:
                pass

    def resume_music(self):
        if self._music_enabled:
            try:
                pygame.mixer.music.unpause()
            except:
                pass

    def set_music_volume(self, volume):
        self._volume_music = max(0.0, min(1.0, volume))
        if self._music_enabled:
            try:
                pygame.mixer.music.set_volume(self._volume_music)
            except:
                pass

    # ==================== 音量控制 ====================

    def set_master_volume(self, sound_vol, music_vol):
        self.set_sound_volume(sound_vol)
        self.set_music_volume(music_vol)

    def toggle_sound(self):
        self._sound_enabled = not self._sound_enabled
        return self._sound_enabled

    def toggle_music(self):
        self._music_enabled = not self._music_enabled
        if not self._music_enabled:
            self.stop_music()
        return self._music_enabled

    # ==================== 状态查询 ====================

    def get_status(self):
        """获取资源加载状态报告"""
        return {
            "sound_enabled": self._sound_enabled,
            "music_enabled": self._music_enabled,
            "sound_volume": self._volume_sound,
            "music_volume": self._volume_music,
            "images_loaded": len(self.images),
            "images_total": len(ASSET_REGISTRY["images"]),
            "sounds_loaded": len(self.sounds),
            "sounds_total": len(ASSET_REGISTRY["sounds"]),
            "music_loaded": len(self.music),
            "music_total": len(ASSET_REGISTRY["music"]),
            "loaded": self._loaded_assets,
            "missing": self._missing_assets,
        }

    def print_status(self):
        """打印资源状态到日志"""
        status = self.get_status()
        print(f"[ASSET] 图片: {status['images_loaded']}/{status['images_total']}")
        print(f"[ASSET] 音效: {status['sounds_loaded']}/{status['sounds_total']}")
        print(f"[ASSET] 音乐: {status['music_loaded']}/{status['music_total']}")
        print(f"[ASSET] 缺失资源: {len(status['missing'])} 项")


# 便捷音效名称映射（用于游戏逻辑中快速调用）
SOUND_MAP = {
    # 武器
    "pistol": ["shoot_pistol"],
    "rifle": ["shoot_rifle"],
    "shotgun": ["shoot_shotgun"],
    "sniper": ["shoot_sniper"],
    "machine_gun": ["shoot_mg"],
    "rocket": ["shoot_rocket"],
    "flamethrower": ["shoot_flame"],
    "plasma": ["shoot_plasma"],
    "railgun": ["shoot_railgun"],
    "minigun": ["shoot_minigun"],
    "crossbow": ["shoot_sniper"],
    "grenade_launcher": ["shoot_rocket"],
    "double_barrel": ["shoot_shotgun"],
    "reload": ["reload"],
    "empty": ["empty_click"],
    # 技能
    "dash": ["skill_dash"],
    "grenade": ["skill_grenade"],
    "turret": ["skill_turret"],
    "airstrike": ["skill_airstrike"],
    "bash": ["skill_bash"],
    "grapple": ["skill_grapple"],
    "time_slow": ["skill_time_slow"],
    "overload": ["skill_overload"],
    "riot_gear": ["skill_riot_gear"],
    "blink": ["skill_blink"],
    "black_hole": ["skill_black_hole"],
    "ice_nova": ["skill_ice_nova"],
    "chain_lightning": ["skill_chain"],
    "berserk": ["skill_berserk"],
    "phantom_strike": ["skill_phantom"],
    "medic_pod": ["skill_medic"],
    "shockwave": ["skill_shockwave"],
    # 敌人
    "zombie_groan": ["zombie_groan"],
    "zombie_attack": ["zombie_attack"],
    "zombie_death": ["zombie_death"],
    "zombie_explode": ["zombie_explode"],
    "boss_roar": ["boss_roar"],
    "boss_death": ["boss_death"],
    # 交互
    "hit_shield": ["hit_shield"],
    "shield_break": ["shield_break"],
    "grapple_hit": ["grapple_hit"],
    "grapple_pull": ["grapple_pull"],
    "pickup_exp": ["pickup_exp"],
    "pickup_item": ["pickup_item"],
    "level_up": ["level_up"],
    "skill_select": ["skill_select"],
    "weapon_switch": ["weapon_switch"],
    "horde_warning": ["horde_warning"],
    "horde_start": ["horde_start"],
    # UI
    "ui_click": ["ui_click"],
    "ui_hover": ["ui_hover"],
    "ui_back": ["ui_back"],
    "ui_error": ["ui_error"],
    # 玩家
    "player_hurt": ["player_hurt"],
    "player_death": ["player_death"],
    "player_dash": ["player_dash"],
    "footstep": ["footstep"],
    # 环境
    "explosion": ["explosion"],
    "fire_burn": ["fire_burn"],
    "electric": ["electric_spark"],
    "glass_break": ["glass_break"],
    # 新武器
    "semi_auto_sniper": ["shoot_sniper"],
    # 新Boss
    "boss_mutant_roar": ["boss_mutant_roar"],
    "boss_mutant_combo": ["boss_mutant_combo"],
    "boss_queen_summon": ["boss_queen_summon"],
    "boss_queen_tentacle": ["boss_queen_tentacle"],
    "boss_titan_stomp": ["boss_titan_stomp"],
    "boss_titan_charge": ["boss_titan_charge"],
    "boss_titan_boulder": ["boss_titan_boulder"],
    # 新敌人
    "zombie_spit": ["zombie_spit"],
    "zombie_leap": ["zombie_leap"],
    "zombie_curse": ["zombie_curse"],
    "elite_heavy_attack": ["elite_heavy_attack"],
    "elite_dash": ["elite_dash"],
    "elite_heal": ["elite_heal"],
    # 新道具
    "pickup_weapon_box": ["pickup_weapon_box"],
    "pickup_treasure": ["pickup_treasure"],
    "pickup_skill_slot": ["pickup_skill_slot"],
    "pickup_buff_charm": ["pickup_buff_charm"],
    # 新特效
    "acid_splash": ["acid_splash"],
    "fear_scream": ["fear_scream"],
    "curse_whisper": ["curse_whisper"],
    "tentacle_rise": ["tentacle_rise"],
    "boulder_throw": ["boulder_throw"],
    "stomp_shock": ["stomp_shock"],
    "freeze_break": ["freeze_break"],
}

MUSIC_MAP = {
    # 界面
    "menu": "menu",
    "victory": "victory",
    "gameover": "gameover",
    "ending": "ending",
    # 地图专属
    "school": "school",
    "street": "street",
    "downtown": "downtown",
    "suburb": "suburb",
    "nuclear": "nuclear",
    # 条件触发
    "boss": "boss",
    "horde": "horde",
    "tension": "tension",
    # 兼容
    "gameplay": "gameplay",
}

# 地图类型到音乐名称的映射
MAP_MUSIC_MAP = {
    "school": "school",
    "street": "street",
    "downtown": "downtown",
    "suburb": "suburb",
    "nuclear_plant": "nuclear",
}
