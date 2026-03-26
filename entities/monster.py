"""
Monster entity — pure data + rendering.
FSM state and update logic live in AISystem to keep this file focused.
"""

from __future__ import annotations

from enum import Enum, auto

import pygame

from settings import MONSTER


class MonsterType(Enum):
    BASIC = auto()  # slow, hunts by proximity
    STALKER = auto()  # fast, only moves in full darkness
    SMASHER = auto()  # targets structures, ignores player


# Per-type tuning table (speed, aggro_radius, hp, color)
_TYPE_STATS: dict[MonsterType, tuple[float, float, float, tuple[int, int, int]]] = {
    MonsterType.BASIC: (90.0, 200.0, 2.0, (160, 40, 40)),
    MonsterType.STALKER: (160.0, 260.0, 1.0, (80, 20, 140)),
    MonsterType.SMASHER: (60.0, 100.0, 5.0, (120, 80, 20)),
}


class Monster:
    def __init__(
        self,
        pos: pygame.Vector2,
        kind: MonsterType,
        speed: float,
        aggro_radius: float,
        hp: float,
        color: tuple[int, int, int],
    ) -> None:
        self.pos: pygame.Vector2 = pygame.Vector2(pos)
        self.kind = kind
        self.speed = speed
        self.aggro_radius = aggro_radius
        self.hp = hp
        self.max_hp = hp
        self._color = color

        self.rect = pygame.Rect(0, 0, 24, 24)
        self.rect.center = (int(self.pos.x), int(self.pos.y))

        # FSM state — written by AISystem
        from systems.ai_system import AIState  # local import avoids circular dep

        self.state: AIState = AIState.WANDER
        self.alert_timer: float = 0.8
        self.wander_target: pygame.Vector2 | None = None

    @classmethod
    def create(cls, kind: MonsterType, pos: pygame.Vector2, night: int) -> Monster:
        speed, aggro, hp, color = _TYPE_STATS[kind]
        difficulty = MONSTER.night_difficulty_scale ** (night - 1)
        return cls(
            pos=pos,
            kind=kind,
            speed=speed * difficulty,
            aggro_radius=aggro,
            hp=hp * 10,
            color=color,
        )

    @property
    def targets_campfire(self) -> bool:
        """SMASHER ignores the player and attacks the campfire instead."""
        return self.kind == MonsterType.SMASHER

    # ------------------------------------------------------------------
    def draw(self, screen: pygame.Surface) -> None:
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        pygame.draw.rect(screen, self._color, self.rect, border_radius=4)

        # HP bar
        if self.hp < self.max_hp:
            bar_w = self.rect.width
            filled = int(bar_w * self.hp / self.max_hp)
            bar_rect = pygame.Rect(self.rect.x, self.rect.top - 6, bar_w, 3)
            pygame.draw.rect(screen, (60, 20, 20), bar_rect)
            pygame.draw.rect(
                screen, (200, 60, 60), pygame.Rect(bar_rect.x, bar_rect.y, filled, 3)
            )
