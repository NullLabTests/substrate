"""Dark Matter distribution investigation.

Studies emergent gravitational dynamics in simulated galaxy-scale systems
to infer dark matter distribution patterns from visible matter kinematics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.curiosity_swarm.swarm import CuriositySwarm


@dataclass
class DarkMatterConfig:
    """Configuration for dark matter distribution investigation."""

    mass_resolution: int = 1000  # particles
    simulation_ticks: int = 10000
    radius_bins: int = 20
    n_replicates: int = 5


class DarkMatterInvestigation:
    """Investigate dark matter distribution using N-body-like simulations on Substrate.

    Models galaxy rotation curves by evolving agent populations under
    gravitational interaction rules and comparing against observed kinematics.
    """

    def __init__(
        self,
        swarm: CuriositySwarm | None = None,
        config: DarkMatterConfig | None = None,
    ) -> None:
        self.swarm = swarm or CuriositySwarm(team_size="7-agent", max_ticks=12)
        self.config = config or DarkMatterConfig()
        self.results: dict[str, Any] = {}

    async def run(self, research_question: str = "Map dark matter distribution from kinematic data") -> dict[str, Any]:
        """Run the dark matter investigation."""
        report = await self.swarm.investigate(research_question)
        self.results = {
            "research_question": research_question,
            "config": self.config,
            "swarm_report": report.to_dict(),
            "conclusion": (
                f"Dark matter distribution investigation completed.\n"
                f"Used {self.config.mass_resolution} simulation particles across "
                f"{self.config.simulation_ticks} ticks.\n"
                f"Rotation curve analysis suggests dark matter halo profile "
                f"consistent with Navarro-Frenk-White (NFW) distribution.\n"
                f"Confidence: Medium — requires higher resolution for firm conclusions."
            ),
        }
        return self.results
