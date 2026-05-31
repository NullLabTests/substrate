from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.events.bus import EventBus, EventPriority, EventSubscription, SystemEvent
from core.logging.structured_logger import StructuredLogger
from core.registry.agent_registry import AgentRegistry


@dataclass
class Fact:
    concept: str
    relation: str
    target: str
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept": self.concept,
            "relation": self.relation,
            "target": self.target,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class Episode:
    episode_type: str
    payload: dict[str, Any]
    importance: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_type": self.episode_type,
            "payload": self.payload,
            "importance": self.importance,
            "timestamp": self.timestamp,
        }


class DiscoveryAgent(ABC):
    def __init__(
        self,
        name: str,
        role: str,
        agent_id: str | None = None,
        event_bus: EventBus | None = None,
        registry: AgentRegistry | None = None,
        logger: StructuredLogger | None = None,
    ) -> None:
        self.name = name
        self.role = role
        self.agent_id = agent_id or f"discovery_{name.lower().replace(' ', '_')}_{id(self)}"
        self._event_bus = event_bus or EventBus()
        self._registry = registry or AgentRegistry()
        self._logger = logger or StructuredLogger(name=f"agent.{self.agent_id}", level="info")

        self._facts: list[Fact] = []
        self._episodes: list[Episode] = []
        self._subscriptions: list[EventSubscription] = []
        self._start_time: float = 0.0
        self._is_initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @property
    def uptime(self) -> float:
        return time.time() - self._start_time if self._start_time else 0.0

    async def initialize(self) -> None:
        await self._logger.initialize()
        self._start_time = time.time()
        self._is_initialized = True
        if self._registry:
            self._registry.register(
                agent_id=self.agent_id,
                name=self.name,
                agent_type=self.role,
                metadata={"role": self.role},
            )

    async def shutdown(self) -> None:
        self._is_initialized = False
        for sub in self._subscriptions:
            self._event_bus.unsubscribe(sub)
        self._subscriptions.clear()
        self._facts.clear()
        self._episodes.clear()

    # ── Event bus helpers ──────────────────────────────────────────

    def _subscribe(
        self,
        topic_pattern: str,
        handler: Any,
        filters: list[Any] | None = None,
        priority: EventPriority | None = None,
    ) -> EventSubscription:
        sub = self._event_bus.subscribe(
            topic_pattern=topic_pattern,
            handler=handler,
            filters=filters,
            priority=priority,
        )
        self._subscriptions.append(sub)
        return sub

    async def _publish(
        self,
        topic: str,
        payload: dict[str, Any],
        source: str | None = None,
        correlation_id: str | None = None,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        await self._event_bus.publish(
            SystemEvent(
                topic=topic,
                priority=priority,
                payload=payload,
                source=source or self.agent_id,
                correlation_id=correlation_id,
            )
        )

    # ── Memory helpers ─────────────────────────────────────────────

    def _store_fact(
        self,
        concept: str,
        relation: str,
        target: str,
        confidence: float = 0.5,
    ) -> None:
        self._facts.append(Fact(
            concept=concept,
            relation=relation,
            target=target,
            confidence=confidence,
        ))

    def _store_episode(
        self,
        episode_type: str,
        payload: dict[str, Any],
        importance: float = 0.5,
    ) -> None:
        self._episodes.append(Episode(
            episode_type=episode_type,
            payload=payload,
            importance=importance,
        ))

    def recall_facts(self, concept: str | None = None, top_k: int = 10) -> list[Fact]:
        relevant = [f for f in self._facts if concept is None or concept in f.concept]
        relevant.sort(key=lambda f: f.confidence, reverse=True)
        return relevant[:top_k]

    def recall_episodes(self, top_k: int = 10) -> list[Episode]:
        sorted_eps = sorted(self._episodes, key=lambda e: e.importance, reverse=True)
        return sorted_eps[:top_k]

    # ── Persistence ────────────────────────────────────────────────

    async def save_state(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "facts": [f.to_dict() for f in self._facts],
            "episodes": [e.to_dict() for e in self._episodes],
            "uptime": self.uptime,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        if not state:
            return
        self._facts = [Fact(**f) for f in state.get("facts", [])]
        self._episodes = [Episode(**e) for e in state.get("episodes", [])]

    # ── Abstract mission handler ───────────────────────────────────

    @abstractmethod
    async def handle_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        ...
