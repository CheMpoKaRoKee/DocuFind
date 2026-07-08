"""Backup creation before safe editor saves."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path


class BackupService:
    def __init__(self, backups_dir: Path) -> None:
        self.backups_dir = Path(backups_dir)

    def create_backup(self, path: Path) -> Path:
        path = Path(path)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        target_dir = self.backups_dir / timestamp[:8]
        target_dir.mkdir(parents=True, exist_ok=True)
        backup_path = target_dir / f"{_safe_name(path)}.{timestamp}.bak"
        shutil.copy2(path, backup_path)
        return backup_path


def _safe_name(path: Path) -> str:
    text = str(path.resolve(strict=False)).replace(":", "").replace("\\", "__").replace("/", "__")
    return text[-180:]
