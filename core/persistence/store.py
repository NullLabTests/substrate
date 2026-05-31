"""Abstract persistence layer interface for storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PersistenceBackend(ABC):
    """Abstract base class for all storage backends.

    Every backend must implement initialize, shutdown, save, load, delete,
    and list_keys methods to support the substrate persistence contract.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend (open connections, create pools, etc.)."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Close all connections and release resources."""

    @abstractmethod
    async def save(self, key: str, value: dict[str, Any]) -> None:
        """Persist a value by key.

        Args:
            key: Namespaced identifier (e.g. 'runtime_state').
            value: Arbitrary JSON-serializable dictionary.
        """

    @abstractmethod
    async def load(self, key: str) -> dict[str, Any] | None:
        """Retrieve a previously saved value by key.

        Args:
            key: The namespaced identifier.

        Returns:
            The stored dictionary, or None if the key does not exist.
        """

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Remove a persisted value by key.

        Args:
            key: The namespaced identifier.

        Returns:
            True if the key existed and was deleted, False otherwise.
        """

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all stored keys, optionally filtered by prefix.

        Args:
            prefix: Only return keys starting with this string.

        Returns:
            Sorted list of matching keys.
        """

    async def save_state(self) -> dict[str, Any]:
        """Serialize backend metadata for snapshot/recovery."""
        return {}

    async def load_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore backend metadata from snapshot."""
