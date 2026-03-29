"""
Top-level Game object. Owns the pygame window, the clock, and all shared
singletons (asset loader, event bus, scene manager).

Nothing outside this module should call ``pygame.init()``.
"""

from __future__ import annotations

import logging
import sys

import pygame

from core.asset_loader import AssetLoader
from core.audio_manager import AudioManager
from core.event_bus import EventBus
from core.scene_manager import SceneManager
from settings import DISPLAY

log = logging.getLogger(__name__)


class Game:
    """
    Instantiate once, then call ``run()``.

    Example
    -------
        game = Game()
        game.scenes.register("menu", MenuScene(game))
        game.scenes.register("game", GameScene(game))
        game.scenes.switch("menu")
        game.run()
    """

    def __init__(self) -> None:
        pygame.init()
        pygame.mixer.init()

        self.screen = pygame.display.set_mode(
            DISPLAY.size,
            pygame.SCALED,
            vsync=int(DISPLAY.vsync),
        )
        pygame.display.set_caption(DISPLAY.title)

        self.clock = pygame.time.Clock()
        self.assets = AssetLoader()
        self.bus = EventBus()
        self.scenes = SceneManager()
        self.audio = AudioManager(self.bus)

        self.running = False

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.running = True
        log.info("Game loop started")

        while self.running:
            dt = self.clock.tick(DISPLAY.fps) / 1000.0
            # Cap dt to avoid spiral-of-death after focus loss / debugger pause
            dt = min(dt, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F4:
                    if event.mod & pygame.KMOD_ALT:
                        self.quit()
                else:
                    self.scenes.handle_event(event)

            self.scenes.update(dt)
            self.scenes.draw(self.screen)
            pygame.display.flip()

        pygame.quit()
        sys.exit(0)

    def quit(self) -> None:
        log.info("Quit requested")
        self.running = False
