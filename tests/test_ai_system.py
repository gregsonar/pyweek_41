"""
Tests for systems.ai_system — FSM state transitions, spawn waves,
lantern damage, and campfire targeting.
"""

import math
from unittest.mock import MagicMock, patch

import pygame
import pytest

from entities.monster import Monster, MonsterType
from settings import DISPLAY, MONSTER
from systems.ai_system import AIState, AISystem, LightEntry


def _monster(state=AIState.WANDER, kind=MonsterType.BASIC, pos=(100, 100)):
    m = Monster.create(kind, pygame.Vector2(*pos), night=1)
    m.state = state
    m.alert_timer = MONSTER.alert_timeout
    return m


def _far_pos():
    """Position well outside the aggro radius."""
    return pygame.Vector2(9999, 9999)


class TestBeginDay:
    def test_clears_all_monsters(self, ai, basic_world):
        ai.monsters.append(_monster())
        ai.monsters.append(_monster())
        ai.begin_day()
        assert ai.monsters == []

    def test_begin_night_also_clears(self, ai, basic_world):
        ai.monsters.append(_monster())
        ai.begin_night(basic_world, night_number=2)
        assert ai.monsters == []


class TestFSMTransitions:
    """
    Drive the FSM directly via _update_fsm rather than running a full
    update() loop so tests are fast and deterministic.
    """

    def _lights_at(self, pos, radius=200.0) -> list[LightEntry]:
        return [(pygame.Vector2(*pos), radius, True)]

    def _no_lights(self) -> list[LightEntry]:
        return []

    def test_wander_to_alert_when_player_close(self, ai, basic_world):
        m = _monster(state=AIState.WANDER)
        player = MagicMock()
        player.pos = pygame.Vector2(m.pos.x + 10, m.pos.y)  # inside aggro_radius

        ai._update_fsm(
            m, dt=0.016, player=player, lights=self._no_lights(), world=basic_world
        )
        assert m.state == AIState.ALERT

    def test_wander_stays_wander_when_player_far(self, ai, basic_world):
        m = _monster(state=AIState.WANDER)
        player = MagicMock()
        player.pos = _far_pos()

        ai._update_fsm(
            m, dt=0.016, player=player, lights=self._no_lights(), world=basic_world
        )
        assert m.state == AIState.WANDER

    def test_alert_to_hunt_after_timeout_player_still_close(self, ai, basic_world):
        m = _monster(state=AIState.ALERT)
        m.alert_timer = 0.001  # about to expire
        player = MagicMock()
        player.pos = pygame.Vector2(m.pos.x + 10, m.pos.y)

        ai._update_fsm(
            m, dt=0.1, player=player, lights=self._no_lights(), world=basic_world
        )
        assert m.state == AIState.HUNT

    def test_alert_to_wander_after_timeout_player_fled(self, ai, basic_world):
        """Fix 1: ALERT → WANDER when player leaves before timer expires."""
        m = _monster(state=AIState.ALERT)
        m.alert_timer = 0.001
        player = MagicMock()
        player.pos = _far_pos()  # player ran away

        ai._update_fsm(
            m, dt=0.1, player=player, lights=self._no_lights(), world=basic_world
        )
        assert m.state == AIState.WANDER

    def test_hunt_to_flee_when_in_light(self, ai, basic_world):
        m = _monster(state=AIState.HUNT)
        player = MagicMock()
        player.pos = _far_pos()

        # Light source right on top of the monster
        lights = self._lights_at((m.pos.x, m.pos.y), radius=300)
        ai._update_fsm(m, dt=0.016, player=player, lights=lights, world=basic_world)
        assert m.state == AIState.FLEE

    def test_alert_to_flee_when_in_light(self, ai, basic_world):
        m = _monster(state=AIState.ALERT)
        player = MagicMock()
        player.pos = pygame.Vector2(m.pos.x + 5, m.pos.y)
        lights = self._lights_at((m.pos.x, m.pos.y), radius=300)

        ai._update_fsm(m, dt=0.016, player=player, lights=lights, world=basic_world)
        assert m.state == AIState.FLEE


