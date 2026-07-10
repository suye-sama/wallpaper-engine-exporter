from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

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
DEFAULT_WORKSHOP_DIR = Path(r"D:\GAME\steam\steamapps\workshop\content\431960")
DEFAULT_REPKG_PATH = PROJECT_ROOT / "tools" / "RePKG" / "RePKG.exe"
DEFAULT_WALLPAPER_EXE = Path(
    r"D:\GAME\steam\steamapps\common\wallpaper_engine\wallpaper64.exe"
)
DEFAULT_EXPORT_ROOT = Path.home() / "Pictures" / "Wallpaper Engine Exports"
DEFAULT_SETTINGS_PATH = default_settings_path()


@dataclass(frozen=True)
class AppSettings:
    workshop_dir: Path = DEFAULT_WORKSHOP_DIR
    export_root: Path = DEFAULT_EXPORT_ROOT
    repkg_path: Path = DEFAULT_REPKG_PATH
    wallpaper_exe: Path = DEFAULT_WALLPAPER_EXE


def _coerce_settings(payload: dict[str, Any]) -> AppSettings:
    defaults = AppSettings()
    values = asdict(defaults)
    values.update({key: Path(value) for key, value in payload.items() if key in values})
    return AppSettings(**values)


def _existing_directory_or(current: Path, fallback: Path | None) -> Path:
    return current if current.is_dir() else fallback or current


def _existing_file_or(current: Path, fallback: Path | None) -> Path:
    return current if current.is_file() else fallback or current


def resolve_settings(settings: AppSettings) -> AppSettings:
    detected = discover_wallpaper_paths()
    return replace(
        settings,
        workshop_dir=_existing_directory_or(
            settings.workshop_dir, detected.workshop_dir
        ),
        export_root=_existing_directory_or(settings.export_root, DEFAULT_EXPORT_ROOT),
        repkg_path=_existing_file_or(settings.repkg_path, DEFAULT_REPKG_PATH),
        wallpaper_exe=_existing_file_or(settings.wallpaper_exe, detected.wallpaper_exe),
    )


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = Path(path) if path is not None else default_settings_path()
    payload: dict[str, Any] = {}
    if settings_path.exists():
        with settings_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"Settings file must contain a JSON object: {settings_path}")

    loaded = _coerce_settings(payload)
    resolved = resolve_settings(loaded)
    if resolved != loaded:
        save_settings(resolved, settings_path)
    return resolved


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    settings_path = Path(path) if path is not None else default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: str(value) for key, value in asdict(settings).items()}
    settings_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
