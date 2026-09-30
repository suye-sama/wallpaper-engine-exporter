from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSplitter,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .frame_extractor import VideoFrameExtractor, compute_timestamps, scaled_size
from .indexer import DIRECT_VIDEO_SUFFIXES, WallpaperEntry
from .paths import frames_folder_for
from .settings import AppSettings

LIST_ICON_SIZE = QSize(72, 40)


def format_time(ms: int) -> str:
    total_seconds = max(0, int(round(ms / 1000)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def video_entries(entries: list[WallpaperEntry]) -> list[WallpaperEntry]:
    return [
        entry
        for entry in entries
        if not entry.error
        and entry.main_file is not None
        and entry.main_file.suffix.lower() in DIRECT_VIDEO_SUFFIXES
        and entry.main_file.exists()
    ]


class VideoFramePage(QWidget):
    """视频壁纸浏览 + 播放定位 + 按参数提取视频帧的独立页面。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings: AppSettings | None = None
        self.entries: list[WallpaperEntry] = []
        self.filtered_entries: list[WallpaperEntry] = []
        self.current_entry: WallpaperEntry | None = None
        self._dragging_slider = False
        self._extractor: VideoFrameExtractor | None = None
        self._last_output_dir: Path | None = None
        self._duration = 0
        self._video_resolution: tuple[int, int] | None = None
        self._auto_previewing = False
        self._auto_pause_token = 0

        self._build_ui()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_list_panel())
        splitter.addWidget(self._build_player_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 820])
        layout.addWidget(splitter, 1)

    def _build_list_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索视频标题或 ID")
        self.search_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_edit)

        self.count_label = QLabel("0 个视频")
        self.count_label.setObjectName("muted")
        layout.addWidget(self.count_label)

        self.video_list = QListWidget()
        self.video_list.setIconSize(LIST_ICON_SIZE)
        self.video_list.setUniformItemSizes(True)
        self.video_list.currentRowChanged.connect(self._on_current_row_changed)
        layout.addWidget(self.video_list, 1)

        return panel

    def _build_player_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.video_widget = QVideoWidget()
        self.video_widget.setObjectName("videoSurface")
        layout.addWidget(self.video_widget, 1)

        controls = QHBoxLayout()
        self.play_button = QPushButton("播放")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self._toggle_playback)
        controls.addWidget(self.play_button)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setEnabled(False)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        controls.addWidget(self.position_slider, 1)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("muted")
        controls.addWidget(self.time_label)
        layout.addLayout(controls)

        params = QGroupBox("提取参数")
        params_layout = QHBoxLayout(params)
        params_layout.setSpacing(10)

        params_layout.addWidget(QLabel("采样间隔"))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600.0)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSuffix(" 秒")
        params_layout.addWidget(self.interval_spin)

        params_layout.addWidget(QLabel("帧总数"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 60)
        self.count_spin.setValue(5)
        self.count_spin.setSuffix(" 张")
        params_layout.addWidget(self.count_spin)

        params_layout.addWidget(QLabel("图片大小"))
        self.size_combo = QComboBox()
        self.size_combo.addItem("原始尺寸", None)
        self.size_combo.addItem("自定义宽度", "custom")
        self.size_combo.currentIndexChanged.connect(self._on_size_mode_changed)
        params_layout.addWidget(self.size_combo)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(16, 7680)
        self.width_spin.setValue(1920)
        self.width_spin.setSuffix(" px")
        self.width_spin.setEnabled(False)
        self.width_spin.setVisible(False)
        self.width_spin.valueChanged.connect(self._update_output_hint)
        params_layout.addWidget(self.width_spin)

        params_layout.addStretch(1)

        self.output_size_label = QLabel("")
        self.output_size_label.setObjectName("muted")
        params_layout.addWidget(self.output_size_label)
        layout.addWidget(params)

        hint = QLabel("从当前播放进度开始，按采样间隔依次截取指定数量的帧。")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        actions = QHBoxLayout()
        self.extract_button = QPushButton("提取视频帧")
        self.extract_button.setObjectName("extractButton")
        self.extract_button.setEnabled(False)
        self.extract_button.clicked.connect(self._extract_frames)
        actions.addWidget(self.extract_button)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        actions.addWidget(self.result_label, 1)

        self.open_button = QPushButton("打开输出")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_last_output)
        actions.addWidget(self.open_button)
        layout.addLayout(actions)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.7)
        self.player.setVideoOutput(self.video_widget)
        self.player.setAudioOutput(self.audio_output)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_player_error)

        return panel

    # -- data ---------------------------------------------------------------

    def set_settings(self, settings: AppSettings | None) -> None:
        self.settings = settings

    def set_entries(self, entries: list[WallpaperEntry]) -> None:
        self.entries = video_entries(entries)
        if self.current_entry is not None and self.current_entry not in self.entries:
            self._unload_current()
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self.search_edit.text().strip().lower()
        self.filtered_entries = [
            entry
            for entry in self.entries
            if not text
            or text in entry.title.lower()
            or text in entry.workshop_id.lower()
        ]
        self.count_label.setText(f"{len(self.filtered_entries)} 个视频")

        self.video_list.blockSignals(True)
        self.video_list.clear()
        for entry in self.filtered_entries:
            item = QListWidgetItem(self._icon_for_entry(entry), entry.title)
            item.setToolTip(f"{entry.title}\nID: {entry.workshop_id}\n{entry.main_file}")
            self.video_list.addItem(item)
        self.video_list.blockSignals(False)

        if self.filtered_entries:
            keep = self.video_list.currentRow()
            if keep < 0 or keep >= len(self.filtered_entries):
                keep = 0
            self.video_list.setCurrentRow(keep)
        else:
            self._unload_current()

    def _icon_for_entry(self, entry: WallpaperEntry) -> QIcon:
        if entry.preview_path and entry.preview_path.is_file():
            pixmap = QPixmap(str(entry.preview_path))
            if not pixmap.isNull():
                return QIcon(
                    pixmap.scaled(
                        LIST_ICON_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        return QIcon()

    # -- preview playback ----------------------------------------------------

    def _on_current_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self.filtered_entries):
            return
        entry = self.filtered_entries[row]
        if entry is self.current_entry:
            return
        self.current_entry = entry
        self.player.setSource(QUrl.fromLocalFile(str(entry.main_file)))
        self.play_button.setEnabled(True)
        self._update_extract_enabled()

    def _unload_current(self) -> None:
        self.current_entry = None
        self._cancel_auto_preview()
        self.player.setSource(QUrl())
        self.play_button.setEnabled(False)
        self.play_button.setText("播放")
        self._duration = 0
        self._video_resolution = None
        self._update_output_hint()
        self.position_slider.setRange(0, 0)
        self._update_extract_enabled()

    def _toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self._cancel_auto_preview()
            self.player.play()

    def _on_media_status(self, status) -> None:
        if status != QMediaPlayer.MediaStatus.LoadedMedia:
            return
        self._read_video_resolution()
        if self.current_entry is not None:
            self._show_first_frame()

    def _read_video_resolution(self) -> None:
        size = self.player.metaData().value(QMediaMetaData.Key.Resolution)
        self._video_resolution = (
            (size.width(), size.height()) if size and size.width() > 0 else None
        )
        self._update_output_hint()

    def _show_first_frame(self) -> None:
        """Briefly play then pause so the first frame appears instead of a black panel."""

        self._auto_previewing = True
        self._auto_pause_token += 1
        token = self._auto_pause_token
        self.audio_output.setMuted(True)
        self.player.play()
        QTimer.singleShot(250, lambda: self._finish_auto_preview(token))

    def _finish_auto_preview(self, token: int) -> None:
        if token != self._auto_pause_token or not self._auto_previewing:
            return
        self._auto_previewing = False
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        self.audio_output.setMuted(False)

    def _cancel_auto_preview(self) -> None:
        self._auto_previewing = False
        self._auto_pause_token += 1
        self.audio_output.setMuted(False)

    def _on_playback_state_changed(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText("暂停" if playing else "播放")

    def _on_duration_changed(self, duration: int) -> None:
        self._duration = max(0, duration)
        self.position_slider.setRange(0, self._duration)
        self._update_time_label()
        self._update_extract_enabled()

    def _on_position_changed(self, position: int) -> None:
        if not self._dragging_slider:
            self.position_slider.setValue(position)
        self._update_time_label()

    def _on_slider_pressed(self) -> None:
        self._dragging_slider = True

    def _on_slider_moved(self, position: int) -> None:
        self._update_time_label(position)

    def _on_slider_released(self) -> None:
        self._dragging_slider = False
        self.player.setPosition(self.position_slider.value())

    def _on_player_error(self, error, message: str) -> None:
        if message:
            self.result_label.setText(f"预览失败：{message}")

    def _update_time_label(self, position: int | None = None) -> None:
        if position is None:
            position = (
                self.position_slider.value() if self._dragging_slider else self.player.position()
            )
        self.time_label.setText(f"{format_time(position)} / {format_time(self._duration)}")

    # -- extraction ------------------------------------------------------------

    def _on_size_mode_changed(self) -> None:
        custom = self.size_combo.currentIndex() == 1
        self.width_spin.setEnabled(custom)
        self.width_spin.setVisible(custom)
        self._update_output_hint()

    def _update_output_hint(self) -> None:
        if not self._video_resolution:
            self.output_size_label.setText("")
            return
        width, height = self._video_resolution
        if self.size_combo.currentIndex() == 1:
            out_width, out_height = scaled_size(
                self._video_resolution, self.width_spin.value()
            )
            self.output_size_label.setText(f"{width}×{height} → {out_width}×{out_height}")
        else:
            self.output_size_label.setText(f"{width}×{height}（原始）")

    def _extract_enabled(self) -> bool:
        return (
            self.current_entry is not None
            and self.current_entry.main_file is not None
            and self._duration > 0
            and self._extractor is None
        )

    def _update_extract_enabled(self) -> None:
        self.extract_button.setEnabled(self._extract_enabled())

    def _extract_frames(self) -> None:
        if not self._extract_enabled():
            return
        assert self.settings is not None
        assert self.current_entry is not None and self.current_entry.main_file is not None

        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()

        start_ms = self.position_slider.value()
        try:
            timestamps = compute_timestamps(
                start_ms,
                self._duration,
                self.interval_spin.value(),
                self.count_spin.value(),
            )
        except ValueError as exc:
            self.result_label.setText(str(exc))
            return
        if not timestamps:
            self.result_label.setText("当前进度之后没有可提取的帧。")
            return

        target_width = (
            self.width_spin.value()
            if self.size_combo.currentIndex() == 1
            else None
        )
        output_dir = frames_folder_for(
            self.settings.export_root, self.current_entry.title
        )

        extractor = VideoFrameExtractor(self)
        extractor.progress.connect(self._on_extract_progress)
        extractor.finished.connect(self._on_extract_finished)
        extractor.failed.connect(self._on_extract_failed)
        self._extractor = extractor
        self._update_extract_enabled()
        self.result_label.setText(f"提取中 0/{len(timestamps)} ...")

        if not extractor.start(
            self.current_entry.main_file, timestamps, output_dir, target_width
        ):
            self._extractor = None
            self._update_extract_enabled()

    def _on_extract_progress(self, done: int, total: int) -> None:
        self.result_label.setText(f"提取中 {done}/{total} ...")

    def _on_extract_finished(self, files: list) -> None:
        self._finish_extraction()
        if files:
            self._last_output_dir = Path(files[0]).parent
            self.open_button.setEnabled(True)
            self.result_label.setText(
                f"已保存 {len(files)} 帧到 {self._last_output_dir}"
            )

    def _on_extract_failed(self, message: str) -> None:
        self._finish_extraction()
        self.result_label.setText(message)

    def _finish_extraction(self) -> None:
        if self._extractor is not None:
            self._extractor.deleteLater()
            self._extractor = None
        self._update_extract_enabled()

    def open_last_output(self) -> None:
        if self._last_output_dir:
            os.startfile(self._last_output_dir)
