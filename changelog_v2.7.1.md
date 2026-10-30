# 僵尸幸存者 v2.7.1 更新日志

## 核心修复：P2 钩爪勾不到任何东西

**根因**：钩爪的飞行碰撞检测函数是**只给 P1 跑的**。

`_update_grapple_collision()` 内部写死了 `self.player.riot_gear`，主循环每帧只调用它一次。
也就是说：P2（以及 P3/P4）的钩爪发射后，钩爪头飞出去的整个过程**从来没有做过任何碰撞判定**——
僵尸、玩家、道具、经验球、资料、宝箱全都不会被勾中。只有「发射瞬间就锁定了目标」的极少数情况能生效，
所以表现就是「P2 钩爪什么都勾不到」。

修复方式不是给 P2 再复制一份，而是把钩爪整体**通用化**：
- `_update_grapple_collision_for(player)`：以 player 为参数，逻辑与旧版等价
- `update_grapple_collisions()`：遍历玩家注册表，**每一位玩家都跑一遍**碰撞
- 旧函数名保留为薄封装（委托给通用实现），其它调用点不受影响

### 顺带修掉的「穿透」问题
钩爪头单帧位移可达 150px，旧判定只看「钩爪头当前所在的那一个点」，
细小目标（经验球/道具/资料）会被整帧跨过去，永远勾不到——P1 同样有这个毛病。
现在改用「上一帧位置 → 当前位置」的**线段距离**判定，所有玩家都受益。

## 多对象/多玩家通用层（新增 `zombie_pkg/mix_players.py`）

这是让「玩家」从写死的全局变量变成一等对象的第一步。

### 玩家注册表
- `tag_of(player)` / `get_player(tag)` / `slot_index_of(player)`：玩家 ↔ 槽位标签(P1~P4) 互查
- `iter_player_slots()` / `registered_players()`：按槽位顺序遍历
- `ensure_player(tag, x, y)`：**可按槽位动态创建玩家实例**，自带完整能力
  （技能树、防爆套装、技能CD表、Buff管理、阵营标识），与单人模式 P1 无差异

### 每玩家运行时上下文（UI 数据管理按玩家分离）
- `camera_for(player)`：独立摄像机，**缺失时惰性创建**（P3/P4 因此也能拿到视口）
- `controls_for(player)`：独立控件集合
- `selected_skill_of(player)` / `set_selected_skill(player, st)`：独立当前技能
- `cycle_selected_skill(player, unlocked)`：技能轮换（单/多人共用）
- `iter_player_ctx()`：一次拿到 (tag, player, camera, controls)

### 钩爪目标解算统一
`resolve_grapple_target(player, dir_x, dir_y, dist, radius)` 成为**唯一的目标解算入口**：
优先级 倒地队友(救援) > 异阵营玩家(PvP) > 同阵营存活玩家 > 僵尸。
P1 与 P2、键控与触控、单人与多人现在走**同一份实现**，不会再出现两套逻辑行为分叉。

### 玩家对玩家
钩爪飞行碰撞新增「其他玩家」判定（此前只有发射瞬间的搜索能勾到人）：
- 合作模式：同阵营队友可勾（救援/自拉），倒地队友优先
- PvP：异阵营玩家可勾，命中后进入 0.8s 打断绳索 QTE（免疫期内无法被勾）

## 其它
- `build_split_viewports` 改为从玩家注册表推导，P3/P4 也能正确分到视口

## 文件变更
- `zombie_pkg/mix_players.py` — **新增**：玩家注册表、每玩家上下文、通用钩爪
- `zombie_pkg/__init__.py` — Game 类混入 `PlayerRegistryMixin`
- `zombie_pkg/mix_playing.py` — 钩爪碰撞改为逐玩家执行；旧函数委托通用实现
- `zombie_pkg/mix_skills.py` — P1 钩爪目标搜索改用统一解算
- `zombie_pkg/mix_multi.py` — P2 钩爪目标搜索改用统一解算
- `entities_pkg/gear.py` — 新发射时清空钩爪头轨迹缓存（抗穿透配套）
- `renderer_pkg/draw_multiplayer.py` — 视口构建走注册表，支持 N 名玩家
- `smoke_v271.py` — **新增** v2.7.1 冒烟测试（37 项）

## 已知未覆盖范围
本次是把「通用层」落地并把钩爪（本次报的 bug）彻底通用化。
游戏内仍有大量历史代码直接引用 `self.player`，尚需逐一迁移到注册表接口；
功能上这些路径目前仍以 P1/P2 为主，但敌人在索敌时已经是遍历全部玩家取最近的。

---

## v2.7.1 补充：数据层平等 + BOSS 对话 Traceback 修复

### BOSS 登场对话报错 / 卡死（全模式）
**现象**：任何模式刷出 Boss 就抛 Traceback，或整个游戏冻住。

**根因有三层**：
1. **强制切 DIALOGUE 冻结世界**：旧实现把游戏切到 `GameState.DIALOGUE`，
   玩家不能动、另一位玩家也被冻住；必须手动点完才能继续。
   多人模式下另一位玩家完全被卡死。
2. **重复触发打断状态机**：对话中途又刷出一只 Boss，旧代码只做了
   `dialogue.active = False`，既不清索引/选项、也不回调 `on_complete` ——
   状态机被顶掉后再也回不到 PLAYING，彻底卡死。
3. **故事模式专属字段在其它模式下不存在**：`story_fragment_items`、
   `map_time_elapsed` 等只在故事模式分支初始化，渲染层却无条件遍历它们 →
   `AttributeError` 打断整帧渲染（这就是"刷 Boss 时报错"的直接来源）。

**修复**：
- BOSS 台词改为**屏幕底部非阻塞字幕**（自动逐句播放、播完自动清空），
  不切状态、不拦截输入、不冻结世界。带选项的那句改为把选项内容并入台词文本。
- 结局对话**仍走原交互流程**（保留多结局选择），且不会被 Boss 字幕顶掉。
- `story_fragment_items` / `story_pending_fragments` / `story_collected_fragments` /
  `current_map_index` / `map_time_elapsed` / `map_transition_timer` /
  `special_event_*` 现在**所有模式一律初始化**，数据层平等。
- 渲染层对剧情收集物再加一层 `getattr` 兜底。

### 数据层平等（P1 / P2 / … / Pn）
新增 `PlayerContext`：每位玩家一套**结构完全相同**的运行时数据
（player / camera / controls / selected_skill / upgrade_paused / pending_levels /
grace_timer / hud / aiming）。P1 不再享有特权字段，它只是槽位 0 的那个 context。

关键设计：散落在 `self` 上的 `player2` / `camera2` / `p2_controls` /
`p2_selected_skill` 等旧属性与 `PlayerContext` **双向同步**——
`camera` 与 `controls` 存的是同一对象引用，`__setattr__` 把旧式赋值镜像回 context，
`__getattr__` 让未显式设置的槽位从 context 取值。
这样历史代码不用改也能受益于统一数据层，且不会再出现"只有 P1 有某字段"。

此前 P2 的升级/暂停状态是挂在 game 上的 `_upgrade_pause_player` 字符串，
现在每个玩家自己的 context 里都有 `upgrade_paused` / `pending_upgrade` /
`pending_levels` / `grace_timer`，与 P1 完全对等。
