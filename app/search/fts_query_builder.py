"""Whitelist-based SQLite FTS query builder."""

from __future__ import annotations

import re

from app.models.query_term_group import QueryTermGroup
from app.models.search_query import SearchQuery

FTS_TOKEN_RE = re.compile(r"^[0-9A-Za-zА-Яа-яЁё_]+$", re.UNICODE)


class FtsQueryBuilder:
    def build(self, query: SearchQuery) -> str | None:
        parts: list[str] = []
        for group in query.groups:
            expression = self._build_group(group)
            if expression:
                parts.append(expression)
        if not parts:
            return None
        return " AND ".join(parts)

    def _build_group(self, group: QueryTermGroup) -> str | None:
        variants = group.variants if group.is_phrase else [*group.variants, *group.lemmas]
        cleaned: list[str] = []
        seen: set[str] = set()
        for variant in variants:
            expression = self._sanitize_phrase(variant) if group.is_phrase else self._sanitize_term(variant)
            if expression and expression not in seen:
                seen.add(expression)
                cleaned.append(expression)
        if not cleaned:
            return None
        if len(cleaned) == 1:
            return cleaned[0]
        return "(" + " OR ".join(cleaned) + ")"

    def _sanitize_phrase(self, value: str) -> str | None:
        tokens = [_quote_token(token) for token in value.split() if _is_allowed_token(token)]
        if not tokens:
            return None
        return '"' + " ".join(token.strip('"') for token in tokens) + '"'

    def _sanitize_term(self, value: str) -> str | None:
        tokens = [_quote_token(token) for token in value.split() if _is_allowed_token(token)]
        if not tokens:
            return None
        if len(tokens) == 1:
            return tokens[0]
        return " AND ".join(tokens)


def _is_allowed_token(token: str) -> bool:
    return bool(FTS_TOKEN_RE.fullmatch(token))


def _quote_token(token: str) -> str:
    return '"' + token.replace('"', "") + '"'


