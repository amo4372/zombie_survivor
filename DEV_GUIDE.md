# 僵尸幸存者 v4.0 游戏开发文档

> 最后更新：2026-08-29
> 引擎：Pygame 2.6+ / Python 3.11+
> 平台：Windows PC / Android（触控）

---

## 一、项目架构

### 1.1 文件结构

| 文件 | 职责 | 行数(约) |
|------|------|----------|
| `main.py` | 入口，初始化并启动 Game | ~30 |
| `game.py` | 主游戏类，游戏循环、状态机、所有系统调度 | ~5700 |
| `entities.py` | Player、Enemy、ExpOrb、RiotGear 等实体 | ~2200 |
| `weapons.py` | Weapon、Projectile、武器配置表 | ~500 |
| `skills.py` | SkillTree、Skill、技能定义与升级 | ~400 |
| `skill_tree_view.py` | 全局技能树可视化（树状图、拖拽、缩放） | ~500 |
| `skill_wheel.py` | 触控端技能轮盘选择器 | ~200 |
| `buff.py` | BuffManager、BuffType、持续效果系统 | ~300 |
| `runes.py` | 符文系统（宝箱开出的局内永久buff） | ~150 |
| `world.py` | GameWorld（地图/障碍物/分块）、HordeManager、SpecialItem、TextItem | ~600 |
| `renderer.py` | 所有渲染逻辑（HUD、菜单、图鉴、技能树等） | ~3000 |
| `ui.py` | Button、VirtualJoystick、TouchButton、SkillCaster、AimButton 等UI组件 | ~600 |
| `config.py` | 全局常量、颜色、枚举（WeaponType/EnemyType/GameState/MapType） | ~400 |
| `dialogue.py` | 对话系统（开场剧情、NPC对话、文本资料查看） | ~200 |
| `codex.py` | 图鉴数据（僵尸/武器/Boss/世界观文本） | ~500 |
| `assets.py` | 资源管理器（图片/音效/音乐加载与播放） | ~300 |
| `records.py` | 游戏记录（最高击杀/最长存活/统计） | ~100 |
| `mod_loader.py` | Mod加载器（钩子系统、Mod API、沙箱执行） | ~400 |
| `logger.py` | 日志工具 | ~30 |
| `build_encrypted.py` | PyInstaller打包脚本（含.pyc加密） | ~100 |
| `verify.py` | 打包后完整性校验 | ~50 |

### 1.2 核心数据流

```
main.py → Game()
  ├── __init__: 加载配置/资源/存档/Mod/触控控件/菜单
  ├── run(): 主循环
  │     ├── handle_events() → 键盘/鼠标/触控事件分发
  │     ├── update(dt) → 按 GameState 分发到各 _update_xxx
  │     └── draw() → renderer.render() 按 GameState 绘制
  └── 各子系统: player / world / horde_manager / particles / renderer
```

---

## 二、游戏状态机

`GameState` 枚举定义在 `config.py`，所有状态切换通过 `self.state = GameState.XXX` 完成。

| 状态 | 说明 | update入口 | draw入口 |
|------|------|-----------|----------|
| `MENU` | 主菜单 | 菜单按钮hover/点击 | `_draw_menu()` |
| `PLAYING` | 游戏进行中 | `_update_playing()` | `_draw_game()` |
| `PAUSED` | 暂停 | 暂停菜单交互 | `_draw_pause()` |
| `LEVEL_UP` | 升级选技能 | 技能卡选择 | `_draw_level_up()` |
| `DIALOGUE` | 对话/剧情 | 对话推进 | `_draw_dialogue()` |
| `CODEX` | 图鉴 | 分类切换/滚动/详情 | `_draw_codex()` |
| `SKILL_TREE` | 全局技能树 | 拖拽/缩放/节点详情 | `_draw_skill_tree()` |
| `TEXT_VIEWER` | 文本资料查看 | 翻页/关闭 | `_draw_text_viewer()` |
| `MOD_MANAGER` | Mod管理 | 启用/禁用/详情 | `_draw_mod_manager()` |
| `ACHIEVEMENTS` | 成就 | 滚动浏览 | `_draw_achievements()` |
| `RECORDS` | 记录 | 浏览 | `_draw_records()` |
| `SETTINGS` | 设置 | 选项调整 | `_draw_settings()` |
| `TUTORIAL` | 教程 | 翻页 | `_draw_tutorial()` |
| `STORY_ARCHIVE` | 剧情资料库 | 选择/查看 | `_draw_story_archive()` |
| `MODE_SELECT` | 模式选择 | 故事/无尽 | `_draw_mode_select()` |
| `DIFFICULTY_SELECT` | 难度选择 | 简单/普通/困难 | `_draw_difficulty_select()` |
| `GAME_OVER` | 游戏结束 | 结算/重开 | `_draw_game_over()` |

