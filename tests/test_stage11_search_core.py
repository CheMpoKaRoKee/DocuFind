from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.indexer.index_service import IndexService
from app.search.search_service import SearchService
from app.storage.database import Database


class SearchCoreTests(unittest.TestCase):
    def test_match_column_is_absolute_when_chunk_starts_inside_long_line(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            target = root / "long.txt"
            target.write_text("a" * 10_000 + "needle", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)

            with db.session() as connection:
                results = SearchService().search(connection, "needle")

            match = results[0].content_matches[0]
            self.assertEqual(match.line_number, 1)
            self.assertEqual(match.column_number, 10_001)
            self.assertEqual(match.char_start, 10_000)

    def test_search_finds_filename_path_and_content(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            target = docs / "personal_notes.md"
            target.write_text("first line\nперсональными данными тут\n", encoding="utf-8", newline="\n")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)

            with db.session() as connection:
                filename_results = SearchService().search(connection, "personal")
                content_results = SearchService().search(connection, "персональными")
                lemma_results = SearchService().search(connection, "персональные данные")
                path_results = SearchService().search(connection, "docs")

            self.assertEqual(filename_results[0].document.filename, "personal_notes.md")
            self.assertTrue(filename_results[0].file_matches)
            self.assertEqual(content_results[0].content_matches[0].line_number, 2)
            self.assertEqual(content_results[0].content_matches[0].column_number, 1)
            self.assertEqual(lemma_results[0].document.path, str(target))
            self.assertEqual(path_results[0].document.path, str(target))

    def test_search_applies_ext_and_folder_filters(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            other = root / "other"
            docs.mkdir()
            other.mkdir()
            md_file = docs / "hit.md"
            txt_file = other / "hit.txt"
            md_file.write_text("contract alpha", encoding="utf-8")
            txt_file.write_text("contract alpha", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)

            with db.session() as connection:
                ext_results = SearchService().search(connection, "contract ext:md")
                folder_results = SearchService().search(connection, f'contract folder:"{docs}"')

            self.assertEqual([result.document.path for result in ext_results], [str(md_file)])
            self.assertEqual([result.document.path for result in folder_results], [str(md_file)])

    def test_multiterm_search_requires_every_term_across_allowed_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            filename_only = root / "alpha.txt"
            filename_only.write_text("unrelated", encoding="utf-8")
            cross_field = root / "alpha_beta.txt"
            cross_field.write_text("unrelated", encoding="utf-8")
            content_match = root / "content.txt"
            content_match.write_text("alpha beta", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)

            with db.session() as connection:
                results = SearchService().search(connection, "alpha beta")

            self.assertEqual([result.document.path for result in results], [str(cross_field), str(content_match)])

    def test_exact_phrase_does_not_fall_back_to_unordered_lemmas(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            exact = root / "exact.txt"
            exact.write_text("personal data", encoding="utf-8")
            unordered = root / "unordered.txt"
            unordered.write_text("data personal", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)

            with db.session() as connection:
                results = SearchService().search(connection, '"personal data"')

            self.assertEqual([result.document.path for result in results], [str(exact)])

    def test_search_marks_has_more_content_matches(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            target = root / "many.txt"
            target.write_text("alpha\nalpha\nalpha\n", encoding="utf-8", newline="\n")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)

            service = SearchService(max_matches_per_document=2)
            with db.session() as connection:
                results = service.search(connection, "alpha")

            self.assertEqual(results[0].total_content_matches, 3)
            self.assertTrue(results[0].has_more_content_matches)
            self.assertEqual(len(results[0].content_matches), 2)

    def test_freshness_guard_hides_changed_stale_result_and_queues_reindex(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            target = root / "note.txt"
            target.write_text("old term", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            target.write_text("new term", encoding="utf-8")

            with db.session() as connection:
                results = SearchService().search(connection, "old")
                doc = connection.execute("SELECT index_status, state_reason FROM documents WHERE path = ?", (str(target),)).fetchone()
                queue_count = connection.execute("SELECT count(*) FROM reindex_queue WHERE status = 'pending'").fetchone()[0]

            self.assertEqual(results, [])
            self.assertEqual(doc["index_status"], "queued_reindex")
            self.assertEqual(doc["state_reason"], "search_stale_detected")
            self.assertEqual(queue_count, 1)

    def test_freshness_guard_hides_missing_result_and_retains_payload(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            target = root / "note.txt"
            target.write_text("old term", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            target.unlink()

            with db.session() as connection:
                results = SearchService().search(connection, "old")
                doc = connection.execute(
                    "SELECT index_status, payload_retained, state_reason FROM documents WHERE path = ?",
                    (str(target),),
                ).fetchone()
                chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]

            self.assertEqual(results, [])
            self.assertEqual(doc["index_status"], "deleted_retained")
            self.assertEqual(doc["payload_retained"], 1)
            self.assertEqual(doc["state_reason"], "search_missing")
            self.assertEqual(chunks, 1)


if __name__ == "__main__":
    unittest.main()
