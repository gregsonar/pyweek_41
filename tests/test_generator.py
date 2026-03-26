"""
Tests for world.generator — procedural map generation.

Key invariants:
  1. Grid alignment: all obstacle/container rects snapped to grid_unit.
  2. Centre zone: no obstacles within SAFE_RADIUS_CELLS of spawn point.
  3. Reachability: containers have at least one free cardinal neighbour.
  4. Night map: campfire present at centre, ring of rocks around it.
"""
import math
import pytest
import pygame
from world.generator import (
    generate_day_map,
    generate_night_map,
    _snap,
    _has_free_neighbour,
    _scatter_obstacles,
)
from world.world import World
from entities.light_source import LightSourceKind
from settings import DISPLAY, WORLD


GRID = WORLD.grid_unit
SAFE_R = 3   # cells, must match generator constant
CX_CELL = (DISPLAY.width  // 2) // GRID
CY_CELL = (DISPLAY.height // 2) // GRID


# ---------------------------------------------------------------------------
# _snap helper
# ---------------------------------------------------------------------------

class TestSnap:
    @pytest.mark.parametrize("value, expected", [
        (0,   0),
        (31,  0),
        (32,  32),
        (63,  32),
        (64,  64),
        (100, 96),
    ])
    def test_snap_values(self, value, expected):
        assert _snap(value, GRID) == expected


# ---------------------------------------------------------------------------
# _has_free_neighbour
# ---------------------------------------------------------------------------

class TestHasFreeNeighbour:
    def test_surrounded_cell_has_no_free_neighbour(self):
        blocked = {(5, 5), (5, 6), (5, 4), (4, 5), (6, 5)}
        assert not _has_free_neighbour(5, 5, blocked)

    def test_open_cell_has_free_neighbour(self):
        assert _has_free_neighbour(0, 0, set())

    def test_partially_blocked_has_free_neighbour(self):
        blocked = {(5, 6), (5, 4), (4, 5)}   # only 3 of 4 neighbours blocked
        assert _has_free_neighbour(5, 5, blocked)


# ---------------------------------------------------------------------------
# _scatter_obstacles
# ---------------------------------------------------------------------------

class TestScatterObstacles:
    def _blocked(self, density=0.15) -> tuple[World, set]:
        w = World()
        blocked = _scatter_obstacles(w, density=density)
        return w, blocked

    def test_centre_zone_always_clear(self):
        """Run multiple times to catch random seeds that might violate the rule."""
        for _ in range(10):
            _, blocked = self._blocked(density=0.30)
            for dx in range(-SAFE_R, SAFE_R + 1):
                for dy in range(-SAFE_R, SAFE_R + 1):
                    cell = (CX_CELL + dx, CY_CELL + dy)
                    assert cell not in blocked, (
                        f"Centre cell {cell} was blocked (dx={dx}, dy={dy})"
                    )

    def test_obstacles_aligned_to_grid(self):
        w, _ = self._blocked()
        for obs in w.obstacles:
            assert obs.rect.x % GRID == 0, f"x={obs.rect.x} not grid-aligned"
            assert obs.rect.y % GRID == 0, f"y={obs.rect.y} not grid-aligned"
            assert obs.rect.width  % GRID == 0
            assert obs.rect.height % GRID == 0

    def test_obstacles_have_positive_size(self):
        w, _ = self._blocked()
        for obs in w.obstacles:
            assert obs.rect.width  >= GRID
            assert obs.rect.height >= GRID

    def test_returns_set_of_tuples(self):
        _, blocked = self._blocked()
        assert isinstance(blocked, set)
        if blocked:
            sample = next(iter(blocked))
            assert isinstance(sample, tuple) and len(sample) == 2


# ---------------------------------------------------------------------------
# generate_day_map
# ---------------------------------------------------------------------------

class TestGenerateDayMap:
    def test_returns_world(self):
        w = generate_day_map(1)
        assert isinstance(w, World)

    def test_has_tiles(self):
        w = generate_day_map(1)
        assert len(w.tiles) > 0

    def test_container_positions_aligned_to_grid(self):
        for night in (1, 2, 5):
            w = generate_day_map(night)
            for c in w.containers:
                assert c.rect.x % GRID == 0, f"Container x={c.rect.x} not grid-aligned"
                assert c.rect.y % GRID == 0

    def test_containers_not_inside_obstacles(self):
        for _ in range(5):
            w = generate_day_map(1)
            for c in w.containers:
                for o in w.obstacles:
                    assert not c.rect.colliderect(o.rect), (
                        f"Container at {c.rect} overlaps obstacle at {o.rect}"
                    )

    def test_containers_have_free_neighbour(self):
        """Reachability: every container must have at least one open cardinal cell."""
        for _ in range(5):
            w = generate_day_map(1)
            # Rebuild blocked set from actual obstacles
            blocked = set()
            for obs in w.obstacles:
                for bx in range(obs.rect.x // GRID, (obs.rect.right) // GRID + 1):
                    for by in range(obs.rect.y // GRID, (obs.rect.bottom) // GRID + 1):
                        blocked.add((bx, by))

            for c in w.containers:
                gx = c.rect.x // GRID
                gy = c.rect.y // GRID
                assert _has_free_neighbour(gx, gy, blocked), (
                    f"Container at grid ({gx},{gy}) is inaccessible"
                )

    def test_difficulty_reduces_loot_density(self):
        """Higher night_number → fewer or equal containers (density decreases)."""
        # Run several seeds and average
        counts_n1 = [len(generate_day_map(1).containers) for _ in range(5)]
        counts_n5 = [len(generate_day_map(5).containers) for _ in range(5)]
        assert sum(counts_n1) >= sum(counts_n5), (
            "Night 5 should not have more containers than night 1 on average"
        )

    def test_no_campfire_on_day_map(self):
        w = generate_day_map(1)
        assert w.campfire is None


# ---------------------------------------------------------------------------
# generate_night_map
# ---------------------------------------------------------------------------

class TestGenerateNightMap:
    def test_returns_world(self):
        w = generate_night_map(1, {})
        assert isinstance(w, World)

    def test_campfire_present_at_centre(self):
        w = generate_night_map(1, {})
        cf = w.campfire
        assert cf is not None
        assert cf.kind == LightSourceKind.CAMPFIRE
        cx, cy = DISPLAY.width // 2, DISPLAY.height // 2
        assert abs(cf.pos.x - cx) < 1
        assert abs(cf.pos.y - cy) < 1

    def test_obstacles_present_as_ring(self):
        """Night map should have a ring of obstacles around the campfire."""
        w = generate_night_map(1, {})
        assert len(w.obstacles) >= 4

    def test_more_obstacles_each_night(self):
        """Higher night → at least as many ring obstacles."""
        w1 = generate_night_map(1, {})
        w5 = generate_night_map(5, {})
        assert len(w5.obstacles) >= len(w1.obstacles)

    def test_no_containers_on_night_map(self):
        """Looting happens during the day only."""
        w = generate_night_map(1, {})
        assert w.containers == []