**状态切换原则**：任何状态切换时必须重置对应触控控件状态（`_reset_touch_controls()`），防止摇杆卡死。

---

## 三、核心系统详解

### 3.1 玩家系统（Player）

**位置**：`entities.py` `class Player`

#### 属性
```python
self.x, self.y          # 世界坐标
self.speed = 3.5        # 基础移动速度（单位/帧，dt*60修正）
self.base_speed = 3.5
self.max_hp = 100
self.hp = 100
self.level, self.exp, self.exp_to_level
self.weapons = [Weapon(WeaponType.FISTS)]  # 初始武器为拳头
self.current_weapon_idx
self.skill_tree = SkillTree()
self.active_skills = {}   # 主动技能冷却计时 {SkillType: remaining}
self.riot_gear = RiotGear()
self.buff_manager = BuffManager()
```

#### 疾跑体力系统（v4.0新增）
```python
self.max_stamina = 100.0
self.stamina = 100.0
self.stamina_regen_rate = 18.0    # 每秒恢复
self.sprint_stamina_cost = 28.0   # 每秒消耗
self.sprint_speed_mult = 1.6       # 疾跑速度倍率
self.sprinting = False
self.stamina_exhausted = False     # 耗尽后需恢复到25%才能再疾跑
```

**疾跑逻辑**（`Player.update()`）：
- 按住Shift（键控）或"跑"按钮（触控）且正在移动 → 消耗体力，速度×1.6
- 体力归零 → `exhausted=True`，禁止疾跑
- 不疾跑时恢复体力，耗尽状态恢复速度×0.5
- 装备防爆套装时：疾跑消耗×1.6、恢复×0.65、普通移动也消耗4/s

#### 移动计算
```python
speed_mult = 1.0
speed_mult *= buff_manager.get_speed_mult()      # Buff加成
speed_mult *= sprint_speed_mult (if sprinting)   # 疾跑
speed_mult *= riot_gear_debuff (if equipped+debuff)  # 套装减速
new_x = x + move_x * speed * speed_mult * speed_mult * dt * 60
```

**注意**：`speed` 是每帧移动单位，通过 `dt * 60` 归一化到60fps。

### 3.2 防爆套装（RiotGear）

**位置**：`entities.py` `class RiotGear`

#### 核心属性（v4.0削弱后）
```python
self.shield_hp = 300          # 护盾HP
self.max_shield_hp = 300
self.viewing_window_hp = 200  # 观察窗HP
self.melee_reduction = 0.3    # 近战减伤30%
self.ranged_reduction = 0.5   # 远程减伤50%
self.magic_immunity = True    # 魔法免疫
self.stamina = 100             # 套装自身体力（盾击用）
self.max_stamina = 100
```

#### 钩爪系统（独立于套装装备）
```python
self.grapple_active = False
self.grapple_state = "idle" | "shooting" | "hit" | "pulling" | "retracting"
self.grapple_speed = 80          # 发射速度
self.grapple_pull_speed = 20     # 拉回速度（v4.0从5提升）
self.grapple_max_range = 800
self.grapple_max_cooldown = 1.5  # 内部CD
# 技能层CD: GRAPPLE_PULL = 2.0秒（v4.0从6秒削减）
```

**钩爪状态机**：
1. `shooting`：钩爪头飞向目标点，检测碰撞（敌人/道具/经验球/文本/宝箱）
2. `hit`：命中后短暂僵直0.4s，钩爪绷紧
3. `pulling`：以20/帧速度将敌人拉向玩家，距离>200时×1.5加速，距离<35时释放
4. `retracting`：未命中或目标死亡，钩爪头收回

**关键修复**：Enemy.update中`grappled`状态不再自行移动，完全由RiotGear控制位置，避免两套拉取逻辑冲突导致"中途断"。

#### 盾牌冲撞
```python
self.charge_damage = 150       # v4.0从220削弱
self.charge_stun_duration = 1.2 # v4.0从2.0削弱
self.charge_knockback = 100     # v4.0从150削弱
self.charge_speed = 680
self.charge_duration = 0.45
```
冲撞额外消耗玩家体力25点（v4.0新增）。

### 3.3 敌人系统（Enemy）

**位置**：`entities.py` `class Enemy`

