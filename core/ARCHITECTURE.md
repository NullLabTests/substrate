# Substrate Architecture

## Overview

Substrate is a tick-based async simulation runtime written in Python 3.11+.
The system is composed of eight core subsystems wired together by a `Platform`
integration layer.

```
┌─────────────────────────────────────────────────────────────┐
│                         Platform                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Runtime  │ │  Event   │ │  Agent   │ │     Tick      │  │
│  │  Engine  │ │   Bus    │ │ Registry │ │   Scheduler   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬───────┘  │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌───────┴───────┐  │
│  │Persistence│ │Telemetry │ │ Logging  │ │   Recovery    │  │
│  │  Layer    │ │ Pipeline │ │          │ │    System     │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Runtime Architecture

The `RuntimeEngine` (`core/runtime/engine.py`) is the central coordinator.
It owns the tick loop, manages subsystem lifecycle, and handles graceful
shutdown via asyncio signals.

```
┌────────────────── RuntimeEngine ──────────────────┐
│                                                    │
│  initialize() → [recovery, event_bus, registry,    │
│                  scheduler, persistence, telemetry] │
│                                                    │
│  run() ─────────────────────────────────────────── │
│  ┌───────────── Main Loop ─────────────────────┐  │
│  │  while not shutdown:                        │  │
│  │    await tick_scheduler.next()              │  │
│  │    publish system.tick event                │  │
│  │    agent_registry.heartbeat_all()           │  │
│  │    run tick hooks                           │  │
│  │    telemetry.record("ticks", 1)             │  │
│  │    save_state every 100 ticks               │  │
│  └─────────────────────────────────────────────┘  │
│                                                    │
│  shutdown() → [reverse order initialize]           │
└────────────────────────────────────────────────────┘
```

**Lifecycle states:** CREATED → INITIALIZING → RUNNING → PAUSED → SHUTTING_DOWN → STOPPED

### Key design decisions
- The tick loop is an asyncio `Task` so it can be cancelled cleanly.
- SIGINT/SIGTERM handlers set an `asyncio.Event` that the main loop awaits.
- State is auto-saved every 100 ticks for crash recovery.
- Plugins register `tick_hooks` to run custom logic each tick.

---

## 2. Event Bus Design

The `EventBus` (`core/events/bus.py`) is an async publish/subscribe message
broker with topic-based routing, priority ordering, subscriber filtering,
and event replay for recovery.

```
┌──────────────────────── EventBus ────────────────────────┐
│                                                           │
│  subscribe(topic_pattern, handler, filters?, priority?)   │
│      ↓                                                    │
│  _subscriptions: Dict[topic_pattern, List[Subscription]]  │
│                                                           │
│  publish(event)                                           │
│      ↓                                                    │
│  _queue (asyncio.Queue)                                   │
│      ↓                                                    │
│  _dispatch_loop (background Task)                         │
│      ↓                                                    │
│  For each matching subscription:                          │
│    1. Topic match (supports *, ** wildcards)              │
│    2. Priority filter                                     │
│    3. Custom predicate filters                            │
│    4. await handler(event)                                │
│                                                           │
│  replay(topic_filter?, since?) → List[SystemEvent]        │
│      ↓                                                    │
│  _history (ring buffer, last N events retained)           │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Topic matching
- `"agent.spawned"` matches exactly `agent.spawned`
- `"agent.*"` matches `agent.spawned`, `agent.died`, etc.
- `"agent.**"` matches `agent.spawned`, `agent.worker.started`, etc.
- `"**"` matches everything

### Priorities (enum order)
```
CRITICAL (0) > HIGH (1) > NORMAL (2) > LOW (3)
```

### Event replay
The bus retains the last N events (default 10,000). The `replay()` method
filters by topic and optional `since` timestamp for recovery scenarios.

---

## 3. Agent Registry

The `AgentRegistry` (`core/registry/agent_registry.py`) tracks all active
agents with their metadata, status, and heartbeat timestamps.

```
┌────────────────── AgentRegistry ──────────────────┐
│                                                    │
│  register(id, name, type, metadata?) → AgentMeta   │
│  unregister(id) → AgentMeta | None                 │
│  get(id) → AgentMeta | None                        │
│  set_status(id, status) → AgentMeta | None         │
│  heartbeat(id) → bool                              │
│  heartbeat_all() → None                            │
│  list_agents(status?, type?) → List[AgentMeta]     │
│                                                    │
│  AgentMeta {                                        │
│    id, name, type, status,                         │
│    created_at, last_seen, metadata: Dict           │
│  }                                                 │
│                                                    │
│  Status values:                                    │
│    CREATED → ACTIVE → BUSY → IDLE                  │
│                   ↘ ERROR → SHUTDOWN                │
└────────────────────────────────────────────────────┘
```

---

## 4. Tick Scheduler

The `TickScheduler` (`core/scheduler/tick_scheduler.py`) generates
incrementing tick numbers at configurable intervals with pause/resume
and lifecycle hooks.

