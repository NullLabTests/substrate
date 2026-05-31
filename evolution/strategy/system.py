"""Evolving strategy system: prompts, policies, mutation, and inheritance.

Strategies are heritable behavioral blueprints that evolve across generations.
Each strategy consists of:
  - A prompt template (text-based behavioral instruction)
  - A set of condition → action policies (decision rules)

Research question: Do successful behaviors propagate through populations?
Measured via: diversity, convergence, innovation, extinction.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

from core.events import bus

# ─── Default prompt templates ─────────────────────────────────────────────

DEFAULT_PROMPT_TEMPLATES: list[str] = [
    "Prioritize energy efficiency. Conserve resources and minimize risk.",
    "Explore aggressively. Seek new resources and opportunities.",
    "Cooperate with nearby agents. Share resources and information.",
    "Compete for scarce resources. Maximize personal gain.",
    "Balance exploration and conservation. Adapt to local conditions.",
    "Specialize in a single resource type. Become an expert harvester.",
    "Trade frequently. Build alliances and exchange value.",
    "Avoid danger. Stay within known safe zones.",
]

# ─── Default policy templates ──────────────────────────────────────────────

DEFAULT_POLICIES: list[dict[str, str]] = [
    {"condition": "energy < 30", "action": "rest_and_conserve"},
    {"condition": "energy < 50 and resources_nearby", "action": "harvest_resources"},
    {"condition": "energy > 80 and agents_nearby", "action": "initiate_trade"},
    {"condition": "energy > 60 and partner_available", "action": "reproduce"},
    {"condition": "danger_nearby", "action": "flee"},
    {"condition": "energy > 70 and explored_recently", "action": "explore"},
    {"condition": "resources_scarce", "action": "move_to_new_area"},
    {"condition": "alliance_offered", "action": "evaluate_and_join"},
]

# ─── Word bank for prompt mutation ─────────────────────────────────────────

_ACTION_VERBS = [
    "prioritize", "maximize", "minimize", "balance", "seek", "avoid",
    "maintain", "optimize", "pursue", "defer", "escalate", "reduce",
]

_RESOURCES = [
    "energy", "resources", "information", "alliances", "territory",
    "tools", "knowledge", "reputation", "safety", "wealth",
]

_MODIFIERS = [
    "aggressively", "cautiously", "selectively", "persistently",
    "opportunistically", "methodically", "strategically", "adaptively",
]

_CONTEXT_CLUES = [
    "when energy is low", "when resources are abundant",
    "when alone", "when outnumbered", "in familiar territory",
    "in unknown territory", "during scarcity", "during abundance",
]


def _mutate_text(text: str, mutation_rate: float = 0.3) -> str:
    """Apply word-level mutations to a prompt string."""
    words = text.split()
    mutated: list[str] = []
    for word in words:
        if random.random() < mutation_rate:
            # Word substitution
            word = word.lower().strip(".,")
            if word in _ACTION_VERBS:
                word = random.choice(_ACTION_VERBS)
            elif word in _RESOURCES:
                word = random.choice(_RESOURCES)
            elif word in [m.strip(".,") for m in _MODIFIERS]:
                word = random.choice(_MODIFIERS)
            # Random capitalization
            if random.random() < 0.1:
                word = word.capitalize()
        mutated.append(word)

    result = " ".join(mutated)

    # Random phrase insertion
    if random.random() < mutation_rate * 0.5:
        clause = random.choice(_CONTEXT_CLUES)
        insert_pos = random.randint(0, len(result))
        result = result[:insert_pos] + " " + clause + result[insert_pos:]

    # Random phrase deletion (trim a trailing clause)
    if random.random() < mutation_rate * 0.3 and len(result) > 15:
        sentences = result.split(".")
        if len(sentences) > 1:
            result = ".".join(sentences[:-1]).strip()

    return result.strip()


def _mutate_policies(
    policies: list[dict[str, str]],
    mutation_rate: float = 0.2,
    max_policies: int = 12,
) -> list[dict[str, str]]:
    """Apply mutations to a list of condition→action policies."""
    result: list[dict[str, str]] = []

    for policy in policies:
        # Copy with possible modification
        mutated_condition = policy["condition"]
        mutated_action = policy["action"]

        if random.random() < mutation_rate:
            # Modify the condition threshold
            for token in ["30", "50", "60", "70", "80", "90"]:
                if token in mutated_condition:
                    shift = random.choice(["-10", "+10", "-20", "+20"])
                    new_val = max(0, int(token) + int(shift))
                    mutated_condition = mutated_condition.replace(token, str(new_val), 1)
                    break

        if random.random() < mutation_rate:
            # Modify the action
            all_actions = [p["action"] for p in DEFAULT_POLICIES]
            if mutated_action in all_actions:
                mutated_action = random.choice(all_actions)

        if random.random() < 0.05:
            # Small chance to delete this policy
            continue

        result.append({"condition": mutated_condition, "action": mutated_action})

    # Random new policy insertion
    while len(result) < max_policies and random.random() < mutation_rate * 0.3:
        new_policy = random.choice(DEFAULT_POLICIES)
        # Add with slight mutation
        if random.random() < 0.5:
            new_policy = {
                "condition": new_policy["condition"],
                "action": random.choice([p["action"] for p in DEFAULT_POLICIES]),
            }
        result.append(dict(new_policy))

    # Trim if over max
    if len(result) > max_policies:
        result = result[:max_policies]

    return result


# ─── Strategy data model ───────────────────────────────────────────────────


@dataclass
class Strategy:
    """A heritable behavioral strategy for an agent.

    Attributes:
        agent_id: The agent that owns this strategy.
        prompt_template: Text-based behavioral instruction that evolves.
        policies: List of condition→action decision rules.
        generation: How many inheritance steps from the root.
        parent_id: The agent_id this strategy was inherited from.
        created_at: Timestamp of strategy creation.
        metadata: Arbitrary additional data (tags, lineage info).
    """

    agent_id: str
    prompt_template: str
    policies: list[dict[str, str]]
    generation: int = 0
    parent_id: str | None = None
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "prompt_template": self.prompt_template,
            "policies": list(self.policies),
            "generation": self.generation,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Strategy:
        return cls(
            agent_id=data["agent_id"],
            prompt_template=data["prompt_template"],
            policies=list(data["policies"]),
            generation=data.get("generation", 0),
            parent_id=data.get("parent_id"),
            created_at=data.get("created_at", time.time()),
            metadata=data.get("metadata", {}),
        )


# ─── Strategy System ───────────────────────────────────────────────────────


class StrategySystem:
    """Manages the creation, mutation, inheritance, and tracking of strategies.

    This is the core system for the research question:
    "Do successful behaviors propagate through populations?"
    """

    def __init__(self) -> None:
        self._strategies: dict[str, Strategy] = {}
        self._generation_count: dict[int, int] = {}  # gen → count
        self._extinct_strategies: dict[str, Strategy] = {}
        self._total_created: int = 0
        self._total_extinct: int = 0

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        self._strategies.clear()
        self._generation_count.clear()

    async def shutdown(self) -> None:
        self._strategies.clear()
        self._generation_count.clear()

    async def save_state(self) -> dict[str, Any]:
        return {
            "strategies": {aid: s.to_dict() for aid, s in self._strategies.items()},
            "extinct_strategies": {aid: s.to_dict() for aid, s in self._extinct_strategies.items()},
            "total_created": self._total_created,
            "total_extinct": self._total_extinct,
        }

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        if not state:
            return
        self._strategies = {
            aid: Strategy.from_dict(d) for aid, d in state.get("strategies", {}).items()
        }
        self._extinct_strategies = {
            aid: Strategy.from_dict(d) for aid, d in state.get("extinct_strategies", {}).items()
        }
        self._total_created = state.get("total_created", 0)
        self._total_extinct = state.get("total_extinct", 0)

    # ── Strategy creation ───────────────────────────────────────────────

    def create_initial_strategy(
        self,
        agent_id: str,
        prompt_template: str | None = None,
        policies: list[dict[str, str]] | None = None,
    ) -> Strategy:
        """Create a brand-new strategy for a seed agent (no parent)."""
        strategy = Strategy(
            agent_id=agent_id,
            prompt_template=prompt_template or random.choice(DEFAULT_PROMPT_TEMPLATES),
            policies=policies or [dict(p) for p in random.sample(DEFAULT_POLICIES, k=min(4, len(DEFAULT_POLICIES)))],
            generation=0,
            parent_id=None,
        )
        self._strategies[agent_id] = strategy
        self._total_created += 1
        self._generation_count[0] = self._generation_count.get(0, 0) + 1

        bus.emit("strategy.created", agent_id, {
            "agent_id": agent_id,
            "prompt": strategy.prompt_template,
            "policy_count": len(strategy.policies),
            "generation": 0,
        })
        return strategy

    def inherit_strategy(
        self,
        child_id: str,
        parent_id: str,
        prompt_mutation_rate: float = 0.3,
        policy_mutation_rate: float = 0.2,
    ) -> Strategy:
        """Create a child strategy by inheriting and mutating a parent strategy.

        This is the mechanism for strategy inheritance across generations.
        Both the prompt template and the policies undergo evolution.
        """
        parent_strategy = self._strategies.get(parent_id)
        if not parent_strategy:
            # Fallback: create initial strategy for the child
            return self.create_initial_strategy(child_id)

        # Copy parent with mutation
        mutated_prompt = evolve_prompt(parent_strategy.prompt_template, prompt_mutation_rate)
        mutated_policies = evolve_policies(parent_strategy.policies, policy_mutation_rate)

        child_strategy = Strategy(
            agent_id=child_id,
            prompt_template=mutated_prompt,
            policies=mutated_policies,
            generation=parent_strategy.generation + 1,
            parent_id=parent_id,
        )
        self._strategies[child_id] = child_strategy
        self._total_created += 1
        gen = child_strategy.generation
        self._generation_count[gen] = self._generation_count.get(gen, 0) + 1

        bus.emit("strategy.inherited", child_id, {
            "child_id": child_id,
            "parent_id": parent_id,
            "generation": gen,
            "prompt": mutated_prompt,
            "policy_count": len(mutated_policies),
            "prompt_mutations": _count_mutations(parent_strategy.prompt_template, mutated_prompt),
            "policy_mutations": len(mutated_policies) - len(parent_strategy.policies),
        })
        return child_strategy

    # ── Strategy access ─────────────────────────────────────────────────

    def get_strategy(self, agent_id: str) -> Strategy | None:
        return self._strategies.get(agent_id)

    def has_strategy(self, agent_id: str) -> bool:
        return agent_id in self._strategies

    def mark_extinct(self, agent_id: str) -> None:
        """Mark an agent's strategy as extinct (agent died without offspring)."""
        strategy = self._strategies.pop(agent_id, None)
        if strategy:
            self._extinct_strategies[agent_id] = strategy
            self._total_extinct += 1
            bus.emit("strategy.extinct", agent_id, {
                "agent_id": agent_id,
                "generation": strategy.generation,
                "prompt": strategy.prompt_template,
            })

    def update_strategy_metadata(self, agent_id: str, **metadata: Any) -> None:
        strategy = self._strategies.get(agent_id)
        if strategy:
            strategy.metadata.update(metadata)

    # ── Reporting ───────────────────────────────────────────────────────

    @property
    def active_count(self) -> int:
        return len(self._strategies)

    @property
    def extinct_count(self) -> int:
        return self._total_extinct

    @property
    def total_created(self) -> int:
        return self._total_created

    def get_generation_distribution(self) -> dict[int, int]:
        return dict(self._generation_count)

    def get_all_prompts(self) -> list[str]:
        return [s.prompt_template for s in self._strategies.values()]

    def get_all_policies(self) -> list[list[dict[str, str]]]:
        return [s.policies for s in self._strategies.values()]


