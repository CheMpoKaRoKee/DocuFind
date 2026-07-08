"""Safe text file loading for the editor."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.indexer.file_filter import SUPPORTED_EXTENSIONS
from app.utils.encoding_detector import EncodingDetector
from app.utils.line_ending_detector import LineEndingDetector
from app.utils.path_rules import read_file_attributes

MAX_EDITOR_FILE_SIZE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class EditorSnapshot:
    path: Path
    size_bytes: int
    modified_ns: int | None
    modified_at: str
    content_hash: str | None
    encoding: str
    line_ending: str
    is_readonly: bool


@dataclass(frozen=True)
class LoadedTextFile:
    text: str
    mode: str
    snapshot: EditorSnapshot | None = None
    message: str | None = None


class TextFileLoader:
    def __init__(
        self,
        *,
        max_size_bytes: int = MAX_EDITOR_FILE_SIZE_BYTES,
        encoding_detector: EncodingDetector | None = None,
        line_ending_detector: LineEndingDetector | None = None,
    ) -> None:
        self.max_size_bytes = max_size_bytes
        self.encoding_detector = encoding_detector or EncodingDetector()
        self.line_ending_detector = line_ending_detector or LineEndingDetector()

    def load(self, path: Path) -> LoadedTextFile:
        path = Path(path)
        if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            return LoadedTextFile(text="", mode="blocked_unsupported", message="Unsupported file type")

        try:
            stat_result = path.stat()
        except OSError as exc:
            return LoadedTextFile(text="", mode="blocked_changed_on_disk", message=str(exc))

        size_bytes = int(stat_result.st_size)
        if size_bytes > self.max_size_bytes:
            return LoadedTextFile(text="", mode="blocked_too_large", message="File exceeds editor size limit")

        try:
            data = path.read_bytes()
        except OSError as exc:
            return LoadedTextFile(text="", mode="blocked_changed_on_disk", message=str(exc))

        encoding = self.encoding_detector.detect(data)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError as exc:
            return LoadedTextFile(text="", mode="blocked_unsupported", message=str(exc))

        attributes = read_file_attributes(path)
        snapshot = EditorSnapshot(
            path=path,
            size_bytes=size_bytes,
            modified_ns=getattr(stat_result, "st_mtime_ns", None),
            modified_at=datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat(),
            content_hash=_hash_bytes(data),
            encoding=encoding,
            line_ending=self.line_ending_detector.detect(text),
            is_readonly=attributes.is_readonly,
        )
        return LoadedTextFile(text=text, mode="read_only" if attributes.is_readonly else "editable", snapshot=snapshot)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
