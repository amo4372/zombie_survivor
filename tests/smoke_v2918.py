#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.9.18：zoom 拉远 + UI 隔离 + 格挡可见 + 贴图画风 + AI 配置页"""
import os, sys, math, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "_vendor")); sys.path.insert(0, ROOT); os.chdir(ROOT)
PASS = FAIL = 0
def check(c, l):
    global PASS, FAIL
    if c: PASS += 1; print("  OK   " + l)
    else: FAIL += 1; print("  FAIL " + l)
def src(p): return open(p, encoding="utf-8").read()

import pygame
pygame.init(); pygame.display.set_mode((1280, 720))
from config import GameState, ControlMode, GameMode, BASE_WIDTH, BASE_HEIGHT
from zombie_pkg import Game

print("[A] 删除镜头位移，恢复 zoom 拉远")
from renderer_pkg.camera import Camera
_c = Camera(1280, 720)
check(hasattr(_c, 'zoom') and _c.zoom == 1.0, "Camera 初始化 zoom=1.0")
check(not hasattr(_c, 'aim_offset_x'), "aim_offset 位移字段已删除")
check('target_cam_x = target_x - self.width // 2' in src('renderer_pkg/camera.py'), "follow 不再读镜头偏移")
check('def draw_aim_follow_line' not in src('renderer_pkg/draw_play.py'), "跟随预瞄线已删除")
check('cam.zoom = _cur + (_target - _cur) * _k' in src('zombie_pkg/mix_players.py'),
      "update_dynamic_zoom 恢复 zoom 平滑")
check('_charge_zoom_active = True' not in src('zombie_pkg/mix_playing.py'),
      "旧蓄力 zoom 抢写已删除")

_g = Game(); _g.config.control_mode = ControlMode.TOUCH
_g.config.game_mode = GameMode.ENDLESS; _g.start_game(); _g.state = GameState.PLAYING
_g.player._awm_saved = 0.0; _g.player._charge_active = True
_g.player._charge_ratio = 1.0
_w = _g.player.get_current_weapon()
if _w is not None:
    _w.hold_charge = True; _w.range = 1400
_g.update_dynamic_zoom(0.5)
check(float(_g.camera.zoom) < 0.99, "长按瞄准时 zoom 确实拉远 (%.3f)" % _g.camera.zoom)

print("[B] UI 缩放隔离（拉远时按钮/摇杆不缩小）")
check('scale = _ui_scale' in src('renderer_pkg/draw_play.py'), "HUD 前恢复 UI 原始缩放")
_seen = []
_orig = _g.joystick.draw
def _spy(screen, sc, *a, **kw):
    _seen.append(float(sc)); return _orig(screen, sc, *a, **kw)
_g.joystick.draw = _spy
_g.camera.zoom = 0.6
try:
    _g.renderer._draw_playing_core(_g.player, _g.camera)
    check(True, "zoom=0.6 下绘制无异常")
except Exception as ex:
    check(False, "绘制异常 %r" % ex)
check(bool(_seen) and abs(_seen[0] - _g.scale) < 1e-6,
      "摇杆 draw 收到的是原始 UI scale（不是 0.6*scale）")
_g.joystick.draw = _orig
# 光照层拿到世界缩放
check('self.screen, cam_x, cam_y, scale,' in src('renderer_pkg/draw_play.py'),
      "光照层用世界缩放与 cam 坐标")

print("[C] 格挡可见")
check('常驻状态标记' in src('zombie_pkg/mix_block.py'), "常驻盾牌标记")
check('半透明蓝填充' in src('zombie_pkg/mix_block.py'), "举盾有填充护盾")
check('if _fx > 0:' in src('zombie_pkg/mix_block.py'), "普通格挡也有成功反馈")
check(src('renderer_pkg/draw_play.py').count('self.game.draw_block_fx(') == 1,
      "世界层格挡特效只画一次（本视口主人）")
# 实际绘制
try:
    from combat_pkg.block import BlockController
    _g.player.block = BlockController(_g.player)
    _g.player.block.press(0.0)
    _g.player.block.active_time = 0.05
    _g.player.block.fx_timer = 0.3
    _g.player.block.fx_perfect = False
    _g.draw_block_fx(_g.renderer.screen, _g.player, 0, 0, 1.0, 0, _g.font_small)
    check(True, "格挡特效绘制无异常")
except Exception as ex:
    check(False, "格挡特效异常 %r" % ex)

