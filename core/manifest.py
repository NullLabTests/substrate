from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.seed import SimulationSeed


@dataclass
class ExperimentManifest:
    experiment_id: str
    seed: SimulationSeed
    config: dict[str, Any]
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    code_version: str | None = None
    python_version: str | None = None
    dependencies: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    expected_metrics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.code_version is None:
            self.code_version = _get_git_commit()
        if self.python_version is None:
            self.python_version = sys.version

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentManifest:
        data["seed"] = SimulationSeed.from_dict(data["seed"])
        return cls(**data)

    @classmethod
    def from_json(cls, path: str | Path) -> ExperimentManifest:
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(self.to_json())
        return path


def _get_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None
