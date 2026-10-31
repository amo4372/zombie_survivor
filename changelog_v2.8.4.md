# 僵尸幸存者 v2.8.4 更新日志

## 一、修复：`'<=' not supported between instances of 'str' and 'int'`

数据库迁移后，SQLite 只有 TEXT/REAL/INTEGER 三种类型，而代码里同一字段可能是
int / float / str / 颜色元组 / bool / dict 混用。直接读回来的值类型对不上。

典型：武器 `ammo` 原为整数 `3`，数据库里按 TEXT 存成 `"3"` →
换弹逻辑 `if self.ammo <= 0` 直接抛类型错误。

## 二、修复：`can't multiply sequence by non-int of type 'float'`

敌人配置读取时**完全没有做颜色转换**（武器/符文做了，敌人漏了）。
`enemy.color` 从数据库读出来是 `"#14501E"` 字符串，
渲染层做 `c * (1.0 - x)` 时就变成"字符串乘浮点"→ 崩溃
（报错栈指向 `ui_pkg/fx.py` 第 37 行，实际根因在数据层）。

## 三、修复：回放 `float & int` 类型错误

回放帧格式升到 v2 后，敌人帧从 7 字段变成 9 字段，`flags` 从**下标 6 移到下标 8**。
`mix_replay.py` 里仍按下标 6 取——v2 下那是 `angle`（float），
`float & 1` 直接抛 `unsupported operand type(s) for &: 'float' and 'int'`。
数据面板一打开就崩。

## 四、修复：函数名与局部变量重名导致渲染崩溃

新增的类型转换助手叫 `_f()`，而 `_draw_replay` 里有个局部变量
`_f = _d.current`（当前帧）→ 调用被遮蔽成"帧对象不可调用"。
已重命名为 `_to_f` / `_to_i`。

## 五、修复：死亡详情的时间一直在往后走

"距死亡 N 秒"此前用实时时钟 `time.monotonic()` 计算。
玩家在结算页停留越久，每条伤害的 `ago` 越大，超出时间窗口后被过滤掉 ——
**表现为看一会儿伤害条目一条条消失**。

改为以**死亡瞬间**为基准（`_damage_log_frozen_at` / `death_detail_base_time`），
数值永久固定，不再随时间漂移。

## 六、统一类型转换层（本次核心）

`gamedata/db.py` 新增 `coerce_like(v, ref)` **以代码内置默认值的类型为准**，
把数据库读出的值强制转换回去：

| 代码里的类型 | 数据库存储 | 读回时 |
|---|---|---|
| 颜色元组 `(20,80,30)` | `#14501E` | 自动还原为元组（兼容 `"(r,g,b)"` 写法） |
| 整数 `3` | `"3"` / `3.0` | 转回 `int` |
| 浮点 `0.38` | `"0.38"` | 转回 `float` |
| 字符串 `"∞"` | `"∞"` | 保持 `str` |
| 布尔 `False` | `0` / `"false"` | 转回 `bool` |
| 字典 `{1: "..."}` | JSON（键变字符串） | **还原 int 键**（否则技能等级描述 KeyError） |
| NULL | — | 回退代码默认值 |

任何转换失败都返回代码默认值 —— **保证类型永远正确，绝不把错类型漏给游戏**。
同时 `key` / `extra` 两个元数据列不再泄漏成对象属性。

## 七、继续数据迁移

新增两张表（累计 7 张）：

| 表 | 内容 | 行数 |
|---|---|---|
| `buffs` | Buff：名称/图标/颜色/是否负面/描述 + 各类倍率（extra） | 25 |
| `skills` | 技能卡：名称/描述/上限/效果键/每级增量/图标色/等级描述 | 52 |

至此共：weapons 31、enemies 32、runes 15、**buffs 25**、**skills 52**、difficulty 4、tuning 18。

## 八、测试脚本路径修正

上一版把测试移进 `tests/` 时，脚本内的 `os.chdir` 仍指向自身所在目录，
导致相对路径全部失效（表现为"编译失败：No such file"）。已统一改为工程根目录。

## 验证
- 新增 `tests/smoke_v284.py`：**30 项全过**
- **全表逐字段类型比对**：weapons / enemies / runes / buffs / skills / difficulty
  与代码内置默认值**零不一致**
- 回归：v2.8.0 (44)、v2.8.1 (22)、v2.8.2 (45)、v2.8.3 (45) 全过

## 文件变更
- `gamedata/db.py` — 新增 `coerce_like` / `merge_row` 类型转换层；各读取方法改用
- `renderer_pkg/draw_replay.py` — 帧解包类型安全；助手函数重命名（修遮蔽）
- `zombie_pkg/mix_replay.py` — flags 下标按 v2 修正 + 类型安全
- `entities_pkg/player.py` — 冻结时刻基准（死亡详情时间不再漂移）
- `zombie_pkg/mix_feedback.py` — 同上
- `buff.py` — Buff 配置接入数据库
- `gamedata/schema.py` / `defaults.py` / `seed.py` — 新增 buffs / skills 表
- `tests/` — 修正路径；新增 smoke_v284.py
