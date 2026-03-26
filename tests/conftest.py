"""
Shared pytest fixtures.

pygame requires a display surface to be initialised before many calls,
but CI/test environments have no display server. We patch the minimal
subset of pygame that the game modules call at import time, then provide
real pygame.Vector2 / pygame.Rect / pygame.Surface for the rest.
"""
import sys
import types
from unittest.mock import MagicMock, patch

import pygame
import pytest


# ---------------------------------------------------------------------------
# Headless pygame bootstrap (runs once per process)
# ---------------------------------------------------------------------------

def _init_headless_pygame() -> None:
    """Initialise pygame with a hidden 1×1 surface so Surface() works."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))


_init_headless_pygame()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh EventBus for each test."""
    from core.event_bus import EventBus
    return EventBus()


@pytest.fixture
def vec2():
    """Shortcut so tests can write vec2(x, y) instead of pygame.Vector2(x, y)."""
    return pygame.Vector2


@pytest.fixture
def player(bus):
    """Player at screen centre with a fresh bus."""
    from entities.player import Player
    return Player(pos=pygame.Vector2(640, 360), bus=bus)


@pytest.fixture
def basic_world():
    """Empty World with no obstacles."""
    from world.world import World
    return World()


@pytest.fixture
def world_with_campfire(basic_world):
    """World that contains a campfire at its centre."""
    from entities.light_source import LightSource, LightSourceKind
    cf = LightSource(pos=pygame.Vector2(640, 360), kind=LightSourceKind.CAMPFIRE)
    basic_world.light_sources.append(cf)
    return basic_world, cf


@pytest.fixture
def ai(bus):
    """Fresh AISystem."""
    from systems.ai_system import AISystem
    return AISystem(bus)


@pytest.fixture
def collision():
    """CollisionSystem with no obstacles loaded."""
    from systems.collision import CollisionSystem
    return CollisionSystem()


@pytest.fixture
def craft(bus):
    """CraftSystem."""
    from systems.craft_system import CraftSystem
    return CraftSystem(bus)
