#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mod 系统 - 简单的模组加载框架

支持：
- 扫描 mods 目录加载 mod
- 钩子系统（on_game_start, on_enemy_spawn, on_player_damage 等）
- mod 元数据（名称、版本、作者、描述）
- mod 启用/禁用状态持久化
"""

import os
import json
import importlib.util
from dataclasses import dataclass, field
from typing import Dict, List, Any, Callable, Optional


@dataclass
class ModInfo:
    """Mod 元数据"""
    id: str
    name: str
    version: str = "1.0.0"
    author: str = "Unknown"
    description: str = ""
    enabled: bool = True
    path: str = ""
    module: Any = None


class ModHook:
    """钩子系统 - 允许 mod 注册回调函数"""
    
    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {}
        self.mod_api = None  # 全局 ModAPI 引用，在模块底部设置
    
    def register(self, hook_name: str, callback: Callable):
        """注册钩子回调"""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(callback)
    
    def _inject_globals(self, callback):
        """向回调的全局命名空间注入常用游戏类
        优先使用 game.py 设置的 _global_classes（已加载的类引用），
        避免在 mod_loader 中 import 导致循环依赖或静默失败。"""
        try:
            g = callback.__globals__
        except AttributeError:
            return
        classes = getattr(self, '_global_classes', None)
        if classes:
            for _name, _cls in classes.items():
                if _name not in g:
                    g[_name] = _cls
        else:
            # 兜底：直接 import（可能因循环依赖失败）
            if 'FloatingText' not in g:
                try:
                    from ui import FloatingText
                    g['FloatingText'] = FloatingText
                except Exception:
                    pass
            for _name in ('WeaponType', 'EnemyType', 'BuffType', 'SkillType'):
                if _name not in g:
                    try:
                        import config as _cfg
                        g[_name] = getattr(_cfg, _name)
                    except Exception:
                        pass

    def trigger(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """触发钩子，返回所有回调的结果"""
        results = []
        if hook_name in self._hooks:
            for callback in self._hooks[hook_name]:
                self._inject_globals(callback)
                try:
                    result = callback(*args, **kwargs)
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    print(f"[Mod] 钩子 {hook_name} 执行错误: {e}")
        return results
    
    def clear(self):
        """清除所有钩子"""
        self._hooks.clear()


# 全局钩子实例
mod_hooks = ModHook()

# 全局 mod 列表
_loaded_mods: List[ModInfo] = []
_mods_enabled: Dict[str, bool] = {}

# 配置文件路径
_MODS_CONFIG = os.path.join(os.path.dirname(__file__), "mods_config.json")
_MODS_DIR = os.path.join(os.path.dirname(__file__), "mods")


def _load_mods_config():
    """加载 mod 启用状态配置"""
    global _mods_enabled
    if os.path.exists(_MODS_CONFIG):
        try:
            with open(_MODS_CONFIG, 'r', encoding='utf-8') as f:
                _mods_enabled = json.load(f)
        except:
            _mods_enabled = {}
    else:
        _mods_enabled = {}


def _save_mods_config():
    """保存 mod 启用状态配置"""
    try:
        with open(_MODS_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(_mods_enabled, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Mod] 保存配置失败: {e}")


def get_mods_dir() -> str:
    """获取 mods 目录路径"""
    if not os.path.exists(_MODS_DIR):
        os.makedirs(_MODS_DIR, exist_ok=True)
        # 创建 README
        readme_path = os.path.join(_MODS_DIR, "README.txt")
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write("""丧尸幸存者 Mod 目录
====================

将 mod 文件夹或 .py 文件放入此目录即可加载。

Mod 结构：
- 每个 mod 可以是一个 .py 文件或包含 __init__.py 的文件夹
- mod 中定义 register(mod_loader) 函数来注册钩子和内容

可用钩子：
- on_game_start(game) - 游戏启动时
- on_enemy_spawn(enemy) - 敌人生成时
- on_player_damage(amount) - 玩家受伤时
- on_player_level_up(level) - 玩家升级时
- on_weapon_pickup(weapon) - 拾取武器时
- on_game_over() - 游戏结束时

