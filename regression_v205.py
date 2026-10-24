import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import pygame, math
pygame.init()
pygame.display.set_mode((1280, 720))
from game import Game
from config import GameState, WeaponType, GameMode
from entities import Enemy, EnemyType


def setup_mp():
    g = Game()
    g.records.unlock_weapon_purchase('SCYTHE')
    g.records.unlock_weapon_purchase('MINIGUN')
    g.multiplayer_mode = 'same_screen'
    g.config.game_mode = GameMode.ENDLESS
    g.selected_weapon = WeaponType.SCYTHE
    g.state = GameState.EQUIP_SELECT
    g.equip_confirm()
    g.selected_weapon = WeaponType.MINIGUN
    g.equip_confirm()
    g.state = GameState.PLAYING
    return g


# ===== v2.0.4 回归 =====
# 1. 摄像机半宽各自中心
g = setup_mp()
g.player.x = 500; g.player.y = 300
g.player2.x = 900; g.player2.y = 300
for _ in range(30):
    g.update(0.016)
assert g.camera.width == 640 and g.camera2.width == 640
assert abs(g.camera.x - 180) < 25, g.camera.x
assert abs(g.camera2.x - 580) < 25, g.camera2.x
print('1. 摄像机半宽各自中心 OK')

# 2. P2 受击倒地不结束
g2 = setup_mp()
g2.player.x = 0; g2.player.y = 0
g2.player2.x = 300; g2.player2.y = 0
e = Enemy(305, 0, EnemyType.ZOMBIE_NORMAL, 1, '普通'); e.damage = 100
g2.enemies.append(e)
for _ in range(200):
    g2.update(0.016)
    if g2.player2.downed:
        break
assert g2.player2.downed and g2.state == GameState.PLAYING
print('2. P2 受击倒地、游戏不结束 OK')

# 3. 倒地不成为目标→转攻P1
g2.player2.x = 900
e2 = Enemy(60, 0, EnemyType.ZOMBIE_NORMAL, 1, '普通'); e2.damage = 5
g2.enemies.append(e2)
p1_old = g2.player.hp
for _ in range(120):
    g2.update(0.016)
assert g2.player.hp < p1_old
print('3. 倒地不成为目标→转攻P1 OK')

# 4. 救援复活
g2.player.hp = -1
g2.player2.downed = False; g2.player2.alive = True; g2.player2.hp = 100
g2.player2.x = g2.player.x + 50; g2.player2.y = g2.player.y
g2._update_rescue(3.0)
assert not g2.player.downed and g2.player.alive and g2.player.hp > 0
print('4. 救援复活 OK')

# 5. 投掷物命中P2
g3 = setup_mp()
g3.player.x = 0; g3.player.y = 0
g3.player2.x = 300; g3.player2.y = 0
g3.enemy_throwables = [{'x': 295, 'y': 0, 'vx': 0, 'vy': 0, 'timer': 1.0, 'height': 0, 'type': 'rock', 'damage': 30}]
for _ in range(20):
    g3.update(0.016)
    if not g3.enemy_throwables:
        break
assert not g3.enemy_throwables and g3.player2.hp < g3.player2.max_hp
print('5. 投掷物命中P2 OK')

# 6. 单人结算
solo = Game()
solo.records.unlock_weapon_purchase('SCYTHE')
solo.multiplayer_mode = None
solo.config.game_mode = GameMode.ENDLESS
solo.selected_weapon = WeaponType.SCYTHE
solo.state = GameState.EQUIP_SELECT
solo.equip_confirm()
solo.state = GameState.PLAYING
es = Enemy(50, 0, EnemyType.ZOMBIE_NORMAL, 1, '普通'); es.damage = 100
solo.enemies.append(es)
for _ in range(200):
    solo.update(0.016)
    if solo.state == GameState.GAME_OVER:
        break
assert solo.state == GameState.GAME_OVER
print('6. 单人结算 OK')

# ===== v2.0.5 新增回归 =====
# 7. P2 升级半屏 + 标注
g4 = setup_mp()
g4.player2.skill_cards = g4.player2.skill_tree.get_random_skill_cards(3)
g4.player2.pending_level_up = True
g4._update_playing(0.016)
assert g4.state == GameState.SKILL_SELECT
assert g4.pending_upgrade_for == 'P2'
r = g4.skill_card_selector.region
assert r is not None and r.x == g4.scaled_width - g4.scaled_width // 2
g4._select_skill_card(0)
assert g4.state == GameState.PLAYING and not g4.player2.pending_level_up
print('7. P2 升级半屏+选卡应用 OK')

# 8. 单人升级全屏（回归）
solo.player.skill_cards = solo.player.skill_tree.get_random_skill_cards(3)
solo.player.pending_level_up = True
solo._update_playing(0.016)
assert solo.state == GameState.SKILL_SELECT
assert solo.skill_card_selector.region is None
solo._select_skill_card(0)
assert solo.state == GameState.PLAYING
print('8. 单人升级全屏 OK')

# 9. 双人全倒地结算不再崩溃（dt NameError）
g5 = setup_mp()
g5.player.hp = -1; g5.player2.hp = -1
g5.update(0.016)
assert g5.state == GameState.GAME_OVER
print('9. 双人全倒地结算无崩溃 OK')

# 10. 双人HUD渲染（新元素：时间/尸潮/体力/Buff/技能）
g6 = setup_mp()
for _ in range(5):
    g6.update(0.016)
g6.renderer.render()
print('10. 双人HUD渲染 OK')

print('==== 全量回归通过 ====')
