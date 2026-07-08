from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.indexer.index_service import IndexService
from app.search.search_service import SearchService
from app.storage.database import Database


class SearchCoreTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

