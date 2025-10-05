"""Log viewer dialog."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
)


class LogViewerDialog(QDialog):
    """Simple dialog that tails a log file."""

    def __init__(self, log_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"ログビューア - {log_path.name}")
        self._log_path = log_path
        self._auto_refresh = True
        self._last_size = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh)
        self._build_ui()
        self._refresh(initial=True)
        self._timer.start()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(str(self._log_path)))
        open_external_btn = QPushButton("別ファイルを開く")
        open_external_btn.clicked.connect(self._open_other_file)
        info_layout.addWidget(open_external_btn)
        info_layout.addStretch(1)
        self.auto_refresh_check = QCheckBox("自動更新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.stateChanged.connect(self._toggle_auto_refresh)
        info_layout.addWidget(self.auto_refresh_check)
        main_layout.addLayout(info_layout)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        main_layout.addWidget(self.text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

    def _toggle_auto_refresh(self, state: int) -> None:
        self._auto_refresh = state != 0
        if self._auto_refresh:
            self._timer.start()
        else:
            self._timer.stop()

    def _refresh(self, initial: bool = False) -> None:
        if not self._auto_refresh and not initial:
            return
        if not self._log_path.exists():
            self.text_edit.setPlainText("ログファイルが見つかりません。")
            return
        data = self._log_path.read_bytes()
        if len(data) == self._last_size and not initial:
            return
        self._last_size = len(data)
        text = data.decode("utf-8", errors="replace")
        self.text_edit.setPlainText(text)
        self.text_edit.verticalScrollBar().setValue(self.text_edit.verticalScrollBar().maximum())

    def _open_other_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "ログファイルを開く")
        if path:
            self._log_path = Path(path)
            self.setWindowTitle(f"ログビューア - {self._log_path.name}")
            self._last_size = 0
            self._refresh(initial=True)
