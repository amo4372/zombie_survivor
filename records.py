#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全局游戏记录系统 - 记录玩家自开始游玩以来的各项详细记录【兼容旧存档版】"""
import json
import os
import datetime
from config import GameMode
RECORDS_FILE = "game_records.json"
class GameRecords:
    """全局游戏记录管理器 - 持久化存储所有游戏数据"""
    def __init__(self, base_path="."):
        self.file_path = os.path.join(base_path, RECORDS_FILE)
        self.data = self._load()
        self._ensure_structure()

    def _load(self):
        """从文件加载记录，损坏文件返回空字典，保证不崩溃"""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[RECORDS] 加载记录失败/文件损坏: {e}")
        return {}

    def _save(self):
        """保存记录到文件"""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RECORDS] 保存记录失败: {e}")

    def _ensure_structure(self):
        """
        【兼容旧存档】只补缺失字段，不覆盖旧存档已有数据
        不会重置玩家已解锁成就、统计数据
        """
        defaults = {
            # === 基础统计 ===
            "total_games_played": 0,
            "total_play_time_seconds": 0,
            "total_play_time_formatted": "0:00:00",
            "first_play_date": None,
            "last_play_date": None,
            # === 最高记录 ===
            "best_score": 0,
            "best_score_date": None,
            "best_level": 0,
            "best_level_date": None,
            "best_time_survived": 0,
            "best_time_survived_date": None,
            "best_kills_single_game": 0,
            "best_kills_date": None,
            # === 累计统计 ===
            "total_kills": 0,
            "total_deaths": 0,
            "total_level_ups": 0,
            "total_skills_upgraded": 0,
            "total_weapons_collected": 0,
            "total_items_collected": 0,
            "total_exp_collected": 0,
            "total_damage_dealt": 0,
            "total_damage_taken": 0,
            "total_shots_fired": 0,
            "total_skills_used": 0,
            "total_dashes": 0,
            "total_bashes": 0,
            "total_grapples": 0,
            # === 敌人击杀统计 ===
            "kills_by_type": {
                "zombie_normal": 0,
                "zombie_fast": 0,
                "zombie_tank": 0,
                "zombie_ranged": 0,
                "zombie_exploder": 0,
                "zombie_crawler": 0,
                "zombie_splitter": 0,
                "zombie_shield": 0,
                "zombie_healer": 0,
                "zombie_phantom": 0,
                "boss_long": 0,
                "boss_xiang": 0,
            },
            # === 武器使用统计 ===
            "weapon_usage": {
                "pistol": 0,
                "rifle": 0,
                "shotgun": 0,
                "sniper": 0,
                "machine_gun": 0,
                "rocket_launcher": 0,
                "flamethrower": 0,
                "crossbow": 0,
                "grenade_launcher": 0,
                "plasma_rifle": 0,
                "railgun": 0,
                "minigun": 0,
                "double_barrel": 0,
            },
            # === 技能使用统计 ===
            "skill_usage": {
                "dash": 0,
                "grenade": 0,
                "turret": 0,
                "airstrike": 0,
                "shield_bash": 0,
                "grapple_pull": 0,
                "time_slow": 0,
                "overload": 0,
                "riot_gear": 0,
                "steel_will": 0,
                "blink": 0,
                "black_hole": 0,
                "ice_nova": 0,
                "chain_lightning": 0,
                "berserk": 0,
                "phantom_strike": 0,
                "medic_pod": 0,
                "shockwave": 0,
            },
            # === 结局统计 ===
            "endings": {
                "perfect": 0,
                "save_long": 0,
                "save_xiang": 0,
                "tragic": 0,
                "kill_both": 0,
                "let_go": 0,
            },
            # === 难度统计 ===
            "games_by_difficulty": {
                "简单": 0,
                "普通": 0,
                "困难": 0,
                "地狱": 0,
            },
            # === 模式统计 ===
            "games_by_mode": {
                "timed": 0,
                "endless": 0,
            },
            # === 历史记录（最近50局）===
            "game_history": [],
            # === 成就【带分组+隐藏标记】 ===
            "achievements": {
                # 战斗
                "first_blood": {"unlocked": False, "desc": "首次击杀", "date": None, "group":"战斗", "hidden":False},
                "zombie_slayer": {"unlocked": False, "desc": "累计击杀100只僵尸", "date": None, "group":"战斗", "hidden":False},
                "zombie_hunter": {"unlocked": False, "desc": "累计击杀1000只僵尸", "date": None, "group":"战斗", "hidden":False},
                "zombie_destroyer": {"unlocked": False, "desc": "累计击杀10000只僵尸", "date": None, "group":"战斗", "hidden":False},
                "boss_slayer": {"unlocked": False, "desc": "累计击杀10个Boss", "date": None, "group":"战斗", "hidden":False},
                "dragon_hunter": {"unlocked": False, "desc": "累计击杀龙某5次", "date": None, "group":"战斗", "hidden":False},
                "xiang_hunter": {"unlocked": False, "desc": "累计击杀向某5次", "date": None, "group":"战斗", "hidden":False},
                "centurion": {"unlocked": False, "desc": "单局击杀超过100只", "date": None, "group":"战斗", "hidden":False},
                "crit_master": {"unlocked": False, "desc": "累计打出500次暴击", "date": None, "group":"战斗", "hidden":False},
                "damage_deal_500k": {"unlocked": False, "desc": "累计造成50万伤害", "date": None, "group":"战斗", "hidden":False},
                "gunner": {"unlocked": False, "desc": "累计射击10000发子弹", "date": None, "group":"战斗", "hidden":False},
                "tough_guy": {"unlocked": False, "desc": "累计承受20万伤害", "date": None, "group":"战斗", "hidden":False},
                # 生存
                "survivor": {"unlocked": False, "desc": "存活超过5分钟", "date": None, "group":"生存", "hidden":False},
                "veteran": {"unlocked": False, "desc": "存活超过15分钟", "date": None, "group":"生存", "hidden":False},
                "legend": {"unlocked": False, "desc": "存活超过30分钟", "date": None, "group":"生存", "hidden":False},
                # 新增死亡成就
                "die_1": {"unlocked": False, "desc": "首次阵亡", "date": None, "group": "生存", "hidden": False},
                "die_10": {"unlocked": False, "desc": "累计阵亡10次", "date": None, "group": "生存", "hidden": False},
                "die_100": {"unlocked": False, "desc": "累计阵亡100次", "date": None, "group": "生存", "hidden": False},
                "die_1000": {"unlocked": False, "desc": "累计阵亡1000次", "date": None, "group": "生存", "hidden": False},
                "die_10000": {"unlocked": False, "desc": "累计阵亡10000次", "date": None, "group": "生存", "hidden": False},
                "horde_survivor_5": {"unlocked": False, "desc": "累计挺过5波尸潮", "date": None, "group":"生存", "hidden":False},
                "horde_survivor_20": {"unlocked": False, "desc": "累计挺过20波尸潮", "date": None, "group":"生存", "hidden":False},
                "untouchable": {"unlocked": False, "desc": "单局不受伤通关", "date": None, "group":"生存", "hidden":False},
                "iron_will": {"unlocked": False, "desc": "地狱难度存活8分钟以上", "date": None, "group":"生存", "hidden":False},
                "speedrunner": {"unlocked": False, "desc": "限时模式10分钟内通关", "date": None, "group":"生存", "hidden":False},
                
                # 技能武器
                "skill_master": {"unlocked": False, "desc": "单局升级技能20次", "date": None, "group":"技能武器", "hidden":False},
                "weapon_collector": {"unlocked": False, "desc": "单局收集所有武器类型", "date": None, "group":"技能武器", "hidden":False},
                "shield_master": {"unlocked": False, "desc": "累计格挡100次攻击", "date": None, "group":"技能武器", "hidden":False},
                "grapple_master": {"unlocked": False, "desc": "累计使用钩爪50次", "date": None, "group":"技能武器", "hidden":False},
                "berserker": {"unlocked": False, "desc": "累计使用狂暴10次", "date": None, "group":"技能武器", "hidden":False},
                "full_armory": {"unlocked": False, "desc": "解锁全部武器", "date": None, "group":"技能武器", "hidden":False},
                "no_skill_challenge": {"unlocked": False, "desc": "单局不使用任何主动技能存活10分钟", "date": None, "group":"技能武器", "hidden":False},
                # 结局挑战
                "millionaire": {"unlocked": False, "desc": "单局得分超过100万", "date": None, "group":"结局挑战", "hidden":False},
                "perfect_ending": {"unlocked": False, "desc": "达成完美结局", "date": None, "group":"结局挑战", "hidden":False},
                "all_endings": {"unlocked": False, "desc": "达成所有结局", "date": None, "group":"结局挑战", "hidden":False},
                # 隐藏成就示例
                "secret_zombie": {"unlocked": False, "desc": "发现秘密僵尸", "date": None, "group":"隐藏", "hidden":True},
            },
            # === 杂项统计 ===
            "total_shield_blocks": 0,
            "total_horde_survived": 0,
            "total_critical_hits": 0,
            "total_dodge_count": 0,
            "total_life_steal_heal": 0,
            "highest_combo_kills": 0,
        }

        # 顶层key：只补缺失，不覆盖旧数据
        for top_key, default_val in defaults.items():
            if top_key not in self.data:
                self.data[top_key] = default_val

        # 成就单独兼容：旧存档已有成就key，只补group/hidden，不覆盖unlocked/date
        ach_defaults = defaults["achievements"]
        if "achievements" not in self.data:
            self.data["achievements"] = ach_defaults
        else:
            for ach_key, def_data in ach_defaults.items():
                if ach_key not in self.data["achievements"]:
                    # 新成就key直接完整写入
                    self.data["achievements"][ach_key] = def_data
                else:
                    old = self.data["achievements"][ach_key]
                    # 只补缺失字段，保留旧存档unlocked、date、desc
                    for fill_k in ["group","hidden"]:
                        if fill_k not in old:
                            old[fill_k] = def_data[fill_k]

        self._save()

    def get_grouped_achievements(self, show_hidden_unlocked_only=True):
        """
        获取分组成就，兼容旧存档缺失group/hidden字段
        show_hidden_unlocked_only: True → 未解锁的隐藏成就过滤
        """
        ach = self.data["achievements"]
        groups = {}
        for key, data in ach.items():
            # 旧存档兜底默认值
            g = data.get("group", "其他")
            h = data.get("hidden", False)
            unlocked = data.get("unlocked", False)
            if h and (not unlocked) and show_hidden_unlocked_only:
                continue
            if g not in groups:
                groups[g] = []
            groups[g].append((key, data))
        return groups

    def get_achievement_progress(self, key):
        """
        获取成就进度，返回 (current, target)；无法量化的成就返回 None。
        已解锁成就返回 (target, target) 即 100%。
        """
        ach = self.data["achievements"].get(key)
        if not ach:
            return None
        if ach.get("unlocked", False):
            # 已解锁直接返回满进度
            targets = {
                "first_blood": 1, "zombie_slayer": 100, "zombie_hunter": 1000,
                "zombie_destroyer": 10000, "boss_slayer": 10, "dragon_hunter": 5,
                "xiang_hunter": 5, "centurion": 100, "crit_master": 500,
                "damage_deal_500k": 500000, "gunner": 10000, "tough_guy": 200000,
                "survivor": 300, "veteran": 900, "legend": 1800,
                "horde_survivor_5": 5, "horde_survivor_20": 20,
                "shield_master": 100, "grapple_master": 50, "berserker": 10,
                "millionaire": 1000000, "perfect_ending": 1, "all_endings": 6,
                "untouchable": 1, "iron_will": 480, "speedrunner": 1,
                "skill_master": 20, "weapon_collector": 13, "full_armory": 13,
                "no_skill_challenge": 1, "secret_zombie": 1,
            }
            t = targets.get(key, 1)
            return (t, t)
        d = self.data
        progress_map = {
            # 战斗 - 累计类
            "first_blood": (d["total_kills"], 1),
            "zombie_slayer": (d["total_kills"], 100),
            "zombie_hunter": (d["total_kills"], 1000),
            "zombie_destroyer": (d["total_kills"], 10000),
            "boss_slayer": (d["kills_by_type"].get("boss_long", 0) + d["kills_by_type"].get("boss_xiang", 0), 10),
            "dragon_hunter": (d["kills_by_type"].get("boss_long", 0), 5),
            "xiang_hunter": (d["kills_by_type"].get("boss_xiang", 0), 5),
            "crit_master": (d["total_critical_hits"], 500),
            "damage_deal_500k": (d["total_damage_dealt"], 500000),
            "gunner": (d["total_shots_fired"], 10000),
            "tough_guy": (d["total_damage_taken"], 200000),
            # 生存 - 用历史最佳
            "survivor": (d["best_time_survived"], 300),
            "veteran": (d["best_time_survived"], 900),
            "legend": (d["best_time_survived"], 1800),
            # 新增死亡进度
            "die_1": (self.data["total_deaths"], 1),
            "die_10": (self.data["total_deaths"], 10),
            "die_100": (self.data["total_deaths"], 100),
            "die_1000": (self.data["total_deaths"], 1000),
            "die_10000": (self.data["total_deaths"], 10000),
            "horde_survivor_5": (d["total_horde_survived"], 5),
            "horde_survivor_20": (d["total_horde_survived"], 20),
            # 技能武器
            "shield_master": (d["total_shield_blocks"], 100),
            "grapple_master": (d["total_grapples"], 50),
            "berserker": (d["skill_usage"].get("berserk", 0), 10),
            # 结局挑战
            "millionaire": (d["best_score"], 1000000),
            "perfect_ending": (d["endings"].get("perfect", 0), 1),
            "all_endings": (sum(1 for v in d["endings"].values() if v > 0), 6),
        }
        return progress_map.get(key, None)

    # ==================== 游戏开始/结束 ====================
    def on_game_start(self, difficulty, game_mode):
        """游戏开始时调用"""
        now = datetime.datetime.now().isoformat()
        if self.data["first_play_date"] is None:
            self.data["first_play_date"] = now
        self.data["last_play_date"] = now
        self.data["total_games_played"] += 1
        self.data["games_by_difficulty"][difficulty] = self.data["games_by_difficulty"].get(difficulty, 0) + 1
        mode_key = "timed" if str(game_mode) == "GameMode.TIMED" or str(game_mode) == "TIMED" else "endless"
        self.data["games_by_mode"][mode_key] = self.data["games_by_mode"].get(mode_key, 0) + 1
        self._save()
        return self._new_session()

    def _new_session(self):
        """创建新游戏会话记录器"""
        return GameSession(self)

    def on_game_end(self, session_data):
        """游戏结束时调用，更新所有统计"""
        d = session_data
        # 更新最高记录
        if d.get("score", 0) > self.data["best_score"]:
            self.data["best_score"] = d["score"]
            self.data["best_score_date"] = datetime.datetime.now().isoformat()
        if d.get("level", 0) > self.data["best_level"]:
            self.data["best_level"] = d["level"]
            self.data["best_level_date"] = datetime.datetime.now().isoformat()
        if d.get("time_survived", 0) > self.data["best_time_survived"]:
            self.data["best_time_survived"] = d["time_survived"]
            self.data["best_time_survived_date"] = datetime.datetime.now().isoformat()
        total_kills = sum(d.get("kills_by_type", {}).values())
        if total_kills > self.data["best_kills_single_game"]:
            self.data["best_kills_single_game"] = total_kills
            self.data["best_kills_date"] = datetime.datetime.now().isoformat()
        # 更新累计统计
        self.data["total_kills"] += total_kills
        self.data["total_deaths"] += 1 if d.get("died", True) else 0
        self.data["total_level_ups"] += d.get("level_ups", 0)
        self.data["total_skills_upgraded"] += d.get("skills_upgraded", 0)
        self.data["total_weapons_collected"] += d.get("weapons_collected", 0)
        self.data["total_items_collected"] += d.get("items_collected", 0)
        self.data["total_exp_collected"] += d.get("exp_collected", 0)
        self.data["total_damage_dealt"] += d.get("damage_dealt", 0)
        self.data["total_damage_taken"] += d.get("damage_taken", 0)
        self.data["total_shots_fired"] += d.get("shots_fired", 0)
        self.data["total_skills_used"] += d.get("skills_used", 0)
        self.data["total_dashes"] += d.get("dashes", 0)
        self.data["total_bashes"] += d.get("bashes", 0)
        self.data["total_grapples"] += d.get("grapples", 0)
        self.data["total_play_time_seconds"] += d.get("play_time", 0)
        self.data["total_shield_blocks"] += d.get("shield_blocks", 0)
        self.data["total_horde_survived"] += d.get("hordes_survived", 0)
        self.data["total_critical_hits"] += d.get("critical_hits", 0)
        self.data["total_dodge_count"] += d.get("dodge_count", 0)
        self.data["total_life_steal_heal"] += d.get("life_steal_heal", 0)
        # 格式化总时长
        total_secs = self.data["total_play_time_seconds"]
        hours = int(total_secs // 3600)
        mins = int((total_secs % 3600) // 60)
        secs = int(total_secs % 60)
        self.data["total_play_time_formatted"] = f"{hours}:{mins:02d}:{secs:02d}"
        # 更新敌人击杀
        for enemy_type, count in d.get("kills_by_type", {}).items():
            key = enemy_type.lower().replace("zombie_", "zombie_").replace("boss_", "boss_")
            if key in self.data["kills_by_type"]:
                self.data["kills_by_type"][key] += count
        # 更新武器使用
        for weapon, count in d.get("weapon_usage", {}).items():
            if weapon in self.data["weapon_usage"]:
                self.data["weapon_usage"][weapon] += count
        # 更新技能使用
        for skill, count in d.get("skill_usage", {}).items():
            if skill in self.data["skill_usage"]:
                self.data["skill_usage"][skill] += count
        # 更新结局
        ending = d.get("ending")
        if ending and ending in self.data["endings"]:
            self.data["endings"][ending] += 1

        # 检查成就，拿到本次新解锁列表
        new_unlock_keys = self._check_achievements(d, total_kills)
        self.data["newly_unlocked_ach_keys"] = new_unlock_keys

        # 更新历史记录
        history_entry = {
            "date": datetime.datetime.now().isoformat(),
            "score": d.get("score", 0),
            "level": d.get("level", 0),
            "time_survived": d.get("time_survived", 0),
            "kills": total_kills,
            "difficulty": d.get("difficulty", "普通"),
            "mode": d.get("mode", "timed"),
            "ending": ending,
            "died": d.get("died", True),
        }
        self.data["game_history"].insert(0, history_entry)
        if len(self.data["game_history"]) > 50:
            self.data["game_history"] = self.data["game_history"][:50]

        self._save()
        return new_unlock_keys

    def _check_achievements(self, d, total_kills):
        """检查并解锁成就，返回本次新解锁key列表，兼容旧存档字段"""
        new_unlocks = []
        now = datetime.datetime.now().isoformat()
        ach = self.data["achievements"]
        def unlock(key):
            item = ach.get(key)
            if not item:
                return
            if not item.get("unlocked", False):
                item["unlocked"] = True
                item["date"] = now
                new_unlocks.append(key)
        # 首次击杀
        if self.data["total_kills"] >= 1:
            unlock("first_blood")
        if self.data["total_kills"] >= 100:
            unlock("zombie_slayer")
        if self.data["total_kills"] >= 1000:
            unlock("zombie_hunter")
        if self.data["total_kills"] >= 10000:
            unlock("zombie_destroyer")
        # 存活时间
        if d.get("time_survived", 0) >= 300:
            unlock("survivor")
        if d.get("time_survived", 0) >= 900:
            unlock("veteran")
        if d.get("time_survived", 0) >= 1800:
            unlock("legend")
                # 死亡成就解锁
        if self.data["total_deaths"] >= 1:
            unlock("die_1")
        if self.data["total_deaths"] >= 10:
            unlock("die_10")
        if self.data["total_deaths"] >= 100:
            unlock("die_100")
        if self.data["total_deaths"] >= 1000:
            unlock("die_1000")
        if self.data["total_deaths"] >= 10000:
            unlock("die_10000")
        # 技能/武器
        if d.get("skills_upgraded", 0) >= 20:
            unlock("skill_master")
        if d.get("weapons_collected", 0) >= 13:
            unlock("weapon_collector")
        # Boss击杀
        boss_total = self.data["kills_by_type"].get("boss_long", 0) + self.data["kills_by_type"].get("boss_xiang", 0)
        if boss_total >= 10:
            unlock("boss_slayer")
        if self.data["kills_by_type"].get("boss_long", 0) >= 5:
            unlock("dragon_hunter")
        if self.data["kills_by_type"].get("boss_xiang", 0) >= 5:
            unlock("xiang_hunter")
        # 结局
        ending = d.get("ending")
        if ending == "perfect":
            unlock("perfect_ending")
        if all(self.data["endings"].get(e, 0) > 0 for e in self.data["endings"]):
            unlock("all_endings")
        # 其他旧成就
        if self.data["total_shield_blocks"] >= 100:
            unlock("shield_master")
        if self.data["total_grapples"] >= 50:
            unlock("grapple_master")
        if self.data["skill_usage"].get("berserk", 0) >= 10:
            unlock("berserker")
        if d.get("score", 0) >= 1000000:
            unlock("millionaire")
        if total_kills >= 100:
            unlock("centurion")
        if d.get("damage_taken", 0) == 0 and not d.get("died", True):
            unlock("untouchable")
        # 新增成就检测
        if self.data["total_horde_survived"] >=5:
            unlock("horde_survivor_5")
        if self.data["total_horde_survived"] >=20:
            unlock("horde_survivor_20")
        if self.data["total_critical_hits"] >=500:
            unlock("crit_master")
        if self.data["total_damage_dealt"] >=500000:
            unlock("damage_deal_500k")
        if self.data["total_shots_fired"] >=10000:
            unlock("gunner")
        if self.data["total_damage_taken"] >=200000:
            unlock("tough_guy")
        if d.get("mode") == "timed" and d.get("time_survived",0) <=600 and not d.get("died",True):
            unlock("speedrunner")
        if d.get("difficulty") == "地狱" and d.get("time_survived",0)>=480:
            unlock("iron_will")
        return new_unlocks

    # ==================== 查询接口 ====================
    def get_summary(self):
        return {
            "games": self.data["total_games_played"],
            "play_time": self.data["total_play_time_formatted"],
            "best_score": self.data["best_score"],
            "best_level": self.data["best_level"],
            "best_time_survived": self.data["best_time_survived"],
            "total_kills": self.data["total_kills"],
            "total_deaths": self.data["total_deaths"],
        }
    def get_full_report(self):
        return self.data.copy()
    def get_achievements(self):
        return self.data["achievements"]
    def get_unlocked_achievements(self):
        return {k: v for k, v in self.data["achievements"].items() if v.get("unlocked",False)}
    def get_game_history(self, limit=10):
        return self.data["game_history"][:limit]
    def get_kills_by_type(self):
        return self.data["kills_by_type"]
    def get_weapon_usage(self):
        return self.data["weapon_usage"]
    def get_skill_usage(self):
        return self.data["skill_usage"]
    def get_endings(self):
        return self.data["endings"]
    def reset_all(self):
        self.data = {}
        self._ensure_structure()
        self._save()

class GameSession:
    """单局游戏会话记录器"""
    def __init__(self, records_manager):
        self.records = records_manager
        self.start_time = datetime.datetime.now()
        self.data = {
            "score": 0,
            "level": 1,
            "level_ups": 0,
            "skills_upgraded": 0,
            "weapons_collected": 0,
            "items_collected": 0,
            "exp_collected": 0,
            "damage_dealt": 0,
            "damage_taken": 0,
            "shots_fired": 0,
            "skills_used": 0,
            "dashes": 0,
            "bashes": 0,
            "grapples": 0,
            "shield_blocks": 0,
            "hordes_survived": 0,
            "critical_hits": 0,
            "dodge_count": 0,
            "life_steal_heal": 0,
            "kills_by_type": {},
            "weapon_usage": {},
            "skill_usage": {},
            "ending": None,
            "died": True,
            "difficulty": "普通",
            "mode": "timed",
            "time_survived": 0,
            "play_time": 0,
        }
    def set_difficulty(self, diff):
        self.data["difficulty"] = diff
    def set_mode(self, mode):
        self.data["mode"] = "timed" if str(mode) == "GameMode.TIMED" or str(mode) == "TIMED" else "endless"
    def add_kill(self, enemy_type):
        key = str(enemy_type).lower().replace("enemytype.", "")
        self.data["kills_by_type"][key] = self.data["kills_by_type"].get(key, 0) + 1
    def add_weapon_use(self, weapon_name):
        key = weapon_name.lower().replace(" ", "_")
        self.data["weapon_usage"][key] = self.data["weapon_usage"].get(key, 0) + 1
    def add_skill_use(self, skill_name):
        key = skill_name.lower().replace(" ", "_")
        self.data["skill_usage"][key] = self.data["skill_usage"].get(key, 0) + 1
        self.data["skills_used"] += 1
    def add_score(self, points):
        self.data["score"] += points
    def add_level_up(self):
        self.data["level_ups"] += 1
        self.data["level"] += 1
    def add_skill_upgrade(self):
        self.data["skills_upgraded"] += 1
    def add_weapon_collected(self):
        self.data["weapons_collected"] += 1
    def add_item_collected(self):
        self.data["items_collected"] += 1
    def add_exp(self, amount):
        self.data["exp_collected"] += amount
    def add_damage_dealt(self, amount):
        self.data["damage_dealt"] += amount
    def add_damage_taken(self, amount):
        self.data["damage_taken"] += amount
    def add_shot_fired(self):
        self.data["shots_fired"] += 1
    def add_dash(self):
        self.data["dashes"] += 1
    def add_bash(self):
        self.data["bashes"] += 1
    def add_grapple(self):
        self.data["grapples"] += 1
    def add_shield_block(self):
        self.data["shield_blocks"] += 1
    def add_horde_survived(self):
        self.data["hordes_survived"] += 1
    def add_critical_hit(self):
        self.data["critical_hits"] += 1
    def add_dodge(self):
        self.data["dodge_count"] += 1
    def add_life_steal(self, amount):
        self.data["life_steal_heal"] += amount
    def set_ending(self, ending_type):
        self.data["ending"] = ending_type
    def set_died(self, died):
        self.data["died"] = died
    def finalize(self):
        elapsed = (datetime.datetime.now() - self.start_time).total_seconds()
        self.data["play_time"] = elapsed
        self.data["time_survived"] = elapsed
        new_unlocks = self.records.on_game_end(self.data)
        return new_unlocks