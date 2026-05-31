"""Migration runner that discovers and applies pending migrations."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiosqlite


async def _get_applied_versions(conn: aiosqlite.Connection) -> set[int]:
    """Return the set of migration version numbers already applied."""
    try:
        cursor = await conn.execute("SELECT version FROM schema_version")
        rows = await cursor.fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()


async def run_migrations(conn: aiosqlite.Connection) -> None:
    """Discover and apply all pending migrations in order.

    Migrations are modules under storage.migrations named {version:03d}_*.py
    that export ``up`` and ``down`` async functions.

    Args:
        conn: An open aiosqlite connection.
    """
    applied = await _get_applied_versions(conn)
    package = "storage.migrations"
    package_path = Path(__file__).parent

    migrations: list[tuple[int, str, Any]] = []

    for importer, modname, is_pkg in pkgutil.iter_modules([str(package_path)]):
        if is_pkg or modname == "runner" or modname == "__init__":
            continue
        try:
            parts = modname.split("_", 1)
            version = int(parts[0])
        except (ValueError, IndexError):
            continue
        module = importlib.import_module(f".{modname}", package)
        migrations.append((version, modname, module))

    migrations.sort(key=lambda x: x[0])

    for version, name, module in migrations:
        if version in applied:
            continue
        if not hasattr(module, "up"):
            continue
        await module.up(conn)
        await conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, name) VALUES (?, ?)",
            (version, name),
        )
        await conn.commit()
