"""JSON-backed localization service."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES = {"ru", "en"}


class I18nService:
    def __init__(self, locale_dir: Path | None = None, language: str = DEFAULT_LANGUAGE) -> None:
        self.locale_dir = locale_dir or Path(__file__).resolve().parent
        self._catalogs: dict[str, dict[str, str]] = {}
        self.language = self._normalize_language(language)
        self._load_all()

    @property
    def available_languages(self) -> tuple[str, ...]:
        return tuple(sorted(self._catalogs))

    def set_language(self, language: str) -> None:
        self.language = self._normalize_language(language)

    def translate(self, key: str, **params: object) -> str:
        value = self._catalogs.get(self.language, {}).get(key)
        if value is None and self.language != DEFAULT_LANGUAGE:
            value = self._catalogs.get(DEFAULT_LANGUAGE, {}).get(key)
        if value is None:
            return key
        if params:
            return value.format_map(_SafeFormatDict(params))
        return value

    def _load_all(self) -> None:
        for language in SUPPORTED_LANGUAGES:
            self._catalogs[language] = self._load(language)

    def _load(self, language: str) -> dict[str, str]:
        path = self.locale_dir / f"{language}.json"
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError(f"Locale file must contain an object: {path}")
        return {str(key): str(value) for key, value in data.items()}

    @staticmethod
    def _normalize_language(language: str) -> str:
        normalized = language.strip().casefold()
        if normalized not in SUPPORTED_LANGUAGES:
            return DEFAULT_LANGUAGE
        return normalized


class _SafeFormatDict(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_i18n(language: str = DEFAULT_LANGUAGE) -> I18nService:
    return I18nService(language=language)


