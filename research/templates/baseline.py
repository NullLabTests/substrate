"""Baseline null-model experiment.

This experiment runs the simulation with default parameters and no interventions.
It establishes the baseline metric distribution against which all other
experiments are compared.

Protocol: baseline
Metrics: all 7 research metrics
Duration: 10,000 ticks
Replicates: 10
"""

from __future__ import annotations

from research.core.experiment import Experiment, ExperimentConfig, ExperimentResult, ExperimentStatus
from research.core.registry import ResearchRegistry


@ResearchRegistry.register_experiment
class BaselineExperiment(Experiment):
    """Baseline experiment with default parameters and no interventions.

    Establishes the null distribution for all 7 metrics. Every other experiment
    type compares its results against BaselineExperiment.
    """

    type_id = "baseline"

    async def run(self) -> ExperimentResult:
        self.start()
        try:
            # ---- Simulation Setup ----
            # In a full implementation, this would:
            #   1. Create RuntimeEngine with config
            #   2. Initialize EventBus, TickScheduler, AgentRegistry
            #   3. Initialize SQLiteBackend for persistence
            #   4. Initialize TelemetryPipeline for metric collection
            #   5. Initialize RecoverySystem for crash recovery
            #
            # For now, this is a simulation stub that demonstrates the pattern.

            from core.runtime.engine import RuntimeEngine
            from core.events.bus import EventBus
            from core.scheduler.tick_scheduler import TickScheduler
            from core.registry.agent_registry import AgentRegistry
            from core.logging.structured_logger import StructuredLogger
            from core.telemetry.pipeline import TelemetryPipeline

            event_bus = EventBus()
            logger = StructuredLogger("baseline", level="info")
            scheduler = TickScheduler(logger=logger)
            registry = AgentRegistry()

            await event_bus.initialize()
            await logger.initialize()
            await scheduler.initialize()
            await registry.initialize()

            runtime = RuntimeEngine(
                config=None,  # type: ignore[arg-type]
                event_bus=event_bus,
                logger=logger,
                scheduler=scheduler,
                registry=registry,
            )
            await runtime.initialize()

            # ---- Interventions ----
            # None for baseline — this is the control condition

            # ---- Run ----
            result_state = await runtime.run(max_ticks=self.config.max_ticks)

            # ---- Collect Metrics ----
            metrics = result_state.get("metrics", {})

            # ---- Cleanup ----
            await runtime.shutdown()
            await registry.shutdown()
            await scheduler.shutdown()
            await logger.shutdown()
            await event_bus.shutdown()

            result = ExperimentResult(
                experiment_id=self.id,
                config=self.config,
                status=ExperimentStatus.COMPLETED,
                tick_count=self.config.max_ticks,
                agent_count_final=len(registry.list_agents()),
                metrics=metrics,
            )
            self.complete(result)
            return result

        except Exception as e:
            return self.fail(str(e))
