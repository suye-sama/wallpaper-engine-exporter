"""Headless end-to-end check of VideoFrameExtractor on a real video."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from wallpaper_exporter.frame_extractor import (
    VideoFrameExtractor,
    compute_timestamps,
)

VIDEO = Path(
    r"D:\GAME\steam\steamapps\workshop\content\431960\2680392402\HuTao-Genshin Impact.mp4"
)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    output_dir = Path(tempfile.mkdtemp(prefix="frame_extract_test_"))
    timestamps = compute_timestamps(1000, None, 1.0, 4)

    state = {"done": False, "files": [], "error": None}
    extractor = VideoFrameExtractor()

    def on_progress(done: int, total: int) -> None:
        print(f"progress {done}/{total}")

    def on_finished(files: list) -> None:
        state["done"] = True
        state["files"] = files

    def on_failed(message: str) -> None:
        state["done"] = True
        state["error"] = message

    extractor.progress.connect(on_progress)
    extractor.finished.connect(on_finished)
    extractor.failed.connect(on_failed)

    if not extractor.start(VIDEO, timestamps, output_dir, target_width=1920):
        print("failed to start")
        return 1

    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(lambda: state.update(done=True, error="watchdog timeout"))
    watchdog.start(30_000)

    while not state["done"]:
        app.processEvents()

    if state["error"]:
        print(f"FAILED: {state['error']}")
        return 1

    print(f"saved {len(state['files'])} frames:")
    for path in state["files"]:
        from PySide6.QtGui import QImage

        image = QImage(str(path))
        print(f"  {path.name}  {image.width()}x{image.height()}  {path.stat().st_size} bytes")
        if image.isNull() or image.width() == 0:
            print("  -> broken image!")
            return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
