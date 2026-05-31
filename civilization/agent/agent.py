from __future__ import annotations
import secrets
import time
from enum import Enum
from typing import Any

from core.events import bus


def _new_id() -> str:
    return secrets.token_hex(16)


class AgentStatus(Enum):
    ALIVE = "alive"
    DEAD = "dead"
    IDLE = "idle"
    BUSY = "busy"


class Agent:
    def __init__(
        self,
        name: str | None = None,
        agent_id: str | None = None,
        energy: float = 100.0,
        position: tuple[int, int] = (0, 0),
    ) -> None:
        self.agent_id: str = agent_id or _new_id()
        self.name: str = name or f"Agent-{self.agent_id[:8]}"
        self.energy: float = energy
        self.position: tuple[int, int] = position
        self.memory_refs: list[str] = []
        self.tool_refs: list[str] = []
        self.status: AgentStatus = AgentStatus.ALIVE
        self.traits: dict[str, float] = {
            "energy_efficiency": 1.0,
            "harvest_rate": 1.0,
            "social_aptitude": 1.0,
            "memory_capacity": 1.0,
        }
        self._birth_tick: int = 0
        self._death_tick: int | None = None

        bus.emit("agent.spawn", self.agent_id, {
            "name": self.name,
            "energy": self.energy,
            "position": list(self.position),
            "traits": self.traits,
        })

    def act(self, tick: int) -> dict[str, Any]:
        if self.status == AgentStatus.DEAD:
            return {"agent_id": self.agent_id, "action": "none", "reason": "dead"}
        self.status = AgentStatus.BUSY
        action: dict[str, Any] = {
            "agent_id": self.agent_id,
            "tick": tick,
            "energy": self.energy,
            "position": list(self.position),
            "action": "idle",
        }
        bus.emit("agent.act", self.agent_id, action)
        self.status = AgentStatus.IDLE
        return action

    def perceive(self, world_state: dict[str, Any]) -> dict[str, Any]:
        perception = {
            "agent_id": self.agent_id,
            "world_state": world_state,
            "timestamp": time.time(),
        }
        bus.emit("agent.perceive", self.agent_id, perception)
        return perception

    def communicate(self, message: dict[str, Any]) -> dict[str, Any]:
        msg = {
            "agent_id": self.agent_id,
            "message": message,
            "timestamp": time.time(),
        }
        bus.emit("agent.communicate", self.agent_id, msg)
        return msg

    def reproduce(self) -> Agent | None:
        if self.status == AgentStatus.DEAD:
            return None
        child = Agent(
            name=f"{self.name}-child",
            energy=self.energy * 0.3,
            position=(self.position[0] + 1, self.position[1] + 1),
        )
        child._birth_tick = self._birth_tick + 1
        return child

    def die(self) -> None:
        self.status = AgentStatus.DEAD
        self._death_tick = self._birth_tick
        bus.emit("agent.die", self.agent_id, {
            "energy": self.energy,
            "position": list(self.position),
            "traits": self.traits,
        })

    @property
    def is_alive(self) -> bool:
        return self.status != AgentStatus.DEAD

    def __repr__(self) -> str:
        return f"Agent(id={self.agent_id[:8]}, name={self.name}, energy={self.energy:.1f}, status={self.status.value})"
