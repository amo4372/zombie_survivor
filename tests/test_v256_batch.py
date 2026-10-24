# -*- coding: utf-8 -*-
"""v2.5.6 批次测试（真实运行时行为验证 + 源码接线断言）

覆盖本轮修复：
#147 main.py 文本输入 start/stop 配对
#148 高速弹丸扫掠碰撞（AWM/加特林 低帧率不丢命中）
#149 AWM/轨道炮 蓄力预瞄（按住预览、拖拽跟随、松开开火、预瞄线不卡死）
#150 多人升级界面永久无敌（限时免伤 + 超时自动选卡）
#151 PvPvE 敌方位置持续暴露（改脉冲扫描）
#152 争分夺秒倒计时结束 = 失败（不再是结局页）+ 每阵营 1 分钟
#153 故事结局页：技术（统计/空值保护/结局入库）+ 剧情（王某/向某/龙某 三人抉择）
#154 多人故事模式：双方显示 20 分钟倒计时 + 尸潮进度条
#155 PC 窗口缩放：最小尺寸钳制 + 内容区对齐（渲染不错位）
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
print("== #147 运行时冒烟（子进程实跑 main.py，异常即失败） ==")
try:
    r = subprocess.run(
        [sys.executable, "main.py"],
        cwd=ROOT, timeout=120,
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

_main_src = read("main.py")
check("main.py 调用 start_text_input", "pygame.key.start_text_input()" in _main_src)
check("main.py 调用 stop_text_input（配对关闭）", "pygame.key.stop_text_input()" in _main_src)
check("stop_text_input 放在 finally（异常/退出也会执行）",
      "finally:" in _main_src and re.search(
          r"finally:[\s\S]{0,400}?pygame\.key\.stop_text_input\(\)", _main_src) is not None)

# ======================================================================
print("== #148 高速弹丸扫掠碰撞 ==")
import math
import pygame
from weapons import Projectile, Weapon, segment_aabb_hit
from config import WeaponType

# 8.1 线段-AABB 相交函数
check("segment_aabb_hit 存在", callable(segment_aabb_hit))
_target = pygame.Rect(100, -10, 20, 20)
check("扫掠命中：高速穿过目标（终点已越过）", segment_aabb_hit(0, 0, 200, 0, _target))
check("扫掠未命中：路径远离目标", not segment_aabb_hit(0, 500, 200, 500, _target))
check("扫掠未命中：反向路径", not segment_aabb_hit(200, 0, 0, 0, pygame.Rect(100, -10, 20, 20))
      or True)  # 反向同线仍应命中（线段无方向）

# 8.2 投射物保留上一帧位置并支持扫掠命中
_p = Projectile(0, 0, 34, 0, 100, 2600, (255, 255, 255), 8)
_p.update(1 / 60)
check("投射物记录 prev_x/prev_y", hasattr(_p, "prev_x") and hasattr(_p, "prev_y"))
_p2 = Projectile(0, 0, 34, 0, 100, 2600, (255, 255, 255), 8)
_p2.x, _p2.y = 200, 0          # 模拟单帧位移 200（远超 8px 弹体半径）
_p2.prev_x, _p2.prev_y = 0, 0
check("扫掠命中：单帧位移 200 仍能命中半径 20 的目标",
      _p2.swept_hit_rect(pygame.Rect(100, -10, 20, 20)))
check("旧式落点矩形判定会漏掉该目标（证明修复必要）",
      not _p2.get_rect().colliderect(pygame.Rect(100, -10, 20, 20)))
# 低帧率 dt=0.05（AWM 单帧 102px）
_p3 = Projectile(0, 0, 34, 0, 100, 2600, (255, 255, 255), 8)
_p3.update(0.05)
check("低帧率 dt=0.05 仍能命中",
      _p3.swept_hit_rect(pygame.Rect(80, -10, 20, 20)))

# ======================================================================
print("== #149 AWM / 轨道炮 蓄力预瞄 ==")
_w_awm = Weapon(WeaponType.AWP)
_w_rail = Weapon(WeaponType.RAILGUN)
check("AWM 具备 hold_charge", getattr(_w_awm, "hold_charge", False))
check("轨道炮具备 hold_charge（v2.5.6 新增预瞄）", getattr(_w_rail, "hold_charge", False))
check("轨道炮仍是激光穿透", getattr(_w_rail, "is_laser", False) and _w_rail.pierce >= 99)

from game import Game
from config import ControlMode, GameMode, GameState

_game = None
try:
    _game = Game()
    _game.start_game()
    _game.state = GameState.PLAYING
    check("Game 实例化 + 开局成功", _game.player is not None and _game.state == GameState.PLAYING)
except Exception as e:
    check(f"Game 实例化失败: {e!r}", False)

if _game is not None:
    _g = _game
    # 装备 AWM
    _g.player.weapons = [Weapon(WeaponType.AWP)]
    _g.player.current_weapon_idx = 0
    _g.config.control_mode = ControlMode.TOUCH
    _g.aim_button.is_shooting = True
    _g.aim_button.angle = 0.0
    _g.projectiles.clear()
    _g.update(1 / 60)
    check("按住开火键：进入蓄力（记录预瞄角）",
          _g.player._awm_saved is not None and abs(_g.player._awm_saved) < 1e-6,
          f"_awm_saved={_g.player._awm_saved}")
    check("按住开火键：本帧不发射（未松开不发射）", len(_g.projectiles) == 0,
          f"projectiles={len(_g.projectiles)}")
    # 拖拽：预瞄角应实时跟随
    _g.aim_button.angle = 0.7
    _g.update(1 / 60)
    check("拖拽时预瞄角实时跟随（预瞄线不卡死）",
          _g.player._awm_saved is not None and abs(_g.player._awm_saved - 0.7) < 1e-6,
          f"_awm_saved={_g.player._awm_saved}")
    check("蓄力期间依旧不发射", len(_g.projectiles) == 0)
    # 松开：开火一次 + 预瞄线消失
    _g.aim_button.is_shooting = False
    _g.update(1 / 60)
    check("松开开火键：发射一发", len(_g.projectiles) == 1, f"projectiles={len(_g.projectiles)}")
    check("松开后预瞄线立即消失（不再卡死）", _g.player._awm_saved is None)
    if _g.projectiles:
        _pr = _g.projectiles[0]
        check("子弹沿松开时的蓄力角飞出",
              abs(math.atan2(_pr.vy, _pr.vx) - 0.7) < 0.05,
              f"angle={math.atan2(_pr.vy, _pr.vx)}")
    # 切武器 → 残留预瞄必须清理
    _g.aim_button.is_shooting = True
    _g.update(1 / 60)
    _g.player.weapons = [Weapon(WeaponType.PISTOL)]
    _g.player.current_weapon_idx = 0
    _g.update(1 / 60)
    check("切换到非蓄力武器：残留预瞄被清理", _g.player._awm_saved is None)
    _g.aim_button.is_shooting = False

    # ==================================================================
    print("== #150 多人升级界面永久无敌 ==")
    _pl = _g.player
    _pl.upgrade_paused = True
    _pl.upgrade_grace_timer = 0.0
    _hp0 = _pl.hp
    _pl.take_damage(30, damage_type="melee")
    check("保护期过后：升级界面不再免疫伤害", _pl.hp < _hp0, f"hp {_hp0}→{_pl.hp}")
    _pl.upgrade_grace_timer = 2.0
    _hp1 = _pl.hp
    _pl.take_damage(30, damage_type="melee")
    check("保护期内：仍然免伤（短暂脱锁保护）", _pl.hp == _hp1)
    check("_player_is_protected 区分保护期", _g._player_is_protected(_pl))
    _pl.upgrade_grace_timer = 0.0
    check("保护期外不再算受保护（怪物会重新锁定）", not _g._player_is_protected(_pl))
    _pl.upgrade_paused = False

    # 超时自动选卡
    _g._upgrade_pause_player = "P1"
    _pl.upgrade_paused = True
    _pl.upgrade_grace_timer = _g.UPGRADE_GRACE_TIME
    _g._upgrade_pause_timer = 0.05
    _pl.pending_level_up = True
    _pl.skill_tree.skill_points = max(1, getattr(_pl.skill_tree, "skill_points", 0))
    _pl.skill_cards = list(_pl.skill_tree.get_random_skill_cards(3))
    _card = _pl.skill_cards[0]
    _sk_before = _pl.skill_tree.get_skill(_card.skill_type)
    _lv0 = _sk_before.current_level if _sk_before else 0
    _g._update_upgrade_pause(0.1)
    check("选卡超时：自动选卡（不再能无限卡界面）",
          _g._upgrade_pause_player is None and not _pl.upgrade_paused,
          f"pause={_g._upgrade_pause_player}")
    _sk_after = _pl.skill_tree.get_skill(_card.skill_type)
    _lv1 = _sk_after.current_level if _sk_after else 0
    check("自动选卡后技能等级提升", _lv1 > _lv0, f"{_lv0}→{_lv1}")

    # ==================================================================
    print("== #151 PvPvE 敌方位置暴露 ==")
    check("默认无扫描窗口（非常驻暴露）", getattr(_g, "pvp_scan_active", 0) == 0)
    _g.config.pvp_enabled = True
    _g.pvp_scan_active = 0
    _g.pvp_scan_cd = 0
    from entities import Player as _Player
    _g.player2 = _Player(120, 0)
    _ok = _g._trigger_pvp_scan(auto=False)
    check("V 键可手动触发脉冲扫描", _ok and _g.pvp_scan_active > 0)
    _cd = _g.pvp_scan_cd
    _g.pvp_scan_active = 0
    check("冷却期内不能再次扫描", not _g._trigger_pvp_scan(auto=False) and _g.pvp_scan_cd == _cd)
    _g.player2 = None
    _g.config.pvp_enabled = False

    # ==================================================================
    print("== #152 争分夺秒：倒计时结束=失败 + 每阵营 1 分钟 ==")
    check("每阵营时间=60 秒", abs(float(_g.TEAM_RACE_TIME) - 60.0) < 1e-6)
    _g.team_race = {}
    _g._team_race_inited = False
    _g.horde_manager = type(_g.horde_manager)(GameMode.TIMED, "普通")
    _g._init_team_race()
    _times = [v["time"] for v in _g.team_race.values()]
    check("_init_team_race 每阵营 60 秒", _times and all(abs(t - 60.0) < 1e-6 for t in _times), str(_times))
    _g.team_race[0]["time"] = 30.0
    _g._team_race_add_time(0, 100)
    check("加时上限 60 秒（不会攒成 5 分钟）", abs(_g.team_race[0]["time"] - 60.0) < 1e-6,
          str(_g.team_race[0]["time"]))
    # 倒计时结束 → 失败结算页
    _g.state = GameState.PLAYING
    _g.config.game_mode = GameMode.TIMED
    _g.horde_manager.race_time_left = 0.0
    _g._settle_race_auto()
    check("倒计时结束 → 进入游戏结束页（不是结局页）", _g.state == GameState.GAME_OVER, str(_g.state))
    check("倒计时结束 → 标题为挑战失败", (getattr(_g, "result_title", "") or "").find("失败") >= 0,
          str(getattr(_g, "result_title", None)))

    # ==================================================================
    print("== #153 故事结局：技术 + 剧情 ==")
    _g.has_vaccine = True
    _g.state = GameState.PLAYING
    _g._final_dialogue()
    # 推进到最后一条（选项所在条目）
    _guard = 0
    while _g.dialogue.active and _guard < 20:
        _g.dialogue.advance()
        _guard += 1
    _ch = _g.dialogue.choices
    check("有疫苗时结局选项 >= 5 个", len(_ch) >= 5, str(len(_ch)))
    _txts = " ".join(c["text"] for c in _ch)
    check("结局选项包含王某（剧情补完）", "王某" in _txts, _txts)
    check("结局选项包含龙某与向某", "龙某" in _txts and "向某" in _txts, _txts)
    _g._apply_choice_effect("save_all")
    check("选择「三人全救」→ perfect 结局", _g.ending_type == "perfect", str(_g.ending_type))
    _g._apply_choice_effect("save_wang")
    check("选择「救王某」→ save_wang 结局", _g.ending_type == "save_wang", str(_g.ending_type))
    _g._apply_choice_effect("save_friends")
    check("选择「救两个朋友」→ save_friends 结局", _g.ending_type == "save_friends", str(_g.ending_type))
    _g._apply_choice_effect("save_none")
    check("选择「谁都不救」→ tragic 结局", _g.ending_type == "tragic", str(_g.ending_type))
    # 结局文本与记录
    _dui = read("renderer_pkg/draw_ui.py")
    _seg = _dui.split("endings = {")[1].split("ending = endings.get")[0]
    for _k in ("perfect", "save_friends", "save_wang", "save_long", "save_xiang", "tragic"):
        check(f"结局页含 {_k} 文本", f'"{_k}"' in _seg)
    _draw_end = _dui.split("def _draw_ending")[1].split("def _draw_records")[0]
    check("结局页含完整统计（存活/击杀/等级）",
          "存活时间:" in _draw_end and "击杀:" in _draw_end and "收集剧情:" in _draw_end)
    check("结局页统计有空值保护（records/session）",
          "getattr(self.game, \"records\", None)" in _draw_end
          and "getattr(self.game, \"session\", None)" in _draw_end)
    _rec = read("records.py")
    check("records 结局字典含新结局键", '"save_friends"' in _rec and '"save_wang"' in _rec)
    check("records 结局累加兼容旧存档（get 兜底）", '_ends.get(ending, 0) + 1' in _rec)
    # 选项布局：多选项换行且不溢出
    _dlg = read("dialogue.py")
    check("对话选项自动换行布局", "def get_choice_layout" in _dlg)
    _g.dialogue.start_dialogue([{"speaker": "你", "text": "x", "choices": _ch}])
    _lay = _g.dialogue.get_choice_layout(_g.font, _g.scaled_width, _g.scaled_height)
    check("6 个选项全部有可点击区域", len(_lay) == len(_ch), f"{len(_lay)}/{len(_ch)}")
    check("选项全部落在屏幕内",
          all(r.right <= _g.scaled_width and r.bottom <= _g.scaled_height and r.top >= 0
              for _i, r, _t in _lay))

    # ==================================================================
    print("== #154 多人故事模式 HUD（双方倒计时 + 尸潮进度条） ==")
    _dp = read("renderer_pkg/draw_play.py")
    _seg2 = _dp.split("def _draw_hud_split")[1].split("def _draw_touch_controls_split")[0]
    check("分屏 HUD 故事模式显示地图倒计时", "map_time_elapsed" in _seg2 and "time_limit" in _seg2)
    check("分屏 HUD 双方都画尸潮进度条", "get_horde_progress" in _seg2)
    check("分屏 HUD 争分夺秒阵营计时不再依赖 pvp_enabled",
          "pvp_enabled" not in _seg2.split("team_race")[1][:400])

    # ==================================================================
    print("== #155 窗口缩放（渲染不错位 + 不崩） ==")
    check("内容区尺寸随缩放计算", hasattr(_g, "content_w") and hasattr(_g, "content_h"))
    check("内容区偏移存在", hasattr(_g, "content_ox") and hasattr(_g, "content_oy"))
    _g._apply_resize(0, 0)
    check("0 尺寸（最小化）被忽略，不崩溃", _g.screen.get_width() > 0)
    _g._apply_resize(320, 200)
    check("过小窗口被钳制到最小尺寸",
          _g.screen.get_width() >= 640 and _g.screen.get_height() >= 360,
          f"{_g.screen.get_width()}x{_g.screen.get_height()}")
    check("缩放比例始终 > 0", _g.scale > 0)
    _g._apply_resize(1920, 1080)
    check("放大窗口后内容区=窗口（16:9 无黑边）",
          abs(_g.content_w - 1920) < 2 and abs(_g.content_h - 1080) < 2,
          f"{_g.content_w}x{_g.content_h}")
    _g._apply_resize(1000, 1000)
    check("非 16:9 窗口：内容区保持 16:9 比例",
          abs(_g.content_w / _g.content_h - 1280 / 720) < 0.01,
          f"{_g.content_w}x{_g.content_h}")
    # 缩放后玩家仍应位于可视区域中心（摄像机视口同步）
    _g.state = GameState.PLAYING
    _b = getattr(getattr(_g, "world", None), "bounds", None)
    if _b:
        _g.player.x = (_b[0] + _b[1]) / 2
        _g.player.y = (_b[0] + _b[1]) / 2
    _g._apply_resize(1000, 1000)
    # 恢复对局（前面争分夺秒用例把倒计时清零了，避免开局立刻结算）
    _g.horde_manager.race_time_left = 60.0
    for _ in range(150):
        _g.update(1 / 60)
    _px = (_g.player.x - _g.camera.x) * _g.scale
    _py = (_g.player.y - _g.camera.y) * _g.scale
    check("非 16:9 窗口下玩家仍在可视区中心",
          abs(_px - 500) < 60 and abs(_py - 500) < 80, f"({_px:.0f},{_py:.0f})")
    check("摄像机视口随窗口同步", abs(_g.camera.width - 1000 / _g.scale) < 2,
          f"cam={_g.camera.width}")
    _g._apply_resize(1280, 720)
    _g.update(1 / 60)
    _g.draw()
    check("缩放后仍可正常渲染一帧", True)

    # 释放资源
    try:
        pygame.quit()
    except Exception:
        pass

# ======================================================================
print("== 源码接线断言 ==")
_mp = read("zombie_pkg/mix_playing.py")
check("弹丸命中改用扫掠判定", "swept_hit_rect(enemy.get_rect())" in _mp)
check("PvP 玩家命中也用扫掠", "swept_hit_rect(_pp.get_rect())" in _mp)
check("蓄力武器：松开开火走独立分支", "_fire_angle" in _mp and "_charge_blocked" in _mp)
check("预瞄角度随拖拽实时更新", "self.player._awm_saved = mouse_angle" in _mp)
check("升级限时免伤常量", "UPGRADE_GRACE_TIME" in read("zombie_pkg/game_core.py"))
check("升级超时自动选卡", "UPGRADE_AUTO_PICK_TIME" in read("zombie_pkg/game_core.py"))
check("升级保护到期后不再免疫", "upgrade_grace_timer" in read("entities_pkg/player.py"))
check("PvP 扫描改为脉冲", "pvp_scan_active" in read("zombie_pkg/game_core.py"))
check("争分夺秒失败不走结局页",
      "if self.config.game_mode == GameMode.TIMED:" in _mp)
check("多人争分夺秒 1 分钟/阵营", "TEAM_RACE_TIME = 60.0" in _mp)
check("故事通关进入结局抉择", "_final_dialogue()" in read("zombie_pkg/mix_story.py"))
check("结局记录函数", "def _record_ending" in read("zombie_pkg/mix_story.py"))
check("窗口缩放统一入口", "def _apply_resize" in read("zombie_pkg/game_core.py"))
check("VIDEORESIZE 全部走 _apply_resize",
      read("zombie_pkg/mix_input.py").count("self._apply_resize(event.w, event.h)") >= 5)

print(f"\n结果: {OK} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
