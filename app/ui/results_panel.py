"""Search results list."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from app.i18n.i18n_service import I18nService
from app.models.search_result import SearchResult


class ResultsPanel(QWidget):
    result_selected = Signal(object)
    open_in_explorer_requested = Signal(str)

    def __init__(self, i18n: I18nService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self._results_count = 0
        self.title_label = QLabel(self)
        self.title_label.setObjectName("resultsTitleLabel")
        self.empty_label = QLabel(self)
        self.empty_label.setObjectName("emptyResultsLabel")
        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("resultsList")
        self.list_widget.setUniformItemSizes(False)
        self.list_widget.setAlternatingRowColors(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title_label)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.list_widget, 1)

        self.list_widget.currentItemChanged.connect(self._emit_selected)
        self.retranslate()
        self.set_results([])

    def retranslate(self) -> None:
        self._render_title()
        self.empty_label.setText(self.i18n.translate("results.empty"))
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            result = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(result, SearchResult):
                item.setData(Qt.ItemDataRole.AccessibleTextRole, self._format_result(result))
                row_widget = self.list_widget.itemWidget(item)
                if isinstance(row_widget, ResultRow):
                    row_widget.retranslate(self.i18n, self._format_result(result))

    def set_results(self, results: list[SearchResult]) -> None:
        self._results_count = len(results)
        self._render_title()
        self.list_widget.setUpdatesEnabled(False)
        try:
            self.list_widget.clear()
            self.empty_label.setVisible(not results)
            self.list_widget.setVisible(bool(results))
            for result in results:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, result)
                item.setData(Qt.ItemDataRole.AccessibleTextRole, self._format_result(result))
                self.list_widget.addItem(item)
                row_widget = ResultRow(self.i18n, self._format_result(result), result.document.path, self.list_widget)
                row_widget.open_requested.connect(self.open_in_explorer_requested)
                item.setSizeHint(row_widget.sizeHint())
                self.list_widget.setItemWidget(item, row_widget)
            if results:
                self.list_widget.setCurrentRow(0)
        finally:
            self.list_widget.setUpdatesEnabled(True)

    def _format_result(self, result: SearchResult) -> str:
        return self.i18n.translate(
            "results.item_summary",
            filename=result.document.filename,
            matches=len(result.file_matches) + result.total_content_matches,
            path=result.document.path,
            context=_result_context(self.i18n, result),
        )

    def _render_title(self) -> None:
        if self._results_count:
            self.title_label.setText(self.i18n.translate("results.title_count", count=self._results_count))
        else:
            self.title_label.setText(self.i18n.translate("results.title"))

    def _emit_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self.result_selected.emit(current.data(Qt.ItemDataRole.UserRole))


class ResultRow(QWidget):
    open_requested = Signal(str)

    def __init__(self, i18n: I18nService, summary: str, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("resultRow")
        self.path = path
        self.summary_label = QLabel(summary, self)
        self.summary_label.setObjectName("resultSummaryLabel")
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.open_button = QPushButton(self)
        self.open_button.setObjectName("openResultInExplorerButton")
        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.path))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)
        layout.addWidget(self.summary_label, 1)
        layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignTop)
        self.retranslate(i18n, summary)

    def retranslate(self, i18n: I18nService, summary: str) -> None:
        self.summary_label.setText(summary)
        self.open_button.setText(i18n.translate("results.open_in_explorer"))
        self.open_button.setToolTip(i18n.translate("results.open_in_explorer_tooltip"))


def _result_context(i18n: I18nService, result: SearchResult) -> str:
    if result.content_matches:
        return _compact_text(result.content_matches[0].snippet)
    if result.file_matches:
        return i18n.translate("results.context_file_match")
    return i18n.translate("results.context_no_preview")


def _compact_text(text: str, *, limit: int = 170) -> str:
    compacted = " ".join(text.split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 3].rstrip() + "..."
