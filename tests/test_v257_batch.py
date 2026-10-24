# -*- coding: utf-8 -*-
"""v2.5.7 批次测试（运行时行为验证 + 源码接线断言）

覆盖本轮修复：
#155 PvP 绿色队友箭头暴露敌人位置（按阵营过滤）
#156 多人口径统一：技能 CD 表唯一真源 + 钩爪 CD + P2 载具 CD
#157 过热倾泻 P2 计时器永不递减（共用更新函数）
#158 湮灭射线长按预瞄不改变释放方向
#159 死亡轮回长按没有预瞄圈
#160 载具形态下任何技能长按都强制下车
#161 多人救援/死亡链路（超时后被重新判定倒地 / 救援永不打断）
#162 P2 技能按钮不显示冷却 + HUD 缺投掷物/防爆信息
#163 地图边界警示对 P2 视口无效
#164 敌人钩爪勾到载具形态玩家
#165 多人名字输入退不出输入态 + 自定义名字不显示
#166 多人房间配置不持久化
#167 P1/P2 开局投掷物规则不一致
#168 道具刷新只围绕 P1（P2 永远捡不到补给）
#169 PvP 缺少毒圈机制
#170 争分夺秒配乐 MIDI 生成 / 乐器清单 / 代码支持导入最终 OGG
"""
import os
import re
import subprocess
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OK = 0
FAIL = 0


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ======================================================================
print("== #155 PvP 绿色队友箭头（按阵营过滤） ==")
_dm = read("renderer_pkg/draw_multiplayer.py")
check("队友指示按 pvp_enabled 分支", "pvp_enabled" in _dm)
check("异阵营玩家被跳过（不画绿箭头）",
      re.search(r"team_id.*!=\s*_my_team[\s\S]{0,120}continue", _dm) is not None)
_du = read("renderer_pkg/draw_ui.py")
check("网络客户端同样按阵营过滤主机箭头",
      re.search(r"_peer_enemy[\s\S]{0,200}if not _peer_enemy", _du) is not None)

# ======================================================================
print("== #156 技能 CD 统一表 ==")
from config import SkillType, get_skill_cooldown, SKILL_COOLDOWNS
check("config 提供 SKILL_COOLDOWNS", isinstance(SKILL_COOLDOWNS, dict) and len(SKILL_COOLDOWNS) > 15)
check("钩爪技能 CD = 2.0s", get_skill_cooldown(SkillType.GRAPPLE_PULL, 1.0) == 2.0)
check("钩爪 CD 吃冷却缩减", get_skill_cooldown(SkillType.GRAPPLE_PULL, 0.5) == 1.0)
check("湮灭射线 CD = 35s", get_skill_cooldown(SkillType.RAILGUN_ANNIHILATION, 1.0) == 35.0)
check("死亡轮回 CD = 30s", get_skill_cooldown(SkillType.SCYTHE_DANCE, 1.0) == 30.0)
check("载具召唤 CD = 60s", get_skill_cooldown(SkillType.VEHICLE_SUMMON, 1.0) == 60.0)
_ms = read("zombie_pkg/mix_skills.py")
check("P1 短按走统一表", "get_skill_cooldown(skill_type, self.player.cooldown_mult)" in _ms)
check("P1 预瞄也走统一表（原来缺传说级技能→一律 10s）",
      _ms.count("get_skill_cooldown(skill_type, self.player.cooldown_mult)") >= 2)
_mm = read("zombie_pkg/mix_multi.py")
check("P2 短按走统一表", "get_skill_cooldown(skill_type, p2.cooldown_mult)" in _mm)
check("P2 预瞄走统一表", _mm.count("get_skill_cooldown(skill_type, p2.cooldown_mult)") >= 2)
check("P2 载具 CD 不再被写成 12s", "cd = 12.0" not in _mm.split("def _use_skill_p2(")[1].split("def ")[0])
check("钩爪 CD 统一 helper 存在", "_grapple_cd_for" in _ms and "_grapple_cd_for(p2)" in _mm)

# ======================================================================
print("== #157 过热倾泻 P1/P2 共用 ==")
check("共用更新函数 _update_overdrive 存在",
      "def _update_overdrive(self, player, dt)" in read("zombie_pkg/mix_playing.py"))
check("P1 调用共用更新", "self._update_overdrive(self.player, dt)" in read("zombie_pkg/mix_playing.py"))
check("P2 调用共用更新", "self._update_overdrive(p2, dt)" in _mm)
check("P2 也有无限弹药", "overdrive_timer" in _mm and "current_ammo" in _mm)

# ======================================================================
print("== #158/#159 预瞄（湮灭射线方向 / 死亡轮回预瞄圈） ==")
check("湮灭射线支持传入瞄准角", "def _skill_railgun_annihilation(self, angle=None)" in _ms)
check("预瞄释放走瞄准角分支",
      re.search(r"RAILGUN_ANNIHILATION[\s\S]{0,200}_skill_railgun_annihilation\(angle=angle\)", _ms) is not None)
