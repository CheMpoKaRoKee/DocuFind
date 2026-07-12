"""Document state transitions for index lifecycle."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


class DocumentStateService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def mark_deleted_retained(self, document_id: int, *, reason: str) -> None:
        now = _now()
        self.connection.execute(
            """
            UPDATE documents
            SET index_status = 'deleted_retained',
                last_missing_at = ?,
                payload_retained = 1,
                state_reason = ?
            WHERE id = ?
            """,
            (now, reason, document_id),
        )

    def mark_deleted_purged(self, document_id: int, *, reason: str = "cleanup") -> None:
        self.connection.execute(
            """
            UPDATE documents
            SET index_status = 'deleted_purged',
                payload_retained = 0,
                state_reason = ?
            WHERE id = ?
            """,
            (reason, document_id),
        )

    def mark_queued_reindex(self, document_id: int, *, reason: str) -> None:
        now = _now()
        self.connection.execute(
            """
            UPDATE documents
            SET index_status = 'queued_reindex',
                stale_detected_at = ?,
                state_reason = ?
            WHERE id = ?
            """,
            (now, reason, document_id),
        )

    def mark_stale(self, document_id: int, *, reason: str) -> None:
        now = _now()
        self.connection.execute(
            """
            UPDATE documents
            SET index_status = 'stale',
                stale_detected_at = ?,
                state_reason = ?
            WHERE id = ?
            """,
            (now, reason, document_id),
        )

    def restore_indexed(self, document_id: int, *, reason: str) -> None:
        now = _now()
        self.connection.execute(
            """
            UPDATE documents
            SET index_status = 'indexed',
                last_seen_at = ?,
                last_verified_at = ?,
                last_missing_at = NULL,
                payload_retained = 1,
                state_reason = ?,
                stale_detected_at = NULL
            WHERE id = ?
            """,
            (now, now, reason, document_id),
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()
