"""Simple deterministic ranking for search results."""

from __future__ import annotations

from app.models.search_result import SearchResult


class Ranking:
    def score(self, result: SearchResult) -> float:
        file_score = 3.0 * len(result.file_matches)
        exact_score = 2.0 * sum(1 for match in result.content_matches if match.match_type == "exact")
        lemma_score = 1.0 * sum(1 for match in result.content_matches if match.match_type == "lemma")
        return file_score + exact_score + lemma_score

    def sort(self, results: list[SearchResult]) -> list[SearchResult]:
        for result in results:
            result.score = self.score(result)
        return sorted(results, key=lambda item: (-item.score, item.document.path.casefold()))

