"""Search results list."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from app.i18n.i18n_service import I18nService
from app.models.search_result import SearchResult


class ResultsPanel(QWidget):
    result_selected = Signal(object)

    def __init__(self, i18n: I18nService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.title_label = QLabel(self)
        self.title_label.setObjectName("resultsTitleLabel")
        self.empty_label = QLabel(self)
        self.empty_label.setObjectName("emptyResultsLabel")
        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("resultsList")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title_label)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.list_widget, 1)

        self.list_widget.currentItemChanged.connect(self._emit_selected)
        self.retranslate()
        self.set_results([])

    def retranslate(self) -> None:
        self.title_label.setText(self.i18n.translate("results.title"))
        self.empty_label.setText(self.i18n.translate("results.empty"))
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            result = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(result, SearchResult):
                item.setText(self._format_result(result))

    def set_results(self, results: list[SearchResult]) -> None:
        self.list_widget.clear()
        self.empty_label.setVisible(not results)
        self.list_widget.setVisible(bool(results))
        for result in results:
            item = QListWidgetItem(self._format_result(result))
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.list_widget.addItem(item)
        if results:
            self.list_widget.setCurrentRow(0)

    def _format_result(self, result: SearchResult) -> str:
        return self.i18n.translate(
            "results.item_summary",
            filename=result.document.filename,
            matches=len(result.file_matches) + result.total_content_matches,
            path=result.document.path,
        )

    def _emit_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self.result_selected.emit(current.data(Qt.ItemDataRole.UserRole))
