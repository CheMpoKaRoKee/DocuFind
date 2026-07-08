"""Deduplicate matches from overlapping chunks or multiple search modes."""

from __future__ import annotations

from app.models.content_match import ContentMatch


class MatchDeduplicator:
    def deduplicate_content(self, matches: list[ContentMatch]) -> list[ContentMatch]:
        seen: set[tuple[int, int | None, int | None, str]] = set()
        result: list[ContentMatch] = []
        for match in matches:
            key = (match.document_id, match.char_start, match.char_end, match.matched_text.casefold())
            if key in seen:
                continue
            seen.add(key)
            result.append(match)
        return result

