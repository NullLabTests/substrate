from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core.logging.structured_logger import StructuredLogger
from core.persistence.store import PersistenceBackend


@dataclass
class SnapshotMetadata:
    snapshot_id: str
    tick_count: int
    timestamp: str
    subsystem_count: int
    event_count: int
    agent_count: int
    size_bytes: int = 0


class SnapshotSystem:
    def __init__(
        self,
        persistence: PersistenceBackend,
        logger: StructuredLogger,
        interval_ticks: int = 500,
        retention_count: int = 20,
    ) -> None:
        self._persistence = persistence
        self._logger = logger
        self._interval_ticks = interval_ticks
        self._retention_count = retention_count
        self._subsystems: dict[str, SubsystemSnapshot] = {}
        self._snapshots: list[str] = []

    def register(self, name: str, subsystem: SubsystemSnapshot) -> None:
        self._subsystems[name] = subsystem

    @property
    def interval_ticks(self) -> int:
        return self._interval_ticks

    @interval_ticks.setter
    def interval_ticks(self, value: int) -> None:
        self._interval_ticks = value

    def should_snapshot(self, tick: int) -> bool:
        return tick > 0 and tick % self._interval_ticks == 0

    async def take_snapshot(self, tick_count: int, label: str = "") -> SnapshotMetadata:
        subsystem_states: dict[str, dict[str, Any]] = {}
        for name, sub in self._subsystems.items():
            try:
                subsystem_states[name] = await sub.save_state()
            except Exception as exc:
                self._logger.error("snapshot_subsystem_failed", subsystem=name, error=str(exc))
                subsystem_states[name] = {"__error__": str(exc)}

        snapshot_id = f"snap_{tick_count:010d}_{datetime.now(UTC).strftime('%H%M%S')}"
        timestamp = datetime.now(UTC).isoformat()
        snapshot = {
            "snapshot_id": snapshot_id, "tick_count": tick_count,
            "timestamp": timestamp, "label": label,
            "subsystems": subsystem_states,
        }
        raw = json.dumps(snapshot, default=str).encode()
        await self._persistence.save(f"snapshot.{snapshot_id}", snapshot)
        self._snapshots.append(snapshot_id)
        await self._enforce_retention()
        meta = SnapshotMetadata(
            snapshot_id=snapshot_id, tick_count=tick_count, timestamp=timestamp,
            subsystem_count=len(subsystem_states),
            event_count=len(subsystem_states.get("event_bus", {}).get("history", [])),
            agent_count=len(subsystem_states.get("registry", {}).get("agents", {})),
            size_bytes=len(raw),
        )
        self._logger.info("snapshot_taken", snapshot_id=snapshot_id, tick=tick_count, size_bytes=len(raw))
        return meta

    async def restore_snapshot(self, snapshot_id: str) -> int:
        snapshot = await self._persistence.load(f"snapshot.{snapshot_id}")
        if not snapshot:
            raise ValueError(f"Snapshot '{snapshot_id}' not found")
        for name, sub in self._subsystems.items():
            state = snapshot.get("subsystems", {}).get(name)
            if state is not None:
                try:
                    await sub.load_state(state)
                except Exception as exc:
                    self._logger.error("snapshot_restore_failed", subsystem=name, error=str(exc))
        self._logger.info("snapshot_restored", snapshot_id=snapshot_id, tick=snapshot.get("tick_count"))
        return snapshot.get("tick_count", 0)

    async def list_snapshots(self) -> list[SnapshotMetadata]:
        keys = await self._persistence.list_keys(prefix="snapshot.")
        results: list[SnapshotMetadata] = []
        for key in keys:
            data = await self._persistence.load(key)
            if data:
                results.append(SnapshotMetadata(
                    snapshot_id=data.get("snapshot_id", key),
                    tick_count=data.get("tick_count", 0),
                    timestamp=data.get("timestamp", ""),
                    subsystem_count=len(data.get("subsystems", {})),
                    event_count=0, agent_count=0,
                ))
        return sorted(results, key=lambda m: m.tick_count)

    async def _enforce_retention(self) -> None:
        if len(self._snapshots) <= self._retention_count:
            return
        for sid in self._snapshots[:-self._retention_count]:
            await self._persistence.delete(f"snapshot.{sid}")
        self._snapshots = self._snapshots[-self._retention_count:]


class SubsystemSnapshot:
    async def save_state(self) -> dict[str, Any]:
        return {}

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        pass
