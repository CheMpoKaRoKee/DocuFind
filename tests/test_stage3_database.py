from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.storage.chunk_repository import ChunkRepository
from app.storage.database import Database
from app.storage.document_lemma_repository import DocumentLemmaRepository
from app.storage.document_repository import DocumentRepository
from app.storage.document_term_repository import DocumentTermRepository
from app.storage.fts_repository import FtsRepository
from app.storage.index_folder_repository import IndexFolderRepository
from app.storage.lemma_repository import LemmaRepository
from app.storage.settings_repository import SettingsRepository
from app.storage.term_repository import TermRepository


class DatabaseTests(unittest.TestCase):
    def test_initialize_creates_schema_indexes_and_fts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(Path(temp_dir) / "docufind.db")
            db.initialize()
            with db.session() as connection:
                names = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
                    )
                }

            self.assertIn("documents", names)
            self.assertIn("chunks", names)
            self.assertIn("documents_fts", names)
            self.assertIn("chunks_fts", names)
            self.assertIn("idx_documents_folder_id", names)
            self.assertIn("idx_indexed_terms_fuzzy", names)

    def test_pragmas_are_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(Path(temp_dir) / "docufind.db")
            with db.session() as connection:
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
                foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
                busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

            self.assertEqual(journal_mode, "wal")
            self.assertEqual(synchronous, 1)
            self.assertEqual(foreign_keys, 1)
            self.assertEqual(busy_timeout, 5000)

    def test_settings_repository_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(Path(temp_dir) / "docufind.db")
            db.initialize()
            with db.session() as connection:
                settings = SettingsRepository(connection)
                settings.set("language", "ru")

            with db.session() as connection:
                settings = SettingsRepository(connection)
                self.assertEqual(settings.get("language"), "ru")
                self.assertEqual(settings.all(), {"language": "ru"})

    def test_repositories_write_index_records_and_fts(self) -> None:
        now = datetime.now(UTC).isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(Path(temp_dir) / "docufind.db")
            db.initialize()
            with db.session() as connection:
                folder_id = IndexFolderRepository(connection).add("D:/Docs", "d docs")
                document_id = DocumentRepository(connection).upsert(
                    {
                        "folder_id": folder_id,
                        "path": "D:/Docs/personal.md",
                        "path_norm": "d docs personal md",
                        "filename": "personal.md",
                        "filename_norm": "personal md",
                        "extension": ".md",
                        "extension_norm": "md",
                        "size_bytes": 42,
                        "modified_at": now,
                        "modified_ns": 100,
                        "indexed_at": now,
                        "last_seen_at": now,
                        "content_hash": "hash",
                        "encoding": "utf-8",
                        "line_ending": "lf",
                        "is_hidden": 0,
                        "is_system": 0,
                        "is_readonly": 0,
                        "index_status": "indexed",
                        "error_message": None,
                    }
                )
                chunk_ids = ChunkRepository(connection).replace_for_document(
                    document_id,
                    [
                        {
                            "chunk_index": 0,
                            "text": "персональные данные",
                            "line_start": 1,
                            "line_end": 1,
                            "char_start": 0,
                            "char_end": 19,
                        }
                    ],
                )
                DocumentTermRepository(connection).replace_for_document(
                    document_id,
                    [("персональные", "content", 1), ("данные", "content", 1)],
                )
                DocumentLemmaRepository(connection).replace_for_document(
                    document_id,
                    [("персональный", "content", 1), ("данные", "content", 1)],
                )
                TermRepository(connection).rebuild()
                LemmaRepository(connection).rebuild()
                fts = FtsRepository(connection)
                fts.replace_document(document_id, "personal md", "d docs personal md")
                fts.replace_chunks(document_id, [(chunk_ids[0], "персональные данные")])

            with db.session() as connection:
                term_count = connection.execute("SELECT count(*) FROM indexed_terms").fetchone()[0]
                lemma_count = connection.execute("SELECT count(*) FROM indexed_lemmas").fetchone()[0]
                fts_row = connection.execute(
                    "SELECT document_id FROM chunks_fts WHERE chunks_fts MATCH ?",
                    ("персональные",),
                ).fetchone()

            self.assertEqual(term_count, 2)
            self.assertEqual(lemma_count, 2)
            self.assertEqual(fts_row["document_id"], document_id)


if __name__ == "__main__":
    unittest.main()
