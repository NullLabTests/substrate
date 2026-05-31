# Architecture

## System Overview

The platform is organized as a layered architecture. Each layer provides well-defined interfaces to the layer above and depends on services from the layer below.

```
                    ┌─────────────────────────────────────────────┐
                    │           Telemetry & Logging                │
                    │  (metrics export, structured logging,       │
                    │   trace collection, dashboards)              │
                    └─────────────────────────────────────────────┘
                                      │
    ┌─────────────────────────────────┼─────────────────────────────────┐
    │              │                  │                  │              │
    │  ┌───────────┴──────────┐  ┌───┴────────────┐  ┌──┴───────────┐  │
    │  │   Civilization       │  │   Economy       │  │   Social     │  │
    │  │   • Agent model      │  │   • Energy      │  │   • Messages │  │
    │  │   • World state      │  │   • Resources   │  │   • Alliances│  │
    │  │   • Environment      │  │   • Trade       │  │   • Rep      │  │
    │  └──────────────────────┘  └─────────────────┘  └─────────────┘  │
    │                    │                    │                         │
    │  ┌─────────────────┴────────────────────┴──────────────────┐     │
    │  │                    Memory Systems                        │     │
    │  │      (episodic, semantic, aging, inheritance)            │     │
    │  └──────────────────────────────────────────────────────────┘     │
    │                    │                    │                         │
    │  ┌─────────────────┴────────────────────┴──────────────────┐     │
    │  │   Evolution Layer     │        Tools Layer               │     │
    │  │   • Reproduction      │        • Creation                │     │
    │  │   • Mutation          │        • Adoption                │     │
    │  │   • Lineage           │        • Mutation                │     │
    │  │   • Selection         │        • Lineage tracking        │     │
    │  └───────────────────────┴──────────────────────────────────┘     │
    └─────────────────────────────────┬─────────────────────────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      │           Event Bus             │
                      │  (pub/sub, topics, ordering,    │
                      │   replay, delivery guarantees)  │
                      └───────────────────────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      │         Runtime Layer           │
                      │  • Tick scheduler               │
                      │  • Agent lifecycle              │
                      │  • Agent registry               │
                      │  • Recovery coordinator          │
                      └───────────────────────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      │       Orchestrator Layer        │
                      │  • Subsystem wiring             │
                      │  • Lifecycle coordination       │
                      │  • Dependency injection         │
                      └───────────────────────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      │       Persistence Layer        │
                      │  (SQLite, WAL mode,           │
                      │   migrations, checkpointing)   │
                      └───────────────────────────────┘
```

## Subsystem Protocol

Every major subsystem must implement the following four methods. This ensures uniform lifecycle management, state persistence, and crash recovery across the entire platform.

```python
class Subsystem(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        """Allocate resources, open connections, start background tasks."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release resources, close connections, stop background tasks."""

    @abstractmethod
    async def save_state(self) -> dict[str, Any]:
        """Serialize subsystem state for persistence/snapshots."""

    @abstractmethod
    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore subsystem state from serialized data."""
```

### Protocol Guarantees

- **initialize()** is idempotent — calling it on an already-initialized subsystem is safe.
- **shutdown()** is idempotent — calling it on an already-shutdown subsystem is safe.
- **save_state()** always returns a JSON-serializable dict.
- **load_state(None)** is a no-op (gracefully handles missing state on first run).
- The pair **(save_state, load_state)** is symmetric:
  - `load_state(await save_state())` restores the subsystem to its previous state.

### Subsystems Implementing the Protocol

| Subsystem | Module | initialize | shutdown | save_state | load_state |
|-----------|--------|:---:|:---:|:---:|:---:|
| EventBus | `core/events/bus.py` | ✅ | ✅ | ✅ | ✅ |
| AgentRegistry | `core/registry/agent_registry.py` | ✅ | ✅ | ✅ | ✅ |
| TickScheduler | `core/scheduler/tick_scheduler.py` | ✅ | ✅ | ✅ | ✅ |
| TelemetryPipeline | `core/telemetry/pipeline.py` | ✅ | ✅ | ✅ | ✅ |
| StructuredLogger | `core/logging/structured_logger.py` | ✅ | ✅ | ✅ | ✅ |
| RecoverySystem | `core/recovery/system.py` | ✅ | ✅ | ✅ | ✅ |
| RuntimeEngine | `core/runtime/engine.py` | ✅ | ✅ | ✅ | ✅ |
| SQLiteBackend | `storage/sqlite/backend.py` | ✅ | ✅ | ✅ | ✅ |
| Orchestrator | `orchestrator/__init__.py` | ✅ | ✅ | ✅ | ✅ |

