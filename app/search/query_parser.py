"""Parse user search syntax into a structured query."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.query_term_group import QueryTermGroup
from app.models.search_query import SearchQuery
from app.russian.lemma_query_expander import LemmaQueryExpander
from app.utils.text_normalizer import TextNormalizer

TOKEN_RE = re.compile(r'(?:ext|folder):"[^"]*"|"[^"]*"|\S+', re.IGNORECASE)


@dataclass(frozen=True)
class QueryParser:
    normalizer: TextNormalizer | None = None
    lemma_expander: LemmaQueryExpander | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "normalizer", self.normalizer or TextNormalizer())
        object.__setattr__(self, "lemma_expander", self.lemma_expander or LemmaQueryExpander())

    def parse(self, raw: str) -> SearchQuery:
        groups: list[QueryTermGroup] = []
        extension: str | None = None
        folder: str | None = None

        for token in _tokenize(raw):
            if not token:
                continue
            lowered = token.casefold()
            if lowered.startswith("ext:"):
                extension = self._parse_extension(token[4:])
                continue
            if lowered.startswith("folder:"):
                folder = self._parse_folder(token[7:])
                continue

            is_phrase = token.startswith('"') and token.endswith('"') and len(token) >= 2
            original = token[1:-1] if is_phrase else token
            normalized = self.normalizer.normalize(original)
            if not normalized:
                continue
            groups.append(
                QueryTermGroup(
                    original=original,
                    variants=[normalized],
                    lemmas=self.lemma_expander.expand(normalized),
                    required=True,
                    is_phrase=is_phrase,
                )
            )

        return SearchQuery(raw=raw, groups=groups, extension=extension, folder=folder)

    def _parse_extension(self, value: str) -> str | None:
        normalized = self.normalizer.normalize(_strip_quotes(value)).replace(" ", "")
        if not normalized:
            return None
        return normalized.removeprefix(".")

    @staticmethod
    def _parse_folder(value: str) -> str | None:
        folder = _strip_quotes(value).strip()
        return folder or None


def _tokenize(raw: str) -> list[str]:
    return [match.group(0) for match in TOKEN_RE.finditer(raw)]


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


