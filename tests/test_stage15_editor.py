from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.editor.backup_cleanup_service import BackupCleanupService
from app.editor.backup_service import BackupService
from app.editor.safe_save_service import SafeSaveError, SafeSaveService
from app.editor.text_file_loader import TextFileLoader
from app.storage.database import Database
from app.workers.index_worker import IndexWorker
from app.workers.worker_state import WorkerResult

PYSIDE6_AVAILABLE = importlib.util.find_spec("PySide6") is not None

if PYSIDE6_AVAILABLE:
    from PySide6.QtWidgets import QApplication

    from app.i18n.i18n_service import load_i18n
    from app.models.content_match import ContentMatch
    from app.models.document import Document
    from app.models.search_result import SearchResult
    from app.ui.editor_panel import EditorPanel
    from app.utils.app_paths import AppPaths


class EditorServiceTests(unittest.TestCase):
    def test_loader_returns_editable_snapshot_for_supported_text_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "note.txt"
            path.write_bytes(b"first\r\nsecond")

            loaded = TextFileLoader().load(path)

            self.assertEqual(loaded.mode, "editable")
            self.assertEqual(loaded.text, "first\r\nsecond")
            self.assertIsNotNone(loaded.snapshot)
            self.assertEqual(loaded.snapshot.line_ending, "crlf")

    def test_loader_blocks_unsupported_and_too_large_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            unsupported = root / "note.bin"
            unsupported.write_text("text", encoding="utf-8")
            too_large = root / "large.txt"
            too_large.write_text("abcdef", encoding="utf-8")
            loader = TextFileLoader(max_size_bytes=3)

            self.assertEqual(loader.load(unsupported).mode, "blocked_unsupported")
            self.assertEqual(loader.load(too_large).mode, "blocked_too_large")

    def test_safe_save_creates_backup_preserves_line_endings_and_reindexes(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            note = root / "note.txt"
            note.write_bytes(b"old\r\nvalue")
            db = Database(root / "data" / "docufind.db")
            IndexWorker(db, root).run()
            loaded = TextFileLoader().load(note)
            self.assertIsNotNone(loaded.snapshot)

            result = SafeSaveService(
                backup_service=BackupService(root / "backups"),
                cleanup_service=BackupCleanupService(root / "backups"),
                database=db,
            ).save(loaded.snapshot, "new\nvalue")

            self.assertTrue(result.backup_path.exists())
            self.assertEqual(result.backup_path.read_bytes(), b"old\r\nvalue")
            self.assertEqual(note.read_bytes(), b"new\r\nvalue")
            self.assertEqual(result.reindex_result.status, "completed")
            with db.session() as connection:
                text = connection.execute("SELECT text FROM chunks WHERE text LIKE '%new%'").fetchone()["text"]
            self.assertEqual(text, "new\r\nvalue")

    def test_safe_save_blocks_external_changes(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            note = root / "note.txt"
            note.write_text("original", encoding="utf-8")
            loaded = TextFileLoader().load(note)
            self.assertIsNotNone(loaded.snapshot)
            time.sleep(0.01)
            note.write_text("external", encoding="utf-8")

            with self.assertRaises(SafeSaveError) as context:
                SafeSaveService(backup_service=BackupService(root / "backups")).save(loaded.snapshot, "mine")

            self.assertEqual(context.exception.mode, "blocked_changed_on_disk")
            self.assertEqual(note.read_text(encoding="utf-8"), "external")

    def test_backup_cleanup_removes_old_files_and_prunes_storage(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            backups = Path(temp_dir) / "backups"
            backups.mkdir()
            old = backups / "old.bak"
            old.write_bytes(b"old")
            recent = backups / "recent.bak"
            recent.write_bytes(b"12345")
            old_time = time.time() - 10 * 24 * 60 * 60
            os.utime(old, (old_time, old_time))

            summary = BackupCleanupService(backups, retention_days=1, max_storage_bytes=3).cleanup()

            self.assertGreaterEqual(summary.deleted_count, 1)
            self.assertFalse(old.exists())
            self.assertFalse(recent.exists())


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not available in this Python environment")
class EditorPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_editor_panel_loads_file_and_retranslates(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            note = root / "note.txt"
            note.write_text("hello", encoding="utf-8")
            paths = AppPaths(base_dir=root, portable=True)
            panel = EditorPanel(load_i18n("ru"), paths=paths)

            panel.load_path(note)
            self.assertEqual(panel.mode, "editable")
            self.assertEqual(panel.save_button.text(), "Сохранить")

            panel.i18n.set_language("en")
            panel.retranslate()
            self.assertEqual(panel.save_button.text(), "Save")
            panel.deleteLater()


    def test_editor_panel_navigates_between_result_mentions(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            note = root / "note.txt"
            text = "alpha\npersonal data\nomega personal"
            note.write_text(text, encoding="utf-8")
            first = text.index("personal")
            second = text.rindex("personal")
            paths = AppPaths(base_dir=root, portable=True)
            panel = EditorPanel(load_i18n("ru"), paths=paths)
            result = SearchResult(
                document=Document(
                    id=1,
                    path=str(note),
                    filename="note.txt",
                    extension=".txt",
                    size_bytes=note.stat().st_size,
                    modified_at="1970-01-01T00:00:00+00:00",
                ),
                content_matches=[
                    ContentMatch(1, 1, 2, 1, first, first + 8, "personal", "personal", "personal data", "exact"),
                    ContentMatch(1, 2, 3, 7, second, second + 8, "personal", "personal", "omega personal", "exact"),
                ],
                total_content_matches=2,
            )

            panel.set_result(result)
            self.assertEqual(panel.match_combo.count(), 2)
            self.assertEqual(panel.text_edit.textCursor().selectedText(), "personal")
            self.assertEqual(panel.text_edit.textCursor().selectionStart(), first)

            panel.next_match()

            self.assertEqual(panel.match_combo.currentIndex(), 1)
            self.assertEqual(panel.text_edit.textCursor().selectedText(), "personal")
            self.assertEqual(panel.text_edit.textCursor().selectionStart(), second)
            panel.deleteLater()

    def test_editor_panel_reports_partial_save_when_reindex_fails_or_is_cancelled(self) -> None:
        for status in ("failed", "cancelled"):
            with self.subTest(status=status), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
                root = Path(temp_dir)
                note = root / "note.txt"
                note.write_text("hello", encoding="utf-8")
                paths = AppPaths(base_dir=root, portable=True)
                panel = EditorPanel(load_i18n("en"), paths=paths)
                panel.load_path(note)
                saved = []
                partial = []
                panel.saved.connect(saved.append)
                panel.save_partial.connect(lambda path, result_status: partial.append((path, result_status)))

                fake_result = type("Result", (), {
                    "reindex_result": WorkerResult(status=status),
                })()
                with patch("app.ui.editor_panel.SafeSaveService") as service_type:
                    service_type.return_value.save.return_value = fake_result
                    panel.save()

                self.assertEqual(saved, [])
                self.assertEqual(partial, [(note, status)])
                self.assertEqual(note.read_text(encoding="utf-8"), "hello")
                panel.deleteLater()
if __name__ == "__main__":
    unittest.main()


