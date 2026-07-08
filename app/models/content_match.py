"""Content search match model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContentMatch:
    document_id: int
    chunk_id: int
    line_number: int | None
    column_number: int | None
    char_start: int | None
    char_end: int | None
    query_term: str
    matched_text: str
    snippet: str
    match_type: str
    similarity: float | None = None

