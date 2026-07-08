"""Path exclusion and filesystem attribute rules."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.app_paths import AppPaths

FILE_ATTRIBUTE_READONLY = 0x01
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_SYSTEM = 0x04
FILE_ATTRIBUTE_REPARSE_POINT = 0x400

DEFAULT_EXCLUDED_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".cache",
    "appdata",
    "windows",
    "program files",
    "program files (x86)",
    "temp",
    "data",
    "logs",
    "backups",
}


@dataclass(frozen=True)
class FileAttributes:
    is_hidden: bool = False
    is_system: bool = False
    is_readonly: bool = False
    is_symlink: bool = False
    is_junction: bool = False


@dataclass(frozen=True)
class PathRules:
    app_paths: AppPaths | None = None
    excluded_names: frozenset[str] = field(default_factory=lambda: frozenset(DEFAULT_EXCLUDED_NAMES))

    def is_excluded(self, path: Path) -> bool:
        normalized_parts = {part.casefold() for part in path.parts}
        if normalized_parts.intersection(self.excluded_names):
            return True

        if self.app_paths is None:
            return False

        try:
            candidate = path.resolve(strict=False)
            service_roots = (
                self.app_paths.data_dir.resolve(strict=False),
                self.app_paths.logs_dir.resolve(strict=False),
                self.app_paths.backups_dir.resolve(strict=False),
            )
            return any(candidate == root or root in candidate.parents for root in service_roots)
        except OSError:
            return False


def read_file_attributes(path: Path) -> FileAttributes:
    is_symlink = path.is_symlink()
    try:
        stat_result = path.stat()
    except OSError:
        return FileAttributes(is_symlink=is_symlink)

    raw_attrs = getattr(stat_result, "st_file_attributes", 0)
    name_hidden = path.name.startswith(".")
    is_hidden = bool(raw_attrs & FILE_ATTRIBUTE_HIDDEN) or name_hidden
    is_system = bool(raw_attrs & FILE_ATTRIBUTE_SYSTEM)
    is_readonly = bool(raw_attrs & FILE_ATTRIBUTE_READONLY) or not os.access(path, os.W_OK)
    is_junction = bool(raw_attrs & FILE_ATTRIBUTE_REPARSE_POINT) and not is_symlink
    return FileAttributes(
        is_hidden=is_hidden,
        is_system=is_system,
        is_readonly=is_readonly,
        is_symlink=is_symlink,
        is_junction=is_junction,
    )

