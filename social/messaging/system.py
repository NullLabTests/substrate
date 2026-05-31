from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import bus


def _new_id() -> str:
    return secrets.token_hex(16)


class Priority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    id: str = field(default_factory=_new_id)
    from_id: str = ""
    to_id: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    priority: Priority = Priority.NORMAL


class MessagingSystem:
    def __init__(self) -> None:
        self._inboxes: dict[str, list[Message]] = {}
        self._history: dict[str, list[Message]] = {}

    def send(
        self, from_id: str, to_id: str, content: str, priority: Priority = Priority.NORMAL
    ) -> Message:
        msg = Message(
            from_id=from_id,
            to_id=to_id,
            content=content,
            priority=priority,
        )
        self._inboxes.setdefault(to_id, []).append(msg)
        self._history.setdefault(from_id, []).append(msg)
        bus.emit("message.send", from_id, {
            "message_id": msg.id,
            "to_id": to_id,
            "priority": priority.value,
            "content_length": len(content),
        })
        return msg

    def receive(self, agent_id: str) -> list[Message]:
        msgs = self._inboxes.pop(agent_id, [])
        msgs.sort(key=lambda m: (m.priority.value, m.timestamp), reverse=True)
        bus.emit("message.receive", agent_id, {
            "count": len(msgs),
        })
        return msgs

    def broadcast(self, from_id: str, content: str, priority: Priority = Priority.NORMAL) -> list[Message]:
        msgs: list[Message] = []
        bus.emit("message.broadcast", from_id, {
            "content_length": len(content),
            "priority": priority.value,
            "target_count": "all",
        })
        return msgs

    def get_history(self, agent_id: str, limit: int = 50) -> list[Message]:
        msgs = self._history.get(agent_id, [])
        return msgs[-limit:]

    def get_inbox_size(self, agent_id: str) -> int:
        return len(self._inboxes.get(agent_id, []))
