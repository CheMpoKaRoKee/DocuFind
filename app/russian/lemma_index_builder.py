"""Build per-source lemma counts for indexing."""

from __future__ import annotations

from collections import Counter

from app.russian.lemmatizer import Lemmatizer


class LemmaIndexBuilder:
    def __init__(self, lemmatizer: Lemmatizer | None = None) -> None:
        self.lemmatizer = lemmatizer or Lemmatizer()

    def collect(self, text: str, source: str) -> list[tuple[str, str, int]]:
        counts = Counter(self.lemmatizer.lemmatize_text(text))
        return [(lemma, source, count) for lemma, count in sorted(counts.items())]

