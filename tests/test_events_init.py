"""Tests for core/events/__init__.py - sync bus bridge."""

from __future__ import annotations

import asyncio

from core.events import _SyncBusBridge
from core.events.bus import EventBus, SystemEvent


class TestSyncBusBridge:
    """Tests for the synchronous event bus bridge."""

    async def test_sync_bridge_emit_creates_event(self, event_bus: EventBus) -> None:
        """Sync bridge emits an event and returns it."""
        bridge = _SyncBusBridge(event_bus)
        event = bridge.emit("test.sync", agent_id="agent-1", payload={"key": "val"})
        assert isinstance(event, SystemEvent)
        assert event.topic == "test.sync"
        assert event.source == "agent-1"
        assert event.payload == {"key": "val"}

    async def test_sync_bridge_delivers_to_subscribers(
        self, event_bus: EventBus
    ) -> None:
        """Events emitted via sync bridge are delivered to subscribers."""
        received: list[SystemEvent] = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        event_bus.subscribe("test.sync.delivery", handler)
        bridge = _SyncBusBridge(event_bus)
        bridge.emit("test.sync.delivery", payload={"msg": "hello"})
        await asyncio.sleep(0.02)
        assert len(received) == 1
        assert received[0].payload["msg"] == "hello"

    async def test_sync_bridge_multiple_events(self, event_bus: EventBus) -> None:
        """Multiple events can be emitted via sync bridge."""
        bridge = _SyncBusBridge(event_bus)
        event1 = bridge.emit("test.multi", payload={"seq": 1})
        event2 = bridge.emit("test.multi", payload={"seq": 2})
        assert event1.payload["seq"] == 1
        assert event2.payload["seq"] == 2

    async def test_sync_bridge_without_payload(self, event_bus: EventBus) -> None:
        """Emit with minimal arguments works."""
        bridge = _SyncBusBridge(event_bus)
        event = bridge.emit("test.minimal")
        assert event.topic == "test.minimal"
        assert event.payload == {}
        assert event.source is None

    async def test_sync_bridge_emit_with_agent_id(self, event_bus: EventBus) -> None:
        """Agent ID is passed as source in emitted event."""
        bridge = _SyncBusBridge(event_bus)
        event = bridge.emit("test.agent", agent_id="my-agent")
        assert event.source == "my-agent"

    async def test_sync_bridge_emit_twice(self, event_bus: EventBus) -> None:
        """Emit can be called multiple times."""
        bridge = _SyncBusBridge(event_bus)
        e1 = bridge.emit("test.two", payload={"n": 1})
        e2 = bridge.emit("test.two", payload={"n": 2})
        assert e1.payload["n"] == 1
        assert e2.payload["n"] == 2
