from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .exporter import ExportNeedsRenderCapture, ExportOptions, export_wallpaper
from .indexer import WallpaperEntry, scan_workshop
from .settings import AppSettings, load_settings, save_settings


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.workshop_edit = QLineEdit(str(settings.workshop_dir))
        self.export_edit = QLineEdit(str(settings.export_root))
        self.repkg_edit = QLineEdit(str(settings.repkg_path))
        self.wallpaper_edit = QLineEdit(str(settings.wallpaper_exe))

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Workshop", _path_row(self.workshop_edit, self._choose_workshop))
        form.addRow("导出根目录", _path_row(self.export_edit, self._choose_export_root))
        form.addRow("RePKG.exe", _path_row(self.repkg_edit, self._choose_repkg))
        form.addRow("wallpaper64.exe", _path_row(self.wallpaper_edit, self._choose_wallpaper))
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("保存")
        save_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def settings(self) -> AppSettings:
        return AppSettings(
            workshop_dir=Path(self.workshop_edit.text().strip()),
            export_root=Path(self.export_edit.text().strip()),
            repkg_path=Path(self.repkg_edit.text().strip()),
            wallpaper_exe=Path(self.wallpaper_edit.text().strip()),
        )

    def _choose_workshop(self) -> None:
        _choose_dir_into(self, self.workshop_edit)

    def _choose_export_root(self) -> None:
        _choose_dir_into(self, self.export_edit)

    def _choose_repkg(self) -> None:
        _choose_file_into(self, self.repkg_edit, "RePKG.exe (*.exe)")

    def _choose_wallpaper(self) -> None:
        _choose_file_into(self, self.wallpaper_edit, "wallpaper64.exe (*.exe)")


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        auto_scan: bool = True,
    ) -> None:
        super().__init__()
        self.settings = settings or load_settings()
        self.entries: list[WallpaperEntry] = []
        self.filtered_entries: list[WallpaperEntry] = []
        self.last_output_dir: Path | None = None

        self.setWindowTitle("Wallpaper 原图导出")
        self.resize(1180, 760)
        self._build_ui()
        self._apply_style()

        if auto_scan:
            self.scan_now()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 10)
        outer.setSpacing(10)

        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索标题或 ID")
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_edit, 1)

        rescan_button = QPushButton("重新扫描")
        rescan_button.clicked.connect(self.scan_now)
        settings_button = QPushButton("设置")
        settings_button.clicked.connect(self.open_settings)
        toolbar.addWidget(rescan_button)
        toolbar.addWidget(settings_button)
        outer.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)

        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        self.count_label = QLabel("0 项")
        self.count_label.setObjectName("muted")
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._selection_changed)
        left_layout.addWidget(self.count_label)
        left_layout.addWidget(self.list_widget, 1)
        splitter.addWidget(left_panel)

        detail_panel = QFrame()
        detail_panel.setObjectName("panel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(10)

        self.preview_label = QLabel("没有预览")
        self.preview_label.setObjectName("preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(560, 315)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        detail_layout.addWidget(self.preview_label, 1)

        self.title_label = QLabel("未选择")
        self.title_label.setObjectName("title")
        self.title_label.setWordWrap(True)
        self.status_strip = QLabel("等待选择")
        self.status_strip.setObjectName("statusStrip")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("detail")
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_label.setWordWrap(True)
        detail_layout.addWidget(self.title_label)
        detail_layout.addWidget(self.status_strip)
        detail_layout.addWidget(self.detail_label)

        actions = QHBoxLayout()
        self.export_button = QPushButton("导出选中")
        self.export_button.clicked.connect(self.export_selected)
        self.open_button = QPushButton("打开输出")
        self.open_button.clicked.connect(self.open_last_output)
        self.open_button.setEnabled(False)
        actions.addStretch(1)
        actions.addWidget(self.open_button)
        actions.addWidget(self.export_button)
        detail_layout.addLayout(actions)
        splitter.addWidget(detail_panel)
        splitter.setSizes([340, 820])

        self.setStatusBar(QStatusBar())

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f7f9;
                color: #1f2937;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
            }
            QFrame#panel {
                background: #ffffff;
                border: 1px solid #dfe3ea;
                border-radius: 8px;
            }
            QListWidget {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                outline: none;
            }
            QListWidget::item {
                min-height: 34px;
                padding: 6px 8px;
            }
            QListWidget::item:selected {
                background: #dbeafe;
                color: #1f2937;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 7px 9px;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 12px;
            }
            QPushButton:hover {
                border-color: #2f6fed;
            }
            QPushButton:pressed {
                background: #eaf1ff;
            }
            QPushButton:disabled {
                color: #9ca3af;
                background: #f3f4f6;
            }
            QLabel#preview {
                background: #111827;
                color: #e5e7eb;
                border-radius: 8px;
            }
            QLabel#title {
                font-size: 20px;
                font-weight: 650;
            }
            QLabel#muted, QLabel#detail {
                color: #6b7280;
            }
            QLabel#statusStrip {
                background: #eef4ff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
                border-radius: 6px;
                padding: 7px 9px;
            }
            """
        )

    def scan_now(self) -> None:
        self.statusBar().showMessage("扫描中...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.entries = scan_workshop(self.settings.workshop_dir)
            self._apply_filter()
            self.statusBar().showMessage(f"扫描完成：{len(self.entries)} 项", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "扫描失败", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def _apply_filter(self) -> None:
        text = self.search_edit.text().strip().lower()
        self.filtered_entries = [
            entry
            for entry in self.entries
            if not text
            or text in entry.title.lower()
            or text in entry.workshop_id.lower()
        ]
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for entry in self.filtered_entries:
            item = QListWidgetItem(f"{entry.title}\n{entry.workshop_id}")
            item.setToolTip(str(entry.root))
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        self.count_label.setText(f"{len(self.filtered_entries)} 项")
        if self.filtered_entries:
            self.list_widget.setCurrentRow(0)
            self._show_entry(self.filtered_entries[0])
        else:
            self._clear_selection()

    def _selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.filtered_entries):
            self._clear_selection()
            return
        self._show_entry(self.filtered_entries[row])

    def _show_entry(self, entry: WallpaperEntry) -> None:
        self.title_label.setText(entry.title)
        self.status_strip.setText(_status_for_entry(entry))
        details = [
            f"ID: {entry.workshop_id}",
            f"类型: {entry.project_type or 'unknown'}",
            f"路径: {entry.root}",
        ]
        if entry.error:
            details.append(f"错误: {entry.error}")
        self.detail_label.setText("\n".join(details))
        self._load_preview(entry.preview_path)
        self.export_button.setEnabled(not bool(entry.error))

    def _clear_selection(self) -> None:
        self.title_label.setText("未选择")
        self.status_strip.setText("等待选择")
        self.detail_label.setText("")
        self.preview_label.setText("没有预览")
        self.preview_label.setPixmap(QPixmap())
        self.export_button.setEnabled(False)

    def _load_preview(self, path: Path | None) -> None:
        self.preview_label.setPixmap(QPixmap())
        if not path or not path.exists():
            self.preview_label.setText("没有预览")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.preview_label.setText("预览不可读")
            return
        self.preview_label.setText("")
        self.preview_label.setPixmap(
            pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.filtered_entries):
            self._load_preview(self.filtered_entries[row].preview_path)

    def selected_entry(self) -> WallpaperEntry | None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.filtered_entries):
            return None
        return self.filtered_entries[row]

    def export_selected(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            return
        try:
            result = self._run_export(entry, ExportOptions(allow_render_capture=False))
        except ExportNeedsRenderCapture as exc:
            answer = QMessageBox.question(
                self,
                "需要抓图",
                f"{entry.title}\n\n{exc}\n\n是否打开 Wallpaper Engine 抓取一帧？",
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage("已取消抓图", 5000)
                return
            result = self._run_export(entry, ExportOptions(allow_render_capture=True))
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return

        self.last_output_dir = result.output_dir
        self.open_button.setEnabled(True)
        self.statusBar().showMessage(f"导出完成：{result.output_dir}", 8000)
        QMessageBox.information(self, "导出完成", str(result.output_dir))

    def _run_export(
        self, entry: WallpaperEntry, options: ExportOptions
    ):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            return export_wallpaper(entry, self.settings, options)
        finally:
            QApplication.restoreOverrideCursor()

    def open_last_output(self) -> None:
        if not self.last_output_dir:
            return
        os.startfile(self.last_output_dir)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.settings = dialog.settings()
        save_settings(self.settings)
        self.scan_now()


def _status_for_entry(entry: WallpaperEntry) -> str:
    if entry.error:
        return "无法读取"
    if entry.main_file and entry.main_file.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        return "直接图片"
    if entry.has_scene_json:
        return "可尝试静态合成"
    if entry.has_scene_pkg:
        return "需要 RePKG"
    return "待判断"


def _path_row(edit: QLineEdit, callback) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(edit, 1)
    button = QPushButton("浏览")
    button.clicked.connect(callback)
    layout.addWidget(button)
    return row


def _choose_dir_into(parent: QWidget, edit: QLineEdit) -> None:
    value = QFileDialog.getExistingDirectory(parent, "选择目录", edit.text())
    if value:
        edit.setText(value)


def _choose_file_into(parent: QWidget, edit: QLineEdit, file_filter: str) -> None:
    value, _selected_filter = QFileDialog.getOpenFileName(
        parent, "选择文件", edit.text(), file_filter
    )
    if value:
        edit.setText(value)


def run_app() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


def open_in_file_manager(path: Path) -> None:
    subprocess.Popen(["explorer", str(path)])
