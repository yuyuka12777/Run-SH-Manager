"""Main window for the run-sh manager application."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..backend.manager import ScriptManager
from ..backend.models import ProcessStatus, ScriptProfile
from .log_viewer import LogViewerDialog
from .profile_dialog import ProfileDialog


class MainWindow(QMainWindow):
    """Primary GUI for interacting with the ScriptManager."""

    columns = [
        "名前",
        "状態",
        "PID",
        "CPU%",
        "メモリ(MB)",
        "自動起動",
        "再起動待機(s)",
        "起動遅延(s)",
        "再起動回数",
        "最終終了コード",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Run SH Manager")
        self.resize(1000, 600)
        try:
            self.manager = ScriptManager()
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "初期化エラー", f"プロファイルの読み込みに失敗しました:\n{exc}")
            raise
        self._build_ui()
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self.refresh_profiles)
        self._status_timer.start()
        self.refresh_profiles()
        self.manager.start_auto_profiles()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._create_actions()
        self._create_tool_bar()
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(QLabel("管理するスクリプト一覧"))
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addWidget(self.restart_button)
        buttons_layout.addWidget(self.view_log_button)
        layout.addLayout(buttons_layout)

        self.setCentralWidget(central)

    def _create_actions(self) -> None:
        self.add_action = QAction("追加", self)
        self.add_action.triggered.connect(self._add_profile)

        self.edit_action = QAction("編集", self)
        self.edit_action.triggered.connect(self._edit_profile)

        self.delete_action = QAction("削除", self)
        self.delete_action.triggered.connect(self._delete_profile)

        self.start_button = QPushButton("起動")
        self.start_button.clicked.connect(self._start_selected)

        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self._stop_selected)

        self.restart_button = QPushButton("再起動")
        self.restart_button.clicked.connect(self._restart_selected)

        self.view_log_button = QPushButton("ログ表示")
        self.view_log_button.clicked.connect(self._view_log)

        self.open_logs_action = QAction("ログディレクトリを開く", self)
        self.open_logs_action.triggered.connect(self._open_logs_dir)

        self.import_action = QAction("プロファイル読み込み", self)
        self.import_action.triggered.connect(self._import_profiles)

        self.export_action = QAction("プロファイル書き出し", self)
        self.export_action.triggered.connect(self._export_profiles)

        self.start_all_action = QAction("自動対象を起動", self)
        self.start_all_action.triggered.connect(self.manager.start_auto_profiles)

        self.stop_all_action = QAction("全て停止", self)
        self.stop_all_action.triggered.connect(self.manager.stop_all)

        self.autostart_action = QAction("ログイン時にアプリを起動", self)
        self.autostart_action.triggered.connect(self._create_autostart_entry)

    def _create_tool_bar(self) -> None:
        tool_bar = QToolBar("操作", self)
        tool_bar.addAction(self.add_action)
        tool_bar.addAction(self.edit_action)
        tool_bar.addAction(self.delete_action)
        tool_bar.addSeparator()
        tool_bar.addAction(self.start_all_action)
        tool_bar.addAction(self.stop_all_action)
        tool_bar.addSeparator()
        tool_bar.addAction(self.open_logs_action)
        tool_bar.addAction(self.import_action)
        tool_bar.addAction(self.export_action)
        tool_bar.addAction(self.autostart_action)
        self.addToolBar(Qt.TopToolBarArea, tool_bar)

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------
    def refresh_profiles(self) -> None:
        selected_name = self._selected_profile_name()
        profiles = self.manager.get_profiles()
        self.table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            status = self.manager.get_status(profile.name) or ProcessStatus(name=profile.name)
            usage = self.manager.get_resource_usage(profile.name)
            cpu_text = "--" if usage["cpu_percent"] is None else f"{usage['cpu_percent']:.1f}"
            mem_text = "--" if usage["memory_mb"] is None else f"{usage['memory_mb']:.1f}"
            values = [
                profile.name,
                status.state.value,
                str(status.pid or ""),
                cpu_text,
                mem_text,
                "はい" if profile.auto_start else "いいえ",
                f"{profile.restart_delay:.1f}",
                f"{profile.start_delay:.1f}",
                str(status.restarts),
                "" if status.last_exit_code is None else str(status.last_exit_code),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.UserRole, profile.name)
                if col == 1:
                    item.setData(Qt.UserRole + 1, status.state.value)
                self.table.setItem(row, col, item)
        self._restore_selection(selected_name)

    def _selected_profile_name(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.UserRole) or item.text()

    def _restore_selection(self, name: Optional[str]) -> None:
        if not name:
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and (item.data(Qt.UserRole) == name or item.text() == name):
                self.table.selectRow(row)
                break

    def _get_profile_by_name(self, name: str) -> Optional[ScriptProfile]:
        for profile in self.manager.get_profiles():
            if profile.name == name:
                return profile
        return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _add_profile(self) -> None:
        dialog = ProfileDialog(self)
        if dialog.exec() == QDialog.Accepted:
            profile = dialog.get_profile()
            if profile:
                try:
                    self.manager.add_profile(profile)
                    self.refresh_profiles()
                except Exception as exc:  # pylint: disable=broad-except
                    QMessageBox.warning(self, "追加エラー", str(exc))

    def _edit_profile(self) -> None:
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(self, "選択なし", "編集するプロファイルを選択してください。")
            return
        profile = self._get_profile_by_name(name)
        if not profile:
            return
        dialog = ProfileDialog(self, profile=profile)
        if dialog.exec() == QDialog.Accepted:
            updated = dialog.get_profile()
            if updated:
                try:
                    self.manager.update_profile(name, updated)
                    self.refresh_profiles()
                except Exception as exc:  # pylint: disable=broad-except
                    QMessageBox.warning(self, "更新エラー", str(exc))

    def _delete_profile(self) -> None:
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(self, "選択なし", "削除するプロファイルを選択してください。")
            return
        reply = QMessageBox.question(self, "確認", f"{name} を削除しますか？")
        if reply == QMessageBox.Yes:
            self.manager.remove_profile(name)
            self.refresh_profiles()

    def _start_selected(self) -> None:
        name = self._selected_profile_name()
        if name:
            self.manager.start_profile(name)
            QTimer.singleShot(500, self.refresh_profiles)

    def _stop_selected(self) -> None:
        name = self._selected_profile_name()
        if name:
            force = QMessageBox.question(
                self,
                "停止方法",
                "強制停止しますか？ (通常は\"いいえ\")",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            ) == QMessageBox.Yes
            self.manager.stop_profile(name, force=force)
            QTimer.singleShot(500, self.refresh_profiles)

    def _restart_selected(self) -> None:
        name = self._selected_profile_name()
        if name:
            self.manager.restart_profile(name)
            QTimer.singleShot(500, self.refresh_profiles)

    def _view_log(self) -> None:
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(self, "選択なし", "ログを表示するプロファイルを選択してください。")
            return
        profile = self._get_profile_by_name(name)
        if not profile or not profile.log_path:
            QMessageBox.information(self, "ログなし", "ログファイルが設定されていません。")
            return
        dialog = LogViewerDialog(Path(profile.log_path), parent=self)
        dialog.exec()

    def _open_logs_dir(self) -> None:
        logs_dir = self.manager.ensure_log_directory()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir)))

    def _import_profiles(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "プロファイルファイルを選択", filter="JSON Files (*.json)")
        if not path:
            return
        try:
            from ..backend.models import ScriptProfile

            data = json.loads(Path(path).read_text(encoding="utf-8"))
            for item in data:
                profile = ScriptProfile.from_dict(item)
                base_name = profile.name
                suffix = 1
                while True:
                    try:
                        self.manager.add_profile(profile)
                        break
                    except ValueError:
                        profile.name = f"{base_name}_{suffix}"
                        suffix += 1
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "読み込みエラー", str(exc))
        self.refresh_profiles()

    def _export_profiles(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存先を選択", filter="JSON Files (*.json)")
        if not path:
            return
        try:
            profiles = [profile.to_dict() for profile in self.manager.get_profiles()]
            Path(path).write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "書き出しエラー", str(exc))

    def _create_autostart_entry(self) -> None:
        autostart_dir = Path.home() / ".config/autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_path = autostart_dir / "run-sh-manager.desktop"
        if desktop_path.exists():
            overwrite = QMessageBox.question(
                self,
                "上書き確認",
                "既に自動起動エントリが存在します。上書きしますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if overwrite != QMessageBox.Yes:
                return
        content = """[Desktop Entry]
Type=Application
Name=Run SH Manager
Comment=Manage shell script services with auto restart
Exec=run-sh-manager
Icon=utilities-terminal
Terminal=false
X-GNOME-Autostart-enabled=true
"""
        desktop_path.write_text(content, encoding="utf-8")
        QMessageBox.information(self, "自動起動設定", f"{desktop_path} に自動起動設定を作成しました。")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        try:
            self.manager.save()
        except Exception:  # pragma: no cover - best effort
            traceback.print_exc()
        reply = QMessageBox.question(
            self,
            "終了確認",
            "アプリを終了すると監視は停止します。実行中のスクリプトを停止しますか？",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.No,
        )
        if reply == QMessageBox.Cancel:
            event.ignore()
            return
        if reply == QMessageBox.Yes:
            self.manager.stop_all()
        event.accept()
