"""Parsed search query model."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.query_term_group import QueryTermGroup


@dataclass(frozen=True)
class SearchQuery:
    raw: str
    groups: list[QueryTermGroup] = field(default_factory=list)
    extension: str | None = None
    folder: str | None = None

    @property
    def has_terms(self) -> bool:
        return bool(self.groups)

