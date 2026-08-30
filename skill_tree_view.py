#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能升级树系统 - 自动从 skills.py 生成真正的树状结构
特性：
- 从 Skill.requires 自动构建依赖树，包含全部技能
- 真正的树状布局，4大根分支向下延伸
- 支持触控/鼠标全方向拖动（上下左右）
- 支持键盘方向键移动 + 滚轮缩放/平移
- 全局解锁：三选一出现过的技能解锁显示
- 已点技能高亮，等级影响发光效果
- 点击技能显示详情面板
"""
import os
import json
import math
import pygame
from config import SkillType, WHITE, BLACK, GRAY, DARK_GRAY, LIGHT_GRAY, RED, GREEN, BLUE, GOLD, CYAN, PURPLE, ORANGE, YELLOW, DARK_BLUE, CHARCOAL

# ============================================================
# 全局解锁管理器
# ============================================================
class SkillTreeUnlockManager:
    """全局技能树解锁管理器 - 持久化保存解锁状态"""
    
    def __init__(self):
        self.unlocked_skills = set()
        self._load()
    
    def _get_save_path(self):
        return os.path.join(os.path.dirname(__file__), "skill_tree_unlock.json")
    
    def _load(self):
        path = self._get_save_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.unlocked_skills = set(data.get("unlocked", []))
            except Exception:
                self.unlocked_skills = set()
    
    def _save(self):
        path = self._get_save_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"unlocked": list(self.unlocked_skills)}, f, ensure_ascii=False)
        except Exception:
            pass
    
    def unlock_skill(self, skill_type):
        """解锁一个技能（三选一出现时调用），立即保存"""
        name = skill_type.name if hasattr(skill_type, 'name') else str(skill_type)
        if name not in self.unlocked_skills:
            self.unlocked_skills.add(name)
            self._save()
    
    def is_unlocked(self, skill_type):
        name = skill_type.name if hasattr(skill_type, 'name') else str(skill_type)
        return name in self.unlocked_skills
    
    def get_unlocked_count(self):
        return len(self.unlocked_skills)

skill_tree_unlock_manager = SkillTreeUnlockManager()

# ============================================================
# 树节点
# ============================================================
class TreeNode:
    def __init__(self, skill_type, name, description, max_level=1,
                 icon_color=WHITE, requires=None, skill_obj=None):
        self.skill_type = skill_type
        self.name = name
        self.description = description
        self.max_level = max_level
        self.icon_color = icon_color
        self.requires = requires or []  # [(SkillType, level), ...]
        self.skill_obj = skill_obj
        self.children = []
        self.x = 0
        self.y = 0
        self.width = 170
        self.height = 70
    
    def add_child(self, child):
        self.children.append(child)

# ============================================================
# 从 skills.py 自动构建技能树
# ============================================================
def build_skill_tree():
    """从 SkillTree 的技能定义自动构建依赖树"""
    try:
        from skills import SkillTree
        st = SkillTree()
    except Exception:
        # 降级：返回空树
        return []
    
    # 创建所有节点（st.skills 是 Skill 对象列表）
    nodes = {}
    for skill in st.skills:
        skill_type = skill.skill_type
        reqs = getattr(skill, 'requires', []) or []
        nodes[skill_type] = TreeNode(
            skill_type=skill_type,
            name=skill.name,
            description=skill.description,
            max_level=skill.max_level,
            icon_color=getattr(skill, 'icon_color', WHITE),
            requires=reqs,
            skill_obj=skill
        )
    
    # 建立父子关系：A requires B → B 是 A 的父节点
    roots = []
    for skill_type, node in nodes.items():
        if node.requires:
            # 取第一个前置作为主要父节点（用于树结构展示）
            parent_type = node.requires[0][0]
            if parent_type in nodes:
                nodes[parent_type].add_child(node)
            else:
                roots.append(node)
        else:
            roots.append(node)
    
    # 布局：4大根分支水平排列，每个分支垂直向下
    layout_tree(roots)
    return roots

def layout_tree(roots, node_width=170, node_height=70, h_gap=50, v_gap=90):
    """树状布局：根节点水平排列，子节点在父节点正下方居中"""
    if not roots:
        return
    
    # 计算每棵子树的宽度
    def subtree_width(node):
        if not node.children:
            return node_width
        child_widths = [subtree_width(c) for c in node.children]
        total = sum(child_widths) + h_gap * (len(node.children) - 1)
        return max(node_width, total)
    
    # 分配 x 坐标
    current_x = 0
    for root in roots:
        w = subtree_width(root)
        root.x = current_x + w / 2 - node_width / 2
        root.y = 0
        _layout_children(root, node_width, node_height, h_gap, v_gap)
        current_x += w + h_gap * 2

def _layout_children(node, node_width, node_height, h_gap, v_gap):
    if not node.children:
        return
    # 计算子节点总宽度
    child_widths = []
    for c in node.children:
        cw = node_width
        if c.children:
            cw = max(node_width, _subtree_width_recursive(c, node_width, h_gap))
        child_widths.append(cw)
    total_w = sum(child_widths) + h_gap * (len(node.children) - 1)
    start_x = node.x + node_width / 2 - total_w / 2
    
    cur_x = start_x
    for i, child in enumerate(node.children):
        child.x = cur_x
        child.y = node.y + node_height + v_gap
        cur_x += child_widths[i] + h_gap
        _layout_children(child, node_width, node_height, h_gap, v_gap)

def _subtree_width_recursive(node, node_width, h_gap):
    if not node.children:
        return node_width
    child_widths = [_subtree_width_recursive(c, node_width, h_gap) for c in node.children]
    return sum(child_widths) + h_gap * (len(node.children) - 1)

# ============================================================
# 技能树渲染器
# ============================================================
class SkillTreeRenderer:
    def __init__(self):
        self.visible = False
        self.camera_x = 0
        self.camera_y = 0
        self.zoom = 1.0
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.cam_start_x = 0
        self.cam_start_y = 0
        self.selected_node = None
        self.keys_pressed = set()
        self.move_speed = 8
        self.roots = build_skill_tree()
        self._init_camera()
    
    def _init_camera(self):
        """初始化相机到第一棵树的根节点附近"""
        all_nodes = self._get_all_nodes()
        if all_nodes:
            min_x = min(n.x for n in all_nodes)
            min_y = min(n.y for n in all_nodes)
            self.camera_x = min_x - 200
            self.camera_y = min_y - 100
    
    def show(self):
        self.visible = True
        self.back_requested = False
        self.roots = build_skill_tree()  # 重新构建以获取最新数据
        self._init_camera()
    
    def hide(self):
        self.visible = False
        self.selected_node = None
        self.back_requested = False  # 返回按钮点击标志
        self.back_button_rect = pygame.Rect(15, 15, 100, 40)  # 返回按钮区域（预初始化）
        self.dragging = False
    
    def handle_input(self, mouse_pos, mouse_pressed, touch_events, scale):
        """处理鼠标/触控输入，支持全方向拖动"""
        sw, sh = pygame.display.get_surface().get_size()
        mx, my = mouse_pos
        
        # 触控事件处理（touch_events 是 dict 列表: {"type": "down"/"up"/"move", "pos": (x,y), "id": ...}）
        for te in touch_events:
            te_type = te.get("type", "")
            tx, ty = te.get("pos", (0, 0))
            if te_type == "down":
                self.dragging = True
                self.drag_start_x = tx
                self.drag_start_y = ty
                self.cam_start_x = self.camera_x
                self.cam_start_y = self.camera_y
                # 检查是否点击了节点
                clicked = self._get_node_at(tx, ty, scale)
                if clicked:
                    self.selected_node = clicked
            elif te_type == "up":
                self.dragging = False
            elif te_type == "move" and self.dragging:
                dx = (tx - self.drag_start_x) / scale
                dy = (ty - self.drag_start_y) / scale
                self.camera_x = self.cam_start_x - dx
                self.camera_y = self.cam_start_y - dy
        
        # 返回按钮点击检测（防御式：属性可能尚未初始化）
        back_rect = getattr(self, 'back_button_rect', None)
        if back_rect and mouse_pressed[0]:
            if back_rect.collidepoint(mx, my):
                self.back_requested = True
                return
        
        # 鼠标拖动
        if mouse_pressed[0]:
            if not self.dragging:
                self.dragging = True
                self.drag_start_x = mx
                self.drag_start_y = my
                self.cam_start_x = self.camera_x
                self.cam_start_y = self.camera_y
                # 检查点击节点
                clicked = self._get_node_at(mx, my, scale)
                if clicked:
                    self.selected_node = clicked
            else:
                dx = (mx - self.drag_start_x) / scale
                dy = (my - self.drag_start_y) / scale
                self.camera_x = self.cam_start_x - dx
                self.camera_y = self.cam_start_y - dy
        else:
            if self.dragging:
                self.dragging = False
        
        self._clamp_camera()
    
    def _get_node_at(self, screen_x, screen_y, scale):
        """检查屏幕坐标是否在某个节点上"""
        all_nodes = self._get_all_nodes()
        for node in all_nodes:
            sx, sy = self._world_to_screen(node.x, node.y, scale)
            w = int(node.width * scale * self.zoom)
            h = int(node.height * scale * self.zoom)
            if sx <= screen_x <= sx + w and sy <= screen_y <= sy + h:
                return node
        return None
    
    def handle_key(self, key):
        self.keys_pressed.add(key)
    
    def handle_key_up(self, key):
        self.keys_pressed.discard(key)
    
    def handle_wheel(self, y, x=0):
        """滚轮：垂直滚动为主，水平滚动为辅"""
        self.camera_y -= y * 30
        self.camera_x -= x * 30
        self._clamp_camera()
    
    def update(self):
        """每帧更新：处理键盘持续移动"""
        for key in self.keys_pressed:
            if key == pygame.K_LEFT or key == pygame.K_a:
                self.camera_x -= self.move_speed
            elif key == pygame.K_RIGHT or key == pygame.K_d:
                self.camera_x += self.move_speed
            elif key == pygame.K_UP or key == pygame.K_w:
                self.camera_y -= self.move_speed
            elif key == pygame.K_DOWN or key == pygame.K_s:
                self.camera_y += self.move_speed
        if self.keys_pressed:
            self._clamp_camera()
    
    def _clamp_camera(self):
        all_nodes = self._get_all_nodes()
        if not all_nodes:
            return
        min_x = min(n.x for n in all_nodes) - 300
        max_x = max(n.x + n.width for n in all_nodes) + 300
        min_y = min(n.y for n in all_nodes) - 200
        max_y = max(n.y + n.height for n in all_nodes) + 200
        self.camera_x = max(min_x, min(max_x, self.camera_x))
        self.camera_y = max(min_y, min(max_y, self.camera_y))
    
    def _get_all_nodes(self):
        result = []
        def collect(node):
            result.append(node)
            for c in node.children:
                collect(c)
        for r in self.roots:
            collect(r)
        return result
    
    def _world_to_screen(self, x, y, scale):
        sw, sh = pygame.display.get_surface().get_size()
        sx = (x - self.camera_x) * scale * self.zoom + sw * 0.1
        sy = (y - self.camera_y) * scale * self.zoom + 60
        return int(sx), int(sy)
    
    def draw(self, screen, font, font_large, font_title, scale, player_skill_tree=None):
        if not self.visible:
            return
        sw, sh = screen.get_size()
        
        # 背景（必须最先绘制，否则会覆盖其他元素）
        screen.fill((15, 15, 25))
        
        # 绘制返回按钮（左上角）
        btn_w, btn_h = 100, 40
        btn_x, btn_y = 15, 15
        self.back_button_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        mouse_pos = pygame.mouse.get_pos()
        is_hover = self.back_button_rect.collidepoint(mouse_pos)
        btn_color = (80, 80, 100) if is_hover else (50, 50, 70)
        pygame.draw.rect(screen, btn_color, self.back_button_rect, border_radius=6)
        pygame.draw.rect(screen, (150, 150, 180), self.back_button_rect, 2, border_radius=6)
        back_text = font.render("← 返回", True, WHITE)
        screen.blit(back_text, (btn_x + (btn_w - back_text.get_width()) // 2,
                                btn_y + (btn_h - back_text.get_height()) // 2))
        
        # 标题
        title_surf = font_title.render("技能升级树", True, GOLD)
        screen.blit(title_surf, (sw // 2 - title_surf.get_width() // 2, 15))
        
        # 提示
        hint = "方向键/WASD移动 | 鼠标/触控拖动 | 滚轮滚动 | ESC返回 | 点击技能查看详情"
        hint_surf = font.render(hint, True, LIGHT_GRAY)
        screen.blit(hint_surf, (sw // 2 - hint_surf.get_width() // 2, sh - 30))
        
        all_nodes = self._get_all_nodes()
        
        # 绘制连接线
        self._draw_connections(screen, all_nodes, scale)
        
        # 绘制节点
        self._draw_nodes(screen, font, font_large, all_nodes, player_skill_tree, scale)
        
        # 绘制详情面板
        if self.selected_node:
            self._draw_node_detail(screen, font, font_large, self.selected_node, player_skill_tree)
        
        # 滚动指示器
        self._draw_scroll_indicators(screen, sw, sh)
    
    def _draw_connections(self, screen, all_nodes, scale):
        for node in all_nodes:
            for child in node.children:
                x1, y1 = self._world_to_screen(node.x + node.width // 2, node.y + node.height, scale)
                x2, y2 = self._world_to_screen(child.x + child.width // 2, child.y, scale)
                # 贝塞尔曲线
                mid_y = (y1 + y2) // 2
                points = []
                for t in range(0, 21):
                    tt = t / 20.0
                    px = x1 + (x2 - x1) * tt
                    py = (1-tt)**2 * y1 + 2*(1-tt)*tt * mid_y + tt**2 * y2
                    points.append((int(px), int(py)))
                if len(points) >= 2:
                    pygame.draw.lines(screen, (80, 80, 120), False, points, 2)
    
    def _is_upgradeable(self, node, player_skill_tree, all_nodes_dict):
        """判断技能是否可升级：已解锁、未满级、前置技能已拥有"""
        if not skill_tree_unlock_manager.is_unlocked(node.skill_type):
            return False
        if not player_skill_tree:
            return False
        skill = player_skill_tree.get_skill(node.skill_type)
        owned_level = skill.current_level if skill else 0
        if owned_level >= node.max_level:
            return False
        # 检查前置技能
        for prereq_type, prereq_lvl in node.requires:
            prereq_skill = player_skill_tree.get_skill(prereq_type)
            prereq_owned = prereq_skill.current_level if prereq_skill else 0
            if prereq_owned < prereq_lvl:
                return False
        return True

    def _draw_nodes(self, screen, font, font_large, all_nodes, player_skill_tree, scale):
        for node in all_nodes:
            sx, sy = self._world_to_screen(node.x, node.y, scale)
            w = int(node.width * scale * self.zoom)
            h = int(node.height * scale * self.zoom)
            
            # 判断状态
            is_unlocked = skill_tree_unlock_manager.is_unlocked(node.skill_type)
            owned_level = 0
            if player_skill_tree and hasattr(player_skill_tree, 'get_level'):
                owned_level = player_skill_tree.get_skill(node.skill_type).current_level if player_skill_tree.get_skill(node.skill_type) else 0
            
            if not is_unlocked:
                # 未解锁：灰色剪影
                bg_color = (30, 30, 35)
                border_color = (50, 50, 55)
                text_color = (60, 60, 65)
            elif owned_level > 0:
                # 已拥有：发光
                glow = min(owned_level, node.max_level)
                bg_color = (20 + glow * 15, 30 + glow * 10, 50 + glow * 20)
                border_color = node.icon_color
                text_color = WHITE
                # 发光效果
                if owned_level >= node.max_level:
                    pygame.draw.rect(screen, node.icon_color, (sx-3, sy-3, w+6, h+6), 2)
            else:
                # 已解锁但未拥有
                bg_color = (35, 35, 45)
                border_color = (100, 100, 130)
                text_color = LIGHT_GRAY
            
            # 可升级高亮检测（构建节点字典用于前置查询）
            all_nodes_dict = {n.skill_type: n for n in all_nodes}
            is_upgradeable = self._is_upgradeable(node, player_skill_tree, all_nodes_dict)
            
            # 绘制节点背景
            pygame.draw.rect(screen, bg_color, (sx, sy, w, h), border_radius=6)
            if is_upgradeable:
                # 可升级：脉动绿色边框 + 发光
                pulse = abs(pygame.time.get_ticks() / 400.0) % 2.0
                glow_alpha = int(80 + 40 * (1.0 if pulse > 1.0 else pulse))
                glow_surf = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (0, 255, 100, glow_alpha), (0, 0, w + 8, h + 8), border_radius=8)
                screen.blit(glow_surf, (sx - 4, sy - 4))
                pygame.draw.rect(screen, (0, 255, 100), (sx, sy, w, h), 3, border_radius=6)
                # 可升级标记
                up_text = font.render("↑可升级", True, (0, 255, 100))
                screen.blit(up_text, (sx + w - up_text.get_width() - 5, sy + 2))
            else:
                pygame.draw.rect(screen, border_color, (sx, sy, w, h), 2, border_radius=6)
            
            # 图标（彩色圆点）
            icon_r = max(6, int(10 * scale * self.zoom))
            icon_x = sx + icon_r + 5
            icon_y = sy + h // 2
            if is_unlocked:
                pygame.draw.circle(screen, node.icon_color, (icon_x, icon_y), icon_r)
            else:
                pygame.draw.circle(screen, (50, 50, 55), (icon_x, icon_y), icon_r)
            
            # 名称
            if is_unlocked:
                name_surf = font.render(node.name, True, text_color)
            else:
                name_surf = font.render("???", True, text_color)
            name_x = icon_x + icon_r + 8
            screen.blit(name_surf, (name_x, sy + 8))
            
            # 等级
            if is_unlocked and node.max_level > 1:
                lvl_text = f"Lv.{owned_level}/{node.max_level}" if owned_level > 0 else f"Max:{node.max_level}"
                lvl_surf = font.render(lvl_text, True, GOLD if owned_level > 0 else GRAY)
                screen.blit(lvl_surf, (name_x, sy + h - 22))
            
            # 选中高亮
            if self.selected_node == node:
                pygame.draw.rect(screen, YELLOW, (sx-2, sy-2, w+4, h+4), 2, border_radius=6)
    
    def _draw_node_detail(self, screen, font, font_large, node, player_skill_tree):
        sw, sh = screen.get_size()
        panel_w = 360
        panel_h = 280
        px = sw - panel_w - 20
        py = 80
        
        # 面板背景
        pygame.draw.rect(screen, (20, 20, 30), (px, py, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(screen, node.icon_color, (px, py, panel_w, panel_h), 2, border_radius=8)
        
        is_unlocked = skill_tree_unlock_manager.is_unlocked(node.skill_type)
        owned_level = 0
        if player_skill_tree and hasattr(player_skill_tree, 'get_level'):
            owned_level = player_skill_tree.get_skill(node.skill_type).current_level if player_skill_tree.get_skill(node.skill_type) else 0
        
        # 标题
        title = node.name if is_unlocked else "未知技能"
        title_surf = font_large.render(title, True, node.icon_color if is_unlocked else GRAY)
        screen.blit(title_surf, (px + 15, py + 12))
        
        # 等级
        if is_unlocked:
            lvl = f"等级: {owned_level}/{node.max_level}"
            lvl_surf = font.render(lvl, True, GOLD)
            screen.blit(lvl_surf, (px + panel_w - 100, py + 15))
        
        # 描述
        if is_unlocked:
            desc = node.description
        else:
            desc = "在游戏中遇到此技能即可解锁详情。"
        
        # 自动换行
        words = desc
        lines = []
        max_chars = panel_w // (font.size("中")[0]) - 4
        cur = ""
        for ch in words:
            cur += ch
            if len(cur) >= max_chars or ch == '\n':
                lines.append(cur)
                cur = ""
        if cur:
            lines.append(cur)
        
        y = py + 50
        for line in lines[:8]:
            line_surf = font.render(line, True, LIGHT_GRAY)
            screen.blit(line_surf, (px + 15, y))
            y += 22
        
        # 前置依赖
        if node.requires and is_unlocked:
            y += 10
            req_surf = font.render("前置依赖:", True, ORANGE)
            screen.blit(req_surf, (px + 15, y))
            y += 20
            for req_type, req_lvl in node.requires:
                req_name = req_type.name if hasattr(req_type, 'name') else str(req_type)
                req_text = f"  - {req_name} Lv.{req_lvl}"
                req_surf2 = font.render(req_text, True, GRAY)
                screen.blit(req_surf2, (px + 15, y))
                y += 18
        
        # 状态
        y = py + panel_h - 35
        if owned_level > 0:
            status = "已学习"
            status_color = GREEN
        elif is_unlocked:
            status = "已解锁（可在升级时选择）"
            status_color = CYAN
        else:
            status = "未解锁"
            status_color = RED
        status_surf = font.render(status, True, status_color)
        screen.blit(status_surf, (px + 15, y))
    
    def _draw_scroll_indicators(self, screen, sw, sh):
        all_nodes = self._get_all_nodes()
        if not all_nodes:
            return
        min_x = min(n.x for n in all_nodes)
        max_x = max(n.x + n.width for n in all_nodes)
        min_y = min(n.y for n in all_nodes)
        max_y = max(n.y + n.height for n in all_nodes)
        
        # 左右箭头
        if self.camera_x > min_x + 100:
            pygame.draw.polygon(screen, GOLD, [(30, sh//2), (50, sh//2-15), (50, sh//2+15)])
        if self.camera_x < max_x - 500:
            pygame.draw.polygon(screen, GOLD, [(sw-30, sh//2), (sw-50, sh//2-15), (sw-50, sh//2+15)])
