"""Tests for TelemetryPipeline."""

from __future__ import annotations

import pytest
import pytest_asyncio

from core.telemetry.pipeline import TelemetryPipeline, MetricRecord, MetricSummary


class TestTelemetryPipeline:
    async def test_record_and_summarize(self, telemetry: TelemetryPipeline) -> None:
        for v in [10, 20, 30]:
            telemetry.record("test.metric", float(v))
        summary = telemetry.summarize("test.metric")
        assert summary is not None
        assert summary.count == 3
        assert summary.min == 10.0
        assert summary.max == 30.0
        assert summary.mean == 20.0
        assert summary.sum == 60.0

    async def test_summarize_missing(self, telemetry: TelemetryPipeline) -> None:
        summary = telemetry.summarize("nonexistent")
        assert summary is None

    async def test_record_with_labels(self, telemetry: TelemetryPipeline) -> None:
        telemetry.record("latency", 42.0, labels={"service": "api"})
        summary = telemetry.summarize("latency")
        assert summary is not None
        assert summary.last == 42.0

    async def test_flush(self, telemetry: TelemetryPipeline) -> None:
        telemetry.record("flush.test", 1.0)
        await telemetry.flush()
        assert len(telemetry._batch) == 0

    async def test_save_and_load_state(self, telemetry: TelemetryPipeline) -> None:
        telemetry.record("state.test", 99.0)
        state = await telemetry.save_state()
        assert len(state["history"]) > 0
