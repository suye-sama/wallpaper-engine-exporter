import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from wallpaper_exporter.settings import AppSettings
from wallpaper_exporter.ui import MainWindow


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
