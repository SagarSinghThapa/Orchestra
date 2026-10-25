from pathlib import Path
import pytest

from app.research.storage.local import LocalStorageBackend


def test_storage_save_read_exists_delete(tmp_path: Path):
    """Verifies basic write, read, existence, and deletion operations."""
    backend = LocalStorageBackend(root_dir=tmp_path)
    data = b"Hello, Orchestra Knowledge Pipeline!"
    storage_key = "projects/1/test_doc.txt"

    # Save
    bytes_written = backend.save(data, storage_key)
    assert bytes_written == len(data)

    # Exists
    assert backend.exists(storage_key) is True

    # Read
    read_data = backend.read(storage_key)
    assert read_data == data

    # Absolute path
    abs_path = backend.get_absolute_path(storage_key)
    assert abs_path.is_file()
    assert abs_path.is_relative_to(tmp_path.resolve())

    # Delete
    deleted = backend.delete(storage_key)
    assert deleted is True
    assert backend.exists(storage_key) is False


def test_storage_idempotent_delete_on_missing_file(tmp_path: Path):
    """Verifies that deleting a non-existent file returns True without raising FileNotFoundError."""
    backend = LocalStorageBackend(root_dir=tmp_path)
    storage_key = "projects/1/never_existed.txt"

    assert backend.exists(storage_key) is False
    # Deleting non-existent file must succeed idempotently
    result = backend.delete(storage_key)
    assert result is True


def test_storage_read_missing_file_raises_error(tmp_path: Path):
    """Verifies that reading a non-existent file raises FileNotFoundError."""
    backend = LocalStorageBackend(root_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        backend.read("projects/1/nonexistent.pdf")


def test_storage_path_traversal_parent_directory_rejected(tmp_path: Path):
    """Verifies path traversal via '..' is strictly blocked."""
    backend = LocalStorageBackend(root_dir=tmp_path)
    traversal_keys = [
        "../outside.txt",
        "../../outside.txt",
        "projects/../../outside.txt",
        "projects/1/../../../etc/passwd",
    ]

    for key in traversal_keys:
        with pytest.raises(ValueError, match="Path traversal detected"):
            backend.save(b"malicious data", key)

        with pytest.raises(ValueError, match="Path traversal detected"):
            backend._resolve_key(key)


def test_storage_path_traversal_null_byte_rejected(tmp_path: Path):
    """Verifies path traversal or truncation via null bytes is strictly blocked."""
    backend = LocalStorageBackend(root_dir=tmp_path)
    null_byte_key = "projects/1/file.pdf\0.txt"

    with pytest.raises(ValueError, match="null byte"):
        backend.save(b"data", null_byte_key)

    with pytest.raises(ValueError, match="null byte"):
        backend._resolve_key(null_byte_key)


def test_storage_absolute_path_escape_rejected(tmp_path: Path):
    """Verifies absolute paths attempting to write outside root_dir are blocked."""
    backend = LocalStorageBackend(root_dir=tmp_path)
    # Attempting to resolve root directly
    with pytest.raises(ValueError):
        backend._resolve_key("/")

    with pytest.raises(ValueError):
        backend._resolve_key("")
