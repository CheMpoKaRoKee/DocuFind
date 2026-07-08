"""Collect normalized terms for indexing and fuzzy candidates."""

from __future__ import annotations

from collections import Counter

from app.utils.text_normalizer import TextNormalizer


class TermCollector:
    def __init__(self, normalizer: TextNormalizer | None = None) -> None:
        self.normalizer = normalizer or TextNormalizer()

    def collect(self, text: str, source: str) -> list[tuple[str, str, int]]:
        counts = Counter(self.normalizer.terms(text))
        return [(term, source, count) for term, count in sorted(counts.items())]

