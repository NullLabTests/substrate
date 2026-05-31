"""Tests for config/settings."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import tempfile
import yaml

from config.settings import Settings


class TestSettings:
    def test_default_values(self) -> None:
        s = Settings()
        assert s.tick_interval == 0.1
        assert s.max_ticks == 0
        assert s.db_path == "substrate.db"
        assert s.log_level == "info"
        assert s.telemetry_batch_size == 100

    def test_env_override(self) -> None:
        os.environ["SUBSTRATE_TICK_INTERVAL"] = "0.5"
        os.environ["SUBSTRATE_LOG_LEVEL"] = "debug"
        try:
            s = Settings.load()
            assert s.tick_interval == 0.5
            assert s.log_level == "debug"
        finally:
            del os.environ["SUBSTRATE_TICK_INTERVAL"]
            del os.environ["SUBSTRATE_LOG_LEVEL"]

    def test_load_from_yaml(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump({"tick_interval": 0.2, "log_level": "warning"}, f)
            defaults_path = f.name

        try:
            s = Settings.load(defaults_path=defaults_path, local_path="nonexistent.yaml")
            assert s.tick_interval == 0.2
            assert s.log_level == "warning"
        finally:
            Path(defaults_path).unlink(missing_ok=True)

    def test_load_from_yaml_fallback(self) -> None:
        s = Settings.load(
            defaults_path="nonexistent_defaults.yaml",
            local_path="nonexistent_local.yaml",
        )
        assert s.tick_interval == 0.1
