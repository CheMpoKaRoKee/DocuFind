"""Indexing controls and index state for the main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.i18n.i18n_service import I18nService


class IndexPanel(QWidget):
    select_folder_requested = Signal()
    index_requested = Signal(Path)
    cancel_requested = Signal()

    def __init__(self, i18n: I18nService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.folder: Path | None = None
        self.folder_edit = QLineEdit(self)
        self.folder_edit.setObjectName("folderEdit")
        self.folder_edit.setReadOnly(True)
        self.select_button = QPushButton(self)
        self.select_button.setObjectName("selectFolderButton")
        self.index_button = QPushButton(self)
        self.index_button.setObjectName("indexButton")
        self.cancel_button = QPushButton(self)
        self.cancel_button.setObjectName("cancelIndexButton")
        self.state_label = QLabel(self)
        self.state_label.setObjectName("indexStateLabel")
        self.state_label.setWordWrap(True)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self.folder_edit, 1)
        controls.addWidget(self.select_button)
        controls.addWidget(self.index_button)
        controls.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self.state_label)

        self.select_button.clicked.connect(self.select_folder_requested.emit)
        self.index_button.clicked.connect(self._emit_index)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.set_busy(False)
        self.retranslate()

    def set_folder(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.folder_edit.setText(str(self.folder))
        self.index_button.setEnabled(True)

    def set_busy(self, busy: bool) -> None:
        self.select_button.setEnabled(not busy)
        self.index_button.setEnabled(not busy and self.folder is not None)
        self.cancel_button.setEnabled(busy)

    def set_index_state_text(self, text: str) -> None:
        self.state_label.setText(text)

    def retranslate(self) -> None:
        self.folder_edit.setPlaceholderText(self.i18n.translate("index.folder_placeholder"))
        self.select_button.setText(self.i18n.translate("index.select_folder"))
        self.index_button.setText(self.i18n.translate("index.start"))
        self.cancel_button.setText(self.i18n.translate("index.cancel"))

    def _emit_index(self) -> None:
        if self.folder is not None:
            self.index_requested.emit(self.folder)
