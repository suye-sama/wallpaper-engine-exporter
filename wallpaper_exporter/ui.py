from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .exporter import ExportNeedsRenderCapture, ExportOptions, export_wallpaper
from .indexer import (
    DIRECT_IMAGE_SUFFIXES,
    DIRECT_VIDEO_SUFFIXES,
    WallpaperEntry,
    scan_workshop,
)
from .settings import AppSettings, load_settings
from .video_page import VideoFramePage


GRID_CARD_WIDTH = 180
GRID_CARD_HEIGHT = 218
GRID_GAP = 10
MAX_GRID_COLUMNS = 6
PREVIEW_SIZE = QSize(164, 92)


def grid_column_count(available_width: int) -> int:
    slots = max(
        1,
        (max(0, available_width) + GRID_GAP)
        // (GRID_CARD_WIDTH + GRID_GAP),
    )
    return min(MAX_GRID_COLUMNS, slots)


class WallpaperCard(QFrame):
    export_requested = Signal(object)

    def __init__(
        self,
        entry: WallpaperEntry,
        status: str,
        preview: QPixmap | None,
        preview_message: str,
    ) -> None:
        super().__init__()
        self.entry = entry
        self.setObjectName("wallpaperCard")
        self.setFixedSize(GRID_CARD_WIDTH, GRID_CARD_HEIGHT)
        self.setToolTip(f"{entry.title}\nID: {entry.workshop_id}\n{entry.root}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.preview_label = QLabel(preview_message)
        self.preview_label.setObjectName("cardPreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(PREVIEW_SIZE)
        if preview is not None:
            self.preview_label.setText("")
            self.preview_label.setPixmap(preview)
        layout.addWidget(self.preview_label)

        self.title_label = QLabel(entry.title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setFixedHeight(36)
        self.title_label.setToolTip(entry.title)
        layout.addWidget(self.title_label)

        self.status_label = QLabel(status)
        self.status_label.setObjectName("cardStatus")
        self.status_label.setFixedHeight(20)
        layout.addWidget(self.status_label)

        self.export_button = QPushButton("导出")
        self.export_button.setObjectName("cardExport")
        self.export_button.setEnabled(not bool(entry.error))
        self.export_button.clicked.connect(
            lambda: self.export_requested.emit(self.entry)
        )
        layout.addWidget(self.export_button)


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        auto_scan: bool = True,
    ) -> None:
        super().__init__()
        self.settings = settings
        self._auto_discover_paths = settings is None
        self.entries: list[WallpaperEntry] = []
        self.filtered_entries: list[WallpaperEntry] = []
        self.last_output_dir: Path | None = None
        self.cards: list[WallpaperCard] = []
        self._grid_columns = 0
        self._preview_cache: dict[tuple[Path, int, int], QPixmap | None] = {}

        self.setWindowTitle("Wallpaper 原图导出")
        self.resize(1180, 760)
        self._build_ui()
        self._apply_style()

        if auto_scan:
            self.scan_now()

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_gallery_page(), "壁纸导出")
        self.video_page = VideoFramePage()
        self.tabs.addTab(self.video_page, "视频帧截图")
        self.setCentralWidget(self.tabs)

        self.setStatusBar(QStatusBar())

    def _build_gallery_page(self) -> QWidget:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 10)
        outer.setSpacing(10)

        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索标题或 ID")
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_edit, 1)

        self.count_label = QLabel("0 项")
        self.count_label.setObjectName("muted")
        toolbar.addWidget(self.count_label)

        rescan_button = QPushButton("重新扫描")
        rescan_button.clicked.connect(self.scan_now)
        toolbar.addWidget(rescan_button)

        self.open_button = QPushButton("打开输出")
        self.open_button.clicked.connect(self.open_last_output)
        self.open_button.setEnabled(False)
        toolbar.addWidget(self.open_button)
        outer.addLayout(toolbar)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setObjectName("galleryScroll")
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery = QWidget()
        self.gallery.setObjectName("gallery")
        self.gallery_layout = QGridLayout(self.gallery)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_layout.setHorizontalSpacing(GRID_GAP)
        self.gallery_layout.setVerticalSpacing(GRID_GAP)
        self.gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.gallery_scroll.setWidget(self.gallery)
        outer.addWidget(self.gallery_scroll, 1)
        return root

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f6f7f9;
                color: #1f2937;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 13px;
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
            QScrollArea#galleryScroll {
                border: none;
                background: transparent;
            }
            QWidget#gallery {
                background: transparent;
            }
            QFrame#wallpaperCard {
                background: #ffffff;
                border: 1px solid #dfe3ea;
                border-radius: 6px;
            }
            QFrame#wallpaperCard:hover {
                border-color: #2f6fed;
            }
            QLabel#cardPreview {
                background: #111827;
                color: #e5e7eb;
                border-radius: 4px;
            }
            QLabel#cardTitle {
                color: #1f2937;
                font-weight: 600;
            }
            QLabel#cardStatus, QLabel#muted {
                color: #64748b;
            }
            QPushButton#cardExport {
                background: #2f6fed;
                border-color: #2f6fed;
                color: #ffffff;
            }
            QPushButton#cardExport:hover {
                background: #245bd0;
                border-color: #245bd0;
            }
            QPushButton#extractButton {
                background: #2f6fed;
                border-color: #2f6fed;
                color: #ffffff;
            }
            QPushButton#extractButton:hover {
                background: #245bd0;
                border-color: #245bd0;
            }
            QPushButton#extractButton:disabled {
                color: #f3f4f6;
                background: #9db8f5;
                border-color: #9db8f5;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: transparent;
                padding: 8px 18px;
            }
            QTabBar::tab:selected {
                color: #2f6fed;
                font-weight: 600;
                border-bottom: 2px solid #2f6fed;
            }
            QListWidget {
                background: #ffffff;
                border: 1px solid #dfe3ea;
                border-radius: 6px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #eaf1ff;
                color: #1f2937;
            }
            QGroupBox {
                border: 1px solid #dfe3ea;
                border-radius: 6px;
                margin-top: 10px;
                padding: 8px 8px 8px 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #64748b;
            }
            QWidget#videoSurface {
                background: #111827;
                border-radius: 4px;
            }
            QLabel#videoPoster {
                background: #111827;
                color: #e5e7eb;
                border-radius: 4px;
            }
            QSlider::groove:horizontal {
                height: 5px;
                background: #d1d5db;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #2f6fed;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #2f6fed;
                width: 12px;
                margin: -5px 0;
                border-radius: 5px;
            }
            """
        )

    def scan_now(self) -> None:
        if self._auto_discover_paths:
            self.settings = load_settings()
        assert self.settings is not None

        workshop_dir = self.settings.workshop_dir
        if workshop_dir is None or not workshop_dir.is_dir():
            self.entries = []
            self._apply_filter()
            self._sync_video_page()
            self.statusBar().showMessage(
                "找不到 Wallpaper Engine Workshop，已重新自动查找 Steam 库。"
            )
            return

        self.statusBar().showMessage("扫描中...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.entries = scan_workshop(workshop_dir)
            self._apply_filter()
            self._sync_video_page()
            self.statusBar().showMessage(f"扫描完成：{len(self.entries)} 项", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "扫描失败", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def _sync_video_page(self) -> None:
        self.video_page.set_settings(self.settings)
        self.video_page.set_entries(self.entries)

    def _apply_filter(self) -> None:
        text = self.search_edit.text().strip().lower()
        self.filtered_entries = [
            entry
            for entry in self.entries
            if not text
            or text in entry.title.lower()
            or text in entry.workshop_id.lower()
        ]
        self.count_label.setText(f"{len(self.filtered_entries)} 项")
        self._rebuild_grid()

    def _clear_grid(self) -> None:
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.cards = []

    def _preview_for_entry(self, entry: WallpaperEntry) -> tuple[QPixmap | None, str]:
        path = entry.preview_path
        if path is None or not path.is_file():
            return None, "没有预览"

        key = (path, PREVIEW_SIZE.width(), PREVIEW_SIZE.height())
        if key not in self._preview_cache:
            source = QPixmap(str(path))
            self._preview_cache[key] = (
                None
                if source.isNull()
                else source.scaled(
                    PREVIEW_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        preview = self._preview_cache[key]
        return (preview, "") if preview is not None else (None, "预览不可读")

    def _rebuild_grid(self) -> None:
        columns = grid_column_count(self.gallery_scroll.viewport().width())
        self._grid_columns = columns
        self._clear_grid()
        for index, entry in enumerate(self.filtered_entries):
            preview, preview_message = self._preview_for_entry(entry)
            card = WallpaperCard(
                entry,
                _status_for_entry(entry),
                preview,
                preview_message,
            )
            card.export_requested.connect(self.export_entry)
            self.cards.append(card)
            self.gallery_layout.addWidget(card, index // columns, index % columns)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._rebuild_grid()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not hasattr(self, "gallery_scroll"):
            return
        columns = grid_column_count(self.gallery_scroll.viewport().width())
        if columns != self._grid_columns:
            self._rebuild_grid()

    def export_entry(self, entry: WallpaperEntry) -> None:
        try:
            result = self._run_export(entry, ExportOptions(allow_render_capture=False))
        except ExportNeedsRenderCapture as exc:
            answer = QMessageBox.question(
                self,
                "需要抓图",
                f"{entry.title}\n\n{exc}\n\n是否打开 Wallpaper Engine 连拍候选帧？",
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
        assert self.settings is not None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            return export_wallpaper(entry, self.settings, options)
        finally:
            QApplication.restoreOverrideCursor()

    def open_last_output(self) -> None:
        if not self.last_output_dir:
            return
        os.startfile(self.last_output_dir)


def _status_for_entry(entry: WallpaperEntry) -> str:
    if entry.error:
        return "无法读取"
    if entry.main_file and entry.main_file.suffix.lower() in DIRECT_IMAGE_SUFFIXES:
        return "直接图片"
    if entry.main_file and entry.main_file.suffix.lower() in DIRECT_VIDEO_SUFFIXES:
        return "直接视频"
    if entry.has_scene_json:
        return "可尝试静态合成"
    if entry.has_scene_pkg:
        return "需要 RePKG"
    return "待判断"


def run_app() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


def open_in_file_manager(path: Path) -> None:
    subprocess.Popen(["explorer", str(path)])
