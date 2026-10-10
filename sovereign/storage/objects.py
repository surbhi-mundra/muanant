"""Object store for document blobs.

Abstraction over filesystem (dev) and S3-compatible storage (prod).
Storage keys are opaque UUIDs — NEVER user-supplied filenames.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import IO, Protocol, runtime_checkable

from sovereign.core.config import Settings
from sovereign.core.errors import NotFoundError, StorageError


@runtime_checkable
class ObjectStore(Protocol):
    def put(self, project_id: str, key: str, data: bytes) -> str: ...
    def put_stream(self, project_id: str, key: str, stream: IO[bytes]) -> str: ...
    def get(self, project_id: str, key: str) -> bytes: ...
    def delete(self, project_id: str, key: str) -> None: ...
    def exists(self, project_id: str, key: str) -> bool: ...


class FilesystemObjectStore:
    """Filesystem-backed object store with project-scoped paths."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        if not project_id:
            msg = "project_id is required for object store paths"
            raise StorageError(msg)
        prefix = project_id[:2]
        d = self._root / prefix / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _resolve(self, project_id: str, key: str) -> Path:
        if not key:
            msg = "key is required"
            raise StorageError(msg)
        if "/" in key or "\\" in key or ".." in key:
            msg = f"invalid key (contains path separators): {key!r}"
            raise StorageError(msg)
        return self._project_dir(project_id) / key

    def put(self, project_id: str, key: str, data: bytes) -> str:
        path = self._resolve(project_id, key)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_bytes(data)
            tmp.replace(path)
        except OSError as e:
            msg = f"failed to write object {key}: {e}"
            raise StorageError(msg) from e
        return key

    def put_stream(self, project_id: str, key: str, stream: IO[bytes]) -> str:
        path = self._resolve(project_id, key)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with tmp.open("wb") as f:
                shutil.copyfileobj(stream, f, length=1024 * 1024)
            tmp.replace(path)
        except OSError as e:
            msg = f"failed to write object {key}: {e}"
            raise StorageError(msg) from e
        return key

    def get(self, project_id: str, key: str) -> bytes:
        path = self._resolve(project_id, key)
        if not path.exists():
            msg = f"object not found: project={project_id} key={key}"
            raise NotFoundError(msg)
        return path.read_bytes()

    def delete(self, project_id: str, key: str) -> None:
        path = self._resolve(project_id, key)
        path.unlink(missing_ok=True)

    def exists(self, project_id: str, key: str) -> bool:
        path = self._resolve(project_id, key)
        return path.exists()


_store: ObjectStore | None = None


def new_storage_key() -> str:
    return uuid.uuid4().hex


def get_object_store(settings: Settings | None = None) -> ObjectStore:
    global _store  # noqa: PLW0603
    if _store is None:
        if settings is None:
            from sovereign.core.config import get_settings

            settings = get_settings()
        if settings.object_store_type == "fs":
            _store = FilesystemObjectStore(settings.object_store_fs_root)
        else:
            msg = f"unsupported object_store_type: {settings.object_store_type}"
            raise StorageError(msg)
    return _store


def reset_object_store() -> None:
    global _store  # noqa: PLW0603
    _store = None