---

## 1. Orchestrator (`orchestrator/`)

### Purpose

The Orchestrator is the top-level integration point. It wires all subsystems together, manages their lifecycle in dependency order, and coordinates state persistence for recovery snapshots.

### Dependency Order (initialization)

```
logger → persistence → recovery → event_bus → registry → scheduler → telemetry → runtime
```

### Dependency Order (shutdown)

Reverse of initialization. Each subsystem is shut down only after the subsystems that depend on it have already stopped.

### State Snapshot

`Orchestrator.save_state()` collects serialized state from every subsystem and passes it to `RecoverySystem.take_snapshot()`, which persists the combined snapshot for crash recovery.

### Key Interface

```python
class Orchestrator:
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def save_state(self) -> None: ...
    async def load_state(self) -> None: ...

    # Subsystem accessors
    @property
    def runtime(self) -> RuntimeEngine: ...
    @property
    def event_bus(self) -> EventBus: ...
    @property
    def registry(self) -> AgentRegistry: ...
    @property
    def scheduler(self) -> TickScheduler: ...
    @property
    def telemetry(self) -> TelemetryPipeline: ...
    @property
    def logger(self) -> StructuredLogger: ...
```

---

## 2. Configuration (`config/`)

### Purpose

Centralized, typed configuration management with three-tier precedence:
1. Built-in defaults (`config/defaults.yaml`)
2. Local overrides (`config/local.yaml`, gitignored)
3. Environment variables (highest precedence)

### Implementation

Uses Pydantic `BaseModel` for type validation and coercion. Each setting field declares its env-var alias for automatic environment variable binding.

```python
class Settings(BaseModel):
    tick_interval: float = Field(default=0.1, alias="SUBSTRATE_TICK_INTERVAL")
    max_ticks: int = Field(default=0, alias="SUBSTRATE_MAX_TICKS")
    db_path: str = Field(default="substrate.db", alias="SUBSTRATE_DB_PATH")
    log_level: str = Field(default="info", alias="SUBSTRATE_LOG_LEVEL")
    log_file: str | None = Field(default=None, alias="SUBSTRATE_LOG_FILE")
    telemetry_batch_size: int = Field(default=100, alias="SUBSTRATE_TELEMETRY_BATCH_SIZE")
    telemetry_flush_interval: float = Field(default=5.0, alias="SUBSTRATE_TELEMETRY_FLUSH_INTERVAL")
    event_history_limit: int = Field(default=10_000, alias="SUBSTRATE_EVENT_HISTORY_LIMIT")
```

### Loading Order

```python
settings = Settings.load()
# 1. Reads config/defaults.yaml
# 2. Reads config/local.yaml (overrides defaults)
# 3. Reads environment variables (overrides YAML)
# 4. Returns validated Settings instance
```

---

## 3. Event Bus (`core/events/`)

### Purpose

Central communication backbone. All inter-component communication passes through the event bus, enabling replay, auditing, and fully decoupled architecture.

### SystemEvent

```python
@dataclass
class SystemEvent:
    topic: str                    # Dot-separated event topic (e.g. 'agent.spawned')
    priority: EventPriority       # CRITICAL(0), HIGH(1), NORMAL(2), LOW(3)
    payload: dict[str, Any]       # JSON-serializable data
    source: str | None            # Identifier of emitting subsystem
    correlation_id: str | None    # Grouping identifier for tracing
    timestamp: str | None         # ISO-8601; auto-set if omitted
```

### EventBus

- **Topic-based pub/sub** with glob-style wildcards (`*`, `**`)
- **Per-subscriber filters** (predicate functions)
- **Priority filtering** (subscribers opt-in to minimum priority level)
- **History ring buffer** (configurable limit, default 10,000 events)
- **Replay** — query history by topic pattern and/or timestamp
- **Async dispatch** via background worker task with `asyncio.Queue`
- **Sync bridge** (`_SyncBusBridge`) for synchronous code paths

### Topics

