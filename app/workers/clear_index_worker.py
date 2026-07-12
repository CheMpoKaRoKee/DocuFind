"""Worker wrapper for explicit index reset."""

from __future__ import annotations

from collections.abc import Callable

from app.models.index_progress import IndexProgress
from app.storage.database import Database
from app.storage.index_reset_service import IndexResetCancelled, IndexResetLocked, IndexResetService
from app.workers.worker_state import WorkerResult, WorkerState


class ClearIndexWorker:
    def __init__(self, database: Database, *, state: WorkerState | None = None) -> None:
        self.database = database
        self.state = state or WorkerState()

    def cancel(self) -> None:
        self.state.cancel()

    def run(self, progress_callback: Callable[[IndexProgress], None] | None = None) -> WorkerResult:
        if not self.state.checkpoint():
            return WorkerResult(status="cancelled")
        try:
            summary = IndexResetService(self.database).clear_index(
                progress_callback=progress_callback,
                cancel_checker=lambda: not self.state.checkpoint(),
            )
            if self.state.is_cancelled:
                return WorkerResult(status="cancelled", payload=summary)
            return WorkerResult(status="completed", payload=summary)
        except IndexResetCancelled:
            return WorkerResult(status="cancelled")
        except IndexResetLocked:
            return WorkerResult(status="failed", error="База данных занята другим процессом. Закройте другие окна DocuFind и повторите удаление индекса.")
        except Exception as exc:
            return WorkerResult(status="failed", error=str(exc))
