from pathlib import Path

from wallpaper_exporter import settings as settings_module
from wallpaper_exporter.settings import AppSettings, load_settings, save_settings


def test_load_settings_uses_expected_defaults(tmp_path):
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

    save_settings(original, path)
    loaded = load_settings(path)

    assert loaded == original
