from __future__ import annotations

import re
from pathlib import Path

EXPORT_GROUP_NAME = "导出原图"
_INVALID_WINDOWS_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_windows_name(value: str, fallback: str = "untitled") -> str:
    cleaned = _INVALID_WINDOWS_NAME.sub("_", value).strip().rstrip(". ")
    return cleaned or fallback


def export_folder_for(root: Path, title: str) -> Path:
    return Path(root) / EXPORT_GROUP_NAME / sanitize_windows_name(title)
