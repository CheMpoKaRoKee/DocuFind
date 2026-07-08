"""Repository for indexing run records."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


class IndexRunRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def start(self, folder_id: int | None) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO index_runs(folder_id, started_at, status)
            VALUES (?, ?, 'running')
            """,
            (folder_id, datetime.now(UTC).isoformat()),
        )
        return int(cursor.lastrowid)

    def finish(
        self,
        run_id: int,
        *,
        status: str,
        files_seen: int,
        files_indexed: int,
        files_skipped: int,
        files_failed: int,
    ) -> None:
        self.connection.execute(
            """
            UPDATE index_runs
            SET finished_at = ?,
                status = ?,
                files_seen = ?,
                files_indexed = ?,
                files_skipped = ?,
                files_failed = ?
            WHERE id = ?
            """,
            (
                datetime.now(UTC).isoformat(),
                status,
                files_seen,
                files_indexed,
                files_skipped,
                files_failed,
                run_id,
            ),
        )

