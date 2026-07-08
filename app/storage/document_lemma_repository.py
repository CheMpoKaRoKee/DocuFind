"""Repository for per-document lemmas."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


class DocumentLemmaRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def replace_for_document(self, document_id: int, lemmas: Iterable[tuple[str, str, int]]) -> None:
        self.connection.execute("DELETE FROM document_lemmas WHERE document_id = ?", (document_id,))
        self.connection.executemany(
            """
            INSERT INTO document_lemmas(document_id, lemma, source, occurrence_count)
            VALUES (?, ?, ?, ?)
            """,
            ((document_id, lemma, source, count) for lemma, source, count in lemmas),
        )

