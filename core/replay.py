from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.events.bus import EventBus, SystemEvent
from core.seed import SimulationSeed


@dataclass
class ReplayEvent:
    tick: int
    event: SystemEvent
    ordering: int


@dataclass
class ReplayResult:
    total_events: int
    total_ticks: int
    start_time: str
    end_time: str
    duration_seconds: float
    events_by_topic: dict[str, int]
    completed: bool


EventHandler = Callable[[SystemEvent], Coroutine[Any, Any, None]]


class ReplaySystem:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._events: list[ReplayEvent] = []
        self._analysis_hooks: list[EventHandler] = []

    def add_analysis_hook(self, hook: EventHandler) -> None:
        self._analysis_hooks.append(hook)

    async def load_from_history(self, history: list[dict[str, Any]]) -> None:
        self._events.clear()
        for i, entry in enumerate(history):
            event = SystemEvent.from_dict(entry)
            tick = event.payload.get("tick", 0)
            self._events.append(ReplayEvent(tick=tick, event=event, ordering=i))

    async def load_from_file(self, path: str | Path) -> None:
        self._events.clear()
        with open(path) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                event = SystemEvent.from_dict(entry)
                tick = event.payload.get("tick", 0)
                self._events.append(ReplayEvent(tick=tick, event=event, ordering=i))

    async def run(
        self,
        max_ticks: int | None = None,
        speed_factor: float = 1.0,
        stop_at_tick: int | None = None,
    ) -> ReplayResult:
        if not self._events:
            return ReplayResult(
                total_events=0, total_ticks=0, start_time="", end_time="",
                duration_seconds=0.0, events_by_topic={}, completed=True,
            )

        start_time = datetime.now(UTC).isoformat()
        events_by_topic: dict[str, int] = {}
        last_tick = 0
        replayed = 0

        for replay_event in self._events:
            if stop_at_tick is not None and replay_event.tick > stop_at_tick:
                break
            if max_ticks is not None and replay_event.tick > max_ticks:
                break
            if replay_event.tick != last_tick and speed_factor > 0:
                await asyncio.sleep(1.0 / speed_factor * 0.001)

            await self._event_bus.publish(replay_event.event)
            events_by_topic[replay_event.event.topic] = (
                events_by_topic.get(replay_event.event.topic, 0) + 1
            )
            for hook in self._analysis_hooks:
                await hook(replay_event.event)
            last_tick = replay_event.tick
            replayed += 1

        end_time = datetime.now(UTC).isoformat()
        duration = (
            datetime.fromisoformat(end_time) - datetime.fromisoformat(start_time)
        ).total_seconds()
        return ReplayResult(
            total_events=replayed, total_ticks=last_tick,
            start_time=start_time, end_time=end_time,
            duration_seconds=duration, events_by_topic=events_by_topic, completed=True,
        )

    async def run_deterministic(
        self, seed: SimulationSeed, max_ticks: int | None = None,
    ) -> ReplayResult:
        return await self.run(max_ticks=max_ticks, speed_factor=0)

    def export_events(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for re in self._events:
                f.write(json.dumps(re.event.to_dict(), default=str) + "\n")
        return path

    @property
    def event_count(self) -> int:
        return len(self._events)
