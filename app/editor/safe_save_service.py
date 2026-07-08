"""Atomic text file save with backup and optional reindex."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.editor.backup_cleanup_service import BackupCleanupService
from app.editor.backup_service import BackupService
from app.editor.file_conflict_detector import FileConflictDetector
from app.editor.text_file_loader import EditorSnapshot
from app.storage.database import Database
from app.workers.reindex_worker import ReindexWorker
from app.workers.worker_state import WorkerResult


class SafeSaveError(Exception):
    def __init__(self, mode: str, message: str) -> None:
        super().__init__(message)
        self.mode = mode


@dataclass(frozen=True)
class SafeSaveResult:
    backup_path: Path | None
    reindex_result: WorkerResult | None = None


class SafeSaveService:
    def __init__(
        self,
        *,
        backup_service: BackupService,
        cleanup_service: BackupCleanupService | None = None,
        conflict_detector: FileConflictDetector | None = None,
        database: Database | None = None,
        backup_enabled: bool = True,
    ) -> None:
        self.backup_service = backup_service
        self.cleanup_service = cleanup_service
        self.conflict_detector = conflict_detector or FileConflictDetector()
        self.database = database
        self.backup_enabled = backup_enabled

    def save(self, snapshot: EditorSnapshot, text: str) -> SafeSaveResult:
        if snapshot.is_readonly:
            raise SafeSaveError("read_only", "File is read-only")
        if self.conflict_detector.has_changed(snapshot):
            raise SafeSaveError("blocked_changed_on_disk", "File changed on disk")

        backup_path = self.backup_service.create_backup(snapshot.path) if self.backup_enabled else None
        encoded = _normalize_line_endings(text, snapshot.line_ending).encode(snapshot.encoding)
        temp_path = _write_temp_file(snapshot.path, encoded)
        try:
            os.replace(temp_path, snapshot.path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        if self.cleanup_service is not None:
            self.cleanup_service.cleanup()

        reindex_result = ReindexWorker(self.database, snapshot.path).run() if self.database is not None else None
        return SafeSaveResult(backup_path=backup_path, reindex_result=reindex_result)


def _write_temp_file(path: Path, data: bytes) -> Path:
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp") as file:
        file.write(data)
        return Path(file.name)


def _normalize_line_endings(text: str, line_ending: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if line_ending == "crlf":
        return normalized.replace("\n", "\r\n")
    if line_ending == "cr":
        return normalized.replace("\n", "\r")
    return normalized
