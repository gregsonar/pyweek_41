"""
Tests for world.generator — procedural map generation.

Imports only the public API (_snap and _scatter_obstacles are tested
indirectly through generate_day_map; _has_free_neighbour is internal).

Key invariants:
  1. Grid alignment: all obstacle/container rects snapped to grid_unit.
  2. Centre zone: no obstacles within SAFE_RADIUS_CELLS of spawn point.
  3. Reachability: containers have at least one free cardinal neighbour.
  4. Night map: campfire present at centre, ring of rocks around it.
"""
import pytest
import pygame
from world.generator import generate_day_map, generate_night_map, _snap
from world.world import World
from entities.light_source import LightSourceKind
from settings import DISPLAY, WORLD


GRID = WORLD.grid_unit
SAFE_R = 3
CX_CELL = (DISPLAY.width  // 2) // GRID
CY_CELL = (DISPLAY.height // 2) // GRID


# ---------------------------------------------------------------------------
# _snap helper — pure function, fine to test directly
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
# generate_day_map
# ---------------------------------------------------------------------------

class TestGenerateDayMap:
    def test_returns_world(self):
        assert isinstance(generate_day_map(1), World)

    def test_has_tiles(self):
        assert len(generate_day_map(1).tiles) > 0

    def test_centre_zone_always_clear(self):
        """No obstacle may overlap the player spawn zone.
        Tested across multiple seeds because the generator is random."""
        cx = DISPLAY.width  // 2
        cy = DISPLAY.height // 2
        safe_zone = pygame.Rect(
            cx - SAFE_R * GRID,
            cy - SAFE_R * GRID,
            SAFE_R * 2 * GRID,
            SAFE_R * 2 * GRID,
        )
        for _ in range(8):
            w = generate_day_map(1)
            for obs in w.obstacles:
                assert not obs.rect.colliderect(safe_zone), (
                    f"Obstacle {obs.rect} overlaps the centre spawn zone {safe_zone}"
                )

    def test_obstacle_positions_aligned_to_grid(self):
        w = generate_day_map(1)
        for obs in w.obstacles:
            assert obs.rect.x % GRID == 0
            assert obs.rect.y % GRID == 0
            assert obs.rect.width  % GRID == 0
            assert obs.rect.height % GRID == 0

    def test_container_positions_aligned_to_grid(self):
        for night in (1, 2, 5):
            w = generate_day_map(night)
            for c in w.containers:
                assert c.rect.x % GRID == 0
                assert c.rect.y % GRID == 0

    def test_containers_not_inside_obstacles(self):
        for _ in range(8):
            w = generate_day_map(1)
            for c in w.containers:
                for o in w.obstacles:
                    assert not c.rect.colliderect(o.rect), (
                        f"Container {c.rect} overlaps obstacle {o.rect}"
                    )

    def test_containers_have_free_neighbour(self):
        """Every container must be approachable from at least one cardinal direction.

        We check reachability using actual rect collisions — the same mechanism
        the game uses — rather than reconstructing the generator's internal cell
        set, which uses a slightly wider blocked region to avoid clipping edges.
        """
        for _ in range(8):
            w = generate_day_map(1)
            for c in w.containers:
                cx, cy = c.rect.x, c.rect.y
                adjacent = [
                    pygame.Rect(cx + GRID, cy, GRID, GRID),
                    pygame.Rect(cx - GRID, cy, GRID, GRID),
                    pygame.Rect(cx, cy + GRID, GRID, GRID),
                    pygame.Rect(cx, cy - GRID, GRID, GRID),
                ]
                has_free = any(
                    not any(adj.colliderect(o.rect) for o in w.obstacles)
                    for adj in adjacent
                )
                assert has_free, (
                    f"Container at {c.rect} has no free adjacent cell"
                )

    def test_difficulty_reduces_loot_density(self):
        counts_n1 = [len(generate_day_map(1).containers) for _ in range(5)]
        counts_n5 = [len(generate_day_map(5).containers) for _ in range(5)]
        assert sum(counts_n1) >= sum(counts_n5)

    def test_no_campfire_on_day_map(self):
        assert generate_day_map(1).campfire is None


# ---------------------------------------------------------------------------
# generate_night_map
# ---------------------------------------------------------------------------

class TestGenerateNightMap:
    def test_returns_world(self):
        assert isinstance(generate_night_map(1, {}), World)

    def test_campfire_present_at_centre(self):
        w = generate_night_map(1, {})
        cf = w.campfire
        assert cf is not None
        assert cf.kind == LightSourceKind.CAMPFIRE
        assert abs(cf.pos.x - DISPLAY.width  // 2) < 1
        assert abs(cf.pos.y - DISPLAY.height // 2) < 1

    def test_obstacles_present_as_ring(self):
        assert len(generate_night_map(1, {}).obstacles) >= 4

    def test_more_obstacles_each_night(self):
        w1 = generate_night_map(1, {})
        w5 = generate_night_map(5, {})
        assert len(w5.obstacles) >= len(w1.obstacles)

    def test_no_containers_on_night_map(self):
        assert generate_night_map(1, {}).containers == []
