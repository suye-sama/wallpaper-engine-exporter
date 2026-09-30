"""Probe: drag slider on the real page -> preroll renders the seeked frame."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QVideoSink
from PySide6.QtWidgets import QApplication

from wallpaper_exporter.discovery import discover_wallpaper_paths
from wallpaper_exporter.indexer import scan_workshop
from wallpaper_exporter.video_page import VideoFramePage, video_entries


def main() -> None:
    app = QApplication([])
    detected = discover_wallpaper_paths()
    entries = video_entries(scan_workshop(detected.workshop_dir))
    video = next((e for e in entries if e.main_file), None)
    if video is None:
        print("FAILED: no video entries")
        return

    page = VideoFramePage()
    frames: list = []
    sink = QVideoSink()
    sink.videoFrameChanged.connect(lambda f: frames.append(f))
    page.player.setVideoSink(sink)

    page.set_entries([video])
    state = {"seeked": False, "done": False}

    def seek() -> None:
        if page._duration > 0 and not state["seeked"]:
            state["seeked"] = True
            page.position_slider.setValue(min(2000, page._duration - 1))
            page._on_slider_released()
            QTimer.singleShot(2000, lambda: state.update(done=True))

    QTimer.singleShot(2500, seek)
    QTimer.singleShot(10000, lambda: state.update(done=True))
    while not state["done"]:
        app.processEvents()

    valid = [f for f in frames if f.isValid()]
    print(
        "duration:", page._duration,
        "| seeked:", state["seeked"],
        "| stack on video:", page.player_stack.currentWidget() is page.video_widget,
        "| frames rendered:", len(valid),
        "| muted after:", page.audio_output.isMuted(),
        "| state:", page.player.playbackState(),
    )


if __name__ == "__main__":
    main()