```
┌──────────────── TickScheduler ─────────────────┐
│                                                 │
│  ticks(interval) → AsyncIterator[int]           │
│      ↓                                          │
│  while True:                                    │
│    await pause_event.wait()   ← blocks if paused │
│    run pre_hooks(tick)                           │
│    tick_count += 1                               │
│    yield tick_count                              │
│    run post_hooks(tick)                          │
│    await asyncio.sleep(interval)                 │
│                                                 │
│  pause()  → pause_event.clear()                 │
│  resume() → pause_event.set()                   │
│                                                 │
│  add_pre_hook(hook)                             │
│  add_post_hook(hook)                            │
└─────────────────────────────────────────────────┘
```

---

## 5. Persistence Layer

The `PersistenceBackend` (`core/persistence/store.py`) abstract base class
defines the interface all storage backends must implement.

```
┌──────────── PersistenceBackend (ABC) ────────────┐
│                                                   │
│  initialize()            # open connections       │
│  shutdown()              # close connections      │
│  save(key, value)        # upsert                 │
│  load(key) → value       # get or None            │
│  delete(key) → bool      # remove                 │
│  list_keys(prefix)       # list by prefix         │
│  save_state() → dict     # serialize metadata     │
│  load_state(state)       # restore metadata       │
│                                                   │
└───────────────────────────────────────────────────┘
```

---

## 6. SQLite Backend

The `SQLiteBackend` (`storage/sqlite/backend.py`) implements the persistence
interface with aiosqlite, WAL mode, and automatic migrations.

```
┌──────────────── SQLiteBackend ─────────────────┐
│                                                 │
│  initialize():                                  │
│    1. Connect to .db file                       │
│    2. PRAGMA journal_mode=WAL                   │
│    3. PRAGMA foreign_keys=ON                    │
│    4. PRAGMA busy_timeout=5000                  │
│    5. PRAGMA synchronous=NORMAL                 │
│    6. Run pending migrations                     │
│                                                 │
│  save(key, value):                              │
│    INSERT OR REPLACE INTO store (key, value)    │
│                                                 │
│  Connection pool: 5 connections                 │
│  Migrations: storage/migrations/                │
└─────────────────────────────────────────────────┘
```

### Migration system

Migrations are auto-discovered modules in `storage/migrations/` named
`{version:03d}_*.py` containing `up(conn)` and `down(conn)` async functions.

```
storage/migrations/
├── __init__.py
├── runner.py          # Discovery + apply logic
└── 001_initial.py     # Creates store, agents, events, snapshots tables
```

---

## 7. Telemetry Pipeline

The `TelemetryPipeline` (`core/telemetry/pipeline.py`) collects, batches,
and writes metrics from all subsystems with pluggable exporters.

```
┌───────────── TelemetryPipeline ──────────────┐
│                                               │
│  record(name, value, labels?, unit?)          │
│      ↓                                        │
│  batch.append(MetricRecord)                   │
│      ↓ (batch_size reached OR flush_interval)  │
│  flush()                                       │
│      ↓                                        │
│  for exporter in exporters:                   │
│    await exporter.export(batch)               │
│                                               │
│  summarize(name) → MetricSummary              │
│    {count, min, max, mean, stdev, sum, last}  │
│                                               │
│  Built-in: ConsoleExporter (JSON lines)       │
└───────────────────────────────────────────────┘
```

---

## 8. Logging

The `StructuredLogger` (`core/logging/structured_logger.py`) produces
JSON-formatted log entries to stdout and/or a rotating file.

```json
{
  "timestamp": "2026-05-31T12:00:00.000000+00:00",
  "severity": "info",
  "module": "runtime.engine",
  "correlation_id": "abc-123",
  "message": "runtime_started",
  "payload": {"tick_interval": 0.1}
}
```

---

## 9. Recovery System

The `RecoverySystem` (`core/recovery/system.py`) detects crashes, replays
events, and restores subsystem state from snapshots.

```
┌────────────── RecoverySystem ──────────────┐
│                                             │
│  initialize():                              │
│    1. Load crash state from persistence     │
│    2. If crashed or no shutdown record:     │
│       a. Replay events from history         │
│       b. Restore subsystem snapshots        │
│       c. Clear crash flag                   │
│    3. If clean shutdown: skip               │
│                                             │
│  take_snapshot(tick, subsystem_states):     │
│    Persist for later recovery               │
│                                             │
│  shutdown():                                │
│    Save "crashed: false" flag              │
└─────────────────────────────────────────────┘
```

---

## 10. CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):

```
Push/PR → Lint (ruff) → Type check (mypy) → Test (pytest + coverage)
                                                  ↓
                                          Coverage ≥ 80%?
```

- Python versions: 3.11, 3.12, 3.13
- Tools: ruff (linting), mypy (type checking), pytest (testing), pytest-cov (coverage)
- Coverage threshold: 80%

---

## Subsystem Dependency Graph

```
Platform
  ├── Config (static, no deps)
  ├── Logger (no deps)
  ├── EventBus (no deps)
  ├── Persistence (no deps)
  ├── Recovery (depends on EventBus, Persistence, Logger)
  ├── AgentRegistry (no deps)
  ├── TickScheduler (optional Logger)
  ├── Telemetry (no deps)
  └── RuntimeEngine (depends on everything above)
```

### Initialization order
1. Logger
2. Persistence
3. Recovery
4. EventBus
5. AgentRegistry
6. TickScheduler
7. Telemetry
8. RuntimeEngine (initializes all above internally)

### Shutdown order (reverse of init)
1. RuntimeEngine
2. Recovery
3. Persistence
4. Telemetry
5. Logger
