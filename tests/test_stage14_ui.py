from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PYSIDE6_AVAILABLE = importlib.util.find_spec("PySide6") is not None

if PYSIDE6_AVAILABLE:
    from PySide6.QtWidgets import QApplication

    from app.i18n.i18n_service import load_i18n
    from app.models.content_match import ContentMatch
    from app.models.document import Document
    from app.models.search_result import SearchResult
    from app.storage.database import Database
    from app.storage.settings_repository import SettingsRepository
    from app.ui.main_window import MainWindow
    from app.ui.preview_panel import PreviewPanel
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

    def test_results_and_preview_render_search_result(self) -> None:
        i18n = load_i18n("en")
        results_panel = ResultsPanel(i18n)
        preview_panel = PreviewPanel(i18n)
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
            preview_panel.set_result(result)

            self.assertEqual(results_panel.list_widget.count(), 1)
            self.assertIn("Line 1", preview_panel.meta_label.text())
            self.assertFalse(preview_panel.stale_label.isHidden())
        results_panel.deleteLater()
        preview_panel.deleteLater()


if __name__ == "__main__":
    unittest.main()

