"""Recursive folder scanner with filtering."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from app.indexer.file_filter import FileFilter, FileFilterResult
from app.utils.logger import get_logger
from app.utils.path_rules import PathRules, read_file_attributes


class FolderScanner:
    def __init__(self, file_filter: FileFilter | None = None, path_rules: PathRules | None = None) -> None:
        self.path_rules = path_rules or PathRules()
        self.file_filter = file_filter or FileFilter(path_rules=self.path_rules)
        self.logger = get_logger("indexing")

    def scan(self, root: Path) -> Iterator[FileFilterResult]:
        root = Path(root)
        if not root.exists() or not root.is_dir():
            self.logger.warning("Scan root is not a directory: path=%s", root)
            return

        stack = [root]
        while stack:
            current = stack.pop()
            try:
                for child in current.iterdir():
                    if child.is_dir():
                        if self._should_enter_dir(child):
                            stack.append(child)
                        continue
                    if child.is_file():
                        yield self.file_filter.evaluate(child)
            except OSError:
                self.logger.warning("Cannot scan directory: path=%s", current)

    def _should_enter_dir(self, path: Path) -> bool:
        attributes = read_file_attributes(path)
        if attributes.is_symlink or attributes.is_junction:
            self.logger.info("Directory skipped: status=skipped_symlink_or_junction path=%s", path)
            return False
        if self.path_rules.is_excluded(path):
            self.logger.info("Directory skipped: status=skipped_excluded_path path=%s", path)
            return False
        if attributes.is_system:
            self.logger.info("Directory skipped: status=skipped_system_file path=%s", path)
            return False
        return True

