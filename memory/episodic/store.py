from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from core.events import bus


def _new_id() -> str:
    return secrets.token_hex(16)


@dataclass
class Episode:
    id: str = field(default_factory=_new_id)
    timestamp: float = field(default_factory=time.time)
    type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5

    @property
    def age(self) -> float:
        return time.time() - self.timestamp


class EpisodicMemory:
    def __init__(self, max_episodes: int = 1000, forgetting_threshold: float = 3600.0) -> None:
        self._store: dict[str, list[Episode]] = {}
        self._max_episodes: int = max_episodes
        self._forgetting_threshold: float = forgetting_threshold

    def store(self, agent_id: str, episode: Episode) -> None:
        self._store.setdefault(agent_id, []).append(episode)
        if len(self._store[agent_id]) > self._max_episodes:
            removed = self._store[agent_id].pop(0)
            bus.emit("memory.episodic.forget", agent_id, {
                "episode_id": removed.id,
                "reason": "max_capacity",
            })
        bus.emit("memory.episodic.store", agent_id, {
            "episode_id": episode.id,
            "type": episode.type,
            "importance": episode.importance,
        })

    def recall(
        self, agent_id: str, query: str | None = None, limit: int = 10
    ) -> list[Episode]:
        episodes = self._store.get(agent_id, [])
        if not episodes:
            return []
        if query:
            query_lower = query.lower()
            episodes = [
                e for e in episodes
                if query_lower in e.type.lower()
                or query_lower in str(e.payload).lower()
            ]
        episodes.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
        bus.emit("memory.episodic.recall", agent_id, {
            "query": query,
            "limit": limit,
            "results": len(episodes[:limit]),
        })
        return episodes[:limit]

    def age(self) -> int:
        now = time.time()
        forgotten = 0
        for agent_id in list(self._store.keys()):
            self._store[agent_id] = [
                e for e in self._store[agent_id]
                if (now - e.timestamp) < self._forgetting_threshold
            ]
            forgotten += 1
        bus.emit("memory.episodic.age", None, {
            "forgotten": forgotten,
            "threshold": self._forgetting_threshold,
        })
        return forgotten

    def forget(self, threshold: float | None = None) -> int:
        if threshold is not None:
            self._forgetting_threshold = threshold
        return self.age()

    def get_all_episodes(self, agent_id: str) -> list[Episode]:
        return self._store.get(agent_id, [])

    def clear_agent(self, agent_id: str) -> None:
        self._store.pop(agent_id, None)
