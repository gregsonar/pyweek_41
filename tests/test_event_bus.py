"""
Tests for core.event_bus — pub/sub correctness and error isolation.
"""
import pytest
from core.event_bus import EventBus, Events


class TestSubscribePublish:
    def test_subscriber_receives_kwargs(self, bus):
        received = []
        bus.subscribe("test_event", lambda val: received.append(val))
        bus.publish("test_event", val=42)
        assert received == [42]

    def test_multiple_subscribers_all_called(self, bus):
        log = []
        bus.subscribe("e", lambda: log.append("a"))
        bus.subscribe("e", lambda: log.append("b"))
        bus.publish("e")
        assert log == ["a", "b"]

    def test_no_subscribers_does_not_raise(self, bus):
        bus.publish("nonexistent_event", foo="bar")   # must not raise

    def test_subscriber_receives_multiple_kwargs(self, bus):
        received = {}
        bus.subscribe("e", lambda x, y: received.update({"x": x, "y": y}))
        bus.publish("e", x=1, y=2)
        assert received == {"x": 1, "y": 2}


class TestUnsubscribe:
    def test_unsubscribe_stops_delivery(self, bus):
        log = []
        cb = lambda: log.append(1)
        bus.subscribe("e", cb)
        bus.publish("e")
        bus.unsubscribe("e", cb)
        bus.publish("e")
        assert log == [1]   # called only once

    def test_unsubscribe_unknown_callback_logs_warning(self, bus, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="core.event_bus"):
            bus.unsubscribe("e", lambda: None)
        assert "not subscribed" in caplog.text

    def test_double_subscribe_ignored(self, bus):
        """Registering the same callback twice should not call it twice."""
        log = []
        cb = lambda: log.append(1)
        bus.subscribe("e", cb)
        bus.subscribe("e", cb)
        bus.publish("e")
        assert log == [1]


class TestClear:
    def test_clear_specific_event(self, bus):
        log = []
        bus.subscribe("a", lambda: log.append("a"))
        bus.subscribe("b", lambda: log.append("b"))
        bus.clear("a")
        bus.publish("a")
        bus.publish("b")
        assert log == ["b"]

    def test_clear_all(self, bus):
        log = []
        bus.subscribe("a", lambda: log.append("a"))
        bus.subscribe("b", lambda: log.append("b"))
        bus.clear()
        bus.publish("a")
        bus.publish("b")
        assert log == []


class TestErrorIsolation:
    def test_raising_subscriber_does_not_block_others(self, bus, caplog):
        """A crashing listener must not prevent subsequent listeners from running."""
        import logging
        log = []

        def bad_cb():
            raise RuntimeError("boom")

        bus.subscribe("e", bad_cb)
        bus.subscribe("e", lambda: log.append("ok"))

        with caplog.at_level(logging.ERROR, logger="core.event_bus"):
            bus.publish("e")

        assert log == ["ok"]
        assert "unhandled exception" in caplog.text

    def test_self_unsubscribing_callback_is_safe(self, bus):
        """A callback that unsubscribes itself during publish must not crash."""
        log = []

        def cb():
            log.append(1)
            bus.unsubscribe("e", cb)

        bus.subscribe("e", cb)
        bus.publish("e")
        bus.publish("e")   # second publish — cb should be gone
        assert log == [1]


class TestWellKnownEvents:
    def test_events_class_has_all_expected_attributes(self):
        expected = [
            "PHASE_DAY_START", "PHASE_NIGHT_START", "PHASE_TRANSITION",
            "CAMPFIRE_LIT", "CAMPFIRE_EXTINGUISHED",
            "LANTERN_FUEL_LOW", "LANTERN_EMPTY",
            "PLAYER_DAMAGED", "PLAYER_DIED",
            "MONSTER_KILLED", "WAVE_SPAWNED",
            "ITEM_PICKED_UP", "ITEM_CRAFTED", "STRUCTURE_BUILT",
            "SCENE_CHANGE", "GAME_OVER",
        ]
        for name in expected:
            assert hasattr(Events, name), f"Events.{name} missing"
