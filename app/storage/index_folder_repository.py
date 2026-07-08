"""Repository for indexed folder records."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


class IndexFolderRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, path: str, path_norm: str, enabled: bool = True) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO index_folders(path, path_norm, enabled, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                path_norm=excluded.path_norm,
                enabled=excluded.enabled
            """,
            (path, path_norm, int(enabled), datetime.now(UTC).isoformat()),
        )
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        row = self.connection.execute("SELECT id FROM index_folders WHERE path = ?", (path,)).fetchone()
        return int(row["id"])

    def list_enabled(self) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM index_folders WHERE enabled = 1 ORDER BY path_norm"))

