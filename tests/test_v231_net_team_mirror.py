# -*- coding: utf-8 -*-
"""v2.3.1 专项测试：
1) 阵营"无论如何还是同阵营"根因修复：房间阵营默认"自动（开局轮转分阵营）"，
   显式 team 才固定；game_core 分配对 team=None 走 _idx % _nteams 轮转
2) 同屏/网络 PvPvE 阵营可视化：玩家头顶 A/B 标签、快照带 team、客户端按敌我渲染
3) 近战 PvP 互砍（melee_hit_players 玩家命中）
4) 网络联机更自定义：端口输入、最大人数/玩法/模式/地图配置行；主机驱动客户端玩家
   （_update_net_host 消费 net_host.inputs，客户端 aim 上报，game_core 已挂载）
5) 更新器自动选择最快下载节点/代理（pick_fastest_mirror / _mirror_candidates）
6) 下拉栏图层/滚动（末尾统一绘制 + 滚动条 + 滚轮 + 触控拖动）
"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = 0
fail = 0

def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail += 1
        print(f"  [FAIL] {name}")

def read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()

src_draw = read("renderer_pkg/draw_ui.py")
src_gc = read("zombie_pkg/game_core.py")
src_net = read("zombie_pkg/mix_net.py")
src_inp = read("zombie_pkg/mix_input.py")
src_cmb = read("zombie_pkg/mix_combat.py")
src_pl = read("entities_pkg/player.py")
src_up = read("updater.py")

print("== 1) 阵营逻辑 ==")
check("房间阵营默认'自动（开局分阵营）'",
      "自动（开局分阵营）" in src_draw and "自动（按序号轮转）" in src_draw)
check("阵营下拉选 0→自动(None)、1..N→显式",
      "None if v == 0 else v" in src_draw)
check("一键统一不覆盖自动(team=None 不复制)",
      "if _pvpm and _src_cfg.get(\"team\") is not None:" in src_draw)
check("game_core 分配：team 为 None 走轮转", "_idx % _nteams" in src_gc)
check("game_core 分配：显式 team 才用配置", '_rcfg.get("team") is not None' in src_gc)

print("== 2) 阵营可视化 ==")
check("玩家头顶 A/B 阵营标签", "'AB'[_tid % 2]" in src_pl and "team_id" in src_pl.split("def draw")[-1])
check("网络快照带 team 字段", '"team": int(getattr(_p, \'team_id\', 0) or 0)' in src_net)
check("客户端按敌我渲染（敌方红标）", '"敌方 " if _enemy else ""' in src_draw and "_my_team" in src_draw)

print("== 3) 近战 PvP 互砍 ==")
check("近战命中非队友玩家（melee_hit_players）", "melee_hit_players" in src_cmb and "_pp.take_damage(self.melee_attack_damage" in src_cmb)
check("攻击结束清空玩家命中集", "melee_hit_players.clear()" in src_cmb)

print("== 4) 网络联机更自定义 ==")
check("端口输入框字段初始化", "net_port_input" in src_gc and "net_port_focused" in src_gc)
check("端口键盘输入处理", "net_port_focused" in src_inp and "net_port_input += ev.text" in src_inp)
check("主机/客户端端口取自输入框", "int(getattr(self, 'net_port_input', '26000')" in src_net)
check("网络页配置行：人数/玩法/模式/地图",
      "最大人数：" in src_draw and "玩法：" in src_draw and "模式：" in src_draw and "地图：" in src_draw)
# v2.4.0 网络页改下滑栏：人数/玩法/模式/地图为 _dd_row 下拉（不再点击循环）
check("网络页下滑栏：_dd_row 与 _opt_pending 尾渲染",
      "def _dd_row" in src_draw and "_opt_pending" in src_draw and "net_dd_key" in src_draw)
check("网络页下滑栏覆盖人数/玩法/模式/地图",
      '"net_cnt"' in src_draw and '"net_pvp"' in src_draw and '"net_mode"' in src_draw and '"net_map"' in src_draw)
check("主机驱动客户端玩家 _update_net_host", "def _update_net_host" in src_net)
check("_update_net_host 消费 net_host.inputs/get_input", "self.net_host.get_input(_idx)" in src_net)
check("客户端输入帧上报 aim 角度", '"aim": _aim' in src_net)
check("game_core 已挂载 _update_net_host", "self._update_net_host(dt)" in src_gc)
check("主机驱动按客户端索引驱动 player{idx+1}",
      'getattr(self, f"player{_idx + 1}", None)' in src_net)
check("主机驱动含技能最小实现 _net_drive_skill", "def _net_drive_skill" in src_net)

print("== 5) 更新器最快节点/代理 ==")
check("候选节点生成 _mirror_candidates", "def _mirror_candidates" in src_up)
check("测速选最快 pick_fastest_mirror", "def pick_fastest_mirror" in src_up and "sample_bytes" in src_up)
check("download_update 下载前测速", "pick_fastest_mirror(download_url)" in src_up and 'UPDATE_STATE["mirror"]' in src_up)
check("UPDATE_STATE 记录所选节点/延迟", '"mirror": ""' in src_up and '"mirror_latency": 0.0' in src_up)

print("== 0) v2.3.2~2.3.4 崩溃修复 ==")
check("下拉滚动值强制 int（Android float 坐标导致 _dopts[float]）",
      "_sval = int(_sc.get(_dkey, 0) or 0)" in src_draw
      and "_gidx = int(_sval) + _oi" in src_draw
      and "_sc[_dkey] = int(_sval)" in src_draw)

check("房间页定义 sh（安卓端 NameError 根因）",
      "sh = self.game.scaled_height  # v2.3.2" in src_draw)
check("下拉裁剪用 clip()（兼容缺失 clip_ip 的 Android pygame 构建）",
      "_clip = _clip.clip(pygame.Rect(0, 0, sw, sh))" in src_draw and ".clip_ip(" not in src_draw)
check("scrap 用 find_spec 探测（避免 import RuntimeWarning）",
      'find_spec("pygame.scrap")' in src_gc and "hasattr(pygame, 'scrap')" not in src_gc)

print("== 6) 下拉栏图层/滚动 ==")
check("展开下拉统一末尾绘制（图层最上层）", "_dd_pending" in src_draw and "for _dkey, _drect, _dopts, _dset, _dcur in _dd_pending:" in src_draw)
check("下拉带滚动条", "_bar_x" in src_draw and "_bar_w" in src_draw)
check("滚轮滚动", 'te.get("type") == "wheel"' in src_draw)
check("触控拖动滚动", "dd_drag" in src_draw and "dd_drag_y" in src_draw)
check("MOUSEWHEEL 统一进事件流", '"type": "wheel"' in src_inp)

print(f"\n===== v2.3.1 专项结果: {ok} 通过, {fail} 失败 =====")
sys.exit(1 if fail else 0)
