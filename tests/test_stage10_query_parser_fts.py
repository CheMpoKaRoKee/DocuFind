from __future__ import annotations

import unittest

from app.search.fts_query_builder import FtsQueryBuilder
from app.search.query_parser import QueryParser


class QueryParserFtsTests(unittest.TestCase):
    def test_parse_words(self) -> None:
        query = QueryParser().parse("персональные данные")

        self.assertEqual([group.original for group in query.groups], ["персональные", "данные"])
        self.assertEqual([group.variants[0] for group in query.groups], ["персональные", "данные"])

    def test_parse_phrase(self) -> None:
        query = QueryParser().parse('"персональные данные"')

        self.assertEqual(len(query.groups), 1)
        self.assertTrue(query.groups[0].is_phrase)
        self.assertEqual(query.groups[0].variants, ["персональные данные"])

    def test_parse_ext_and_folder(self) -> None:
        query = QueryParser().parse('ext:MD folder:"D:\\Docs" договор')

        self.assertEqual(query.extension, "md")
        self.assertEqual(query.folder, "D:\\Docs")
        self.assertEqual(query.groups[0].original, "договор")

    def test_fts_builder_quotes_words_and_requires_groups(self) -> None:
        query = QueryParser().parse("персональные данные")

        fts = FtsQueryBuilder().build(query)

        self.assertIn('"персональные"', fts)
        self.assertIn("AND", fts)
        self.assertIn('"данные"', fts)

    def test_fts_builder_builds_phrase(self) -> None:
        query = QueryParser().parse('"персональные данные"')

        self.assertEqual(FtsQueryBuilder().build(query), '"персональные данные"')

    def test_bad_query_does_not_pass_raw_match_syntax(self) -> None:
        raw = '"; DROP TABLE documents; -- OR персональные* NEAR данные'
        query = QueryParser().parse(raw)

        fts = FtsQueryBuilder().build(query)

        self.assertIsNotNone(fts)
        self.assertNotIn("DROP", fts)
        self.assertNotIn("--", fts)
        self.assertNotIn("NEAR", fts)
        self.assertNotIn("*", fts)

    def test_empty_or_punctuation_query_has_no_match_query(self) -> None:
        query = QueryParser().parse('"; -- *')

        self.assertIsNone(FtsQueryBuilder().build(query))

    def test_parser_adds_russian_lemmas(self) -> None:
        query = QueryParser().parse("персональными данными")

        lemmas = [lemma for group in query.groups for lemma in group.lemmas]

        self.assertIn("персональный", lemmas)
        self.assertIn("данные", lemmas)


if __name__ == "__main__":
    unittest.main()

