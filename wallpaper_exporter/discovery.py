from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path


_STRUCTURED_PATH = re.compile(
    r'"[0-9]+"\s*\{[^{}]*?"path"\s*"((?:\\.|[^"])*)"',
    re.DOTALL | re.IGNORECASE,
)
_LEGACY_PATH = re.compile(
    r'^\s*"[0-9]+"\s*"((?:\\.|[^"])*)"\s*$',
    re.MULTILINE,
)


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
    structured = [
        _unescape_vdf_path(match.group(1)) for match in _STRUCTURED_PATH.finditer(text)
    ]
    legacy = [_unescape_vdf_path(match.group(1)) for match in _LEGACY_PATH.finditer(text)]
    return unique_paths([*structured, *legacy])
