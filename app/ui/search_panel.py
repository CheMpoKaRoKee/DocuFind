"""Search controls for the main window."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from app.i18n.i18n_service import I18nService


class SearchPanel(QWidget):
    search_requested = Signal(str)

    def __init__(self, i18n: I18nService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.query_edit = QLineEdit(self)
        self.query_edit.setObjectName("queryEdit")
        self.search_button = QPushButton(self)
        self.search_button.setObjectName("searchButton")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.query_edit, 1)
        layout.addWidget(self.search_button)

        self.search_button.clicked.connect(self._emit_search)
        self.query_edit.returnPressed.connect(self._emit_search)
        self.retranslate()

    def retranslate(self) -> None:
        self.query_edit.setPlaceholderText(self.i18n.translate("search.placeholder"))
        self.search_button.setText(self.i18n.translate("search.run"))

    def set_busy(self, busy: bool) -> None:
        self.search_button.setEnabled(not busy)
        self.query_edit.setEnabled(not busy)

    def _emit_search(self) -> None:
        self.search_requested.emit(self.query_edit.text().strip())
