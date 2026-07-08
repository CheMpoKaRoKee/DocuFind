"""Repository for application settings."""

from __future__ import annotations

import sqlite3


class SettingsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return default if row is None else str(row["value"])

    def set(self, key: str, value: str) -> None:
        self.connection.execute(
            """
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )

    def all(self) -> dict[str, str]:
        rows = self.connection.execute("SELECT key, value FROM settings ORDER BY key")
        return {str(row["key"]): str(row["value"]) for row in rows}

