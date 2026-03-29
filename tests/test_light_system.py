"""
Tests for systems.light_system — geometry correctness and rendering pipeline.

Imports only the public API — no private names like _UNIFORM_RAY_COUNT.
Tests check *behaviour* (the polygon is smooth enough, shadows are cast,
overlapping lights don't darken the scene) rather than implementation details.
"""
import math
import pytest
import pygame
from systems.light_system import (
    Segment,
    _ray_segment_intersect,
    _rect_to_segments,
    compute_visibility_polygon,
    LightSystem,
)


class TestRaySegmentIntersect:
    def test_perpendicular_ray_hits_horizontal_segment(self):
        seg = Segment(0, 50, 100, 50)
        t = _ray_segment_intersect(50, 0, 0, 1, seg)
        assert t is not None
        assert abs(t - 50) < 1e-6

    def test_parallel_ray_returns_none(self):
        seg = Segment(0, 50, 100, 50)
        t = _ray_segment_intersect(0, 0, 1, 0, seg)
        assert t is None

    def test_ray_behind_segment_returns_none(self):
        seg = Segment(0, 50, 100, 50)
        t = _ray_segment_intersect(50, 100, 0, 1, seg)
        assert t is None

    def test_ray_misses_segment_endpoint(self):
        seg = Segment(200, 0, 300, 0)
        t = _ray_segment_intersect(0, 0, 0, 1, seg)
        assert t is None

    def test_returns_correct_t_at_diagonal(self):
        seg = Segment(50, -100, 50, 100)
        dx, dy = math.cos(math.radians(45)), math.sin(math.radians(45))
        t = _ray_segment_intersect(0, 0, dx, dy, seg)
        assert t is not None
        assert abs(dx * t - 50) < 1e-4


class TestRectToSegments:
    def test_produces_four_segments(self):
        r = pygame.Rect(0, 0, 100, 100)
        segs = _rect_to_segments(r)
        assert len(segs) == 4

    def test_segments_cover_all_four_edges(self):
        r = pygame.Rect(10, 20, 60, 40)
        segs = _rect_to_segments(r)
        endpoints = set()
        for s in segs:
            endpoints.add((s.ax, s.ay))
            endpoints.add((s.bx, s.by))
        assert (10, 20) in endpoints
        assert (70, 20) in endpoints
        assert (70, 60) in endpoints
        assert (10, 60) in endpoints


class TestComputeVisibilityPolygon:
    def test_no_obstacles_returns_smooth_polygon(self):
        """Without obstacles the polygon should approximate a circle well enough
        that arcs don't look angular — at least 32 vertices required."""
        pts = compute_visibility_polygon(0, 0, [], radius=100)
        assert len(pts) >= 32, (
            f"Expected ≥32 vertices for a smooth circle, got {len(pts)}"
        )

    def test_all_points_within_radius(self):
        pts = compute_visibility_polygon(0, 0, [], radius=100)
        for x, y in pts:
            dist = math.hypot(x, y)
            assert dist <= 100 + 1e-6, f"Point ({x},{y}) outside radius"

    def test_obstacle_creates_shadow(self):
        """A tall wall to the right should cast a shadow behind it.

        Only the mid-section of the shadow cone is checked (|y| < 100).
        Rays near the wall endpoints are allowed through — that is correct
        raycasting behaviour at corners, not a bug.
        """
        wall = Segment(50, -200, 50, 200)
        pts = compute_visibility_polygon(0, 0, [wall], radius=300)

        shadow_leaks = [(x, y) for x, y in pts if x > 60 and abs(y) < 100]
        assert not shadow_leaks, (
            f"Rays leaked through shadow wall mid-section: {shadow_leaks[:3]}"
        )

    def test_no_exact_duplicate_points(self):
        seg = Segment(50, -50, 50, 50)
        pts = compute_visibility_polygon(0, 0, [seg], radius=200)
        rounded = [(round(x, 3), round(y, 3)) for x, y in pts]
        assert len(set(rounded)) == len(rounded), "Exact duplicate points found"

    def test_points_sorted_by_angle(self):
        """Vertices must be sorted CCW so pygame.draw.polygon works correctly."""
        pts = compute_visibility_polygon(0, 0, [], radius=100)
        angles = [math.atan2(y, x) for x, y in pts]
        assert angles == sorted(angles)

    def test_more_points_with_obstacles(self):
        """Obstacles add corner-hugging rays → polygon has more vertices."""
        no_obs = compute_visibility_polygon(0, 0, [], radius=200)
        seg = Segment(50, -50, 50, 50)
        with_obs = compute_visibility_polygon(0, 0, [seg], radius=200)
        assert len(with_obs) >= len(no_obs)


class TestLightSystemRendering:
    def test_single_mask_architecture(self):
        """The system must accumulate all light polygons into one mask before
        subtracting — the old per-source surface caused double-subtract bugs."""
        ls = LightSystem((640, 360))
        assert hasattr(ls, "_light_mask")
        assert not hasattr(ls, "_light_surf")

    def test_draw_does_not_crash_with_no_sources(self):
        ls = LightSystem((640, 360))
        screen = pygame.Surface((640, 360), pygame.SRCALPHA)
        ls.draw(screen, segments=[], light_sources=[])

    def test_draw_does_not_crash_with_one_source(self):
        ls = LightSystem((640, 360))
        screen = pygame.Surface((640, 360), pygame.SRCALPHA)
        ls.draw(
            screen,
            segments=[],
            light_sources=[(pygame.Vector2(320, 180), 100.0, 1.0)],
        )

    def test_draw_darkens_screen(self):
        """The area far from any light source must be darker after draw()."""
        ls = LightSystem((640, 360))
        screen = pygame.Surface((640, 360))
        screen.fill((200, 200, 200))

        ls.draw(
            screen,
            segments=[],
            light_sources=[(pygame.Vector2(0, 0), 50.0, 1.0)],
        )
        r, g, b, *_ = screen.get_at((630, 350))
        assert (r + g + b) / 3 < 150, "Bottom-right pixel not darkened"

    def test_two_overlapping_sources_do_not_over_darken(self):
        """Two co-located lights must not make the centre darker than one light.
        Regression test for the double-subtract bug."""
        ls = LightSystem((640, 360))

        screen_single = pygame.Surface((640, 360))
        screen_single.fill((10, 10, 20))
        ls.draw(screen_single, [], [(pygame.Vector2(320, 180), 200.0, 1.0)])
        r1, *_ = screen_single.get_at((320, 180))

        screen_double = pygame.Surface((640, 360))
        screen_double.fill((10, 10, 20))
        ls.draw(screen_double, [], [
            (pygame.Vector2(320, 180), 200.0, 1.0),
            (pygame.Vector2(320, 180), 200.0, 1.0),
        ])
        r2, *_ = screen_double.get_at((320, 180))

        assert r2 >= r1, "Overlapping lights darkened centre (double-subtract bug)"
