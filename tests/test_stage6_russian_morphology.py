from __future__ import annotations

import unittest
import importlib.util

from app.russian.lemma_index_builder import LemmaIndexBuilder
from app.russian.lemma_query_expander import LemmaQueryExpander
from app.russian.lemmatizer import Lemmatizer
from app.russian.morphology_analyzer import MorphologyAnalyzer
from app.russian.russian_tokenizer import RussianTokenizer


class RussianMorphologyTests(unittest.TestCase):
    def test_tokenizer_extracts_russian_tokens(self) -> None:
        tokens = RussianTokenizer().russian_tokens("Final: Персональные данные v2")

        self.assertEqual(tokens, ["персональные", "данные"])

    def test_lemmatizer_handles_required_forms(self) -> None:
        lemmatizer = Lemmatizer()

        self.assertEqual(lemmatizer.lemmatize_text("персональные данные"), ["персональный", "данные"])
        self.assertEqual(lemmatizer.lemmatize_text("персональных данных"), ["персональный", "данные"])
        self.assertEqual(lemmatizer.lemmatize_text("персональными данными"), ["персональный", "данные"])
        self.assertEqual(lemmatizer.lemmatize_text("персональным данным"), ["персональный", "данные"])


    @unittest.skipUnless(importlib.util.find_spec("pymorphy3") is not None, "pymorphy3 is not available")
    def test_morphology_uses_pymorphy3_when_available(self) -> None:
        analyzer = MorphologyAnalyzer()

        self.assertEqual(analyzer.source, "pymorphy3")
        self.assertEqual(analyzer.normalize("персональными").lemma, "персональный")
    def test_query_expander_matches_required_document_forms(self) -> None:
        query_lemmas = set(LemmaQueryExpander().expand("персональные данные"))
        documents = [
            "персональных данных",
            "персональными данными",
            "персональным данным",
        ]

        for document in documents:
            document_lemmas = set(Lemmatizer().lemmatize_text(document))
            self.assertTrue(query_lemmas.issubset(document_lemmas))

    def test_lemma_index_builder_counts_lemmas(self) -> None:
        lemmas = LemmaIndexBuilder().collect("персональные данные персональных данных", "content")

        self.assertIn(("персональный", "content", 2), lemmas)
        self.assertIn(("данные", "content", 2), lemmas)


if __name__ == "__main__":
    unittest.main()


