from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.i18n.i18n_service import I18nService
from app.utils.app_paths import AppPaths
from app.utils.logger import resolve_log_dir


class AppPathsI18nTests(unittest.TestCase):
    def test_portable_paths_use_workspace_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            paths = AppPaths.from_environment(base_dir=base, portable=True)

            self.assertTrue(paths.portable)
            self.assertEqual(paths.data_dir, base / "data")
            self.assertEqual(paths.logs_dir, base / "logs")
            self.assertEqual(paths.backups_dir, base / "backups")
            self.assertEqual(paths.database_path, base / "data" / "docufind.db")

    def test_installed_paths_use_local_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}, clear=False):
                paths = AppPaths.from_environment(portable=False)

            expected = Path(temp_dir) / "DocuFind"
            self.assertFalse(paths.portable)
            self.assertEqual(paths.base_dir, expected)
            self.assertEqual(paths.data_dir, expected)
            self.assertEqual(paths.database_path, expected / "docufind.db")

    def test_logger_uses_app_paths_for_portable_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            self.assertEqual(resolve_log_dir(portable=True, base_dir=base), base / "logs")

    def test_i18n_loads_russian_by_default(self) -> None:
        service = I18nService()

        self.assertEqual(service.language, "ru")
        self.assertEqual(service.translate("search.run"), "Найти")

    def test_i18n_switches_to_english(self) -> None:
        service = I18nService(language="en")

        self.assertEqual(service.translate("search.run"), "Search")
        service.set_language("ru")
        self.assertEqual(service.translate("search.run"), "Найти")

    def test_i18n_falls_back_to_key_for_missing_translation(self) -> None:
        service = I18nService(language="en")

        self.assertEqual(service.translate("missing.key"), "missing.key")


if __name__ == "__main__":
    unittest.main()

