"""Path normalization helpers."""

from __future__ import annotations

import unicodedata
from pathlib import Path


def normalize_path(path: str | Path) -> str:
    text = str(path).replace("\\", "/")
    text = unicodedata.normalize("NFKC", text).casefold()
    parts = [part for part in text.split("/") if part]
    return " ".join(parts)

