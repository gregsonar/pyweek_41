"""
Heads-up display.

Drawn last (on top of everything). Stateless — receives all values as
arguments to ``draw()`` so it has zero coupling to game state.

Exposes ``mute_button_rect`` so GameScene can hit-test mouse clicks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from core.asset_loader import AssetLoader
from settings import DISPLAY, LIGHT, PHASE

if TYPE_CHECKING:
    from entities.player import Player


_BAR_W = 120
_BAR_H = 10
_MARGIN = 16


class HUD:
    def __init__(self, assets: AssetLoader) -> None:
        self._font_big = assets.font(None, 28)
        self._font_mid = assets.font(None, 22)
        self._font_small = assets.font(None, 18)
        self._font_mute = assets.font(None, 20)

        # Rect is updated every draw() call — used for click detection
        self.mute_button_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)

    # ------------------------------------------------------------------
    def draw(
        self,
        screen: pygame.Surface,
        *,
        phase: str,
        time_left: float,
        night: int,
        player: Player,
        muted: bool,
    ) -> None:
        w = DISPLAY.width

        # Phase + timer — top centre
        is_night = "NIGHT" in phase
        phase_color = (200, 160, 80) if not is_night else (120, 160, 220)
        label = f"Night {night}  —  {'DAY' if not is_night else 'NIGHT'}"
        label_surf = self._font_big.render(label, True, phase_color)
        screen.blit(label_surf, label_surf.get_rect(centerx=w // 2, top=_MARGIN))

        timer_surf = self._font_mid.render(f"{time_left:.0f}s", True, (200, 200, 200))
        screen.blit(timer_surf, timer_surf.get_rect(centerx=w // 2, top=_MARGIN + 30))

        # HP — top left
        hp_label = self._font_small.render("HP", True, (180, 80, 80))
        screen.blit(hp_label, (_MARGIN, _MARGIN))
        for i in range(player.hp):
            pygame.draw.circle(
                screen, (220, 60, 60), (_MARGIN + 30 + i * 18, _MARGIN + 8), 7
            )

        # Lantern fuel bar — below HP
        self._draw_bar(
            screen,
            x=_MARGIN,
            y=_MARGIN + 28,
            value=player.lantern_fuel,
            maximum=LIGHT.lantern_max_fuel,
            label="Lantern",
            color_full=(220, 200, 100),
            color_empty=(80, 70, 30),
        )

        # Inventory summary — bottom left
        if player.inventory:
            self._draw_inventory(screen, player.inventory)

        # Controls hint (night) — bottom right
        if is_night:
            hint = "F — toggle lantern   E — interact"
            hint_surf = self._font_small.render(hint, True, (100, 100, 120))
            screen.blit(
                hint_surf,
                hint_surf.get_rect(right=w - _MARGIN, bottom=DISPLAY.height - _MARGIN),
            )

        # Mute button — top right
        self._draw_mute_button(screen, muted)

    # ------------------------------------------------------------------
    def _draw_mute_button(self, screen: pygame.Surface, muted: bool) -> None:
        label = "Shush!" if not muted else "Music!"
        color = (160, 160, 140) if not muted else (120, 120, 100)
        surf = self._font_mute.render(label, True, color)
        rect = surf.get_rect(right=DISPLAY.width - _MARGIN, top=_MARGIN)

        # Subtle background pill
        pad = 6
        bg_rect = rect.inflate(pad * 2, pad)
        pygame.draw.rect(screen, (30, 30, 35), bg_rect, border_radius=6)
        pygame.draw.rect(screen, (60, 60, 70), bg_rect, 1, border_radius=6)

        screen.blit(surf, rect)
        self.mute_button_rect = bg_rect

    # ------------------------------------------------------------------
    def _draw_bar(
        self,
        screen: pygame.Surface,
        x: int,
        y: int,
        value: float,
        maximum: float,
        label: str,
        color_full: tuple[int, int, int],
        color_empty: tuple[int, int, int],
    ) -> None:
        label_surf = self._font_small.render(label, True, (160, 160, 160))
        screen.blit(label_surf, (x, y))

        bar_y = y + 16
        bg = pygame.Rect(x, bar_y, _BAR_W, _BAR_H)
        fill_w = int(_BAR_W * max(0.0, value / maximum))
        fill = pygame.Rect(x, bar_y, fill_w, _BAR_H)

        pygame.draw.rect(screen, (40, 40, 45), bg, border_radius=3)
        if fill_w > 0:
            pygame.draw.rect(screen, color_full, fill, border_radius=3)
        pygame.draw.rect(screen, (80, 80, 90), bg, 1, border_radius=3)

    def _draw_inventory(
        self,
        screen: pygame.Surface,
        inventory: dict[str, int],
    ) -> None:
        x = _MARGIN
        y = DISPLAY.height - _MARGIN - len(inventory) * 18
        for item, qty in sorted(inventory.items()):
            surf = self._font_small.render(f"{item}: {qty}", True, (160, 160, 130))
            screen.blit(surf, (x, y))
            y += 18
