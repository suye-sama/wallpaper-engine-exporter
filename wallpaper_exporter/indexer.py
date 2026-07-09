from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DIRECT_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PREVIEW_NAMES = ("preview.jpg", "preview.png", "preview.gif")


@dataclass
class WallpaperEntry:
    workshop_id: str
    title: str
    root: Path
    project_type: str = ""
    main_file: Path | None = None
    preview_path: Path | None = None
    has_scene_pkg: bool = False
    has_scene_json: bool = False
    has_materials: bool = False
    direct_image_files: list[Path] = field(default_factory=list)
    project: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def read_project(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Project file must contain a JSON object: {path}")
    return payload


def scan_workshop(workshop_dir: Path) -> list[WallpaperEntry]:
    root = Path(workshop_dir)
    if not root.exists():
        return []

    entries = []
    for item_dir in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda p: p.name):
        entries.append(_entry_from_item_dir(item_dir))
    return entries


def _entry_from_item_dir(item_dir: Path) -> WallpaperEntry:
    project_path = item_dir / "project.json"
    if not project_path.exists():
        return WallpaperEntry(
            workshop_id=item_dir.name,
            title=item_dir.name,
            root=item_dir,
            error="project.json not found",
            direct_image_files=_find_direct_images(item_dir),
            has_scene_pkg=(item_dir / "scene.pkg").exists(),
            has_scene_json=(item_dir / "scene.json").exists(),
            has_materials=(item_dir / "materials").is_dir(),
        )

    try:
        project = read_project(project_path)
    except Exception as exc:
        return WallpaperEntry(
            workshop_id=item_dir.name,
            title=item_dir.name,
            root=item_dir,
            error=str(exc),
        )

    title = str(project.get("title") or item_dir.name)
    project_type = str(project.get("type") or "")
    main_file = _resolve_optional_file(item_dir, project.get("file"))
    return WallpaperEntry(
        workshop_id=item_dir.name,
        title=title,
        root=item_dir,
        project_type=project_type,
        main_file=main_file,
        preview_path=_resolve_preview(item_dir, project),
        has_scene_pkg=(item_dir / "scene.pkg").exists(),
        has_scene_json=(item_dir / "scene.json").exists(),
        has_materials=(item_dir / "materials").is_dir(),
        direct_image_files=_find_direct_images(item_dir),
        project=project,
    )


def _resolve_optional_file(root: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path
    return root / path


def _resolve_preview(root: Path, project: dict[str, Any]) -> Path | None:
    preview = _resolve_optional_file(root, project.get("preview"))
    if preview and preview.exists():
        return preview

    for name in PREVIEW_NAMES:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def _find_direct_images(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in DIRECT_IMAGE_SUFFIXES
        ),
        key=lambda path: path.name.lower(),
    )
