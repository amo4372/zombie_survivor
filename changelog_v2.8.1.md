# 僵尸幸存者 v2.8.1 更新日志

## 一、修复：KeyError: 'damage_timer'

**现象**：向某（Boss）的烟雾弹命中后游戏直接崩溃。

**根因**：`mix_playing.py` 里创建烟雾区域时只写了 `timer`，**漏了 `damage_timer`**，
而 `_update_smoke_zones` 每帧执行 `zone["damage_timer"] -= dt` → KeyError。
其余 6 处区域创建点都有这个字段，唯独这一处没有。

**修复**：补上 `damage_timer: 0.0`；同时把燃烧/烟雾区域的更新改为
`zone.get("damage_timer", 0.0)` 兜底，**任何缺字段的区域都不再能崩掉游戏**。

## 二、修复：NoneType object has no attribute 'update'

**根因**：主循环里 `world.update()` / `horde_manager.update()` /
`particles.update()` 三处**没有空值防御**。这些对象一旦因初始化顺序或
异常回退为 None，就会抛 `NoneType has no attribute 'update'` 并打断整帧
（开发者面板的某些操作会走到这条路径）。

**修复**：三处全部加空值判断；顺带给区域特效里的 `particles.spawn` 也加了防御。

## 三、修复：ModuleNotFoundError: No module named 'replay'

**根因**：v2.8.0 新增的回放系统 `replay.py` 是**根目录下的新文件**，
但 `build_release.py` 的必需文件清单里没有它 —— 发布包里根本没这个文件，
`mix_replay.py` 顶部 `from replay import ...` 直接失败。

这也是本次更新最该记住的教训：新增顶层模块必须同步登记进打包清单。
（已同步在清单里加注释标明依赖关系。）

## 四、自动更新改为「只下载真正变化的文件」

以前每次更新都要下 **76 MB 全量包**，哪怕只改了一行代码。现在：

1. 先从 Release 资产下载 **manifest.json**（几 KB，含每个文件的 MD5）
2. 与本地文件逐个比对 MD5，**只挑出真正变化或缺失的文件**
3. 逐文件下载并应用（单文件超时 15 秒，带重试）
4. 变化文件超过 400 个时自动改用全量包（增量未必更快）
5. 增量失败（拿不到清单 / 下载异常）→ **自动回退全量包**，不会卡住

用户数据（`config.json`、存档、记录、日志等）在比对阶段就被排除，
**绝不会被覆盖**。

## 五、修复：合作模式争分夺秒一打开就结束

**根因**：`_check_round_end`（阵营胜负判定）在争分夺秒下会统计"未出局的阵营"。
合作模式里 P1、P2 都是 team 0，**全场只有 1 个阵营**，
于是 `len(_active) <= 1` 恒成立 → 开局第一帧就返回 0，
判为"阵营 0 胜利" → 立刻 GAME_OVER。

**修复**：阵营胜负只在**真正多阵营（PvP）**时有意义。
合作模式（所有玩家同阵营且未开 PvP）直接返回 None，不做阵营判定；
争分夺秒合作模式正常走"倒计时耗尽 → 挑战结算"的流程。
PvP 异阵营判定不受影响（已回归验证）。

## 文件变更
- `zombie_pkg/mix_playing.py` — 烟雾区域补 damage_timer；world/horde/particles 空值防御；阵营胜负修复
- `zombie_pkg/mix_effects.py` — 区域字段 .get 兜底；粒子空值防御
- `zombie_pkg/game_core.py` — 救援结算统一走死亡反应时间
- `updater.py` — **增量更新**（清单比对 + 逐文件下载 + 失败回退全量）
- `build_release.py` — 补登记 `replay.py`
- `smoke_v281.py` — 新增快速测试 22 项（不跑帧）
