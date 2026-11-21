# 丧尸幸存者 v2.9.22.1

> 保持 2.9.x，未跳 3.0.0。**v2.9.23 与 GPU 实验版已废弃删除**。

## 一、为什么有这个版本

v2.9.23 的画面改动（技能预瞄线当帧摄像机注入、拉远视野按完整范围圈计算）与后续 GPU/GLES 应用在实际设备上表现不如 v2.9.22 的纯 Pygame 路径；视野全量渲染实测密集障碍下 17.38 ms/帧，超过一帧预算。

因此：**画面逐字回退到 v2.9.22**，只把 v2.9.23 里「数值与机制」层的改动合并过来，形成 v2.9.22.1。

## 二、合入（数值 / 机制）

| 项 | 内容 |
|---|---|
| 武器 | `WEAPON_PVP_MULTS` 32 把各自独立；AWM 对玩家 110→**100**；`DATA_VERSION=7`；投射物带 `pvp_mult` |
| 抗性 | `DamagePacket.resist_scale`，按 `1−(1−抗性倍率)×系数` 结算；gear 0.25 / vehicle 0.20 / skill 0.45 / 默认 1.0 |
| 耐久 | 盾 500→300、观察窗 400→220；重卡 900→540、坦克 1800→1080、武直 1100→700、大运 Lv2/Lv3 →900/1320 |
| 湮灭射线 | 取消 300 瞬发，改 220/s、总 480、1.6s 帧伤；对敌方玩家保留 1 HP 不致死；PvE ×0.55 |
| 手雷 | 技能 1.1s→0.32s、投掷物 1.2s→0.42s；技能手雷/EMP 破片对敌方玩家生效（×0.75 + 抗性系数 0.45） |
| 僵尸 | 全部可跨越障碍物，穿越时移速 ×0.35；幽灵/幽影不受阻 |
| 地图 | 游戏内编辑器剥离，独立 `tools/map_editor_standalone.py`（键控+触控）；`.zmap` 零配置导入 `maps/active.zmap` |
| 文档 | `VISION_PERF.md` 保留「不全量启用视野」的实测结论 |

## 三、明确剔除（画面 / 渲染）

- `renderer_pkg/draw_play.py`：`_world_scale` 注入、`_sync_aim_caster` 当帧预瞄同步 —— 不合并
- `ui_pkg/skills_ui.py`：`AIM_RADIUS_BY_SKILL` 与预瞄线视口偏移 —— 不合并
- `zombie_pkg/mix_players.py`：拉远视野按「瞄准距离 + 2R」计算 —— 不合并
- `mix_playing.py` / `mix_multi.py` 中 `_skill_aim_radius` 写入 —— 不合并（同文件里的湮灭锁血 hunk 已单独摘出）
- `glrender_pkg/` / `gpu_refactor/` / GLES 兼容层 —— 全部不进入本版包

## 四、删除清单

- `zombie_survivor_v2.9.23_update.zip`、`changelog_v2.9.23.md`、v2.9.23 回退包
- `zombie_survivor_v2.9.24_update.zip`、`changelog_v2.9.24.md`、GPU 增量/完整运行包与开发快照
- 工作区 `glrender_pkg/`、`gpu_refactor/`、`GPU_RENDER.md` 与 GPU 专项测试
- 游戏内 `renderer_pkg/draw_map_editor.py`、`zombie_pkg/map_editor.py`

保留：独立的 GLES 全新项目与 C++ 迁移文档作为后续重构资料，不属于 Python 游戏本体。

## 五、验证

`tests/smoke_v2922b.py`：静态断言 + 伤害管线数值断言，PASS=xx FAIL=0；全项目 `compileall` 0 失败；包内 manifest、version.txt、zip 完整性通过。按「测试时间缩短」口径不跑长回归与长帧。

## 六、边界

- 网络联机仍为空实现，等完整叙述后重写。
- 线上 Release 需另行同步（删除 v2.9.23 Tag/Release 并把 latest 指向本版）。
