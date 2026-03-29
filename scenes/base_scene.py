"""Abstract base for all scenes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from core.game         import Game
    from core.scene_manager import SceneManager


class BaseScene(ABC):
    """
    All scenes receive the ``Game`` instance for access to shared resources.
    ``manager`` is injected by ``SceneManager.register()``.
    """

    def __init__(self, game: Game) -> None:
        self.game: Game = game
        self.manager: SceneManager  # set by SceneManager

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    def on_enter(self) -> None:
        """Called once when this scene becomes active."""

    def on_exit(self) -> None:
        """Called once just before this scene is replaced."""

    # ------------------------------------------------------------------
    # Per-frame
    # ------------------------------------------------------------------
    @abstractmethod
    def handle_event(self, event: pygame.Event) -> None: ...

    @abstractmethod
    def update(self, dt: float) -> None: ...

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None: ...
