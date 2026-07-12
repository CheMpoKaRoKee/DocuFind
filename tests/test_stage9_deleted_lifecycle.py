from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.indexer.index_service import IndexService
from app.indexer.deleted_file_detector import _canonical_path, _is_under
from app.storage.database import Database


class DeletedLifecycleTests(unittest.TestCase):
    def test_inaccessible_subtree_protects_nested_documents(self) -> None:
        subtree = _canonical_path(Path("C:/Docs/Locked"))

        self.assertTrue(_is_under(_canonical_path(Path("c:/docs/locked/nested/note.txt")), subtree))
        self.assertFalse(_is_under(_canonical_path(Path("c:/docs/locked-other/note.txt")), subtree))

    def test_missing_file_is_marked_deleted_retained_and_payload_is_kept(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            document = root / "gone.txt"
            document.write_text("персональные данные", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            service = IndexService(db)

            first = service.index_folder(root)
            document.unlink()
            second = service.index_folder(root)

            self.assertEqual(first.files_indexed, 1)
            self.assertEqual(second.files_seen, 0)
            with db.session() as connection:
                doc = connection.execute("SELECT index_status, payload_retained FROM documents WHERE path = ?", (str(document),)).fetchone()
                chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
                terms = connection.execute("SELECT count(*) FROM document_terms").fetchone()[0]
                lemmas = connection.execute("SELECT count(*) FROM document_lemmas").fetchone()[0]
                chunks_fts = connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
                runs = connection.execute("SELECT status, files_seen, files_indexed FROM index_runs ORDER BY id").fetchall()

            self.assertEqual(second.files_deleted, 1)
            self.assertEqual(doc["index_status"], "deleted_retained")
            self.assertEqual(doc["payload_retained"], 1)
            self.assertEqual(chunks, 1)
            self.assertGreater(terms, 0)
            self.assertGreater(lemmas, 0)
            self.assertEqual(chunks_fts, 1)
            self.assertEqual([row["status"] for row in runs], ["completed", "completed"])
            self.assertEqual(runs[0]["files_seen"], 1)
            self.assertEqual(runs[0]["files_indexed"], 1)
            self.assertEqual(runs[1]["files_seen"], 0)

    def test_restored_unchanged_file_returns_without_reindex(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            document = root / "restored.txt"
            document.write_text("same content", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            service = IndexService(db)
            service.index_folder(root)
            with db.session() as connection:
                chunk_before = connection.execute("SELECT id FROM chunks").fetchone()["id"]

            content = document.read_text(encoding="utf-8")
            document.unlink()
            service.index_folder(root)
            document.write_text(content, encoding="utf-8")
            summary = service.index_folder(root)

            with db.session() as connection:
                doc = connection.execute("SELECT index_status FROM documents WHERE path = ?", (str(document),)).fetchone()
                chunk_after = connection.execute("SELECT id FROM chunks").fetchone()["id"]

            self.assertEqual(summary.files_restored, 1)
            self.assertEqual(summary.files_reindexed, 0)
            self.assertEqual(doc["index_status"], "indexed")
            self.assertEqual(chunk_before, chunk_after)

    def test_restored_changed_file_is_reindexed(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            document = root / "restored.txt"
            document.write_text("old", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            service = IndexService(db)
            service.index_folder(root)
            document.unlink()
            service.index_folder(root)
            document.write_text("new", encoding="utf-8")

            summary = service.index_folder(root)

            with db.session() as connection:
                doc = connection.execute("SELECT index_status FROM documents WHERE path = ?", (str(document),)).fetchone()
                old_term = connection.execute(
                    "SELECT count(*) FROM indexed_terms WHERE normalized_term = 'old'"
                ).fetchone()[0]
                new_term = connection.execute(
                    "SELECT count(*) FROM indexed_terms WHERE normalized_term = 'new'"
                ).fetchone()[0]

            self.assertEqual(summary.files_restored, 1)
            self.assertEqual(summary.files_reindexed, 1)
            self.assertEqual(doc["index_status"], "indexed")
            self.assertEqual(old_term, 0)
            self.assertEqual(new_term, 1)

    def test_index_run_records_failures(self) -> None:
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
                run = connection.execute("SELECT status, files_seen, files_failed FROM index_runs").fetchone()

            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["files_seen"], 1)
            self.assertEqual(run["files_failed"], 1)


if __name__ == "__main__":
    unittest.main()
