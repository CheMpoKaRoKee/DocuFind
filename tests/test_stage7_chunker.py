from __future__ import annotations

import unittest

from app.indexer.chunker import Chunker


class ChunkerTests(unittest.TestCase):
    def test_chunks_by_lines_with_character_limit(self) -> None:
        chunks = Chunker(chunk_size=5, overlap=0).chunk("a\nbb\nccc\n")

        self.assertEqual([chunk.text for chunk in chunks], ["a\nbb\n", "ccc\n"])
        self.assertEqual((chunks[0].line_start, chunks[0].line_end), (1, 2))
        self.assertEqual((chunks[1].line_start, chunks[1].line_end), (3, 3))

    def test_chunks_keep_char_ranges(self) -> None:
        chunks = Chunker(chunk_size=5, overlap=0).chunk("a\nbb\nccc\n")

        self.assertEqual((chunks[0].char_start, chunks[0].char_end), (0, 5))
        self.assertEqual((chunks[1].char_start, chunks[1].char_end), (5, 9))

    def test_overlap_is_added_to_next_chunk(self) -> None:
        chunks = Chunker(chunk_size=10, overlap=3).chunk("abcd\nefgh\nijkl\n")

        self.assertEqual(chunks[0].text, "abcd\nefgh\n")
        self.assertTrue(chunks[1].text.startswith("gh\n"))
        self.assertEqual(chunks[1].char_start, 7)

    def test_very_long_line_is_split_by_characters(self) -> None:
        chunks = Chunker(chunk_size=5, overlap=0, max_line_length=4).chunk("abcdefghi")

        self.assertEqual([chunk.text for chunk in chunks], ["abcd", "efgh", "i"])
        self.assertEqual([(chunk.line_start, chunk.line_end) for chunk in chunks], [(1, 1), (1, 1), (1, 1)])
        self.assertEqual([chunk.column_start for chunk in chunks], [1, 5, 9])

    def test_rejects_invalid_overlap(self) -> None:
        with self.assertRaises(ValueError):
            Chunker(chunk_size=10, overlap=10)


if __name__ == "__main__":
    unittest.main()
