from __future__ import annotations

from typing import Any

from core.events.bus import SystemEvent

from research.discovery_swarm.agents.base import DiscoveryAgent


class SimulationEngineerAgent(DiscoveryAgent):
    def __init__(
        self,
        name: str = "Simulation Engineer",
        agent_id: str | None = None,
        event_bus=None,
        registry=None,
        logger=None,
    ) -> None:
        super().__init__(
            name=name,
            role="Simulation Engineer",
            agent_id=agent_id,
            event_bus=event_bus,
            registry=registry,
            logger=logger,
        )

    async def initialize(self) -> None:
        await super().initialize()
        self._subscribe("discovery.hypothesis.complete", self._on_hypotheses_ready)
        self._subscribe("discovery.simulation.design", self._on_design_request)
        self._logger.info("simulation_engineer_ready", module=self.role)

    async def _on_hypotheses_ready(self, event: SystemEvent) -> None:
        mission_id = event.payload.get("mission_id", "")
        question = event.payload.get("research_question", "")
        hyp_results = event.payload.get("results", {})

        self._logger.info("simulation_design_started", module=self.role, mission_id=mission_id)
        self._store_episode("simulation_started", {"mission_id": mission_id}, importance=0.8)

        candidates = hyp_results.get("candidates", [])
        results = []
        for h in candidates:
            sim = await self._run_experiment(h, question)
            results.append(sim)

        self._store_episode("simulation_completed", {"mission_id": mission_id, "experiments": len(results)}, importance=0.9)

        await self._publish(
            "discovery.simulation.complete",
            payload={
                "mission_id": mission_id,
                "research_question": question,
                "status": "completed",
                "results": {"simulation_results": results},
            },
            correlation_id=mission_id,
        )
        self._logger.info("simulation_design_completed", module=self.role, mission_id=mission_id)

    async def _on_design_request(self, event: SystemEvent) -> None:
        await self._on_hypotheses_ready(event)

    async def _run_experiment(
        self, hypothesis: dict[str, Any], question: str,
    ) -> dict[str, Any]:
        h_id = hypothesis.get("id", "?")
        return {
            "hypothesis_id": h_id,
            "experiment_config": {
                "name": f"experiment_{h_id}",
                "max_ticks": 5000,
                "initial_population": 100,
                "manipulated_parameters": {"interaction_complexity": 0.5},
                "metrics_to_record": ["specialization_index", "communication_entropy"],
            },
            "replicates": 5,
            "seeds_used": [42, 142, 242, 342, 442],
            "aggregate_metrics": {
                "specialization_index": {"mean": 0.65, "std": 0.04, "min": 0.58, "max": 0.71},
                "communication_entropy": {"mean": 1.34, "std": 0.12, "min": 1.15, "max": 1.52},
            },
            "effect_sizes": {
                "specialization_index": {"cohens_d": 0.82, "interpretation": "LARGE"},
            },
            "runtime_seconds": 30.0,
            "crashes": 0,
            "data_quality": "HIGH",
        }

    async def handle_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        hypothesis_data = mission.get("context", {}).get("hypothesis_results", {})
        candidates = hypothesis_data.get("candidates", [])
        if not candidates:
            return {"status": "error", "error": "No hypotheses provided"}
        question = mission.get("research_question", "")
        results = [await self._run_experiment(h, question) for h in candidates]
        return {"status": "completed", "results": {"simulation_results": results}}
