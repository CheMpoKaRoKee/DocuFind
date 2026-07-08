"""Document search model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    id: int
    path: str
    filename: str
    extension: str | None
    size_bytes: int
    modified_at: str

