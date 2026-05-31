"""Telemetry pipeline collecting, batching, and writing metrics."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from statistics import mean, stdev
from typing import Any, Protocol


class MetricExporter(Protocol):
    """Protocol for pluggable metric exporters."""

    async def export(self, batch: list[MetricRecord]) -> None:
        """Write a batch of metric records."""


@dataclass
class MetricRecord:
    """A single metric data point."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    unit: str = ""


@dataclass
class MetricSummary:
    """Aggregated summary of a named metric."""

    name: str
    count: int
    min: float
    max: float
    mean: float
    stdev: float | None
    sum: float
    last: float


class TelemetryPipeline:
    """Collects, batches, and writes metrics from all subsystems.

    Supports pluggable exporters (console, file, network, etc.)
    and auto-flushes on a configurable interval.
    """

    def __init__(
        self,
        exporters: list[MetricExporter] | None = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ) -> None:
        self._exporters: list[MetricExporter] = exporters or []
        self._batch: list[MetricRecord] = []
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._worker_task: asyncio.Task[None] | None = None
        self._initialized = False
        self._history: list[MetricRecord] = []
        self._history_limit = 10_000

    async def initialize(self) -> None:
        """Start the background flush worker."""
        self._initialized = True
        self._worker_task = asyncio.create_task(self._flush_loop())

    async def shutdown(self) -> None:
        """Flush remaining metrics and stop the worker."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        await self.flush()
        self._initialized = False

    async def save_state(self) -> dict[str, Any]:
        """Serialize recent telemetry history."""
        return {
            "history": [
                asdict(r) for r in self._history[-100:]
            ]
        }

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore telemetry state (no-op)."""

    def add_exporter(self, exporter: MetricExporter) -> None:
        """Register an additional metric exporter.

        Args:
            exporter: An object implementing MetricExporter protocol.
        """
        self._exporters.append(exporter)

    def record(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        unit: str = "",
    ) -> None:
        """Record a single metric value.

        Args:
            name: Metric name (e.g. 'ticks', 'agents.spawned').
            value: Numeric value.
            labels: Optional key-value dimensions.
            unit: Optional unit string (e.g. 'ms', 'bytes').
        """
        record = MetricRecord(
            name=name,
            value=value,
            labels=labels or {},
            unit=unit,
        )
        self._batch.append(record)
        self._history.append(record)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit:]

        if len(self._batch) >= self._batch_size:
            asyncio.ensure_future(self.flush())

    async def flush(self) -> None:
        """Flush buffered metrics to all exporters."""
        if not self._batch:
            return
        batch = self._batch[:]
        self._batch.clear()
        for exporter in self._exporters:
            try:
                await exporter.export(batch)
            except Exception:
                pass

    def summarize(self, name: str) -> MetricSummary | None:
        """Compute summary statistics for a named metric.

        Args:
            name: Metric name to summarize.

        Returns:
            MetricSummary or None if no records exist.
        """
        values = [r.value for r in self._history if r.name == name]
        if not values:
            return None
        return MetricSummary(
            name=name,
            count=len(values),
            min=min(values),
            max=max(values),
            mean=mean(values),
            stdev=stdev(values) if len(values) > 1 else None,
            sum=sum(values),
            last=values[-1],
        )

    async def _flush_loop(self) -> None:
        """Background loop that periodically flushes batched metrics."""
        while True:
            try:
                await asyncio.sleep(self._flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception:
                pass


class ConsoleExporter:
    """Exports metrics to stdout as JSON lines."""

    async def export(self, batch: list[MetricRecord]) -> None:
        for record in batch:
            print(json.dumps(asdict(record)))
