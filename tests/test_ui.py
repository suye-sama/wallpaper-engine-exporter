import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from wallpaper_exporter.indexer import WallpaperEntry
from wallpaper_exporter.settings import AppSettings
from wallpaper_exporter.ui import MainWindow, _status_for_entry


def test_main_window_can_be_created_without_scanning(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = AppSettings(
        workshop_dir=tmp_path / "workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )

    window = MainWindow(settings=settings, auto_scan=False)

    assert window.windowTitle() == "Wallpaper 原图导出"
    assert window.export_button.text() == "导出选中"
    window.close()
    app.processEvents()


def test_status_for_video_entry_is_direct_video(tmp_path):
    entry = WallpaperEntry(
        workshop_id="3611760129",
        title="Silvervale Summer 2025 [4K-60FPS]",
        root=tmp_path,
        project_type="video",
        main_file=tmp_path / "[ 4K-60 ] SilverVale.mp4",
    )

    assert _status_for_entry(entry) == "直接视频"


def test_missing_workshop_shows_settings_hint(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = AppSettings(
        workshop_dir=tmp_path / "missing-workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )
    window = MainWindow(settings=settings, auto_scan=False)

    window.scan_now()

    message = window.statusBar().currentMessage()
    assert "Workshop" in message
    assert "设置" in message
    window.close()
    app.processEvents()
