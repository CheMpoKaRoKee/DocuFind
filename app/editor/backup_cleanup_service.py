"""Backup retention and storage cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class BackupCleanupSummary:
    deleted_count: int = 0
    remaining_bytes: int = 0


class BackupCleanupService:
    def __init__(
        self,
        backups_dir: Path,
        *,
        retention_days: int = 30,
        max_storage_bytes: int = 500 * 1024 * 1024,
    ) -> None:
        self.backups_dir = Path(backups_dir)
        self.retention_days = retention_days
        self.max_storage_bytes = max_storage_bytes

    def cleanup(self) -> BackupCleanupSummary:
        if not self.backups_dir.exists():
            return BackupCleanupSummary()

        deleted = 0
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        files = [path for path in self.backups_dir.rglob("*") if path.is_file()]
        for path in files:
            if _modified_at(path) < cutoff:
                deleted += _delete(path)

        files = sorted((path for path in self.backups_dir.rglob("*") if path.is_file()), key=_modified_at)
        total = sum(_size(path) for path in files)
        for path in files:
            if total <= self.max_storage_bytes:
                break
            size = _size(path)
            deleted += _delete(path)
            total -= size

        self._remove_empty_dirs()
        return BackupCleanupSummary(deleted_count=deleted, remaining_bytes=max(total, 0))

    def _remove_empty_dirs(self) -> None:
        for path in sorted((p for p in self.backups_dir.rglob("*") if p.is_dir()), reverse=True):
            try:
                path.rmdir()
            except OSError:
                pass


def _modified_at(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC)


def _size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _delete(path: Path) -> int:
    try:
        path.unlink()
        return 1
    except OSError:
        return 0
