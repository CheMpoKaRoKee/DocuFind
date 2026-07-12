"""Application-wide UI polish."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget


def apply_theme(widget: QWidget) -> None:
    widget.setStyleSheet(STYLESHEET)
    app = QApplication.instance()
    if app is not None:
        app.setStyle("Fusion")


STYLESHEET = """
QMainWindow, QWidget {
    background: #202124;
    color: #f1f3f4;
    font-size: 12px;
}

QToolBar {
    background: #191a1d;
    border: 0;
    border-bottom: 1px solid #34363a;
    padding: 6px 8px;
    spacing: 8px;
}

QSplitter::handle {
    background: #34363a;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QLabel#resultsTitleLabel,
QLabel#previewTitleLabel {
    color: #ffffff;
    font-weight: 600;
}

QLabel#indexStateLabel,
QLabel#indexProgressDetailsLabel,
QLabel#previewMetaLabel,
QLabel#editorStatusLabel {
    color: #d6d9de;
}

QLabel#indexProgressStatusLabel {
    color: #ffffff;
    font-weight: 600;
}

QLabel#previewStaleLabel {
    color: #ffcf70;
}

QLineEdit, QTextEdit, QComboBox, QListWidget {
    background: #2b2d31;
    color: #f1f3f4;
    border: 1px solid #45484f;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #6ea8fe;
    selection-color: #101214;
}

QTextEdit#previewEdit,
QTextEdit#editorTextEdit {
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 12px;
}

QPushButton {
    background: #303238;
    color: #f1f3f4;
    border: 1px solid #50535b;
    border-radius: 6px;
    padding: 6px 10px;
}

QPushButton:hover {
    background: #383b42;
}

QPushButton:pressed {
    background: #454951;
}

QPushButton:disabled {
    background: #25272b;
    color: #858b96;
    border-color: #34363a;
}

QPushButton#clearIndexButton {
    color: #ffd6d6;
}

QProgressBar {
    background: #2b2d31;
    border: 1px solid #45484f;
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
    text-align: center;
}

QProgressBar::chunk {
    background: #8ab4f8;
    border-radius: 5px;
}

QListWidget::item {
    padding: 10px;
    border-bottom: 1px solid #34363a;
}

QListWidget::item:selected {
    background: #3f5f8f;
    color: #ffffff;
}

QListWidget#resultsList::item {
    padding: 0;
    margin: 0;
}

QWidget#resultRow,
QLabel#resultSummaryLabel {
    background: transparent;
    border: 0;
}

QTabWidget::pane {
    border: 1px solid #34363a;
    border-radius: 6px;
}

QTabBar::tab {
    background: #25272b;
    color: #d6d9de;
    border: 1px solid #34363a;
    padding: 7px 12px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background: #303238;
    color: #ffffff;
}
"""
