"""
Centralised asset loader with lazy loading and in-memory cache.

All paths are relative to the project root.
Images are converted to the display format on first load for blitting speed.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"


class AssetLoader:
    def __init__(self) -> None:
        self._images: dict[str, pygame.Surface] = {}
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._fonts:  dict[tuple[str, int], pygame.font.Font] = {}

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------
    def image(self, path: str, *, alpha: bool = True) -> pygame.Surface:
        """
        Load and cache a surface.

        Parameters
        ----------
        path:
            Relative to ``assets/``, e.g. ``"sprites/player.png"``.
        alpha:
            If True use ``convert_alpha()`` (per-pixel alpha), otherwise
            ``convert()`` (faster for opaque sprites).
        """
        if path not in self._images:
            full = _ASSETS_ROOT / path
            try:
                surf = pygame.image.load(full)
                self._images[path] = surf.convert_alpha() if alpha else surf.convert()
            except FileNotFoundError:
                log.warning("AssetLoader: image not found — %s (using placeholder)", full)
                self._images[path] = self._make_placeholder(32, 32)
        return self._images[path]

    def spritesheet_region(
        self,
        path: str,
        rect: pygame.Rect,
        *,
        alpha: bool = True,
    ) -> pygame.Surface:
        """Slice a region out of a spritesheet."""
        sheet = self.image(path, alpha=alpha)
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        surface.blit(sheet, (0, 0), rect)
        return surface

    # ------------------------------------------------------------------
    # Sounds
    # ------------------------------------------------------------------
    def sound(self, path: str) -> pygame.mixer.Sound | None:
        if path not in self._sounds:
            full = _ASSETS_ROOT / path
            try:
                self._sounds[path] = pygame.mixer.Sound(full)
            except (FileNotFoundError, pygame.error):
                log.warning("AssetLoader: sound not found — %s", full)
                return None
        return self._sounds[path]

    def play(self, path: str, *, volume: float = 1.0, loops: int = 0) -> None:
        snd = self.sound(path)
        if snd is not None:
            snd.set_volume(volume)
            snd.play(loops=loops)

    # ------------------------------------------------------------------
    # Fonts
    # ------------------------------------------------------------------
    def font(self, path: str | None, size: int) -> pygame.font.Font:
        """
        Parameters
        ----------
        path:
            Relative to ``assets/fonts/``, or None for the pygame default.
        """
        key = (path or "", size)
        if key not in self._fonts:
            if path is None:
                self._fonts[key] = pygame.font.Font(None, size)
            else:
                full = _ASSETS_ROOT / "fonts" / path
                try:
                    self._fonts[key] = pygame.font.Font(full, size)
                except FileNotFoundError:
                    log.warning("AssetLoader: font not found — %s, falling back to default", full)
                    self._fonts[key] = pygame.font.Font(None, size)
        return self._fonts[key]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _make_placeholder(w: int, h: int) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((255, 0, 255, 200))
        pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
        return surf

    def unload_all(self) -> None:
        self._images.clear()
        self._sounds.clear()
        self._fonts.clear()
