"""Repository for indexed text chunks."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping


class ChunkRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def replace_for_document(self, document_id: int, chunks: Iterable[Mapping[str, object]]) -> list[int]:
        self.connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        chunk_ids: list[int] = []
        for chunk in chunks:
            cursor = self.connection.execute(
                """
                INSERT INTO chunks(document_id, chunk_index, text, line_start, line_end, char_start, char_end)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    chunk["chunk_index"],
                    chunk["text"],
                    chunk.get("line_start"),
                    chunk.get("line_end"),
                    chunk.get("char_start"),
                    chunk.get("char_end"),
                ),
            )
            chunk_ids.append(int(cursor.lastrowid))
        return chunk_ids

    def list_by_document(self, document_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
                (document_id,),
            )
        )

