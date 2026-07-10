from pathlib import Path

from wallpaper_exporter.discovery import DetectedWallpaperPaths
from wallpaper_exporter import settings as settings_module
from wallpaper_exporter.settings import (
    AppSettings,
    load_settings,
    resolve_settings,
    save_settings,
)


def test_load_settings_uses_expected_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings_module,
        "discover_wallpaper_paths",
        lambda: DetectedWallpaperPaths(None, None),
    )

    settings = load_settings(tmp_path / "missing.json")

    assert settings.workshop_dir == Path(
        r"D:\GAME\steam\steamapps\workshop\content\431960"
    )
    assert settings.repkg_path == settings_module.DEFAULT_REPKG_PATH
    assert settings.wallpaper_exe == Path(
        r"D:\GAME\steam\steamapps\common\wallpaper_engine\wallpaper64.exe"
    )


def test_save_and_load_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    original = AppSettings(
        workshop_dir=tmp_path / "workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )
    original.workshop_dir.mkdir()
    original.export_root.mkdir()
    original.repkg_path.write_bytes(b"exe")
    original.wallpaper_exe.write_bytes(b"exe")

    save_settings(original, path)
    loaded = load_settings(path)

    assert loaded == original


def test_resolve_settings_preserves_existing_saved_paths(tmp_path, monkeypatch):
    workshop = tmp_path / "chosen-workshop"
    workshop.mkdir()
    exports = tmp_path / "chosen-exports"
    exports.mkdir()
    repkg = tmp_path / "chosen-RePKG.exe"
    repkg.write_bytes(b"exe")
    engine = tmp_path / "chosen-wallpaper64.exe"
    engine.write_bytes(b"exe")
    settings = AppSettings(workshop, exports, repkg, engine)
    monkeypatch.setattr(
        settings_module,
        "discover_wallpaper_paths",
        lambda: DetectedWallpaperPaths(
            tmp_path / "detected-workshop",
            tmp_path / "detected-wallpaper64.exe",
        ),
    )

    assert resolve_settings(settings) == settings


def test_load_settings_repairs_missing_paths_and_persists_result(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
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
    save_settings(
        AppSettings(
            workshop_dir=tmp_path / "missing-workshop",
            export_root=tmp_path / "missing-exports",
            repkg_path=tmp_path / "missing-RePKG.exe",
            wallpaper_exe=tmp_path / "missing-wallpaper64.exe",
        ),
        settings_path,
    )

    loaded = load_settings(settings_path)

    assert loaded.workshop_dir == detected_workshop
    assert loaded.export_root == settings_module.DEFAULT_EXPORT_ROOT
    assert loaded.repkg_path == bundled_repkg
    assert loaded.wallpaper_exe == detected_engine
    assert load_settings(settings_path) == loaded


def test_resolve_settings_replaces_paths_with_wrong_types(tmp_path, monkeypatch):
    wrong_workshop = tmp_path / "workshop.txt"
    wrong_workshop.write_text("not a directory", encoding="utf-8")
    wrong_export = tmp_path / "exports.txt"
    wrong_export.write_text("not a directory", encoding="utf-8")
    wrong_repkg = tmp_path / "RePKG"
    wrong_repkg.mkdir()
    wrong_engine = tmp_path / "wallpaper64"
    wrong_engine.mkdir()
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

    resolved = resolve_settings(
        AppSettings(wrong_workshop, wrong_export, wrong_repkg, wrong_engine)
    )

    assert resolved == AppSettings(
        detected_workshop,
        settings_module.DEFAULT_EXPORT_ROOT,
        bundled_repkg,
        detected_engine,
    )
