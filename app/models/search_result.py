"""Aggregated search result model."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.content_match import ContentMatch
from app.models.document import Document
from app.models.file_match import FileMatch


@dataclass
class SearchResult:
    document: Document
    file_matches: list[FileMatch] = field(default_factory=list)
    content_matches: list[ContentMatch] = field(default_factory=list)
    total_content_matches: int = 0
    has_more_content_matches: bool = False
    score: float = 0.0

