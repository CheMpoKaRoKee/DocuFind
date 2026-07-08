"""Repository for aggregated indexed lemmas."""

from __future__ import annotations

import sqlite3


class LemmaRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def rebuild(self) -> None:
        self.connection.execute("DELETE FROM indexed_lemmas")
        self.connection.execute(
            """
            INSERT INTO indexed_lemmas(lemma, source, first_char, length, document_count, occurrence_count)
            SELECT
                lemma,
                source,
                substr(lemma, 1, 1),
                length(lemma),
                count(DISTINCT document_id),
                sum(occurrence_count)
            FROM document_lemmas
            GROUP BY lemma, source
            """
        )

