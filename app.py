"""Application launcher for run-sh-manager."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .ui.main_window import MainWindow


def launch_app() -> None:
    """Launch the Qt application."""

    app = QApplication(sys.argv)
    app.setApplicationName("Run SH Manager")
    try:
        window = MainWindow()
    except Exception as exc:  # pylint: disable=broad-except
        QMessageBox.critical(None, "起動エラー", str(exc))
        sys.exit(1)
    window.show()
    app.exec()
