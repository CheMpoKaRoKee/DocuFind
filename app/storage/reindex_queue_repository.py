"""Repository for pending reindex tasks."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from app.utils.path_normalizer import normalize_path


class ReindexQueueRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def enqueue(self, path: str, reason: str, document_id: int | None = None, priority: int = 100) -> int:
        path_norm = normalize_path(path)
        existing = self.connection.execute(
            """
            SELECT id
            FROM reindex_queue
            WHERE path_norm = ?
              AND reason = ?
              AND status IN ('pending', 'processing')
            ORDER BY id
            LIMIT 1
            """,
            (path_norm, reason),
        ).fetchone()
        now = _now()
        if existing is not None:
            task_id = int(existing["id"])
            self.connection.execute(
                "UPDATE reindex_queue SET updated_at = ?, priority = MIN(priority, ?) WHERE id = ?",
                (now, priority, task_id),
            )
            return task_id
        cursor = self.connection.execute(
            """
            INSERT INTO reindex_queue(
                path, path_norm, document_id, reason, status, priority,
                attempts, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?, 0, ?, ?)
            """,
            (path, path_norm, document_id, reason, priority, now, now),
        )
        return int(cursor.lastrowid)

    def list_pending(self, limit: int = 100) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT *
                FROM reindex_queue
                WHERE status = 'pending'
                ORDER BY priority, created_at
                LIMIT ?
                """,
                (limit,),
            )
        )

    def mark_processing(self, task_id: int) -> None:
        now = _now()
        self.connection.execute(
            """
            UPDATE reindex_queue
            SET status = 'processing',
                attempts = attempts + 1,
                updated_at = ?,
                locked_at = ?
            WHERE id = ?
            """,
            (now, now, task_id),
        )

    def mark_done(self, task_id: int) -> None:
        self.connection.execute(
            "UPDATE reindex_queue SET status = 'done', updated_at = ?, locked_at = NULL WHERE id = ?",
            (_now(), task_id),
        )

    def mark_failed(self, task_id: int, error: str) -> None:
        self.connection.execute(
            """
            UPDATE reindex_queue
            SET status = 'failed',
                last_error = ?,
                updated_at = ?,
                locked_at = NULL
            WHERE id = ?
            """,
            (error, _now(), task_id),
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()
