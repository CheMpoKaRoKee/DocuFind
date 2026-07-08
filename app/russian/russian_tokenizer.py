"""Russian-aware tokenization."""

from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)
RUSSIAN_RE = re.compile(r"[А-Яа-яЁё]")


class RussianTokenizer:
    def tokenize(self, text: str) -> list[str]:
        return [match.group(0).casefold().replace("ё", "е") for match in TOKEN_RE.finditer(text)]

    def russian_tokens(self, text: str) -> list[str]:
        return [token for token in self.tokenize(text) if RUSSIAN_RE.search(token)]


def is_russian_token(token: str) -> bool:
    return bool(RUSSIAN_RE.search(token))

