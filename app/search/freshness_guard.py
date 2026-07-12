"""Filter stale search results against the filesystem before returning them."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.indexer.document_state_service import DocumentStateService
from app.indexer.file_change_detector import FileChangeDetector
from app.models.search_result import SearchResult
from app.storage.document_repository import DocumentRepository
from app.storage.reindex_queue_repository import ReindexQueueRepository


class FreshnessGuard:
    def __init__(self, change_detector: FileChangeDetector | None = None) -> None:
        self.change_detector = change_detector or FileChangeDetector()

    def filter_results(self, connection: sqlite3.Connection, results: list[SearchResult]) -> list[SearchResult]:
        document_repo = DocumentRepository(connection)
        state_service = DocumentStateService(connection)
        queue_repo = ReindexQueueRepository(connection)
        fresh: list[SearchResult] = []
        for result in results:
            row = document_repo.get(result.document.id)
            if row is None:
                continue
            decision = self.change_detector.detect(row, Path(result.document.path))
            if decision.decision == "missing":
                state_service.mark_deleted_retained(result.document.id, reason="search_missing")
                continue
            if decision.decision in {"changed_hash", "restored_changed"}:
                state_service.mark_queued_reindex(result.document.id, reason="search_stale_detected")
                queue_repo.enqueue(result.document.path, "search_stale_detected", result.document.id, priority=10)
                continue
            if decision.decision == "changed_metadata":
                document_repo.update_metadata_from_signature(result.document.id, decision.signature, status="indexed")
            elif decision.decision == "restored_unchanged":
                state_service.restore_indexed(result.document.id, reason="restored_without_reindex")
            else:
                document_repo.touch_verified(result.document.id)
            fresh.append(result)
        return fresh
