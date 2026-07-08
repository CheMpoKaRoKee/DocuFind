from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.indexer.index_service import IndexService
from app.storage.database import Database


class IndexServiceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()


