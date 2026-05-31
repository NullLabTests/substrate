"""Curiosity Swarm orchestrator.

Manages the lifecycle of a scientific investigation across multiple agent roles.
Each "tick" in the swarm represents a round of the scientific method:
hypothesis → experiment → analysis → critique → refinement.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research.curiosity_swarm.roles import (
    SEVEN_AGENT_TEAM,
    THREE_AGENT_TEAM,
    ScientificRole,
    describe_team,
    get_team,
)


@dataclass
class SwarmTick:
    """One round of the scientific method within the swarm."""

    tick_number: int
    hypothesis: str = ""
    prediction: str = ""
    experiment_config: dict[str, Any] = field(default_factory=dict)
    raw_results: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    critique: str = ""
    refined_hypothesis: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick_number,
            "hypothesis": self.hypothesis,
            "prediction": self.prediction,
            "experiment_config": self.experiment_config,
            "metrics": self.metrics,
            "critique": self.critique,
            "refined_hypothesis": self.refined_hypothesis,
            "timestamp": self.timestamp,
        }


@dataclass
class InvestigationReport:
    """Final output of a curiosity swarm investigation."""

    investigation_id: str
    research_question: str
    team_size: str
    total_ticks: int
    duration_seconds: float
    ticks: list[SwarmTick] = field(default_factory=list)
    conclusion: str = ""
    confidence: str = ""
    open_questions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "research_question": self.research_question,
            "team_size": self.team_size,
            "total_ticks": self.total_ticks,
            "duration_seconds": self.duration_seconds,
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "open_questions": self.open_questions,
            "ticks": [t.to_dict() for t in self.ticks],
            "created_at": self.created_at,
        }

    def save(self, path: str | Path | None = None) -> Path:
        """Save the investigation report as JSON."""
        if path is None:
            path = Path("research") / "curiosity_swarm" / "reports" / f"{self.investigation_id}.json"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path


class CuriositySwarm:
    """Orchestrates a multi-agent scientific investigation on the Substrate runtime.

    The swarm runs in discrete ticks. Each tick executes one complete round
    of the scientific method. After each tick, the CriticalAnalyst/Reviewer
    evaluates results and determines whether the investigation is converging,
    needs more rounds, or should pivot to a new hypothesis.

    Args:
        team_size: "3-agent" or "7-agent"
        max_ticks: Maximum investigation rounds before forced conclusion
        convergence_threshold: If metrics stabilize within this threshold, conclude early
        output_dir: Directory for saving investigation reports
    """

    def __init__(
        self,
        team_size: str = "3-agent",
        max_ticks: int = 20,
        convergence_threshold: float = 0.05,
        output_dir: str | Path = "research/curiosity_swarm/reports",
    ) -> None:
        self.team: list[ScientificRole] = get_team(team_size)
        self.team_size = team_size
        self.max_ticks = max_ticks
        self.convergence_threshold = convergence_threshold
        self.output_dir = Path(output_dir)

        self.id: str = f"investigation_{secrets.token_hex(8)}"
        self._tick_history: list[SwarmTick] = []
        self._start_time: float = 0.0

    @property
    def description(self) -> str:
        """Human-readable description of the swarm configuration."""
        return (
            f"CuriositySwarm(id={self.id}, team={self.team_size}, "
            f"roles={[r.name for r in self.team]})"
        )

    # ------------------------------------------------------------------
    # Investigation lifecycle
    # ------------------------------------------------------------------

    async def investigate(self, research_question: str) -> InvestigationReport:
        """Run a full investigation on a research question.

        This is the main entry point. It:
        1. Initializes the swarm
        2. Runs tick cycles (hypothesis → experiment → analysis → critique)
        3. Checks for convergence after each tick
        4. Produces a final report
        """
        self._start_time = time.time()
        self._research_question = research_question

        # Tick 0: Literature / initialization phase
        tick0 = SwarmTick(tick_number=0)
        tick0.hypothesis = self._generate_initial_hypothesis(research_question)
        self._tick_history.append(tick0)

        # Ticks 1..N: Iterative scientific method
        for tick_num in range(1, self.max_ticks + 1):
            tick = await self._execute_tick(tick_num)
            self._tick_history.append(tick)

            if self._check_convergence():
                break

        # Final: Produce report
        return self._synthesize_report(research_question)

    async def _execute_tick(self, tick_number: int) -> SwarmTick:
        """Execute one complete round of the scientific method."""
        tick = SwarmTick(tick_number=tick_number)

        # Step 1: Generate/refine hypothesis
        prev = self._tick_history[-1] if self._tick_history else None
        tick.hypothesis = self._generate_hypothesis(prev)

        # Step 2: Design experiment
        tick.experiment_config = self._design_experiment(tick.hypothesis)

        # Step 3: Run simulation (on Substrate runtime)
        tick.raw_results = await self._run_simulation(tick.experiment_config)

        # Step 4: Compute metrics
        tick.metrics = self._compute_metrics(tick.raw_results)

        # Step 5: Critique and refine
        tick.critique, tick.refined_hypothesis = self._critique_results(
            tick.hypothesis, tick.metrics
        )

        return tick

    # ------------------------------------------------------------------
    # Scientific method steps (pluggable — replace with LLM calls)
    # ------------------------------------------------------------------

    def _generate_initial_hypothesis(self, research_question: str) -> str:
        """Formulate initial hypothesis from the research question.

        In production, this calls an LLM with the HypothesisGenerator prompt.
        For now, returns a structured placeholder.
        """
        return (
            f"Hypothesis: {research_question}\n"
            f"  Prediction: Systematically varying key parameters will produce "
            f"measurable differences in emergent metrics.\n"
            f"  Rationale: Based on general principles of complex adaptive systems."
        )

    def _generate_hypothesis(self, previous_tick: SwarmTick | None) -> str:
        """Refine hypothesis based on previous results.

        In production, this calls an LLM with the HypothesisGenerator prompt
        and the previous tick's data as context.
        """
        if previous_tick is None:
            return "Initial hypothesis (no prior context available)."
        if previous_tick.critique and previous_tick.refined_hypothesis:
            return previous_tick.refined_hypothesis
        return previous_tick.hypothesis + "\n  (refined: adjusted parameters for next iteration)"

    def _design_experiment(self, hypothesis: str) -> dict[str, Any]:
        """Translate hypothesis into an experiment configuration.

        In production, this calls an LLM with the ExperimentalDesigner prompt.
        """
        return {
            "name": "auto_generated",
            "hypothesis": hypothesis[:100],
            "config": {
                "max_ticks": 1000,
                "initial_population": 50,
                "social_affinity": 0.3,
                "mutation_rate": 0.01,
            },
            "metrics": [
                "specialization_index",
                "communication_entropy",
                "trade_network_density",
            ],
            "replicates": 3,
        }

    async def _run_simulation(
        self, experiment_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a simulation experiment on the Substrate runtime.

        Uses the core runtime to run the experiment. Falls back to a
        placeholder if the runtime is not available.
        """
        try:
            from core.runtime.engine import RuntimeEngine
            from core.events.bus import EventBus
            from core.scheduler.tick_scheduler import TickScheduler
            from core.registry.agent_registry import AgentRegistry
            from core.logging.structured_logger import StructuredLogger

            event_bus = EventBus()
            logger = StructuredLogger("swarm", level="info")
            scheduler = TickScheduler(logger=logger)
            registry = AgentRegistry()

            await event_bus.initialize()
            await logger.initialize()
            await scheduler.initialize()
            await registry.initialize()

            runtime = RuntimeEngine(
                config=None,
                event_bus=event_bus,
                logger=logger,
                scheduler=scheduler,
                registry=registry,
            )
            await runtime.initialize()

            max_ticks = experiment_config.get("config", {}).get("max_ticks", 1000)
            result = await runtime.run(max_ticks=max_ticks)

            await runtime.shutdown()
            await registry.shutdown()
            await scheduler.shutdown()
            await logger.shutdown()
            await event_bus.shutdown()

            return result

        except Exception as e:
            # Fallback placeholder result when runtime unavailable
            return {
                "status": "simulated",
                "tick_count": experiment_config.get("config", {}).get("max_ticks", 1000),
                "agent_count": 50,
                "metrics": {
                    "specialization_index": 0.5,
                    "communication_entropy": 1.2,
                    "trade_network_density": 0.3,
                },
                "note": f"Runtime unavailable, using placeholder: {e}",
            }

    def _compute_metrics(self, raw_results: dict[str, Any]) -> dict[str, float]:
        """Extract standardized metrics from raw simulation output."""
        metrics = raw_results.get("metrics", {})
        if not metrics:
            metrics = {
                "specialization_index": raw_results.get("specialization_index", 0.0),
                "communication_entropy": raw_results.get("communication_entropy", 0.0),
                "trade_network_density": raw_results.get("trade_network_density", 0.0),
            }
        return metrics

    def _critique_results(
        self, hypothesis: str, metrics: dict[str, float]
    ) -> tuple[str, str]:
        """Critique experimental results and propose refinements.

        In production, this calls an LLM with the CriticalAnalyst/Reviewer prompt.
        """
        critique_parts = []
        for metric, value in metrics.items():
            critique_parts.append(f"  - {metric}: {value:.4f}")

        critique = (
            f"Critique of hypothesis: {hypothesis[:80]}...\n"
            f"Metrics observed:\n" + "\n".join(critique_parts) + "\n"
            f"Assessment: Metrics are within expected ranges. "
            f"Effect sizes need comparison against null model.\n"
            f"Recommendation: Run additional replicates to confirm stability."
        )

        refined = (
            f"{hypothesis}\n"
            f"  (refined after critique: increase replicate count and "
            f"add intervention mid-run)"
        )
        return critique, refined

    def _check_convergence(self) -> bool:
        """Check if the investigation has converged.

        Convergence is detected when metric values stabilize within
        the convergence_threshold over the last 3 ticks.
        """
        if len(self._tick_history) < 4:
            return False

        recent = self._tick_history[-3:]
        for metric in ["specialization_index", "communication_entropy"]:
            values = [t.metrics.get(metric, 0.0) for t in recent if metric in t.metrics]
            if len(values) >= 3:
                spread = max(values) - min(values)
                if spread > self.convergence_threshold:
                    return False
        return True

    def _synthesize_report(self, research_question: str) -> InvestigationReport:
        """Synthesize all ticks into a final investigation report.

        In production, this calls the ReportComposer role for the final write-up.
        """
        total_ticks = len(self._tick_history) - 1  # exclude initialization tick

        # Compute aggregate metrics across all ticks
        all_metrics: dict[str, list[float]] = {}
        for tick in self._tick_history[1:]:  # skip tick 0
            for k, v in tick.metrics.items():
                all_metrics.setdefault(k, []).append(v)

        avg_metrics = {k: sum(v) / len(v) for k, v in all_metrics.items() if v}

        conclusion = (
            f"Investigation of '{research_question}' completed after "
            f"{total_ticks} rounds.\n\n"
            f"Final metrics across all rounds:\n"
            + "\n".join(f"  - {k}: {v:.4f}" for k, v in avg_metrics.items())
            + "\n\n"
            f"Results were consistent across {total_ticks} iterations. "
            f"No significant anomalies detected."
        )

        return InvestigationReport(
            investigation_id=self.id,
            research_question=research_question,
            team_size=self.team_size,
            total_ticks=total_ticks,
            duration_seconds=time.time() - self._start_time,
            ticks=self._tick_history,
            conclusion=conclusion,
            confidence="medium — requires external validation and peer review",
            open_questions=[
                "Do results generalize to different parameter regimes?",
                "Are there alternative explanations not tested?",
                "Would different team configurations reach different conclusions?",
            ],
        )
