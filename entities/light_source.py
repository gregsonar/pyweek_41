"""
Stationary light source entity — campfire, torch, placed lantern, etc.

The LightSystem queries ``world.light_sources`` each frame and uses
these objects to build the visibility polygon.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import pygame

from settings import LIGHT, RESOURCES


class LightSourceKind(Enum):
    CAMPFIRE = auto()
    TORCH = auto()
    LANTERN = auto()
    CANDLE = auto()


# (radius, max_fuel, fuel_drain_per_sec, color_rgb, has_hp)
_KIND_STATS: dict[
    LightSourceKind, tuple[float, float, float, tuple[int, int, int], bool]
] = {
    LightSourceKind.CAMPFIRE: (LIGHT.campfire_radius, 300.0, 5.0, (255, 140, 40), True),
    LightSourceKind.TORCH: (100.0, 80.0, 10.0, (255, 180, 80), False),
    LightSourceKind.LANTERN: (140.0, 120.0, 6.0, (220, 210, 160), False),
    LightSourceKind.CANDLE: (60.0, 60.0, 4.0, (240, 200, 100), False),
}


@dataclass
class LightSource:
    pos: pygame.Vector2
    kind: LightSourceKind
    radius: float = field(init=False)
    fuel: float = field(init=False)
    max_fuel: float = field(init=False)
    hp: float = field(init=False)
    max_hp: float = field(init=False)
    _drain: float = field(init=False, repr=False)
    _color: tuple[int, int, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        radius, max_fuel, drain, color, has_hp = _KIND_STATS[self.kind]
        self.radius = radius
        self.max_fuel = max_fuel
        self.fuel = max_fuel
        self._drain = drain
        self._color = color
        self.max_hp = LIGHT.campfire_max_hp if has_hp else -1.0
        self.hp = self.max_hp

    @property
    def active(self) -> bool:
        """Campfire goes out if fuel OR hp reaches 0. Others only need fuel."""
        if self.max_hp > 0 and self.hp <= 0:
            return False
        return self.fuel > 0

    @property
    def intensity(self) -> float:
        """0..1 — used by LightSystem and for threat calculation."""
        return max(0.0, min(1.0, self.fuel / self.max_fuel))

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.active:
            self.fuel = max(0.0, self.fuel - self._drain * dt)

    def refuel(self, amount: float) -> None:
        self.fuel = min(self.max_fuel, self.fuel + amount)

    def take_damage(self, amount: float) -> None:
        """Only campfire (has_hp=True) takes structural damage."""
        if self.max_hp > 0:
            self.hp = max(0.0, self.hp - amount)

    def repair(self, amount: float) -> None:
        if self.max_hp > 0:
            self.hp = min(self.max_hp, self.hp + amount)

    def draw(self, screen: pygame.Surface) -> None:
        if not self.active:
            return
        cx, cy = int(self.pos.x), int(self.pos.y)
        pygame.draw.circle(screen, self._color, (cx, cy), 10)
        pygame.draw.circle(screen, (255, 255, 200), (cx, cy), 4)

        # HP bar for campfire
        if self.max_hp > 0:
            bar_w = 40
            filled = int(bar_w * self.hp / self.max_hp)
            bar_y = cy - 20
            pygame.draw.rect(
                screen, (60, 20, 20), pygame.Rect(cx - bar_w // 2, bar_y, bar_w, 4)
            )
            if filled > 0:
                pygame.draw.rect(
                    screen,
                    (220, 140, 40),
                    pygame.Rect(cx - bar_w // 2, bar_y, filled, 4),
                )
