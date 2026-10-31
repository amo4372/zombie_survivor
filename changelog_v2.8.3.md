# 僵尸幸存者 v2.8.3 更新日志

## 一、修复：NameError: name 'CACHE_DIR' is not defined

**现象**：检查更新时后台线程直接崩，更新永远做不了。

**根因**：增量更新里写了 `os.path.join(game_dir, CACHE_DIR, "incremental")`，
但常量实际叫 `UPDATE_CACHE_DIR`。这个分支只在真正走增量下载时才执行，
所以此前一直没暴露 —— 直到 v2.8.1 上线增量更新才被触发。

**修复**：改用 `UPDATE_CACHE_DIR`；顺带给 `connect()` 加了重试
（某些文件系统首次打开 SQLite 会瞬时返回 disk I/O error）。

## 二、重大重构：数据与代码行为分离（SQLite）

新增 `gamedata/` 包，游戏机制数值全部落到 **`game_data.db`**（SQLite，游戏根目录）。

**策划工作流**：用任意 SQLite 工具打开 `game_data.db` 改数值 → 存盘 → 生效。
不需要碰代码，也不需要重新打包。

### 已迁移的数据表

| 表 | 内容 | 行数 |
|---|---|---|
| `weapons` | 全部武器：伤害/射速/射程/弹速/散布/穿透/弹体大小/震屏/颜色/描述/弹药/换弹 | 31 |
| `enemies` | 全部敌人：血量/速度/伤害/体型/颜色 + 特殊机制（extra JSON） | 32 |
| `runes` | 符文：名称/颜色/稀有度/描述/最大层数 | 15 |
| `difficulty` | 难度：敌我双方各项倍率/掉落/经验/初始武器数 | 4 |
| `tuning` | 全局标量：玩家基础属性、尸潮间隔与规模、经验、掉落、Boss 倍率等 | 18 |

`extra` 列存 JSON，承载各单位的特殊机制（如爆炸僵尸的爆炸伤害、盾兵的正面减伤）。

### 关键保障

1. **绝不因数据库崩溃**：任何读取失败 / 缺表 / 缺行 → 回退代码内置默认值
2. **首次运行自动建库**：用代码现有数值播种，行为与旧版完全一致
3. **数据库不被更新覆盖**：`game_data.db` 列入用户数据，自动更新与打包都跳过它，
   玩家/策划调好的数值永远不会丢
4. **热重载**：按文件修改时间自动重载，改库后无需重启（重新开局即生效）
5. **兼容受限文件系统**：`journal_mode=MEMORY` + 连接重试，
   Android 外置存储 / 容器挂载目录也能正常读写

### 命令行工具

```bash
python -m gamedata sync      # 只补缺失行（保留手工修改）★ 推荐
python -m gamedata rebuild   # 清空重建（会丢失手工修改）
python -m gamedata export    # 导出 game_data.json，便于对比/版本管理
python -m gamedata verify    # 校验完整性（缺表/缺行）
python -m gamedata show runes  # 打印某张表
```

## 三、文件结构优化

- 新增 `gamedata/` 包（`__init__` / `db` / `schema` / `defaults` / `seed` / `cli`）
- 根目录 39 个 `.py` → **28 个**
- 全部测试脚本（smoke_v20xx / smoke_v2xx / regression）移入 `tests/`
- 开发工具（音乐生成、加密工具、API 发布脚本等）移入 `tools/`
- 数值抽取走**纯 AST**，不 import 游戏模块 —— 缺 pygame 的环境也能建库

## 文件变更
- `gamedata/` — **新增**：数据层（SQLite 读写 + 默认值 + 播种 + CLI）
- `updater.py` — 修复 CACHE_DIR；`game_data.db` 列入用户数据；连接重试
- `weapons.py` — 武器数值改从数据库读（带内置兜底）
- `entities_pkg/enemy.py` — 敌人数值改从数据库读
- `runes.py` — 符文数值改从数据库读
- `config.py` — 难度配置改从数据库读
- `build_release.py` — 打包 `gamedata`；排除 `game_data.db/json`
- `tests/smoke_v283.py` — 新增快速测试 45 项（不跑帧）
