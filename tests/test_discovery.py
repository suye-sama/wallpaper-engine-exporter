from pathlib import Path

from wallpaper_exporter.discovery import parse_libraryfolders


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
