from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


KNOWN_STEAM_ROOTS = (
    Path(r"C:\Program Files (x86)\Steam"),
    Path(r"C:\Program Files\Steam"),
    Path(r"D:\GAME\steam"),
)
_VDF_TOKEN = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])')


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        candidate = Path(path)
        key = str(candidate).casefold()
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _unescape_vdf_path(value: str) -> Path:
    return Path(value.replace(r"\\", "\\").replace(r'\"', '"'))


def parse_libraryfolders(text: str) -> list[Path]:
    tokens = [
        quoted or brace
        for quoted, brace in _VDF_TOKEN.findall(text)
    ]
    try:
        root_start = tokens.index("{") + 1
    except ValueError:
        return []

    root, _position = _parse_vdf_object(tokens, root_start)
    libraries: list[Path] = []
    for key, value in root:
        if not key.isdigit():
            continue
        if isinstance(value, str):
            libraries.append(_unescape_vdf_path(value))
            continue
        for field, field_value in value:
            if field.casefold() == "path" and isinstance(field_value, str):
                libraries.append(_unescape_vdf_path(field_value))
                break
    return unique_paths(libraries)


def _parse_vdf_object(
    tokens: Sequence[str], position: int
) -> tuple[list[tuple[str, str | list]], int]:
    result: list[tuple[str, str | list]] = []
    while position < len(tokens):
        token = tokens[position]
        if token == "}":
            return result, position + 1
        if token == "{":
            position += 1
            continue

        key = token
        position += 1
        if position >= len(tokens):
            break
        if tokens[position] == "{":
            value, position = _parse_vdf_object(tokens, position + 1)
            result.append((key, value))
            continue
        if tokens[position] != "}":
            result.append((key, tokens[position]))
            position += 1
    return result, position


@dataclass(frozen=True)
class DetectedWallpaperPaths:
    workshop_dir: Path | None
    wallpaper_exe: Path | None


def registry_steam_roots() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []

    keys = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Valve\Steam",
            "InstallPath",
        ),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    )
    roots: list[Path] = []
    for hive, key_name, value_name in keys:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _kind = winreg.QueryValueEx(key, value_name)
        except OSError:
            continue
        if isinstance(value, str) and value:
            roots.append(Path(value))
    return unique_paths(roots)


def steam_root_candidates(
    registry_roots: Iterable[Path] | None = None,
    known_roots: Sequence[Path] = KNOWN_STEAM_ROOTS,
) -> list[Path]:
    resolved_registry = (
        list(registry_roots) if registry_roots is not None else registry_steam_roots()
    )
    return unique_paths([*resolved_registry, *known_roots])


def steam_library_roots(steam_roots: Iterable[Path]) -> list[Path]:
    libraries: list[Path] = []
    for steam_root in unique_paths(steam_roots):
        if not steam_root.is_dir():
            continue
        libraries.append(steam_root)
        vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
        try:
            text = vdf_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        libraries.extend(parse_libraryfolders(text))
    return unique_paths(libraries)


def discover_wallpaper_paths(
    library_roots: Iterable[Path] | None = None,
) -> DetectedWallpaperPaths:
    libraries = (
        list(library_roots)
        if library_roots is not None
        else steam_library_roots(steam_root_candidates())
    )
    workshop_dir = None
    wallpaper_exe = None
    for library in unique_paths(libraries):
        if workshop_dir is None:
            candidate = library / "steamapps" / "workshop" / "content" / "431960"
            if candidate.is_dir():
                workshop_dir = candidate
        if wallpaper_exe is None:
            candidate = (
                library
                / "steamapps"
                / "common"
                / "wallpaper_engine"
                / "wallpaper64.exe"
            )
            if candidate.is_file():
                wallpaper_exe = candidate
        if workshop_dir is not None and wallpaper_exe is not None:
            break
    return DetectedWallpaperPaths(workshop_dir, wallpaper_exe)
