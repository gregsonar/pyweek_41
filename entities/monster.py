"""
Monster entity — pure data + rendering.
FSM state and update logic live in AISystem to keep this file focused.
"""

from __future__ import annotations

import math
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

from settings import MONSTER

if TYPE_CHECKING:
    from core.sprite_renderer import AnimatedSprite


class MonsterType(Enum):
    BASIC = auto()  # slow, hunts by proximity
    STALKER = auto()  # fast, only moves in full darkness
    SMASHER = auto()  # targets structures, ignores player


# sprite name for each type (None = coloured placeholder until sprite is ready)
_TYPE_SPRITE: dict[MonsterType, str | None] = {
    MonsterType.BASIC: "monster_basic",
    MonsterType.STALKER: "monster_stalker",
    MonsterType.SMASHER: "monster_smasher",
}

# Per-type tuning table (speed, aggro_radius, hp, color)
_TYPE_STATS: dict[MonsterType, tuple[float, float, float, tuple[int, int, int]]] = {
    MonsterType.BASIC: (90.0, 200.0, 2.0, (160, 40, 40)),
    MonsterType.STALKER: (160.0, 260.0, 1.0, (80, 20, 140)),
    MonsterType.SMASHER: (60.0, 100.0, 5.0, (120, 80, 20)),
}

# Facing angle constants (degrees, CCW — pygame.transform.rotate convention).
# Source sprite faces UP (north), so 0° = no rotation needed.
_ANGLE_UP = 0.0
_ANGLE_LEFT = 90.0
_ANGLE_DOWN = 180.0
_ANGLE_RIGHT = 270.0  # == -90°


def _direction_to_angle(dx: float, dy: float) -> float:
    """
    Convert a movement delta to a rotation angle for a sprite that faces up.

    pygame.transform.rotate convention: positive = CCW.
    Screen coords: y increases downward.

    Expected results:
        up    (dy<0) →   0°  (no rotation)
        left  (dx<0) →  90°  (CCW quarter turn)
        down  (dy>0) → 180°  (half turn)
        right (dx>0) → 270°  (CW quarter turn)
    """
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return _ANGLE_UP
    rad = math.atan2(dy, dx)  # standard atan2, y positive downward
    deg = math.degrees(rad)  # 0 = east, CCW positive
    return (270.0 - deg) % 360.0  # remap so 0° = north (up)


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
        from systems.ai_system import AIState

        self.state: AIState = AIState.WANDER
        self.alert_timer: float = 0.8
        self.wander_target: pygame.Vector2 | None = None

        # Direction the sprite faces (degrees, see _direction_to_angle)
        self.facing_angle: float = _ANGLE_UP

        # Per-instance animation — None until SpriteRegistry.init() is called
        self.animated_sprite: AnimatedSprite | None = None
        self._try_load_sprite()

    # ------------------------------------------------------------------
    def _try_load_sprite(self) -> None:
        """Attach an AnimatedSprite if the registry is already initialised."""
        sprite_name = _TYPE_SPRITE.get(self.kind)
        if sprite_name is None:
            return
        try:
            from core.sprite_renderer import SpriteRegistry

            self.animated_sprite = SpriteRegistry.get_animated(sprite_name)
        except Exception:
            pass  # registry not yet initialised — draw() will use placeholder

    # ------------------------------------------------------------------
    @classmethod
    def create(cls, kind: MonsterType, pos: pygame.Vector2, night: int) -> Monster:
        speed, aggro, hp, color = _TYPE_STATS[kind]
        difficulty = MONSTER.night_difficulty_scale ** (night - 1)
        return cls(
            pos=pos,
            kind=kind,
            speed=speed * difficulty,
            aggro_radius=aggro,
            hp=hp * 10.0,
            color=color,
        )

    @property
    def targets_campfire(self) -> bool:
        return self.kind == MonsterType.SMASHER

    # ------------------------------------------------------------------
    def update_animation(self, dt: float, dx: float, dy: float) -> None:
        """
        Advance the animation and update the facing direction.

        Called by AISystem every frame.

        Parameters
        ----------
        dx, dy:
            Movement delta for this frame (can be 0,0 when idle).
        """
        if abs(dx) > 1e-4 or abs(dy) > 1e-4:
            self.facing_angle = _direction_to_angle(dx, dy)

        if self.animated_sprite is not None:
            self.animated_sprite.update(dt)

    # ------------------------------------------------------------------
    def draw(self, screen: pygame.Surface) -> None:
        self.rect.center = (int(self.pos.x), int(self.pos.y))

        if self.animated_sprite is not None:
            frame = self.animated_sprite.current_frame(self.facing_angle)
            # Centre the (possibly rotated) frame on the monster's rect centre
            frame_rect = frame.get_rect(center=self.rect.center)
            screen.blit(frame, frame_rect.topleft)
        else:
            # Coloured placeholder
            pygame.draw.rect(screen, self._color, self.rect, border_radius=4)

        # HP bar (shown only when damaged, on top of sprite)
        if self.hp < self.max_hp:
            bar_w = self.rect.width
            filled = int(bar_w * self.hp / self.max_hp)
            bar_rect = pygame.Rect(self.rect.x, self.rect.top - 6, bar_w, 3)
            pygame.draw.rect(screen, (60, 20, 20), bar_rect)
            pygame.draw.rect(
                screen,
                (200, 60, 60),
                pygame.Rect(bar_rect.x, bar_rect.y, filled, 3),
            )
