"""
Sprite registry for static and animated sprites loaded from Aseprite exports.

Usage
-----
Call ``SpriteRegistry.init()`` once in GameScene._init_game() before the
first frame is rendered. After that every draw() method can call
``SpriteRegistry.get()`` and ``SpriteRegistry.get_for_obstacle()`` freely —
all results are cached, so hot-path cost is a single dict lookup.

No dependency on AssetLoader: sprites are loaded directly from
``assets/sprites/`` using pygame.image.load so they keep their SRCALPHA
channel intact.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

log = logging.getLogger(__name__)

_SPRITES_DIR = Path(__file__).resolve().parent.parent / "assets" / "sprites"
_GRID_UNIT = 32  # matches WORLD.grid_unit — kept local to avoid circular import


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(filename: str) -> pygame.Surface | None:
    """Load a PNG with alpha. Returns None and logs a warning on failure."""
    path = _SPRITES_DIR / filename
    try:
        return pygame.image.load(path).convert_alpha()
    except (FileNotFoundError, pygame.error):
        log.warning("SpriteRegistry: sprite not found — %s", path)
        return None


def _desaturate(surface: pygame.Surface, brightness: float = 0.55) -> pygame.Surface:
    """
    Return a desaturated + darkened copy of *surface*, alpha preserved.

    Parameters
    ----------
    brightness:
        Multiplier applied to the gray value. 1.0 = full gray, 0.5 = dark.
        Default 0.55 gives a clearly "used / empty" look.
    """
    out = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for x in range(surface.get_width()):
        for y in range(surface.get_height()):
            r, g, b, a = surface.get_at((x, y))
            gray = int((r * 0.299 + g * 0.587 + b * 0.114) * brightness)
            out.set_at((x, y), (gray, gray, gray, a))
    return out


def _tile(base: pygame.Surface, w: int, h: int) -> pygame.Surface:
    """Tile *base* (32×32) to fill a surface of size (w, h)."""
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    gu = _GRID_UNIT
    for tx in range(0, w, gu):
        for ty in range(0, h, gu):
            out.blit(base, (tx, ty))
    return out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class SpriteRegistry:
    """
    Class-level cache — all state is shared across the process.
    Call ``init()`` once; all subsequent lookups are O(1) dict reads.
    """

    _ready: bool = False
    _surfaces: dict[str, pygame.Surface] = {}

    # ------------------------------------------------------------------
    @classmethod
    def init(cls) -> None:
        """Load and cache all known sprites. Safe to call multiple times."""
        if cls._ready:
            return

        # --- obstacles ---
        single = _load("Single_Brick_1.png")
        triple = _load("Triple_Bricks.png")

        if single is not None:
            cls._surfaces["obstacle_single"] = single

            # Pre-build tiled variants for all sizes the generator can produce
            # (1–3 grid units wide × 1–3 grid units tall = 9 combinations)
            gu = _GRID_UNIT
            for nx in range(1, 4):
                for ny in range(1, 4):
                    w, h = nx * gu, ny * gu
                    key = f"obstacle_{w}x{h}"
                    if nx == 3 and ny == 1 and triple is not None:
                        # Exact match: use the artist's triple-brick sprite
                        cls._surfaces[key] = triple
                    elif nx == 1 and ny == 1:
                        cls._surfaces[key] = single
                    else:
                        cls._surfaces[key] = _tile(single, w, h)

        if triple is not None:
            cls._surfaces["obstacle_triple"] = triple

        # --- container ---
        crate = _load("Crate.png")
        if crate is not None:
            cls._surfaces["container"] = crate
            cls._surfaces["container_opened"] = _desaturate(crate)

        # --- decoration ---
        bush = _load("The-Kust.png")
        if bush is not None:
            cls._surfaces["bush"] = bush

        cls._ready = True
        log.debug(
            "SpriteRegistry: loaded %d surfaces: %s",
            len(cls._surfaces),
            list(cls._surfaces.keys()),
        )

    # ------------------------------------------------------------------
    @classmethod
    def get(cls, name: str) -> pygame.Surface | None:
        """Return a cached surface by name, or None if not found."""
        return cls._surfaces.get(name)

    @classmethod
    def get_for_obstacle(cls, rect: pygame.Rect) -> pygame.Surface | None:
        """
        Return the correct tiled/matched sprite for an obstacle rect.
        Falls back to None (caller renders a colored placeholder).
        """
        key = f"obstacle_{rect.width}x{rect.height}"
        return cls._surfaces.get(key)

    @classmethod
    def reset(cls) -> None:
        """Clear all cached surfaces (useful between sessions / tests)."""
        cls._surfaces.clear()
        cls._ready = False
