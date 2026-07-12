"""Fuzzy search over indexed terms and lemmas."""

from __future__ import annotations

import difflib
import sqlite3
from dataclasses import dataclass

from app.models.content_match import ContentMatch
from app.models.file_match import FileMatch
from app.models.search_query import SearchQuery
from app.search.filename_search import _document_filters
from app.search.occurrence_locator import OccurrenceLocator
from app.search.snippet_builder import SnippetBuilder


@dataclass(frozen=True)
class FuzzyCandidate:
    value: str
    source: str
    similarity: float


class FuzzyScorer:
    def __init__(self) -> None:
        self._rapid_ratio = _load_rapid_ratio()

    def ratio(self, left: str, right: str) -> float:
        if self._rapid_ratio is not None:
            return float(self._rapid_ratio(left, right))
        return difflib.SequenceMatcher(None, left, right).ratio() * 100


class FuzzySearch:
    def __init__(
        self,
        *,
        scorer: FuzzyScorer | None = None,
        locator: OccurrenceLocator | None = None,
        snippet_builder: SnippetBuilder | None = None,
        filename_threshold: float = 78,
        content_threshold: float = 88,
        max_variants_per_term: int = 5,
        max_candidates_before_scoring: int = 500,
    ) -> None:
        self.scorer = scorer or FuzzyScorer()
        self.locator = locator or OccurrenceLocator()
        self.snippet_builder = snippet_builder or SnippetBuilder()
        self.filename_threshold = filename_threshold
        self.content_threshold = content_threshold
        self.max_variants_per_term = max_variants_per_term
        self.max_candidates_before_scoring = max_candidates_before_scoring

    def search(
        self,
        connection: sqlite3.Connection,
        query: SearchQuery,
    ) -> tuple[dict[int, list[FileMatch]], dict[int, list[ContentMatch]]]:
        file_results: dict[int, list[FileMatch]] = {}
        content_results: dict[int, list[ContentMatch]] = {}
        for query_term in _query_terms(query):
            for source in ("filename", "path", "content"):
                threshold = self.content_threshold if source == "content" else self.filename_threshold
                candidates = self._find_candidates(connection, query_term, source, threshold)
                for candidate in candidates:
                    if source in {"filename", "path"}:
                        self._add_file_matches(connection, query, query_term, candidate, file_results)
                    else:
                        self._add_content_matches(connection, query, query_term, candidate, content_results)
        return file_results, content_results

    def _find_candidates(
        self,
        connection: sqlite3.Connection,
        query_term: str,
        source: str,
        threshold: float,
    ) -> list[FuzzyCandidate]:
        if not query_term:
            return []
        first_char = query_term[0]
        min_length = max(1, len(query_term) - 2)
        max_length = len(query_term) + 2
        rows = connection.execute(
            """
            SELECT normalized_term AS value, source
            FROM indexed_terms
            WHERE source = ?
              AND first_char = ?
              AND length BETWEEN ? AND ?
            UNION
            SELECT lemma AS value, source
            FROM indexed_lemmas
            WHERE source = ?
              AND first_char = ?
              AND length BETWEEN ? AND ?
            LIMIT ?
            """,
            (
                source,
                first_char,
                min_length,
                max_length,
                source,
                first_char,
                min_length,
                max_length,
                self.max_candidates_before_scoring,
            ),
        )
        scored = [
            FuzzyCandidate(str(row["value"]), source, self.scorer.ratio(query_term, str(row["value"])))
            for row in rows
            if str(row["value"]) != query_term
        ]
        scored = [candidate for candidate in scored if candidate.similarity >= threshold]
        scored.sort(key=lambda candidate: (-candidate.similarity, candidate.value))
        return scored[: self.max_variants_per_term]

    def _add_file_matches(
        self,
        connection: sqlite3.Connection,
        query: SearchQuery,
        query_term: str,
        candidate: FuzzyCandidate,
        results: dict[int, list[FileMatch]],
    ) -> None:
        where, params = _document_filters(query)
        field_norm = "filename_norm" if candidate.source == "filename" else "path_norm"
        field = "filename" if candidate.source == "filename" else "path"
        rows = connection.execute(
            f"""
            SELECT id, {field} AS matched_text
            FROM documents
            WHERE index_status = 'indexed'
              AND {field_norm} LIKE ? {where}
            """,
            [f"%{candidate.value}%", *params],
        )
        for row in rows:
            document_id = int(row["id"])
            results.setdefault(document_id, []).append(
                FileMatch(
                    document_id=document_id,
                    match_field=field,
                    query_term=query_term,
                    matched_text=str(row["matched_text"]),
                    match_type="fuzzy",
                    similarity=candidate.similarity,
                )
            )

    def _add_content_matches(
        self,
        connection: sqlite3.Connection,
        query: SearchQuery,
        query_term: str,
        candidate: FuzzyCandidate,
        results: dict[int, list[ContentMatch]],
    ) -> None:
        where, params = _document_filters(query)
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
                  FROM document_terms
                  WHERE source = 'content'
                    AND normalized_term = ?
                  UNION
                  SELECT document_id
                  FROM document_lemmas
                  WHERE source = 'content'
                    AND lemma = ?
              )
            """,
            [*params, candidate.value, candidate.value],
        )
        for row in rows:
            document_id = int(row["document_id"])
            chunk_id = int(row["chunk_id"])
            chunk_offset = int(row["chunk_char_start"] or 0)
            line_offset = int(row["chunk_line_start"] or 1) - 1
            column_offset = int(row["chunk_column_start"] or 1) - 1
            occurrences = [
                *self.locator.locate_exact(
                    row["text"], [candidate.value], line_number_offset=line_offset,
                    first_line_column_offset=column_offset,
                ),
                *self.locator.locate_lemmas(
                    row["text"], [candidate.value], line_number_offset=line_offset,
                    first_line_column_offset=column_offset,
                ),
            ]
            for occurrence in occurrences:
                results.setdefault(document_id, []).append(
                    ContentMatch(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        line_number=occurrence.line_number,
                        column_number=occurrence.column_number,
                        char_start=chunk_offset + occurrence.char_start,
                        char_end=chunk_offset + occurrence.char_end,
                        query_term=query_term,
                        matched_text=occurrence.matched_text,
                        snippet=self.snippet_builder.build(row["text"], occurrence.char_start, occurrence.char_end),
                        match_type="fuzzy",
                        similarity=candidate.similarity,
                    )
                )


def _query_terms(query: SearchQuery) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for group in query.groups:
        for variant in group.variants:
            for token in variant.split():
                if token not in seen:
                    seen.add(token)
                    terms.append(token)
    return terms


def _load_rapid_ratio():
    try:
        from rapidfuzz import fuzz  # type: ignore

        return fuzz.ratio
    except Exception:
        return None
