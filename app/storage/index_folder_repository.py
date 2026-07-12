"""Repository for indexed folder records."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from collections.abc import Iterable


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

    def sync_enabled(self, paths: Iterable[tuple[str, str]]) -> None:
        """Make enabled folder state exactly match settings without deleting index data."""
        desired = list(paths)
        self.connection.execute("UPDATE index_folders SET enabled = 0 WHERE enabled = 1")
        for path, path_norm in desired:
            row = self.connection.execute(
                "SELECT id FROM index_folders WHERE path_norm = ? ORDER BY id LIMIT 1",
                (path_norm,),
            ).fetchone()
            if row is None:
                self.add(path, path_norm, enabled=True)
            else:
                self.connection.execute(
                    "UPDATE index_folders SET path = ?, path_norm = ?, enabled = 1 WHERE id = ?",
                    (path, path_norm, int(row["id"])),
                )
