"""Lemma search over indexed chunks."""

from __future__ import annotations

import sqlite3

from app.models.content_match import ContentMatch
from app.models.search_query import SearchQuery
from app.search.filename_search import _document_filters
from app.search.occurrence_locator import OccurrenceLocator
from app.search.snippet_builder import SnippetBuilder


class LemmaSearch:
    def __init__(
        self,
        *,
        locator: OccurrenceLocator | None = None,
        snippet_builder: SnippetBuilder | None = None,
        max_matches: int = 2000,
    ) -> None:
        self.locator = locator or OccurrenceLocator()
        self.snippet_builder = snippet_builder or SnippetBuilder()
        self.max_matches = max_matches

    def search(self, connection: sqlite3.Connection, query: SearchQuery) -> dict[int, list[ContentMatch]]:
        lemmas = _query_lemmas(query)
        if not lemmas:
            return {}

        where, params = _document_filters(query)
        placeholders = ", ".join("?" for _ in lemmas)
        rows = connection.execute(
            f"""
            SELECT c.document_id, c.id AS chunk_id, c.text,
                   c.char_start AS chunk_char_start, c.line_start AS chunk_line_start,
                   c.column_start AS chunk_column_start
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.index_status = 'indexed' {where}
              AND c.document_id IN (
                  SELECT document_id
                  FROM document_lemmas
                  WHERE source = 'content'
                    AND lemma IN ({placeholders})
                  GROUP BY document_id
                  HAVING count(DISTINCT lemma) = ?
              )
            LIMIT ?
            """,
            [*params, *lemmas, len(lemmas), self.max_matches],
        )

        results: dict[int, list[ContentMatch]] = {}
        for row in rows:
            document_id = int(row["document_id"])
            chunk_id = int(row["chunk_id"])
            chunk_offset = int(row["chunk_char_start"] or 0)
            line_offset = int(row["chunk_line_start"] or 1) - 1
            column_offset = int(row["chunk_column_start"] or 1) - 1
            for occurrence in self.locator.locate_lemmas(
                row["text"], lemmas, line_number_offset=line_offset,
                first_line_column_offset=column_offset,
            ):
                results.setdefault(document_id, []).append(
                    ContentMatch(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        line_number=occurrence.line_number,
                        column_number=occurrence.column_number,
                        char_start=chunk_offset + occurrence.char_start,
                        char_end=chunk_offset + occurrence.char_end,
                        query_term=occurrence.query_term,
                        matched_text=occurrence.matched_text,
                        snippet=self.snippet_builder.build(row["text"], occurrence.char_start, occurrence.char_end),
                        match_type="lemma",
                    )
                )
        return results


def _query_lemmas(query: SearchQuery) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for group in query.groups:
        if group.is_phrase:
            continue
        for lemma in group.lemmas:
            if lemma not in seen:
                seen.add(lemma)
                result.append(lemma)
    return result
