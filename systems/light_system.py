"""
Real-time 2-D shadow / visibility system using the visibility-polygon
(raycasting) algorithm.

Algorithm overview
------------------
1. Collect all obstacle *segments* (edges of axis-aligned rects).
2. For each light source:
   a. For every segment endpoint, cast three rays: angle-ε, angle, angle+ε.
   b. For each ray, find the *closest* intersection with any segment.
   c. Sort hit points by angle → this forms the illuminated polygon.
3. Render a darkness overlay; punch a transparent hole for each lit polygon.

Rendering (pygame)
------------------
- ``darkness`` surface: SRCALPHA, filled with NIGHT_COLOR + alpha.
- ``light_mask`` surface: SRCALPHA, all transparent.
  For each light polygon, draw it with a warm tint.
- Blit ``darkness`` using BLEND_RGBA_SUB to cut out the lit areas.
- The result: world is dark, lit polygons glow through.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import pygame

from settings import LIGHT


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Segment:
    ax: float
    ay: float
    bx: float
    by: float


def _rect_to_segments(r: pygame.Rect) -> list[Segment]:
    """Four edges of a rectangle, one Segment each."""
    return [
        Segment(r.left,  r.top,    r.right, r.top),
        Segment(r.right, r.top,    r.right, r.bottom),
        Segment(r.right, r.bottom, r.left,  r.bottom),
        Segment(r.left,  r.bottom, r.left,  r.top),
    ]


def _ray_segment_intersect(
    ox: float, oy: float,
    dx: float, dy: float,
    seg: Segment,
) -> float | None:
    """
    Parametric ray–segment intersection.

    Ray:     P(t) = (ox,oy) + t*(dx,dy)   t ≥ 0
    Segment: Q(s) = A + s*(B-A)            0 ≤ s ≤ 1

    Returns *t* if they intersect, None otherwise.
    """
    sdx = seg.bx - seg.ax
    sdy = seg.by - seg.ay

    denom = dx * sdy - dy * sdx
    if abs(denom) < 1e-10:
        return None  # parallel / collinear

    t = ((seg.ax - ox) * sdy - (seg.ay - oy) * sdx) / denom
    s = ((seg.ax - ox) * dy  - (seg.ay - oy) * dx)  / denom

    if t >= 0.0 and 0.0 <= s <= 1.0:
        return t
    return None


# ---------------------------------------------------------------------------
# Visibility polygon
# ---------------------------------------------------------------------------

def compute_visibility_polygon(
    ox: float,
    oy: float,
    segments: Sequence[Segment],
    radius: float,
    epsilon: float = LIGHT.ray_epsilon,
) -> list[tuple[float, float]]:
    """
    Compute the illuminated polygon for a single light source.

    Parameters
    ----------
    ox, oy:    Light source position (world space).
    segments:  All obstacle segments to cast shadows from.
    radius:    Maximum light radius in pixels.
    epsilon:   Angular offset for corner-hugging rays.

    Returns
    -------
    List of (x, y) world-space points forming the lit polygon.
    Guaranteed to be sorted by angle (CCW) relative to (ox, oy).
    """
    # Gather candidate angles: every segment endpoint ± ε
    angles: list[float] = []
    for seg in segments:
        for ex, ey in ((seg.ax, seg.ay), (seg.bx, seg.by)):
            a = math.atan2(ey - oy, ex - ox)
            angles.append(a - epsilon)
            angles.append(a)
            angles.append(a + epsilon)

    if not angles:
        # No obstacles — full circle (approximate with N rays)
        angles = [math.tau * i / 64 for i in range(64)]

    points: list[tuple[float, float]] = []
    for angle in angles:
        dx = math.cos(angle)
        dy = math.sin(angle)

        # Find the closest intersection along this ray
        closest_t = radius
        for seg in segments:
            t = _ray_segment_intersect(ox, oy, dx, dy, seg)
            if t is not None and t < closest_t:
                closest_t = t

        points.append((ox + dx * closest_t, oy + dy * closest_t))

    # Sort by angle so pygame can draw a proper polygon
    points.sort(key=lambda p: math.atan2(p[1] - oy, p[0] - ox))
    return points


# ---------------------------------------------------------------------------
# LightSystem
# ---------------------------------------------------------------------------

# (R,G,B) tint of each light; give each type a slightly different warmth
_LANTERN_TINT  = (255, 210, 140)
_CAMPFIRE_TINT = (255, 160,  80)
_DEFAULT_TINT  = (255, 220, 180)

# How many alpha units the darkness overlay uses per night
_NIGHT_ALPHA = LIGHT.darkness_alpha_night


class LightSystem:
    """
    Owns the shadow surface and renders it each frame.

    Usage (in GameScene.draw):
        light_system.draw(screen, world.obstacle_segments(), light_sources)
    """

    def __init__(self, screen_size: tuple[int, int]) -> None:
        w, h = screen_size
        # Persistent surface — recreated only if window resizes
        self._darkness = pygame.Surface((w, h), pygame.SRCALPHA)
        self._size = screen_size

        # Reusable per-light surface
        self._light_surf = pygame.Surface((w, h), pygame.SRCALPHA)

    # ------------------------------------------------------------------
    def draw(
        self,
        screen: pygame.Surface,
        segments: list[Segment],
        # (world_pos, radius, intensity 0..1)
        light_sources: list[tuple[pygame.Vector2, float, float]],
        *,
        darkness_alpha: int = _NIGHT_ALPHA,
        camera_offset: pygame.Vector2 | None = None,
    ) -> None:
        """
        Render the shadow/light overlay onto *screen*.

        Parameters
        ----------
        segments:
            Obstacle geometry in *world* space.
        light_sources:
            Each entry: (position in world space, radius, intensity).
        camera_offset:
            If the world scrolls, pass the camera offset so world→screen
            conversion is applied before rendering.
        """
        offset = camera_offset or pygame.Vector2(0, 0)

        # --- 1. Fill darkness ---
        self._darkness.fill((*LIGHT.darkness_color, darkness_alpha))

        # --- 2. For each light, cut an illuminated polygon ---
        for world_pos, radius, intensity in light_sources:
            ox = world_pos.x
            oy = world_pos.y

            # Compute visibility polygon in world space
            vis_world = compute_visibility_polygon(ox, oy, segments, radius)
            if len(vis_world) < 3:
                continue

            # Convert to screen space
            vis_screen = [
                (p[0] - offset.x, p[1] - offset.y)
                for p in vis_world
            ]

            # Draw the lit area on a transparent surface, then subtract from darkness
            self._light_surf.fill((0, 0, 0, 0))
            alpha = int(255 * max(0.0, min(1.0, intensity)))
            pygame.draw.polygon(self._light_surf, (0, 0, 0, alpha), vis_screen)

            # BLEND_RGBA_SUB: darkness_alpha -= light_alpha → punches a hole
            self._darkness.blit(
                self._light_surf, (0, 0),
                special_flags=pygame.BLEND_RGBA_SUB,
            )

            # Optional: soft glow halo at lower opacity
            self._draw_glow(vis_screen, ox - offset.x, oy - offset.y, radius, intensity)

        # --- 3. Blit the final shadow overlay ---
        screen.blit(self._darkness, (0, 0))

    # ------------------------------------------------------------------
    def _draw_glow(
        self,
        vis_screen: list[tuple[float, float]],
        sx: float,
        sy: float,
        radius: float,
        intensity: float,
    ) -> None:
        """
        Paint a soft warm circle that bleeds slightly outside the hard polygon.
        This fakes a glow without per-pixel shaders.
        """
        glow_alpha = int(60 * intensity)
        glow_radius = int(radius * 0.3)
        if glow_radius < 4 or glow_alpha < 5:
            return

        glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            glow_surf,
            (*_DEFAULT_TINT, glow_alpha),
            (glow_radius, glow_radius),
            glow_radius,
        )
        self._darkness.blit(
            glow_surf,
            (int(sx) - glow_radius, int(sy) - glow_radius),
            special_flags=pygame.BLEND_RGBA_SUB,
        )
