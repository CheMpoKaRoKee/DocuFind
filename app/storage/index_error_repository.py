"""Repository for indexing errors."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


class IndexErrorRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, run_id: int | None, path: str, error_type: str, error_message: str | None = None) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO index_errors(run_id, path, error_type, error_message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, path, error_type, error_message, datetime.now(UTC).isoformat()),
        )
        return int(cursor.lastrowid)
