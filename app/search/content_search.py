"""FTS-backed content search."""

from __future__ import annotations

import sqlite3

from app.models.content_match import ContentMatch
from app.models.search_query import SearchQuery
from app.search.fts_query_builder import FtsQueryBuilder
from app.search.filename_search import _document_filters
from app.search.occurrence_locator import OccurrenceLocator
from app.search.snippet_builder import SnippetBuilder


class ContentSearch:
    def __init__(
        self,
        *,
        fts_builder: FtsQueryBuilder | None = None,
        locator: OccurrenceLocator | None = None,
        snippet_builder: SnippetBuilder | None = None,
        max_matches: int = 2000,
    ) -> None:
        self.fts_builder = fts_builder or FtsQueryBuilder()
        self.locator = locator or OccurrenceLocator()
        self.snippet_builder = snippet_builder or SnippetBuilder()
        self.max_matches = max_matches

    def search(self, connection: sqlite3.Connection, query: SearchQuery) -> dict[int, list[ContentMatch]]:
        fts_query = self.fts_builder.build(query)
        if not fts_query:
            return {}

        where, params = _document_filters(query)
        rows = connection.execute(
            f"""
            SELECT d.id AS document_id, c.id AS chunk_id, c.text, c.char_start AS chunk_char_start
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE chunks_fts MATCH ?
              AND d.index_status = 'indexed' {where}
            LIMIT ?
            """,
            [fts_query, *params, self.max_matches],
        )

        results: dict[int, list[ContentMatch]] = {}
        for row in rows:
            document_id = int(row["document_id"])
            chunk_id = int(row["chunk_id"])
            chunk_offset = int(row["chunk_char_start"] or 0)
            for group in query.groups:
                terms = group.variants if group.is_phrase else group.variants
                for occurrence in self.locator.locate_exact(row["text"], terms, is_phrase=group.is_phrase):
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
                            match_type="exact",
                        )
                    )
        return results

