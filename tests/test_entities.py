"""
Tests for entities: Player, Monster, LightSource.
"""
import pytest
import pygame
from unittest.mock import MagicMock, patch

from entities.player       import Player
from entities.monster      import Monster, MonsterType
from entities.light_source import LightSource, LightSourceKind
from settings import LIGHT, MONSTER, PLAYER


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class TestPlayerInputLock:
    def test_locked_player_ignores_keydown(self, player):
        player.input_locked = True
        player.handle_keydown(pygame.K_f)   # F toggles lantern
        assert player.lantern_on is True    # unchanged

    def test_unlocked_player_responds_to_keydown(self, player):
        player.input_locked = False
        player.lantern_on = True
        player.handle_keydown(pygame.K_f)
        assert player.lantern_on is False

    def test_keyup_ignored_when_locked(self, player):
        player.input_locked = True
        player._sprinting = True
        player.handle_keyup(pygame.K_LSHIFT)
        assert player._sprinting is True   # unchanged


class TestLanternFuel:
    def test_fuel_drains_at_night(self, player, basic_world):
        from systems.collision import CollisionSystem
        col = CollisionSystem()
        col.load_world(basic_world)
        player.lantern_on  = True
        player.lantern_fuel = LIGHT.lantern_max_fuel

        player.update(1.0, basic_world, col, is_night=True)

        expected = LIGHT.lantern_max_fuel - LIGHT.lantern_fuel_drain_per_sec
        assert abs(player.lantern_fuel - expected) < 0.01

    def test_fuel_does_not_drain_during_day(self, player, basic_world):
        from systems.collision import CollisionSystem
        col = CollisionSystem()
        col.load_world(basic_world)
        player.lantern_on  = True
        player.lantern_fuel = 50.0

        player.update(1.0, basic_world, col, is_night=False)
        assert player.lantern_fuel == 50.0

    def test_fuel_recharges_when_lantern_off(self, player, basic_world):
        from systems.collision import CollisionSystem
        col = CollisionSystem()
        col.load_world(basic_world)
        player.lantern_on  = False
        player.lantern_fuel = 0.0

        player.update(1.0, basic_world, col, is_night=True)

        if LIGHT.lantern_recharge_enabled:
            assert player.lantern_fuel > 0
        else:
            assert player.lantern_fuel == 0.0

    def test_fuel_capped_at_maximum(self, player, basic_world):
        from systems.collision import CollisionSystem
        col = CollisionSystem()
        col.load_world(basic_world)
        player.lantern_on  = False
        player.lantern_fuel = LIGHT.lantern_max_fuel

        player.update(10.0, basic_world, col, is_night=True)
        assert player.lantern_fuel <= LIGHT.lantern_max_fuel

    def test_fuel_never_goes_below_zero(self, player, basic_world):
        from systems.collision import CollisionSystem
        col = CollisionSystem()
        col.load_world(basic_world)
        player.lantern_on  = True
        player.lantern_fuel = 0.01

        player.update(10.0, basic_world, col, is_night=True)
        assert player.lantern_fuel >= 0.0


class TestPlayerDamageAndDeath:
    def test_take_damage_reduces_hp(self, player, bus):
        player.hp = 3
        player.take_damage(1)
        assert player.hp == 2

    def test_death_publishes_event(self, player, bus):
        from core.event_bus import Events
        died = []
        bus.subscribe(Events.PLAYER_DIED, lambda: died.append(True))
        player.hp = 1
        player.take_damage(1)
        assert died == [True]

    def test_no_death_event_if_hp_remains(self, player, bus):
        from core.event_bus import Events
        died = []
        bus.subscribe(Events.PLAYER_DIED, lambda: died.append(True))
        player.hp = 3
        player.take_damage(1)
        assert died == []


class TestPlayerBoundary:
    def test_player_clamped_inside_screen(self, player, basic_world):
        """Player must not leave the screen after update, even with huge velocity."""
        from systems.collision import CollisionSystem
        from settings import DISPLAY
        col = CollisionSystem()
        col.load_world(basic_world)

        # Force position way off screen
        player.rect.topleft = (-9999, -9999)
        player.pos.update(-9999, -9999)

        player.input_locked = True   # disable movement so only clamp applies
        player.update(0.016, basic_world, col, is_night=False)

        assert player.rect.left   >= 0
        assert player.rect.top    >= 0
        assert player.rect.right  <= DISPLAY.width
        assert player.rect.bottom <= DISPLAY.height


