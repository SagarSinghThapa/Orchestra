import logging
from pathlib import Path

from app.research.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    """
    Filesystem-backed implementation of StorageBackend with strict path traversal defenses
    and idempotent deletion semantics.
    """

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_key(self, storage_key: str) -> Path:
        """
        Resolves storage_key relative to root_dir, strictly rejecting path traversal,
        null bytes, and escapes outside canonical root.
        """
        if not storage_key or not isinstance(storage_key, str):
            raise ValueError("Storage key must be a non-empty string")

        if "\0" in storage_key:
            raise ValueError("Path traversal detected: null byte in storage key")

        # Normalize key and resolve relative to root_dir
        # Strip leading slashes to prevent root escapes
        clean_key = storage_key.strip().lstrip("/\\")
        candidate_path = (self.root_dir / clean_key).resolve()

        try:
            if not candidate_path.is_relative_to(self.root_dir) or candidate_path == self.root_dir:
                raise ValueError("Path traversal detected: resolved path escapes storage root")
        except AttributeError:
            # Fallback for Python < 3.9 if ever needed
            if not str(candidate_path).startswith(str(self.root_dir)):
                raise ValueError("Path traversal detected: resolved path escapes storage root")

        return candidate_path

    def save(self, data: bytes, storage_key: str) -> int:
        """Write file bytes and return byte count."""
        resolved = self._resolve_key(storage_key)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(data)
        return len(data)

    def read(self, storage_key: str) -> bytes:
        """Read and return file bytes. Raises FileNotFoundError if absent."""
        resolved = self._resolve_key(storage_key)
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found for storage key: {storage_key}")
        return resolved.read_bytes()

    def delete(self, storage_key: str) -> bool:
        """
        Deletes physical file idempotently.
        If file is missing (FileNotFoundError), logs warning and returns True.
        """
        resolved = self._resolve_key(storage_key)
        try:
            resolved.unlink()
            return True
        except FileNotFoundError:
            logger.warning("Attempted to delete non-existent storage file: %s", storage_key)
            return True

    def exists(self, storage_key: str) -> bool:
        """Check whether physical file exists on disk."""
        resolved = self._resolve_key(storage_key)
        return resolved.is_file()

    def get_absolute_path(self, storage_key: str) -> Path:
        """Return safe resolved path on filesystem."""
        return self._resolve_key(storage_key)