print("[D] 僵尸贴图画风与图鉴接入")
_new = ['zombie_hunter','zombie_bomber','zombie_frost','zombie_venom',
        'zombie_berserker','zombie_ghoul','zombie_shaman','zombie_juggernaut']
check(all(os.path.exists('assets/images/%s.png' % k) for k in _new), "8 张新贴图存在")
check(not os.path.isdir('assets/images/zombies'), "v2.9.17 画风不符的旧目录已删")
for k in _new:
    _im = pygame.image.load('assets/images/%s.png' % k)
    check(_im.get_size() == (64, 64), "%s 为 64x64（与原素材一致）" % k)
_a = src('assets.py')
check(all(('"%s"' % k) in _a for k in _new), "8 张贴图已注册到 assets")
check('getattr(EnemyType, _nm, None)' in src('entities_pkg/enemy.py'),
      "Enemy.draw type_map 安全接入新类别")
check('draw_zombie_sprite' not in src('renderer_pkg/draw_play.py'),
      "删除风格分叉的第二套贴图绘制")
# 图鉴预览命中
from codex import MONSTER_CODEX
_missing = [k for k in MONSTER_CODEX
            if not os.path.exists('assets/images/%s.png' % k.lower())]
check(not _missing, "图鉴全部怪物条目都有贴图（缺：%s）" % _missing[:4])
try:
    _g.state = GameState.CODEX
    _g.codex_tab = 'monster'; _g.codex_selected = 'ZOMBIE_FROST'
    _g.renderer._draw_codex_item_preview('ZOMBIE_FROST', 'monster', 100, 100, 130, 130)
    check(True, "图鉴预览渲染无异常")
except Exception as ex:
    check(False, "图鉴预览异常 %r" % ex)

print("[E] AI 配置页（分页卡片 / 无重叠 / 触控可用）")
from ai_pkg.player_bots import BotManager, BotDifficulty
_s = src('renderer_pkg/draw_ui.py')
check('def _draw_bot_config' in _s, "配置页存在")
check('b.text = label' in _s, "按钮用正确的 text 属性（不是 .label）")
check('每页 3 个 AI' in _s or '_page * 3' in _s, "分页每页 3 个")
check('int(sw - 236 * scale)' in _s, "房间页入口挪到右上角（不压开始/返回）")
_g2 = Game(); _g2.config.control_mode = ControlMode.TOUCH
_g2.start_game(); _g2.state = GameState.BOT_CONFIG
_g2.touch_events = []
try:
    _g2.renderer.render()
    check(True, "AI 配置页渲染无异常")
except Exception as ex:
    check(False, "AI 配置页异常 %r" % ex)
_btns = getattr(_g2, 'bot_cfg_btns', {})
check(len(_btns) >= 18, "当前页按钮已创建（%d 个）" % len(_btns))
# 本页按钮矩形两两不重叠
_rects = [b.get_scaled_rect(_g2.scale) for b in _btns.values()]
_overlap = 0
for i in range(len(_rects)):
    for j in range(i + 1, len(_rects)):
        if _rects[i].colliderect(_rects[j]):
            _overlap += 1
check(_overlap == 0, "按钮之间零重叠（重合 %d 对）" % _overlap)
# 底部按钮不与卡片区重叠
_card_bottom = (150 + 3 * (148 + 12)) * _g2.scale
_bottoms = [r for r in _rects if r.top >= 600 * _g2.scale]
check(bool(_bottoms) and all(r.top >= _card_bottom for r in _bottoms),
      "底部全局按钮与卡片区不重叠")

print("[F] 全模式跑帧")
for _m in ('STORY', 'ENDLESS', 'TIMED'):
    try:
        _gg = Game(); _gg.config.game_mode = getattr(GameMode, _m, None)
        _gg.config.control_mode = ControlMode.TOUCH
        _gg.start_game(); _gg.state = GameState.PLAYING
        for _i in range(30): _gg.update(1/60); _gg.draw()
        check(True, "%s 30 帧无异常" % _m)
    except Exception as ex:
        check(False, "%s 跑帧异常 %r" % (_m, ex))
try:
    _gg = Game(); _gg.multiplayer_mode = 'same_screen'
    _gg.config.game_mode = GameMode.ENDLESS; _gg.config.control_mode = ControlMode.TOUCH
    _gg.start_game(); _gg.state = GameState.PLAYING
    for _i in range(30): _gg.update(1/60); _gg.draw()
    check(True, "同屏双人 30 帧无异常")
except Exception as ex:
    check(False, "双人跑帧异常 %r" % ex)

print("\n===== v2.9.18 测试: PASS=%d FAIL=%d =====" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
