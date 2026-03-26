"""Main menu scene."""

from __future__ import annotations

import pygame

from scenes.base_scene import BaseScene


class MenuScene(BaseScene):
    def on_enter(self) -> None:
        self._font_title = self.game.assets.font(None, 72)
        self._font_hint = self.game.assets.font(None, 32)

    def handle_event(self, event: pygame.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.manager.switch("game")
            elif event.key == pygame.K_ESCAPE:
                self.game.quit()

        if event.type == pygame.MOUSEBUTTONDOWN:
            self.manager.switch("game")

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((10, 10, 25))

        w, h = screen.get_size()
        title = self._font_title.render(
            "Working Title: INTO THE DARK", True, (220, 200, 140)
        )
        hint = self._font_hint.render(
            "Press ENTER or click to begin survival", True, (140, 140, 160)
        )

        screen.blit(title, title.get_rect(center=(w // 2, h // 2 - 60)))
        screen.blit(hint, hint.get_rect(center=(w // 2, h // 2 + 40)))
