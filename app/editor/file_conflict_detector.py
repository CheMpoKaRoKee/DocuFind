"""Detect external file changes before saving."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.editor.text_file_loader import EditorSnapshot


class FileConflictDetector:
    def has_changed(self, snapshot: EditorSnapshot) -> bool:
        path = Path(snapshot.path)
        try:
            stat_result = path.stat()
        except OSError:
            return True

        if int(stat_result.st_size) != snapshot.size_bytes:
            return True
        modified_ns = getattr(stat_result, "st_mtime_ns", None)
        if modified_ns is not None and snapshot.modified_ns is not None and modified_ns != snapshot.modified_ns:
            return _content_hash(path) != snapshot.content_hash
        return _content_hash(path) != snapshot.content_hash


def _content_hash(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()
