"""Repository for document metadata."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime

from app.indexer.file_signature_service import FileSignature

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
    "last_verified_at",
    "last_missing_at",
    "payload_retained",
    "state_reason",
    "stale_detected_at",
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
        now = _now()
        self.connection.execute(
            """
            UPDATE documents
            SET index_status = 'deleted_retained',
                last_missing_at = ?,
                payload_retained = 1,
                state_reason = 'missing_on_scan'
            WHERE id = ?
            """,
            (now, document_id),
        )

    def touch_verified(self, document_id: int) -> None:
        now = _now()
        self.connection.execute(
            """
            UPDATE documents
            SET last_seen_at = ?,
                last_verified_at = ?,
                state_reason = NULL
            WHERE id = ?
            """,
            (now, now, document_id),
        )

    def update_metadata_from_signature(
        self,
        document_id: int,
        signature: FileSignature,
        *,
        status: str | None = None,
    ) -> None:
        now = _now()
        status_sql = ", index_status = ?" if status is not None else ""
        params: list[object] = [
            signature.size_bytes,
            signature.modified_at,
            signature.modified_ns,
            now,
            now,
        ]
        if status is not None:
            params.append(status)
        params.append(document_id)
        self.connection.execute(
            f"""
            UPDATE documents
            SET size_bytes = ?,
                modified_at = ?,
                modified_ns = ?,
                last_seen_at = ?,
                last_verified_at = ?,
                stale_detected_at = NULL,
                state_reason = NULL
                {status_sql}
            WHERE id = ?
            """,
            tuple(params),
        )

    def list_active_by_folder(self, folder_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT *
                FROM documents
                WHERE folder_id = ?
                  AND index_status NOT IN ('deleted_retained', 'deleted_purged')
                """,
                (folder_id,),
            )
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()


