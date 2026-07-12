"""Line-aware text chunking with overlap and source positions."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int
    column_start: int


class Chunker:
    def __init__(self, *, chunk_size: int = 10_000, overlap: int = 800, max_line_length: int = 20_000) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.max_line_length = max_line_length

    def chunk(self, text: str) -> list[TextChunk]:
        if not text:
            return []

        line_starts = _line_starts(text)
        segments = list(self._segments(text))
        chunks: list[TextChunk] = []
        current_text = ""
        current_start = 0
        current_end = 0

        def flush() -> TextChunk | None:
            nonlocal current_text, current_start, current_end
            if not current_text:
                return None
            chunk = TextChunk(
                chunk_index=len(chunks),
                text=current_text,
                line_start=_line_for_char(line_starts, current_start),
                line_end=_line_for_char(line_starts, max(current_end - 1, current_start)),
                char_start=current_start,
                char_end=current_end,
                column_start=_column_for_char(text, current_start),
            )
            chunks.append(chunk)
            current_text = ""
            return chunk

        for segment_start, segment_end, force_boundary_after in segments:
            segment_text = text[segment_start:segment_end]
            if current_text and len(current_text) + len(segment_text) > self.chunk_size:
                previous = flush()
                if previous is not None:
                    seed_len = min(self.overlap, len(previous.text), max(0, self.chunk_size - len(segment_text)))
                    if seed_len:
                        current_text = previous.text[-seed_len:]
                        current_start = previous.char_end - seed_len
                        current_end = previous.char_end

            if not current_text:
                current_start = segment_start
            current_text += segment_text
            current_end = segment_end

            if force_boundary_after:
                flush()

        flush()
        return chunks

    def _segments(self, text: str) -> list[tuple[int, int, bool]]:
        result: list[tuple[int, int, bool]] = []
        segment_limit = min(self.max_line_length, self.chunk_size)
        position = 0
        for line in text.splitlines(keepends=True):
            line_start = position
            line_end = position + len(line)
            body = line.rstrip("\r\n")
            ending_length = len(line) - len(body)
            body_start = line_start
            body_end = line_end - ending_length

            if len(body) > segment_limit:
                start = body_start
                while start < body_end:
                    end = min(start + segment_limit, body_end)
                    result.append((start, end, True))
                    start = end
                if ending_length:
                    result.append((body_end, line_end, True))
            else:
                result.append((line_start, line_end, False))
            position = line_end

        if position < len(text):
            result.append((position, len(text), False))
        return result


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n" and index + 1 < len(text):
            starts.append(index + 1)
    return starts


def _line_for_char(line_starts: list[int], char_index: int) -> int:
    return bisect_right(line_starts, char_index) or 1


def _column_for_char(text: str, char_index: int) -> int:
    last_newline = text.rfind("\n", 0, char_index)
    return char_index - last_newline
