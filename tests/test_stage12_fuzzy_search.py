from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.indexer.index_service import IndexService
from app.search.fuzzy_search import FuzzySearch
from app.search.query_parser import QueryParser
from app.search.search_service import SearchService
from app.storage.database import Database


class FuzzySearchTests(unittest.TestCase):
    def test_fuzzy_search_finds_filename_typo(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            target = root / "personal_report.md"
            target.write_text("plain text", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)

            with db.session() as connection:
                results = SearchService().search(connection, "perssonal")

            self.assertEqual(results[0].document.path, str(target))
            self.assertEqual(results[0].file_matches[0].match_type, "fuzzy")
            self.assertGreaterEqual(results[0].file_matches[0].similarity, 78)

    def test_fuzzy_search_finds_content_typo(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            target = root / "note.txt"
            target.write_text("персональные данные", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)

            with db.session() as connection:
                results = SearchService().search(connection, "персональныи")

            self.assertEqual(results[0].document.path, str(target))
            fuzzy_matches = [match for match in results[0].content_matches if match.match_type == "fuzzy"]
            self.assertTrue(fuzzy_matches)
            self.assertGreaterEqual(fuzzy_matches[0].similarity, 88)

    def test_fuzzy_candidates_are_filtered_by_first_char_and_length(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "alpha.txt").write_text("contract", encoding="utf-8")
            (root / "beta.txt").write_text("xontract", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            query = QueryParser().parse("conract")

            with db.session() as connection:
                _, content = FuzzySearch(content_threshold=70).search(connection, query)

            matched = [match.matched_text for matches in content.values() for match in matches]
            self.assertIn("contract", matched)
            self.assertNotIn("xontract", matched)

    def test_fuzzy_variant_limit_is_applied(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            for index, word in enumerate(["contract", "contracts", "contact", "contrast"]):
                (root / f"{index}.txt").write_text(word, encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            query = QueryParser().parse("contrct")

            with db.session() as connection:
                fuzzy = FuzzySearch(content_threshold=60, max_variants_per_term=1)
                candidates = fuzzy._find_candidates(connection, "contrct", "content", 60)

            self.assertEqual(len(candidates), 1)

    def test_content_threshold_blocks_weak_match(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "note.txt").write_text("contract", encoding="utf-8")
            db = Database(root / "data" / "docufind.db")
            IndexService(db).index_folder(root)
            query = QueryParser().parse("contact")

            with db.session() as connection:
                _, content = FuzzySearch(content_threshold=99).search(connection, query)

            self.assertEqual(content, {})


if __name__ == "__main__":
    unittest.main()

