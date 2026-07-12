from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.indexer.index_service import IndexService
from app.indexer.folder_scanner import FolderScanError
from app.storage.database import Database
from app.storage.index_reset_service import IndexResetCancelled, IndexResetService
from app.storage.settings_repository import SettingsRepository


class IndexServiceTests(unittest.TestCase):
    def test_large_folder_is_counted_then_streamed_in_batches(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            for index in range(205):
                (root / f"note-{index:03}.txt").write_text(f"value {index}", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            events = []

            summary = IndexService(db, batch_size=25).index_folder(root, progress_callback=events.append)

            self.assertEqual(summary.files_processed, 205)
            self.assertEqual(events[-1].percent, 100)
            indexing_percent = [event.percent for event in events if event.phase == "indexing"]
            self.assertTrue(all(percent is not None and 0 <= percent <= 95 for percent in indexing_percent))
            self.assertEqual([event.percent for event in events if event.phase == "marking_deleted"][-1], 96)
            self.assertEqual([event.percent for event in events if event.phase == "refreshing_caches"][-1], 98)

    def test_missing_root_does_not_mark_existing_documents_deleted(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            base = Path(temp_dir)
            root = base / "docs"
            root.mkdir()
            document = root / "note.txt"
            document.write_text("keep", encoding="utf-8")
            db = Database(base / "data" / "docufind.db")
            service = IndexService(db)
            service.index_folder(root)
            document.unlink()
            root.rmdir()

            with self.assertRaises(FolderScanError):
                service.index_folder(root)

            with db.session() as connection:
                row = connection.execute(
                    "SELECT index_status FROM documents WHERE path = ?",
                    (str(document),),
                ).fetchone()

            self.assertEqual(row["index_status"], "indexed")

    def test_index_folder_writes_documents_chunks_terms_lemmas_and_fts(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            document = root / "personal.md"
            document.write_text("персональными данными\nsecond line", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")

            summary = IndexService(db, batch_size=1).index_folder(root)

            self.assertEqual(summary.files_seen, 1)
            self.assertEqual(summary.files_indexed, 1)
            with db.session() as connection:
                doc_row = connection.execute("SELECT * FROM documents WHERE path = ?", (str(document),)).fetchone()
                chunk_count = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
                term_count = connection.execute("SELECT count(*) FROM indexed_terms WHERE source = 'content'").fetchone()[0]
                lemma_rows = connection.execute(
                    "SELECT lemma FROM indexed_lemmas WHERE source = 'content' ORDER BY lemma"
                ).fetchall()
                fts_row = connection.execute(
                    "SELECT document_id FROM chunks_fts WHERE chunks_fts MATCH ?",
                    ("персональными",),
                ).fetchone()

            self.assertIsNotNone(doc_row)
            self.assertEqual(doc_row["index_status"], "indexed")
            self.assertEqual(chunk_count, 1)
            self.assertGreaterEqual(term_count, 3)
            self.assertEqual([row["lemma"] for row in lemma_rows], ["данные", "персональный"])
            self.assertEqual(fts_row["document_id"], doc_row["id"])

    def test_index_folder_records_skipped_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            skipped = root / "image.png"
            skipped.write_bytes(b"png")
            db = Database(root / "data" / "docufind.db")

            summary = IndexService(db).index_folder(root)

            self.assertEqual(summary.files_seen, 1)
            self.assertEqual(summary.files_skipped, 1)
            with db.session() as connection:
                row = connection.execute("SELECT index_status FROM documents WHERE path = ?", (str(skipped),)).fetchone()
                chunk_count = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]

            self.assertEqual(row["index_status"], "skipped_unsupported_extension")
            self.assertEqual(chunk_count, 0)

    def test_reindex_replaces_old_chunks_and_terms(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            document = root / "note.txt"
            document.write_text("first term", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            service = IndexService(db)
            service.index_folder(root)

            document.write_text("second value", encoding="utf-8")
            service.index_folder(root)

            with db.session() as connection:
                chunks = connection.execute("SELECT text FROM chunks").fetchall()
                old_term = connection.execute(
                    "SELECT count(*) FROM indexed_terms WHERE normalized_term = 'first'"
                ).fetchone()[0]
                new_term = connection.execute(
                    "SELECT count(*) FROM indexed_terms WHERE normalized_term = 'second'"
                ).fetchone()[0]

            self.assertEqual([row["text"] for row in chunks], ["second value"])
            self.assertEqual(old_term, 0)
            self.assertEqual(new_term, 1)

    def test_unchanged_file_is_not_reindexed(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            document = root / "note.txt"
            document.write_text("stable term", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            service = IndexService(db)
            service.index_folder(root)
            with db.session() as connection:
                before = connection.execute(
                    "SELECT id, text FROM chunks WHERE document_id = (SELECT id FROM documents WHERE path = ?)",
                    (str(document),),
                ).fetchone()
                indexed_at = connection.execute("SELECT indexed_at FROM documents WHERE path = ?", (str(document),)).fetchone()[
                    "indexed_at"
                ]

            summary = service.index_folder(root)

            with db.session() as connection:
                after = connection.execute(
                    "SELECT id, text FROM chunks WHERE document_id = (SELECT id FROM documents WHERE path = ?)",
                    (str(document),),
                ).fetchone()
                after_indexed_at = connection.execute(
                    "SELECT indexed_at FROM documents WHERE path = ?",
                    (str(document),),
                ).fetchone()["indexed_at"]

            self.assertEqual(summary.files_processed, 1)
            self.assertEqual(summary.files_unchanged, 1)
            self.assertEqual(summary.files_indexed, 0)
            self.assertEqual(summary.files_reindexed, 0)
            self.assertEqual(before["id"], after["id"])
            self.assertEqual(before["text"], after["text"])
            self.assertEqual(indexed_at, after_indexed_at)

    def test_changed_file_is_reindexed_incrementally(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            document = root / "note.txt"
            document.write_text("old term", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            service = IndexService(db)
            service.index_folder(root)

            document.write_text("new term", encoding="utf-8")
            summary = service.index_folder(root)

            self.assertEqual(summary.files_changed, 1)
            self.assertEqual(summary.files_reindexed, 1)
            with db.session() as connection:
                old_term = connection.execute(
                    "SELECT count(*) FROM indexed_terms WHERE normalized_term = 'old'"
                ).fetchone()[0]
                new_term = connection.execute(
                    "SELECT count(*) FROM indexed_terms WHERE normalized_term = 'new'"
                ).fetchone()[0]
            self.assertEqual(old_term, 0)
            self.assertEqual(new_term, 1)

    def test_progress_callback_reports_counts(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "a.txt").write_text("alpha", encoding="utf-8")
            (root / "b.txt").write_text("beta", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            events = []

            summary = IndexService(db).index_folder(root, progress_callback=events.append)

            self.assertGreater(len(events), 2)
            self.assertIn("scanning", [event.phase for event in events])
            self.assertIn("indexing", [event.phase for event in events])
            self.assertEqual(events[-1].phase, "completed")
            self.assertEqual(events[-1].percent, 100)
            self.assertEqual(events[-1].files_total, 2)
            self.assertEqual(events[-1].files_processed, 2)
            self.assertEqual(events[-1].files_indexed, summary.files_indexed)
            self.assertEqual(events[-1].files_reindexed, summary.files_reindexed)
            self.assertTrue(all(event.percent != 100 for event in events[:-1]))

    def test_cancel_after_files_before_finalization_does_not_emit_100_percent(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "a.txt").write_text("alpha", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            events = []

            def cancel_after_processing() -> bool:
                return any(event.files_processed >= 1 for event in events)

            summary = IndexService(db).index_folder(
                root,
                progress_callback=events.append,
                cancel_checker=cancel_after_processing,
            )

            self.assertEqual(summary.files_processed, 1)
            self.assertEqual(events[-1].phase, "cancelled")
            self.assertIsNotNone(events[-1].percent)
            self.assertLess(events[-1].percent, 100)

    def test_index_errors_are_recorded_for_extraction_failure(self) -> None:
        class FailingExtractor:
            def extract(self, path: Path):
                raise RuntimeError("boom")

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            document = root / "bad.txt"
            document.write_text("bad", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")

            summary = IndexService(db, text_extractor=FailingExtractor()).index_folder(root)

            self.assertEqual(summary.files_failed, 1)
            with db.session() as connection:
                doc_status = connection.execute("SELECT index_status FROM documents WHERE path = ?", (str(document),)).fetchone()
                errors = connection.execute("SELECT error_type, error_message FROM index_errors").fetchall()

            self.assertEqual(doc_status["index_status"], "error_extract")
            self.assertEqual(errors[0]["error_type"], "error_extract")
            self.assertIn("boom", errors[0]["error_message"])

    def test_clear_index_removes_payload_but_keeps_folders_and_settings(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "note.txt").write_text("alpha", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            with db.session() as connection:
                SettingsRepository(connection).set("language", "ru")

            summary = IndexResetService(db).clear_index()

            self.assertEqual(summary.documents_deleted, 1)
            with db.session() as connection:
                documents = connection.execute("SELECT count(*) FROM documents").fetchone()[0]
                chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
                chunks_fts = connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
                terms = connection.execute("SELECT count(*) FROM indexed_terms").fetchone()[0]
                lemmas = connection.execute("SELECT count(*) FROM indexed_lemmas").fetchone()[0]
                runs = connection.execute("SELECT count(*) FROM index_runs").fetchone()[0]
                folders = connection.execute("SELECT count(*) FROM index_folders").fetchone()[0]
                language = SettingsRepository(connection).get("language")

            self.assertEqual(documents, 0)
            self.assertEqual(chunks, 0)
            self.assertEqual(chunks_fts, 0)
            self.assertEqual(terms, 0)
            self.assertEqual(lemmas, 0)
            self.assertEqual(runs, 0)
            self.assertEqual(folders, 1)
            self.assertEqual(language, "ru")

    def test_clear_index_reports_progress(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "note.txt").write_text("alpha", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            events = []

            IndexResetService(db).clear_index(progress_callback=events.append)

            self.assertGreater(len(events), 1)
            self.assertEqual(events[0].phase, "clearing_index")
            self.assertEqual(events[-1].phase, "clear_completed")
            self.assertEqual(events[-1].percent, 100)

    def test_clear_index_cancel_rolls_back_partial_delete(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "note.txt").write_text("alpha", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            checks = {"count": 0}

            def cancel_after_first_table() -> bool:
                checks["count"] += 1
                return checks["count"] > 1

            with self.assertRaises(IndexResetCancelled):
                IndexResetService(db).clear_index(cancel_checker=cancel_after_first_table)

            with db.session() as connection:
                documents = connection.execute("SELECT count(*) FROM documents").fetchone()[0]
                chunks_fts = connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
            self.assertEqual(documents, 1)
            self.assertEqual(chunks_fts, 1)


if __name__ == "__main__":
    unittest.main()