| Topic | Publishers | Subscribers |
|-------|-----------|-------------|
| `agent.spawn` | Registry | Civilization, Persistence |
| `agent.act` | Runtime | Civilization, Memory, Persistence |
| `agent.die` | Runtime | Registry, Evolution, Persistence |
| `social.message` | Social | Memory, Telemetry |
| `social.alliance` | Social | Reputation, Telemetry |
| `economy.trade` | Economy | Social, Memory, Telemetry |
| `tool.create` | Tools | Registry, Evolution, Telemetry |
| `tool.adopt` | Tools | Registry, Telemetry |
| `tool.abandon` | Tools | Registry, Telemetry |
| `system.tick` | Runtime | All |
| `system.bus.initialized` | EventBus | All |
| `system.recovery.state_restored.*` | Recovery | Targeted subsystems |

### Key Operations

```python
# Subscribe with optional filters and priority
sub = bus.subscribe("agents.*", handler, filters=[...], priority=EventPriority.HIGH)

# Unsubscribe
bus.unsubscribe(sub)

# Publish (async, queued)
await bus.publish(SystemEvent(topic="agent.spawned", payload={"id": "..."}))

# Replay (synchronous, from history)
events = bus.replay(topic_filter="agents.*", since="2025-01-01T00:00:00Z")
```

---

## 4. Agent Registry (`core/registry/`)

### Purpose

Central repository of all agent identities and their current lifecycle state. Provides lookup, enumeration, and state transition operations.

### AgentMetadata

```python
class AgentMetadata(BaseModel):
    id: str
    name: str
    agent_type: str            # e.g. 'worker', 'coordinator'
    status: str                # created, active, idle, busy, error, shutdown
    created_at: str            # ISO-8601 timestamp
    last_seen: str             # ISO-8601 heartbeat timestamp
    metadata: dict[str, Any]   # Arbitrary key-value payload
```

### AgentStatus

| Status | Description |
|--------|-------------|
| `created` | Agent registered but not yet active |
| `active` | Agent is running and participating |
| `idle` | Agent alive but not currently acting |
| `busy` | Agent is processing an action |
| `error` | Agent encountered a fault |
| `shutdown` | Agent has been terminated |

### Key Operations

```python
registry.register("agent-1", "Alpha", "worker", metadata={"energy": 100})
meta = registry.get("agent-1")
registry.set_status("agent-1", AgentStatus.ACTIVE)
await registry.heartbeat("agent-1")
await registry.heartbeat_all()
agents = registry.list_agents(status=AgentStatus.ACTIVE, agent_type="worker")
removed = registry.unregister("agent-1")
```

---

## 5. Tick Scheduler (`core/scheduler/`)

### Purpose

Drives the simulation's main loop by generating ticks at a configurable interval. Supports pause/resume, pre/post hooks, and async iteration.

### Key Interface

```python
class TickScheduler:
    @asynccontextmanager
    async def ticks(self, interval: float = 0.1) -> AsyncIterator[AsyncIterator[int]]:
        """Context manager yielding an async iterator of tick numbers."""

    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def add_pre_hook(self, hook: Callable[[int], Coroutine]) -> None: ...
    def add_post_hook(self, hook: Callable[[int], Coroutine]) -> None: ...
```

### Usage

```python
async with scheduler.ticks(interval=0.05) as ticker:
    async for tick in ticker:
        await process_tick(tick)
```

### Tick Flow

1. Wait for pause event (allows pause/resume)
2. Execute all pre-hooks
3. Increment tick counter
4. Yield tick number to consumer
5. Execute all post-hooks
6. Sleep for configured interval

---

## 6. Runtime Engine (`core/runtime/`)

### Purpose

The runtime engine is the core simulation coordinator. It owns the main loop, manages subsystem initialization/shutdown order, handles OS signals for graceful termination, and maintains the current simulation state.

### Lifecycle States

```
CREATED → INITIALIZING → RUNNING → SHUTTING_DOWN → STOPPED
                              ↓
                          PAUSED
```

### Key Interface

```python
class RuntimeEngine:
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def save_state(self) -> dict[str, Any]: ...
    async def load_state(self) -> dict[str, Any]: ...

    async def run(self) -> None: ...
    async def stop(self) -> None: ...
    def register_tick_hook(self, hook: Callable[[int], Coroutine]) -> None: ...
```

### Tick Loop

The tick loop operates at a configurable tick rate (default: 10 Hz). Each tick:

1. **Publish system.tick event** — notifies all subsystems
2. **Heartbeat all agents** — updates last_seen timestamps
3. **Execute tick hooks** — custom per-tick logic
4. **Record telemetry** — increment tick counter
5. **Periodic checkpoint** — save state every 100 ticks

