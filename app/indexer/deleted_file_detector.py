"""Detect and mark indexed files that disappeared from disk."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
import unicodedata

from app.indexer.document_state_service import DocumentStateService


class DeletedFileDetector:
    def find_deleted_document_ids(
        self,
        connection: sqlite3.Connection,
        folder_id: int,
        seen_paths: set[str],
        *,
        protected_subtrees: Iterable[Path] = (),
    ) -> list[int]:
        protected = [_canonical_path(path) for path in protected_subtrees]
        rows = connection.execute(
            """
            SELECT id, path, path_norm
            FROM documents
            WHERE folder_id = ?
              AND index_status NOT IN ('deleted_retained', 'deleted_purged')
            """,
            (folder_id,),
        )
        return [
            int(row["id"])
            for row in rows
            if str(row["path"]) not in seen_paths
            and not any(_is_under(_canonical_path(str(row["path"])), prefix) for prefix in protected)
        ]

    def mark_deleted(self, connection: sqlite3.Connection, document_ids: list[int]) -> None:
        state_service = DocumentStateService(connection)
        for document_id in document_ids:
            state_service.mark_deleted_retained(document_id, reason="missing_on_scan")


def _is_under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


def _canonical_path(path: str | Path) -> str:
    return unicodedata.normalize("NFKC", str(path).replace("\\", "/")).casefold().rstrip("/")
