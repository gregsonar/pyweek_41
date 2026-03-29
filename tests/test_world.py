"""
Tests for world.world — World container, campfire property, geometry helpers.
"""
import pytest
import pygame
from world.world import World, Obstacle, Container, Tile
from entities.light_source import LightSource, LightSourceKind
from systems.light_system import Segment


class TestCampfireProperty:
    def test_returns_none_when_no_light_sources(self, basic_world):
        assert basic_world.campfire is None

    def test_returns_campfire_when_present(self, basic_world):
        cf = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        basic_world.light_sources.append(cf)
        assert basic_world.campfire is cf

    def test_returns_first_campfire(self, basic_world):
        cf1 = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        cf2 = LightSource(pos=pygame.Vector2(100, 0), kind=LightSourceKind.CAMPFIRE)
        basic_world.light_sources.extend([cf1, cf2])
        assert basic_world.campfire is cf1

    def test_ignores_non_campfire_sources(self, basic_world):
        torch = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.TORCH)
        basic_world.light_sources.append(torch)
        assert basic_world.campfire is None


class TestObstacleGeometry:
    def test_obstacle_rects_returns_list(self, basic_world):
        basic_world.obstacles.append(Obstacle(rect=pygame.Rect(0, 0, 64, 64)))
        rects = basic_world.obstacle_rects()
        assert len(rects) == 1
        assert isinstance(rects[0], pygame.Rect)

    def test_obstacle_segments_count(self, basic_world):
        """Each rect produces 4 segments."""
        basic_world.obstacles.append(Obstacle(rect=pygame.Rect(0, 0, 64, 64)))
        segs = basic_world.obstacle_segments()
        assert len(segs) == 4

    def test_obstacle_segments_are_segment_instances(self, basic_world):
        basic_world.obstacles.append(Obstacle(rect=pygame.Rect(0, 0, 32, 32)))
        for seg in basic_world.obstacle_segments():
            assert isinstance(seg, Segment)

    def test_multiple_obstacles_multiply_segments(self, basic_world):
        basic_world.obstacles.append(Obstacle(rect=pygame.Rect(0, 0, 32, 32)))
        basic_world.obstacles.append(Obstacle(rect=pygame.Rect(100, 0, 32, 32)))
        assert len(basic_world.obstacle_segments()) == 8


class TestInteractables:
    def test_containers_are_interactable(self, basic_world):
        c = Container(
            pos=pygame.Vector2(100, 100),
            rect=pygame.Rect(84, 84, 32, 32),
            loot={"wood": 2},
        )
        basic_world.containers.append(c)
        assert c in basic_world.interactables

    def test_container_interact_gives_loot(self, basic_world, player, bus):
        c = Container(
            pos=pygame.Vector2(100, 100),
            rect=pygame.Rect(84, 84, 32, 32),
            loot={"wood": 3, "metal": 1},
        )
        c.interact(player)
        assert player.inventory.get("wood") == 3
        assert player.inventory.get("metal") == 1

    def test_container_interact_twice_gives_loot_once(self, basic_world, player, bus):
        c = Container(
            pos=pygame.Vector2(100, 100),
            rect=pygame.Rect(84, 84, 32, 32),
            loot={"wood": 3},
        )
        c.interact(player)
        c.interact(player)
        assert player.inventory.get("wood") == 3   # not 6


class TestWorldUpdate:
    def test_update_drains_campfire_fuel(self, world_with_campfire):
        world, cf = world_with_campfire
        initial_fuel = cf.fuel
        world.update(1.0)
        assert cf.fuel < initial_fuel