#### 敌人类型（EnemyType枚举，config.py）
基础僵尸、疾行者、自爆僵尸、分裂者、重甲僵尸、治疗僵尸、幻影僵尸、食尸鬼、Boss等。

#### 核心属性
```python
self.x, self.y, self.size, self.speed
self.hp, self.max_hp, self.damage
self.alive, self.grappled = False
self.buff_manager = BuffManager()  # 每个敌人独立Buff系统
```

#### 状态优先级（update方法）
```python
if not alive: return
if frozen_timer > 0: 减速/不动; return
if grappled: return  # 被钩爪控制，不做自主行动
# 正常AI: 朝玩家移动 → 攻击检测 → 特殊能力
```

#### Buff对怪的伤害
敌人通过 `buff_manager.update(dt, self)` 处理持续伤害（燃烧/中毒/流血等）。伤害事件通过返回值 `buff_damage_events` 传递给game.py显示伤害数字。

**常见bug**：Buff伤害为0通常是因为 `damage_mult` 被抗性覆盖，或Buff的 `damage_per_tick` 未正确设置。

### 3.4 武器系统（Weapon）

**位置**：`weapons.py`

#### 武器类型
拳头（初始）、手枪、冲锋枪、霰弹枪、狙击枪、机枪、火焰喷射器、榴弹、加特林、等离子步枪、轨道炮、十字弩、双管霰弹等。

#### 核心机制
```python
self.weapon_type, self.damage, self.fire_rate, self.ammo, self.max_ammo
self.reload_time, self.projectile_speed, self.projectile_size, self.spread
self.is_melee (拳头/近战), self.is_throwable (手雷)
self.color (弹道颜色)
```

#### 射击流程
1. `can_shoot()` 检查冷却/弹药
2. `shoot()` 生成Projectile，消耗弹药，设置冷却
3. Projectile.update() 移动+碰撞检测
4. 命中敌人 → `enemy.take_damage()` + 粒子特效 + 伤害数字

### 3.5 技能系统（SkillTree）

**位置**：`skills.py` + `skill_tree_view.py`

#### 技能分类
- **被动技能**：生命强化、速度提升、伤害加成、暴击、生命偷取、护甲、闪避、再生等
- **主动技能**：冲刺、手雷、盾击、钩爪、空袭、时间减缓、过载、闪烁、黑洞、冰新星、连锁闪电、狂暴、幻影打击、医疗舱、冲击波等

#### 升级机制
- 玩家升级时弹出3选1技能卡
- 技能有前置依赖（prereq），需先解锁前置才能出现
- 主动技能上限5级（v4.0提升），每级增强伤害/范围/冷却
- 满级技能附加特殊效果（如钩爪5级=AOE爆炸+眩晕）

#### 全局技能树（skill_tree_view.py）
- 独立于升级的可视化界面，按树状布局展示所有技能
- 只显示玩家"见过"的技能（升级时三选一出现过即解锁显示）
- 已点技能高亮显示，等级影响视觉效果
- 支持鼠标拖拽/滚轮缩放（键控）、手指拖拽（触控）
- 按键打开（默认T键或暂停菜单入口）

### 3.6 Buff系统（BuffManager）

**位置**：`buff.py`

#### BuffType枚举
速度提升、伤害提升、防御提升、燃烧、中毒、流血、冰冻、眩晕、减速、狂暴、生命偷取等。

#### 机制
```python
buff_manager.add_buff(BuffType, duration=10.0, damage_per_tick=5)
buff_manager.update(dt, entity) → (heal_events, damage_events)
buff_manager.get_speed_mult() / get_damage_mult() / ...
```
- 每个Buff有持续时间、每tick伤害/治疗
- 同类Buff叠加刷新持续时间
- 玩家和敌人各有独立的BuffManager

### 3.7 符文系统（Runes）

**位置**：`runes.py`

- 宝箱（TREASURE_CHEST）开出的局内永久buff
- 符文类型：伤害、速度、生命、护甲、暴击、经验加成等
- 效果直接叠加到玩家属性，持续整局
- 通过 `self.rune_buffs` 字典管理

### 3.8 世界与地图（GameWorld）

**位置**：`world.py`

#### 地图类型（MapType）
沦陷的校园、废弃街道、市中心、郊区、核电站等。

#### 分块加载
```python
self.chunk_size = 2000
self.generated_chunks = set()
ensure_chunks_around(player_x, player_y)  # 只生成玩家周围的区块
```
障碍物（墙/车/树）按区块生成，避免全地图预加载。

