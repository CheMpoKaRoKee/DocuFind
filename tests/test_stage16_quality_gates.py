from __future__ import annotations

import json
import unittest
from pathlib import Path


class QualityGateTests(unittest.TestCase):
    def test_ru_and_en_catalogs_have_same_keys(self) -> None:
        ru = _load_catalog("ru")
        en = _load_catalog("en")

        self.assertEqual(set(ru), set(en))

    def test_required_ui_and_editor_i18n_keys_exist(self) -> None:
        required = {
            "app.title",
            "index.select_folder",
            "search.run",
            "results.empty",
            "preview.stale",
            "editor.title",
            "editor.save",
            "editor.mode.editable",
            "editor.mode.read_only",
            "editor.mode.blocked_too_large",
            "editor.mode.blocked_unsupported",
            "editor.mode.blocked_changed_on_disk",
            "settings.language",
            "status.search_completed",
        }
        ru = _load_catalog("ru")
        en = _load_catalog("en")

        self.assertTrue(required.issubset(ru))
        self.assertTrue(required.issubset(en))

    def test_stage_test_modules_exist(self) -> None:
        expected = {
            "test_stage2_app_paths_i18n.py",
            "test_stage3_database.py",
            "test_stage4_scanner_filter.py",
            "test_stage5_text_extraction.py",
            "test_stage6_russian_morphology.py",
            "test_stage7_chunker.py",
            "test_stage8_index_service.py",
            "test_stage9_deleted_lifecycle.py",
            "test_stage10_query_parser_fts.py",
            "test_stage11_search_core.py",
            "test_stage12_fuzzy_search.py",
            "test_stage13_workers.py",
            "test_stage14_ui.py",
            "test_stage15_editor.py",
            "test_stage16_quality_gates.py",
        }
        actual = {path.name for path in (Path.cwd() / "tests").glob("test_stage*.py")}

        self.assertTrue(expected.issubset(actual))


def _load_catalog(language: str) -> dict[str, str]:
    path = Path.cwd() / "app" / "i18n" / f"{language}.json"
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return {str(key): str(value) for key, value in data.items()}


if __name__ == "__main__":
    unittest.main()
