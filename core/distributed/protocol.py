from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    TICK_ASSIGNMENT = "tick_assignment"
    TICK_RESULT = "tick_result"
    AGENT_ACTION = "agent_action"
    AGENT_ACTION_RESULT = "agent_action_result"
    HEARTBEAT = "heartbeat"
    SYNC_STATE = "sync_state"
    SHUTDOWN = "shutdown"
    REGISTER_WORKER = "register_worker"
    WORKER_READY = "worker_ready"
    COORDINATOR_ELECTION = "coordinator_election"
    GLOBAL_EVENT = "global_event"


@dataclass
class DistributedMessage:
    msg_type: MessageType
    source_id: str
    destination_id: str
    payload: dict[str, Any]
    correlation_id: str | None = None
    tick: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "msg_type": self.msg_type.value,
            "source_id": self.source_id,
            "destination_id": self.destination_id,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "tick": self.tick,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DistributedMessage:
        return cls(
            msg_type=MessageType(data["msg_type"]),
            source_id=data["source_id"],
            destination_id=data["destination_id"],
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id"),
            tick=data.get("tick"),
        )


@dataclass
class TickAssignment:
    worker_id: str
    tick: int
    agent_ids: list[str]
    global_state_snapshot: dict[str, Any] = field(default_factory=dict)
    seed_derivation: int | None = None
    timeout_seconds: float = 30.0

    def to_message(self, coordinator_id: str) -> DistributedMessage:
        return DistributedMessage(
            msg_type=MessageType.TICK_ASSIGNMENT,
            source_id=coordinator_id,
            destination_id=self.worker_id,
            payload={
                "tick": self.tick,
                "agent_ids": self.agent_ids,
                "global_state_snapshot": self.global_state_snapshot,
                "seed_derivation": self.seed_derivation,
                "timeout_seconds": self.timeout_seconds,
            },
            tick=self.tick,
        )

    @classmethod
    def from_message(cls, msg: DistributedMessage) -> TickAssignment:
        return cls(
            worker_id=msg.destination_id,
            tick=msg.payload["tick"],
            agent_ids=msg.payload["agent_ids"],
            global_state_snapshot=msg.payload.get("global_state_snapshot", {}),
            seed_derivation=msg.payload.get("seed_derivation"),
            timeout_seconds=msg.payload.get("timeout_seconds", 30.0),
        )


@dataclass
class TickResult:
    worker_id: str
    tick: int
    agent_results: dict[str, dict[str, Any]]
    local_events: list[dict[str, Any]]
    success: bool
    error: str | None = None
    duration_ms: float = 0.0

    def to_message(self) -> DistributedMessage:
        return DistributedMessage(
            msg_type=MessageType.TICK_RESULT,
            source_id=self.worker_id,
            destination_id="coordinator",
            payload={
                "tick": self.tick,
                "agent_results": self.agent_results,
                "local_events": self.local_events,
                "success": self.success,
                "error": self.error,
                "duration_ms": self.duration_ms,
            },
            tick=self.tick,
        )


@dataclass
class AgentAction:
    action_id: str
    agent_id: str
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_worker: str | None = None

    def to_message(self, destination: str) -> DistributedMessage:
        return DistributedMessage(
            msg_type=MessageType.AGENT_ACTION,
            source_id=self.source_worker or "",
            destination_id=destination,
            payload={
                "action_id": self.action_id,
                "agent_id": self.agent_id,
                "action_type": self.action_type,
                "payload": self.payload,
            },
        )


@dataclass
class AgentActionResult:
    action_id: str
    agent_id: str
    success: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    source_worker: str | None = None

    def to_message(self, destination: str) -> DistributedMessage:
        return DistributedMessage(
            msg_type=MessageType.AGENT_ACTION_RESULT,
            source_id=self.source_worker or "",
            destination_id=destination,
            payload={
                "action_id": self.action_id,
                "agent_id": self.agent_id,
                "success": self.success,
                "result": self.result,
                "error": self.error,
            },
        )


@dataclass
class Heartbeat:
    node_id: str
    node_type: str
    tick: int
    load: float
    alive: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> DistributedMessage:
        return DistributedMessage(
            msg_type=MessageType.HEARTBEAT,
            source_id=self.node_id,
            destination_id="coordinator",
            payload={
                "node_type": self.node_type, "tick": self.tick,
                "load": self.load, "alive": self.alive, "extra": self.extra,
            },
            tick=self.tick,
        )


@dataclass
class SyncState:
    state_snapshot: dict[str, Any]
    tick: int
    source_worker: str

    def to_message(self, destination: str) -> DistributedMessage:
        return DistributedMessage(
            msg_type=MessageType.SYNC_STATE,
            source_id=self.source_worker,
            destination_id=destination,
            payload={"state_snapshot": self.state_snapshot, "tick": self.tick},
            tick=self.tick,
        )
