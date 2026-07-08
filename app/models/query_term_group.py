"""Search query term group model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QueryTermGroup:
    original: str
    variants: list[str] = field(default_factory=list)
    lemmas: list[str] = field(default_factory=list)
    fuzzy_variants: list[str] = field(default_factory=list)
    required: bool = True
    is_phrase: bool = False

