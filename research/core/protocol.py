"""Experimental protocol definitions.

Defines the formal structure for research protocols, null models,
statistical tests, and replication criteria used across all experiments.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class InterventionType(Enum):
    """Types of controlled perturbations that can be injected mid-experiment."""

    RESOURCE_SHOCK = "resource_shock"
    AGENT_REMOVAL = "agent_removal"
    TOOL_BAN = "tool_ban"
    MIGRATION_WAVE = "migration_wave"
    CLIMATE_SHIFT = "climate_shift"


class StatisticalTest(Enum):
    """Statistical tests used for hypothesis testing."""

    PERMUTATION_TEST = "permutation_test"
    MANN_WHITNEY_U = "mann_whitney_u"
    KOLMOGOROV_SMIRNOV = "kolmogorov_smirnov"
    WELCHS_TTEST = "welchs_ttest"
    BOOTSTRAP = "bootstrap"


@dataclass
class NullModel:
    """A null model that generates expected metric distributions.

    Used for statistical comparison against experimental observations.
    """

    name: str
    description: str
    generator: Callable[[int], list[float]] | None = None
    expected_mean: float = 0.0
    expected_variance: float = 1.0

    def generate_samples(self, n: int = 1000) -> list[float]:
        """Generate n samples from the null distribution."""
        if self.generator:
            return self.generator(n)
        return [random.gauss(self.expected_mean, math.sqrt(self.expected_variance)) for _ in range(n)]


@dataclass
class ReplicationCriteria:
    """Criteria for a result to be considered replicated."""

    min_replicates: int = 8
    total_replicates: int = 10
    min_effect_size: float = 0.5  # Cohen's d
    significance_level: float = 0.01
    direction_consistency_required: bool = True

    @property
    def replication_threshold(self) -> float:
        """Fraction of replicates that must show the effect."""
        return self.min_replicates / self.total_replicates


# --- Pre-built Null Models ---

NULL_MODELS: dict[str, NullModel] = {
    "specialization": NullModel(
        name="Uniform Random Role Assignment",
        description="Agents assigned roles uniformly at random produces ~0.5 specialization index",
        expected_mean=0.5,
        expected_variance=0.02,
    ),
    "communication": NullModel(
        name="Random Message Selection",
        description="Uniform random message types produce entropy ~log(k/2)",
        expected_mean=0.0,
        expected_variance=0.0,
    ),
    "tool_adoption": NullModel(
        name="Random Adoption Model",
        description="No systematic diffusion; adoption rate k ≈ 0, ceiling L ≈ 1",
        expected_mean=0.0,
        expected_variance=0.5,
    ),
    "memory_persistence": NullModel(
        name="Pure Random Forgetting",
        description="Memory survival follows exponential decay with half-life = 1/decay_rate",
        expected_mean=0.0,
        expected_variance=0.0,
    ),
    "lineage_survival": NullModel(
        name="Neutral Drift Model",
        description="Lineage survival follows exponential decay under neutral drift",
        expected_mean=0.0,
        expected_variance=0.0,
    ),
    "trade_network": NullModel(
        name="Random Pairing Model",
        description="Trade network density proportional to random encounter rate",
        expected_mean=0.0,
        expected_variance=0.0,
    ),
    "reputation": NullModel(
        name="No-Reputation Update Model",
        description="Reputation follows random walk without update mechanism",
        expected_mean=0.0,
        expected_variance=0.0,
    ),
}


# --- Statistical Helpers ---


def permutation_test(
    observed: list[float],
    null_samples: list[float],
    n_permutations: int = 10_000,
) -> float:
    """Two-sided permutation test. Returns p-value."""
    combined = observed + null_samples
    n_obs = len(observed)
    observed_stat = abs(sum(observed) / n_obs - sum(null_samples) / len(null_samples))

    count_extreme = 0
    for _ in range(n_permutations):
        random.shuffle(combined)
        perm_obs = combined[:n_obs]
        perm_null = combined[n_obs:]
        perm_stat = abs(sum(perm_obs) / n_obs - sum(perm_null) / len(null_samples))
        if perm_stat >= observed_stat:
            count_extreme += 1

    return (count_extreme + 1) / (n_permutations + 1)


def cohens_d(sample_a: list[float], sample_b: list[float]) -> float:
    """Cohen's d effect size between two samples."""
    mean_a = sum(sample_a) / len(sample_a)
    mean_b = sum(sample_b) / len(sample_b)

    var_a = sum((x - mean_a) ** 2 for x in sample_a) / len(sample_a)
    var_b = sum((x - mean_b) ** 2 for x in sample_b) / len(sample_b)

    pooled_std = math.sqrt((var_a + var_b) / 2)
    if pooled_std == 0:
        return 0.0
    return abs(mean_a - mean_b) / pooled_std


# --- Protocol Definition ---


@dataclass
class ExperimentalProtocol:
    """A complete experimental protocol specification.

    This is the formal document that defines what an experiment tests,
    how it's configured, what measurements are taken, and what counts
    as evidence.
    """

    id: str
    title: str
    description: str
    research_question: str
    hypothesis: str
    predictions: list[str] = field(default_factory=list)
    config_template: dict[str, Any] = field(default_factory=dict)
    metrics: list[str] = field(default_factory=list)
    null_model: NullModel | None = None
    statistical_test: StatisticalTest = StatisticalTest.PERMUTATION_TEST
    replication_criteria: ReplicationCriteria = field(default_factory=ReplicationCriteria)
    interventions: list[InterventionType] = field(default_factory=list)
    expected_duration_ticks: int = 10_000
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "research_question": self.research_question,
            "hypothesis": self.hypothesis,
            "predictions": self.predictions,
            "config_template": self.config_template,
            "metrics": self.metrics,
            "null_model": self.null_model.name if self.null_model else None,
            "statistical_test": self.statistical_test.value,
            "replication_criteria": {
                "min_replicates": self.replication_criteria.min_replicates,
                "total_replicates": self.replication_criteria.total_replicates,
                "min_effect_size": self.replication_criteria.min_effect_size,
                "significance_level": self.replication_criteria.significance_level,
            },
            "interventions": [iv.value for iv in self.interventions],
            "expected_duration_ticks": self.expected_duration_ticks,
            "tags": self.tags,
        }
