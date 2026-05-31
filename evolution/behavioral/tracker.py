"""Behavioral diversity tracking and metrics.

Tracks per-agent behaviors over time and computes population-level
diversity metrics to answer the research question:
"Do successful behaviors propagate through populations?"

Metrics:
  - Diversity: Shannon entropy of behavioral action distribution
  - Convergence: Rate of strategy similarity increase over time
  - Innovation: Rate of novel strategy/policy emergence
  - Extinction: Rate of strategy/lineage loss
"""

from __future__ import annotations

import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from core.events import bus


@dataclass
class BehaviorRecord:
    """A single behavioral observation for an agent."""

    agent_id: str
    action: str
    tick: int
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class DiversityMetrics:
    """Snapshot of population-level diversity metrics at a point in time."""

    tick: int
    diversity: float           # Shannon entropy of action distribution [0, log2(N)]
    normalized_diversity: float  # Diversity / max_possible [0, 1]
    convergence: float         # Rate of strategy similarity increase [0, 1]
    innovation_rate: float     # Novel strategies per tick
    extinction_rate: float     # Strategy losses per tick
    active_strategies: int     # Number of distinct strategies in population
    total_actions: int         # Total behavioral observations this period
    dominant_action: str | None = None  # Most common action in this window
    dominant_frequency: float = 0.0     # Frequency of dominant action


