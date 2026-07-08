"""Build compact snippets around content matches."""

from __future__ import annotations


class SnippetBuilder:
    def __init__(self, context_chars: int = 60) -> None:
        self.context_chars = context_chars

    def build(self, text: str, start: int, end: int) -> str:
        snippet_start = max(0, start - self.context_chars)
        snippet_end = min(len(text), end + self.context_chars)
        prefix = "..." if snippet_start > 0 else ""
        suffix = "..." if snippet_end < len(text) else ""
        return prefix + text[snippet_start:snippet_end].replace("\r", "").replace("\n", " ") + suffix

