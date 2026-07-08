from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.storage.database import Database
from app.workers.index_worker import IndexWorker
from app.workers.reindex_worker import ReindexWorker
from app.workers.search_worker import SearchWorker
from app.workers.worker_state import WorkerState


class WorkerTests(unittest.TestCase):
    def test_index_worker_indexes_with_own_connection(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "note.txt").write_text("персональные данные", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")

            result = IndexWorker(db, root).run()

            self.assertEqual(result.status, "completed")
            with db.session() as connection:
                count = connection.execute("SELECT count(*) FROM documents WHERE index_status = 'indexed'").fetchone()[0]
            self.assertEqual(count, 1)

    def test_search_worker_uses_own_connection(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "note.txt").write_text("персональные данные", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexWorker(db, root).run()

            result = SearchWorker(db, "персональные").run()

            self.assertEqual(result.status, "completed")
            self.assertEqual(len(result.payload), 1)

    def test_reindex_worker_updates_changed_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            note = root / "note.txt"
            note.write_text("old", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexWorker(db, root).run()

            note.write_text("new value", encoding="utf-8")
            result = ReindexWorker(db, note).run()

            self.assertEqual(result.status, "completed")
            with db.session() as connection:
                text = connection.execute("SELECT text FROM chunks").fetchone()["text"]
            self.assertEqual(text, "new value")


    def test_reindex_worker_only_updates_target_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            target = root / "target.txt"
            sibling = root / "sibling.txt"
            target.write_text("old target", encoding="utf-8")
            sibling.write_text("old sibling", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexWorker(db, root).run()

            target.write_text("new target", encoding="utf-8")
            sibling.unlink()
            result = ReindexWorker(db, target).run()

            self.assertEqual(result.status, "completed")
            with db.session() as connection:
                target_row = connection.execute(
                    "SELECT index_status FROM documents WHERE path = ?",
                    (str(target),),
                ).fetchone()
                sibling_row = connection.execute(
                    "SELECT index_status FROM documents WHERE path = ?",
                    (str(sibling),),
                ).fetchone()
                target_text = connection.execute(
                    """
                    SELECT chunks.text
                    FROM chunks
                    JOIN documents ON documents.id = chunks.document_id
                    WHERE documents.path = ?
                    """,
                    (str(target),),
                ).fetchone()["text"]

            self.assertEqual(target_row["index_status"], "indexed")
            self.assertEqual(sibling_row["index_status"], "indexed")
            self.assertEqual(target_text, "new target")
    def test_cancel_before_run_returns_cancelled(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            db = Database(root / "data" / "docufind.db")
            state = WorkerState()
            state.cancel()

            result = IndexWorker(db, root, state=state).run()

            self.assertEqual(result.status, "cancelled")


if __name__ == "__main__":
    unittest.main()


