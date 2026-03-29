"""
World — runtime container for the current map.

Holds:
    tiles          — background tile rects + type
    decorations    — visual-only overlays (bushes etc.), no collision
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
    kind: str
    color: tuple[int, int, int]


@dataclass
class Decoration:
    """
    Visual-only element drawn on top of background tiles.
    No collision, no game logic — purely cosmetic.
    """

    rect: pygame.Rect
    sprite_name: str

    def draw(self, screen: pygame.Surface) -> None:
        from core.sprite_renderer import SpriteRegistry

        surf = SpriteRegistry.get(self.sprite_name)
        if surf is not None:
            screen.blit(surf, self.rect.topleft)


@dataclass
class Container:
    """Lootable crate / chest on the day map."""

    pos: pygame.Vector2
    rect: pygame.Rect
    loot: dict[str, int]
    opened: bool = False

    def interact(self, player) -> None:
        if self.opened:
            return
        self.opened = True
        for item, qty in self.loot.items():
            player.add_item(item, qty)

    def draw(self, screen: pygame.Surface) -> None:
        from core.sprite_renderer import SpriteRegistry

        sprite_name = "container_opened" if self.opened else "container"
        surf = SpriteRegistry.get(sprite_name)
        if surf is not None:
            screen.blit(surf, self.rect.topleft)
        else:
            # Fallback colored rect
            color = (60, 50, 40) if self.opened else (100, 80, 60)
            pygame.draw.rect(screen, color, self.rect, border_radius=3)
            if not self.opened:
                pygame.draw.rect(screen, (180, 140, 80), self.rect, 2, border_radius=3)


@dataclass
class Obstacle:
    rect: pygame.Rect
    kind: str = "wall"
    hp: int = -1  # -1 = indestructible

    def draw(self, screen: pygame.Surface) -> None:
        from core.sprite_renderer import SpriteRegistry

        surf = SpriteRegistry.get_for_obstacle(self.rect)
        if surf is not None:
            screen.blit(surf, self.rect.topleft)
        else:
            # Fallback colored rect
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
        self.decorations: list[Decoration] = []  # bushes, debris — no collision
        self.obstacles: list[Obstacle] = []
        self.containers: list[Container] = []
        self.light_sources: list[LightSource] = []

    @property
    def interactables(self):
        return self.containers

    @property
    def campfire(self):
        from entities.light_source import LightSourceKind

        return next(
            (ls for ls in self.light_sources if ls.kind == LightSourceKind.CAMPFIRE),
            None,
        )

    # ------------------------------------------------------------------
    def obstacle_rects(self) -> list[pygame.Rect]:
        return [o.rect for o in self.obstacles]

    def obstacle_segments(self) -> list[Segment]:
        segs: list[Segment] = []
        for o in self.obstacles:
            segs.extend(_rect_to_segments(o.rect))
        return segs

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        for ls in self.light_sources:
            ls.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        # 1. Background tiles
        for tile in self.tiles:
            pygame.draw.rect(screen, tile.color, tile.rect)

        # 2. Grid lines
        tile_size = 64
        w, h = screen.get_size()
        line_color = (30, 30, 35)
        for x in range(0, w, tile_size):
            pygame.draw.line(screen, line_color, (x, 0), (x, h))
        for y in range(0, h, tile_size):
            pygame.draw.line(screen, line_color, (0, y), (w, y))

        # 3. Decorations (bushes etc.) — under obstacles
        for dec in self.decorations:
            dec.draw(screen)

        # 4. Obstacles, containers, light sources
        for obs in self.obstacles:
            obs.draw(screen)
        for con in self.containers:
            con.draw(screen)
        for ls in self.light_sources:
            ls.draw(screen)
