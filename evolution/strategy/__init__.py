"""Strategy system: evolving prompts, policies, and inheritance."""

from evolution.strategy.system import (
    Strategy,
    StrategySystem,
    evolve_prompt,
    evolve_policies,
    strategy_distance,
    DEFAULT_PROMPT_TEMPLATES,
    DEFAULT_POLICIES,
)

__all__ = [
    "Strategy",
    "StrategySystem",
    "evolve_prompt",
    "evolve_policies",
    "strategy_distance",
    "DEFAULT_PROMPT_TEMPLATES",
    "DEFAULT_POLICIES",
]
