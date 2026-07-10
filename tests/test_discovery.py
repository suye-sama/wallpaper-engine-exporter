from pathlib import Path

from wallpaper_exporter.discovery import (
    DetectedWallpaperPaths,
    discover_wallpaper_paths,
    parse_libraryfolders,
    steam_library_roots,
    steam_root_candidates,
)


def test_parse_libraryfolders_reads_current_structured_entries():
    text = r'''
    "libraryfolders"
    {
        "0" { "path" "D:\\SteamLibrary" }
        "1" { "path" "E:\\Games\\Steam" }
    }
    '''

    assert parse_libraryfolders(text) == [
        Path(r"D:\SteamLibrary"),
        Path(r"E:\Games\Steam"),
    ]


def test_parse_libraryfolders_reads_legacy_numeric_entries():
    text = r'''
    "LibraryFolders"
    {
        "1" "D:\\SteamLibrary"
        "2" "E:\\Games\\Steam"
    }
    '''

    assert parse_libraryfolders(text) == [
        Path(r"D:\SteamLibrary"),
        Path(r"E:\Games\Steam"),
    ]


def test_parse_libraryfolders_ignores_malformed_lines_and_duplicates():
    text = r'''
    "libraryfolders"
    {
        "0" { "path" "D:\\SteamLibrary" }
        "1" { "path" "D:\\SteamLibrary" }
        "2" { "label" "not a path" }
        "broken" "E:\\Ignored"
    }
    '''

    assert parse_libraryfolders(text) == [Path(r"D:\SteamLibrary")]


def test_steam_root_candidates_keep_registry_order_before_known_roots(tmp_path):
    registry = tmp_path / "registry-steam"
    known = tmp_path / "known-steam"

    assert steam_root_candidates([registry], [known]) == [registry, known]


def test_steam_library_roots_include_root_and_vdf_libraries(tmp_path):
    steam = tmp_path / "Steam"
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(
        '"libraryfolders" { "1" { "path" "D:\\\\SteamLibrary" } }',
        encoding="utf-8",
    )

    assert steam_library_roots([steam]) == [steam, Path(r"D:\SteamLibrary")]


def test_discover_wallpaper_paths_uses_first_existing_path_for_each_resource(tmp_path):
    first = tmp_path / "first"
    workshop = first / "steamapps" / "workshop" / "content" / "431960"
    workshop.mkdir(parents=True)

    second = tmp_path / "second"
    executable = (
        second / "steamapps" / "common" / "wallpaper_engine" / "wallpaper64.exe"
    )
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")

    detected = discover_wallpaper_paths([first, second])

    assert detected == DetectedWallpaperPaths(
        workshop_dir=workshop,
        wallpaper_exe=executable,
    )