# ─── Standalone evolution functions ───────────────────────────────────────


def evolve_prompt(prompt: str, mutation_rate: float = 0.3) -> str:
    """Evolve a prompt template via word-level mutation."""
    return _mutate_text(prompt, mutation_rate)


def evolve_policies(
    policies: list[dict[str, str]],
    mutation_rate: float = 0.2,
) -> list[dict[str, str]]:
    """Evolve a list of policies via mutation, insertion, and deletion."""
    return _mutate_policies(policies, mutation_rate)


def strategy_distance(s1: Strategy, s2: Strategy) -> float:
    """Compute a normalized distance between two strategies.

    Uses a combination of:
    - Prompt edit distance (Levenshtein-like via word overlap)
    - Policy overlap (Jaccard similarity on condition→action pairs)

    Returns a float in [0, 1] where 0 = identical, 1 = maximally different.
    """
    # Prompt word overlap (simple set-based Jaccard distance)
    words1 = set(s1.prompt_template.lower().split())
    words2 = set(s2.prompt_template.lower().split())
    if not words1 and not words2:
        prompt_dist = 0.0
    else:
        intersection = words1 & words2
        union = words1 | words2
        prompt_dist = 1.0 - (len(intersection) / len(union))

    # Policy Jaccard distance
    pairs1 = {(p["condition"], p["action"]) for p in s1.policies}
    pairs2 = {(p["condition"], p["action"]) for p in s2.policies}
    if not pairs1 and not pairs2:
        policy_dist = 0.0
    else:
        p_intersection = pairs1 & pairs2
        p_union = pairs1 | pairs2
        policy_dist = 1.0 - (len(p_intersection) / len(p_union))

    # Weighted average
    return 0.4 * prompt_dist + 0.6 * policy_dist


def _count_mutations(original: str, mutated: str) -> int:
    """Count approximate number of word-level changes between two prompts."""
    orig_words = original.split()
    mut_words = mutated.split()
    changes = abs(len(orig_words) - len(mut_words))
    for ow, mw in zip(orig_words, mut_words):
        if ow != mw:
            changes += 1
    return changes
