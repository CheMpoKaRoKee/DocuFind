"""Search orchestration over the local index."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.models.document import Document
from app.models.query_term_group import QueryTermGroup
from app.models.search_result import SearchResult
from app.search.content_search import ContentSearch
from app.search.filename_search import FilenameSearch
from app.search.freshness_guard import FreshnessGuard
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
        freshness_guard: FreshnessGuard | None = None,
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
        self.freshness_guard = freshness_guard or FreshnessGuard()
        self.deduplicator = deduplicator or MatchDeduplicator()
        self.ranking = ranking or Ranking()
        self.enable_fuzzy = enable_fuzzy
        self.max_documents = max_documents
        self.max_matches_per_document = max_matches_per_document

    def search(
        self,
        connection: sqlite3.Connection,
        raw_query: str,
        *,
        cancel_checker: Callable[[], bool] | None = None,
    ) -> list[SearchResult]:
        if _cancelled(cancel_checker):
            return []
        query = self.query_parser.parse(raw_query)
        if not query.has_terms:
            return []

        file_matches = self.filename_search.search(connection, query)
        if _cancelled(cancel_checker):
            return []
        content_matches = self.content_search.search(connection, query)
        if _cancelled(cancel_checker):
            return []
        lemma_matches = self.lemma_search.search(connection, query)
        if _cancelled(cancel_checker):
            return []
        if self.enable_fuzzy:
            fuzzy_file_matches, fuzzy_content_matches = self.fuzzy_search.search(connection, query)
            if _cancelled(cancel_checker):
                return []
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
            all_matches = [*file_matches.get(document_id, []), *combined_content]
            if not _matches_all_required_groups(query.groups, all_matches):
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

        ranked = self.ranking.sort(results)
        fresh = self.freshness_guard.filter_results(connection, ranked)
        return fresh[: self.max_documents]


def _cancelled(cancel_checker: Callable[[], bool] | None) -> bool:
    return cancel_checker is not None and cancel_checker()


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


def _matches_all_required_groups(groups: list[QueryTermGroup], matches: list[object]) -> bool:
    required_groups = [group for group in groups if group.required]
    return all(any(_match_belongs_to_group(match, group) for match in matches) for group in required_groups)


def _match_belongs_to_group(match: object, group: QueryTermGroup) -> bool:
    query_term = _normalize_match_term(getattr(match, "query_term", ""))
    if not query_term:
        return False
    candidates = {
        _normalize_match_term(value)
        for value in [*group.variants, *group.lemmas, group.original]
        if value
    }
    if query_term in candidates:
        return True
    variant_tokens = {
        _normalize_match_term(token)
        for variant in group.variants
        for token in variant.split()
    }
    return query_term in variant_tokens


def _normalize_match_term(value: object) -> str:
    return str(value).casefold().replace("ё", "е").strip()
