"""Safe rotating logging setup for DocuFind Local."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.utils.app_paths import AppPaths

LOG_CATEGORIES = {
    "app",
    "indexing",
    "search",
    "fuzzy",
    "morphology",
    "editor",
    "backup",
    "database",
    "errors",
}

_CONFIGURED = False


def resolve_log_dir(portable: bool | None = None, base_dir: Path | None = None) -> Path:
    """Resolve log directory without reading or logging user file contents."""
    return AppPaths.from_environment(base_dir=base_dir, portable=portable).logs_dir


def setup_logging(
    *,
    portable: bool | None = None,
    base_dir: Path | None = None,
    level: int = logging.INFO,
    max_bytes: int = 1_000_000,
    backup_count: int = 5,
) -> Path:
    """Configure category loggers and return the active log directory."""
    global _CONFIGURED

    log_dir = resolve_log_dir(portable=portable, base_dir=base_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    if _CONFIGURED:
        return log_dir

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root_logger = logging.getLogger("docufind")
    root_logger.setLevel(level)
    root_logger.propagate = False

    app_handler = RotatingFileHandler(
        log_dir / "docufind.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(level)
    root_logger.addHandler(app_handler)

    error_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    for category in LOG_CATEGORIES:
        logger = logging.getLogger(f"docufind.{category}")
        logger.setLevel(level)
        logger.propagate = True

    _CONFIGURED = True
    return log_dir


def get_logger(category: str) -> logging.Logger:
    if category not in LOG_CATEGORIES:
        category = "app"
    return logging.getLogger(f"docufind.{category}")
