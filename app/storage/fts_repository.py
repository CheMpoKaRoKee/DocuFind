"""Repository for SQLite FTS tables."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


class FtsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def replace_document(self, document_id: int, filename_norm: str, path_norm: str) -> None:
        self.connection.execute("DELETE FROM documents_fts WHERE document_id = ?", (document_id,))
        self.connection.execute(
            "INSERT INTO documents_fts(document_id, filename_norm, path_norm) VALUES (?, ?, ?)",
            (document_id, filename_norm, path_norm),
        )

    def replace_chunks(self, document_id: int, chunks: Iterable[tuple[int, str]]) -> None:
        self.connection.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
        self.connection.executemany(
            "INSERT INTO chunks_fts(chunk_id, document_id, text) VALUES (?, ?, ?)",
            ((chunk_id, document_id, text) for chunk_id, text in chunks),
        )

