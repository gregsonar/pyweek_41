"""
Craft and build system.

Recipes are defined in ``settings.CraftRecipes`` — no logic here is
hardcoded to a specific item name.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.event_bus import EventBus, Events
from settings       import RECIPES

if TYPE_CHECKING:
    from entities.player import Player

log = logging.getLogger(__name__)


class CraftSystem:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    # ------------------------------------------------------------------
    def can_craft(self, result: str, inventory: dict[str, int]) -> bool:
        recipe = RECIPES.recipes.get(result)
        if recipe is None:
            return False
        return all(inventory.get(ingredient, 0) >= qty for ingredient, qty in recipe.items())

    def craft(self, result: str, player: Player) -> bool:
        """
        Attempt to craft *result* using player's inventory.

        Returns True on success.
        """
        if not self.can_craft(result, player.inventory):
            log.debug("CraftSystem: cannot craft %r — missing resources", result)
            return False

        recipe = RECIPES.recipes[result]
        for ingredient, qty in recipe.items():
            player.inventory[ingredient] = player.inventory.get(ingredient, 0) - qty

        self._bus.publish(Events.ITEM_CRAFTED, result=result)
        log.info("Crafted: %s", result)
        return True

    def available_recipes(self, inventory: dict[str, int]) -> list[str]:
        """Return the names of all craftable items given current inventory."""
        return [r for r in RECIPES.recipes if self.can_craft(r, inventory)]
