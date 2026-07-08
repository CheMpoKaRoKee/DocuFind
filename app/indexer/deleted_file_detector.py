"""Detect and mark indexed files that disappeared from disk."""

from __future__ import annotations

import sqlite3


class DeletedFileDetector:
    def find_deleted_document_ids(self, connection: sqlite3.Connection, folder_id: int, seen_paths: set[str]) -> list[int]:
        rows = connection.execute(
            """
            SELECT id, path
            FROM documents
            WHERE folder_id = ?
              AND index_status != 'deleted'
            """,
            (folder_id,),
        )
        return [int(row["id"]) for row in rows if str(row["path"]) not in seen_paths]

    def mark_deleted(self, connection: sqlite3.Connection, document_ids: list[int]) -> None:
        for document_id in document_ids:
            connection.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
            connection.execute("DELETE FROM documents_fts WHERE document_id = ?", (document_id,))
            connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            connection.execute("DELETE FROM document_terms WHERE document_id = ?", (document_id,))
            connection.execute("DELETE FROM document_lemmas WHERE document_id = ?", (document_id,))
            connection.execute("UPDATE documents SET index_status = 'deleted' WHERE id = ?", (document_id,))