#### 尸潮管理器（HordeManager）
```python
self.timer, self.horde_active, self.current_horde_size
should_spawn() → EnemyType or None
```
- 尸潮频率和规模随时间/难度动态调整
- 击败Boss后在Boss死亡位置刷新奖励（武器箱/宝箱/符文）

#### 特殊道具（SpecialItem）
疫苗、血包、弹药箱、速度提升、伤害提升、护盾修复、武器箱、宝箱、技能槽、Buff护符、燃烧弹、烟雾弹、集束炸弹、EMP等。
- 支持`magnetized`磁吸（被钩爪勾中后拉向玩家）

### 3.9 图鉴系统（Codex）

**位置**：`codex.py` 数据 + `renderer.py::_draw_codex()` 渲染

#### 分类
基础僵尸、特殊僵尸、Boss、武器、世界观、剧情资料等。

#### 解锁机制
- 僵尸图鉴：游戏中遇到（生成）该类型僵尸即解锁
- 武器图鉴：游戏中获得该武器即解锁
- 解锁数据持久化到存档，非正常退出也保存（即时写入）

#### 交互
- 顶部分类标签点击切换
- 列表支持鼠标滚轮/触控手指滑动滚动
- 点击条目显示详情（描述/属性/掉落）

---

## 四、输入系统

### 4.1 双模式架构

```python
ControlMode.KEYBOARD  # 键控（PC默认）
ControlMode.TOUCH     # 触控（Android默认，PC也可切换）
```

**关键原则**：输入逻辑遵循用户选择的模式，PC上也可能使用触控。事件底层统一处理，不假设平台。

### 4.2 键控输入

```python
keys = pygame.key.get_pressed()
# 移动: WASD / 方向键
# 射击: 鼠标左键 / J
# 换弹: R
# 切换武器: Q / 滚轮
# 疾跑: 左Shift / 右Shift  ← v4.0新增
# 技能: G（瞄准）/ 空格（释放）/ 1-9数字键
# 技能树: T
# 暂停: ESC / P
```

### 4.3 触控输入

```python
self.joystick = VirtualJoystick(120, BASE_HEIGHT-120, 70)  # 移动摇杆
self.aim_button = AimButton(...)                               # 攻击/瞄准摇杆
self.sprint_button = TouchButton(230, BASE_HEIGHT-230, 38, '跑', (100,200,255))  # 疾跑 ← v4.0
self.touch_buttons = {shoot, weapon_switch, pause, chat}
self.skill_selector = SkillSelector(...)  # 技能切换/轮盘
self.skill_caster = SkillCaster(...)      # 技能释放/瞄准
self.throwable_caster = SkillCaster(...)  # 投掷物
```

**触控事件格式**：统一转为 `{"type": "down"/"move"/"up", "pos": (x,y), "id": finger_id}` 字典列表，所有触控组件消费同一事件流。

### 4.4 摇杆卡死修复（v4.0）

**问题**：持续操作摇杆时，如果游戏状态切换到对话/升级/暂停，摇杆的`FINGERUP`事件丢失，导致摇杆卡死在某方向。

**修复**：
1. 每次状态切换时调用 `_reset_touch_controls()`，重置所有摇杆/按钮状态
2. 摇杆内部维护`touch_id`，`FINGERUP`时按ID匹配释放
3. 每帧检查：如果摇杆active但对应finger_id不在当前触控事件中，自动重置

---

## 五、渲染系统

### 5.1 渲染管线

```
Renderer.render()
  ├── 清屏（黑色背景）
  ├── 按 GameState 分发:
  │     ├── MENU → _draw_menu()
  │     ├── PLAYING → _draw_game()
  │     │     ├── 世界（地图/障碍物/道具）
  │     │     ├── 敌人
  │     │     ├── 玩家+武器
  │     │     ├── 投射物+粒子
  │     │     ├── HUD（HP/体力/经验/武器/Buff/小地图）
  │     │     └── 触控控件（仅TOUCH模式）
  │     ├── PAUSED → _draw_pause()
  │     ├── LEVEL_UP → _draw_level_up()
  │     ├── CODEX → _draw_codex()
  │     ├── SKILL_TREE → _draw_skill_tree()
  │     └── ...其他状态
  └── pygame.display.flip()
```

### 5.2 摄像机与缩放

```python
self.camera.x = player.x - BASE_WIDTH/2/scale  # 摄像机跟随玩家
self.scale = min(screen_w/BASE_WIDTH, screen_h/BASE_HEIGHT)  # 等比缩放
```
所有世界坐标 → 屏幕坐标：`screen_x = (world_x - camera.x) * scale`

