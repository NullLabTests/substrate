"""SQLite persistence backend with WAL mode, connection pooling, and migrations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import aiosqlite

from core.logging.structured_logger import StructuredLogger
from core.persistence.store import PersistenceBackend
from storage.migrations.runner import run_migrations


class SQLiteBackend(PersistenceBackend):
    """SQLite implementation of the persistence interface.

    Uses aiosqlite for async access, WAL mode for concurrent reads,
    and runs migrations on initialize().
    """

    def __init__(
        self,
        db_path: str | Path = "substrate.db",
        logger: StructuredLogger | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None
        self._logger = logger
        self._pool: list[aiosqlite.Connection] = []
        self._pool_size = 5

    async def initialize(self) -> None:
        """Open database connection, enable WAL mode, run migrations."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(str(self._db_path))
        self._conn.row_factory = aiosqlite.Row

        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA cache_size=-64000")

        for _ in range(self._pool_size - 1):
            c = await aiosqlite.connect(str(self._db_path))
            c.row_factory = aiosqlite.Row
            self._pool.append(c)

        await run_migrations(self._conn)

        if self._logger:
            self._logger.info("sqlite_initialized", path=str(self._db_path))

    async def shutdown(self) -> None:
        """Close all database connections."""
        for c in self._pool:
            await c.close()
        self._pool.clear()
        if self._conn:
            await self._conn.close()
            self._conn = None
        if self._logger:
            self._logger.info("sqlite_shutdown")

    async def save_state(self) -> dict[str, Any]:
        """Return SQLite backend metadata."""
        return {"db_path": str(self._db_path)}

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore backend; no-op since we reinitialize from disk."""

    async def save(self, key: str, value: dict[str, Any]) -> None:
        """Upsert a key-value pair into the store table."""
        assert self._conn is not None
        raw = json.dumps(value, default=str)
        await self._conn.execute(
            """INSERT INTO store (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
                 value = excluded.value,
                 updated_at = datetime('now')""",
            (key, raw),
        )
        await self._conn.commit()

    async def load(self, key: str) -> dict[str, Any] | None:
        """Load a value by key from the store table."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT value FROM store WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    async def delete(self, key: str) -> bool:
        """Delete a key from the store. Returns True if deleted."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "DELETE FROM store WHERE key = ?", (key,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys, optionally filtered by prefix."""
        assert self._conn is not None
        if prefix:
            cursor = await self._conn.execute(
                "SELECT key FROM store WHERE key LIKE ? ORDER BY key",
                (f"{prefix}%",),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT key FROM store ORDER BY key"
            )
        rows = await cursor.fetchall()
        return [row["key"] for row in rows]
