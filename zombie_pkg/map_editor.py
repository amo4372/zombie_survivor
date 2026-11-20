# -*- coding: utf-8 -*-
"""MapEditorMixin — v2.9.21 游戏内地图编辑器（直接编辑 world.obstacles）。

与旧的 rl/map_editor.py（独立 .zmap tile 工具）不同，本编辑器操作的就是
主游戏真正使用的障碍物列表，因此编辑结果可一键试玩，且每个障碍带
「材质 → 挡弹 / 挡视线」属性，与 damage/vision 两个新系统直接联动。
"""
import os
import json
import pygame
from config import GameState

# 工具栏常用类型（覆盖六类材质）
MAP_EDITOR_TYPES = [
    ('wall', '实体墙'), ('building', '建筑'), ('car', '车辆'),
    ('fence', '栅栏'), ('sandbag', '沙袋'), ('terminal', '终端'),
    ('crate', '板条箱'), ('pipe', '管道'), ('tree', '树'),
    ('bush', '灌木'), ('barrel', '油桶'), ('pillar', '立柱'),
]
MAP_DIR = 'maps'


class MapEditorMixin:

    def _me_enter(self):
        self.state = GameState.MAP_EDITOR
        if not hasattr(self, 'me_obstacles'):
            self.me_obstacles = []
        self.me_cam_x = float(getattr(self, 'me_cam_x', 200.0))
        self.me_cam_y = float(getattr(self, 'me_cam_y', 150.0))
        self.me_zoom = float(getattr(self, 'me_zoom', 1.0) or 1.0)
        self.me_type = getattr(self, 'me_type', 'wall')
        self.me_rot = int(getattr(self, 'me_rot', 0) or 0)
        self.me_grid = int(getattr(self, 'me_grid', 40) or 40)
        self.me_tip = ''
        self.me_last_pos = None

    def _me_types(self):
        return MAP_EDITOR_TYPES

    def _me_material(self, otype):
        try:
            from world import GameWorld
            return GameWorld.material_of({'type': otype})
        except Exception:
            return 'solid'

    def _me_rule_text(self, otype):
        return {
            'solid': '挡绝大多数子弹 / 挡视线（激光·高穿透可过）',
            'vehicle': '挡所有弹，爆炸弹可炸穿 / 挡视线',
            'thin': '挡普通弹，高伤(≥80)或爆炸打穿 / 可看穿',
            'glass': '低速弹被挡，高速(≥16)·高伤(≥60)·爆炸打碎 / 可看穿',
            'hollow': '挡普通弹，高穿透(≥3)·激光穿过 / 可看穿',
            'foliage': '不挡子弹，但挡视线（可藏人）',
        }.get(self._me_material(otype), '')

    def _me_screen_to_world(self, sx, sy):
        s = self.scale
        return (sx / s / self.me_zoom + self.me_cam_x,
                sy / s / self.me_zoom + self.me_cam_y)

    def _me_place(self, sx, sy, erase=False):
        _wx, _wy = self._me_screen_to_world(sx, sy)
        _g = self.me_grid
        _x = int(_wx // _g) * _g
        _y = int(_wy // _g) * _g
        if erase:
            _r = pygame.Rect(_x, _y, _g * 2, _g * 2)
            self.me_obstacles = [o for o in self.me_obstacles
                                 if not o['rect'].colliderect(_r)]
            return
        for _o in self.me_obstacles:
            if _o['rect'].collidepoint(_x + _g, _y + _g):
                return                       # 已有障碍，跳过
        try:
            from world import GameWorld
            _color = GameWorld._obs_color(None, self.me_type)
        except Exception:
            _color = (110, 100, 95)
        self.me_obstacles.append({
            'rect': pygame.Rect(_x, _y, _g * 2, _g * 2),
            'type': self.me_type, 'color': _color,
            'rotation': self.me_rot,
        })

    def _me_clear(self):
        self.me_obstacles = []
        self.me_tip = '已清空'

    def _me_save(self, name='custom'):
        try:
            os.makedirs(MAP_DIR, exist_ok=True)
            _p = os.path.join(MAP_DIR, '%s.json' % name)
            _data = [{'x': o['rect'].x, 'y': o['rect'].y,
                      'w': o['rect'].w, 'h': o['rect'].h,
                      'type': o['type'], 'rotation': o.get('rotation', 0)}
                     for o in self.me_obstacles]
            with open(_p, 'w', encoding='utf-8') as f:
                json.dump({'version': 1, 'grid': self.me_grid,
                           'obstacles': _data}, f, ensure_ascii=False, indent=1)
            self.me_tip = '已保存 %s（%d 个障碍）' % (_p, len(_data))
            return True
        except Exception as e:
            self.me_tip = '保存失败：%s' % e
            return False

    def _me_load(self, name='custom'):
        try:
            _p = os.path.join(MAP_DIR, '%s.json' % name)
            with open(_p, encoding='utf-8') as f:
                _d = json.load(f)
            from world import GameWorld
            self.me_grid = int(_d.get('grid', 40) or 40)
            self.me_obstacles = []
            for _o in _d.get('obstacles', []):
                self.me_obstacles.append({
                    'rect': pygame.Rect(int(_o['x']), int(_o['y']),
                                        int(_o['w']), int(_o['h'])),
                    'type': str(_o.get('type', 'wall')),
                    'color': GameWorld._obs_color(None, str(_o.get('type', 'wall'))),
                    'rotation': int(_o.get('rotation', 0) or 0)})
            self.me_tip = '已载入 %s（%d 个障碍）' % (_p, len(self.me_obstacles))
            return True
        except Exception as e:
            self.me_tip = '载入失败：%s' % e
            return False

    def _me_playtest(self):
        """把当前编辑结果装进 world 并开局（所见即所玩）。"""
        try:
            self._me_save('custom')
            self.me_playtest_pending = True
            self.state = GameState.PLAYING
            self.start_game()
            _w = getattr(self, 'world', None)
            if _w is not None:
                import copy
                _w.obstacles = [dict(o) for o in self.me_obstacles]
                try: _w.invalidate_obs_grid()
                except Exception: pass
            self.state = GameState.PLAYING
            return True
        except Exception as e:
            self.me_tip = '试玩失败：%s' % e
            return False

    def _me_toggle_vision(self):
        _v = getattr(self, 'vision', None)
        if _v is not None:
            _v.enabled = not _v.enabled
            self.me_tip = '视野机制：%s' % ('开' if _v.enabled else '关')
