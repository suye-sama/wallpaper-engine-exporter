from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


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


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = Path(path) if path is not None else default_settings_path()
    if not settings_path.exists():
        return AppSettings()

    with settings_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Settings file must contain a JSON object: {settings_path}")
    return _coerce_settings(payload)


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    settings_path = Path(path) if path is not None else default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: str(value) for key, value in asdict(settings).items()}
    settings_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
