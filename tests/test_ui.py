import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from wallpaper_exporter import ui as ui_module
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


def test_missing_workshop_explains_that_automatic_discovery_was_retried(tmp_path):
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
    assert "自动" in message
    window.close()
    app.processEvents()


def test_rescan_rediscovers_the_workshop_directory(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    old_settings = AppSettings(
        workshop_dir=tmp_path / "old-workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )
    fresh_workshop = tmp_path / "fresh-workshop"
    fresh_workshop.mkdir()
    fresh_settings = AppSettings(
        workshop_dir=fresh_workshop,
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )
    discovered = iter([old_settings, fresh_settings])
    scanned_paths: list[Path] = []
    monkeypatch.setattr(ui_module, "load_settings", lambda: next(discovered))
    monkeypatch.setattr(
        ui_module,
        "scan_workshop",
        lambda path: scanned_paths.append(path) or [],
    )

    window = MainWindow(auto_scan=False)
    window.scan_now()
    window.scan_now()

    assert scanned_paths == [fresh_workshop]
    window.close()
    app.processEvents()
