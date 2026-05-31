"""Recovery system for crash recovery, event replay, and state restoration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from core.events.bus import EventBus, SystemEvent, EventPriority
from core.logging.structured_logger import StructuredLogger
from core.persistence.store import PersistenceBackend


class RecoverySystem:
    """Handles crash recovery on startup.

    Checks for crash state, replays event log for subsystems that
    require it, and restores the last persisted snapshot.
    """

    def __init__(
        self,
        event_bus: EventBus,
        persistence: PersistenceBackend,
        logger: StructuredLogger,
    ) -> None:
        self._event_bus = event_bus
        self._persistence = persistence
        self._logger = logger
        self._initialized = False

    async def initialize(self) -> None:
        """Run recovery checks and restore state."""
        self._initialized = True
        self._logger.info("recovery_initializing")

        crash_state = await self._detect_crash()
        if crash_state:
            self._logger.warning("crash_detected", crash_state=crash_state)
            await self._replay_events()
            await self._restore_subsystem_states()
            await self._clear_crash_state()
            self._logger.info("recovery_complete")
        else:
            self._logger.info("clean_shutdown_detected")

    async def shutdown(self) -> None:
        """Mark clean shutdown state."""
        await self._persistence.save(
            "recovery.crash_state",
            {"crashed": False, "last_clean_shutdown": datetime.now(timezone.utc).isoformat()},
        )
        self._initialized = False

    async def save_state(self) -> dict[str, Any]:
        """Serialize recovery metadata."""
        saved = await self._persistence.load("recovery.crash_state")
        return {"crash_state": saved} if saved else {"crash_state": None}

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore recovery state; run detection on initialize instead."""
        if state:
            self._initialized = True

    async def _detect_crash(self) -> dict[str, Any] | None:
        """Check if the last shutdown was clean.

        Returns:
            The crash state dict if a crash is detected, else None.
        """
        state = await self._persistence.load("recovery.crash_state")
        if state is None:
            return {"reason": "no_shutdown_record"}
        if state.get("crashed", True):
            return state
        return None

    async def _replay_events(self) -> None:
        """Replay events from the persisted history."""
        self._logger.info("replaying_events")
        state = await self._event_bus.save_state()
        for event_dict in state.get("history", []):
            event = SystemEvent.from_dict(event_dict)
            await self._event_bus.publish(event)

    async def _restore_subsystem_states(self) -> None:
        """Restore subsystem state from the last snapshot."""
        self._logger.info("restoring_subsystem_state")

        snapshot_data = await self._persistence.load("recovery.snapshot")
        if not snapshot_data:
            self._logger.info("no_snapshot_found")
            return

        states = snapshot_data.get("subsystems", {})
        for subsystem, state in states.items():
            await self._event_bus.publish(
                SystemEvent(
                    topic=f"system.recovery.state_restored.{subsystem}",
                    priority=EventPriority.HIGH,
                    payload={"subsystem": subsystem, "state": state},
                    source="recovery",
                )
            )
        self._logger.info("state_restored", subsystems=list(states.keys()))

    async def take_snapshot(
        self,
        tick_count: int,
        subsystem_states: dict[str, dict[str, Any]],
    ) -> None:
        """Create a recovery snapshot at the given tick.

        Args:
            tick_count: Current simulation tick number.
            subsystem_states: Dict of subsystem name -> serialized state.
        """
        snapshot = {
            "tick_count": tick_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subsystems": subsystem_states,
        }
        await self._persistence.save("recovery.snapshot", snapshot)
        self._logger.debug("snapshot_taken", tick=tick_count)

    async def _clear_crash_state(self) -> None:
        """Mark crash state as resolved."""
        await self._persistence.save(
            "recovery.crash_state",
            {"crashed": True, "recovered_at": datetime.now(timezone.utc).isoformat()},
        )
