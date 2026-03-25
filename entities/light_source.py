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
    TORCH    = auto()
    LANTERN  = auto()
    CANDLE   = auto()


# (radius, max_fuel, fuel_drain_per_sec, color_rgb)
_KIND_STATS: dict[LightSourceKind, tuple[float, float, float, tuple[int,int,int]]] = {
    LightSourceKind.CAMPFIRE: (LIGHT.campfire_radius, 300.0, 5.0,  (255, 140, 40)),
    LightSourceKind.TORCH:    (100.0,                  80.0, 10.0, (255, 180, 80)),
    LightSourceKind.LANTERN:  (140.0,                 120.0, 6.0,  (220, 210, 160)),
    LightSourceKind.CANDLE:   (60.0,                   60.0, 4.0,  (240, 200, 100)),
}


@dataclass
class LightSource:
    pos:       pygame.Vector2
    kind:      LightSourceKind
    radius:    float   = field(init=False)
    fuel:      float   = field(init=False)
    max_fuel:  float   = field(init=False)
    _drain:    float   = field(init=False, repr=False)
    _color:    tuple[int,int,int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.radius, self.max_fuel, self._drain, self._color = _KIND_STATS[self.kind]
        self.fuel = self.max_fuel

    @property
    def active(self) -> bool:
        return self.fuel > 0

    @property
    def intensity(self) -> float:
        """0..1 — used by LightSystem and for threat calculation."""
        return max(0.0, min(1.0, self.fuel / self.max_fuel))

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.fuel > 0:
            self.fuel = max(0.0, self.fuel - self._drain * dt)

    def refuel(self, amount: float) -> None:
        self.fuel = min(self.max_fuel, self.fuel + amount)

    def draw(self, screen: pygame.Surface) -> None:
        if not self.active:
            return
        # Placeholder sprite: coloured circle + flicker hint
        cx, cy = int(self.pos.x), int(self.pos.y)
        pygame.draw.circle(screen, self._color, (cx, cy), 10)
        pygame.draw.circle(screen, (255, 255, 200), (cx, cy), 4)
