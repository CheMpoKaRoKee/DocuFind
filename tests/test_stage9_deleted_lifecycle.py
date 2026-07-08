from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.indexer.index_service import IndexService
from app.storage.database import Database


class DeletedLifecycleTests(unittest.TestCase):
    def test_missing_file_is_marked_deleted_and_index_payload_is_removed(self) -> None:
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
                doc = connection.execute("SELECT index_status FROM documents WHERE path = ?", (str(document),)).fetchone()
                chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
                terms = connection.execute("SELECT count(*) FROM document_terms").fetchone()[0]
                lemmas = connection.execute("SELECT count(*) FROM document_lemmas").fetchone()[0]
                chunks_fts = connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
                runs = connection.execute("SELECT status, files_seen, files_indexed FROM index_runs ORDER BY id").fetchall()

            self.assertEqual(doc["index_status"], "deleted")
            self.assertEqual(chunks, 0)
            self.assertEqual(terms, 0)
            self.assertEqual(lemmas, 0)
            self.assertEqual(chunks_fts, 0)
            self.assertEqual([row["status"] for row in runs], ["completed", "completed"])
            self.assertEqual(runs[0]["files_seen"], 1)
            self.assertEqual(runs[0]["files_indexed"], 1)
            self.assertEqual(runs[1]["files_seen"], 0)

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

