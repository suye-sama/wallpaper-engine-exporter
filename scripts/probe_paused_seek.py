"""Probe: does QMediaPlayer.setPosition while paused deliver a frame (no play)?"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
from PySide6.QtWidgets import QApplication

from wallpaper_exporter.discovery import discover_wallpaper_paths
from wallpaper_exporter.indexer import scan_workshop
from wallpaper_exporter.video_page import video_entries


def main() -> None:
    app = QApplication([])
    detected = discover_wallpaper_paths()
    entries = video_entries(scan_workshop(detected.workshop_dir))
    video = next((e for e in entries if e.main_file), None)
    if video is None:
        print("FAILED: no video entries")
        return

    player = QMediaPlayer()
    sink = QVideoSink()
    player.setVideoSink(sink)
    frames: list = []
    sink.videoFrameChanged.connect(lambda f: frames.append(f))

    state = {"loaded": False, "seeked": False, "done": False}
    player.mediaStatusChanged.connect(
        lambda s: state.update(loaded=state["loaded"] or s == QMediaPlayer.MediaStatus.LoadedMedia)
    )
    player.setSource(QUrl.fromLocalFile(str(video.main_file)))

    def seek() -> None:
        if state["loaded"] and not state["seeked"]:
            state["seeked"] = True
            print("loaded; seeking to 2000ms while paused (never played)")
            player.setPosition(2000)
            QTimer.singleShot(2000, lambda: state.update(done=True))

    QTimer.singleShot(3000, seek)
    QTimer.singleShot(9000, lambda: state.update(done=True))
    while not state["done"]:
        app.processEvents()

    nonempty = [f for f in frames if f.isValid()]
    print(
        "seeked:", state["seeked"],
        "| position:", player.position(),
        "| frames delivered:", len(nonempty),
        "| playbackState:", player.playbackState(),
    )


if __name__ == "__main__":
    main()
