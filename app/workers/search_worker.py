"""Search worker wrapper."""

from __future__ import annotations

from app.search.fuzzy_search import FuzzySearch
from app.search.search_service import SearchService
from app.settings import ApplicationSettings, load_settings
from app.storage.database import Database
from app.storage.settings_repository import SettingsRepository
from app.utils.app_paths import AppPaths
from app.workers.worker_state import WorkerResult, WorkerState


class SearchWorker:
    def __init__(
        self,
        database: Database,
        query: str,
        *,
        state: WorkerState | None = None,
        settings: ApplicationSettings | None = None,
    ) -> None:
        self.database = database
        self.query = query
        self.state = state or WorkerState()
        self.settings = settings

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
            settings = self.settings or _load_worker_settings(self.database)
            service = SearchService(
                fuzzy_search=FuzzySearch(
                    filename_threshold=settings.fuzzy_filename_threshold,
                    content_threshold=settings.fuzzy_content_threshold,
                ),
                enable_fuzzy=settings.fuzzy_enabled,
                max_documents=settings.search_result_limit,
                max_matches_per_document=settings.matches_per_file_limit,
            )
            with self.database.session() as connection:
                results = service.search(connection, self.query)
            if self.state.is_cancelled:
                return WorkerResult(status="cancelled", payload=results)
            return WorkerResult(status="completed", payload=results)
        except Exception as exc:
            return WorkerResult(status="failed", error=str(exc))


def _load_worker_settings(database: Database) -> ApplicationSettings:
    database.initialize()
    with database.session() as connection:
        paths = AppPaths(base_dir=database.path.parent, portable=True)
        return load_settings(SettingsRepository(connection), paths)

