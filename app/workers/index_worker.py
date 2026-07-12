"""Index worker wrapper."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from app.indexer.file_filter import FileFilter
from app.indexer.folder_scanner import FolderScanner
from app.indexer.index_service import IndexService
from app.models.index_progress import IndexProgress
from app.settings import ApplicationSettings, load_settings
from app.storage.database import Database
from app.storage.settings_repository import SettingsRepository
from app.utils.app_paths import AppPaths
from app.utils.path_rules import PathRules
from app.workers.worker_state import WorkerResult, WorkerState


class IndexWorker:
    def __init__(
        self,
        database: Database,
        folder: Path,
        *,
        state: WorkerState | None = None,
        settings: ApplicationSettings | None = None,
    ) -> None:
        self.database = database
        self.folder = Path(folder)
        self.state = state or WorkerState()
        self.settings = settings

    def cancel(self) -> None:
        self.state.cancel()

    def pause(self) -> None:
        self.state.pause()

    def resume(self) -> None:
        self.state.resume()

    def run(self, progress_callback: Callable[[IndexProgress], None] | None = None) -> WorkerResult:
        if not self.state.checkpoint():
            return WorkerResult(status="cancelled")
        try:
            settings = self.settings or _load_worker_settings(self.database)
            path_rules = PathRules(excluded_names=frozenset(settings.excluded_folders))
            file_filter = FileFilter(
                path_rules=path_rules,
                max_size_bytes=settings.max_index_file_size_bytes,
                supported_extensions=frozenset(settings.enabled_extensions),
            )
            scanner = FolderScanner(file_filter=file_filter, path_rules=path_rules)
            summary = IndexService(self.database, scanner=scanner).index_folder(
                self.folder,
                progress_callback=progress_callback,
                cancel_checker=lambda: not self.state.checkpoint(),
            )
            if self.state.is_cancelled:
                return WorkerResult(status="cancelled", payload=summary)
            return WorkerResult(status="completed", payload=summary)
        except Exception as exc:
            return WorkerResult(status="failed", error=str(exc))


def _load_worker_settings(database: Database) -> ApplicationSettings:
    database.initialize()
    with database.session() as connection:
        paths = AppPaths(base_dir=database.path.parent, portable=True)
        return load_settings(SettingsRepository(connection), paths)

