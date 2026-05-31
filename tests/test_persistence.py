"""Tests for persistence interface and SQLite backend."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from core.persistence.store import PersistenceBackend
from storage.sqlite.backend import SQLiteBackend
from tests.conftest import InMemoryBackend


class TestInMemoryBackend:
    @pytest_asyncio.fixture
    async def backend(self) -> AsyncGenerator[InMemoryBackend, None]:
        b = InMemoryBackend()
        await b.initialize()
        yield b
        await b.shutdown()

    async def test_save_and_load(self, backend: InMemoryBackend) -> None:
        await backend.save("test_key", {"hello": "world"})
        val = await backend.load("test_key")
        assert val == {"hello": "world"}

    async def test_load_missing(self, backend: InMemoryBackend) -> None:
        val = await backend.load("nonexistent")
        assert val is None

    async def test_delete(self, backend: InMemoryBackend) -> None:
        await backend.save("del_key", {"data": 1})
        assert await backend.delete("del_key") is True
        assert await backend.delete("del_key") is False

    async def test_list_keys(self, backend: InMemoryBackend) -> None:
        await backend.save("alpha.1", {})
        await backend.save("alpha.2", {})
        await backend.save("beta.1", {})
        keys = await backend.list_keys(prefix="alpha")
        assert keys == ["alpha.1", "alpha.2"]
        all_keys = await backend.list_keys()
        assert all_keys == ["alpha.1", "alpha.2", "beta.1"]


class TestSQLiteBackend:
    @pytest_asyncio.fixture
    async def backend(self) -> AsyncGenerator[SQLiteBackend, None]:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        b = SQLiteBackend(db_path=db_path)
        await b.initialize()
        yield b
        await b.shutdown()
        Path(db_path).unlink(missing_ok=True)

    async def test_save_and_load(self, backend: SQLiteBackend) -> None:
        await backend.save("sqlite_key", {"nested": {"a": 1, "b": [2, 3]}})
        val = await backend.load("sqlite_key")
        assert val == {"nested": {"a": 1, "b": [2, 3]}}

    async def test_load_missing(self, backend: SQLiteBackend) -> None:
        val = await backend.load("missing_key")
        assert val is None

    async def test_delete(self, backend: SQLiteBackend) -> None:
        await backend.save("del_me", {"x": 1})
        assert await backend.delete("del_me") is True
        assert await backend.delete("del_me") is False

    async def test_list_keys(self, backend: SQLiteBackend) -> None:
        await backend.save("pre.a", {})
        await backend.save("pre.b", {})
        await backend.save("other.c", {})
        keys = await backend.list_keys(prefix="pre")
        assert keys == ["pre.a", "pre.b"]
        all_keys = await backend.list_keys()
        assert len(all_keys) == 3

    async def test_upsert(self, backend: SQLiteBackend) -> None:
        await backend.save("upsert", {"v": 1})
        await backend.save("upsert", {"v": 2})
        val = await backend.load("upsert")
        assert val == {"v": 2}

    async def test_initialize_creates_tables(self, backend: SQLiteBackend) -> None:
        import aiosqlite
        async with aiosqlite.connect(backend._db_path) as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = {row[0] for row in await cursor.fetchall()}
        assert "store" in tables
        assert "schema_version" in tables
        assert "agents" in tables
        assert "events" in tables
        assert "snapshots" in tables
