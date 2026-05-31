"""Initial migration: creates agents, events, snapshots, and store tables."""

MIGRATION_VERSION = 1
MIGRATION_NAME = "001_initial"

UP_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS store (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2,
    payload TEXT NOT NULL DEFAULT '{}',
    source TEXT,
    correlation_id TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subsystem TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT '{}',
    tick_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_topic ON events(topic);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_snapshots_subsystem ON snapshots(subsystem);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS snapshots;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS store;
DROP TABLE IF EXISTS schema_version;
"""


async def up(conn) -> None:
    """Apply the initial migration."""
    await conn.executescript(UP_SQL)
    await conn.commit()


async def down(conn) -> None:
    """Roll back the initial migration."""
    await conn.executescript(DOWN_SQL)
    await conn.commit()
