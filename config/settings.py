"""Configuration management with YAML/env loading and typed settings."""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML config file, returning an empty dict on failure."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


class Settings(BaseModel):
    """Typed application settings with defaults.

    Loads from:
        1. ``config/defaults.yaml`` (built-in defaults)
        2. ``config/local.yaml`` (local overrides, gitignored)
        3. Environment variables (highest precedence)
    """

    # --- Runtime ---
    tick_interval: float = Field(
        default=0.1,
        description="Seconds between simulation ticks",
        alias="SUBSTRATE_TICK_INTERVAL",
    )
    max_ticks: int = Field(
        default=0,
        description="Maximum ticks before auto-stop (0 = unlimited)",
        alias="SUBSTRATE_MAX_TICKS",
    )

    # --- Persistence ---
    db_path: str = Field(
        default="substrate.db",
        description="Filesystem path for the SQLite database",
        alias="SUBSTRATE_DB_PATH",
    )

    # --- Logging ---
    log_level: str = Field(
        default="info",
        description="Minimum log level (debug, info, warning, error, critical)",
        alias="SUBSTRATE_LOG_LEVEL",
    )
    log_file: str | None = Field(
        default=None,
        description="Optional path to a log file (rotating file handler)",
        alias="SUBSTRATE_LOG_FILE",
    )

    # --- Telemetry ---
    telemetry_batch_size: int = Field(
        default=100,
        description="Max buffered metrics before auto-flush",
        alias="SUBSTRATE_TELEMETRY_BATCH_SIZE",
    )
    telemetry_flush_interval: float = Field(
        default=5.0,
        description="Seconds between automatic metric flushes",
        alias="SUBSTRATE_TELEMETRY_FLUSH_INTERVAL",
    )

    # --- Event Bus ---
    event_history_limit: int = Field(
        default=10_000,
        description="Max events retained in bus history",
        alias="SUBSTRATE_EVENT_HISTORY_LIMIT",
    )

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @classmethod
    def load(
        cls,
        defaults_path: str = "config/defaults.yaml",
        local_path: str = "config/local.yaml",
    ) -> Settings:
        """Create a Settings instance by merging YAML files and env vars.

        Args:
            defaults_path: Path to default YAML config.
            local_path: Path to local (overriding) YAML config.

        Returns:
            Fully populated Settings instance.
        """
        merged: dict[str, Any] = {}

        defaults = _load_yaml(Path(defaults_path))
        merged.update(defaults)

        local = _load_yaml(Path(local_path))
        merged.update(local)

        env_overrides: dict[str, Any] = {}
        for field_name, field_info in cls.model_fields.items():
            alias = field_info.alias or field_name
            env_val = os.environ.get(field_name.upper()) or os.environ.get(alias)
            if env_val is not None:
                env_overrides[field_name] = env_val

        merged.update(env_overrides)
        return cls(**merged)
