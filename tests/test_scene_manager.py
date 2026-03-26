"""
Tests for core.scene_manager — lifecycle hooks and deferred switching.
"""
import pytest
import pygame
from unittest.mock import MagicMock, call
from core.scene_manager import SceneManager
from scenes.base_scene import BaseScene


def _make_scene(name="scene"):
    """Return a mock scene that satisfies the BaseScene interface."""
    scene = MagicMock(spec=BaseScene)
    scene.on_enter = MagicMock()
    scene.on_exit  = MagicMock()
    scene.update   = MagicMock()
    scene.draw     = MagicMock()
    scene.handle_event = MagicMock()
    return scene


class TestRegistration:
    def test_register_and_switch(self):
        sm = SceneManager()
        s = _make_scene()
        sm.register("a", s)
        sm.switch("a")
        sm.update(0.016)   # switch is applied here
        s.on_enter.assert_called_once()

    def test_switch_unknown_raises(self):
        sm = SceneManager()
        with pytest.raises(KeyError):
            sm.switch("does_not_exist")


class TestLifecycle:
    def test_on_exit_called_before_on_enter(self):
        sm = SceneManager()
        order = []
        a = _make_scene()
        b = _make_scene()
        a.on_exit.side_effect  = lambda: order.append("a_exit")
        b.on_enter.side_effect = lambda: order.append("b_enter")

        sm.register("a", a)
        sm.register("b", b)

        sm.switch("a")
        sm.update(0.016)   # activates a
        sm.switch("b")
        sm.update(0.016)   # exits a, enters b

        assert order == ["a_exit", "b_enter"]

    def test_on_enter_called_exactly_once_per_switch(self):
        sm = SceneManager()
        s = _make_scene()
        sm.register("s", s)
        sm.switch("s")
        sm.update(0.016)
        sm.update(0.016)   # second frame — on_enter must NOT fire again
        s.on_enter.assert_called_once()


class TestDeferredSwitch:
    def test_switch_is_not_applied_mid_update(self):
        """Switching during update must take effect on the NEXT frame, not
        immediately, to avoid mutating the active scene while it's running."""
        sm = SceneManager()
        a = _make_scene()
        b = _make_scene()
        sm.register("a", a)
        sm.register("b", b)

        switch_happened_during_update = []

        def a_update(dt):
            sm.switch("b")
            # At this point, b should NOT be active yet
            switch_happened_during_update.append(sm._active is a)

        a.update.side_effect = a_update

        sm.switch("a")
        sm.update(0.016)   # activates a
        sm.update(0.016)   # a.update calls switch("b"), then frame ends

        assert switch_happened_during_update == [True], (
            "Scene switched mid-frame instead of being deferred"
        )
        # On the NEXT frame b should be active
        sm.update(0.016)
        assert sm._active is b


class TestRouting:
    def test_events_routed_to_active_scene(self):
        sm = SceneManager()
        s = _make_scene()
        sm.register("s", s)
        sm.switch("s")
        sm.update(0.016)

        fake_event = MagicMock(spec=pygame.event.Event)
        sm.handle_event(fake_event)
        s.handle_event.assert_called_once_with(fake_event)

    def test_no_crash_with_no_active_scene(self):
        sm = SceneManager()
        sm.update(0.016)
        sm.draw(pygame.Surface((10, 10)))
        sm.handle_event(MagicMock())
