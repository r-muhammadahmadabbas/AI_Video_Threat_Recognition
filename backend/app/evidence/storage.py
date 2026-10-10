"""Evidence storage abstraction (S4-4C).

Artifacts are addressed by relative keys, never by filesystem path, so a
local-filesystem store can later become object storage without touching the
worker or the API. The database records the key; anything that reads the bytes
back resolves the key through the store, which is what makes path traversal
on the serving side impossible.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import NamedTuple


class EvidenceStoreError(Exception):
    """Raised when a key cannot be stored or resolved safely."""


class EvidenceHandle(NamedTuple):
    """A stored artifact, addressed by key for later retrieval."""

    key: str
    uri: str


class EvidenceStore(ABC):
    """Contract for storing and resolving evidence artifacts."""

    @abstractmethod
    def put(self, key: str, source: Path | bytes, *, media_type: str) -> EvidenceHandle:
        """Store bytes or a file under ``key``; returns a handle."""

    @abstractmethod
    def resolve(self, key: str) -> str:
        """Return the absolute location of ``key``, verified inside the store.

        Raises :class:`EvidenceStoreError` for keys that would escape the
        store root (``..``, absolute paths, drive letters).
        """

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove ``key`` if it exists; missing keys are a no-op."""


class LocalEvidenceStore(EvidenceStore):
    """Filesystem-backed store confined to a root directory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def put(self, key: str, source: Path | bytes, *, media_type: str) -> EvidenceHandle:
        del media_type  # the local store has no per-type handling yet

        target = Path(self._safe_join(key))
        target.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(source, Path):
            shutil.copyfile(source, target)
        else:
            target.write_bytes(source)

        return EvidenceHandle(key=key, uri=str(target))

    def resolve(self, key: str) -> str:
        return self._safe_join(key)

    def delete(self, key: str) -> None:
        target = Path(self._safe_join(key))
        if target.exists():
            target.unlink()

    def _safe_join(self, key: str) -> str:
        """Join ``key`` onto the root, refusing anything that escapes it.

        ``Path.resolve()`` normalizes ``..`` and symlinks on every platform,
        so after resolution the candidate must still live under the root.
        """
        candidate = Path(key)
        if candidate.is_absolute():
            raise EvidenceStoreError(f"absolute keys are not allowed: {key!r}")

        resolved = (self._root / candidate).resolve()
        if self._root not in resolved.parents:
            raise EvidenceStoreError(f"key escapes the evidence root: {key!r}")

        return str(resolved)
