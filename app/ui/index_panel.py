"""Indexing controls and index state for the main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.i18n.i18n_service import I18nService
from app.models.index_progress import IndexProgress


class IndexPanel(QWidget):
    select_folder_requested = Signal()
    index_requested = Signal(Path)
    cancel_requested = Signal()
    clear_index_requested = Signal()

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
        self.clear_index_button = QPushButton(self)
        self.clear_index_button.setObjectName("clearIndexButton")
        self.state_label = QLabel(self)
        self.state_label.setObjectName("indexStateLabel")
        self.state_label.setWordWrap(True)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("indexProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_status_label = QLabel(self)
        self.progress_status_label.setObjectName("indexProgressStatusLabel")
        self.progress_current_label = QLabel(self)
        self.progress_current_label.setObjectName("indexProgressCurrentLabel")
        self.progress_counts_label = QLabel(self)
        self.progress_counts_label.setObjectName("indexProgressCountsLabel")
        self.progress_details_label = QLabel(self)
        self.progress_details_label.setObjectName("indexProgressDetailsLabel")
        self.progress_details_label.setWordWrap(True)

        folder_controls = QHBoxLayout()
        folder_controls.setContentsMargins(0, 0, 0, 0)
        folder_controls.addWidget(self.folder_edit, 1)
        folder_controls.addWidget(self.select_button)

        action_controls = QHBoxLayout()
        action_controls.setContentsMargins(0, 0, 0, 0)
        action_controls.addWidget(self.index_button)
        action_controls.addWidget(self.cancel_button)
        action_controls.addWidget(self.clear_index_button)
        action_controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(folder_controls)
        layout.addLayout(action_controls)
        layout.addWidget(self.state_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_status_label)
        layout.addWidget(self.progress_counts_label)
        layout.addWidget(self.progress_details_label)
        layout.addWidget(self.progress_current_label)

        self.select_button.clicked.connect(self.select_folder_requested.emit)
        self.index_button.clicked.connect(self._emit_index)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.clear_index_button.clicked.connect(self.clear_index_requested.emit)
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
        self.clear_index_button.setEnabled(not busy)

    def set_cancelling(self) -> None:
        self.cancel_button.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_status_label.setText(self.i18n.translate("index.progress_cancelling"))
        self.progress_current_label.setText(self.i18n.translate("index.progress_cancelling_wait"))

    def reset_progress(self) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_status_label.setText(self.i18n.translate("index.progress_idle"))
        self.progress_counts_label.setText(
            self.i18n.translate("index.progress_counts", processed=0, total=0, indexed=0)
        )
        self.progress_details_label.setText(
            self.i18n.translate(
                "index.progress_details",
                new=0,
                reindexed=0,
                unchanged=0,
                skipped=0,
                deleted=0,
                restored=0,
                failed=0,
            )
        )
        self.progress_current_label.setText(
            self.i18n.translate("index.progress_current", path=self.i18n.translate("index.progress_no_file"))
        )

    def set_index_state_text(self, text: str) -> None:
        self.state_label.setText(text)

    def set_progress(self, progress: object) -> None:
        if not isinstance(progress, IndexProgress):
            return
        if progress.percent is None:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(progress.percent)
        total = "?" if progress.files_total is None else str(progress.files_total)
        indexed_total = progress.files_indexed + progress.files_reindexed
        percent = "..." if progress.percent is None else str(progress.percent)
        phase = self.i18n.translate(f"index.phase.{progress.phase}")
        eta = _format_eta(self.i18n, progress.eta_seconds)
        speed = _format_speed(self.i18n, progress.files_per_second)
        self.progress_status_label.setText(
            self.i18n.translate("index.progress_status", phase=phase, percent=percent, eta=eta, speed=speed)
        )
        processed = progress.files_processed
        if progress.phase == "scanning" and progress.message:
            processed = progress.message
        if progress.phase in {"clearing_index", "clear_completed"}:
            self.progress_counts_label.setText(
                self.i18n.translate("index.clear_progress_counts", processed=processed, total=total)
            )
            self.progress_details_label.setText(self.i18n.translate("index.clear_progress_details"))
        else:
            self.progress_counts_label.setText(
                self.i18n.translate(
                    "index.progress_counts",
                    processed=processed,
                    total=total,
                    indexed=indexed_total,
                )
            )
            self.progress_details_label.setText(
                self.i18n.translate(
                    "index.progress_details",
                    new=progress.files_new,
                    reindexed=progress.files_reindexed,
                    unchanged=progress.files_unchanged,
                    skipped=progress.files_skipped,
                    deleted=progress.files_deleted,
                    restored=progress.files_restored,
                    failed=progress.files_failed,
                )
            )
        current = Path(progress.current_path).name if progress.current_path else self.i18n.translate("index.progress_no_file")
        if progress.phase in {"clearing_index", "clear_completed"}:
            self.progress_current_label.setText(self.i18n.translate("index.clear_progress_current", table=current))
        else:
            self.progress_current_label.setText(self.i18n.translate("index.progress_current", path=current))

    def retranslate(self) -> None:
        self.folder_edit.setPlaceholderText(self.i18n.translate("index.folder_placeholder"))
        self.select_button.setText(self.i18n.translate("index.select_folder"))
        self.index_button.setText(self.i18n.translate("index.start"))
        self.cancel_button.setText(self.i18n.translate("index.cancel"))
        self.clear_index_button.setText(self.i18n.translate("index.clear"))
        self.cancel_button.setToolTip(self.i18n.translate("index.cancel_tooltip"))
        self.clear_index_button.setToolTip(self.i18n.translate("index.clear_tooltip"))
        self.reset_progress()

    def _emit_index(self) -> None:
        if self.folder is not None:
            self.index_requested.emit(self.folder)


def _format_eta(i18n: I18nService, seconds: int | None) -> str:
    if seconds is None:
        return i18n.translate("index.progress_eta_unknown")
    if seconds <= 0:
        return i18n.translate("index.progress_eta_done")
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)
    if hours:
        return i18n.translate("index.progress_eta_hms", hours=hours, minutes=remaining_minutes)
    if minutes:
        return i18n.translate("index.progress_eta_ms", minutes=minutes, seconds=remaining_seconds)
    return i18n.translate("index.progress_eta_s", seconds=remaining_seconds)


def _format_speed(i18n: I18nService, files_per_second: float | None) -> str:
    if files_per_second is None or files_per_second <= 0:
        return i18n.translate("index.progress_speed_unknown")
    return i18n.translate("index.progress_speed_value", speed=f"{files_per_second:.1f}")
