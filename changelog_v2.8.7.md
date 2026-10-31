# 僵尸幸存者 v2.8.7 更新日志

## 一、修复：AttributeError: 'NoneType' object has no attribute 'draw'

死亡瞬间渲染伤害数字时崩溃（`draw_play.py` → `dn.draw(...)`）。

**根因**：`damage_numbers` 列表里混进了 `None`。来源是 Mod API
`spawn_damage_number()` —— 它 `from entities import DamageNumber`，
但 `entities` 模块里根本没有这个类（实际在 `ui_pkg/fx`），
导入失败后把 `None` 塞进了列表。渲染层无条件调用 `.draw()` → 整帧渲染被打断。

**修复**：
1. 渲染时跳过 `None` / 无 `draw` 的元素，并顺手清理列表（避免无限增长）
2. 浮动文字同样处理
3. Mod API 改为从正确位置导入（`ui` → `ui_pkg.fx` 兜底），且返回前校验非 None

## 二、修复：回放按钮"一次点击算两次"

移动端（Pydroid3 / Android）触摸会**同时**产生两套事件：
`FINGERDOWN/FINGERUP` 和 `MOUSEBUTTONDOWN/MOUSEBUTTONUP`。
两者的"抬起"往往落在不同帧：触控在第 N 帧触发一次，鼠标在第 N+1 帧再触发一次
→ 点一下播放=播了又停，点一下倍速=跳两档，点一下退出=连退两层。

**修复**：`Button` 增加 180ms 去抖。同一次物理点击只放行一次，
超过间隔的正常连点不受影响（已验证）。

## 三、修复：多人 / PvP 不保存录像、死亡详情空白

只有"玩家死亡"路径（`_begin_death_reaction`）做了归档，
**PvP 阵营胜利 / 计时结算等路径完全没做** —— 不冻结伤害日志、不保存回放。
这就是"多人模式不保存录像""PvP 死亡详情一片空白"。

**修复**：新增统一的 `finalize_replay()`（冻结全部玩家伤害日志 →
强制采样最后一帧 → 写事件 → 保存 .zsr）。所有结束路径都调用它，
死亡路径也改走同一函数，行为完全一致。

实测双人：回放已保存，快照含 P1/P2，死亡详情 2 行。

## 四、修复：钩爪预瞄线/锁定圈泄漏到别的玩家屏幕

渲染层对**所有玩家**无差别调用 `riot_gear.draw()`，
于是 P2 的预瞄线出现在 P1 屏幕，P1 的锁定圈出现在 P2 屏幕 ——
等于把自己的瞄准意图和锁定目标直接暴露给对手。

**修复**：新增 `own_view` 参数。
- **已发射的绳索/钩头**：所有视口都画（对手看得见你在勾谁，合理）
- **瞄准中的预瞄线 / 锁定圈 / 蓄力弧**：只在本人视口画

`player.draw()` 同步透传该参数（此前主要泄漏点在玩家自绘路径）。

## 五、修复：P2 钩爪自动锁定无效

锁定圈只在 `p2_selected_skill == SkillType.GRAPPLE_PULL` 时更新。
但钩爪在 v2.7.0 后已改为**防爆套装自带能力**，不再占技能卡位 ——
P2 装备套装后瞄准，选中技能并不是 GRAPPLE_PULL，锁定圈永远不更新。

**修复**：新增 `_p2_grapple_available()`，选中钩爪技能**或**已装备防爆套装
均视为可用。键控（长按 U）与触控两条分支都改用新判定。

## 文件变更
- `renderer_pkg/draw_play.py` — 伤害数字/浮动文字 None 防御；其他玩家传 `own_view=False`
- `mod_loader.py` — Mod API 修正 DamageNumber / FloatingText 的导入位置
- `ui_pkg/base.py` — Button 去抖（180ms）
- `zombie_pkg/mix_replay.py` — 新增 `finalize_replay()` 统一局末归档
- `zombie_pkg/mix_feedback.py` — 死亡路径改用统一归档
- `zombie_pkg/mix_playing.py` — PvP 阵营胜利也归档
- `zombie_pkg/mix_multi.py` — 新增 `_p2_grapple_available()`；两条分支改用新判定
- `entities_pkg/gear.py` / `entities_pkg/player.py` — `own_view` 视口隔离
- `tests/smoke_v287.py` — 新增快速测试 27 项（不跑帧）

## 验证
- 新增 `tests/smoke_v287.py`：**27 项全过**
- 实测双人：回放保存成功、快照含 P1/P2、死亡详情 2 行、渲染不崩
- 去抖验证：紧随的第二次触发被拦截，间隔后正常连点仍生效
- 回归：v2.8.4 (30)、v2.8.5 (22)、v2.8.6 (26) 全过
