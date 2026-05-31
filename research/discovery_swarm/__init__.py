"""Discovery Swarm — autonomous scientific discovery on the Substrate runtime.

The Discovery Swarm is a 7-agent system that conducts end-to-end scientific
discovery missions. It breaks down a research question, surveys literature,
generates hypotheses, runs simulations, quantifies uncertainty, and delivers
ranked proposals — all within a reproducible, auditable workflow.

Mission workflow (DAG order)::

    ┌──────────────┐
    │ Orchestrator │  breaks down question → mission_plan
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │Literature    │  surveys existing knowledge → knowledge_survey
    │ Scout        │
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │Hypothesis    │  generates candidate ideas → hypothesis_bank
    │ Forge        │
    └──────┬───────┘
           │
    ┌──────┴──────────────────┐
    │         PARALLEL         │
    ├──────────────────────────┤
    │ Critical     │ Simulation│
    │ Reviewer     │ Engineer  │
    │ (critique)   │ (design)  │
    ├──────────────┼──────────┤
    │ Uncertainty Quanitifier  │
    │ (confidence assessment)  │
    └──────────────┴──────────┘
           │
    ┌──────▼───────────────┐
    │ Synthesis Architect  │  ranked proposals → discovery_report
    └──────────────────────┘

Usage::

    from research.discovery_swarm import DiscoveryMission

    mission = DiscoveryMission(
        question="Design a room-temperature superconductor candidate",
        max_parallel_workers=3
    )
    report = await mission.run()
    report.save("superconductor_mission.json")
"""

from research.discovery_swarm.discovery_crew import DiscoveryCrew
from research.discovery_swarm.mission import (
    DiscoveryMission,
    MissionPhase,
    MissionReport,
    MissionStatus,
)
from research.discovery_swarm.roles import (
    DISCOVERY_SWARM_ROLES,
    get_discovery_role,
    list_discovery_roles,
)

__all__ = [
    "DiscoveryCrew",
    "DiscoveryMission",
    "MissionPhase",
    "MissionReport",
    "MissionStatus",
    "DISCOVERY_SWARM_ROLES",
    "get_discovery_role",
    "list_discovery_roles",
]
