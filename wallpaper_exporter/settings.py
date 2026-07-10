from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .discovery import discover_wallpaper_paths


SETTINGS_FILENAME = "wallpaper_exporter_settings.json"


def runtime_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[1]


def settings_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_settings_path() -> Path:
    return settings_root() / SETTINGS_FILENAME


PROJECT_ROOT = runtime_root()
DEFAULT_REPKG_PATH = PROJECT_ROOT / "tools" / "RePKG" / "RePKG.exe"
DEFAULT_EXPORT_ROOT = Path.home() / "Pictures" / "Wallpaper Engine Exports"


@dataclass(frozen=True)
class AppSettings:
    workshop_dir: Path | None = None
    export_root: Path = DEFAULT_EXPORT_ROOT
    repkg_path: Path = DEFAULT_REPKG_PATH
    wallpaper_exe: Path | None = None


def load_settings() -> AppSettings:
    _remove_legacy_settings_file()
    detected = discover_wallpaper_paths()
    return AppSettings(
        workshop_dir=detected.workshop_dir,
        export_root=DEFAULT_EXPORT_ROOT,
        repkg_path=DEFAULT_REPKG_PATH,
        wallpaper_exe=detected.wallpaper_exe,
    )


def _remove_legacy_settings_file() -> None:
    try:
        default_settings_path().unlink(missing_ok=True)
    except OSError:
        pass
