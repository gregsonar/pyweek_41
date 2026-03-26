"""
World — runtime container for the current map.

Holds:
    tiles          — background tile rects + type
    obstacle_rects — solid collideable rectangles
    containers     — lootable objects (chests, crates)
    interactables  — anything the player can press E on
    light_sources  — stationary LightSource instances
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from systems.light_system import Segment, _rect_to_segments

if TYPE_CHECKING:
    from entities.light_source import LightSource


@dataclass
class Tile:
    rect: pygame.Rect
    kind: str  # "ground", "grass", "dirt", …
    color: tuple[int, int, int]


@dataclass
class Container:
    """Lootable crate / chest on the day map."""

    pos: pygame.Vector2
    rect: pygame.Rect
    loot: dict[str, int]  # resource → quantity
    opened: bool = False

    def interact(self, player) -> None:
        if self.opened:
            return
        self.opened = True
        for item, qty in self.loot.items():
            player.add_item(item, qty)

    def draw(self, screen: pygame.Surface) -> None:
        color = (100, 80, 60) if not self.opened else (60, 50, 40)
        pygame.draw.rect(screen, color, self.rect, border_radius=3)
        if not self.opened:
            pygame.draw.rect(screen, (180, 140, 80), self.rect, 2, border_radius=3)


@dataclass
class Obstacle:
    rect: pygame.Rect
    kind: str = "wall"  # "wall", "rock", "barricade", …
    hp: int = -1  # -1 = indestructible

    def draw(self, screen: pygame.Surface) -> None:
        colors = {
            "wall": (80, 80, 90),
            "rock": (100, 95, 85),
            "barricade": (120, 90, 50),
        }
        color = colors.get(self.kind, (90, 90, 90))
        pygame.draw.rect(screen, color, self.rect, border_radius=2)
        pygame.draw.rect(screen, (50, 50, 55), self.rect, 1, border_radius=2)


class World:
    def __init__(self) -> None:
        self.tiles: list[Tile] = []
        self.obstacles: list[Obstacle] = []
        self.containers: list[Container] = []
        self.light_sources: list[LightSource] = []

    @property
    def interactables(self):
        """Everything the player can interact with (E key)."""
        return self.containers

    @property
    def campfire(self):
        """Returns the first active campfire on the map, or None."""
        from entities.light_source import LightSourceKind

        return next(
            (ls for ls in self.light_sources if ls.kind == LightSourceKind.CAMPFIRE),
            None,
        )

    # ------------------------------------------------------------------
    # Geometry helpers queried by LightSystem and CollisionSystem
    # ------------------------------------------------------------------
    def obstacle_rects(self) -> list[pygame.Rect]:
        return [o.rect for o in self.obstacles]

    def obstacle_segments(self) -> list[Segment]:
        segs: list[Segment] = []
        for o in self.obstacles:
            segs.extend(_rect_to_segments(o.rect))
        return segs

    # ------------------------------------------------------------------
    # Frame
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        for ls in self.light_sources:
            ls.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        # Background tiles
        for tile in self.tiles:
            pygame.draw.rect(screen, tile.color, tile.rect)

        # Grid lines (cheap "tiled" feel until real sprites arrive)
        tile_size = 64
        w, h = screen.get_size()
        line_color = (30, 30, 35)
        for x in range(0, w, tile_size):
            pygame.draw.line(screen, line_color, (x, 0), (x, h))
        for y in range(0, h, tile_size):
            pygame.draw.line(screen, line_color, (0, y), (w, y))

        for obs in self.obstacles:
            obs.draw(screen)
        for con in self.containers:
            con.draw(screen)
        for ls in self.light_sources:
            ls.draw(screen)
