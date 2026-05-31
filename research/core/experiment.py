"""Base experiment class and lifecycle management.

Every experiment follows a strict lifecycle:
    DRAFT -> CONFIGURED -> RUNNING -> COMPLETED -> ANALYZED -> ARCHIVED

Subclass `Experiment` and implement `run()` to create a new experiment type.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

import yaml


EXPERIMENT_ROOT: Path = Path(os.getcwd()) / "research" / "experiments"


class ExperimentStatus(Enum):
    """Lifecycle states for an experiment."""

    DRAFT = "draft"
    CONFIGURED = "configured"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ANALYZED = "analyzed"
    ARCHIVED = "archived"


@dataclass
class Intervention:
    """A controlled perturbation injected mid-experiment."""

    tick: int
    type: str  # resource_shock, agent_removal, tool_ban, migration_wave, climate_shift
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"tick": self.tick, "type": self.type, "params": self.params}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Intervention:
        return cls(tick=data["tick"], type=data["type"], params=data.get("params", {}))


@dataclass
class ExperimentConfig:
    """Complete configuration for a single experiment run.

    All fields are serializable to YAML/JSON for replication packages.
    """

    # --- Core ---
    name: str = "unnamed_experiment"
    description: str = ""
    random_seed: int = 42
    max_ticks: int = 10_000

    # --- World ---
    world_width: int = 100
    world_height: int = 100
    resource_types: list[str] = field(default_factory=lambda: ["food", "mineral", "water"])
    resource_density: float = 0.3
    regeneration_rate: float = 0.01

    # --- Agent ---
    initial_population: int = 50
    cognitive_capacity: float = 10.0
    energy_efficiency: float = 0.5
    social_affinity: float = 0.3
    mutation_rate: float = 0.01

    # --- Memory ---
    episodic_capacity: int = 1000
    semantic_capacity: int = 500
    decay_rate: float = 0.001
    inheritance_fraction: float = 0.3

    # --- Economy ---
    initial_energy: float = 100.0
    energy_decay_rate: float = 0.01
    trade_enabled: bool = True

    # --- Tools ---
    tool_mutation_rate: float = 0.05
    adoption_cost: float = 5.0
    initial_tools: int = 5

    # --- Persistence ---
    checkpoint_interval: int = 1000
    persistence_path: str = ""

    # --- Interventions ---
    interventions: list[Intervention] = field(default_factory=list)

    # --- Telemetry ---
    telemetry_batch_size: int = 100
    telemetry_flush_interval: float = 5.0
    metric_log_interval: int = 10

    # --- Replication ---
    num_replicates: int = 10
    replicate_seeds: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.replicate_seeds:
            self.replicate_seeds = [self.random_seed + i for i in range(self.num_replicates)]
        self._validate()

    def _validate(self) -> None:
        assert self.max_ticks > 0, "max_ticks must be positive"
        assert self.initial_population > 0, "initial_population must be positive"
        assert 0 < self.resource_density <= 1, "resource_density in (0, 1]"
        assert self.initial_energy > 0, "initial_energy must be positive"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "random_seed": self.random_seed,
            "max_ticks": self.max_ticks,
            "world": {
                "width": self.world_width,
                "height": self.world_height,
                "resource_types": self.resource_types,
                "resource_density": self.resource_density,
                "regeneration_rate": self.regeneration_rate,
            },
            "agent": {
                "initial_population": self.initial_population,
                "cognitive_capacity": self.cognitive_capacity,
                "energy_efficiency": self.energy_efficiency,
                "social_affinity": self.social_affinity,
                "mutation_rate": self.mutation_rate,
            },
            "memory": {
                "episodic_capacity": self.episodic_capacity,
                "semantic_capacity": self.semantic_capacity,
                "decay_rate": self.decay_rate,
                "inheritance_fraction": self.inheritance_fraction,
            },
            "economy": {
                "initial_energy": self.initial_energy,
                "energy_decay_rate": self.energy_decay_rate,
                "trade_enabled": self.trade_enabled,
            },
            "tools": {
                "mutation_rate": self.tool_mutation_rate,
                "adoption_cost": self.adoption_cost,
                "initial_tools": self.initial_tools,
            },
            "persistence": {
                "checkpoint_interval": self.checkpoint_interval,
                "path": self.persistence_path,
            },
            "interventions": [iv.to_dict() for iv in self.interventions],
            "telemetry": {
                "batch_size": self.telemetry_batch_size,
                "flush_interval": self.telemetry_flush_interval,
                "metric_log_interval": self.metric_log_interval,
            },
            "replication": {
                "num_replicates": self.num_replicates,
                "seeds": self.replicate_seeds,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        interventions = [Intervention.from_dict(iv) for iv in data.get("interventions", [])]
        return cls(
            name=data.get("name", "unnamed_experiment"),
            description=data.get("description", ""),
            random_seed=data.get("random_seed", 42),
            max_ticks=data.get("max_ticks", 10_000),
            world_width=data.get("world", {}).get("width", 100),
            world_height=data.get("world", {}).get("height", 100),
            resource_types=data.get("world", {}).get("resource_types", ["food"]),
            resource_density=data.get("world", {}).get("resource_density", 0.3),
            regeneration_rate=data.get("world", {}).get("regeneration_rate", 0.01),
            initial_population=data.get("agent", {}).get("initial_population", 50),
            cognitive_capacity=data.get("agent", {}).get("cognitive_capacity", 10),
            energy_efficiency=data.get("agent", {}).get("energy_efficiency", 0.5),
            social_affinity=data.get("agent", {}).get("social_affinity", 0.3),
            mutation_rate=data.get("agent", {}).get("mutation_rate", 0.01),
            episodic_capacity=data.get("memory", {}).get("episodic_capacity", 1000),
            semantic_capacity=data.get("memory", {}).get("semantic_capacity", 500),
            decay_rate=data.get("memory", {}).get("decay_rate", 0.001),
            inheritance_fraction=data.get("memory", {}).get("inheritance_fraction", 0.3),
            initial_energy=data.get("economy", {}).get("initial_energy", 100.0),
            energy_decay_rate=data.get("economy", {}).get("energy_decay_rate", 0.01),
            trade_enabled=data.get("economy", {}).get("trade_enabled", True),
            tool_mutation_rate=data.get("tools", {}).get("mutation_rate", 0.05),
            adoption_cost=data.get("tools", {}).get("adoption_cost", 5.0),
            initial_tools=data.get("tools", {}).get("initial_tools", 5),
            checkpoint_interval=data.get("persistence", {}).get("checkpoint_interval", 1000),
            persistence_path=data.get("persistence", {}).get("path", ""),
            interventions=interventions,
            telemetry_batch_size=data.get("telemetry", {}).get("batch_size", 100),
            telemetry_flush_interval=data.get("telemetry", {}).get("flush_interval", 5.0),
            metric_log_interval=data.get("telemetry", {}).get("metric_log_interval", 10),
            num_replicates=data.get("replication", {}).get("num_replicates", 10),
            replicate_seeds=data.get("replication", {}).get("seeds", []),
        )

    def to_yaml(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, path: str | Path) -> ExperimentConfig:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


@dataclass
class ExperimentResult:
    """Results from a single experiment run."""

    experiment_id: str
    config: ExperimentConfig
    status: ExperimentStatus
    tick_count: int = 0
    duration_seconds: float = 0.0
    agent_count_final: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    output_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "status": self.status.value,
            "tick_count": self.tick_count,
            "duration_seconds": self.duration_seconds,
            "agent_count_final": self.agent_count_final,
            "metrics": self.metrics,
            "error": self.error,
            "output_path": self.output_path,
        }


@dataclass
class ReplicationPackage:
    """Self-contained replication package for an experiment.

    Structure::
        experiment/
            config.yaml
            seeds.txt
            results/
                run_001/
                run_002/
                ...
            analysis/
                compute_metrics.py
                figures/
                summary_stats.json
            build_info.json
    """

    experiment_id: str
    root_path: Path
    config: ExperimentConfig
    results: list[ExperimentResult] = field(default_factory=list)
    git_commit_hash: str = ""
    python_version: str = ""
    platform_info: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        self.git_commit_hash = self._get_git_hash()
        self.python_version = sys.version
        self.platform_info = platform.platform()

    @staticmethod
    def _get_git_hash() -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    @staticmethod
    def _get_dependencies() -> dict[str, str]:
        """Capture installed package versions for replication."""
        deps: dict[str, str] = {}
        try:
            import pkg_resources

            for pkg in pkg_resources.working_set:
                deps[pkg.key] = pkg.version
        except Exception:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "freeze"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in result.stdout.strip().split("\n"):
                    if "==" in line:
                        name, _, ver = line.partition("==")
                        deps[name.strip()] = ver.strip()
            except Exception:
                pass
        return deps

    def build(self, output_dir: str | Path | None = None) -> Path:
        """Assemble the replication package on disk."""
        if output_dir is None:
            output_dir = EXPERIMENT_ROOT / self.experiment_id
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write config
        self.config.to_yaml(output_dir / "config.yaml")

        # Write seeds
        with open(output_dir / "seeds.txt", "w") as f:
            for seed in self.config.replicate_seeds:
                f.write(f"{seed}\n")

        # Write build info
        self.dependencies = self._get_dependencies()
        info = {
            "experiment_id": self.experiment_id,
            "created_at": self.created_at,
            "git_commit_hash": self.git_commit_hash,
            "python_version": self.python_version,
            "platform": self.platform_info,
            "dependencies": self.dependencies,
        }
        with open(output_dir / "build_info.json", "w") as f:
            json.dump(info, f, indent=2)

        # Create result directories
        for i, seed in enumerate(self.config.replicate_seeds):
            run_dir = output_dir / "results" / f"run_{i + 1:03d}"
            run_dir.mkdir(parents=True, exist_ok=True)
            with open(run_dir / "seed.txt", "w") as f:
                f.write(str(seed))

        # Create analysis directory
        (output_dir / "analysis" / "figures").mkdir(parents=True, exist_ok=True)

        return output_dir


class Experiment:
    """Base class for all experiments.

    Subclass and implement `run()` to define a new experiment type.
    Use the lifecycle methods to manage state.

    Example::

        class MyExperiment(Experiment):
            async def run(self) -> ExperimentResult:
                # ... setup subsystems ...
                # ... run simulation ...
                return ExperimentResult(...)
    """

    # Unique identifier for this experiment class (used in registry)
    type_id: ClassVar[str] = "base"

    def __init__(self, config: ExperimentConfig | None = None) -> None:
        self.config: ExperimentConfig = config or ExperimentConfig()
        self.status: ExperimentStatus = ExperimentStatus.DRAFT
        self.id: str = f"{self.type_id}_{secrets.token_hex(4)}"
        self._start_time: float = 0.0
        self._result: ExperimentResult | None = None

    # --- Lifecycle ---

    def configure(self, config: ExperimentConfig) -> None:
        """Set experiment configuration."""
        self.config = config
        self.status = ExperimentStatus.CONFIGURED

    def start(self) -> None:
        """Mark experiment as running."""
        self.status = ExperimentStatus.RUNNING
        self._start_time = time.time()

    def complete(self, result: ExperimentResult) -> None:
        """Mark experiment as completed."""
        self._result = result
        self.status = ExperimentStatus.COMPLETED

    def fail(self, error: str) -> ExperimentResult:
        """Mark experiment as failed."""
        self.status = ExperimentStatus.FAILED
        self._result = ExperimentResult(
            experiment_id=self.id,
            config=self.config,
            status=ExperimentStatus.FAILED,
            error=error,
        )
        return self._result

    def analyze(self) -> dict[str, float]:
        """Compute metrics from completed run. Override in subclass."""
        if self._result is None:
            return {}
        self.status = ExperimentStatus.ANALYZED
        return self._result.metrics

    # --- Core ---

    async def run(self) -> ExperimentResult:
        """Execute the experiment. Must be implemented by subclasses."""
        raise NotImplementedError

    async def run_replicates(self, num_workers: int = 1) -> list[ExperimentResult]:
        """Run all replicates defined in the config."""
        results: list[ExperimentResult] = []
        for i, seed in enumerate(self.config.replicate_seeds):
            config = self.config
            config.random_seed = seed
            config.name = f"{self.config.name}_rep_{i + 1}"
            result = await self.run()
            results.append(result)
        return results

    def to_replication_package(self) -> ReplicationPackage:
        """Create a replication package from experiment results."""
        pkg = ReplicationPackage(
            experiment_id=self.id,
            root_path=EXPERIMENT_ROOT / self.id,
            config=self.config,
            results=[self._result] if self._result else [],
        )
        return pkg

    # --- Serialization ---

    def save_state(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type_id": self.type_id,
            "status": self.status.value,
            "config": self.config.to_dict(),
        }

    def load_state(self, state: dict[str, Any]) -> None:
        self.id = state["id"]
        self.status = ExperimentStatus(state["status"])
        self.config = ExperimentConfig.from_dict(state["config"])
