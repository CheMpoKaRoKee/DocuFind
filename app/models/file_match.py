"""File-level search match model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileMatch:
    document_id: int
    match_field: str
    query_term: str
    matched_text: str
    match_type: str
    similarity: float | None = None

