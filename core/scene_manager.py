"""
Scene manager — owns the active scene stack and routes pygame events.

Scenes are registered by name. Switching is deferred to the start of the
next frame to avoid mutating the stack mid-update.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from scenes.base_scene import BaseScene

log = logging.getLogger(__name__)


class SceneManager:
    def __init__(self) -> None:
        self._scenes: dict[str, BaseScene] = {}
        self._active: BaseScene | None = None
        self._pending_switch: str | None = None

    # ------------------------------------------------------------------
    def register(self, name: str, scene: BaseScene) -> None:
        self._scenes[name] = scene
        scene.manager = self

    def switch(self, name: str) -> None:
        """Request a scene switch. Applied at the start of the next frame."""
        if name not in self._scenes:
            raise KeyError(f"SceneManager: no scene registered as {name!r}")
        self._pending_switch = name

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.Event) -> None:
        if self._active:
            self._active.handle_event(event)

    def update(self, dt: float) -> None:
        self._apply_pending_switch()
        if self._active:
            self._active.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        if self._active:
            self._active.draw(screen)

    # ------------------------------------------------------------------
    def _apply_pending_switch(self) -> None:
        if self._pending_switch is None:
            return
        name = self._pending_switch
        self._pending_switch = None

        if self._active:
            self._active.on_exit()
            log.debug("Scene exit: %s", type(self._active).__name__)

        self._active = self._scenes[name]
        self._active.on_enter()
        log.debug("Scene enter: %s", type(self._active).__name__)
