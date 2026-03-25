"""Game-over / results screen."""
from __future__ import annotations

import pygame

from scenes.base_scene import BaseScene


class GameOverScene(BaseScene):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.nights_survived: int = 0

    def on_enter(self) -> None:
        self._font_big  = self.game.assets.font(None, 64)
        self._font_mid  = self.game.assets.font(None, 40)
        self._font_hint = self.game.assets.font(None, 28)

    def handle_event(self, event: pygame.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.manager.switch("game")
            elif event.key == pygame.K_ESCAPE:
                self.manager.switch("menu")

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((5, 5, 15))

        w, h = screen.get_size()
        title   = self._font_big.render("YOU DIED", True, (200, 60, 60))
        survived = self._font_mid.render(
            f"Nights survived: {self.nights_survived}", True, (200, 180, 120)
        )
        hint = self._font_hint.render(
            "ENTER — try again   |   ESC — main menu", True, (100, 100, 120)
        )

        screen.blit(title,    title.get_rect(center=(w // 2, h // 2 - 80)))
        screen.blit(survived, survived.get_rect(center=(w // 2, h // 2)))
        screen.blit(hint,     hint.get_rect(center=(w // 2, h // 2 + 80)))
