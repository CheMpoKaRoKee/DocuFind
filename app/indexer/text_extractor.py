"""Text extraction for MVP text formats."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from app.indexer.file_filter import MAX_INDEX_FILE_SIZE_BYTES, SUPPORTED_EXTENSIONS
from app.utils.encoding_detector import EncodingDetector
from app.utils.line_ending_detector import LineEndingDetector
from app.utils.long_line_handler import LongLineHandler


@dataclass(frozen=True)
class ExtractedText:
    text: str
    encoding: str
    line_ending: str
    long_line_count: int = 0
    content_hash: str | None = None


class TextExtractionError(Exception):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


class TextExtractor:
    def __init__(
        self,
        *,
        max_size_bytes: int = MAX_INDEX_FILE_SIZE_BYTES,
        encoding_detector: EncodingDetector | None = None,
        line_ending_detector: LineEndingDetector | None = None,
        long_line_handler: LongLineHandler | None = None,
    ) -> None:
        self.max_size_bytes = max_size_bytes
        self.encoding_detector = encoding_detector or EncodingDetector()
        self.line_ending_detector = line_ending_detector or LineEndingDetector()
        self.long_line_handler = long_line_handler or LongLineHandler()

    def extract(self, path: Path) -> ExtractedText:
        if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            raise TextExtractionError("skipped_unsupported_extension", f"Unsupported file extension: {path.suffix}")

        try:
            size_bytes = path.stat().st_size
        except OSError as exc:
            raise TextExtractionError("error_read", str(exc)) from exc

        if size_bytes > self.max_size_bytes:
            raise TextExtractionError("skipped_too_large", "File exceeds text extraction size limit")

        try:
            data = path.read_bytes()
        except OSError as exc:
            raise TextExtractionError("error_read", str(exc)) from exc

        encoding = self.encoding_detector.detect(data)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError as exc:
            raise TextExtractionError("error_decode", str(exc)) from exc

        line_ending = self.line_ending_detector.detect(text)
        if path.suffix.casefold() in {".html", ".htm"}:
            text = _sanitize_html(text)
        processed = self.long_line_handler.process(text)
        return ExtractedText(
            text=processed.text,
            encoding=encoding,
            line_ending=line_ending,
            long_line_count=processed.long_line_count,
            content_hash=hashlib.sha256(data).hexdigest(),
        )


_HIDDEN_HTML_RE = re.compile(
    r"<(script|style|noscript|svg)\b[^>]*>.*?</\1\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_MARKUP_RE = re.compile(r"<!--.*?-->|<![^>]*>|<[^>]+>", flags=re.DOTALL)


def _sanitize_html(text: str) -> str:
    """Remove non-visible HTML while preserving source offsets and lines."""
    text = _HIDDEN_HTML_RE.sub(_blank_preserving_newlines, text)
    return _HTML_MARKUP_RE.sub(_blank_preserving_newlines, text)


def _blank_preserving_newlines(match: re.Match[str]) -> str:
    return "".join(char if char in "\r\n" else " " for char in match.group(0))
