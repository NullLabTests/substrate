"""Curiosity Swarm — self-directed scientific discovery on the Substrate runtime.

The Curiosity Swarm is a multi-agent system that conducts autonomous scientific
investigations. It formulates hypotheses, designs and runs simulation experiments,
analyzes results, critiques findings, and composes publication-ready reports —
all within the Substrate tick-based runtime.

Team configurations:
  - **3-agent** (minimal): HypothesisGenerator → ExperimentalDesigner → CriticalAnalyst
  - **7-agent** (full): LiteratureSynthesizer → HypothesisGenerator → ExperimentalDesigner
    → SimulationRunner → StatisticalAnalyst → CriticalReviewer → ReportComposer

Usage::

    from research.curiosity_swarm import CuriositySwarm

    swarm = CuriositySwarm(team_size="7-agent")
    report = await swarm.investigate("Resolve the Hubble tension")
"""

from research.curiosity_swarm.swarm import CuriositySwarm
from research.curiosity_swarm.roles import (
    ScientificRole,
    get_team,
    describe_team,
    TEAM_CONFIGS,
)

__all__ = [
    "CuriositySwarm",
    "ScientificRole",
    "get_team",
    "describe_team",
    "TEAM_CONFIGS",
]
