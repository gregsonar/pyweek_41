"""
Tests for systems.collision — AABB spatial grid and movement resolution.
"""
import pytest
import pygame
from systems.collision import CollisionSystem
from world.world import World, Obstacle


def _world_with_wall(x, y, w, h) -> World:
    world = World()
    world.obstacles.append(Obstacle(rect=pygame.Rect(x, y, w, h)))
    return world


class TestLoadWorld:
    def test_load_empty_world(self, collision):
        world = World()
        collision.load_world(world)   # must not raise

    def test_load_world_with_obstacles(self, collision):
        world = _world_with_wall(100, 100, 64, 64)
        collision.load_world(world)
        assert collision.is_solid_at((132, 132))

    def test_clear_space_not_solid(self, collision):
        world = _world_with_wall(100, 100, 64, 64)
        collision.load_world(world)
        assert not collision.is_solid_at((0, 0))


class TestMove:
    def test_free_movement_in_open_space(self, collision):
        world = World()
        collision.load_world(world)
        rect = pygame.Rect(0, 0, 32, 32)
        new_rect, collided = collision.move(rect, pygame.Vector2(50, 30))
        assert not collided
        assert new_rect.x == 50
        assert new_rect.y == 30

    def test_blocked_by_wall(self, collision):
        """Moving into a wall should be stopped or deflected."""
        world = _world_with_wall(200, 0, 64, 400)
        collision.load_world(world)
        rect = pygame.Rect(100, 100, 32, 32)
        # Use velocity just large enough to reach the wall but not tunnel through it
        new_rect, collided = collision.move(rect, pygame.Vector2(80, 0))
        assert collided
        assert new_rect.right <= 200

    def test_slide_along_wall_horizontally(self, collision):
        """When blocked horizontally, vertical movement should still work."""
        world = _world_with_wall(200, 0, 64, 400)
        collision.load_world(world)
        rect = pygame.Rect(168, 100, 32, 32)   # tight against wall
        new_rect, _ = collision.move(rect, pygame.Vector2(100, 40))
        # Should slide: y moved even if x didn't
        assert new_rect.y > rect.y

    def test_zero_velocity_no_movement(self, collision):
        world = World()
        collision.load_world(world)
        rect = pygame.Rect(50, 50, 32, 32)
        new_rect, collided = collision.move(rect, pygame.Vector2(0, 0))
        assert not collided
        assert new_rect == rect


class TestSpatialGrid:
    def test_multiple_obstacles_all_solid(self, collision):
        world = World()
        positions = [(0, 0), (200, 200), (400, 100)]
        for x, y in positions:
            world.obstacles.append(Obstacle(rect=pygame.Rect(x, y, 32, 32)))
        collision.load_world(world)

        for x, y in positions:
            assert collision.is_solid_at((x + 10, y + 10)), (
                f"Expected solid at ({x+10},{y+10})"
            )

    def test_reload_clears_old_data(self, collision):
        world_a = _world_with_wall(0, 0, 64, 64)
        collision.load_world(world_a)
        assert collision.is_solid_at((10, 10))

        world_b = World()   # empty
        collision.load_world(world_b)
        assert not collision.is_solid_at((10, 10))
