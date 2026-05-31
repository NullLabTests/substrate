from __future__ import annotations
import time
from typing import Any

from core.events import bus


class ReputationSystem:
    def __init__(self) -> None:
        self._global_reputation: dict[str, float] = {}
        self._pairwise_ratings: dict[tuple[str, str], list[float]] = {}
        self._adjustment_log: list[dict[str, Any]] = []

    def get_reputation(self, agent_id: str) -> float:
        return self._global_reputation.get(agent_id, 0.0)

    def adjust(self, agent_id: str, delta: float, reason: str) -> float:
        old = self._global_reputation.get(agent_id, 0.0)
        self._global_reputation[agent_id] = old + delta
        entry = {
            "agent_id": agent_id,
            "delta": delta,
            "reason": reason,
            "old": old,
            "new": self._global_reputation[agent_id],
            "timestamp": time.time(),
        }
        self._adjustment_log.append(entry)
        bus.emit("reputation.adjust", agent_id, entry)
        return self._global_reputation[agent_id]

    def rate(self, from_id: str, to_id: str, score: float) -> None:
        score = max(-1.0, min(1.0, score))
        key = (from_id, to_id)
        self._pairwise_ratings.setdefault(key, []).append(score)
        self.adjust(to_id, score * 0.1, f"rated_by_{from_id}")
        bus.emit("reputation.rate", from_id, {
            "from": from_id,
            "to": to_id,
            "score": score,
        })

    def get_rating(self, from_id: str, to_id: str) -> float:
        scores = self._pairwise_ratings.get((from_id, to_id), [])
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def get_all_reputations(self) -> dict[str, float]:
        return dict(self._global_reputation)

    def get_adjustment_log(
        self, agent_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if agent_id is None:
            return self._adjustment_log[-limit:]
        return [e for e in self._adjustment_log if e["agent_id"] == agent_id][-limit:]
