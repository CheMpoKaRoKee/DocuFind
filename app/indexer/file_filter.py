"""File filtering before text extraction and indexing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.utils.binary_detector import BinaryDetector
from app.utils.logger import get_logger
from app.utils.path_rules import PathRules, read_file_attributes

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".ts",
    ".css",
    ".sql",
    ".log",
    ".ini",
    ".yaml",
    ".yml",
}

MAX_INDEX_FILE_SIZE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class FileFilterResult:
    path: Path
    status: str
    can_index: bool
    size_bytes: int = 0
    is_hidden: bool = False
    is_system: bool = False
    is_readonly: bool = False
    error_message: str | None = None


class FileFilter:
    def __init__(
        self,
        *,
        path_rules: PathRules | None = None,
        binary_detector: BinaryDetector | None = None,
        max_size_bytes: int = MAX_INDEX_FILE_SIZE_BYTES,
        supported_extensions: set[str] | frozenset[str] | None = None,
    ) -> None:
        self.path_rules = path_rules or PathRules()
        self.binary_detector = binary_detector or BinaryDetector()
        self.max_size_bytes = max_size_bytes
        self.supported_extensions = {
            extension if extension.startswith(".") else f".{extension}"
            for extension in (supported_extensions or SUPPORTED_EXTENSIONS)
        }
        self.logger = get_logger("indexing")

    def evaluate(self, path: Path) -> FileFilterResult:
        try:
            attributes = read_file_attributes(path)

            if attributes.is_symlink:
                return self._skip(path, "skipped_symlink", attributes=attributes)
            if attributes.is_junction:
                return self._skip(path, "skipped_junction", attributes=attributes)
            if self.path_rules.is_excluded(path):
                return self._skip(path, "skipped_excluded_path", attributes=attributes)
            if attributes.is_system:
                return self._skip(path, "skipped_system_file", attributes=attributes)
            if path.suffix.casefold() not in self.supported_extensions:
                return self._skip(path, "skipped_unsupported_extension", attributes=attributes)

            stat_result = path.stat()
            size_bytes = int(stat_result.st_size)
            if size_bytes > self.max_size_bytes:
                return self._skip(path, "skipped_too_large", size_bytes=size_bytes, attributes=attributes)
            if self.binary_detector.is_binary(path):
                return self._skip(path, "skipped_binary", size_bytes=size_bytes, attributes=attributes)

            return FileFilterResult(
                path=path,
                status="indexed",
                can_index=True,
                size_bytes=size_bytes,
                is_hidden=attributes.is_hidden,
                is_system=attributes.is_system,
                is_readonly=attributes.is_readonly,
            )
        except OSError as exc:
            self.logger.warning("File filter read error: status=error_read path=%s", _safe_path(path))
            return FileFilterResult(path=path, status="error_read", can_index=False, error_message=str(exc))

    def _skip(
        self,
        path: Path,
        status: str,
        *,
        size_bytes: int = 0,
        attributes=None,
    ) -> FileFilterResult:
        self.logger.info("File skipped: status=%s path=%s", status, _safe_path(path))
        return FileFilterResult(
            path=path,
            status=status,
            can_index=False,
            size_bytes=size_bytes,
            is_hidden=bool(getattr(attributes, "is_hidden", False)),
            is_system=bool(getattr(attributes, "is_system", False)),
            is_readonly=bool(getattr(attributes, "is_readonly", False)),
        )


def _safe_path(path: Path) -> str:
    text = str(path)
    return text if len(text) <= 160 else "..." + text[-157:]
