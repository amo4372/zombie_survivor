# 丧尸幸存者 Mod 开发指南

> 版本：v1.0 | 适用游戏版本：v4.0 黑暗尸潮

## 目录

1. [快速开始](#1-快速开始)
2. [Mod 结构](#2-mod-结构)
3. [元数据声明](#3-元数据声明)
4. [钩子系统（Hooks）](#4-钩子系统hooks)
5. [Mod API 参考](#5-mod-api-参考)
6. [完整示例](#6-完整示例)
7. [调试与发布](#7-调试与发布)

---

## 1. 快速开始

### 1.1 创建你的第一个 Mod

在游戏目录的 `mods/` 文件夹下创建一个 `.py` 文件，例如 `my_first_mod.py`：

```python
# mods/my_first_mod.py
MOD_NAME = "我的第一个Mod"
MOD_VERSION = "1.0.0"
MOD_AUTHOR = "你的名字"
MOD_DESCRIPTION = "这是一个示例Mod，玩家受伤时输出日志"

def register(mod_loader):
    def on_player_damage(amount):
        print(f"[我的Mod] 玩家受到了 {amount} 点伤害！")
        return amount  # 可以返回修改后的伤害值
    
    mod_loader.register("on_player_damage", on_player_damage)
    print("[我的Mod] 加载成功！")
```

启动游戏，在主菜单进入 **Mod管理**，确认你的 Mod 已启用（默认启用），开始游戏即可生效。

### 1.2 启用/禁用 Mod

- 进入主菜单 → **Mod管理**
- 左侧列表单击选中 Mod，右侧显示详情
- 点击「启用/禁用」按钮切换状态
- **修改后需要重启游戏才能生效**

---

## 2. Mod 结构

### 2.1 单文件 Mod

最简单的形式：`mods/your_mod.py`

```
zombie_survivor_package/
├── mods/
│   ├── your_mod.py        ← 单文件Mod
│   └── README.txt
├── game.py
├── main.py
└── ...
```

### 2.2 文件夹 Mod（多文件）

如果 Mod 较大，可以用文件夹形式，必须包含 `__init__.py`：

```
mods/
└── my_big_mod/            ← 文件夹Mod
    ├── __init__.py        ← 入口（必须有 register 函数）
    ├── config.py
    └── utils.py
```

`__init__.py` 示例：

```python
from .config import MOD_CONFIG
from .utils import helper_function

MOD_NAME = "大型Mod"
MOD_VERSION = "2.0.0"
MOD_AUTHOR = "作者"
MOD_DESCRIPTION = "一个多文件的大型Mod"

def register(mod_loader):
    def on_game_start(game):
        helper_function()
    mod_loader.register("on_game_start", on_game_start)
```

---

## 3. 元数据声明

在 Mod 文件顶部声明以下变量（全部可选，但建议填写）：

| 变量 | 类型 | 说明 |
|------|------|------|
| `MOD_NAME` | str | Mod 显示名称 |
| `MOD_VERSION` | str | 版本号，如 "1.0.0" |
| `MOD_AUTHOR` | str | 作者名 |
| `MOD_DESCRIPTION` | str | 详细描述（支持中文，会在Mod管理界面显示） |

也可以在 `register` 函数中通过 `info` 字典设置：

```python
def register(mod_loader):
    mod_loader.info = {
        "name": "Mod名称",
        "version": "1.0.0",
        "author": "作者",
        "description": "描述"
    }
```

---

## 4. 钩子系统（Hooks）

钩子是 Mod 与游戏交互的核心方式。通过 `mod_loader.register(hook_name, callback)` 注册回调函数。

### 4.1 生命周期钩子

| 钩子名 | 参数 | 返回值 | 触发时机 |
|--------|------|--------|----------|
| `on_game_start` | `(game)` | - | 游戏开始（进入PLAYING状态） |
| `on_game_tick` | `(game, dt)` | - | 每帧调用（dt为帧间隔秒数） |
| `on_game_over` | `(result_data)` | - | 游戏结束 |
| `on_game_save` | `(save_data)` | 可修改save_data | 游戏存档时 |
| `on_game_load` | `(save_data)` | 可修改save_data | 游戏读档时 |
| `on_state_change` | `(old_state, new_state)` | - | 游戏状态切换 |

### 4.2 玩家相关钩子

| 钩子名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `on_player_damage` | `(amount)` | 修改后的伤害值 | 玩家受伤时，返回新伤害 |
| `on_player_heal` | `(amount)` | 修改后的治疗量 | 玩家被治疗时 |
| `on_player_level_up` | `(level)` | - | 玩家升级时 |
| `on_player_death` | `()` | - | 玩家死亡时 |
| `on_skill_unlock` | `(skill_type, level)` | - | 技能解锁/升级时 |
| `on_buff_apply` | `(buff_type, duration)` | - | Buff施加时 |

### 4.3 敌人相关钩子

| 钩子名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `on_enemy_spawn` | `(enemy)` | - | 敌人生成时，可修改enemy属性 |
| `on_enemy_death` | `(enemy, killer)` | - | 敌人死亡时 |
| `on_enemy_damage` | `(enemy, damage, type)` | 修改后的伤害 | 敌人受伤时 |
| `on_boss_spawn` | `(boss)` | - | Boss生成时 |
| `on_boss_death` | `(boss)` | - | Boss死亡时 |

### 4.4 战斗相关钩子

| 钩子名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `on_weapon_pickup` | `(weapon)` | - | 拾取武器时 |
| `on_weapon_fire` | `(weapon, player)` | - | 武器开火时 |
| `on_bullet_hit` | `(bullet, enemy)` | - | 子弹命中时 |
| `on_grenade_detonate` | `(grenade)` | - | 手雷爆炸时 |

### 4.5 波次/地图钩子

| 钩子名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `on_horde_start` | `(wave_number)` | - | 尸潮开始时 |
| `on_wave_complete` | `(wave_number)` | - | 尸潮完成时 |
| `on_map_change` | `(map_name)` | - | 地图切换时 |

### 4.6 道具/文本钩子

| 钩子名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `on_item_pickup` | `(item_type)` | - | 拾取道具时 |
| `on_text_pickup` | `(text_id)` | - | 拾取文本资料时 |

### 4.7 对话钩子

| 钩子名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `on_dialogue_start` | `(dialogue_id)` | - | 对话开始时 |
| `on_dialogue_end` | `(dialogue_id)` | - | 对话结束时 |

### 4.8 渲染/输入钩子

| 钩子名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `on_render_hud` | `(screen, game)` | - | HUD渲染后，可自定义绘制 |
| `on_render_world` | `(screen, game)` | - | 世界渲染后，可自定义绘制 |
| `on_menu_draw` | `(screen, game)` | - | 菜单绘制后 |
| `on_keydown` | `(key)` | True=阻止默认 | 按键按下时 |
| `on_mouse_click` | `(pos, button)` | True=阻止默认 | 鼠标点击时 |

### 4.9 注册钩子示例

```python
def register(mod_loader):
    # 单个钩子
    mod_loader.register("on_enemy_spawn", my_spawn_handler)
    
    # 多个钩子
    mod_loader.register("on_player_damage", damage_handler)
    mod_loader.register("on_game_tick", tick_handler)
    mod_loader.register("on_render_hud", render_handler)
```

### 4.10 高级自由钩子（v1.0.1 新增）

以下钩子允许 Mod 更自由地接管核心逻辑，返回特定值可覆盖游戏行为：

| 钩子名 | 参数 | 返回值 | 说明 |
|--------|------|--------|------|
| `on_touch_event` | `(event, game)` | 返回 `True` 拦截该事件 | 触控事件（按下/移动/抬起）分发前触发，可用于自定义手势/覆盖控件行为 |
| `on_player_move` | `(game, move_x, move_y, dt)` | 返回 `(nx, ny)` 覆盖移动 | 玩家移动结算前触发，可完全接管/改写移动输入 |
| `on_player_fire` | `(weapon, player)` | - | 当前武器开火前触发 |
| `on_skill_use` | `(skill_type, player)` | - | 技能施放时触发 |
| `on_enemy_update` | `(enemy, dt)` | - | 每个敌人更新前触发，可读取/修改敌人状态 |
| `on_damage_dealt` | `(victim, damage, damage_type, attacker)` | 返回数值覆盖伤害 | 任意伤害结算（玩家或敌人受击）前触发，返回值将作为最终伤害 |

示例（覆盖玩家移动并拦截触控）：

```python
def register(mod_loader):
    def on_move(game, mx, my, dt):
        return (mx * 2, my * 2)   # 移动速度翻倍
    def on_touch(ev, game):
        if ev.get("type") == "down" and ev.get("x", 0) < 0.2:
            return True            # 拦截屏幕左 20% 区域的点击
    def on_damage(victim, dmg, dtype, attacker):
        return dmg * 1.5           # 所有伤害提高 50%
    mod_loader.register("on_player_move", on_move)
    mod_loader.register("on_touch_event", on_touch)
    mod_loader.register("on_damage_dealt", on_damage)
```

---

## 5. Mod API 参考

通过 `mod_loader.mod_api` 可以调用游戏提供的 API。在 `register` 函数中即可访问：

```python
def register(mod_loader):
    api = mod_loader.mod_api
    
    def on_game_start(game):
        api.log("游戏开始了！")
        api.show_message("欢迎使用我的Mod！")
    
    mod_loader.register("on_game_start", on_game_start)
```

### 5.1 玩家 API

| 方法 | 说明 |
|------|------|
| `api.get_player()` | 获取玩家对象 |
| `api.get_player_pos()` | 获取玩家位置 (x, y) |
| `api.get_player_hp()` | 获取当前生命值 |
| `api.get_player_max_hp()` | 获取最大生命值 |
| `api.set_player_hp(hp)` | 设置生命值 |
| `api.damage_player(amount, type)` | 对玩家造成伤害 |
| `api.heal_player(amount)` | 治疗玩家 |
| `api.get_player_level()` | 获取等级 |
| `api.get_player_exp()` | 获取经验值 |
| `api.add_player_exp(amount)` | 增加经验值 |
| `api.get_player_weapons()` | 获取武器列表 |
| `api.get_current_weapon()` | 获取当前武器 |

### 5.2 敌人 API

| 方法 | 说明 |
|------|------|
| `api.get_enemies()` | 获取所有敌人列表 |
| `api.get_enemy_count()` | 获取敌人数量 |
| `api.spawn_enemy(x, y, type, level)` | 生成敌人 |
| `api.damage_enemy(enemy, amount, type)` | 对敌人造成伤害 |
| `api.kill_enemy(enemy)` | 直接击杀敌人 |

### 5.3 世界/地图 API

| 方法 | 说明 |
|------|------|
| `api.get_world()` | 获取世界对象 |
| `api.get_current_map()` | 获取当前地图名 |
| `api.get_map_size()` | 获取地图尺寸 (w, h) |

### 5.4 道具/掉落 API

| 方法 | 说明 |
|------|------|
| `api.spawn_item(x, y, item_type)` | 生成道具 |
| `api.spawn_exp_orb(x, y, value)` | 生成经验球 |
| `api.spawn_text_item(x, y, text_id)` | 生成文本资料 |

### 5.5 特效 API

| 方法 | 说明 |
|------|------|
| `api.spawn_particles(x, y, color, count, speed, life)` | 生成粒子 |
| `api.spawn_damage_number(x, y, damage, color)` | 生成伤害数字 |
| `api.spawn_floating_text(x, y, text, color)` | 生成浮动文字 |
| `api.screen_shake(intensity, duration)` | 屏幕震动 |

### 5.6 音效/音乐 API

| 方法 | 说明 |
|------|------|
| `api.play_sound(name)` | 播放音效 |
| `api.play_music(name)` | 播放音乐 |
| `api.stop_music()` | 停止音乐 |

### 5.7 游戏状态 API

| 方法 | 说明 |
|------|------|
| `api.get_game_state()` | 获取游戏状态 |
| `api.get_game_time()` | 获取游戏时间（秒） |
| `api.get_wave_number()` | 获取尸潮波数 |
| `api.get_difficulty()` | 获取难度 |
| `api.get_game_mode()` | 获取游戏模式 |
| `api.pause_game()` | 暂停游戏 |
| `api.resume_game()` | 恢复游戏 |
| `api.end_game(victory)` | 结束游戏 |

### 5.8 数据存储 API

| 方法 | 说明 |
|------|------|
| `api.save_mod_data(mod_id, data)` | 保存Mod数据到JSON |
| `api.load_mod_data(mod_id, default)` | 加载Mod数据 |
| `api.get_mod_data_dir()` | 获取Mod数据目录 |
| `api.get_config()` | 获取游戏配置对象 |

### 5.9 工具 API

| 方法 | 说明 |
|------|------|
| `api.log(message)` | 输出日志 |
| `api.show_message(text, duration)` | 屏幕显示消息 |

---

## 6. 完整示例

### 6.1 示例1：简单难度修改

```python
# mods/easy_mode.py
MOD_NAME = "简单模式"
MOD_VERSION = "1.0.0"
MOD_AUTHOR = "示例作者"
MOD_DESCRIPTION = "敌人血量减半，玩家伤害翻倍，适合休闲玩家。"

def register(mod_loader):
    api = mod_loader.mod_api
    
    def on_enemy_spawn(enemy):
        enemy.max_hp = int(enemy.max_hp * 0.5)
        enemy.hp = enemy.max_hp
        enemy.damage = int(enemy.damage * 0.7)
    
    def on_player_damage(amount):
        return int(amount * 0.5)  # 玩家受伤减半
    
    def on_game_start(game):
        api.show_message("简单模式已激活！")
    
    mod_loader.register("on_enemy_spawn", on_enemy_spawn)
    mod_loader.register("on_player_damage", on_player_damage)
    mod_loader.register("on_game_start", on_game_start)
```

### 6.2 示例2：自定义事件（每波结束回血）

```python
# mods/wave_healer.py
MOD_NAME = "波次治疗者"
MOD_VERSION = "1.0.0"
MOD_AUTHOR = "示例作者"
MOD_DESCRIPTION = "每完成一波尸潮，玩家恢复30%最大生命值。"

def register(mod_loader):
    api = mod_loader.mod_api
    
    def on_wave_complete(wave_number):
        player = api.get_player()
        if player:
            heal_amount = int(player.max_hp * 0.3)
            api.heal_player(heal_amount)
            api.show_message(f"波次 {wave_number} 完成！恢复 {heal_amount} 生命")
            api.spawn_particles(player.x, player.y, (0, 255, 0), count=20)
    
    mod_loader.register("on_wave_complete", on_wave_complete)
```

### 6.3 示例3：自定义HUD显示

```python
# mods/custom_hud.py
MOD_NAME = "自定义HUD"
MOD_VERSION = "1.0.0"
MOD_AUTHOR = "示例作者"
MOD_DESCRIPTION = "在屏幕左上角显示击杀计数和游戏时间。"
import pygame

kill_count = 0

def register(mod_loader):
    api = mod_loader.mod_api
    
    def on_enemy_death(enemy, killer):
        global kill_count
        kill_count += 1
    
    def on_render_hud(screen, game):
        font = pygame.font.SysFont("SimHei", 20)
        # 击杀数
        text = font.render(f"击杀: {kill_count}", True, (255, 200, 100))
        screen.blit(text, (10, 10))
        # 游戏时间
        time_text = font.render(f"时间: {int(api.get_game_time())}s", True, (200, 200, 255))
        screen.blit(time_text, (10, 35))
    
    def on_game_start(game):
        global kill_count
        kill_count = 0
    
    mod_loader.register("on_enemy_death", on_enemy_death)
    mod_loader.register("on_render_hud", on_render_hud)
    mod_loader.register("on_game_start", on_game_start)
```

### 6.4 示例4：使用数据持久化

```python
# mods/total_kills_tracker.py
MOD_NAME = "总击杀追踪器"
MOD_VERSION = "1.0.0"
MOD_AUTHOR = "示例作者"
MOD_DESCRIPTION = "跨游戏记录总击杀数，数据持久化保存。"

MOD_ID = "total_kills_tracker"
total_kills = 0

def register(mod_loader):
    api = mod_loader.mod_api
    
    # 加载历史数据
    global total_kills
    data = api.load_mod_data(MOD_ID, {"total_kills": 0})
    total_kills = data.get("total_kills", 0)
    
    def on_enemy_death(enemy, killer):
        global total_kills
        total_kills += 1
        # 每100杀保存一次
        if total_kills % 100 == 0:
            api.save_mod_data(MOD_ID, {"total_kills": total_kills})
    
    def on_game_over(result_data):
        # 游戏结束时保存
        api.save_mod_data(MOD_ID, {"total_kills": total_kills})
        api.log(f"总击杀数: {total_kills}")
    
    def on_game_start(game):
        api.show_message(f"历史总击杀: {total_kills}")
    
    mod_loader.register("on_enemy_death", on_enemy_death)
    mod_loader.register("on_game_over", on_game_over)
    mod_loader.register("on_game_start", on_game_start)
```

### 6.5 示例5：生成自定义敌人

```python
# mods/boss_summoner.py
MOD_NAME = "Boss召唤器"
MOD_VERSION = "1.0.0"
MOD_AUTHOR = "示例作者"
MOD_DESCRIPTION = "按 B 键在玩家位置召唤一个Boss（测试用）。"
import pygame
from config import EnemyType

def register(mod_loader):
    api = mod_loader.mod_api
    
    def on_keydown(key):
        if key == pygame.K_b:
            pos = api.get_player_pos()
            boss = api.spawn_enemy(pos[0] + 100, pos[1], EnemyType.BOSS_ZOMBIE, level=5)
            if boss:
                api.show_message("Boss已召唤！")
                api.screen_shake(15, 0.5)
            return True  # 阻止默认按键处理
        return False
    
    mod_loader.register("on_keydown", on_keydown)
```

---

## 7. 调试与发布

### 7.1 调试技巧

1. **使用 `api.log()` 输出日志**：日志会显示在控制台和游戏日志文件中
2. **使用 `api.show_message()` 在游戏内显示消息**：方便快速验证
3. **检查 Mod 是否加载**：启动游戏时控制台会输出 `[Mod] 已加载: xxx`
4. **常见错误**：
   - `缺少 register 函数`：Mod 文件中必须定义 `def register(mod_loader):`
   - `钩子执行错误`：回调函数参数数量不匹配，检查钩子签名表
   - `Mod 不生效`：确认在 Mod管理 中已启用，并重启了游戏

### 7.2 注意事项

- **性能**：`on_game_tick` 每帧调用，避免在其中做耗时操作
- **异常安全**：钩子中的异常会被捕获并打印，不会导致游戏崩溃
- **返回值**：需要修改数值的钩子（如 `on_player_damage`）必须返回数值，否则不生效
- **多 Mod 冲突**：多个 Mod 注册同一钩子时，按加载顺序依次调用，后注册的返回值覆盖前者

### 7.3 发布 Mod

1. 将 Mod 文件（或文件夹）打包为 `.zip`
2. 包含 `README.md` 说明文件
3. 用户只需将解压后的文件放入 `mods/` 目录即可

### 7.4 Mod 配置文件

Mod 的启用/禁用状态保存在游戏目录的 `mods_config.json` 中：

```json
{
  "easy_mode": true,
  "my_mod": false
}
```

---

## 附录：可用常量导入

```python
# 敌人类型
from config import EnemyType
# EnemyType.NORMAL_ZOMBIE, EnemyType.FAST_ZOMBIE, EnemyType.BOSS_ZOMBIE 等

# 武器类型
from config import WeaponType
# WeaponType.PISTOL, WeaponType.SHOTGUN, WeaponType.RIFLE 等

# 道具类型
from world import ItemType
# ItemType.HEALTH_PACK, ItemType.AMMO_BOX, ItemType.WEAPON_BOX 等

# 游戏状态
from config import GameState
# GameState.MENU, GameState.PLAYING, GameState.PAUSED 等

# 颜色
from config import RED, GREEN, BLUE, YELLOW, WHITE, BLACK 等
```

---

**祝 Mod 开发愉快！如有问题，请在游戏社区反馈。**
