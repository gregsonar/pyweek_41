"""
Simple AABB collision detection backed by a spatial grid for O(1) lookups
in dense scenes.

Usage
-----
    col = CollisionSystem()
    col.load_world(world)         # call once when map changes

    # Moving entity:
    new_pos, collided = col.move(entity_rect, velocity * dt)
"""
from __future__ import annotations

import pygame

from settings import WORLD


class CollisionSystem:
    def __init__(self, cell_size: int = WORLD.tile_size * 2) -> None:
        self._cell_size = cell_size
        self._grid: dict[tuple[int, int], list[pygame.Rect]] = {}
        self._static_rects: list[pygame.Rect] = []

    # ------------------------------------------------------------------
    def load_world(self, world) -> None:
        """Rebuild the spatial grid from world obstacles."""
        self._static_rects = list(world.obstacle_rects())
        self._grid.clear()
        for rect in self._static_rects:
            for cell in self._cells_for_rect(rect):
                self._grid.setdefault(cell, []).append(rect)

    # ------------------------------------------------------------------
    def move(
        self,
        rect: pygame.Rect,
        velocity: pygame.Vector2,
    ) -> tuple[pygame.Rect, bool]:
        """
        Move *rect* by *velocity* (pixels), resolving collisions.

        Returns
        -------
        (new_rect, collided)  — new_rect is the adjusted position.
        """
        collided = False
        new_rect = rect.move(int(velocity.x), int(velocity.y))

        obstacles = self._nearby_rects(new_rect)
        for obs in obstacles:
            if new_rect.colliderect(obs):
                collided = True
                new_rect = self._resolve(rect, new_rect, velocity, obs)
                break

        return new_rect, collided

    def is_solid_at(self, point: tuple[float, float]) -> bool:
        cell = self._cell(int(point[0]), int(point[1]))
        for rect in self._grid.get(cell, []):
            if rect.collidepoint(point):
                return True
        return False

    # ------------------------------------------------------------------
    def _resolve(
        self,
        old: pygame.Rect,
        new: pygame.Rect,
        vel: pygame.Vector2,
        obstacle: pygame.Rect,
    ) -> pygame.Rect:
        """Axis-separated push-out."""
        # Try horizontal only
        h = old.move(int(vel.x), 0)
        if not h.colliderect(obstacle):
            return h
        # Try vertical only
        v = old.move(0, int(vel.y))
        if not v.colliderect(obstacle):
            return v
        # Can't move
        return old

    def _nearby_rects(self, rect: pygame.Rect) -> list[pygame.Rect]:
        seen: set[int] = set()
        result: list[pygame.Rect] = []
        for cell in self._cells_for_rect(rect):
            for r in self._grid.get(cell, []):
                rid = id(r)
                if rid not in seen:
                    seen.add(rid)
                    result.append(r)
        return result

    def _cells_for_rect(self, rect: pygame.Rect) -> list[tuple[int, int]]:
        cs = self._cell_size
        x0, y0 = rect.left // cs,  rect.top // cs
        x1, y1 = rect.right // cs, rect.bottom // cs
        return [
            (x, y)
            for x in range(x0, x1 + 1)
            for y in range(y0, y1 + 1)
        ]

    def _cell(self, x: int, y: int) -> tuple[int, int]:
        return x // self._cell_size, y // self._cell_size
