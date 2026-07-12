"""Controlled cleanup for retained payload of missing documents."""

from __future__ import annotations

import sqlite3

from app.indexer.document_state_service import DocumentStateService


class DeletedPayloadCleanup:
    def cleanup_document(self, connection: sqlite3.Connection, document_id: int) -> None:
        connection.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM documents_fts WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM document_terms WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM document_lemmas WHERE document_id = ?", (document_id,))
        DocumentStateService(connection).mark_deleted_purged(document_id)
