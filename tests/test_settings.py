from pathlib import Path

from wallpaper_exporter.discovery import DetectedWallpaperPaths
from wallpaper_exporter import settings as settings_module
from wallpaper_exporter.settings import load_settings


def test_load_settings_discovers_paths_without_hard_coded_defaults(monkeypatch, tmp_path):
    detected_workshop = tmp_path / "detected-workshop"
    detected_workshop.mkdir()
    detected_engine = tmp_path / "detected-wallpaper64.exe"
    detected_engine.write_bytes(b"exe")
    bundled_repkg = tmp_path / "bundled-RePKG.exe"
    bundled_repkg.write_bytes(b"exe")
    monkeypatch.setattr(
        settings_module,
        "discover_wallpaper_paths",
        lambda: DetectedWallpaperPaths(detected_workshop, detected_engine),
    )
    monkeypatch.setattr(settings_module, "DEFAULT_REPKG_PATH", bundled_repkg)
    loaded = load_settings()

    assert loaded.workshop_dir == detected_workshop
    assert loaded.export_root == settings_module.DEFAULT_EXPORT_ROOT
    assert loaded.repkg_path == bundled_repkg
    assert loaded.wallpaper_exe == detected_engine


def test_load_settings_removes_legacy_json_instead_of_using_saved_paths(tmp_path, monkeypatch):
    settings_path = tmp_path / "wallpaper_exporter_settings.json"
    settings_path.write_text(
        '{"workshop_dir": "D:\\\\stale", "export_root": "D:\\\\old-output"}',
        encoding="utf-8",
    )
    detected_workshop = tmp_path / "detected-workshop"
    detected_workshop.mkdir()
    detected_engine = tmp_path / "detected-wallpaper64.exe"
    detected_engine.write_bytes(b"exe")
    bundled_repkg = tmp_path / "bundled-RePKG.exe"
    bundled_repkg.write_bytes(b"exe")
    monkeypatch.setattr(
        settings_module,
        "discover_wallpaper_paths",
        lambda: DetectedWallpaperPaths(detected_workshop, detected_engine),
    )
    monkeypatch.setattr(settings_module, "DEFAULT_REPKG_PATH", bundled_repkg)
    monkeypatch.setattr(settings_module, "default_settings_path", lambda: settings_path)

    loaded = load_settings()

    assert loaded.workshop_dir == detected_workshop
    assert not settings_path.exists()
