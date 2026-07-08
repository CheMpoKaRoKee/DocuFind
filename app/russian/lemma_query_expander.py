"""Expand user queries to Russian lemma variants."""

from __future__ import annotations

from app.russian.lemmatizer import Lemmatizer


class LemmaQueryExpander:
    def __init__(self, lemmatizer: Lemmatizer | None = None) -> None:
        self.lemmatizer = lemmatizer or Lemmatizer()

    def expand(self, query: str) -> list[str]:
        seen: set[str] = set()
        lemmas: list[str] = []
        for lemma in self.lemmatizer.lemmatize_text(query):
            if lemma not in seen:
                seen.add(lemma)
                lemmas.append(lemma)
        return lemmas

