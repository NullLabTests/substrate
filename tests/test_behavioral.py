"""Tests for the behavioral diversity tracker."""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio

from evolution.behavioral.tracker import BehavioralDiversity, DiversityMetrics


@pytest_asyncio.fixture
async def tracker() -> AsyncGenerator[BehavioralDiversity, None]:
    bt = BehavioralDiversity(history_limit=100, convergence_window=50)
    await bt.initialize()
    yield bt
    await bt.shutdown()


class TestBehaviorRecording:
    """Tests for recording behavioral observations."""

    async def test_record_single_behavior(self, tracker: BehavioralDiversity) -> None:
        tracker.record_behavior("agent-1", "explore", tick=1)
        assert tracker.total_observations == 1

    async def test_record_multiple_agents(self, tracker: BehavioralDiversity) -> None:
        tracker.record_behavior("agent-1", "explore", tick=1)
        tracker.record_behavior("agent-2", "rest", tick=1)
        tracker.record_behavior("agent-1", "harvest", tick=2)
        assert tracker.total_observations == 3

    async def test_record_with_context(self, tracker: BehavioralDiversity) -> None:
        tracker.record_behavior("agent-1", "trade", tick=5, context={"partner": "agent-2"})
        assert tracker.total_observations == 1

    async def test_history_limit(self, tracker: BehavioralDiversity) -> None:
        """History should not exceed the configured limit."""
        for i in range(200):
            tracker.record_behavior(f"agent-{i % 10}", f"action_{i % 5}", tick=i)
        assert tracker.total_observations <= 100  # history_limit=100


class TestDiversityMetrics:
    """Tests for diversity metrics computation."""

    async def test_diversity_with_single_action(self, tracker: BehavioralDiversity) -> None:
        for i in range(50):
            tracker.record_behavior("agent-1", "explore", tick=i)
        metrics = tracker.compute_diversity(tick=50)
        assert metrics.diversity == 0.0  # Zero entropy for a single action
        assert metrics.normalized_diversity == 0.0

    async def test_diversity_with_two_actions(self, tracker: BehavioralDiversity) -> None:
        for i in range(50):
            action = "explore" if i % 2 == 0 else "rest"
            tracker.record_behavior("agent-1", action, tick=i)
        metrics = tracker.compute_diversity(tick=50)
        assert metrics.diversity > 0.0  # Non-zero entropy
        assert metrics.normalized_diversity > 0.0

    async def test_diversity_with_equal_distribution(self, tracker: BehavioralDiversity) -> None:
        """Equal distribution of 4 actions should give max entropy."""
        actions = ["explore", "rest", "harvest", "trade"]
        for i in range(40):
            tracker.record_behavior("agent-1", actions[i % 4], tick=i)
        metrics = tracker.compute_diversity(tick=40)
        # log2(4) = 2.0 is max entropy
        assert metrics.diversity > 1.5
        assert metrics.normalized_diversity > 0.9

    async def test_dominant_action(self, tracker: BehavioralDiversity) -> None:
        # convergence_window=50, so only last 50 records are in the window.
        # First 50: all "explore"; records 50-89: "explore" (40); records 90-99: "rest" (10)
        # => explore freq = 40/50 = 0.8 > 0.7
        for i in range(100):
            action = "explore" if i < 90 else "rest"
            tracker.record_behavior("agent-1", action, tick=i)
        metrics = tracker.compute_diversity(tick=100)
        assert metrics.dominant_action == "explore"
        assert metrics.dominant_frequency > 0.7

    async def test_diversity_empty_history(self, tracker: BehavioralDiversity) -> None:
        metrics = tracker.compute_diversity(tick=0)
        assert metrics.diversity == 0.0
        assert metrics.active_strategies == 0
        assert metrics.total_actions == 0

    async def test_total_actions_in_metrics(self, tracker: BehavioralDiversity) -> None:
        for i in range(30):
            tracker.record_behavior("agent-1", "explore", tick=i)
        metrics = tracker.compute_diversity(tick=30)
        assert metrics.total_actions == 30


