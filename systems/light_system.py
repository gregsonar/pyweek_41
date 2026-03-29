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
        Segment(r.left, r.top, r.right, r.top),
        Segment(r.right, r.top, r.right, r.bottom),
        Segment(r.right, r.bottom, r.left, r.bottom),
        Segment(r.left, r.bottom, r.left, r.top),
    ]


def _ray_segment_intersect(
    ox: float,
    oy: float,
    dx: float,
    dy: float,
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
    s = ((seg.ax - ox) * dy - (seg.ay - oy) * dx) / denom

    if t >= 0.0 and 0.0 <= s <= 1.0:
        return t
    return None


# ---------------------------------------------------------------------------
# Visibility polygon
# ---------------------------------------------------------------------------

_UNIFORM_RAY_COUNT = 72  # baseline rays every 5° — keeps arcs smooth between obstacles


def compute_visibility_polygon(
    ox: float,
    oy: float,
    segments: Sequence[Segment],
    radius: float,
    epsilon: float = LIGHT.ray_epsilon,
) -> list[tuple[float, float]]:
    """
    Compute the illuminated polygon for a single light source.

    Combines:
      1. Uniform baseline rays (every 360/N degrees) — ensure smooth arcs in open areas.
      2. Corner-hugging rays (angle ± ε) at every obstacle endpoint — crisp shadow edges.

    Returns a list of (x, y) world-space points sorted by angle, ready for
    pygame.draw.polygon.
    """
    # 1. Uniform baseline — guarantees the polygon is never more angular than
    #    a 72-gon even when there are no nearby obstacles.
    angles: list[float] = [
        math.tau * i / _UNIFORM_RAY_COUNT for i in range(_UNIFORM_RAY_COUNT)
    ]

    # 2. Obstacle endpoint rays
    for seg in segments:
        for ex, ey in ((seg.ax, seg.ay), (seg.bx, seg.by)):
            a = math.atan2(ey - oy, ex - ox)
            angles.append(a - epsilon)
            angles.append(a)
            angles.append(a + epsilon)

    # Deduplicate angles that are closer than epsilon/2 to avoid near-duplicate
    # vertices that can cause micro self-intersections in the polygon.
    angles.sort()
    deduped: list[float] = []
    prev = -math.inf
    for a in angles:
        if a - prev > epsilon / 2:
            deduped.append(a)
            prev = a

    points: list[tuple[float, float]] = []
    for angle in deduped:
        dx = math.cos(angle)
        dy = math.sin(angle)

        closest_t = radius
        for seg in segments:
            t = _ray_segment_intersect(ox, oy, dx, dy, seg)
            if t is not None and t < closest_t:
                closest_t = t

        points.append((ox + dx * closest_t, oy + dy * closest_t))

    # Already sorted (angles were sorted above), but re-sort by atan2 to be safe
    # after the epsilon offsets may have pushed some angles across the ±π boundary.
    points.sort(key=lambda p: math.atan2(p[1] - oy, p[0] - ox))
    return points


# ---------------------------------------------------------------------------
# LightSystem
# ---------------------------------------------------------------------------

# (R,G,B) tint of each light; give each type a slightly different warmth
_LANTERN_TINT = (255, 210, 140)
_CAMPFIRE_TINT = (255, 160, 80)
_DEFAULT_TINT = (255, 220, 180)

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
        self._darkness = pygame.Surface((w, h), pygame.SRCALPHA)
        self._light_mask = pygame.Surface((w, h), pygame.SRCALPHA)
        # Temporary surface for a single polygon — blitted into _light_mask
        # with BLEND_RGBA_MAX so the brightest source always wins.
        self._poly_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        self._size = screen_size

    # ------------------------------------------------------------------
    def draw(
        self,
        screen: pygame.Surface,
        segments: list[Segment],
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
            Obstacle geometry in world space.
        light_sources:
            Each entry: (position in world space, radius, intensity 0..1).
        camera_offset:
            If the world scrolls, pass the camera offset for world→screen conversion.
        """
        offset = camera_offset or pygame.Vector2(0, 0)

        # --- 1. Darkness base ---
        self._darkness.fill((*LIGHT.darkness_color, darkness_alpha))

        # --- 2. Accumulate ALL lit polygons into a single mask ---
        #    Using BLEND_RGBA_MAX: overlapping light polygons take the brighter value,
        #    no double-subtraction artifacts.
        self._light_mask.fill((0, 0, 0, 0))

        for world_pos, radius, intensity in light_sources:
            ox, oy = world_pos.x, world_pos.y

            vis_world = compute_visibility_polygon(ox, oy, segments, radius)
            if len(vis_world) < 3:
                continue

            vis_screen = [(p[0] - offset.x, p[1] - offset.y) for p in vis_world]

            alpha = int(min(darkness_alpha, 255) * max(0.0, min(1.0, intensity)))
            self._poly_surf.fill((0, 0, 0, 0))
            pygame.draw.polygon(self._poly_surf, (0, 0, 0, alpha), vis_screen)
            # MAX-blend: brightest source wins in every overlapping pixel.
            # A dim campfire can never darken an area lit by a bright lantern.
            self._light_mask.blit(
                self._poly_surf,
                (0, 0),
                special_flags=pygame.BLEND_RGBA_MAX,
            )

            self._draw_glow(
                ox - offset.x, oy - offset.y, radius, intensity, darkness_alpha
            )

        # --- 3. One subtract pass ---
        self._darkness.blit(
            self._light_mask, (0, 0), special_flags=pygame.BLEND_RGBA_SUB
        )

        # --- 4. Composite onto screen ---
        screen.blit(self._darkness, (0, 0))

    # ------------------------------------------------------------------
    def _draw_glow(
        self,
        sx: float,
        sy: float,
        radius: float,
        intensity: float,
        darkness_alpha: int,
    ) -> None:
        """Soft warm halo that bleeds slightly outside the hard shadow polygon."""
        glow_alpha = int(40 * intensity)
        glow_radius = int(radius * 0.25)
        if glow_radius < 4 or glow_alpha < 4:
            return

        d = glow_radius * 2
        glow_surf = pygame.Surface((d, d), pygame.SRCALPHA)
        pygame.draw.circle(
            glow_surf,
            (*_DEFAULT_TINT, glow_alpha),
            (glow_radius, glow_radius),
            glow_radius,
        )
        self._light_mask.blit(
            glow_surf,
            (int(sx) - glow_radius, int(sy) - glow_radius),
        )
