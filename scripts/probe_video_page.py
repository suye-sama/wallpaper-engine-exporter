"""Probe: native-resolution extraction + first-frame rendering on video widget."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from wallpaper_exporter.frame_extractor import VideoFrameExtractor
from wallpaper_exporter.indexer import WallpaperEntry
from wallpaper_exporter.video_page import VideoFramePage

VIDEO = Path(
    r"D:\GAME\steam\steamapps\workshop\content\431960\2680392402\HuTao-Genshin Impact.mp4"
)


def probe_native_resolution() -> None:
    app = QApplication.instance() or QApplication([])
    output_dir = Path(tempfile.mkdtemp(prefix="native_res_test_"))
    state = {"done": False, "files": [], "error": None}
    extractor = VideoFrameExtractor()
    extractor.finished.connect(lambda files: state.update(done=True, files=files))
    extractor.failed.connect(lambda msg: state.update(done=True, error=msg))
    extractor.start(VIDEO, [1000], output_dir, target_width=None)
    QTimer.singleShot(20_000, lambda: state.update(done=True, error="timeout"))
    while not state["done"]:
        app.processEvents()
    if state["error"]:
        print("native-resolution probe FAILED:", state["error"])
        return
    from PySide6.QtGui import QImage

    for path in state["files"]:
        image = QImage(str(path))
        print(f"native probe: {image.width()}x{image.height()} (source is 2560x1440)")


def probe_first_frame() -> None:
    app = QApplication.instance() or QApplication([])
    page = VideoFramePage()
    entry = WallpaperEntry(
        workshop_id="2680392402",
        title="probe",
        root=VIDEO.parent,
        project_type="video",
        main_file=VIDEO,
    )
    page.set_entries([entry])

    frames: list[int] = []
    sink = page.video_widget.videoSink()
    sink.videoFrameChanged.connect(lambda frame: frames.append(1))

    state = {"done": False}

    def kick() -> None:
        page.player.play()
        QTimer.singleShot(400, page.player.pause)
        QTimer.singleShot(2_000, lambda: state.update(done=True))

    QTimer.singleShot(500, kick)

    while not state["done"]:
        app.processEvents()

    print(
        "| poster shown first:", page.poster_label.text() or "pixmap",
        "| frames delivered while playing:", len(frames),
        "| stack on video:", page.player_stack.currentWidget() is page.video_widget,
        "| resolution:", page._video_resolution,
        "| final state:", page.player.playbackState(),
    )


if __name__ == "__main__":
    probe_native_resolution()
    probe_first_frame()
    sys.exit(0)
