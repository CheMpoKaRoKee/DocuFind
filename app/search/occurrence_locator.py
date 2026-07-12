"""Locate exact and lemma occurrences inside chunks."""

from __future__ import annotations

from dataclasses import dataclass

from app.russian.lemmatizer import Lemmatizer
from app.russian.russian_tokenizer import TOKEN_RE


@dataclass(frozen=True)
class LocatedOccurrence:
    line_number: int
    column_number: int
    char_start: int
    char_end: int
    matched_text: str
    query_term: str
    match_type: str


class OccurrenceLocator:
    def __init__(self, lemmatizer: Lemmatizer | None = None) -> None:
        self.lemmatizer = lemmatizer or Lemmatizer()

    def locate_exact(
        self,
        text: str,
        terms: list[str],
        *,
        is_phrase: bool = False,
        line_number_offset: int = 0,
        first_line_column_offset: int = 0,
    ) -> list[LocatedOccurrence]:
        haystack = text.casefold().replace("ё", "е")
        results: list[LocatedOccurrence] = []
        for term in terms:
            needle = term.casefold().replace("ё", "е")
            if not needle:
                continue
            start = 0
            while True:
                index = haystack.find(needle, start)
                if index < 0:
                    break
                end = index + len(needle)
                results.append(
                    self._build(text, index, end, term, "exact", line_number_offset, first_line_column_offset)
                )
                start = end if is_phrase else index + 1
        return results

    def locate_lemmas(
        self,
        text: str,
        lemmas: list[str],
        *,
        line_number_offset: int = 0,
        first_line_column_offset: int = 0,
    ) -> list[LocatedOccurrence]:
        lemma_set = set(lemmas)
        results: list[LocatedOccurrence] = []
        for match in TOKEN_RE.finditer(text):
            token = match.group(0)
            lemma = self.lemmatizer.lemmatize_token(token)
            if lemma in lemma_set:
                results.append(
                    self._build(
                        text, match.start(), match.end(), lemma, "lemma",
                        line_number_offset, first_line_column_offset,
                    )
                )
        return results

    def _build(
        self,
        text: str,
        start: int,
        end: int,
        query_term: str,
        match_type: str,
        line_number_offset: int = 0,
        first_line_column_offset: int = 0,
    ) -> LocatedOccurrence:
        line_number = text.count("\n", 0, start) + 1
        last_newline = text.rfind("\n", 0, start)
        line_start = 0 if last_newline < 0 else last_newline + 1
        return LocatedOccurrence(
            line_number=line_number + line_number_offset,
            column_number=start - line_start + 1 + (first_line_column_offset if line_number == 1 else 0),
            char_start=start,
            char_end=end,
            matched_text=text[start:end],
            query_term=query_term,
            match_type=match_type,
        )
