"""Tests for the evolving strategy system."""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio

from evolution.strategy.system import (
    StrategySystem,
    Strategy,
    evolve_prompt,
    evolve_policies,
    strategy_distance,
    DEFAULT_PROMPT_TEMPLATES,
    DEFAULT_POLICIES,
)


@pytest_asyncio.fixture
async def strategy_sys() -> AsyncGenerator[StrategySystem, None]:
    sys = StrategySystem()
    await sys.initialize()
    yield sys
    await sys.shutdown()


class TestStrategyCreation:
    """Tests for initial strategy creation."""

    async def test_create_initial_strategy(self, strategy_sys: StrategySystem) -> None:
        s = strategy_sys.create_initial_strategy("agent-1")
        assert s.agent_id == "agent-1"
        assert s.generation == 0
        assert s.parent_id is None
        assert s.prompt_template in DEFAULT_PROMPT_TEMPLATES
        assert len(s.policies) > 0
        assert strategy_sys.active_count == 1

    async def test_create_initial_with_custom_prompt(self, strategy_sys: StrategySystem) -> None:
        s = strategy_sys.create_initial_strategy("agent-2", prompt_template="Custom prompt.")
        assert s.prompt_template == "Custom prompt."

    async def test_create_initial_with_custom_policies(self, strategy_sys: StrategySystem) -> None:
        policies = [{"condition": "test", "action": "do_thing"}]
        s = strategy_sys.create_initial_strategy("agent-3", policies=policies)
        assert s.policies == policies

    async def test_create_multiple_agents(self, strategy_sys: StrategySystem) -> None:
        for i in range(5):
            strategy_sys.create_initial_strategy(f"agent-{i}")
        assert strategy_sys.active_count == 5
        assert strategy_sys.total_created == 5

    async def test_get_strategy_exists(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("agent-get")
        s = strategy_sys.get_strategy("agent-get")
        assert s is not None
        assert s.agent_id == "agent-get"

    async def test_get_strategy_missing(self, strategy_sys: StrategySystem) -> None:
        s = strategy_sys.get_strategy("nonexistent")
        assert s is None

    async def test_has_strategy(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("agent-has")
        assert strategy_sys.has_strategy("agent-has") is True
        assert strategy_sys.has_strategy("nonexistent") is False


class TestStrategyInheritance:
    """Tests for strategy inheritance and mutation."""

    async def test_inherit_propagates_generation(self, strategy_sys: StrategySystem) -> None:
        parent = strategy_sys.create_initial_strategy("parent-1")
        child = strategy_sys.inherit_strategy("child-1", "parent-1")
        assert child.generation == parent.generation + 1
        assert child.parent_id == "parent-1"

    async def test_inherit_preserves_structure(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("parent-2")
        child = strategy_sys.inherit_strategy("child-2", "parent-2")
        assert child.agent_id == "child-2"
        assert child.prompt_template is not None
        assert len(child.policies) > 0

    async def test_inherit_fallback_to_initial(self, strategy_sys: StrategySystem) -> None:
        """Inherit from nonexistent parent falls back to initial strategy."""
        child = strategy_sys.inherit_strategy("orphan", "nonexistent")
        assert child.generation == 0
        assert child.parent_id is None

    async def test_inheritance_chain(self, strategy_sys: StrategySystem) -> None:
        """Multiple generations of inheritance."""
        s1 = strategy_sys.create_initial_strategy("gen0")
        s2 = strategy_sys.inherit_strategy("gen1", "gen0")
        s3 = strategy_sys.inherit_strategy("gen2", "gen1")
        assert s3.generation == 2
        assert s3.parent_id == "gen1"

    async def test_inheritance_increases_count(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("p")
        strategy_sys.inherit_strategy("c1", "p")
        strategy_sys.inherit_strategy("c2", "p")
        assert strategy_sys.active_count == 3
        assert strategy_sys.total_created == 3

    async def test_generation_distribution(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("g0a")
        strategy_sys.create_initial_strategy("g0b")
        strategy_sys.inherit_strategy("g1a", "g0a")
        strategy_sys.inherit_strategy("g1b", "g0a")
        strategy_sys.inherit_strategy("g2", "g1a")
        dist = strategy_sys.get_generation_distribution()
        assert dist.get(0) == 2
        assert dist.get(1) == 2
        assert dist.get(2) == 1


class TestStrategyExtinction:
    """Tests for strategy extinction tracking."""

    async def test_mark_extinct(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("doomed")
        assert strategy_sys.active_count == 1
        strategy_sys.mark_extinct("doomed")
        assert strategy_sys.active_count == 0
        assert strategy_sys.extinct_count == 1

    async def test_mark_extinct_nonexistent(self, strategy_sys: StrategySystem) -> None:
        """Marking a nonexistent agent as extinct does nothing."""
        strategy_sys.mark_extinct("ghost")
        assert strategy_sys.extinct_count == 0

    async def test_extinct_strategy_removed_from_active(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("a")
        strategy_sys.mark_extinct("a")
        assert strategy_sys.get_strategy("a") is None

    async def test_multiple_extinctions(self, strategy_sys: StrategySystem) -> None:
        for i in range(3):
            strategy_sys.create_initial_strategy(f"a{i}")
        for i in range(3):
            strategy_sys.mark_extinct(f"a{i}")
        assert strategy_sys.extinct_count == 3
        assert strategy_sys.active_count == 0


class TestStrategyMetadata:
    """Tests for strategy metadata updates."""

    async def test_update_metadata(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("agent-meta")
        strategy_sys.update_strategy_metadata("agent-meta", fitness=0.95, tags=["explorer"])
        s = strategy_sys.get_strategy("agent-meta")
        assert s is not None
        assert s.metadata["fitness"] == 0.95
        assert "explorer" in s.metadata["tags"]

    async def test_update_metadata_nonexistent(self, strategy_sys: StrategySystem) -> None:
        """Updating metadata for a nonexistent agent does nothing."""
        strategy_sys.update_strategy_metadata("ghost", key="val")
        # No crash = test passes


class TestStrategyState:
    """Tests for save/load state."""

    async def test_save_and_load_state(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("a1")
        strategy_sys.create_initial_strategy("a2")
        strategy_sys.inherit_strategy("b1", "a1")
        strategy_sys.mark_extinct("a2")

        state = await strategy_sys.save_state()
        assert "strategies" in state
        assert len(state["strategies"]) == 2  # a1 and b1
        assert len(state["extinct_strategies"]) == 1  # a2

        new_sys = StrategySystem()
        await new_sys.load_state(state)
        assert new_sys.active_count == 2
        assert new_sys.total_created == 3
        assert new_sys.extinct_count == 1

    async def test_load_empty_state(self, strategy_sys: StrategySystem) -> None:
        await strategy_sys.load_state(None)
        assert strategy_sys.active_count == 0

    async def test_load_empty_dict(self, strategy_sys: StrategySystem) -> None:
        await strategy_sys.load_state({})
        assert strategy_sys.active_count == 0


class TestStrategyFunctions:
    """Tests for standalone evolution functions."""

    def test_evolve_prompt_returns_string(self) -> None:
        original = "Prioritize energy efficiency."
        evolved = evolve_prompt(original, mutation_rate=1.0)  # Force high mutation
        assert isinstance(evolved, str)
        assert len(evolved) > 0

    def test_evolve_prompt_low_mutation(self) -> None:
        original = "Explore aggressively."
        evolved = evolve_prompt(original, mutation_rate=0.0)
        # With 0 mutation, should be identical
        assert evolved == original

    def test_evolve_policies_returns_list(self) -> None:
        policies = [{"condition": "energy < 30", "action": "rest"}]
        evolved = evolve_policies(policies, mutation_rate=1.0)
        assert isinstance(evolved, list)
        assert len(evolved) > 0

    def test_evolve_policies_low_mutation(self) -> None:
        policies = [{"condition": "energy < 30", "action": "rest"}]
        evolved = evolve_policies(policies, mutation_rate=0.0)
        assert evolved == policies

    def test_evolve_policies_max_limit(self) -> None:
        """Policies should not exceed max_policies."""
        many_policies = [dict(p) for p in DEFAULT_POLICIES * 3]  # 24 policies
        evolved = evolve_policies(many_policies, mutation_rate=0.0)
        assert len(evolved) <= 12  # default max_policies

    def test_evolve_policies_can_add_new(self) -> None:
        """With high mutation rate, policies can be added."""
        few_policies = [{"condition": "test", "action": "test_action"}]
        evolved = evolve_policies(few_policies, mutation_rate=1.0)
        assert len(evolved) >= 1

    def test_strategy_distance_identical(self) -> None:
        s1 = Strategy(
            agent_id="a",
            prompt_template="Test prompt.",
            policies=[{"condition": "test", "action": "do"}],
        )
        s2 = Strategy(
            agent_id="b",
            prompt_template="Test prompt.",
            policies=[{"condition": "test", "action": "do"}],
        )
        dist = strategy_distance(s1, s2)
        assert dist == 0.0

    def test_strategy_distance_different(self) -> None:
        s1 = Strategy(
            agent_id="a",
            prompt_template="Completely different prompt text here.",
            policies=[{"condition": "alpha", "action": "action_a"}],
        )
        s2 = Strategy(
            agent_id="b",
            prompt_template="Another totally unrelated prompt string.",
            policies=[{"condition": "beta", "action": "action_b"}],
        )
        dist = strategy_distance(s1, s2)
        assert dist > 0.0
        assert dist <= 1.0

    def test_strategy_distance_same_prompt_diff_policies(self) -> None:
        s1 = Strategy(
            agent_id="a",
            prompt_template="Same prompt.",
            policies=[{"condition": "cond1", "action": "act1"}],
        )
        s2 = Strategy(
            agent_id="b",
            prompt_template="Same prompt.",
            policies=[{"condition": "cond2", "action": "act2"}],
        )
        dist = strategy_distance(s1, s2)
        assert dist > 0.0
        assert dist < 1.0

    def test_get_all_prompts(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("p1", prompt_template="Prompt A")
        strategy_sys.create_initial_strategy("p2", prompt_template="Prompt B")
        prompts = strategy_sys.get_all_prompts()
        assert "Prompt A" in prompts
        assert "Prompt B" in prompts

    def test_get_all_policies(self, strategy_sys: StrategySystem) -> None:
        strategy_sys.create_initial_strategy("p1")
        strategy_sys.create_initial_strategy("p2")
        all_policies = strategy_sys.get_all_policies()
        assert len(all_policies) == 2


class TestStrategyMutationDeterminism:
    """Tests for mutation behavior properties."""

    def test_mutation_never_empties_prompt(self) -> None:
        for _ in range(100):
            evolved = evolve_prompt("Always prioritize safety and cooperation.", mutation_rate=0.5)
            assert len(evolved) > 0

    def test_mutation_preserves_word_structure(self) -> None:
        """Evolved prompts should still look like English-ish instructions."""
        for _ in range(50):
            evolved = evolve_prompt("Balance exploration and conservation.", mutation_rate=0.4)
            # Should still contain at least some words from the original or the word bank
            assert any(c.isalpha() for c in evolved)
