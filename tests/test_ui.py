import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from wallpaper_exporter import ui as ui_module
from wallpaper_exporter.exporter import (
    ExportNeedsRenderCapture,
    ExportOptions,
    ExportResult,
)
from wallpaper_exporter.indexer import WallpaperEntry
from wallpaper_exporter.settings import AppSettings
from wallpaper_exporter.ui import MainWindow, _status_for_entry, grid_column_count


def _settings(tmp_path) -> AppSettings:
    return AppSettings(
        workshop_dir=tmp_path / "workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )


def test_grid_column_count_keeps_six_cards_at_normal_width_and_five_when_narrower():
    assert grid_column_count(1130) == 6
    assert grid_column_count(1129) == 5
    assert grid_column_count(1000) == 5
    assert grid_column_count(179) == 1


def test_main_window_can_be_created_without_scanning(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = _settings(tmp_path)

    window = MainWindow(settings=settings, auto_scan=False)

    assert window.windowTitle() == "Wallpaper 原图导出"
    assert window.open_button.text() == "打开输出"
    assert not window.open_button.isEnabled()
    window.close()
    app.processEvents()


def test_filter_rebuilds_a_wallpaper_card_for_each_matching_entry(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=_settings(tmp_path), auto_scan=False)
    first = WallpaperEntry("100", "First beach", tmp_path / "100")
    second = WallpaperEntry("200", "Second beach", tmp_path / "200")
    third = WallpaperEntry("300", "Mountain", tmp_path / "300")

    window.entries = [first, second, third]
    window._apply_filter()

    assert [card.entry for card in window.cards] == [first, second, third]
    assert window.count_label.text() == "3 项"

    window.search_edit.setText("beach")

    assert [card.entry for card in window.cards] == [first, second]
    assert window.count_label.text() == "2 项"
    window.close()
    app.processEvents()


def test_card_export_uses_its_own_entry_and_enables_open_output(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=_settings(tmp_path), auto_scan=False)
    entry = WallpaperEntry("100", "Export me", tmp_path / "100")
    output_dir = tmp_path / "exports" / "Export me"
    calls: list[tuple[WallpaperEntry, ExportOptions]] = []

    def fake_run_export(passed_entry, options):
        calls.append((passed_entry, options))
        return ExportResult(method="direct", output_dir=output_dir)

    monkeypatch.setattr(window, "_run_export", fake_run_export)
    monkeypatch.setattr(ui_module.QMessageBox, "information", lambda *args: None)
    window.entries = [entry]
    window._apply_filter()

    window.cards[0].export_button.click()

    assert calls == [(entry, ExportOptions(allow_render_capture=False))]
    assert window.last_output_dir == output_dir
    assert window.open_button.isEnabled()
    window.close()
    app.processEvents()


def test_invalid_entry_card_disables_export_but_a_missing_preview_does_not(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=_settings(tmp_path), auto_scan=False)
    invalid = WallpaperEntry(
        "100",
        "Broken",
        tmp_path / "100",
        error="project.json not found",
    )
    valid_without_preview = WallpaperEntry("200", "No preview", tmp_path / "200")

    window.entries = [invalid, valid_without_preview]
    window._apply_filter()

    assert not window.cards[0].export_button.isEnabled()
    assert window.cards[0].preview_label.text() == "没有预览"
    assert window.cards[1].export_button.isEnabled()
    assert window.cards[1].preview_label.text() == "没有预览"
    window.close()
    app.processEvents()


def test_card_export_retries_with_capture_after_user_confirms(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=_settings(tmp_path), auto_scan=False)
    entry = WallpaperEntry("100", "Dynamic", tmp_path / "100")
    output_dir = tmp_path / "exports" / "Dynamic"
    calls: list[ExportOptions] = []

    def fake_run_export(_entry, options):
        calls.append(options)
        if not options.allow_render_capture:
            raise ExportNeedsRenderCapture("dynamic scene")
        return ExportResult(method="render", output_dir=output_dir)

    monkeypatch.setattr(window, "_run_export", fake_run_export)
    monkeypatch.setattr(
        ui_module.QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(ui_module.QMessageBox, "information", lambda *args: None)
    window.entries = [entry]
    window._apply_filter()

    window.cards[0].export_button.click()

    assert calls == [
        ExportOptions(allow_render_capture=False),
        ExportOptions(allow_render_capture=True),
    ]
    assert window.last_output_dir == output_dir
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