_ui = read("ui_pkg/skills_ui.py")
check("预瞄渲染含湮灭射线", "SkillType.RAILGUN_ANNIHILATION" in _ui)
check("预瞄渲染含死亡轮回", "SkillType.SCYTHE_DANCE" in _ui)
check("湮灭射线最大距离已登记（900）",
      "SkillType.RAILGUN_ANNIHILATION: 900" in _ms)

# ======================================================================
print("== #160 载具形态长按退出 ==")
_mp = read("zombie_pkg/mix_playing.py")
check("P1 触控：仅载具召唤技能可退出载具",
      re.search(r"_is_veh_skill = \(self\.selected_skill == SkillType\.VEHICLE_SUMMON\)", _mp) is not None)
_mi = read("zombie_pkg/mix_input.py")
check("P1 键盘：仅载具召唤技能可退出载具",
      "self.selected_skill == SkillType.VEHICLE_SUMMON" in _mi)
check("P2：仅载具召唤技能可退出载具", "_p2_veh_skill = (st == SkillType.VEHICLE_SUMMON)" in _mm)
check("P2 预瞄释放标记每帧重置（长按后残留会让短按也走预瞄）",
      re.search(r"def _update_player2[\s\S]{0,900}self\._p2_cast_aimed = False", _mm) is not None)
check("P2 键控技能统一由松开 U 键触发（按住首帧短放会吃掉长按预瞄）",
      "_kb_skill_blocked" in _mm)

# ======================================================================
print("== #161 救援 / 死亡链路 ==")
check("永久死亡标记", "permanently_dead" in _mp)
check("超时死亡后不再重新判定倒地",
      re.search(r"permanently_dead[\s\S]{0,400}continue", _mp) is not None)
check("救援者被击打会打断救援", "_rescue_mate_last_hp" in _mp)
check("救援冷却有文字提示", "救援冷却中" in _mp)

# ======================================================================
print("== #162 P2 HUD / 按钮 ==")
check("P2 技能按钮刷新 CD", "set_cooldown(p2.active_skills[_sel2])" in _mm)
_dp = read("renderer_pkg/draw_play.py")
check("分屏 HUD 显示投掷物", "投掷: " in _dp)
check("分屏 HUD 显示防爆套装状态", "防爆套装" in _dp)
check("自定义名字可显示（nickname/nick）", "getattr(p, 'nick', None)" in _dp)

# ======================================================================
print("== #163 地图边界警示（P2 视口） ==")
check("边界警示按当前视口尺寸绘制", "_vw = self.screen.get_width()" in _dp)
check("边界文字用视口中心", "midtop=(_vw // 2" in _dp)
check("不再用整窗宽度定位（P2 会画到屏幕外）",
      "self.game.scaled_width // 2 + viewport_x" not in _dp)

# ======================================================================
print("== #164 敌人钩爪不可勾载具形态玩家 ==")
_gc = read("zombie_pkg/game_core.py")
check("_enemy_players_of 排除载具形态",
      re.search(r"vehicle', None\) is not None or getattr\(_p, 'riding_vehicle', None\) is not None", _gc) is not None)

# ======================================================================
print("== #165/#166 名字输入 + 房间配置持久化 ==")
check("名字输入框位置被记录（供输入处理）", "g.room_name_rect = _nr" in _du)
check("点击输入框外自动退出输入态", "pygame.key.stop_text_input()" in _du and "_outside" in _du)
check("聚焦时有光标提示", "请输入名字…" in _du)
check("config 持久化多人房间配置", "mp_room_cfgs" in _gc)
check("进入房间配置页自动恢复", "_load_room_cfgs_from_config()" in _du)
check("开局/返回时保存配置", "_save_room_cfgs_to_config()" in _du)
check("恢复函数与保存函数都实现", "_load_room_cfgs_from_config" in _gc and "_save_room_cfgs_to_config" in _gc)

# ======================================================================
print("== #167 投掷物规则统一 ==")
check("共用库存函数 _ensure_throwable_stock", "def _ensure_throwable_stock(self, player)" in _gc)
check("P1 投掷前走统一函数", "_ensure_throwable_stock(self.player)" in read("zombie_pkg/mix_combat.py"))
check("P2 投掷走统一函数", "self._ensure_throwable_stock(p2)" in _mm)
check("开局给所有玩家统一库存", "_ensure_throwable_stock(_pp2)" in _gc)

# ======================================================================
print("== #168 道具刷新按每个玩家 ==")
_w = read("world.py")
check("world.update 支持多玩家位置", "def update(self, dt, player_x, player_y, extra_positions=None)" in _w)
check("道具按每个玩家位置刷新", "for _px, _py in positions:" in _w)
check("调用点传入其余玩家位置", "self.world.update(dt, self.player.x, self.player.y, _wpos)" in _mp)