### Signal Handling

The runtime registers handlers for SIGINT and SIGTERM to perform an orderly shutdown on process termination.

```python
loop.add_signal_handler(sigint, self._signal_handler)
loop.add_signal_handler(sigterm, self._signal_handler)
```

---

## 7. Persistence Layer (`storage/`)

### Purpose

Ensures simulation state survives process termination. Provides a key-value store abstraction over SQLite with automatic schema migrations and WAL mode for concurrent read access.

### Abstract Interface

```python
class PersistenceBackend(ABC):
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...

    async def save(self, key: str, value: dict[str, Any]) -> None: ...
    async def load(self, key: str) -> dict[str, Any] | None: ...
    async def delete(self, key: str) -> bool: ...
    async def list_keys(self, prefix: str = "") -> list[str]: ...
```

### SQLite Implementation

- **Async**: Uses `aiosqlite` for non-blocking database access
- **WAL mode**: Write-Ahead Logging for concurrent reads during writes
- **Connection pool**: Maintains multiple connections (default pool size: 5)
- **PRAGMA settings**:
  - `journal_mode=WAL` — concurrent read/write
  - `foreign_keys=ON` — referential integrity
  - `busy_timeout=5000` — 5s wait on lock contention
  - `synchronous=NORMAL` — durability with performance
  - `cache_size=-64000` — 64MB page cache

### Schema

```sql
-- Schema version tracking
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Key-value store for arbitrary state
CREATE TABLE store (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,           -- JSON-serialized
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Agent table for direct agent state persistence
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT NOT NULL DEFAULT '{}'
);

-- Event log
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2,
    payload TEXT NOT NULL DEFAULT '{}',
    source TEXT,
    correlation_id TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Recovery snapshots
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subsystem TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT '{}',
    tick_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_events_topic ON events(topic);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_snapshots_subsystem ON snapshots(subsystem);
```

### Migrations

Migrations are auto-discovered modules under `storage/migrations/` named `{version:03d}_*.py`. Each exports `up(conn)` and `down(conn)` async functions.

```python
# storage/migrations/001_initial.py
async def up(conn) -> None:
    await conn.executescript(UP_SQL)
    await conn.commit()

async def down(conn) -> None:
    await conn.executescript(DOWN_SQL)
    await conn.commit()
```

Migration runner flow:
1. Query `schema_version` for already-applied versions
2. Discover all migration modules, parse version from filename
3. Sort by version, apply unapplied migrations in order
4. Record each applied migration in `schema_version`

---

## 8. Recovery System (`core/recovery/`)

### Purpose

Ensure that a simulation crash does not lose more than a configurable amount of work. Detect crashes on startup, replay events, and restore subsystems from the last snapshot.

### Mechanism

1. **Crash detection** on startup by checking `recovery.crash_state` in persistence
2. **Event replay** — restore the event bus history from the last persisted state
3. **Snapshot restoration** — load persisted subsystem snapshot and emit recovery events
4. **Clean shutdown marking** — writes `{"crashed": false}` on graceful shutdown

### Crash Detection Logic

| State in DB | Detection Result |
|-------------|-----------------|
| No `recovery.crash_state` key | Crash detected (no shutdown record) |
| `{"crashed": True}` | Crash detected |
| `{"crashed": False}` | Clean shutdown — no recovery needed |

### Snapshot Lifecycle

```python
# During normal operation (every N ticks):
await recovery.take_snapshot(tick_count, subsystem_states)

# On startup with crash detection:
crash_state = await recovery._detect_crash()
if crash_state:
    await recovery._replay_events()
    await recovery._restore_subsystem_states()
    await recovery._clear_crash_state()
```

---

## 9. Telemetry Pipeline (`core/telemetry/`)

### Purpose

Collect, batch, and export metrics from all subsystems. Provides both real-time and post-hoc analysis capability.

### Architecture

```
Subsystems → TelemetryPipeline.record(name, value, labels)
                  │
                  ├── Batch buffer (configurable size)
                  │
                  ├── Auto-flush (configurable interval)
                  │
                  └── MetricExporters (pluggable)
                       ├── ConsoleExporter (stdout JSON lines)
                       └── Custom exporters (file, network, Prometheus, etc.)
```

### MetricExporter Protocol

```python
class MetricExporter(Protocol):
    async def export(self, batch: list[MetricRecord]) -> None: ...
```

