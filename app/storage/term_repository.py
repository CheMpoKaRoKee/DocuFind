"""Repository for aggregated indexed terms."""

from __future__ import annotations

import sqlite3


class TermRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def rebuild(self) -> None:
        self.connection.execute("DELETE FROM indexed_terms")
        self.connection.execute(
            """
            INSERT INTO indexed_terms(term, normalized_term, source, first_char, length, document_count, occurrence_count)
            SELECT
                normalized_term,
                normalized_term,
                source,
                substr(normalized_term, 1, 1),
                length(normalized_term),
                count(DISTINCT document_id),
                sum(occurrence_count)
            FROM document_terms
            GROUP BY normalized_term, source
            """
        )

