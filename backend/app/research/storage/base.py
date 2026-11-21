from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Abstract protocol for raw document file persistence."""

    def save(self, data: bytes, storage_key: str) -> int:
        """Write bytes to storage key and return byte count."""
        ...

    def read(self, storage_key: str) -> bytes:
        """Read and return bytes for storage key."""
        ...

    def delete(self, storage_key: str) -> bool:
        """
        Delete file for storage key idempotently.
        Returns True if file was deleted or was already absent.
        """
        ...

    def exists(self, storage_key: str) -> bool:
        """Check whether file exists for storage key."""
        ...

    def get_absolute_path(self, storage_key: str) -> Path:
        """Return safe resolved absolute path for storage key."""
        ...
