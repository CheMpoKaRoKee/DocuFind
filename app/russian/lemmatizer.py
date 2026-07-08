"""Lemmatization facade."""

from __future__ import annotations

from app.russian.morphology_analyzer import MorphologyAnalyzer
from app.russian.russian_tokenizer import RussianTokenizer, is_russian_token


class Lemmatizer:
    def __init__(
        self,
        *,
        tokenizer: RussianTokenizer | None = None,
        morphology: MorphologyAnalyzer | None = None,
    ) -> None:
        self.tokenizer = tokenizer or RussianTokenizer()
        self.morphology = morphology or MorphologyAnalyzer()

    def lemmatize_token(self, token: str) -> str:
        if not is_russian_token(token):
            return token.casefold()
        return self.morphology.normalize(token).lemma

    def lemmatize_text(self, text: str) -> list[str]:
        return [self.lemmatize_token(token) for token in self.tokenizer.russian_tokens(text)]

