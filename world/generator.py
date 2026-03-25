"""
Procedural map generator.

generate_day_map(night_number)  → World
    Scatters obstacles and loot containers on a randomised grid.

generate_night_map(night_number, inventory) → World
    Places the campfire at the centre; adds obstacles the player
    built during the day (derived from inventory).
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from entities.light_source import LightSource, LightSourceKind
from settings import DISPLAY, RESOURCES, WORLD
from world.world import Container, Obstacle, Tile, World

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TILE_COLORS: dict[str, tuple[int, int, int]] = {
    "ground": (28, 32, 28),
    "grass":  (32, 42, 30),
    "dirt":   (40, 35, 28),
}

_LOOT_TABLE: list[tuple[str, int, float]] = [
    # (resource, max_qty, weight)
    (RESOURCES.FUEL,    3, 0.30),
    (RESOURCES.BATTERY, 2, 0.20),
    (RESOURCES.WOOD,    4, 0.30),
    (RESOURCES.METAL,   2, 0.10),
    (RESOURCES.CLOTH,   3, 0.10),
]


def _random_loot(min_types: int = 1, max_types: int = 3) -> dict[str, int]:
    resources, weights = zip(*[(r, w) for r, _, w in _LOOT_TABLE])
    chosen = random.choices(resources, weights=weights, k=random.randint(min_types, max_types))
    loot: dict[str, int] = {}
    for r in chosen:
        max_q = next(m for name, m, _ in _LOOT_TABLE if name == r)
        loot[r] = loot.get(r, 0) + random.randint(1, max_q)
    return loot


def _fill_tiles(world: World, tile_type: str = "ground") -> None:
    ts = WORLD.tile_size
    color = _TILE_COLORS[tile_type]
    w, h = DISPLAY.width, DISPLAY.height
    for tx in range(0, w, ts):
        for ty in range(0, h, ts):
            world.tiles.append(Tile(
                rect=pygame.Rect(tx, ty, ts, ts),
                kind=tile_type,
                color=color,
            ))


def _scatter_obstacles(
    world: World,
    density: float,
    screen_margin: int = 80,
) -> None:
    ts = WORLD.tile_size
    w, h = DISPLAY.width, DISPLAY.height

    for tx in range(screen_margin, w - screen_margin, ts):
        for ty in range(screen_margin, h - screen_margin, ts):
            if random.random() < density:
                rect = pygame.Rect(
                    tx + random.randint(0, ts // 3),
                    ty + random.randint(0, ts // 3),
                    random.randint(ts // 2, ts),
                    random.randint(ts // 2, ts),
                )
                world.obstacles.append(Obstacle(rect=rect, kind="rock"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_day_map(night_number: int) -> World:
    """
    Randomised exploration map.

    Difficulty creep: slightly more obstacles per night,
    slightly less loot.
    """
    rng_seed = random.randint(0, 2**31)
    random.seed(rng_seed)

    world = World()
    _fill_tiles(world, "grass")

    density = min(WORLD.obstacle_density * (1 + (night_number - 1) * 0.05), 0.25)
    _scatter_obstacles(world, density=density)

    # Loot containers
    ts = WORLD.tile_size
    w, h = DISPLAY.width, DISPLAY.height
    loot_density = max(WORLD.container_density * (1 - (night_number - 1) * 0.03), 0.02)
    margin = 100

    for tx in range(margin, w - margin, ts):
        for ty in range(margin, h - margin, ts):
            if random.random() < loot_density:
                pos = pygame.Vector2(
                    tx + ts // 2 + random.randint(-10, 10),
                    ty + ts // 2 + random.randint(-10, 10),
                )
                rect = pygame.Rect(0, 0, 36, 36)
                rect.center = (int(pos.x), int(pos.y))

                # Don't overlap obstacles
                if any(rect.colliderect(o.rect) for o in world.obstacles):
                    continue

                world.containers.append(Container(
                    pos=pos,
                    rect=rect,
                    loot=_random_loot(),
                ))

    return world


def generate_night_map(night_number: int, inventory: dict[str, int]) -> World:
    """
    Camp map: campfire at centre, ring of obstacles, darkness all around.

    Obstacles can include player-built barricades derived from inventory.
    """
    world = World()
    _fill_tiles(world, "dirt")

    cx, cy = DISPLAY.width // 2, DISPLAY.height // 2

    # Central campfire
    campfire = LightSource(
        pos=pygame.Vector2(cx, cy),
        kind=LightSourceKind.CAMPFIRE,
    )
    world.light_sources.append(campfire)

    # Ring of default rocks around the camp
    ring_radius = 160
    rock_count = 6 + night_number // 2
    for i in range(rock_count):
        angle_deg = 360 * i / rock_count + random.uniform(-15, 15)
        import math
        angle_rad = math.radians(angle_deg)
        rx = cx + ring_radius * math.cos(angle_rad)
        ry = cy + ring_radius * math.sin(angle_rad)
        size = random.randint(32, 56)
        rect = pygame.Rect(int(rx) - size // 2, int(ry) - size // 2, size, size)
        world.obstacles.append(Obstacle(rect=rect, kind="rock"))

    # TODO: add barricades the player built during the day
    # for barricade in player_structures:
    #     world.obstacles.append(Obstacle(rect=barricade.rect, kind="barricade"))

    return world
