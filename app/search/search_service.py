"""Search orchestration over the local index."""

from __future__ import annotations

import sqlite3

from app.models.document import Document
from app.models.search_result import SearchResult
from app.search.content_search import ContentSearch
from app.search.filename_search import FilenameSearch
from app.search.fuzzy_search import FuzzySearch
from app.search.lemma_search import LemmaSearch
from app.search.match_deduplicator import MatchDeduplicator
from app.search.query_parser import QueryParser
from app.search.ranking import Ranking


class SearchService:
    def __init__(
        self,
        *,
        query_parser: QueryParser | None = None,
        filename_search: FilenameSearch | None = None,
        content_search: ContentSearch | None = None,
        lemma_search: LemmaSearch | None = None,
        fuzzy_search: FuzzySearch | None = None,
        deduplicator: MatchDeduplicator | None = None,
        ranking: Ranking | None = None,
        enable_fuzzy: bool = True,
        max_documents: int = 500,
        max_matches_per_document: int = 100,
    ) -> None:
        self.query_parser = query_parser or QueryParser()
        self.filename_search = filename_search or FilenameSearch()
        self.content_search = content_search or ContentSearch()
        self.lemma_search = lemma_search or LemmaSearch()
        self.fuzzy_search = fuzzy_search or FuzzySearch()
        self.deduplicator = deduplicator or MatchDeduplicator()
        self.ranking = ranking or Ranking()
        self.enable_fuzzy = enable_fuzzy
        self.max_documents = max_documents
        self.max_matches_per_document = max_matches_per_document

    def search(self, connection: sqlite3.Connection, raw_query: str) -> list[SearchResult]:
        query = self.query_parser.parse(raw_query)
        if not query.has_terms:
            return []

        file_matches = self.filename_search.search(connection, query)
        content_matches = self.content_search.search(connection, query)
        lemma_matches = self.lemma_search.search(connection, query)
        if self.enable_fuzzy:
            fuzzy_file_matches, fuzzy_content_matches = self.fuzzy_search.search(connection, query)
            _merge_matches(file_matches, fuzzy_file_matches)
            _merge_matches(content_matches, fuzzy_content_matches)

        document_ids = set(file_matches) | set(content_matches) | set(lemma_matches)
        if not document_ids:
            return []

        documents = _load_documents(connection, document_ids)
        results: list[SearchResult] = []
        for document_id in document_ids:
            combined_content = [
                *content_matches.get(document_id, []),
                *lemma_matches.get(document_id, []),
            ]
            deduped = self.deduplicator.deduplicate_content(combined_content)
            total_content_matches = len(deduped)
            limited_content = deduped[: self.max_matches_per_document]
            document = documents.get(document_id)
            if document is None:
                continue
            results.append(
                SearchResult(
                    document=document,
                    file_matches=file_matches.get(document_id, []),
                    content_matches=limited_content,
                    total_content_matches=total_content_matches,
                    has_more_content_matches=total_content_matches > len(limited_content),
                )
            )

        return self.ranking.sort(results)[: self.max_documents]


def _merge_matches(target: dict[int, list], source: dict[int, list]) -> None:
    for document_id, matches in source.items():
        target.setdefault(document_id, []).extend(matches)


def _load_documents(connection: sqlite3.Connection, document_ids: set[int]) -> dict[int, Document]:
    placeholders = ", ".join("?" for _ in document_ids)
    rows = connection.execute(
        f"""
        SELECT id, path, filename, extension, size_bytes, modified_at
        FROM documents
        WHERE id IN ({placeholders})
        """,
        list(document_ids),
    )
    return {
        int(row["id"]): Document(
            id=int(row["id"]),
            path=str(row["path"]),
            filename=str(row["filename"]),
            extension=row["extension"],
            size_bytes=int(row["size_bytes"]),
            modified_at=str(row["modified_at"]),
        )
        for row in rows
    }
