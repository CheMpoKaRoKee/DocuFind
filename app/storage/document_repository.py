"""Repository for document metadata."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

DOCUMENT_COLUMNS = (
    "folder_id",
    "path",
    "path_norm",
    "filename",
    "filename_norm",
    "extension",
    "extension_norm",
    "size_bytes",
    "modified_at",
    "modified_ns",
    "indexed_at",
    "last_seen_at",
    "content_hash",
    "encoding",
    "line_ending",
    "is_hidden",
    "is_system",
    "is_readonly",
    "index_status",
    "error_message",
)


class DocumentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert(self, data: Mapping[str, object]) -> int:
        values = {column: data.get(column) for column in DOCUMENT_COLUMNS}
        placeholders = ", ".join("?" for _ in DOCUMENT_COLUMNS)
        updates = ", ".join(f"{column}=excluded.{column}" for column in DOCUMENT_COLUMNS if column != "path")
        self.connection.execute(
            f"""
            INSERT INTO documents({", ".join(DOCUMENT_COLUMNS)})
            VALUES ({placeholders})
            ON CONFLICT(path) DO UPDATE SET {updates}
            """,
            tuple(values[column] for column in DOCUMENT_COLUMNS),
        )
        row = self.get_by_path(str(values["path"]))
        if row is None:
            raise RuntimeError("Document upsert did not return or find a document id")
        return int(row["id"])

    def get_by_path(self, path: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM documents WHERE path = ?", (path,)).fetchone()

    def get(self, document_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()

    def mark_deleted(self, document_id: int) -> None:
        self.connection.execute("UPDATE documents SET index_status = 'deleted' WHERE id = ?", (document_id,))


