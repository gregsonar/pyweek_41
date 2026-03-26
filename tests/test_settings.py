"""
Settings sanity tests.

These tests guard against accidental misconfiguration — a designer
changing one value that silently breaks a game invariant.
"""
import pytest
from settings import DISPLAY, LIGHT, MONSTER, WORLD, RECIPES, PHASE, PLAYER


class TestDisplayConfig:
    def test_size_tuple_matches_fields(self):
        assert DISPLAY.size == (DISPLAY.width, DISPLAY.height)

    def test_center_is_midpoint(self):
        cx, cy = DISPLAY.center
        assert cx == DISPLAY.width // 2
        assert cy == DISPLAY.height // 2

    def test_fps_positive(self):
        assert DISPLAY.fps > 0


class TestLightConfig:
    def test_lantern_radius_exceeds_campfire(self):
        """Lantern must reach beyond the campfire so the player's light
        is visible outside the campfire's illuminated zone."""
        assert LIGHT.lantern_base_radius > LIGHT.campfire_radius, (
            f"lantern_base_radius ({LIGHT.lantern_base_radius}) must be greater "
            f"than campfire_radius ({LIGHT.campfire_radius})"
        )

    def test_lantern_max_fuel_positive(self):
        assert LIGHT.lantern_max_fuel > 0

    def test_fuel_drain_positive(self):
        assert LIGHT.lantern_fuel_drain_per_sec > 0

    def test_recharge_rate_positive(self):
        assert LIGHT.lantern_recharge_rate > 0

    def test_recharge_slower_than_drain(self):
        """Recharge must be slower than drain so toggling on/off is a trade-off,
        not a way to get infinite fuel."""
        assert LIGHT.lantern_recharge_rate < LIGHT.lantern_fuel_drain_per_sec

    def test_campfire_max_hp_positive(self):
        assert LIGHT.campfire_max_hp > 0

    def test_darkness_alpha_night_greater_than_day(self):
        assert LIGHT.darkness_alpha_night > LIGHT.darkness_alpha_day


class TestMonsterConfig:
    def test_base_spawn_count_positive(self):
        assert MONSTER.base_spawn_count > 0

    def test_difficulty_scale_above_one(self):
        """Scale < 1 would make the game easier over time."""
        assert MONSTER.night_difficulty_scale > 1.0

    def test_alert_timeout_positive(self):
        assert MONSTER.alert_timeout > 0

    def test_light_damage_positive(self):
        assert MONSTER.light_damage_per_sec > 0

    def test_campfire_damage_positive(self):
        assert MONSTER.campfire_damage_per_sec > 0


class TestWorldConfig:
    def test_grid_unit_divides_tile_size(self):
        """grid_unit should be a factor of tile_size so snapped objects
        align with the background tile grid."""
        assert WORLD.tile_size % WORLD.grid_unit == 0

    def test_grid_unit_power_of_two(self):
        """Not strictly required but conventional for pixel-art games."""
        n = WORLD.grid_unit
        assert n > 0 and (n & (n - 1)) == 0


class TestRecipes:
    def test_all_ingredients_are_known_resources(self):
        from settings import RESOURCES
        known = {
            RESOURCES.FUEL, RESOURCES.BATTERY,
            RESOURCES.WOOD, RESOURCES.METAL, RESOURCES.CLOTH,
        }
        for result, ingredients in RECIPES.recipes.items():
            for ingredient in ingredients:
                assert ingredient in known, (
                    f"Recipe '{result}' uses unknown resource '{ingredient}'"
                )

    def test_all_quantities_positive(self):
        for result, ingredients in RECIPES.recipes.items():
            for ingredient, qty in ingredients.items():
                assert qty > 0, f"Recipe '{result}': qty for '{ingredient}' must be > 0"


class TestPhaseConfig:
    def test_day_shorter_than_night(self):
        """Day is supposed to be a short scavenging window."""
        assert PHASE.day_duration < PHASE.night_duration

    def test_transition_shorter_than_day(self):
        assert PHASE.transition_duration < PHASE.day_duration
