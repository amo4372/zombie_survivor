import os
os.chdir(r'C:\Users\A\Desktop\zombie_survivor_package')

# ==================== 1. renderer.py: 体力条显示数字 ====================
with open('renderer.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_sta_label = '''        sta_label = self.game.font_small.render("体力", True, (*stamina_color[:3], 200))
        # 体力标签放在体力条右侧
        self.screen.blit(sta_label, (bar_x + bar_w + int(10*scale), stamina_y + 1))'''
new_sta_label = '''        sta_label = self.game.font_small.render(
            f"体力 {int(player.stamina)}/{int(player.max_stamina)}", True, (*stamina_color[:3], 220))
        # 体力标签+数字放在体力条右侧
        self.screen.blit(sta_label, (bar_x + bar_w + int(10*scale), stamina_y + 1))'''
c = c.replace(old_sta_label, new_sta_label, 1)
print('1. renderer.py: stamina bar numbers added')

# ==================== 2. entities.py: Enemy障碍物碰撞 + DOT致死安全检查 ====================
with open('entities.py', 'r', encoding='utf-8') as f:
    c = f.read()

# 2a. Enemy.update 添加world参数
old_enemy_update_sig = '    def update(self, dt, player_x, player_y, player):'
new_enemy_update_sig = '    def update(self, dt, player_x, player_y, player, world=None):'
c = c.replace(old_enemy_update_sig, new_enemy_update_sig, 1)

# 2b. DOT致死安全检查（在buff_manager.update之后）
old_buff_update = '''        # 更新Buff系统（持续伤害/治疗等）
        _, self.buff_damage_events = self.buff_manager.update(dt, self)
        self._buff_speed_mult = self.buff_manager.get_speed_mult()'''
new_buff_update = '''        # 更新Buff系统（持续伤害/治疗等）
        _, self.buff_damage_events = self.buff_manager.update(dt, self)
        # DOT致死安全检查：确保持续伤害能杀死怪物
        if self.hp <= 0 and self.alive:
            self.alive = False
        self._buff_speed_mult = self.buff_manager.get_speed_mult()'''
c = c.replace(old_buff_update, new_buff_update, 1)

# 2c. 移动逻辑添加障碍物碰撞（替换直接修改x/y的部分）
old_movement = '''                if getattr(self, "attack_range", 0) > 0 and dist < self.attack_range:
                    if dist < self.attack_range * 0.5:
                        self.x -= (dx / dist) * self.speed * self._buff_speed_mult * dt * 60
                        self.y -= (dy / dist) * self.speed * self._buff_speed_mult * dt * 60
                    else:
                        self._ranged_attack(dt, player_x, player_y, dist)
                else:
                    self.x += (dx / dist) * self.speed * self._buff_speed_mult * dt * 60
                    self.y += (dy / dist) * self.speed * self._buff_speed_mult * dt * 60'''

new_movement = '''                if getattr(self, "attack_range", 0) > 0 and dist < self.attack_range:
                    if dist < self.attack_range * 0.5:
                        move_dx = -(dx / dist) * self.speed * self._buff_speed_mult * dt * 60
                        move_dy = -(dy / dist) * self.speed * self._buff_speed_mult * dt * 60
                        self._move_with_obstacle_collision(move_dx, move_dy, world)
                    else:
                        self._ranged_attack(dt, player_x, player_y, dist)
                else:
                    move_dx = (dx / dist) * self.speed * self._buff_speed_mult * dt * 60
                    move_dy = (dy / dist) * self.speed * self._buff_speed_mult * dt * 60
                    self._move_with_obstacle_collision(move_dx, move_dy, world)'''
c = c.replace(old_movement, new_movement, 1)

# 2d. 添加障碍物碰撞移动方法（在Enemy类中，_boss_behavior之前）
old_boss_behavior = '''    def _boss_behavior(self, dt, player_x, player_y, dist, player):'''
new_collision_method = '''    def _move_with_obstacle_collision(self, move_dx, move_dy, world):
        """带障碍物碰撞的移动：普通怪物被阻挡，特殊怪物可穿越"""
        # 可穿越障碍物的特殊怪物
        can_phase = (getattr(self, "is_crawler", False) or   # 爬行者可攀爬
                      getattr(self, "is_phantom", False) or    # 幻影可穿墙
                      getattr(self, "is_wraith", False) or     # 怨灵可飞行
                      getattr(self, "is_leaper", False) or      # 跳跃者可跳过
                      getattr(self, "is_boss", False))          # Boss可撞破

        if can_phase or world is None or not hasattr(world, 'obstacles'):
            self.x += move_dx
            self.y += move_dy
            return

        # 普通怪物：障碍物碰撞检测（尝试X和Y分别移动实现滑动）
        enemy_rect = pygame.Rect(self.x - self.size, self.y - self.size,
                                  self.size * 2, self.size * 2)
        # 尝试X方向移动
        new_rect_x = enemy_rect.copy()
        new_rect_x.x += move_dx
        x_blocked = any(new_rect_x.colliderect(obs['rect']) for obs in world.obstacles)
        if not x_blocked:
            self.x += move_dx
        # 尝试Y方向移动
        new_rect_y = enemy_rect.copy()
        new_rect_y.y += move_dy
        y_blocked = any(new_rect_y.colliderect(obs['rect']) for obs in world.obstacles)
        if not y_blocked:
            self.y += move_dy

    def _boss_behavior(self, dt, player_x, player_y, dist, player):'''
c = c.replace(old_boss_behavior, new_collision_method, 1)

print('2. entities.py: obstacle collision + DOT death safety added')

# ==================== 3. game.py: 传递world给enemy.update ====================
with open('game.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_enemy_call = '            result = enemy.update(dt, target_x, target_y, target_obj)'
new_enemy_call = '            result = enemy.update(dt, target_x, target_y, target_obj, self.world)'
c = c.replace(old_enemy_call, new_enemy_call, 1)
print('3. game.py: world passed to enemy.update')

# ==================== 4. world.py: 增加障碍物密度 ====================
with open('world.py', 'r', encoding='utf-8') as f:
    c = f.read()

# 找到障碍物生成数量并增加
old_obs_count = '''        # 生成障碍物
        for _ in range(80):'''
new_obs_count = '''        # 生成障碍物（根据地图类型增加密度）
        obs_density = {
            MapType.SCHOOL: 150,
            MapType.STREET: 130,
            MapType.DOWNTOWN: 160,
            MapType.SUBURB: 100,
            MapType.NUCLEAR_PLANT: 140,
        }
        obs_count = obs_density.get(map_type, 120)
        for _ in range(obs_count):'''
c = c.replace(old_obs_count, new_obs_count, 1)
print('4. world.py: obstacle density increased per map type')

with open('entities.py', 'w', encoding='utf-8') as f:
    f.write(c)
with open('renderer.py', 'w', encoding='utf-8') as f:
    f.write(c)
with open('game.py', 'w', encoding='utf-8') as f:
    f.write(c)
with open('world.py', 'w', encoding='utf-8') as f:
    f.write(c)

# 编译验证
import subprocess
for fn in ['entities.py', 'renderer.py', 'game.py', 'world.py']:
    r = subprocess.run(['python', '-m', 'py_compile', fn], capture_output=True, text=True, cwd=r'C:\Users\A\Desktop\zombie_survivor_package')
    print(f'{fn}: {"OK" if r.returncode == 0 else r.stderr[:600]}')
