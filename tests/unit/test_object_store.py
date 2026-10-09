"""Tests for sovereign.storage.objects — FilesystemObjectStore."""

from __future__ import annotations

import pytest

from sovereign.core.errors import NotFoundError, StorageError
from sovereign.storage.objects import (
    FilesystemObjectStore,
    new_storage_key,
)


@pytest.fixture
def store(tmp_path: pytest.TempPathFactory) -> FilesystemObjectStore:
    return FilesystemObjectStore(tmp_path / "objects")


def test_put_and_get(store: FilesystemObjectStore) -> None:
    """Stored data should be retrievable."""
    key = new_storage_key()
    data = b"test document content"
    store.put("proj_1", key, data)
    assert store.get("proj_1", key) == data


def test_exists(store: FilesystemObjectStore) -> None:
    """exists() should reflect put/delete."""
    key = new_storage_key()
    assert store.exists("proj_1", key) is False
    store.put("proj_1", key, b"data")
    assert store.exists("proj_1", key) is True


def test_delete_is_idempotent(store: FilesystemObjectStore) -> None:
    """Deleting a missing key should not raise."""
    key = new_storage_key()
    store.put("proj_1", key, b"data")
    store.delete("proj_1", key)
    store.delete("proj_1", key)  # no error
    assert store.exists("proj_1", key) is False


def test_get_missing_raises_not_found(store: FilesystemObjectStore) -> None:
    """Getting a missing key should raise NotFoundError."""
    key = new_storage_key()
    with pytest.raises(NotFoundError):
        store.get("proj_1", key)


def test_project_isolation(store: FilesystemObjectStore) -> None:
    """A key stored under project A should not be readable from project B."""
    key = new_storage_key()
    store.put("proj_a", key, b"secret")
    with pytest.raises(NotFoundError):
        store.get("proj_b", key)


def test_path_traversal_rejected(store: FilesystemObjectStore) -> None:
    """Keys with path separators must be rejected."""
    with pytest.raises(StorageError):
        store.put("proj_1", "../../../etc/passwd", b"x")
    with pytest.raises(StorageError):
        store.put("proj_1", "foo/bar", b"x")
    with pytest.raises(StorageError):
        store.put("proj_1", "..", b"x")


def test_empty_project_rejected(store: FilesystemObjectStore) -> None:
    """Empty project_id must be rejected."""
    with pytest.raises(StorageError):
        store.put("", new_storage_key(), b"x")


def test_empty_key_rejected(store: FilesystemObjectStore) -> None:
    """Empty key must be rejected."""
    with pytest.raises(StorageError):
        store.put("proj_1", "", b"x")


def test_put_stream(store: FilesystemObjectStore) -> None:
    """put_stream should work with file-like objects."""
    import io

    key = new_storage_key()
    stream = io.BytesIO(b"streamed content")
    store.put_stream("proj_1", key, stream)
    assert store.get("proj_1", key) == b"streamed content"


def test_overwrite(store: FilesystemObjectStore) -> None:
    """Putting with the same key should overwrite."""
    key = new_storage_key()
    store.put("proj_1", key, b"original")
    store.put("proj_1", key, b"replaced")
    assert store.get("proj_1", key) == b"replaced"


def test_new_storage_key_is_unique() -> None:
    """Storage keys should be unique."""
    keys = {new_storage_key() for _ in range(1000)}
    assert len(keys) == 1000


def test_new_storage_key_is_hex() -> None:
    """Storage keys should be hex strings (UUID4 hex)."""
    key = new_storage_key()
    assert len(key) == 32
    int(key, 16)  # should not raise — it's valid hex
