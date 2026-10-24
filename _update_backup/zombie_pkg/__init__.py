# -*- coding: utf-8 -*-
"""zombie_pkg - 游戏逻辑包（由 game.py 拆分，零逻辑改动）
类 Game 聚合 GameCore + 各功能 Mixin，外部 from game import Game 保持兼容。
"""
from .game_core import GameCore, Config, logger, _save_encrypt, _save_decrypt
from .mix_menu import MenuMixin
from .mix_hud import HudMixin
from .mix_input import InputMixin
from .mix_skills import SkillsMixin
from .mix_combat import CombatMixin
from .mix_effects import EffectsMixin
from .mix_playing import PlayingMixin
from .mix_multi import MultiplayerMixin
from .mix_net import NetMixin
from .mix_records import RecordsMixin
from .mix_shop import ShopMixin
from .mix_story import StoryMixin


class Game(GameCore, MenuMixin, HudMixin, InputMixin, SkillsMixin, CombatMixin,
           EffectsMixin, PlayingMixin, MultiplayerMixin, NetMixin, RecordsMixin,
           ShopMixin, StoryMixin):
    """完整游戏类（聚合拆分后的全部功能 Mixin，逻辑与拆分前等价）"""
    pass


__all__ = ["Game", "GameCore", "Config", "logger",
           "_save_encrypt", "_save_decrypt"]
