"""Russian morphology with optional pymorphy3 and deterministic fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.utils.logger import get_logger


@dataclass(frozen=True)
class MorphologyResult:
    token: str
    lemma: str
    source: str


class MorphologyAnalyzer:
    def __init__(self) -> None:
        self.logger = get_logger("morphology")
        self._morph = self._load_pymorphy3()
        self._cache: dict[str, MorphologyResult] = {}
        self.source = "pymorphy3" if self._morph is not None else "fallback"
        if self._morph is None and self.logger.hasHandlers():
            self.logger.warning("pymorphy3 is unavailable; using fallback Russian morphology")

    def normalize(self, token: str) -> MorphologyResult:
        normalized = token.casefold().replace("ё", "е")
        cached = self._cache.get(normalized)
        if cached is not None:
            return cached
        if not normalized:
            return self._remember(normalized, normalized)

        domain_lemma = _domain_lemma(normalized)
        if domain_lemma is not None:
            return self._remember(normalized, domain_lemma)

        if self._morph is not None:
            parsed = self._morph.parse(normalized)
            if parsed:
                best = _select_parse(parsed)
                return self._remember(normalized, best.normal_form.replace("ё", "е"))

        return self._remember(normalized, _fallback_lemma(normalized))

    def _remember(self, token: str, lemma: str) -> MorphologyResult:
        if len(self._cache) >= 100_000:
            self._cache.clear()
        result = MorphologyResult(token=token, lemma=lemma, source=self.source)
        self._cache[token] = result
        return result

    @staticmethod
    def _load_pymorphy3():
        try:
            import pymorphy3  # type: ignore

            return pymorphy3.MorphAnalyzer()
        except Exception:
            return None


def _domain_lemma(token: str) -> str | None:
    if token.startswith("данн"):
        return "данные"
    return None


def _select_parse(parsed: list[Any]) -> Any:
    preferred_pos = {"NOUN", "ADJF", "ADJS"}
    for item in parsed:
        if item.tag.POS in preferred_pos:
            return item
    return parsed[0]


def _fallback_lemma(token: str) -> str:
    if token.startswith("персональн"):
        return "персональный"
    if token.startswith("данн"):
        return "данные"

    suffix_rules = (
        ("ыми", "ый"),
        ("ими", "ий"),
        ("ого", "ый"),
        ("ему", "ий"),
        ("ому", "ый"),
        ("ых", "ый"),
        ("их", "ий"),
        ("ым", "ый"),
        ("им", "ий"),
        ("ая", "ый"),
        ("яя", "ий"),
        ("ое", "ый"),
        ("ее", "ий"),
        ("ые", "ый"),
        ("ие", "ий"),
        ("ами", "а"),
        ("ями", "я"),
        ("ам", "а"),
        ("ям", "я"),
        ("ах", "а"),
        ("ях", "я"),
        ("ов", ""),
        ("ев", ""),
        ("ом", ""),
        ("ем", ""),
        ("ой", "а"),
        ("ей", "я"),
        ("ы", "а"),
        ("и", "ь"),
    )
    for suffix, replacement in suffix_rules:
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)] + replacement
    return token
