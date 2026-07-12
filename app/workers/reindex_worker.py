"""Single-file reindex worker wrapper."""

from __future__ import annotations

from pathlib import Path

from app.indexer.index_service import IndexService
from app.storage.database import Database
from app.workers.worker_state import WorkerResult, WorkerState


class ReindexCancelled(Exception):
    """Cancellation observed before the single-file transaction committed."""


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
            summary = IndexService(self.database).reindex_file(
                self.file_path,
                cancel_checker=self._checkpoint,
            )
            return WorkerResult(status="completed", payload=summary)
        except ReindexCancelled:
            return WorkerResult(status="cancelled")
        except Exception as exc:
            return WorkerResult(status="failed", error=str(exc))

    def _checkpoint(self) -> bool:
        if not self.state.checkpoint():
            raise ReindexCancelled()
        return True


