from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PYSIDE6_AVAILABLE = importlib.util.find_spec("PySide6") is not None

if PYSIDE6_AVAILABLE:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.i18n.i18n_service import load_i18n
    from app.indexer.index_service import IndexService
    from app.models.content_match import ContentMatch
    from app.models.document import Document
    from app.models.index_progress import IndexProgress
    from app.models.search_result import SearchResult
    from app.storage.database import Database
    from app.storage.settings_repository import SettingsRepository
    from app.workers.index_worker import IndexWorker
    from app.ui.main_window import MainWindow
    from app.ui.index_panel import IndexPanel
    from app.ui.results_panel import ResultsPanel
    from app.ui.search_panel import SearchPanel


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not available in this Python environment")
class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_search_panel_retranslates(self) -> None:
        i18n = load_i18n("ru")
        panel = SearchPanel(i18n)
        self.assertEqual(panel.search_button.text(), "Найти")

        i18n.set_language("en")
        panel.retranslate()

        self.assertEqual(panel.search_button.text(), "Search")
        panel.deleteLater()

    def test_main_window_switches_language_and_persists_setting(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            db = Database(Path(temp_dir) / "data" / "docufind.db")
            window = MainWindow(database=db, i18n=load_i18n("ru"))

            window.apply_language("en")

            self.assertEqual(window.search_panel.search_button.text(), "Search")
            with db.session() as connection:
                language = SettingsRepository(connection).get("language")
            self.assertEqual(language, "en")
            window.close()
            window.deleteLater()

    def test_results_render_search_result(self) -> None:
        i18n = load_i18n("en")
        results_panel = ResultsPanel(i18n)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "note.txt"
            path.write_text("personal data", encoding="utf-8")
            stat_result = path.stat()
            result = SearchResult(
                document=Document(
                    id=1,
                    path=str(path),
                    filename="note.txt",
                    extension=".txt",
                    size_bytes=stat_result.st_size,
                    modified_at="1970-01-01T00:00:00+00:00",
                ),
                content_matches=[
                    ContentMatch(
                        document_id=1,
                        chunk_id=1,
                        line_number=1,
                        column_number=1,
                        char_start=0,
                        char_end=8,
                        query_term="personal",
                        matched_text="personal",
                        snippet="personal data",
                        match_type="exact",
                    )
                ],
                total_content_matches=1,
            )

            results_panel.set_results([result])

            self.assertEqual(results_panel.list_widget.count(), 1)
            row = results_panel.list_widget.itemWidget(results_panel.list_widget.item(0))
            self.assertEqual(row.open_button.text(), "In Explorer")
        results_panel.deleteLater()

    def test_result_row_requests_open_in_explorer(self) -> None:
        i18n = load_i18n("en")
        panel = ResultsPanel(i18n)
        path = str(Path("C:/Docs/note.txt"))
        result = SearchResult(
            document=Document(
                id=1,
                path=path,
                filename="note.txt",
                extension=".txt",
                size_bytes=1,
                modified_at="1970-01-01T00:00:00+00:00",
            )
        )
        requested = []
        panel.open_in_explorer_requested.connect(requested.append)
        panel.set_results([result])

        row = panel.list_widget.itemWidget(panel.list_widget.item(0))
        row.open_button.click()

        self.assertEqual(requested, [path])
        panel.deleteLater()

    def test_main_window_opens_result_with_explorer_select(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            window = MainWindow(
                database=Database(Path(temp_dir) / "data" / "docufind.db"),
                i18n=load_i18n("en"),
            )
            path = str(Path(temp_dir) / "note.txt")

            with patch("app.ui.main_window.subprocess.Popen") as popen:
                window._open_result_in_explorer(path)

            popen.assert_called_once_with(["explorer.exe", "/select,", path])
            window.close()
            window.deleteLater()

    def test_index_progress_updates_main_window_labels(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            db = Database(Path(temp_dir) / "data" / "docufind.db")
            window = MainWindow(database=db, i18n=load_i18n("ru"))

            window.index_panel.set_progress(
                IndexProgress(
                    phase="indexing",
                    current_path=str(Path(temp_dir) / "report.txt"),
                    files_total=10,
                    files_processed=4,
                    files_indexed=2,
                    files_reindexed=1,
                    files_new=2,
                    files_changed=1,
                    files_unchanged=1,
                    files_skipped=0,
                    files_deleted=0,
                    files_restored=0,
                    files_failed=0,
                    percent=40,
                )
            )

            self.assertEqual(window.index_panel.progress_bar.value(), 40)
            self.assertIn("Обработано: 4 / 10", window.index_panel.progress_counts_label.text())
            self.assertIn("Проиндексировано: 3", window.index_panel.progress_counts_label.text())
            self.assertIn("report.txt", window.index_panel.progress_current_label.text())
            window.close()
            window.deleteLater()

    def test_index_progress_switches_from_scan_activity_to_determinate_batches(self) -> None:
        panel = IndexPanel(load_i18n("en"))
        panel.set_progress(IndexProgress(phase="scanning", message="250"))
        self.assertEqual((panel.progress_bar.minimum(), panel.progress_bar.maximum()), (0, 0))
        self.assertIn("250", panel.progress_counts_label.text())

        panel.set_progress(IndexProgress(phase="indexing", files_total=1000, files_processed=250, percent=23))
        self.assertEqual((panel.progress_bar.minimum(), panel.progress_bar.maximum()), (0, 100))
        self.assertEqual(panel.progress_bar.value(), 23)
        self.assertIn("250 / 1000", panel.progress_counts_label.text())
        panel.deleteLater()

    def test_index_cancel_request_is_visible_in_panel(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            db = Database(Path(temp_dir) / "data" / "docufind.db")
            window = MainWindow(database=db, i18n=load_i18n("ru"))
            window.index_panel.set_folder(Path(temp_dir))
            window._active_worker = IndexWorker(db, Path(temp_dir))
            window.index_panel.set_busy(True)

            window._cancel_active_worker()

            self.assertFalse(window.index_panel.cancel_button.isEnabled())
            self.assertEqual(window.index_panel.progress_bar.minimum(), 0)
            self.assertEqual(window.index_panel.progress_bar.maximum(), 0)
            self.assertIn("отмена запрошена", window.index_panel.progress_status_label.text())
            self.assertIn("отмена запрошена", window.index_panel.state_label.text())
            window.close()
            window.deleteLater()

    def test_clear_index_button_resets_index_state(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "note.txt").write_text("alpha", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            window = MainWindow(database=db, i18n=load_i18n("ru"))

            with patch("app.ui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                window._clear_index()
            self.assertFalse(window.index_panel.clear_index_button.isEnabled())
            _wait_for_window_worker(window)

            with db.session() as connection:
                documents = connection.execute("SELECT count(*) FROM documents").fetchone()[0]
                folders = connection.execute("SELECT count(*) FROM index_folders").fetchone()[0]
            self.assertEqual(documents, 0)
            self.assertEqual(folders, 1)
            self.assertIn("индекс пуст", window.index_panel.state_label.text())
            self.assertEqual(window.index_panel.progress_bar.value(), 0)
            window.close()
            window.deleteLater()

    def test_results_are_shown_in_own_tab_with_context(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "note.txt"
            path.write_text("personal data context", encoding="utf-8")
            stat_result = path.stat()
            db = Database(Path(temp_dir) / "data" / "docufind.db")
            window = MainWindow(database=db, i18n=load_i18n("ru"))
            result = SearchResult(
                document=Document(
                    id=1,
                    path=str(path),
                    filename="note.txt",
                    extension=".txt",
                    size_bytes=stat_result.st_size,
                    modified_at="1970-01-01T00:00:00+00:00",
                ),
                content_matches=[
                    ContentMatch(
                        document_id=1,
                        chunk_id=1,
                        line_number=1,
                        column_number=1,
                        char_start=0,
                        char_end=8,
                        query_term="personal",
                        matched_text="personal",
                        snippet="personal data context",
                        match_type="exact",
                    )
                ],
                total_content_matches=1,
            )

            window.results_panel.set_results([result])

            self.assertEqual(window.content_tabs.indexOf(window.results_panel), 0)
            self.assertEqual(window.content_tabs.tabText(0), "Результаты")
            self.assertEqual(window.content_tabs.tabText(1), "Редактор")
            row = window.results_panel.list_widget.itemWidget(window.results_panel.list_widget.item(0))
            self.assertIn("personal data context", row.summary_label.text())
            window.close()
            window.deleteLater()


def _wait_for_window_worker(window: MainWindow, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while window._active_thread is not None and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()
    if window._active_thread is not None:
        raise AssertionError("worker did not finish")


if __name__ == "__main__":
    unittest.main()

