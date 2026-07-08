"""Read-only preview for the selected search result."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from app.i18n.i18n_service import I18nService
from app.models.content_match import ContentMatch
from app.models.search_result import SearchResult


class PreviewPanel(QWidget):
    def __init__(self, i18n: I18nService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.current_result: SearchResult | None = None
        self.title_label = QLabel(self)
        self.title_label.setObjectName("previewTitleLabel")
        self.meta_label = QLabel(self)
        self.meta_label.setObjectName("previewMetaLabel")
        self.stale_label = QLabel(self)
        self.stale_label.setObjectName("previewStaleLabel")
        self.preview_edit = QTextEdit(self)
        self.preview_edit.setObjectName("previewEdit")
        self.preview_edit.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.stale_label)
        layout.addWidget(self.preview_edit, 1)

        self.retranslate()
        self.clear()

    def retranslate(self) -> None:
        self.title_label.setText(self.i18n.translate("preview.title"))
        self.stale_label.setText(self.i18n.translate("preview.stale"))
        if self.current_result is None:
            self.meta_label.setText(self.i18n.translate("preview.empty"))
        else:
            self._render_result(self.current_result)

    def clear(self) -> None:
        self.current_result = None
        self.meta_label.setText(self.i18n.translate("preview.empty"))
        self.stale_label.setVisible(False)
        self.preview_edit.clear()

    def set_result(self, result: SearchResult | None) -> None:
        if result is None:
            self.clear()
            return
        self.current_result = result
        self._render_result(result)

    def _render_result(self, result: SearchResult) -> None:
        match = result.content_matches[0] if result.content_matches else None
        if match is None:
            self.meta_label.setText(self.i18n.translate("preview.file_only", path=result.document.path))
            self.preview_edit.setPlainText(result.document.path)
        else:
            self.meta_label.setText(
                self.i18n.translate(
                    "preview.location",
                    path=result.document.path,
                    line=match.line_number or 0,
                    column=match.column_number or 0,
                )
            )
            self.preview_edit.setHtml(_highlight_match(match))
        self.stale_label.setVisible(_is_stale(result))


def _highlight_match(match: ContentMatch) -> str:
    snippet = escape(match.snippet)
    matched = escape(match.matched_text)
    if matched:
        snippet = snippet.replace(matched, f"<mark>{matched}</mark>", 1)
    return f"<pre>{snippet}</pre>"


def _is_stale(result: SearchResult) -> bool:
    path = Path(result.document.path)
    try:
        stat_result = path.stat()
    except OSError:
        return True
    if stat_result.st_size != result.document.size_bytes:
        return True
    try:
        indexed_mtime = datetime.fromisoformat(result.document.modified_at).timestamp()
    except ValueError:
        return False
    return abs(stat_result.st_mtime - indexed_mtime) > 1.0