### MetricRecord

```python
@dataclass
class MetricRecord:
    name: str                     # e.g. 'ticks', 'agents.spawned'
    value: float                  # Numeric value
    labels: dict[str, str]        # e.g. {"service": "runtime"}
    timestamp: str                # ISO-8601
    unit: str                     # e.g. 'ms', 'bytes'
```

### MetricSummary

Supports computing summary statistics (count, min, max, mean, stdev, sum, last) for any named metric from the history buffer.

### Logged Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| `ticks` | count | Total ticks processed |
| `agents.spawned` | count | Agents spawned this interval |
| `agents.died` | count | Agents terminated this interval |
| `agents.active` | count | Currently active agents |
| `events.published` | count | Events published this interval |
| `latency` | ms | Operation latency samples |

---

## 10. Structured Logging (`core/logging/`)

### Purpose

JSON-structured logging with severity levels, correlation IDs, and rotating file output. All log entries are machine-parseable for log aggregation systems.

### Log Entry Format

```json
{
    "timestamp": "2025-01-01T00:00:00.000000+00:00",
    "severity": "info",
    "module": "runtime.engine",
    "correlation_id": null,
    "message": "runtime_started",
    "payload": {"tick_interval": 0.1, "started_at": "2025-01-01T00:00:00+00:00"}
}
```

### Log Levels

| Level | Method |
|-------|--------|
| debug | `logger.debug(msg, **payload)` |
| info | `logger.info(msg, **payload)` |
| warning | `logger.warning(msg, **payload)` |
| error | `logger.error(msg, **payload)` |
| critical | `logger.critical(msg, **payload)` |

### Outputs

- **stdout**: JSON lines for real-time consumption
- **Rotating file**: Configurable path, max bytes, backup count (default: 10MB, 5 backups)

---

## 11. GitHub Actions CI (`.github/workflows/`)

### Purpose

Automated testing, linting, type-checking, and coverage enforcement for the substrate platform.

### Workflow: `substrate-ci.yml`

```yaml
Triggers:
  - push to main
  - pull requests targeting main

Jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Set up Python 3.11
      - Install dependencies (pip install -e ".[dev]")
      - Run linter (ruff check)
      - Run type checker (mypy)
      - Run tests with coverage (pytest --cov --cov-fail-under=80)
```

### Coverage Requirements

- All owned modules (`core`, `storage`, `config`, `orchestrator`) must maintain **≥80% line coverage**.
- Coverage is enforced via `--cov-fail-under=80` in CI.
- New code must maintain or improve coverage.

### CI Quality Gates

| Gate | Tool | Threshold |
|------|------|-----------|
| Linting | `ruff` | Zero errors |
| Type checking | `mypy` (strict) | Zero errors |
| Unit tests | `pytest` | 100% pass rate |
| Coverage | `pytest-cov` | ≥80% line coverage |

---

## 12. Testing Strategy (`tests/`)

### Principles

1. **Every subsystem is testable in isolation** via its initialize/shutdown protocol and the `InMemoryBackend` persistence mock.
2. **Async-first** — all tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
3. **Deterministic** — tests use controlled tick intervals and manual event propagation.
4. **State round-trip** — every subsystem is tested for `save_state() → load_state()` symmetry.

### Test Fixtures (`tests/conftest.py`)

| Fixture | Type | Description |
|---------|------|-------------|
| `event_bus` | EventBus | Initialized async event bus |
| `logger` | StructuredLogger | Debug-level logger for tests |
| `persistence` | InMemoryBackend | In-memory key-value store |
| `registry` | AgentRegistry | Fresh agent registry |
| `scheduler` | TickScheduler | Scheduler with test logger |
| `telemetry` | TelemetryPipeline | Telemetry with no exporters |

### InMemoryBackend

A drop-in replacement for `PersistenceBackend` that stores data in a `dict`. Used by all subsystem tests to avoid SQLite dependency in unit tests.

### Coverage Targets

| Module | Current Coverage | Target |
|--------|:---:|:---:|
| `config/__init__` | 100% | 100% |
| `config/settings` | 100% | 100% |
| `core/events/bus` | 92% | ≥80% |
| `core/logging/structured_logger` | 100% | 100% |
| `core/persistence/store` | 95% | ≥80% |
| `core/recovery/system` | 94% | ≥80% |
| `core/registry/agent_registry` | 95% | ≥80% |
| `core/runtime/engine` | 91% | ≥80% |
| `core/scheduler/tick_scheduler` | 97% | ≥80% |
| `core/telemetry/pipeline` | 85% | ≥80% |
| `orchestrator/__init__` | 0% | ≥80% |
| `storage/migrations/runner` | 84% | ≥80% |
| `storage/sqlite/backend` | 96% | ≥80% |

