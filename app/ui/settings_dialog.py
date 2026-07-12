"""Settings dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)

from app.i18n.i18n_service import I18nService
from app.settings import ApplicationSettings, load_settings, save_settings
from app.storage.database import Database
from app.storage.index_folder_repository import IndexFolderRepository
from app.storage.settings_repository import SettingsRepository
from app.utils.app_paths import AppPaths
from app.utils.path_normalizer import normalize_path


class SettingsDialog(QDialog):
    language_changed = Signal(str)
    settings_saved = Signal(object)

    def __init__(self, i18n: I18nService, database: Database, paths: AppPaths, parent=None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.database = database
        self.paths = paths
        self.settings = self._load_settings()

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("settingsTabs")
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.setObjectName("settingsButtonBox")

        self.index_folders_edit = QTextEdit(self)
        self.index_folders_edit.setObjectName("indexFoldersEdit")
        self.excluded_folders_edit = QTextEdit(self)
        self.excluded_folders_edit.setObjectName("excludedFoldersEdit")
        self.max_file_size_spin = _spinbox(self, 1, 102400)
        self.max_file_size_spin.setObjectName("maxIndexFileSizeSpin")
        self.extensions_edit = QLineEdit(self)
        self.extensions_edit.setObjectName("enabledExtensionsEdit")

        self.fuzzy_enabled_check = QCheckBox(self)
        self.fuzzy_enabled_check.setObjectName("fuzzyEnabledCheck")
        self.filename_threshold_spin = _spinbox(self, 0, 100)
        self.filename_threshold_spin.setObjectName("filenameFuzzyThresholdSpin")
        self.content_threshold_spin = _spinbox(self, 0, 100)
        self.content_threshold_spin.setObjectName("contentFuzzyThresholdSpin")
        self.result_limit_spin = _spinbox(self, 1, 100000)
        self.result_limit_spin.setObjectName("searchResultLimitSpin")
        self.matches_limit_spin = _spinbox(self, 1, 100000)
        self.matches_limit_spin.setObjectName("matchesPerFileLimitSpin")

        self.language_combo = QComboBox(self)
        self.language_combo.setObjectName("languageCombo")

        self.backup_enabled_check = QCheckBox(self)
        self.backup_enabled_check.setObjectName("backupEnabledCheck")
        self.backup_path_edit = QLineEdit(self)
        self.backup_path_edit.setObjectName("backupPathEdit")
        self.backup_retention_spin = _spinbox(self, 1, 3650)
        self.backup_retention_spin.setObjectName("backupRetentionSpin")
        self.backup_max_size_spin = _spinbox(self, 1, 102400)
        self.backup_max_size_spin.setObjectName("backupMaxSizeSpin")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.button_box)

        self._build_tabs()
        self._load_values(self.settings)
        self.button_box.accepted.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(self.i18n.translate("settings.title"))
        self.tabs.setTabText(0, self.i18n.translate("settings.indexing"))
        self.tabs.setTabText(1, self.i18n.translate("settings.search"))
        self.tabs.setTabText(2, self.i18n.translate("settings.interface"))
        self.tabs.setTabText(3, self.i18n.translate("settings.backup"))
        self.language_combo.clear()
        self.language_combo.addItem(self.i18n.translate("app.language.ru"), "ru")
        self.language_combo.addItem(self.i18n.translate("app.language.en"), "en")
        index = self.language_combo.findData(self.settings.language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        self.fuzzy_enabled_check.setText(self.i18n.translate("settings.fuzzy_enabled"))
        self.backup_enabled_check.setText(self.i18n.translate("settings.backup_enabled"))

    def _build_tabs(self) -> None:
        indexing = QGroupBox(self)
        indexing_layout = QFormLayout(indexing)
        indexing_layout.addRow(self.i18n.translate("settings.index_folders"), self.index_folders_edit)
        indexing_layout.addRow(self.i18n.translate("settings.excluded_folders"), self.excluded_folders_edit)
        indexing_layout.addRow(self.i18n.translate("settings.max_file_size_mb"), self.max_file_size_spin)
        indexing_layout.addRow(self.i18n.translate("settings.enabled_extensions"), self.extensions_edit)
        self.tabs.addTab(indexing, "")

        search = QGroupBox(self)
        search_layout = QFormLayout(search)
        search_layout.addRow("", self.fuzzy_enabled_check)
        search_layout.addRow(self.i18n.translate("settings.filename_threshold"), self.filename_threshold_spin)
        search_layout.addRow(self.i18n.translate("settings.content_threshold"), self.content_threshold_spin)
        search_layout.addRow(self.i18n.translate("settings.result_limit"), self.result_limit_spin)
        search_layout.addRow(self.i18n.translate("settings.matches_limit"), self.matches_limit_spin)
        self.tabs.addTab(search, "")

        interface = QGroupBox(self)
        interface_layout = QFormLayout(interface)
        interface_layout.addRow(self.i18n.translate("settings.language"), self.language_combo)
        self.tabs.addTab(interface, "")

        backup = QGroupBox(self)
        backup_layout = QFormLayout(backup)
        backup_layout.addRow("", self.backup_enabled_check)
        backup_layout.addRow(self.i18n.translate("settings.backup_path"), self.backup_path_edit)
        backup_layout.addRow(self.i18n.translate("settings.backup_retention_days"), self.backup_retention_spin)
        backup_layout.addRow(self.i18n.translate("settings.backup_max_size_mb"), self.backup_max_size_spin)
        self.tabs.addTab(backup, "")

    def _load_values(self, settings: ApplicationSettings) -> None:
        self.index_folders_edit.setPlainText("\n".join(settings.index_folders))
        self.excluded_folders_edit.setPlainText("\n".join(settings.excluded_folders))
        self.max_file_size_spin.setValue(settings.max_index_file_size_mb)
        self.extensions_edit.setText(", ".join(settings.enabled_extensions))
        self.fuzzy_enabled_check.setChecked(settings.fuzzy_enabled)
        self.filename_threshold_spin.setValue(settings.fuzzy_filename_threshold)
        self.content_threshold_spin.setValue(settings.fuzzy_content_threshold)
        self.result_limit_spin.setValue(settings.search_result_limit)
        self.matches_limit_spin.setValue(settings.matches_per_file_limit)
        self.backup_enabled_check.setChecked(settings.backup_enabled)
        self.backup_path_edit.setText(settings.backup_path)
        self.backup_retention_spin.setValue(settings.backup_retention_days)
        self.backup_max_size_spin.setValue(settings.backup_max_size_mb)

    def _save_and_accept(self) -> None:
        settings = ApplicationSettings(
            index_folders=_lines(self.index_folders_edit.toPlainText()),
            excluded_folders=_lines(self.excluded_folders_edit.toPlainText()),
            max_index_file_size_mb=self.max_file_size_spin.value(),
            enabled_extensions=_split_csv(self.extensions_edit.text()),
            fuzzy_enabled=self.fuzzy_enabled_check.isChecked(),
            fuzzy_filename_threshold=self.filename_threshold_spin.value(),
            fuzzy_content_threshold=self.content_threshold_spin.value(),
            search_result_limit=self.result_limit_spin.value(),
            matches_per_file_limit=self.matches_limit_spin.value(),
            language=str(self.language_combo.currentData()),
            backup_enabled=self.backup_enabled_check.isChecked(),
            backup_path=self.backup_path_edit.text().strip() or str(self.paths.backups_dir),
            backup_retention_days=self.backup_retention_spin.value(),
            backup_max_size_mb=self.backup_max_size_spin.value(),
        )
        with self.database.session() as connection:
            save_settings(SettingsRepository(connection), settings)
            folder_repo = IndexFolderRepository(connection)
            folder_repo.sync_enabled(
                (folder, normalize_path(Path(folder))) for folder in settings.index_folders
            )
        self.settings = settings
        self.language_changed.emit(settings.language)
        self.settings_saved.emit(settings)
        self.accept()

    def _load_settings(self) -> ApplicationSettings:
        with self.database.session() as connection:
            settings = load_settings(SettingsRepository(connection), self.paths)
        return settings


def _spinbox(parent, minimum: int, maximum: int) -> QSpinBox:
    spinbox = QSpinBox(parent)
    spinbox.setRange(minimum, maximum)
    return spinbox


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _split_csv(text: str) -> list[str]:
    return [part.strip() for part in text.replace("\n", ",").split(",") if part.strip()]
