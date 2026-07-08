"""Main PySide6 window for DocuFind Local."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.i18n.i18n_service import I18nService, load_i18n
from app.settings import ApplicationSettings, load_settings, save_settings
from app.storage.database import Database
from app.storage.index_folder_repository import IndexFolderRepository
from app.storage.settings_repository import SettingsRepository
from app.ui.editor_panel import EditorPanel
from app.ui.index_panel import IndexPanel
from app.ui.preview_panel import PreviewPanel
from app.ui.results_panel import ResultsPanel
from app.ui.search_panel import SearchPanel
from app.ui.settings_dialog import SettingsDialog
from app.utils.app_paths import AppPaths
from app.utils.path_normalizer import normalize_path
from app.workers.index_worker import IndexWorker
from app.workers.search_worker import SearchWorker

LANGUAGE_SETTING = "language"


class WorkerThread(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, task: Callable[[], object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task = task

    def run(self) -> None:
        try:
            self.completed.emit(self.task())
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        i18n: I18nService | None = None,
        database: Database | None = None,
        paths: AppPaths | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.paths = paths or AppPaths.from_environment()
        self.paths.ensure_runtime_dirs()
        self.database = database or Database(self.paths.database_path)
        self.database.initialize()
        self.settings = self._load_settings()
        self.i18n = i18n or load_i18n(self.settings.language)
        self._active_thread: WorkerThread | None = None
        self._active_worker: object | None = None
        self._reindex_required = False

        self.index_panel = IndexPanel(self.i18n, self)
        self.search_panel = SearchPanel(self.i18n, self)
        self.results_panel = ResultsPanel(self.i18n, self)
        self.preview_panel = PreviewPanel(self.i18n, self)
        self.editor_panel = EditorPanel(
            self.i18n,
            paths=self.paths,
            database=self.database,
            settings=self.settings,
            parent=self,
        )
        self.settings_button = QPushButton(self)
        self.settings_button.setObjectName("settingsButton")

        self._build_layout()
        self._connect_signals()
        self._set_initial_folder()
        self.retranslate()
        self._refresh_index_state()

    def retranslate(self) -> None:
        self.setWindowTitle(self.i18n.translate("app.title"))
        self.settings_button.setText(self.i18n.translate("settings.title"))
        self.index_panel.retranslate()
        self.search_panel.retranslate()
        self.results_panel.retranslate()
        self.preview_panel.retranslate()
        self.editor_panel.retranslate()
        self.content_tabs.setTabText(0, self.i18n.translate("preview.title"))
        self.content_tabs.setTabText(1, self.i18n.translate("editor.title"))
        self.statusBar().showMessage(self.i18n.translate("status.ready"))
        self._refresh_index_state()

    def apply_language(self, language: str) -> None:
        self.i18n.set_language(language)
        self.settings = replace(self.settings, language=self.i18n.language)
        with self.database.session() as connection:
            SettingsRepository(connection).set(LANGUAGE_SETTING, self.i18n.language)
        self.retranslate()

    def _build_layout(self) -> None:
        toolbar = QToolBar(self)
        toolbar.setObjectName("mainToolbar")
        toolbar.addWidget(self.settings_button)
        self.addToolBar(toolbar)

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self.index_panel)
        left_layout.addWidget(self.search_panel)
        left_layout.addWidget(self.results_panel, 1)

        self.content_tabs = QTabWidget(self)
        self.content_tabs.setObjectName("contentTabs")
        self.content_tabs.addTab(self.preview_panel, self.i18n.translate("preview.title"))
        self.content_tabs.addTab(self.editor_panel, self.i18n.translate("editor.title"))

        splitter = QSplitter(self)
        splitter.setObjectName("mainSplitter")
        splitter.addWidget(left_panel)
        splitter.addWidget(self.content_tabs)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar(self))
        self.resize(1100, 700)

    def _connect_signals(self) -> None:
        self.index_panel.select_folder_requested.connect(self._select_folder)
        self.index_panel.index_requested.connect(self._start_index)
        self.index_panel.cancel_requested.connect(self._cancel_active_worker)
        self.search_panel.search_requested.connect(self._start_search)
        self.results_panel.result_selected.connect(self.preview_panel.set_result)
        self.results_panel.result_selected.connect(self.editor_panel.set_result)
        self.editor_panel.saved.connect(lambda _path: self.statusBar().showMessage(self.i18n.translate("editor.saved")))
        self.editor_panel.saved.connect(lambda _path: self._refresh_index_state())
        self.editor_panel.save_failed.connect(self._show_error)
        self.settings_button.clicked.connect(self._open_settings)

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.i18n.translate("index.select_folder"))
        if folder:
            path = Path(folder)
            self.index_panel.set_folder(path)
            self._persist_index_folder(path)
            self._refresh_index_state()

    def _start_index(self, folder: Path) -> None:
        if self._active_thread is not None:
            return
        self._persist_index_folder(folder)
        worker = IndexWorker(self.database, folder, settings=self.settings)
        self._active_worker = worker
        self._set_busy(True)
        self._refresh_index_state(running=True)
        self.statusBar().showMessage(self.i18n.translate("status.indexing"))
        self._run_thread(worker.run, self._handle_index_result)

    def _start_search(self, query: str) -> None:
        if self._active_thread is not None or not query:
            return
        worker = SearchWorker(self.database, query, settings=self.settings)
        self._active_worker = worker
        self.search_panel.set_busy(True)
        self.statusBar().showMessage(self.i18n.translate("status.searching"))
        self._run_thread(worker.run, self._handle_search_result)

    def _run_thread(self, task: Callable[[], object], on_completed: Callable[[object], None]) -> None:
        thread = WorkerThread(task, self)
        self._active_thread = thread
        thread.completed.connect(on_completed)
        thread.failed.connect(self._handle_thread_error)
        thread.finished.connect(self._clear_thread)
        thread.start()

    def _cancel_active_worker(self) -> None:
        cancel = getattr(self._active_worker, "cancel", None)
        if callable(cancel):
            cancel()
            self.statusBar().showMessage(self.i18n.translate("status.cancelling"))

    def _handle_index_result(self, result: object) -> None:
        status = getattr(result, "status", "failed")
        if status == "completed":
            self._reindex_required = False
            summary = getattr(result, "payload", None)
            self.statusBar().showMessage(
                self.i18n.translate(
                    "status.index_completed",
                    indexed=getattr(summary, "files_indexed", 0),
                    skipped=getattr(summary, "files_skipped", 0),
                    failed=getattr(summary, "files_failed", 0),
                )
            )
        elif status == "cancelled":
            self.statusBar().showMessage(self.i18n.translate("status.cancelled"))
        else:
            self._show_error(getattr(result, "error", None) or self.i18n.translate("common.error"))
        self._refresh_index_state()

    def _handle_search_result(self, result: object) -> None:
        status = getattr(result, "status", "failed")
        if status == "completed":
            results = getattr(result, "payload", []) or []
            self.results_panel.set_results(results)
            self.statusBar().showMessage(self.i18n.translate("status.search_completed", count=len(results)))
        elif status == "cancelled":
            self.statusBar().showMessage(self.i18n.translate("status.cancelled"))
        else:
            self._show_error(getattr(result, "error", None) or self.i18n.translate("common.error"))

    def _handle_thread_error(self, message: str) -> None:
        self._show_error(message)

    def _clear_thread(self) -> None:
        if self._active_thread is not None:
            self._active_thread.deleteLater()
        self._active_thread = None
        self._active_worker = None
        self._set_busy(False)
        self._refresh_index_state()

    def _set_busy(self, busy: bool) -> None:
        self.index_panel.set_busy(busy)
        self.search_panel.set_busy(busy)

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage(message)
        QMessageBox.critical(self, self.i18n.translate("common.error"), message)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.i18n, self.database, self.paths, self)
        dialog.settings_saved.connect(self._apply_settings)
        dialog.exec()

    def _apply_settings(self, settings: object) -> None:
        if not isinstance(settings, ApplicationSettings):
            return
        old_settings = self.settings
        self.settings = settings
        self.editor_panel.update_settings(settings)
        if settings.index_folders:
            self.index_panel.set_folder(Path(settings.index_folders[0]))
        if _index_settings_changed(old_settings, settings) and self._has_indexed_documents():
            self._reindex_required = True
            message = self.i18n.translate("settings.saved_reindex_required")
        else:
            message = self.i18n.translate("settings.saved_applied")
        if self.i18n.language != settings.language:
            self.apply_language(settings.language)
        self._refresh_index_state()
        QMessageBox.information(self, self.i18n.translate("settings.title"), message)

    def _load_settings(self) -> ApplicationSettings:
        try:
            with self.database.session() as connection:
                settings = load_settings(SettingsRepository(connection), self.paths)
                if settings.index_folders:
                    return settings
                rows = connection.execute("SELECT path FROM index_folders WHERE enabled = 1 ORDER BY path_norm").fetchall()
            if rows:
                return replace(settings, index_folders=[str(row["path"]) for row in rows])
            return settings
        except Exception:
            return ApplicationSettings.defaults(self.paths)

    def _set_initial_folder(self) -> None:
        if self.settings.index_folders:
            self.index_panel.set_folder(Path(self.settings.index_folders[0]))

    def _persist_index_folder(self, folder: Path) -> None:
        folder_text = str(Path(folder))
        folders = list(self.settings.index_folders)
        if folder_text not in folders:
            folders.append(folder_text)
            self.settings = replace(self.settings, index_folders=folders)
            self.editor_panel.update_settings(self.settings)
        with self.database.session() as connection:
            save_settings(SettingsRepository(connection), self.settings)
            IndexFolderRepository(connection).add(folder_text, normalize_path(Path(folder_text)), enabled=True)

    def _refresh_index_state(self, *, running: bool = False) -> None:
        try:
            stats = self._load_index_stats()
        except Exception as exc:
            self.index_panel.set_index_state_text(str(exc))
            return
        if running or isinstance(self._active_worker, IndexWorker):
            status = self.i18n.translate("index.status.running")
        elif self._reindex_required:
            status = self.i18n.translate("index.status.reindex_required")
        elif stats["files"] > 0:
            status = self.i18n.translate("index.status.saved")
        else:
            status = self.i18n.translate("index.status.empty")
        self.index_panel.set_index_state_text(
            self.i18n.translate(
                "index.state_template",
                files=stats["files"],
                chunks=stats["chunks"],
                folders=stats["folders"],
                last=stats["last_indexed"],
                database=self.database.path,
                status=status,
            )
        )

    def _load_index_stats(self) -> dict[str, object]:
        with self.database.session() as connection:
            files = connection.execute(
                "SELECT count(*) FROM documents WHERE index_status = 'indexed'"
            ).fetchone()[0]
            chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
            folders = connection.execute("SELECT count(*) FROM index_folders WHERE enabled = 1").fetchone()[0]
            last_row = connection.execute(
                """
                SELECT COALESCE(finished_at, started_at) AS value
                FROM index_runs
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        return {
            "files": int(files),
            "chunks": int(chunks),
            "folders": int(folders),
            "last_indexed": str(last_row["value"]) if last_row and last_row["value"] else self.i18n.translate("index.never"),
        }

    def _has_indexed_documents(self) -> bool:
        with self.database.session() as connection:
            count = connection.execute("SELECT count(*) FROM documents WHERE index_status = 'indexed'").fetchone()[0]
        return int(count) > 0

    def _load_language(self) -> str:
        try:
            with self.database.session() as connection:
                return SettingsRepository(connection).get(LANGUAGE_SETTING, "ru") or "ru"
        except Exception:
            return "ru"


def _index_settings_changed(old: ApplicationSettings, new: ApplicationSettings) -> bool:
    return (
        old.index_folders != new.index_folders
        or old.excluded_folders != new.excluded_folders
        or old.max_index_file_size_mb != new.max_index_file_size_mb
        or old.enabled_extensions != new.enabled_extensions
    )