---

## 13. Durability Guarantees

### Crash Resilience

1. **Periodic checkpoints**: Full state snapshots every N ticks (configurable, default 100)
2. **Atomic writes**: SQLite transactions ensure checkpoint writes are atomic
3. **Crash detection**: Recovery system detects unclean shutdowns on startup
4. **Event replay**: Event bus history is persisted and replayed on recovery
5. **State restoration**: `load_state()` restores each subsystem to its pre-crash state

### Runtime Guarantees

- At most `checkpoint_interval + 1` ticks of work lost on crash
- Graceful shutdown via OS signal handlers (SIGINT, SIGTERM)
- Context manager (`managed_run()`) for safe lifecycle in hosting environments

---

## 14. Package Structure

```
substrate/                        # Package name: "substrate"
├── config/                       # Configuration management
│   ├── __init__.py              # Exports Settings
│   ├── settings.py              # Pydantic settings with YAML/env loading
│   └── defaults.yaml            # Default configuration values
├── core/                         # Core subsystems
│   ├── events/                   # Event bus
│   │   ├── __init__.py
│   │   └── bus.py               # EventBus, SystemEvent, EventPriority
│   ├── logging/                  # Structured logging
│   │   ├── __init__.py
│   │   └── structured_logger.py # JSON logger with file rotation
│   ├── persistence/              # Persistence abstraction
│   │   ├── __init__.py
│   │   └── store.py             # PersistenceBackend ABC
│   ├── recovery/                 # Crash recovery
│   │   ├── __init__.py
│   │   └── system.py            # Crash detection, snapshot, replay
│   ├── registry/                 # Agent registry
│   │   ├── __init__.py
│   │   └── agent_registry.py    # Agent identity and lifecycle
│   ├── runtime/                  # Simulation runtime
│   │   ├── __init__.py
│   │   └── engine.py            # Main loop, lifecycle, signal handling
│   ├── scheduler/                # Tick scheduler
│   │   ├── __init__.py
│   │   └── tick_scheduler.py    # Async tick generator with hooks
│   └── telemetry/                # Metrics pipeline
│       ├── __init__.py
│       └── pipeline.py          # Collection, batching, export
├── orchestrator/                 # Top-level integration
│   └── __init__.py              # Wires all subsystems together
├── storage/                      # Persistence backends
│   ├── sqlite/
│   │   ├── __init__.py
│   │   └── backend.py           # SQLite with WAL, pool, migrations
│   └── migrations/
│       ├── __init__.py
│       ├── runner.py             # Migration discovery and application
│       └── 001_initial.py        # Initial schema
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures, InMemoryBackend
│   ├── test_config.py
│   ├── test_event_bus.py
│   ├── test_logger.py
│   ├── test_persistence.py
│   ├── test_recovery.py
│   ├── test_registry.py
│   ├── test_runtime.py
│   ├── test_scheduler.py
│   └── test_telemetry.py
└── .github/                      # CI/CD
    └── workflows/
        └── substrate-ci.yml     # Substrate CI pipeline
```

---

## 15. Design Decisions

### Why rename `platform/` to `orchestrator/`?

The directory `platform/` shadows Python's stdlib `platform` module (used by `uuid`, `os`, and other built-in modules). This caused an import cycle: `pydantic → uuid → platform (stdlib) → platform/__init__.py (local) → pydantic`. Renaming to `orchestrator/` resolves this collision while maintaining semantic clarity.

### Why use `aiosqlite` instead of `sqlite3`?

The entire runtime is async (tick loop, event bus, lifecycle). Using `aiosqlite` allows non-blocking database operations within the async event loop without blocking the tick scheduler.

### Why Pydantic for settings?

Pydantic provides:
- Automatic type coercion (e.g., `"0.5"` → `0.5` for float fields)
- Environment variable binding via field aliases
- Validation error messages with clear context
- Serialization/deserialization for state persistence

### Why InMemoryBackend for tests?

Using an in-memory dict instead of SQLite for unit tests provides:
- Faster test execution (no I/O)
- No file cleanup needed
- Deterministic behavior
- Complete isolation between test runs