class TestPlayerInventory:
    def test_add_item_increases_count(self, player, bus):
        player.add_item("wood", 3)
        assert player.inventory["wood"] == 3

    def test_add_item_accumulates(self, player, bus):
        player.add_item("wood", 2)
        player.add_item("wood", 5)
        assert player.inventory["wood"] == 7

    def test_add_item_publishes_event(self, player, bus):
        from core.event_bus import Events
        received = []
        bus.subscribe(Events.ITEM_PICKED_UP, lambda item, qty: received.append((item, qty)))
        player.add_item("metal", 2)
        assert received == [("metal", 2)]


# ---------------------------------------------------------------------------
# Monster
# ---------------------------------------------------------------------------

class TestMonsterCreation:
    @pytest.mark.parametrize("kind", list(MonsterType))
    def test_create_all_types(self, kind):
        m = Monster.create(kind, pygame.Vector2(0, 0), night=1)
        assert m.hp > 0
        assert m.speed > 0
        assert m.kind == kind

    def test_difficulty_scales_speed(self):
        m1 = Monster.create(MonsterType.BASIC, pygame.Vector2(0, 0), night=1)
        m3 = Monster.create(MonsterType.BASIC, pygame.Vector2(0, 0), night=3)
        assert m3.speed > m1.speed

    def test_smasher_targets_campfire(self):
        m = Monster.create(MonsterType.SMASHER, pygame.Vector2(0, 0), night=1)
        assert m.targets_campfire is True

    def test_basic_does_not_target_campfire(self):
        m = Monster.create(MonsterType.BASIC, pygame.Vector2(0, 0), night=1)
        assert m.targets_campfire is False

    def test_stalker_does_not_target_campfire(self):
        m = Monster.create(MonsterType.STALKER, pygame.Vector2(0, 0), night=1)
        assert m.targets_campfire is False


class TestMonsterHp:
    def test_hp_starts_at_max(self):
        m = Monster.create(MonsterType.BASIC, pygame.Vector2(0, 0), 1)
        assert m.hp == m.max_hp

    def test_hp_can_reach_zero(self):
        m = Monster.create(MonsterType.BASIC, pygame.Vector2(0, 0), 1)
        m.hp = 0
        assert m.hp == 0


# ---------------------------------------------------------------------------
# LightSource
# ---------------------------------------------------------------------------

class TestLightSourceFuel:
    def test_campfire_starts_active(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        assert ls.active

    def test_fuel_drains_over_time(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.TORCH)
        initial = ls.fuel
        ls.update(1.0)
        assert ls.fuel < initial

    def test_fuel_never_below_zero(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CANDLE)
        ls.update(10_000.0)
        assert ls.fuel >= 0.0

    def test_empty_fuel_deactivates(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.TORCH)
        ls.fuel = 0.0
        assert not ls.active

    def test_refuel_caps_at_max(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        ls.fuel = ls.max_fuel - 1
        ls.refuel(9999)
        assert ls.fuel == ls.max_fuel


class TestCampfireHp:
    def test_campfire_has_positive_max_hp(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        assert ls.max_hp > 0

    def test_other_types_have_no_hp(self):
        for kind in (LightSourceKind.TORCH, LightSourceKind.LANTERN, LightSourceKind.CANDLE):
            ls = LightSource(pos=pygame.Vector2(0, 0), kind=kind)
            assert ls.max_hp < 0, f"{kind} should have no structural HP"

    def test_damage_reduces_hp(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        ls.take_damage(10)
        assert ls.hp == ls.max_hp - 10

    def test_hp_reaches_zero_deactivates_campfire(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        ls.take_damage(ls.max_hp)
        assert not ls.active

    def test_hp_never_below_zero(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        ls.take_damage(ls.max_hp * 10)
        assert ls.hp >= 0.0

    def test_repair_caps_at_max(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        ls.take_damage(20)
        ls.repair(9999)
        assert ls.hp == ls.max_hp

    def test_non_campfire_ignores_damage(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.TORCH)
        ls.take_damage(9999)
        assert ls.active   # still active — damage is ignored for non-campfires


class TestLightSourceIntensity:
    def test_full_fuel_is_full_intensity(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        assert abs(ls.intensity - 1.0) < 1e-6

    def test_half_fuel_is_half_intensity(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.CAMPFIRE)
        ls.fuel = ls.max_fuel / 2
        assert abs(ls.intensity - 0.5) < 1e-6

    def test_intensity_bounds(self):
        ls = LightSource(pos=pygame.Vector2(0, 0), kind=LightSourceKind.TORCH)
        assert 0.0 <= ls.intensity <= 1.0
