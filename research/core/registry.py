"""Research registry for experiments, benchmarks, and protocols.

Provides a central registry for discovering and running registered
experiments and benchmarks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research.core.experiment import Experiment
    from research.core.protocol import ExperimentalProtocol


class ResearchRegistry:
    """Global registry of experiments, benchmarks, and protocols."""

    _experiments: dict[str, type[Experiment]] = {}
    _protocols: dict[str, ExperimentalProtocol] = {}

    @classmethod
    def register_experiment(cls, experiment_cls: type[Experiment]) -> type[Experiment]:
        """Register an experiment class by its type_id."""
        cls._experiments[experiment_cls.type_id] = experiment_cls
        return experiment_cls

    @classmethod
    def get_experiment(cls, type_id: str) -> type[Experiment]:
        if type_id not in cls._experiments:
            msg = f"Experiment '{type_id}' not registered. Available: {list(cls._experiments.keys())}"
            raise KeyError(msg)
        return cls._experiments[type_id]

    @classmethod
    def list_experiments(cls) -> list[str]:
        return list(cls._experiments.keys())

    @classmethod
    def register_protocol(cls, protocol: ExperimentalProtocol) -> None:
        cls._protocols[protocol.id] = protocol

    @classmethod
    def get_protocol(cls, protocol_id: str) -> ExperimentalProtocol:
        if protocol_id not in cls._protocols:
            msg = f"Protocol '{protocol_id}' not registered."
            raise KeyError(msg)
        return cls._protocols[protocol_id]

    @classmethod
    def list_protocols(cls) -> list[str]:
        return list(cls._protocols.keys())