### 5.3 HUD元素
- HP条（左上，红色）
- **体力条**（HP条下方，蓝色/金黄/红色，v4.0新增）
- 经验条（体力条下方，青色）
- 等级+分数
- 武器信息（弹药/换弹进度）
- Buff图标列表
- 小地图（右上）
- 尸潮倒计时（顶部中央）

---

## 六、Mod系统

### 6.1 架构

**位置**：`mod_loader.py`

```
ModLoader
  ├── scan_mods()      # 扫描 mods/ 目录
  ├── load_mod(id)     # 执行mod的main.py，注册钩子
  ├── unload_mod(id)   # 卸载mod
  ├── trigger_hook(name, *args)  # 触发钩子，遍历所有已启用mod
  └── mod_api          # 暴露给mod的API对象
```

### 6.2 Mod目录结构
```
mods/
  └── my_mod/
      ├── mod.json      # 元数据（name/version/author/description）
      └── main.py       # 入口，定义 register(mod_api) 函数
```

### 6.3 钩子点
`on_game_start`, `on_game_tick`, `on_player_damage`, `on_enemy_spawn`, `on_enemy_death`, `on_keydown`, `on_level_up`, `on_horde_start`, `on_horde_end` 等。

### 6.4 Mod API
mod通过 `mod_api` 对象访问：`mod_api.log()`, `mod_api.get_player()`, `mod_api.spawn_enemy()`, `mod_api.add_buff()`, `mod_api.load_mod_data()`, `mod_api.save_mod_data()` 等。

### 6.5 Mod管理页面
- 主菜单 → Mod管理
- 列表显示所有mod，单击显示详情
- 启用/禁用切换（重启生效）
- 开发者模式mod（dev_mode）不加入build_encrypted.py打包

---

## 七、存档与持久化

### 7.1 存档数据
- 玩家位置/HP/等级/经验/武器/技能
- 世界状态（已生成区块/道具/敌人）
- 游戏时间/难度/模式
- 图鉴解锁状态（即时写入，非正常退出也保留）
- 已收集文本资料
- 成就进度
- Mod启用状态

### 7.2 存档文件
- 存档路径：用户目录下 `.zombie_survivor/save.dat`（加密）
- 图鉴/成就/文本收集：独立文件，即时写入
- 存档加密：自定义XOR+Base64，防止篡改

---

## 八、难度系统

| 难度 | 玩家HP | 伤害倍率 | 敌人HP | 敌人伤害 | 尸潮频率 |
|------|--------|---------|--------|---------|---------|
| 简单 | 130 | 1.2x | 0.7x | 0.7x | 慢 |
| 普通 | 100 | 1.0x | 1.0x | 1.0x | 中 |
| 困难 | 80 | 0.9x | 1.5x | 1.3x | 快 |

难度系数应用于：敌人生成概率、Boss属性、奖励品质、成就系数。

---

## 九、已知技术要点与坑

### 9.1 颜色常量
所有颜色定义在 `config.py`，使用时 `from config import *`。新增颜色必须在config.py定义，不能在文件内硬编码RGB元组（除非是临时UI色）。

### 9.2 dt归一化
所有移动/计时用 `dt * 60` 归一化到60fps。`speed=3.5` 表示60fps时每帧移动3.5像素。

### 9.3 事件消费
触控事件是字典列表 `[{"type":..., "pos":..., "id":...}]`，不是pygame.event对象。访问用 `event["type"]` 而非 `event.type`。

### 9.4 钩爪与敌人控制
被钩爪勾中的敌人（`grappled=True`）在 `Enemy.update()` 中直接return，不做自主移动。位置完全由 `RiotGear._update_grapple()` 控制。不要在Enemy.update中添加grappled状态的自行移动逻辑，会导致冲突。

### 9.5 状态切换时重置触控
任何 `self.state = GameState.XXX` 切换后，如果从PLAYING切出，必须调用 `_reset_touch_controls()` 防止摇杆卡死。

### 9.6 编译检查
修改任何.py文件后必须运行 `python -m py_compile filename.py` 验证语法。

---

## 十、打包与发布

### 10.1 PyInstaller打包
```bash
python build_encrypted.py
```
- 单文件架构，输出到 `dist_encrypted/`
- 核心模块编译为.pyc并加密
- `dev_mode` mod不打入发布包
- 打包后运行 `verify.py` 校验完整性

### 10.2 Android打包
通过 python-for-android (p4a) 打包APK，架构arm64-v8a，NDK r25c。

---

*本文档随游戏版本更新维护。修改核心系统后请同步更新对应章节。*