class TestStrategyRegistration:
    """Tests for strategy birth/death tracking."""

    async def test_register_strategy_birth(self, tracker: BehavioralDiversity) -> None:
        tracker.register_strategy_birth("strat-1")
        assert tracker.active_strategy_count == 1
        assert tracker.innovation_count == 1

    async def test_register_strategy_death(self, tracker: BehavioralDiversity) -> None:
        tracker.register_strategy_birth("strat-1")
        tracker.register_strategy_death("strat-1")
        assert tracker.active_strategy_count == 0
        assert tracker.extinction_count == 1

    async def test_strategy_multiple_births(self, tracker: BehavioralDiversity) -> None:
        for i in range(5):
            tracker.register_strategy_birth(f"strat-{i}")
        assert tracker.active_strategy_count == 5
        assert tracker.innovation_count == 5

    async def test_innovation_rate(self, tracker: BehavioralDiversity) -> None:
        for i in range(3):
            tracker.register_strategy_birth(f"s{i}")
        metrics = tracker.compute_diversity(tick=100)
        assert metrics.innovation_rate > 0.0

    async def test_extinction_rate(self, tracker: BehavioralDiversity) -> None:
        tracker.register_strategy_birth("s1")
        tracker.register_strategy_death("s1")
        metrics = tracker.compute_diversity(tick=100)
        assert metrics.extinction_rate > 0.0


class TestAgentDiversity:
    """Tests for per-agent diversity computation."""

    async def test_agent_diversity_single_action(self, tracker: BehavioralDiversity) -> None:
        for i in range(10):
            tracker.record_behavior("agent-1", "explore", tick=i)
        div = tracker.compute_agent_diversity("agent-1")
        assert div == 0.0

    async def test_agent_diversity_multiple_actions(self, tracker: BehavioralDiversity) -> None:
        for i in range(20):
            action = "explore" if i % 2 == 0 else "rest"
            tracker.record_behavior("agent-1", action, tick=i)
        div = tracker.compute_agent_diversity("agent-1")
        assert div > 0.0

    async def test_agent_diversity_no_data(self, tracker: BehavioralDiversity) -> None:
        div = tracker.compute_agent_diversity("nonexistent")
        assert div == 0.0


class TestActionDistribution:
    """Tests for action distribution reporting."""

    async def test_action_distribution(self, tracker: BehavioralDiversity) -> None:
        tracker.record_behavior("a1", "explore", tick=1)
        tracker.record_behavior("a1", "explore", tick=2)
        tracker.record_behavior("a1", "rest", tick=3)
        dist = tracker.action_distribution
        assert dist["explore"] == 2
        assert dist["rest"] == 1

    async def test_action_distribution_empty(self, tracker: BehavioralDiversity) -> None:
        assert tracker.action_distribution == {}

    async def test_convergence(self, tracker: BehavioralDiversity) -> None:
        """Convergence should be higher when actions are increasingly similar."""
        # Record two phases: first half varied, then all same action
        for i in range(30):
            tracker.record_behavior("a1", ["explore", "rest"][i % 2], tick=i)
        for i in range(30):
            tracker.record_behavior("a1", "explore", tick=30 + i)
        metrics = tracker.compute_diversity(tick=60)
        # Convergence should be non-zero
        assert isinstance(metrics.convergence, float)


class TestBehavioralState:
    """Tests for save/load state."""

    async def test_save_and_load_state(self, tracker: BehavioralDiversity) -> None:
        tracker.record_behavior("a1", "explore", tick=1)
        tracker.record_behavior("a1", "rest", tick=2)
        tracker.register_strategy_birth("s1")
        tracker.register_strategy_birth("s2")
        tracker.register_strategy_death("s1")

        state = await tracker.save_state()
        assert "action_counts" in state
        assert state["innovation_events"] == 2
        assert state["extinction_events"] == 1

        new_tracker = BehavioralDiversity()
        await new_tracker.load_state(state)
        assert new_tracker.innovation_count == 2
        assert new_tracker.extinction_count == 1

    async def test_load_empty_state(self, tracker: BehavioralDiversity) -> None:
        await tracker.load_state(None)
        assert tracker.total_observations == 0