# ======================================================================
print("== #169 PvP 毒圈 ==")
check("毒圈阶段表存在", "PVP_ZONE_PHASES" in _gc)
check("毒圈初始化", "def _init_pvp_zone(self)" in _gc)
check("毒圈更新（收缩+伤害）", "def _update_pvp_zone(self, dt)" in _gc)
check("更新循环里调用毒圈", "_update_pvp_zone(dt)" in _mp)
check("毒圈渲染（圈外遮罩）", "def _draw_pvp_zone_fill(self, cam_x, cam_y, scale)" in _dp)
check("毒圈 HUD 提示", "_pvp_zone_status" in _dp)
check("只有 PvP 才初始化毒圈", "pvp_enabled" in _gc.split("def _init_pvp_zone")[1][:600])

# ======================================================================
print("== #170 争分夺秒 MIDI / 乐器清单 / OGG 导入支持 ==")
_mid = "assets/music/race_urgency.mid"
check("MIDI 文件存在", os.path.exists(_mid))
try:
    from midi_lite import read_midi
    hdr, tracks = read_midi(_mid)
    check("MIDI 为 Type 1（多轨可逐轨编辑）", hdr.get("format") == 1)
    check("MIDI 分辨率 480 tpb", hdr.get("division") == 480)
    check("MIDI 含 7 轨（1 速度 + 6 乐器）", hdr.get("ntrks") == 7, hdr.get("ntrks"))
    _progs = {}
    _names = []
    for _tr in tracks:
        _nm = ""
        _pg = None
        for _tick, _typ, _d in _tr:
            if _typ == "track_name":
                _nm = _d.get("name", "")
            elif _typ == "program_change":
                _pg = _d.get("program")
        if _nm:
            _names.append(_nm)
            _progs[_nm] = _pg
    check("6 条乐器轨都有名字", len(_names) == 6, _names)
    check("弦乐轨 GM48", _progs.get("1-Strings Staccato") == 48)
    check("铜管轨 GM56", _progs.get("2-Brass Alarm") == 56)
    check("贝斯轨 GM33", _progs.get("3-Bass Pulse") == 33)
    check("定音鼓轨 GM47", _progs.get("4-Timpani") == 47)
    check("合成警报轨 GM83", _progs.get("5-Synth Alarm") == 83)
    check("鼓组轨走 GM 鼓组通道（无 program_change）", "6-Drums Stopwatch" in _progs
          and _progs.get("6-Drums Stopwatch") is None)
    check("速度轨有 end_of_track（部分 App 要求文件完整）",
          any(_ty == "end_of_track" for _t, _ty, _d in tracks[0]))
except Exception as e:
    check(f"MIDI 解析失败: {e!r}", False)

check("零依赖 MIDI 写入器 midi_lite 存在", os.path.exists("midi_lite.py"))
check("生成器在无 mido 时自动回退",
      "from midi_lite import" in read("generate_music.py"))
check("乐器清单生成器存在", os.path.exists("generate_music_manifest.py"))
check("清单文件已生成", os.path.exists("assets/music/race_urgency.tracks.txt"))
try:
    _man = read("assets/music/race_urgency.tracks.txt")
    check("清单含 GM 音色对照", "String Ensemble 1" in _man and "Trumpet" in _man)
    check("清单含鼓组说明", "GM 鼓组" in _man)
except Exception as e:
    check(f"清单读取失败: {e!r}", False)

_assets = read("assets.py")
check("资源表登记 race 音乐", '"race":' in _assets and "race_urgency.ogg" in _assets)
check("缺 OGG 时静默跳过（资源管理器行为）",
      "self._missing_assets.append(f\"[MUS] {name}: file not found\")" in _assets)
check("争分夺秒模式优先用 race 配乐", "GameMode.TIMED" in _gc.split("def _resolve_map_music")[1][:800])
check("地图音乐解析函数", "def _resolve_map_music(self)" in _gc)

# 生成器可重跑（无 mido 环境也要能生成）
try:
    _r = subprocess.run([sys.executable, "generate_music_race.py"], cwd=ROOT, timeout=120,
                        capture_output=True, text=True)
    check("generate_music_race.py 可直接运行", _r.returncode == 0, _r.stdout[-300:] + _r.stderr[-300:])
    _r2 = subprocess.run([sys.executable, "generate_music_manifest.py"], cwd=ROOT, timeout=120,
                         capture_output=True, text=True)
    check("generate_music_manifest.py 可直接运行", _r2.returncode == 0, _r2.stdout[-300:])
except Exception as e:
    check(f"生成器运行异常: {e!r}", False)

# ======================================================================
print("== 运行时冒烟（子进程实跑 main.py） ==")
try:
    r = subprocess.run(
        [sys.executable, "main.py"],
        cwd=ROOT, timeout=180,
        env={**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy",
             "ZOMBIE_SMOKE": "1"},
        capture_output=True, text=True)
    out = r.stdout + r.stderr
    has_err = bool(re.search(r"Traceback \(most recent call last\)", out)) or "RuntimeError" in out
    check("子进程退出码=0", r.returncode == 0, out[-600:])
    check("输出含冒烟通过标记", "[SMOKE] 运行时冒烟通过" in out, out[-400:])
    check("无 Traceback/运行时异常", not has_err, out[-600:])
except Exception as e:
    check(f"子进程启动(超时/环境): {e}", False)

print()
print(f"===== v2.5.7 批次结果: {OK} 通过, {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
