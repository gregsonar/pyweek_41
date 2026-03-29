"""
Sprite registry and animation for Aseprite-exported sprites.

Usage
-----
    # Once at startup:
    SpriteRegistry.init()

    # In Monster.__init__:
    self.animated_sprite = SpriteRegistry.get_animated("monster_basic")

    # In Monster.update_animation(dt):
    if self.animated_sprite:
        self.animated_sprite.update(dt)

    # In Monster.draw(screen):
    if self.animated_sprite:
        frame = self.animated_sprite.current_frame(self.facing_angle)
        screen.blit(frame, rect.topleft)
"""

from __future__ import annotations

import json
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


def _load_json(filename: str) -> dict | None:
    path = _SPRITES_DIR / filename
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log.warning("SpriteRegistry: JSON not found — %s", path)
        return None


def _desaturate(surface: pygame.Surface, brightness: float = 0.55) -> pygame.Surface:
    """Return a desaturated + darkened copy, alpha preserved."""
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
    for tx in range(0, w, _GRID_UNIT):
        for ty in range(0, h, _GRID_UNIT):
            out.blit(base, (tx, ty))
    return out


def _slice_frames(
    sheet: pygame.Surface, meta: dict
) -> list[tuple[pygame.Surface, float]]:
    """
    Parse Aseprite JSON and return a list of (surface, duration_sec) tuples
    in frame order.

    Frame order follows the insertion order of ``meta["frames"]``, which
    matches the visual left-to-right order in a horizontal sprite sheet.
    """
    frames: list[tuple[pygame.Surface, float]] = []
    for frame_data in meta["frames"].values():
        f = frame_data["frame"]
        dur = frame_data.get("duration", 100) / 1000.0  # ms → seconds
        surf = pygame.Surface((f["w"], f["h"]), pygame.SRCALPHA)
        surf.blit(sheet, (0, 0), pygame.Rect(f["x"], f["y"], f["w"], f["h"]))
        frames.append((surf, dur))
    return frames


# ---------------------------------------------------------------------------
# AnimatedSprite
# ---------------------------------------------------------------------------


class AnimatedSprite:
    """
    Per-instance animation state for a single sprite strip.

    The source sprite is assumed to face **up** (north).
    ``current_frame(angle)`` returns the current frame rotated to face
    the requested direction.

    Rotation convention (matches pygame.transform.rotate):
        0°   → faces up    (north, default)
        90°  → faces left  (west)
        180° → faces down  (south)
        270° → faces right (east)   i.e. -90° clockwise

    Parameters
    ----------
    frames:
        List of (surface, duration_sec) pairs produced by _slice_frames.
    """

    def __init__(self, frames: list[tuple[pygame.Surface, float]]) -> None:
        self._frames = frames
        self._index: int = 0
        self._elapsed: float = 0.0
        # Rotation cache: angle → rotated surface for the current frame index.
        # Invalidated whenever _index changes.
        self._rot_cache: dict[float, pygame.Surface] = {}

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Advance the animation by *dt* seconds."""
        _, duration = self._frames[self._index]
        self._elapsed += dt
        if self._elapsed >= duration:
            self._elapsed -= duration
            new_index = (self._index + 1) % len(self._frames)
            if new_index != self._index:
                self._index = new_index
                self._rot_cache.clear()

    def current_frame(self, angle: float = 0.0) -> pygame.Surface:
        """
        Return the current frame rotated by *angle* degrees (CCW).

        Results are cached per angle so rotate() is only called when the
        frame or the direction changes.
        """
        if angle not in self._rot_cache:
            surf = self._frames[self._index][0]
            self._rot_cache[angle] = (
                pygame.transform.rotate(surf, angle) if angle != 0.0 else surf
            )
        return self._rot_cache[angle]

    def reset(self) -> None:
        self._index = 0
        self._elapsed = 0.0
        self._rot_cache.clear()


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
    _anim_frames: dict[str, list[tuple[pygame.Surface, float]]] = {}

    # ------------------------------------------------------------------
    @classmethod
    def init(cls) -> None:
        """Load and cache all sprites. Safe to call multiple times."""
        if cls._ready:
            return

        # --- obstacles ---
        single = _load("Single_Brick_1.png")
        triple = _load("Triple_Bricks.png")

        if single is not None:
            cls._surfaces["obstacle_single"] = single
            gu = _GRID_UNIT
            for nx in range(1, 4):
                for ny in range(1, 4):
                    w, h = nx * gu, ny * gu
                    key = f"obstacle_{w}x{h}"
                    if nx == 3 and ny == 1 and triple is not None:
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

        # --- animated monsters ---
        cls._load_animation("monster_basic", "Begun.png", "Begun.json")
        cls._load_animation("monster_stalker", "Klyaksa.png", "Klyaksa.json")
        cls._load_animation("monster_smasher", "Shadow_fiend.png", "Shadow_fiend.json")

        cls._ready = True
        log.debug(
            "SpriteRegistry: %d surfaces, %d animations",
            len(cls._surfaces),
            len(cls._anim_frames),
        )

    # ------------------------------------------------------------------
    @classmethod
    def _load_animation(cls, name: str, png: str, json_file: str) -> None:
        sheet = _load(png)
        meta = _load_json(json_file)
        if sheet is None or meta is None:
            return
        cls._anim_frames[name] = _slice_frames(sheet, meta)
        log.debug(
            "SpriteRegistry: animation %r — %d frames",
            name,
            len(cls._anim_frames[name]),
        )

    # ------------------------------------------------------------------
    @classmethod
    def get(cls, name: str) -> pygame.Surface | None:
        return cls._surfaces.get(name)

    @classmethod
    def get_for_obstacle(cls, rect: pygame.Rect) -> pygame.Surface | None:
        return cls._surfaces.get(f"obstacle_{rect.width}x{rect.height}")

    @classmethod
    def get_animated(cls, name: str) -> AnimatedSprite | None:
        """
        Create a fresh AnimatedSprite instance for *name*.

        Each monster gets its own instance so their timers are independent.
        Returns None if the animation was not loaded (missing file etc.).
        """
        frames = cls._anim_frames.get(name)
        if frames is None:
            return None
        return AnimatedSprite(frames)

    @classmethod
    def reset(cls) -> None:
        cls._surfaces.clear()
        cls._anim_frames.clear()
        cls._ready = False
