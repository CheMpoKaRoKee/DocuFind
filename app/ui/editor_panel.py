"""Text editor panel for indexed text files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLabel, QPushButton, QComboBox, QTextEdit, QToolBar, QVBoxLayout, QWidget

from app.editor.backup_cleanup_service import BackupCleanupService
from app.editor.backup_service import BackupService
from app.editor.safe_save_service import SafeSaveError, SafeSaveService
from app.editor.text_file_loader import EditorSnapshot, TextFileLoader
from app.i18n.i18n_service import I18nService
from app.models.content_match import ContentMatch
from app.models.search_result import SearchResult
from app.settings import ApplicationSettings
from app.storage.database import Database
from app.utils.app_paths import AppPaths


class EditorPanel(QWidget):
    saved = Signal(Path)
    save_failed = Signal(str)

    def __init__(
        self,
        i18n: I18nService,
        *,
        paths: AppPaths,
        database: Database | None = None,
        loader: TextFileLoader | None = None,
        settings: ApplicationSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.paths = paths
        self.database = database
        self.settings = settings or ApplicationSettings.defaults(paths)
        self.loader = loader or TextFileLoader()
        self.snapshot: EditorSnapshot | None = None
        self.mode = "blocked_unsupported"
        self.matches: list[ContentMatch] = []
        self.current_match_index = -1

        self.toolbar = QToolBar(self)
        self.save_button = QPushButton(self)
        self.save_button.setObjectName("editorSaveButton")
        self.reload_button = QPushButton(self)
        self.reload_button.setObjectName("editorReloadButton")
        self.previous_match_button = QPushButton(self)
        self.previous_match_button.setObjectName("editorPreviousMatchButton")
        self.next_match_button = QPushButton(self)
        self.next_match_button.setObjectName("editorNextMatchButton")
        self.match_combo = QComboBox(self)
        self.match_combo.setObjectName("editorMatchCombo")
        self.match_combo.setMinimumWidth(260)
        self.toolbar.addWidget(self.save_button)
        self.toolbar.addWidget(self.reload_button)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.previous_match_button)
        self.toolbar.addWidget(self.match_combo)
        self.toolbar.addWidget(self.next_match_button)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("editorStatusLabel")
        self.text_edit = QTextEdit(self)
        self.text_edit.setObjectName("editorTextEdit")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.text_edit, 1)

        self.save_button.clicked.connect(self.save)
        self.reload_button.clicked.connect(self.reload)
        self.previous_match_button.clicked.connect(self.previous_match)
        self.next_match_button.clicked.connect(self.next_match)
        self.match_combo.currentIndexChanged.connect(self._select_match_from_combo)
        self.retranslate()
        self.clear()

    def update_settings(self, settings: ApplicationSettings) -> None:
        self.settings = settings

    def retranslate(self) -> None:
        self.save_button.setText(self.i18n.translate("editor.save"))
        self.reload_button.setText(self.i18n.translate("editor.reload"))
        self.previous_match_button.setText(self.i18n.translate("editor.previous_match"))
        self.next_match_button.setText(self.i18n.translate("editor.next_match"))
        self._populate_match_combo()
        self._render_mode()

    def clear(self) -> None:
        self.snapshot = None
        self.mode = "blocked_unsupported"
        self.matches = []
        self.current_match_index = -1
        self.text_edit.clear()
        self.text_edit.setReadOnly(True)
        self._populate_match_combo()
        self._render_mode()

    def set_result(self, result: SearchResult | None) -> None:
        if result is None:
            self.clear()
            return
        self.matches = list(result.content_matches)
        self.current_match_index = 0 if self.matches else -1
        self._populate_match_combo()
        self.load_path(Path(result.document.path))
        self._go_to_current_match()

    def load_path(self, path: Path, *, line_number: int | None = None) -> None:
        loaded = self.loader.load(path)
        self.snapshot = loaded.snapshot
        self.mode = loaded.mode
        self.text_edit.setPlainText(loaded.text)
        self.text_edit.setReadOnly(self.mode != "editable")
        self._render_mode(loaded.message)
        if line_number is not None and loaded.text:
            self._go_to_line(line_number)

    def reload(self) -> None:
        if self.snapshot is not None:
            self.load_path(self.snapshot.path)
            self._go_to_current_match()

    def save(self) -> None:
        if self.snapshot is None:
            return
        backup_dir = Path(self.settings.backup_path or str(self.paths.backups_dir))
        try:
            service = SafeSaveService(
                backup_service=BackupService(backup_dir),
                cleanup_service=BackupCleanupService(
                    backup_dir,
                    retention_days=self.settings.backup_retention_days,
                    max_storage_bytes=self.settings.backup_max_size_bytes,
                ),
                database=self.database,
                backup_enabled=self.settings.backup_enabled,
            )
            service.save(self.snapshot, self.text_edit.toPlainText())
        except SafeSaveError as exc:
            self.mode = exc.mode
            self.text_edit.setReadOnly(True)
            self._render_mode(str(exc))
            self.save_failed.emit(str(exc))
            return
        self.saved.emit(self.snapshot.path)
        self.load_path(self.snapshot.path)
        self._go_to_current_match()

    def previous_match(self) -> None:
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index - 1) % len(self.matches)
        self.match_combo.setCurrentIndex(self.current_match_index)
        self._go_to_current_match()

    def next_match(self) -> None:
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        self.match_combo.setCurrentIndex(self.current_match_index)
        self._go_to_current_match()

    def _select_match_from_combo(self, index: int) -> None:
        if index < 0 or index >= len(self.matches):
            return
        self.current_match_index = index
        self._go_to_current_match()

    def _go_to_current_match(self) -> None:
        if self.current_match_index < 0 or self.current_match_index >= len(self.matches):
            self._render_match_status()
            return
        match = self.matches[self.current_match_index]
        if match.char_start is not None and match.char_end is not None:
            self._select_char_range(match.char_start, match.char_end)
        elif match.line_number is not None:
            self._go_to_line(match.line_number)
        self._render_match_status()

    def _select_char_range(self, start: int, end: int) -> None:
        document_length = len(self.text_edit.toPlainText())
        start = max(0, min(start, document_length))
        end = max(start, min(end, document_length))
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
        self.text_edit.setFocus()

    def _populate_match_combo(self) -> None:
        blocked = self.match_combo.blockSignals(True)
        self.match_combo.clear()
        if not self.matches:
            self.match_combo.addItem(self.i18n.translate("editor.no_matches"))
            self.match_combo.setEnabled(False)
        else:
            for index, match in enumerate(self.matches, start=1):
                self.match_combo.addItem(_format_match_label(self.i18n, index, len(self.matches), match))
            self.match_combo.setEnabled(True)
            if 0 <= self.current_match_index < self.match_combo.count():
                self.match_combo.setCurrentIndex(self.current_match_index)
        self.match_combo.blockSignals(blocked)
        self._update_match_controls()

    def _render_mode(self, message: str | None = None) -> None:
        key = {
            "editable": "editor.mode.editable",
            "read_only": "editor.mode.read_only",
            "blocked_too_large": "editor.mode.blocked_too_large",
            "blocked_unsupported": "editor.mode.blocked_unsupported",
            "blocked_changed_on_disk": "editor.mode.blocked_changed_on_disk",
        }.get(self.mode, "editor.mode.blocked_unsupported")
        text = self.i18n.translate(key)
        if message:
            text = f"{text}: {message}"
        self.status_label.setText(text)
        self.save_button.setEnabled(self.mode == "editable" and self.snapshot is not None)
        self.reload_button.setEnabled(self.snapshot is not None)
        self._update_match_controls()

    def _render_match_status(self) -> None:
        if not self.matches or self.current_match_index < 0:
            self._render_mode()
            return
        match = self.matches[self.current_match_index]
        self.status_label.setText(
            self.i18n.translate(
                "editor.match_status",
                current=self.current_match_index + 1,
                total=len(self.matches),
                line=match.line_number or 0,
                column=match.column_number or 0,
            )
        )
        self._update_match_controls()

    def _update_match_controls(self) -> None:
        enabled = bool(self.matches) and self.snapshot is not None
        self.previous_match_button.setEnabled(enabled)
        self.next_match_button.setEnabled(enabled)
        self.match_combo.setEnabled(enabled)

    def _go_to_line(self, line_number: int) -> None:
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        for _ in range(max(line_number - 1, 0)):
            cursor.movePosition(cursor.MoveOperation.Down)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
        self.text_edit.setFocus()


def _format_match_label(i18n: I18nService, index: int, total: int, match: ContentMatch) -> str:
    text = match.matched_text.replace("\n", " ").strip()
    if len(text) > 48:
        text = text[:45] + "..."
    return i18n.translate(
        "editor.match_item",
        current=index,
        total=total,
        line=match.line_number or 0,
        column=match.column_number or 0,
        text=text,
    )
