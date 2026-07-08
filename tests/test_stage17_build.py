from __future__ import annotations

import unittest
from pathlib import Path


class BuildConfigurationTests(unittest.TestCase):
    def test_pyinstaller_files_exist(self) -> None:
        self.assertTrue((Path.cwd() / "DocuFindLocal.spec").exists())
        self.assertTrue((Path.cwd() / "build_exe.py").exists())

    def test_spec_includes_i18n_data_and_app_entry(self) -> None:
        spec = (Path.cwd() / "DocuFindLocal.spec").read_text(encoding="utf-8")

        self.assertIn("app/main.py", spec)
        self.assertIn("app/i18n/*.json", spec)
        self.assertIn('name="DocuFindLocal"', spec)
        self.assertIn('pymorphy3', spec)

    def test_readme_has_ru_and_en_usage_sections(self) -> None:
        readme = (Path.cwd() / "README.md").read_text(encoding="utf-8-sig")

        self.assertIn("## Русский", readme)
        self.assertIn("## English", readme)
        self.assertIn("py -3.13 -m app.main", readme)
        self.assertIn("py -3.13 build_exe.py", readme)


if __name__ == "__main__":
    unittest.main()