class BehavioralDiversity:
    """Tracks agent behaviors and computes population diversity metrics.

    Maintains a rolling window of behavioral observations and computes
    diversity statistics on configurable intervals.
    """

    def __init__(
        self,
        history_limit: int = 10_000,
        convergence_window: int = 100,
    ) -> None:
        self._history: list[BehaviorRecord] = []
        self._history_limit = history_limit
        self._convergence_window = convergence_window
        self._action_counts: Counter[str] = Counter()
        self._agent_actions: dict[str, Counter[str]] = defaultdict(Counter)
        self._strategy_ids: set[str] = set()
        self._strategy_births: dict[str, float] = {}  # strategy_id → birth time
        self._strategy_deaths: dict[str, float] = {}  # strategy_id → death time
        self._innovation_events: int = 0
        self._extinction_events: int = 0

    async def initialize(self) -> None:
        self._history.clear()
        self._action_counts.clear()

    async def shutdown(self) -> None:
        self._history.clear()

    async def save_state(self) -> dict[str, Any]:
        return {
            "action_counts": dict(self._action_counts),
            "innovation_events": self._innovation_events,
            "extinction_events": self._extinction_events,
        }

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        if not state:
            return
        self._action_counts = Counter(state.get("action_counts", {}))
        self._innovation_events = state.get("innovation_events", 0)
        self._extinction_events = state.get("extinction_events", 0)

    # ── Recording ──────────────────────────────────────────────────────

    def record_behavior(
        self,
        agent_id: str,
        action: str,
        tick: int,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record a behavioral observation for an agent."""
        record = BehaviorRecord(
            agent_id=agent_id,
            action=action,
            tick=tick,
            context=context or {},
        )
        self._history.append(record)
        if len(self._history) > self._history_limit:
            # Remove oldest record and update counters
            oldest = self._history.pop(0)
            self._action_counts[oldest.action] -= 1
            if self._action_counts[oldest.action] <= 0:
                del self._action_counts[oldest.action]

        self._action_counts[action] += 1
        self._agent_actions[agent_id][action] += 1

    def register_strategy_birth(self, strategy_id: str) -> None:
        """Register the emergence of a new strategy."""
        self._strategy_ids.add(strategy_id)
        self._strategy_births[strategy_id] = time.time()
        self._innovation_events += 1

    def register_strategy_death(self, strategy_id: str) -> None:
        """Register the extinction/loss of a strategy."""
        if strategy_id in self._strategy_ids:
            self._strategy_ids.discard(strategy_id)
        self._strategy_deaths[strategy_id] = time.time()
        self._extinction_events += 1

    # ── Metrics computation ─────────────────────────────────────────────

    def compute_diversity(self, tick: int) -> DiversityMetrics:
        """Compute current diversity metrics based on recent behavior window."""
        # Use the most recent window of actions
        window = self._history[-self._convergence_window:] if len(self._history) > self._convergence_window else self._history

        # Innovation/extinction rates are global (strategy events), not window-based
        innovation_rate = self._innovation_events / max(tick, 1)
        extinction_rate = self._extinction_events / max(tick, 1)

        if not window:
            return DiversityMetrics(
                tick=tick,
                diversity=0.0,
                normalized_diversity=0.0,
                convergence=0.0,
                innovation_rate=round(innovation_rate, 6),
                extinction_rate=round(extinction_rate, 6),
                active_strategies=0,
                total_actions=0,
            )

        # Action frequency distribution
        action_counts: Counter[str] = Counter()
        for record in window:
            action_counts[record.action] += 1

        total = sum(action_counts.values())

        # Shannon entropy: H = -sum(p_i * log2(p_i))
        entropy = 0.0
        for count in action_counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        n_types = len(action_counts)
        max_entropy = math.log2(max(n_types, 2))  # Normalize factor
        normalized = entropy / max_entropy if max_entropy > 0 else 0.0

        # Dominant action
        dominant_action, dominant_count = action_counts.most_common(1)[0]
        dominant_freq = dominant_count / total

        # Convergence: similarity to previous time window
        convergence = self._compute_convergence()

        return DiversityMetrics(
            tick=tick,
            diversity=entropy,
            normalized_diversity=round(normalized, 4),
            convergence=round(convergence, 4),
            innovation_rate=round(innovation_rate, 6),
            extinction_rate=round(extinction_rate, 6),
            active_strategies=len(self._strategy_ids),
            total_actions=total,
            dominant_action=dominant_action,
            dominant_frequency=round(dominant_freq, 4),
        )

    def _compute_convergence(self) -> float:
        """Compute behavioral convergence by comparing action distributions
        between the first and second halves of the current window.

        Returns:
            A value in [0, 1] where higher = more convergent (less diverse).
        """
        if len(self._history) < 20:
            return 0.0

        mid = len(self._history) // 2
        first_half = self._history[:mid]
        second_half = self._history[mid:]

        # Get action sets
        first_actions: Counter[str] = Counter()
        for r in first_half:
            first_actions[r.action] += 1

        second_actions: Counter[str] = Counter()
        for r in second_half:
            second_actions[r.action] += 1

        # Jaccard similarity between action sets
        all_actions = set(first_actions.keys()) | set(second_actions.keys())
        if not all_actions:
            return 0.0

        # Weighted overlap
        overlap = 0.0
        for action in all_actions:
            f = first_actions.get(action, 0)
            s = second_actions.get(action, 0)
            if f > 0 and s > 0:
                overlap += min(f, s) / max(f, s)

        similarity = overlap / len(all_actions) if all_actions else 0.0

        # Convergence is the rate of similarity increase.
        # For a single snapshot, we report the current similarity as a proxy.
        return similarity

    def compute_agent_diversity(self, agent_id: str) -> float:
        """Compute behavioral entropy for a single agent."""
        action_counts = self._agent_actions.get(agent_id, Counter())
        total = sum(action_counts.values())
        if total == 0:
            return 0.0

        entropy = 0.0
        for count in action_counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        n_types = len(action_counts)
        max_entropy = math.log2(max(n_types, 2))
        return entropy / max_entropy if max_entropy > 0 else 0.0

    # ── Reporting ───────────────────────────────────────────────────────

    @property
    def total_observations(self) -> int:
        return len(self._history)

    @property
    def action_distribution(self) -> dict[str, int]:
        return dict(self._action_counts)

    @property
    def active_strategy_count(self) -> int:
        return len(self._strategy_ids)

    @property
    def innovation_count(self) -> int:
        return self._innovation_events

    @property
    def extinction_count(self) -> int:
        return self._extinction_events
