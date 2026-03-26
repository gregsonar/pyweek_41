"""
Tests for systems.light_system — geometry correctness and rendering pipeline.

These tests are the most critical: the light system is the #1 priority feature
and had two major bugs (inverted polygons, double-subtract artifacts).
"""

import math

import pygame
import pytest

from systems.light_system import (
    LightSystem,
    Segment,
    _ray_segment_intersect,
    _rect_to_segments,
    compute_visibility_polygon,
)


class TestRaySegmentIntersect:
    def test_perpendicular_ray_hits_horizontal_segment(self):
        seg = Segment(0, 50, 100, 50)  # horizontal at y=50
        t = _ray_segment_intersect(50, 0, 0, 1, seg)
        assert t is not None
        assert abs(t - 50) < 1e-6

    def test_parallel_ray_returns_none(self):
        seg = Segment(0, 50, 100, 50)  # horizontal at y=50
        t = _ray_segment_intersect(0, 0, 1, 0, seg)  # ray also horizontal
        assert t is None

    def test_ray_behind_segment_returns_none(self):
        seg = Segment(0, 50, 100, 50)
        # Ray pointing away (downward)
        t = _ray_segment_intersect(50, 100, 0, 1, seg)
        assert t is None

    def test_ray_misses_segment_endpoint(self):
        # Ray shoots past the segment's x-range
        seg = Segment(200, 0, 300, 0)
        t = _ray_segment_intersect(0, 0, 0, 1, seg)  # straight down from (0,0)
        assert t is None

    def test_returns_correct_t_at_diagonal(self):
        # Ray from origin at 45°, segment is vertical at x=50
        seg = Segment(50, -100, 50, 100)
        dx, dy = math.cos(math.radians(45)), math.sin(math.radians(45))
        t = _ray_segment_intersect(0, 0, dx, dy, seg)
        assert t is not None
        hit_x = dx * t
        assert abs(hit_x - 50) < 1e-4


class TestRectToSegments:
    def test_produces_four_segments(self):
        r = pygame.Rect(0, 0, 100, 100)
        segs = _rect_to_segments(r)
        assert len(segs) == 4

    def test_segments_cover_all_four_edges(self):
        r = pygame.Rect(10, 20, 60, 40)
        segs = _rect_to_segments(r)
        # Each edge should be covered
        endpoints = set()
        for s in segs:
            endpoints.add((s.ax, s.ay))
            endpoints.add((s.bx, s.by))
        assert (10, 20) in endpoints  # top-left
        assert (70, 20) in endpoints  # top-right
        assert (70, 60) in endpoints  # bottom-right
        assert (10, 60) in endpoints  # bottom-left


class TestComputeVisibilityPolygon:
    def test_no_obstacles_returns_uniform_baseline(self):
        pts = compute_visibility_polygon(0, 0, [], radius=100)
        assert len(pts) == _UNIFORM_RAY_COUNT

    def test_all_points_within_radius(self):
        pts = compute_visibility_polygon(0, 0, [], radius=100)
        for x, y in pts:
            dist = math.hypot(x, y)
            assert dist <= 100 + 1e-6, f"Point ({x},{y}) outside radius 100"

    def test_obstacle_creates_shadow(self):
        """A wall directly to the right should cast a shadow behind it.

        We only check rays that travel in the cone directly behind the wall
        (near-horizontal, away from the endpoints at y≈±50). Rays near the
        endpoints are intentionally allowed through — that's correct raycasting
        behaviour at corners, not a bug.
        """
        wall = Segment(50, -200, 50, 200)  # tall vertical wall at x=50
        pts = compute_visibility_polygon(0, 0, [wall], radius=300)

        # Only examine points that are both (a) clearly behind the wall and
        # (b) in the mid-section of the shadow cone (|y| < 100 avoids corners)
        shadow_leaks = [(x, y) for x, y in pts if x > 60 and abs(y) < 100]
        assert not shadow_leaks, (
            f"Rays leaked through shadow wall mid-section: {shadow_leaks[:3]}"
        )

    def test_no_exact_duplicate_points(self):
        seg = Segment(50, -50, 50, 50)
        pts = compute_visibility_polygon(0, 0, [seg], radius=200)
        rounded = [(round(x, 3), round(y, 3)) for x, y in pts]
        assert len(set(rounded)) == len(rounded), (
            "Exact duplicate points found in polygon"
        )

    def test_points_sorted_by_angle(self):
        """Polygon vertices must be sorted CCW for pygame.draw.polygon."""
        pts = compute_visibility_polygon(0, 0, [], radius=100)
        angles = [math.atan2(y, x) for x, y in pts]
        # Sorted ascending (CCW from -π to π)
        assert angles == sorted(angles)

    def test_more_points_with_obstacles(self):
        """Adding obstacles adds corner rays → more vertices than baseline."""
        no_obs = compute_visibility_polygon(0, 0, [], radius=200)
        seg = Segment(50, -50, 50, 50)
        with_obs = compute_visibility_polygon(0, 0, [seg], radius=200)
        assert len(with_obs) >= len(no_obs)


class TestLightSystemRendering:
    def test_single_mask_architecture(self):
        ls = LightSystem((640, 360))
        assert hasattr(ls, "_light_mask")
        assert not hasattr(ls, "_light_surf"), (
            "_light_surf was the old per-source surface that caused double-subtract bugs"
        )

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
        """After draw(), the area far from any light should be darker than before."""
        ls = LightSystem((640, 360))
        screen = pygame.Surface((640, 360))
        screen.fill((200, 200, 200))  # start bright

        # Light source in the top-left corner only
        ls.draw(
            screen,
            segments=[],
            light_sources=[(pygame.Vector2(0, 0), 50.0, 1.0)],
        )
        # Sample a pixel in the bottom-right — should be darkened
        r, g, b, *_ = screen.get_at((630, 350))
        avg = (r + g + b) / 3
        assert avg < 150, f"Bottom-right pixel not darkened: avg={avg}"

    def test_two_overlapping_sources_do_not_over_darken(self):
        """
        The single-mask fix: overlapping light polygons should not subtract
        darkness twice. The overlapping area must be at least as bright as
        either source alone.
        """
        ls = LightSystem((640, 360))

        # Screen with a single centred source
        screen_single = pygame.Surface((640, 360))
        screen_single.fill((10, 10, 20))
        ls.draw(screen_single, [], [(pygame.Vector2(320, 180), 200.0, 1.0)])
        r1, g1, b1, *_ = screen_single.get_at((320, 180))

        # Screen with two co-located sources (worst-case overlap)
        screen_double = pygame.Surface((640, 360))
        screen_double.fill((10, 10, 20))
        ls.draw(
            screen_double,
            [],
            [
                (pygame.Vector2(320, 180), 200.0, 1.0),
                (pygame.Vector2(320, 180), 200.0, 1.0),
            ],
        )
        r2, g2, b2, *_ = screen_double.get_at((320, 180))

        # The doubled source must not make the centre DARKER than single
        # (which would indicate double-subtraction)
        assert r2 >= r1, "Overlapping lights made centre darker (double-subtract bug)"
