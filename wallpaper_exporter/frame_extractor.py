from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink

from .paths import frames_folder_for

FRAME_TIMEOUT_MS = 4000
SEEK_POSITION_TOLERANCE_MS = 250


def compute_timestamps(
    start_ms: int,
    duration_ms: int | None,
    interval_s: float,
    count: int,
) -> list[int]:
    """Compute millisecond timestamps for frame extraction.

    Starts at ``start_ms`` and takes ``count`` frames spaced by
    ``interval_s`` seconds. Timestamps at or beyond ``duration_ms`` are
    dropped; a missing (``None``/non-positive) duration disables the check.
    """

    if count < 1:
        raise ValueError("frame count must be at least 1")
    if interval_s <= 0:
        raise ValueError("sampling interval must be positive")
    if start_ms < 0:
        raise ValueError("start position must not be negative")

    step_ms = max(1, round(interval_s * 1000))
    timestamps = [start_ms + index * step_ms for index in range(count)]
    if duration_ms is not None and duration_ms > 0:
        timestamps = [ts for ts in timestamps if ts < duration_ms]
    return timestamps


def frame_filename(index: int) -> str:
    if index < 1:
        raise ValueError("frame index starts at 1")
    return f"frame_{index:03d}.png"


def scaled_size(
    frame_size: tuple[int, int], target_width: int | None
) -> tuple[int, int]:
    """Scale ``frame_size`` to ``target_width`` keeping the aspect ratio."""

    width, height = frame_size
    if width <= 0 or height <= 0:
        raise ValueError("frame size must be positive")
    if not target_width or target_width <= 0:
        return width, height
    scaled_height = max(1, round(height * target_width / width))
    return target_width, scaled_height


class VideoFrameExtractor(QObject):
    """Extract still frames from a video by seeking with QMediaPlayer.

    Signal-driven and non-blocking: run inside the Qt event loop, listen to
    ``progress``/``finished``/``failed``.
    """

    progress = Signal(int, int)  # completed frames, total frames
    finished = Signal(list)  # saved file paths
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._sink = QVideoSink(self)
        self._player.setVideoSink(self._sink)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._player.errorOccurred.connect(self._on_player_error)
        self._sink.videoFrameChanged.connect(self._on_frame_changed)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_frame_timeout)

        self._active = False
        self._waiting_for_load = False
        self._timestamps: list[int] = []
        self._target_ms = 0
        self._index = 0
        self._target_width: int | None = None
        self._output_dir = Path()
        self._saved: list[Path] = []

    # -- public API ---------------------------------------------------------

    def start(
        self,
        video_path: Path,
        timestamps: list[int],
        output_dir: Path,
        target_width: int | None = None,
    ) -> bool:
        """Begin extraction; returns False if already running."""

        if self._active:
            return False
        if not timestamps:
            self.failed.emit("没有可提取的帧")
            return False

        self._active = True
        self._timestamps = list(timestamps)
        self._index = 0
        self._saved = []
        self._target_width = target_width
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._waiting_for_load = True
        self._player.setSource(QUrl.fromLocalFile(str(video_path)))
        return True

    def cancel(self) -> None:
        if not self._active:
            return
        self._stop()
        self.failed.emit("已取消提取")

    # -- internals ----------------------------------------------------------

    def _stop(self) -> None:
        self._timer.stop()
        self._active = False
        self._waiting_for_load = False
        self._player.pause()
        self._player.setSource(QUrl())

    def _on_media_status(self, status) -> None:
        if not self._active or not self._waiting_for_load:
            return
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._waiting_for_load = False
            self._begin_frame()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._stop()
            self.failed.emit("无法加载视频（可能是缺少对应的解码器）")

    def _on_player_error(self, error, message: str) -> None:
        if not self._active:
            return
        self._stop()
        self.failed.emit(f"视频播放出错：{message or error}")

    def _begin_frame(self) -> None:
        self._target_ms = self._timestamps[self._index]
        self._player.pause()
        self._player.setPosition(self._target_ms)
        self._timer.start(FRAME_TIMEOUT_MS)

    def _on_frame_changed(self, frame) -> None:
        if not self._active or self._waiting_for_load:
            return
        if abs(self._player.position() - self._target_ms) > SEEK_POSITION_TOLERANCE_MS:
            return  # stale frame from before the seek settled

        image = frame.toImage()
        if image.isNull():
            return
        self._save_image(image)

    def _on_frame_timeout(self) -> None:
        if not self._active:
            return
        image = self._sink.videoFrame().toImage()
        if not image.isNull():
            self._save_image(image)
            return
        self._advance()

    def _save_image(self, image: QImage) -> None:
        if self._target_width and self._target_width > 0:
            image = image.scaledToWidth(
                self._target_width,
                Qt.TransformationMode.SmoothTransformation,
            )
        output_path = self._output_dir / frame_filename(self._index + 1)
        if not image.save(str(output_path), "PNG"):
            self._advance()
            return
        self._saved.append(output_path)
        self._advance()

    def _advance(self) -> None:
        self._index += 1
        self.progress.emit(min(self._index, len(self._timestamps)), len(self._timestamps))
        if self._index >= len(self._timestamps):
            saved = list(self._saved)
            self._stop()
            if saved:
                self.finished.emit(saved)
            else:
                self.failed.emit("未能从视频中提取到任何帧（可能是解码器不支持该格式）")
            return
        self._begin_frame()


def default_output_folder(export_root: Path, title: str) -> Path:
    return frames_folder_for(export_root, title)
