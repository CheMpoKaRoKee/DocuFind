from __future__ import annotations

import tempfile
import unittest
import hashlib
from pathlib import Path

from app.indexer.text_extractor import TextExtractionError, TextExtractor
from app.utils.encoding_detector import EncodingDetector
from app.utils.line_ending_detector import LineEndingDetector
from app.utils.long_line_handler import LongLineHandler


class TextExtractionTests(unittest.TestCase):
    def test_encoding_detector_prefers_utf8(self) -> None:
        self.assertEqual(EncodingDetector().detect("текст".encode("utf-8")), "utf-8")

    def test_encoding_detector_supports_cp1251(self) -> None:
        self.assertEqual(EncodingDetector().detect("персональные данные".encode("cp1251")), "cp1251")

    def test_line_ending_detector_detects_crlf(self) -> None:
        self.assertEqual(LineEndingDetector().detect("a\r\nb\r\n"), "crlf")

    def test_extracts_utf8_text_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "note.md"
            path.write_text("line 1\nline 2\n", encoding="utf-8", newline="\n")

            result = TextExtractor().extract(path)

            self.assertEqual(result.text, "line 1\nline 2\n")
            self.assertEqual(result.encoding, "utf-8")
            self.assertEqual(result.line_ending, "lf")
            self.assertEqual(result.long_line_count, 0)

    def test_extracts_cp1251_text(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "ru.txt"
            path.write_bytes("персональные данные".encode("cp1251"))

            result = TextExtractor().extract(path)

            self.assertEqual(result.text, "персональные данные")
            self.assertEqual(result.encoding, "cp1251")

    def test_rejects_too_large_file_before_reading(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "large.txt"
            path.write_text("123456", encoding="utf-8")

            with self.assertRaises(TextExtractionError) as error:
                TextExtractor(max_size_bytes=5).extract(path)

            self.assertEqual(error.exception.status, "skipped_too_large")

    def test_long_line_handler_splits_long_lines(self) -> None:
        result = LongLineHandler(max_line_length=4).process("abcdefghi\nok")

        self.assertEqual(result.long_line_count, 1)
        self.assertEqual(result.text, "abcd\nefgh\ni\nok")

    def test_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "image.png"
            path.write_text("text", encoding="utf-8")

            with self.assertRaises(TextExtractionError) as error:
                TextExtractor().extract(path)

            self.assertEqual(error.exception.status, "skipped_unsupported_extension")

    def test_html_removes_markup_and_scripts_without_changing_offsets(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "page.html"
            source = '<html><style>.noise{color:red}</style><body>Hello <b>world</b><script>very slow noise</script></body></html>'
            path.write_text(source, encoding="utf-8")

            result = TextExtractor().extract(path)

            self.assertEqual(len(result.text), len(source))
            self.assertEqual(result.text.index("Hello"), source.index("Hello"))
            self.assertEqual(result.text.index("world"), source.index("world"))
            self.assertNotIn("noise", result.text)
            self.assertNotIn("<b>", result.text)
            self.assertEqual(result.content_hash, hashlib.sha256(source.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    unittest.main()