示例 mod：
    def register(mod_loader):
        mod_loader.info = {
            "name": "我的Mod",
            "version": "1.0",
            "author": "我",
            "description": "示例mod"
        }
        
        def on_enemy_spawn(enemy):
            enemy.hp *= 0.5  # 敌人血量减半
        
        mod_loader.hooks.register("on_enemy_spawn", on_enemy_spawn)
""")
    return _MODS_DIR


def load_mod(mod_path: str) -> Optional[ModInfo]:
    """加载单个 mod"""
    mod_id = os.path.splitext(os.path.basename(mod_path))[0]
    
    # 检查是否禁用
    if not _mods_enabled.get(mod_id, True):
        return None
    
    try:
        # 动态加载模块
        spec = importlib.util.spec_from_file_location(f"mod_{mod_id}", mod_path)
        if spec is None or spec.loader is None:
            return None
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 注入常用游戏类到 mod 命名空间，mod 可直接使用无需 import
        try:
            from ui import FloatingText
            module.FloatingText = FloatingText
        except Exception:
            pass
        try:
            from config import WeaponType, EnemyType, BuffType, SkillType
            module.WeaponType = WeaponType
            module.EnemyType = EnemyType
            module.BuffType = BuffType
            module.SkillType = SkillType
        except Exception:
            pass
        
        # 检查是否有 register 函数
        if not hasattr(module, 'register'):
            print(f"[Mod] {mod_id} 缺少 register 函数，跳过")
            return None
        
        # 创建 mod 信息
        mod_info = ModInfo(
            id=mod_id,
            name=getattr(module, 'MOD_NAME', mod_id),
            version=getattr(module, 'MOD_VERSION', "1.0.0"),
            author=getattr(module, 'MOD_AUTHOR', "Unknown"),
            description=getattr(module, 'MOD_DESCRIPTION', ""),
            path=mod_path,
            module=module
        )
        
        # 调用 register 函数
        try:
            module.register(mod_hooks)
            # 如果 register 中设置了 info 属性
            if hasattr(module, 'info') and isinstance(module.info, dict):
                mod_info.name = module.info.get("name", mod_info.name)
                mod_info.version = module.info.get("version", mod_info.version)
                mod_info.author = module.info.get("author", mod_info.author)
                mod_info.description = module.info.get("description", mod_info.description)
        except Exception as e:
            print(f"[Mod] {mod_id} register 错误: {e}")
            return None
        
        print(f"[Mod] 已加载: {mod_info.name} v{mod_info.version} by {mod_info.author}")
        return mod_info
        
    except Exception as e:
        print(f"[Mod] 加载 {mod_id} 失败: {e}")
        return None


def load_all_mods() -> List[ModInfo]:
    """加载所有 mod"""
    global _loaded_mods
    
    _load_mods_config()
    mods_dir = get_mods_dir()
    _loaded_mods = []
    
    # 扫描 .py 文件
    if os.path.exists(mods_dir):
        for filename in os.listdir(mods_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                mod_path = os.path.join(mods_dir, filename)
                mod_info = load_mod(mod_path)
                if mod_info:
                    _loaded_mods.append(mod_info)
        
        # 扫描文件夹（包含 __init__.py）
        for dirname in os.listdir(mods_dir):
            dir_path = os.path.join(mods_dir, dirname)
            if os.path.isdir(dir_path):
                init_path = os.path.join(dir_path, '__init__.py')
                if os.path.exists(init_path):
                    mod_info = load_mod(init_path)
                    if mod_info:
                        mod_info.id = dirname
                        _loaded_mods.append(mod_info)
    
    print(f"[Mod] 共加载 {len(_loaded_mods)} 个 mod")
    return _loaded_mods


def get_loaded_mods() -> List[ModInfo]:
    """获取已加载的 mod 列表"""
    return _loaded_mods


def toggle_mod(mod_id: str, enabled: bool):
    """启用/禁用 mod（需要重启游戏生效）"""
    _mods_enabled[mod_id] = enabled
    _save_mods_config()


def trigger_hook(hook_name: str, *args, **kwargs) -> List[Any]:
    """触发全局钩子（便捷函数）"""
    return mod_hooks.trigger(hook_name, *args, **kwargs)


# 可用钩子名称常量
HOOK_GAME_START = "on_game_start"
HOOK_GAME_TICK = "on_game_tick"           # 每帧调用 (game, dt)
HOOK_ENEMY_SPAWN = "on_enemy_spawn"       # 敌人生成时 (enemy)
HOOK_ENEMY_DEATH = "on_enemy_death"       # 敌人死亡时 (enemy, killer)
HOOK_ENEMY_DAMAGE = "on_enemy_damage"     # 敌人受伤时 (enemy, damage, damage_type) -> 返回修改后的伤害
HOOK_PLAYER_DAMAGE = "on_player_damage"   # 玩家受伤时 (amount) -> 返回修改后的伤害
HOOK_PLAYER_HEAL = "on_player_heal"       # 玩家治疗时 (amount) -> 返回修改后的治疗量
HOOK_PLAYER_LEVEL_UP = "on_player_level_up"  # 玩家升级时 (level)
HOOK_PLAYER_DEATH = "on_player_death"     # 玩家死亡时
HOOK_WEAPON_PICKUP = "on_weapon_pickup"   # 拾取武器时 (weapon)
HOOK_WEAPON_FIRE = "on_weapon_fire"       # 武器开火时 (weapon, player)
HOOK_BULLET_HIT = "on_bullet_hit"         # 子弹命中时 (bullet, enemy)
HOOK_GRENADE_DETONATE = "on_grenade_detonate"  # 手雷爆炸时 (grenade)
HOOK_WAVE_COMPLETE = "on_wave_complete"   # 尸潮完成时 (wave_number)
HOOK_HORDE_START = "on_horde_start"       # 尸潮开始时 (wave_number)
HOOK_BOSS_SPAWN = "on_boss_spawn"         # Boss 生成时 (boss)
HOOK_BOSS_DEATH = "on_boss_death"         # Boss 死亡时 (boss)
HOOK_ITEM_PICKUP = "on_item_pickup"       # 拾取道具时 (item_type)
HOOK_TEXT_PICKUP = "on_text_pickup"       # 拾取文本资料时 (text_id)
HOOK_MAP_CHANGE = "on_map_change"         # 地图切换时 (map_name)
HOOK_GAME_OVER = "on_game_over"           # 游戏结束时 (result_data)
HOOK_GAME_SAVE = "on_game_save"           # 游戏保存时 (save_data) -> 可修改 save_data
HOOK_GAME_LOAD = "on_game_load"           # 游戏读取时 (save_data) -> 可修改 save_data
HOOK_DIALOGUE_START = "on_dialogue_start" # 对话开始时 (dialogue_id)
HOOK_DIALOGUE_END = "on_dialogue_end"     # 对话结束时 (dialogue_id)
HOOK_SKILL_UNLOCK = "on_skill_unlock"     # 技能解锁时 (skill_type, level)
HOOK_BUFF_APPLY = "on_buff_apply"         # Buff 施加时 (buff_type, duration)
HOOK_RENDER_HUD = "on_render_hud"         # 渲染 HUD 后 (screen, game) -> 可自定义绘制
HOOK_RENDER_WORLD = "on_render_world"     # 渲染世界后 (screen, game) -> 可自定义绘制
HOOK_KEYDOWN = "on_keydown"               # 按键按下时 (key) -> 返回 True 阻止默认处理
HOOK_MOUSE_CLICK = "on_mouse_click"       # 鼠标点击时 (pos, button) -> 返回 True 阻止默认
HOOK_MENU_DRAW = "on_menu_draw"           # 菜单绘制后 (screen, game)
HOOK_STATE_CHANGE = "on_state_change"     # 游戏状态切换时 (old_state, new_state)


class ModAPI:
    """Mod 可调用的游戏 API 接口 - 通过 register(mod_loader) 中的 mod_loader 参数访问"""
    
    def __init__(self):
        self._game = None
        self._hooks = mod_hooks
    
    def _bind_game(self, game):
        """内部方法：绑定游戏实例"""
        self._game = game
    
    # === 玩家相关 ===
    def get_player(self):
        """获取玩家对象"""
        return self._game.player if self._game else None
    
    def get_player_pos(self):
        """获取玩家位置 (x, y)"""
        if self._game and self._game.player:
            return (self._game.player.x, self._game.player.y)
        return (0, 0)
    
    def get_player_hp(self):
        """获取玩家当前生命值"""
        if self._game and self._game.player:
            return self._game.player.hp
        return 0
    
    def get_player_max_hp(self):
        """获取玩家最大生命值"""
        if self._game and self._game.player:
            return self._game.player.max_hp
        return 100
    
    def set_player_hp(self, hp):
        """设置玩家生命值"""
        if self._game and self._game.player:
            self._game.player.hp = max(0, min(hp, self._game.player.max_hp))
    
    def damage_player(self, amount, damage_type="mod"):
        """对玩家造成伤害"""
        if self._game and self._game.player:
            self._game.player.take_damage(amount, damage_type=damage_type)
    
    def heal_player(self, amount):
        """治疗玩家"""
        if self._game and self._game.player:
            self._game.player.hp = min(self._game.player.max_hp, self._game.player.hp + amount)
    
    def get_player_level(self):
        """获取玩家等级"""
        if self._game and self._game.player:
            return self._game.player.level
        return 1
    
    def get_player_exp(self):
        """获取玩家经验值"""
        if self._game and self._game.player:
            return self._game.player.exp
        return 0
    
    def add_player_exp(self, amount):
        """给玩家增加经验值"""
        if self._game and self._game.player:
            self._game.player.gain_exp(amount)
    
    def get_player_weapons(self):
        """获取玩家武器列表"""
        if self._game and self._game.player:
            return self._game.player.weapons
        return []
    
    def get_current_weapon(self):
        """获取当前武器"""
        if self._game and self._game.player:
            return self._game.player.current_weapon
        return None
    
    # === 敌人相关 ===
    def get_enemies(self):
        """获取当前所有敌人列表"""
        if self._game:
            return self._game.enemies
        return []
    
    def spawn_enemy(self, x, y, enemy_type, level=1):
        """在指定位置生成敌人"""
        if self._game:
            from entities import Enemy
            enemy = Enemy(x, y, enemy_type, level, self._game.config.difficulty)
            self._game.enemies.append(enemy)
            return enemy
        return None
    
    def damage_enemy(self, enemy, amount, damage_type="mod"):
        """对敌人造成伤害"""
        if enemy and hasattr(enemy, 'take_damage'):
            enemy.take_damage(amount, damage_type=damage_type)
    
    def kill_enemy(self, enemy):
        """直接击杀敌人"""
        if enemy:
            enemy.hp = 0
            enemy.alive = False
    
    def get_enemy_count(self):
        """获取当前敌人数量"""
        if self._game:
            return len(self._game.enemies)
        return 0
    
    # === 世界/地图相关 ===
    def get_world(self):
        """获取世界对象"""
        if self._game:
            return self._game.world
        return None
    
    def get_current_map(self):
        """获取当前地图名称"""
        if self._game and self._game.world:
            return self._game.world.map_name
        return ""
    
    def get_map_size(self):
        """获取地图尺寸 (width, height)"""
        if self._game and self._game.world:
            return (self._game.world.width, self._game.world.height)
        return (0, 0)
    
    # === 道具/掉落相关 ===
    def spawn_item(self, x, y, item_type):
        """在指定位置生成道具"""
        if self._game:
            from world import SpecialItem
            item = SpecialItem(x, y, item_type)
            self._game.world.items.append(item)
            return item
        return None
    
    def spawn_exp_orb(self, x, y, value=10):
        """在指定位置生成经验球"""
        if self._game:
            from entities import ExpOrb
            orb = ExpOrb(x, y, value)
            self._game.exp_orbs.append(orb)
            return orb
        return None
    
    def spawn_text_item(self, x, y, text_id):
        """在指定位置生成文本资料"""
        if self._game:
            from world import TextItem
            item = TextItem(x, y, text_id)
            self._game.text_items.append(item)
            return item
        return None
    
    # === 特效/粒子相关 ===
    def spawn_particles(self, x, y, color, count=10, speed=100, life=0.5):
        """在指定位置生成粒子效果"""
        if self._game and hasattr(self._game, 'particles'):
            for _ in range(count):
                import random, math
                angle = random.uniform(0, math.pi * 2)
                spd = random.uniform(speed * 0.5, speed)
                self._game.particles.add(x, y, 
                    math.cos(angle) * spd, math.sin(angle) * spd,
                    color, life)
    
    def spawn_damage_number(self, x, y, damage, color=(255, 255, 255)):
        """生成伤害数字"""
        if self._game:
            from entities import DamageNumber
            dn = DamageNumber(x, y, damage, color)
            self._game.damage_numbers.append(dn)
    
    def spawn_floating_text(self, x, y, text, color=(255, 255, 255)):
        """生成浮动文字"""
        if self._game:
            from ui import FloatingText
            ft = FloatingText(x, y, text, color)
            self._game.floating_texts.append(ft)
    
    def screen_shake(self, intensity=10, duration=0.3):
        """屏幕震动"""
        if self._game and hasattr(self._game, 'camera'):
            self._game.camera.shake(intensity, duration)
    
    # === 音效/音乐相关 ===
    def play_sound(self, sound_name):
        """播放音效"""
        if self._game and self._game.assets:
            self._game.assets.play_sound(sound_name)
    
    def play_music(self, music_name):
        """播放音乐"""
        if self._game and self._game.assets:
            self._game.assets.play_music(music_name)
    
    def stop_music(self):
        """停止音乐"""
        if self._game and self._game.assets:
            self._game.assets.stop_music()
    
    # === 游戏状态相关 ===
    def get_game_state(self):
        """获取当前游戏状态"""
        if self._game:
            return self._game.state
        return None
    
    def get_game_time(self):
        """获取游戏时间（秒）"""
        if self._game:
            return self._game.game_time
        return 0
    
    def get_wave_number(self):
        """获取当前尸潮波数"""
        if self._game and self._game.horde_manager:
            return self._game.horde_manager.wave
        return 0
    
    def get_difficulty(self):
        """获取难度"""
        if self._game and self._game.config:
            return self._game.config.difficulty
        return "normal"
    
    def get_game_mode(self):
        """获取游戏模式"""
        if self._game and self._game.config:
            return self._game.config.game_mode
        return "story"
    
    def pause_game(self):
        """暂停游戏"""
        if self._game:
            from config import GameState
            self._game.prev_state = self._game.state
            self._game.state = GameState.PAUSED
    
    def resume_game(self):
        """恢复游戏"""
        if self._game:
            self._game.state = getattr(self._game, 'prev_state', None) or self._game.state
    
    def end_game(self, victory=False):
        """结束游戏"""
        if self._game:
            self._game.game_over(victory)
    
    # === 日志/调试相关 ===
    def log(self, message):
        """输出日志"""
        print(f"[Mod] {message}")
        if self._game and hasattr(self._game, 'logger'):
            self._game.logger.info(f"[Mod] {message}")
    
    def show_message(self, text, duration=3.0):
        """在屏幕上显示消息"""
        if self._game:
            self._game.floating_texts.append(
                FloatingText(self._game.player.x if self._game.player else 0,
                           self._game.player.y - 60 if self._game.player else 0,
                           text, (255, 255, 200))
            )
    
    # === 配置/数据相关 ===
    def get_config(self):
        """获取游戏配置对象"""
        if self._game:
            return self._game.config
        return None
    
    def get_mod_data_dir(self):
        """获取 mod 数据存储目录（用于保存 mod 自己的数据）"""
        import os
        data_dir = os.path.join(os.path.dirname(__file__), "mods_data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    
    def save_mod_data(self, mod_id, data):
        """保存 mod 数据到 JSON 文件"""
        import os, json
        data_dir = self.get_mod_data_dir()
        path = os.path.join(data_dir, f"{mod_id}.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.log(f"保存数据失败: {e}")
            return False
    
    def load_mod_data(self, mod_id, default=None):
        """加载 mod 数据"""
        import os, json
        data_dir = self.get_mod_data_dir()
        path = os.path.join(data_dir, f"{mod_id}.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"加载数据失败: {e}")
        return default


# 全局 API 实例
mod_api = ModAPI()
# 将全局 API 绑定到全局钩子（mod 注册时即可使用 mod_api）
mod_hooks.mod_api = mod_api



def get_all_available_mods():
    """获取所有可用的 mod 列表（不加载，只读取元数据），包括已禁用的"""
    _load_mods_config()
    mods_dir = get_mods_dir()
    mods = []
    
    if not os.path.exists(mods_dir):
        return mods
    
    # 扫描 .py 文件
    for filename in os.listdir(mods_dir):
        if filename.endswith('.py') and not filename.startswith('_'):
            mod_path = os.path.join(mods_dir, filename)
            mod_id = os.path.splitext(filename)[0]
            mod_info = _read_mod_metadata(mod_path, mod_id)
            if mod_info:
                mods.append(mod_info)
    
    # 扫描文件夹
    for dirname in os.listdir(mods_dir):
        dir_path = os.path.join(mods_dir, dirname)
        if os.path.isdir(dir_path):
            init_path = os.path.join(dir_path, '__init__.py')
            if os.path.exists(init_path):
                mod_info = _read_mod_metadata(init_path, dirname)
                if mod_info:
                    mods.append(mod_info)
    
    return mods


def _read_mod_metadata(mod_path, mod_id):
    """读取 mod 的元数据（不执行 register 函数）"""
    try:
        # 读取文件内容，提取元数据
        with open(mod_path, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
        
        # 尝试从源码中提取 MOD_NAME, MOD_VERSION, MOD_AUTHOR, MOD_DESCRIPTION
        import re
        name = mod_id
        version = "1.0.0"
        author = "Unknown"
        description = ""
        
        # 搜索 MOD_NAME = "xxx"
        name_match = re.search(r'MOD_NAME\s*=\s*["\']([^"\']+)["\']', source)
        if name_match:
            name = name_match.group(1)
        
        version_match = re.search(r'MOD_VERSION\s*=\s*["\']([^"\']+)["\']', source)
        if version_match:
            version = version_match.group(1)
        
        author_match = re.search(r'MOD_AUTHOR\s*=\s*["\']([^"\']+)["\']', source)
        if author_match:
            author = author_match.group(1)
        
        desc_match = re.search(r'MOD_DESCRIPTION\s*=\s*["\']([^"\']+)["\']', source)
        if desc_match:
            description = desc_match.group(1)
        
        # 如果没有找到 MOD_ 变量，尝试从 register 函数中的 info 字典提取
        if name == mod_id or description == "":
            info_match = re.search(r'info\s*=\s*\{([^}]+)\}', source, re.DOTALL)
            if info_match:
                info_content = info_match.group(1)
                n_match = re.search(r'["\']name["\']\s*:\s*["\']([^"\']+)["\']', info_content)
                if n_match and name == mod_id:
                    name = n_match.group(1)
                v_match = re.search(r'["\']version["\']\s*:\s*["\']([^"\']+)["\']', info_content)
                if v_match:
                    version = v_match.group(1)
                a_match = re.search(r'["\']author["\']\s*:\s*["\']([^"\']+)["\']', info_content)
                if a_match and author == "Unknown":
                    author = a_match.group(1)
                d_match = re.search(r'["\']description["\']\s*:\s*["\']([^"\']+)["\']', info_content)
                if d_match and description == "":
                    description = d_match.group(1)
        
        enabled = _mods_enabled.get(mod_id, True)
        
        return ModInfo(
            id=mod_id,
            name=name,
            version=version,
            author=author,
            description=description,
            enabled=enabled,
            path=mod_path
        )
    except Exception as e:
        print(f"[Mod] 读取 {mod_id} 元数据失败: {e}")
        return None


def is_mod_enabled(mod_id):
    """检查 mod 是否启用"""
    _load_mods_config()
    return _mods_enabled.get(mod_id, True)
