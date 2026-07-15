from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.indexer.file_filter import FileFilter
from app.indexer.folder_scanner import FolderScanError, FolderScanner
from app.utils.path_rules import PathRules


class ScannerFilterTests(unittest.TestCase):
    def test_scan_paths_does_not_run_expensive_file_filter(self) -> None:
        class CountingFilter:
            def __init__(self) -> None:
                self.calls = 0

            def evaluate(self, path: Path):
                self.calls += 1
                return FileFilter().evaluate(path)

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            (root / "a.txt").write_text("a", encoding="utf-8")
            file_filter = CountingFilter()
            scanner = FolderScanner(file_filter=file_filter)

            paths = list(scanner.scan_paths(root))

            self.assertEqual(paths, [root / "a.txt"])
            self.assertEqual(file_filter.calls, 0)
    def test_supported_text_file_is_indexed(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "note.md"
            path.write_text("hello", encoding="utf-8")

            result = FileFilter().evaluate(path)

            self.assertTrue(result.can_index)
            self.assertEqual(result.status, "indexed")
            self.assertEqual(result.size_bytes, 5)

    def test_unsupported_extension_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "image.png"
            path.write_bytes(b"not really an image")

            result = FileFilter().evaluate(path)

            self.assertFalse(result.can_index)
            self.assertEqual(result.status, "skipped_unsupported_extension")

    def test_binary_content_with_supported_extension_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "fake.txt"
            path.write_bytes(b"text\x00binary")

            result = FileFilter().evaluate(path)

            self.assertFalse(result.can_index)
            self.assertEqual(result.status, "skipped_binary")

    def test_too_large_file_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "large.txt"
            path.write_text("123456", encoding="utf-8")

            result = FileFilter(max_size_bytes=5).evaluate(path)

            self.assertFalse(result.can_index)
            self.assertEqual(result.status, "skipped_too_large")

    def test_hidden_file_is_indexed(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / ".hidden.md"
            path.write_text("hidden", encoding="utf-8")

            result = FileFilter().evaluate(path)

            self.assertTrue(result.can_index)
            self.assertTrue(result.is_hidden)

    def test_excluded_directory_is_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            included = root / "docs"
            excluded = root / "logs"
            included.mkdir()
            excluded.mkdir()
            (included / "keep.md").write_text("keep", encoding="utf-8")
            (excluded / "skip.md").write_text("skip", encoding="utf-8")

            scanner = FolderScanner(path_rules=PathRules())
            results = list(scanner.scan(root))

            self.assertEqual([result.path.name for result in results], ["keep.md"])
            self.assertTrue(results[0].can_index)

    def test_missing_root_is_a_scan_error(self) -> None:
        missing = Path.cwd() / "folder-that-does-not-exist"

        with self.assertRaises(FolderScanError):
            list(FolderScanner().scan(missing))

    def test_symlink_file_is_skipped_when_available(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            target = root / "target.md"
            target.write_text("target", encoding="utf-8")
            link = root / "link.md"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("Symlink creation is not available")

            result = FileFilter().evaluate(link)

            self.assertFalse(result.can_index)
            self.assertEqual(result.status, "skipped_symlink")


if __name__ == "__main__":
    unittest.main()


