"""Single-file reindex worker wrapper."""

from __future__ import annotations

from pathlib import Path

from app.indexer.index_service import IndexService
from app.storage.database import Database
from app.workers.worker_state import WorkerResult, WorkerState


class ReindexWorker:
    def __init__(self, database: Database, file_path: Path, *, state: WorkerState | None = None) -> None:
        self.database = database
        self.file_path = Path(file_path)
        self.state = state or WorkerState()

    def cancel(self) -> None:
        self.state.cancel()

    def pause(self) -> None:
        self.state.pause()

    def resume(self) -> None:
        self.state.resume()

    def run(self) -> WorkerResult:
        if not self.state.checkpoint():
            return WorkerResult(status="cancelled")
        try:
            summary = IndexService(self.database).reindex_file(self.file_path)
            if self.state.is_cancelled:
                return WorkerResult(status="cancelled", payload=summary)
            return WorkerResult(status="completed", payload=summary)
        except Exception as exc:
            return WorkerResult(status="failed", error=str(exc))


