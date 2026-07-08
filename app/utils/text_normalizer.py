"""Text normalization for filename, path, and content terms."""

from __future__ import annotations

import re
import unicodedata

TOKEN_SEPARATOR_RE = re.compile(r"[^0-9A-Za-zА-Яа-яЁё]+", re.UNICODE)
SPACE_RE = re.compile(r"\s+")


class TextNormalizer:
    def normalize(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
        normalized = TOKEN_SEPARATOR_RE.sub(" ", normalized)
        return SPACE_RE.sub(" ", normalized).strip()

    def terms(self, text: str) -> list[str]:
        normalized = self.normalize(text)
        if not normalized:
            return []
        return normalized.split(" ")