class TestFleeAndDespawn:
    def test_flee_moves_monster_away_from_light(self, ai):
        m = _monster(state=AIState.FLEE, pos=(320, 180))
        original_pos = pygame.Vector2(m.pos)

        for _ in range(30):
            ai._do_flee(m, dt=0.1)

        # Monster should have moved
        assert m.pos.distance_to(original_pos) > 10

    def test_flee_despawns_when_offscreen(self, ai):
        """Fix 3: monster running off-screen should have hp set to 0."""
        m = _monster(state=AIState.FLEE)
        # Start near the edge and run out
        m.pos.update(DISPLAY.width - 5, DISPLAY.height // 2)
        m.speed = 999

        for _ in range(100):
            ai._do_flee(m, dt=0.1)
            if m.hp <= 0:
                break

        assert m.hp <= 0, "Monster did not despawn after fleeing off-screen"


class TestLanternDamage:
    def test_monster_takes_damage_inside_lantern(self, ai):
        """Fix 4: monsters inside the lantern radius lose HP."""
        m = _monster(pos=(320, 180))
        initial_hp = m.hp
        lantern = [(pygame.Vector2(320, 180), 999.0)]  # huge radius, monster inside

        ai._apply_lantern_damage(m, dt=1.0, lantern_sources=lantern)
        assert m.hp < initial_hp

    def test_monster_outside_lantern_unharmed(self, ai):
        m = _monster(pos=(9000, 9000))
        initial_hp = m.hp
        lantern = [(pygame.Vector2(0, 0), 10.0)]  # tiny radius far away

        ai._apply_lantern_damage(m, dt=1.0, lantern_sources=lantern)
        assert m.hp == initial_hp

    def test_damage_proportional_to_dt(self, ai):
        m1 = _monster(pos=(320, 180))
        m1.hp = 100.0
        m2 = _monster(pos=(320, 180))
        m2.hp = 100.0
        lantern = [(pygame.Vector2(320, 180), 999.0)]

        ai._apply_lantern_damage(m1, dt=1.0, lantern_sources=lantern)
        ai._apply_lantern_damage(m2, dt=2.0, lantern_sources=lantern)

        assert abs((m1.hp - m2.hp) - MONSTER.light_damage_per_sec) < 0.01


class TestLightExposureCheck:
    """Fix 6: _is_in_light must use min(lr, flee_light_radius), not lr."""

    def test_monster_in_tiny_light_not_detected_beyond_flee_radius(self, ai):
        """A very large light source should still only trigger fear within
        MONSTER.flee_light_radius, not at the source's full radius."""
        m = _monster(pos=(100, 100))
        huge_light: list[LightEntry] = [(pygame.Vector2(100, 100), 999_999.0, True)]
        # Monster is at the light source centre → should be in light
        assert ai._is_in_light(m, huge_light)

    def test_monster_outside_flee_radius_not_detected(self, ai):
        m = _monster(pos=(9000, 9000))
        nearby_light: list[LightEntry] = [(pygame.Vector2(0, 0), 999_999.0, True)]
        # Monster is far from the source; flee_light_radius caps detection
        assert not ai._is_in_light(m, nearby_light)

    def test_no_lights_returns_false(self, ai):
        m = _monster()
        assert not ai._is_in_light(m, [])


class TestSpawnWave:
    def test_begin_day_clears_monsters(self, ai, basic_world):
        ai.monsters.append(_monster())
        ai.begin_day()
        assert len(ai.monsters) == 0

    def test_offscreen_spawn_position(self, ai):
        for _ in range(50):
            pos = ai._random_offscreen_pos()
            w, h = DISPLAY.width, DISPLAY.height
            margin = MONSTER.spawn_margin
            on_screen = 0 <= pos.x <= w and 0 <= pos.y <= h
            assert not on_screen, f"Spawn inside screen: {pos}"

    def test_pick_type_night_5_includes_smasher(self, ai):
        ai._night_number = 5
        types = {ai._pick_type() for _ in range(200)}
        assert MonsterType.SMASHER in types
