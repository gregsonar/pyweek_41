"""
Tests for systems.craft_system — recipe checking and resource deduction.
"""
import pytest
from unittest.mock import MagicMock
from systems.craft_system import CraftSystem
from settings import RECIPES


def _player_with_inventory(inv: dict) -> MagicMock:
    p = MagicMock()
    p.inventory = dict(inv)
    return p


class TestCanCraft:
    def test_can_craft_with_exact_resources(self, craft):
        inv = {"wood": 2, "cloth": 1}   # torch recipe
        assert craft.can_craft("torch", inv)

    def test_can_craft_with_surplus(self, craft):
        inv = {"wood": 10, "cloth": 5}
        assert craft.can_craft("torch", inv)

    def test_cannot_craft_missing_ingredient(self, craft):
        inv = {"wood": 2}   # missing cloth
        assert not craft.can_craft("torch", inv)

    def test_cannot_craft_insufficient_quantity(self, craft):
        inv = {"wood": 1, "cloth": 1}   # need 2 wood for torch
        assert not craft.can_craft("torch", inv)

    def test_unknown_recipe_returns_false(self, craft):
        assert not craft.can_craft("nuclear_bomb", {"wood": 999})


class TestCraft:
    def test_successful_craft_deducts_resources(self, craft):
        p = _player_with_inventory({"wood": 5, "cloth": 2})
        result = craft.craft("torch", p)
        assert result is True
        assert p.inventory["wood"] == 3   # 5 - 2
        assert p.inventory["cloth"] == 1  # 2 - 1

    def test_failed_craft_does_not_deduct(self, craft):
        p = _player_with_inventory({"wood": 1})   # not enough
        result = craft.craft("torch", p)
        assert result is False
        assert p.inventory["wood"] == 1   # unchanged

    def test_craft_publishes_event(self, bus):
        from systems.craft_system import CraftSystem
        craft = CraftSystem(bus)
        received = []
        bus.subscribe("item_crafted", lambda result: received.append(result))

        p = _player_with_inventory({"wood": 2, "cloth": 1})
        craft.craft("torch", p)
        assert received == ["torch"]

    def test_craft_campfire_requires_wood_only(self, craft):
        p = _player_with_inventory({"wood": 5})
        assert craft.craft("campfire", p) is True

    def test_craft_campfire_deducts_correct_wood(self, craft):
        p = _player_with_inventory({"wood": 8})
        craft.craft("campfire", p)
        assert p.inventory["wood"] == 3   # 8 - 5


class TestAvailableRecipes:
    def test_no_resources_no_recipes(self, craft):
        assert craft.available_recipes({}) == []

    def test_returns_only_affordable_recipes(self, craft):
        inv = {"wood": 2, "cloth": 1}   # enough for torch only
        available = craft.available_recipes(inv)
        assert "torch" in available
        assert "campfire" not in available   # needs 5 wood

    def test_returns_all_when_wealthy(self, craft):
        inv = {"wood": 99, "cloth": 99, "metal": 99, "battery": 99}
        available = craft.available_recipes(inv)
        assert set(available) == set(RECIPES.recipes.keys())
