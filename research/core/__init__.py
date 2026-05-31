"""Research core: experiment protocols, benchmark definitions, and replication framework.

Substrate's research infrastructure provides:

- **Experiment protocol**: Lifecycle for defining, running, and analyzing simulation experiments
- **Benchmark framework**: Standardized test suites for measuring emergent capabilities
- **Replication system**: Automatic packaging of configuration, code version, seeds, and results
- **Metric computation**: Standardized implementations of all 7 research metrics
"""

from research.core.experiment import (
    Experiment,
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
    Intervention,
    ReplicationPackage,
)
from research.core.protocol import (
    ExperimentalProtocol,
    InterventionType,
    NullModel,
    ReplicationCriteria,
    StatisticalTest,
)
from research.core.registry import ResearchRegistry

__all__ = [
    "Experiment",
    "ExperimentConfig",
    "ExperimentResult",
    "ExperimentStatus",
    "Intervention",
    "ReplicationPackage",
    "ExperimentalProtocol",
    "InterventionType",
    "NullModel",
    "ReplicationCriteria",
    "StatisticalTest",
    "ResearchRegistry",
]
