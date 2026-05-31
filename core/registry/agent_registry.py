"""Agent registry tracking all active agents with metadata."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AgentStatus:
    CREATED = "created"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class AgentMetadata(BaseModel):
    """Immutable metadata for a registered agent."""

    id: str
    name: str
    agent_type: str = Field(alias="type")
    status: str = AgentStatus.CREATED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "frozen": False}

    def touch(self) -> None:
        """Update last_seen to now."""
        self.last_seen = datetime.now(timezone.utc).isoformat()


class AgentRegistry:
    """Tracks all active agents in the simulation.

    Supports registration, lookup by ID, heartbeat (last_seen update),
    status transitions, and listing with optional filters.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentMetadata] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Prepare the registry for operation."""
        self._initialized = True

    async def shutdown(self) -> None:
        """Clear the registry and release resources."""
        self._agents.clear()
        self._initialized = False

    async def save_state(self) -> dict[str, Any]:
        """Serialize all agent metadata for persistence."""
        return {
            "agents": {aid: meta.model_dump() for aid, meta in self._agents.items()}
        }

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore agent registry from serialized state."""
        if not state:
            return
        for aid, data in state.get("agents", {}).items():
            self._agents[aid] = AgentMetadata(**data)

    def register(
        self,
        agent_id: str,
        name: str,
        agent_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> AgentMetadata:
        """Register a new agent in the registry.

        Args:
            agent_id: Unique identifier for the agent.
            name: Human-readable name.
            agent_type: Classification type (e.g. 'worker', 'coordinator').
            metadata: Optional additional key-value payload.

        Returns:
            The newly created AgentMetadata instance.

        Raises:
            ValueError: If an agent with the same ID already exists.
        """
        if agent_id in self._agents:
            raise ValueError(f"Agent '{agent_id}' is already registered.")

        meta = AgentMetadata(
            id=agent_id,
            name=name,
            type=agent_type,
            metadata=metadata or {},
        )
        self._agents[agent_id] = meta
        return meta

    def unregister(self, agent_id: str) -> AgentMetadata | None:
        """Remove an agent from the registry.

        Args:
            agent_id: The agent to remove.

        Returns:
            The removed AgentMetadata, or None if not found.
        """
        return self._agents.pop(agent_id, None)

    def get(self, agent_id: str) -> AgentMetadata | None:
        """Look up an agent by ID.

        Args:
            agent_id: The agent identifier.

        Returns:
            AgentMetadata if found, else None.
        """
        return self._agents.get(agent_id)

    def set_status(self, agent_id: str, status: str) -> AgentMetadata | None:
        """Transition an agent to a new status.

        Args:
            agent_id: The agent to update.
            status: One of AgentStatus constants.

        Returns:
            Updated AgentMetadata, or None if not found.
        """
        meta = self._agents.get(agent_id)
        if meta is None:
            return None
        meta.status = status
        meta.touch()
        return meta

    async def heartbeat(self, agent_id: str) -> bool:
        """Record a heartbeat for the given agent.

        Args:
            agent_id: The agent to update.

        Returns:
            True if the agent was found and updated, False otherwise.
        """
        meta = self._agents.get(agent_id)
        if meta is None:
            return False
        meta.touch()
        return True

    async def heartbeat_all(self) -> None:
        """Update last_seen for every registered agent."""
        now_ts = datetime.now(timezone.utc).isoformat()
        for meta in self._agents.values():
            meta.last_seen = now_ts

    def list_agents(
        self,
        status: str | None = None,
        agent_type: str | None = None,
    ) -> list[AgentMetadata]:
        """List registered agents, optionally filtered.

        Args:
            status: If set, only return agents with this status.
            agent_type: If set, only return agents of this type.

        Returns:
            List of matching AgentMetadata objects.
        """
        results = list(self._agents.values())
        if status:
            results = [a for a in results if a.status == status]
        if agent_type:
            results = [a for a in results if a.agent_type == agent_type]
        return results

    @property
    def count(self) -> int:
        """Total number of registered agents."""
        return len(self._agents)

    @property
    def active_count(self) -> int:
        """Number of agents with ACTIVE status."""
        return sum(1 for a in self._agents.values() if a.status == AgentStatus.ACTIVE)
