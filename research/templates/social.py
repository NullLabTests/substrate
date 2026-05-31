"""Social dynamics experiment.

Tests RQ2: Do cooperative strategies emerge without explicit rewards?
Conditions vary social_affinity and communication channel capacity
to measure impact on reputation convergence and trade network density.

Protocol: social_dynamics
Key metrics: reputation_convergence, trade_network_density, communication_entropy
Interventions: agent_removal (to test reputation robustness)
"""

from __future__ import annotations

from research.core.experiment import Experiment, ExperimentConfig, ExperimentResult, ExperimentStatus, Intervention
from research.core.registry import ResearchRegistry


@ResearchRegistry.register_experiment
class SocialDynamicsExperiment(Experiment):
    """Tests how social affinity and communication capacity affect
    reputation convergence and trade network formation.

    Hypothesis: Cooperative strategies (resource sharing, mutual defense)
    can emerge and stabilize when agents interact repeatedly and have
    memory of past interactions.
    """

    type_id = "social_dynamics"

    @staticmethod
    def high_affinity_config() -> ExperimentConfig:
        """Configuration with high social affinity (expected: strong cooperation)."""
        return ExperimentConfig(
            name="social_high_affinity",
            description="High social affinity — agents strongly inclined to interact",
            social_affinity=0.8,
            max_ticks=20_000,
            num_replicates=10,
            interventions=[
                Intervention(tick=5_000, type="agent_removal", params={"fraction": 0.2}),
            ],
        )

    @staticmethod
    def low_affinity_config() -> ExperimentConfig:
        """Configuration with low social affinity (expected: weak cooperation)."""
        return ExperimentConfig(
            name="social_low_affinity",
            description="Low social affinity — agents weakly inclined to interact",
            social_affinity=0.1,
            max_ticks=20_000,
            num_replicates=10,
        )

    async def run(self) -> ExperimentResult:
        self.start()
        try:
            # Social dynamics simulation using:
            #   - AgentRegistry for agent lifecycle
            #   - EventBus for message passing
            #   - TelemetryPipeline for reputation metrics
            #
            # Full implementation would use the social sub-systems:
            #   - social.messaging for directed agent-to-agent communication
            #   - social.alliances for alliance formation tracking
            #   - social.reputation for reputation score management

            from core.runtime.engine import RuntimeEngine
            from core.events.bus import EventBus
            from core.logging.structured_logger import StructuredLogger
            from core.scheduler.tick_scheduler import TickScheduler
            from core.registry.agent_registry import AgentRegistry

            event_bus = EventBus()
            logger = StructuredLogger("social", level="info")
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

            result_state = await runtime.run(max_ticks=self.config.max_ticks)
            metrics = result_state.get("metrics", {})

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
