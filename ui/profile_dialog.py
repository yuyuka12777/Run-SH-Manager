"""Dialog for creating and editing script profiles."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QWidget,
)

from ..backend.models import ScriptProfile


def _dict_to_env_text(environment: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in environment.items())


def _env_text_to_dict(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        striped = line.strip()
        if not striped or striped.startswith("#"):
            continue
        if "=" not in striped:
            raise ValueError(f"環境変数の形式が正しくありません: '{striped}'")
        key, value = striped.split("=", 1)
        env[key.strip()] = value.strip()
    return env


class ProfileDialog(QDialog):
    """Modal dialog used to create or edit a ScriptProfile."""

    def __init__(self, parent: Optional[QWidget] = None, profile: Optional[ScriptProfile] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("プロファイル設定")
        self._original_profile = profile
        self._build_ui(profile)

    def _build_ui(self, profile: Optional[ScriptProfile]) -> None:
        layout = QFormLayout(self)

        self.name_edit = QLineEdit(profile.name if profile else "")
        layout.addRow("名前", self.name_edit)

        self.script_path_edit = QLineEdit(profile.script_path if profile else "")
        browse_script_btn = QPushButton("参照")
        browse_script_btn.clicked.connect(self._browse_script)
        script_layout = QHBoxLayout()
        script_layout.addWidget(self.script_path_edit)
        script_layout.addWidget(browse_script_btn)
        script_container = QWidget()
        script_container.setLayout(script_layout)
        layout.addRow("スクリプトパス", script_container)

        self.workdir_edit = QLineEdit(profile.working_dir if profile and profile.working_dir else "")
        browse_workdir_btn = QPushButton("参照")
        browse_workdir_btn.clicked.connect(self._browse_workdir)
        workdir_layout = QHBoxLayout()
        workdir_layout.addWidget(self.workdir_edit)
        workdir_layout.addWidget(browse_workdir_btn)
        workdir_container = QWidget()
        workdir_container.setLayout(workdir_layout)
        layout.addRow("作業ディレクトリ", workdir_container)

        self.log_path_edit = QLineEdit(profile.log_path if profile and profile.log_path else "")
        layout.addRow("ログファイル", self.log_path_edit)

        self.auto_start_check = QCheckBox("アプリ起動時に自動起動する")
        self.auto_start_check.setChecked(profile.auto_start if profile else False)
        layout.addRow(self.auto_start_check)

        self.restart_check = QCheckBox("終了時に自動再起動する")
        self.restart_check.setChecked(profile.restart_on_exit if profile else True)
        layout.addRow(self.restart_check)

        self.enabled_check = QCheckBox("プロファイルを有効化")
        self.enabled_check.setChecked(profile.enabled if profile else True)
        layout.addRow(self.enabled_check)

        self.restart_delay_spin = QDoubleSpinBox()
        self.restart_delay_spin.setMinimum(0.0)
        self.restart_delay_spin.setMaximum(3600.0)
        self.restart_delay_spin.setSuffix(" 秒")
        self.restart_delay_spin.setValue(profile.restart_delay if profile else 5.0)
        layout.addRow("再起動までの待機", self.restart_delay_spin)

        self.start_delay_spin = QDoubleSpinBox()
        self.start_delay_spin.setMinimum(0.0)
        self.start_delay_spin.setMaximum(3600.0)
        self.start_delay_spin.setSuffix(" 秒")
        self.start_delay_spin.setValue(profile.start_delay if profile else 0.0)
        layout.addRow("起動遅延", self.start_delay_spin)

        self.max_restarts_spin = QSpinBox()
        self.max_restarts_spin.setMinimum(0)
        self.max_restarts_spin.setMaximum(1000)
        self.max_restarts_spin.setSpecialValueText("無制限")
        self.max_restarts_spin.setValue(profile.max_restarts if profile and profile.max_restarts is not None else 0)
        layout.addRow("最大再起動回数", self.max_restarts_spin)

        self.env_edit = QPlainTextEdit()
        self.env_edit.setPlaceholderText("KEY=value 形式で1行ごとに入力")
        if profile:
            self.env_edit.setPlainText(_dict_to_env_text(profile.environment))
        layout.addRow(QLabel("環境変数"))
        layout.addRow(self.env_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _browse_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "スクリプトの選択")
        if path:
            self.script_path_edit.setText(path)

    def _browse_workdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "作業ディレクトリを選択")
        if path:
            self.workdir_edit.setText(path)

    def _on_accept(self) -> None:
        name = self.name_edit.text().strip()
        script_path = self.script_path_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前を入力してください。")
            return
        if not script_path:
            QMessageBox.warning(self, "入力エラー", "スクリプトパスを入力してください。")
            return
        try:
            environment = _env_text_to_dict(self.env_edit.toPlainText())
        except ValueError as exc:
            QMessageBox.warning(self, "環境変数エラー", str(exc))
            return
        max_restarts = self.max_restarts_spin.value()
        profile = ScriptProfile(
            name=name,
            script_path=script_path,
            working_dir=self.workdir_edit.text().strip() or None,
            auto_start=self.auto_start_check.isChecked(),
            restart_on_exit=self.restart_check.isChecked(),
            restart_delay=self.restart_delay_spin.value(),
            start_delay=self.start_delay_spin.value(),
            environment=environment,
            log_path=self.log_path_edit.text().strip() or None,
            max_restarts=max_restarts if max_restarts != 0 else None,
            enabled=self.enabled_check.isChecked(),
        )
        self._result_profile = profile
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_profile(self) -> Optional[ScriptProfile]:
        return getattr(self, "_result_profile", None)
