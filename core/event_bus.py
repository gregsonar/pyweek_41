"""
Lightweight synchronous pub/sub event bus.

Usage
-----
    bus = EventBus()

    def on_fire_out(campfire_id: int) -> None:
        ...

    bus.subscribe("campfire_extinguished", on_fire_out)
    bus.publish("campfire_extinguished", campfire_id=42)
    bus.unsubscribe("campfire_extinguished", on_fire_out)

Events are dispatched synchronously in subscription order.
No thread-safety guarantees — call only from the main thread.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger(__name__)

Callback = Callable[..., None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callback]] = defaultdict(list)

    # ------------------------------------------------------------------
    def subscribe(self, event: str, callback: Callback) -> None:
        if callback not in self._listeners[event]:
            self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callback) -> None:
        try:
            self._listeners[event].remove(callback)
        except ValueError:
            log.warning("EventBus.unsubscribe: %r not subscribed to %r", callback, event)

    def publish(self, event: str, **kwargs: Any) -> None:
        for cb in list(self._listeners[event]):   # copy: cb may unsubscribe itself
            try:
                cb(**kwargs)
            except Exception:
                log.exception("EventBus: unhandled exception in listener %r for event %r", cb, event)

    def clear(self, event: str | None = None) -> None:
        """Remove all listeners for *event*, or all events if None."""
        if event is None:
            self._listeners.clear()
        else:
            self._listeners.pop(event, None)


# ---------------------------------------------------------------------------
# Well-known event names — use these constants instead of raw strings
# so typos are caught at import time.
# ---------------------------------------------------------------------------
class Events:
    # Phase transitions
    PHASE_DAY_START   = "phase_day_start"
    PHASE_NIGHT_START = "phase_night_start"
    PHASE_TRANSITION  = "phase_transition"     # kwargs: to_phase: str

    # Light
    CAMPFIRE_LIT        = "campfire_lit"
    CAMPFIRE_EXTINGUISHED = "campfire_extinguished"
    LANTERN_FUEL_LOW    = "lantern_fuel_low"   # kwargs: fuel: float
    LANTERN_EMPTY       = "lantern_empty"

    # Combat / survival
    PLAYER_DAMAGED      = "player_damaged"     # kwargs: hp_remaining: int
    PLAYER_DIED         = "player_died"
    MONSTER_KILLED      = "monster_killed"     # kwargs: monster_type: str
    WAVE_SPAWNED        = "wave_spawned"       # kwargs: count: int

    # Resource / craft
    ITEM_PICKED_UP      = "item_picked_up"     # kwargs: item: str, qty: int
    ITEM_CRAFTED        = "item_crafted"       # kwargs: result: str
    STRUCTURE_BUILT     = "structure_built"    # kwargs: kind: str

    # Scene
    SCENE_CHANGE        = "scene_change"       # kwargs: name: str
    GAME_OVER           = "game_over"          # kwargs: nights_survived: int
