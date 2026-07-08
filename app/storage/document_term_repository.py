"""Repository for per-document normalized terms."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


class DocumentTermRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def replace_for_document(self, document_id: int, terms: Iterable[tuple[str, str, int]]) -> None:
        self.connection.execute("DELETE FROM document_terms WHERE document_id = ?", (document_id,))
        self.connection.executemany(
            """
            INSERT INTO document_terms(document_id, normalized_term, source, occurrence_count)
            VALUES (?, ?, ?, ?)
            """,
            ((document_id, term, source, count) for term, source, count in terms),
        )

