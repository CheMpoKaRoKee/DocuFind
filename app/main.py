"""Application entry point for the PySide6 UI."""

from __future__ import annotations

import sys
from pathlib import Path

from app.utils.app_paths import AppPaths
from app.utils.logger import get_logger, setup_logging
from app.utils.single_instance import SingleInstanceError, SingleInstanceLock


def main() -> int:
    paths = AppPaths.from_environment()
    paths.ensure_runtime_dirs()
    setup_logging(portable=paths.portable, base_dir=paths.base_dir)
    logger = get_logger("app")
    logger.info("DocuFind Local UI startup")
    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication, QMessageBox

        from app.storage.database import Database
        from app.ui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        logger.error("UI dependency is unavailable: %s", exc)
        print(f"UI dependency is unavailable: {exc}", file=sys.stderr)
        return 1

    app = QApplication(sys.argv)
    icon_path = Path(__file__).resolve().parent / "assets" / "library-building.png"
    app.setWindowIcon(QIcon(str(icon_path)))
    try:
        instance_lock = SingleInstanceLock(paths.base_dir / "docufind.lock")
    except SingleInstanceError:
        QMessageBox.warning(
            None,
            "DocuFind Local",
            "DocuFind Local уже запущен. Закройте другое окно приложения и повторите действие.",
        )
        return 0
    window = MainWindow(database=Database(paths.database_path), paths=paths)
    window.setWindowIcon(app.windowIcon())
    app.aboutToQuit.connect(instance_lock.release)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
