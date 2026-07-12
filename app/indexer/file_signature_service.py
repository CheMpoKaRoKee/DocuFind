"""File signature collection for incremental indexing and freshness checks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.utils.path_rules import FileAttributes, read_file_attributes


@dataclass(frozen=True)
class FileSignature:
    exists: bool
    is_file: bool
    size_bytes: int | None = None
    modified_at: str | None = None
    modified_ns: int | None = None
    content_hash: str | None = None
    attributes: FileAttributes | None = None
    error: str | None = None


class FileSignatureService:
    def get_signature(self, path: Path, *, include_hash: bool = False) -> FileSignature:
        path = Path(path)
        if not path.exists():
            return FileSignature(exists=False, is_file=False)
        if not path.is_file():
            return FileSignature(exists=True, is_file=False)
        try:
            stat_result = path.stat()
            content_hash = _content_hash(path) if include_hash else None
            return FileSignature(
                exists=True,
                is_file=True,
                size_bytes=int(stat_result.st_size),
                modified_at=datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat(),
                modified_ns=getattr(stat_result, "st_mtime_ns", None),
                content_hash=content_hash,
                attributes=read_file_attributes(path),
            )
        except OSError as exc:
            return FileSignature(exists=True, is_file=True, error=str(exc))


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
