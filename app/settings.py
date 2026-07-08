"""Typed application settings stored in the SQLite settings table."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.indexer.file_filter import MAX_INDEX_FILE_SIZE_BYTES, SUPPORTED_EXTENSIONS
from app.storage.settings_repository import SettingsRepository
from app.utils.app_paths import AppPaths
from app.utils.path_rules import DEFAULT_EXCLUDED_NAMES


@dataclass(frozen=True)
class ApplicationSettings:
    index_folders: list[str]
    excluded_folders: list[str]
    max_index_file_size_mb: int
    enabled_extensions: list[str]
    fuzzy_enabled: bool
    fuzzy_filename_threshold: int
    fuzzy_content_threshold: int
    search_result_limit: int
    matches_per_file_limit: int
    language: str
    backup_enabled: bool
    backup_path: str
    backup_retention_days: int
    backup_max_size_mb: int

    @classmethod
    def defaults(cls, paths: AppPaths) -> "ApplicationSettings":
        return cls(
            index_folders=[],
            excluded_folders=sorted(DEFAULT_EXCLUDED_NAMES),
            max_index_file_size_mb=max(1, MAX_INDEX_FILE_SIZE_BYTES // (1024 * 1024)),
            enabled_extensions=sorted(SUPPORTED_EXTENSIONS),
            fuzzy_enabled=True,
            fuzzy_filename_threshold=78,
            fuzzy_content_threshold=88,
            search_result_limit=500,
            matches_per_file_limit=100,
            language="ru",
            backup_enabled=True,
            backup_path=str(paths.backups_dir),
            backup_retention_days=30,
            backup_max_size_mb=500,
        )

    @property
    def max_index_file_size_bytes(self) -> int:
        return max(1, self.max_index_file_size_mb) * 1024 * 1024

    @property
    def backup_max_size_bytes(self) -> int:
        return max(1, self.backup_max_size_mb) * 1024 * 1024


def load_settings(repository: SettingsRepository, paths: AppPaths) -> ApplicationSettings:
    defaults = ApplicationSettings.defaults(paths)
    return ApplicationSettings(
        index_folders=_json_list(repository.get("index.folders"), defaults.index_folders),
        excluded_folders=_json_list(repository.get("index.excluded_folders"), defaults.excluded_folders),
        max_index_file_size_mb=_int(repository.get("index.max_file_size_mb"), defaults.max_index_file_size_mb),
        enabled_extensions=_extensions(repository.get("index.enabled_extensions"), defaults.enabled_extensions),
        fuzzy_enabled=_bool(repository.get("search.fuzzy_enabled"), defaults.fuzzy_enabled),
        fuzzy_filename_threshold=_int(
            repository.get("search.fuzzy_filename_threshold"),
            defaults.fuzzy_filename_threshold,
        ),
        fuzzy_content_threshold=_int(
            repository.get("search.fuzzy_content_threshold"),
            defaults.fuzzy_content_threshold,
        ),
        search_result_limit=_int(repository.get("search.result_limit"), defaults.search_result_limit),
        matches_per_file_limit=_int(repository.get("search.matches_per_file_limit"), defaults.matches_per_file_limit),
        language=repository.get("language", defaults.language) or defaults.language,
        backup_enabled=_bool(repository.get("backup.enabled"), defaults.backup_enabled),
        backup_path=repository.get("backup.path", defaults.backup_path) or defaults.backup_path,
        backup_retention_days=_int(repository.get("backup.retention_days"), defaults.backup_retention_days),
        backup_max_size_mb=_int(repository.get("backup.max_size_mb"), defaults.backup_max_size_mb),
    )


def save_settings(repository: SettingsRepository, settings: ApplicationSettings) -> None:
    repository.set("index.folders", json.dumps(_clean_paths(settings.index_folders), ensure_ascii=False))
    repository.set(
        "index.excluded_folders",
        json.dumps(_clean_names(settings.excluded_folders), ensure_ascii=False),
    )
    repository.set("index.max_file_size_mb", str(max(1, settings.max_index_file_size_mb)))
    repository.set(
        "index.enabled_extensions",
        json.dumps(_clean_extensions(settings.enabled_extensions), ensure_ascii=False),
    )
    repository.set("search.fuzzy_enabled", "1" if settings.fuzzy_enabled else "0")
    repository.set("search.fuzzy_filename_threshold", str(_clamp(settings.fuzzy_filename_threshold, 0, 100)))
    repository.set("search.fuzzy_content_threshold", str(_clamp(settings.fuzzy_content_threshold, 0, 100)))
    repository.set("search.result_limit", str(max(1, settings.search_result_limit)))
    repository.set("search.matches_per_file_limit", str(max(1, settings.matches_per_file_limit)))
    repository.set("language", settings.language if settings.language in {"ru", "en"} else "ru")
    repository.set("backup.enabled", "1" if settings.backup_enabled else "0")
    repository.set("backup.path", str(Path(settings.backup_path).expanduser()))
    repository.set("backup.retention_days", str(max(1, settings.backup_retention_days)))
    repository.set("backup.max_size_mb", str(max(1, settings.backup_max_size_mb)))


def _json_list(raw: str | None, default: list[str]) -> list[str]:
    if not raw:
        return list(default)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return list(default)
    if not isinstance(value, list):
        return list(default)
    return [str(item).strip() for item in value if str(item).strip()]


def _extensions(raw: str | None, default: list[str]) -> list[str]:
    return _clean_extensions(_json_list(raw, default))


def _clean_extensions(values: list[str]) -> list[str]:
    cleaned = []
    for value in values:
        extension = value.strip().casefold()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = "." + extension
        cleaned.append(extension)
    return sorted(set(cleaned))


def _clean_names(values: list[str]) -> list[str]:
    return sorted({value.strip().casefold() for value in values if value.strip()})


def _clean_paths(values: list[str]) -> list[str]:
    return [str(Path(value).expanduser()) for value in values if value.strip()]


def _int(raw: str | None, default: int) -> int:
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
