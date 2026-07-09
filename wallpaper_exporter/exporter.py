from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .wallpaper_engine.compose_we_auto import analyze_scene, compose_auto

from .indexer import DIRECT_MEDIA_SUFFIXES, WallpaperEntry
from .paths import export_folder_for
from .settings import AppSettings


@dataclass(frozen=True)
class ExportOptions:
    allow_render_capture: bool = False
    width: int | None = None
    height: int | None = None
    render_capture_count: int = 5
    render_capture_interval: float = 0.3


@dataclass(frozen=True)
class ExportResult:
    method: str
    output_dir: Path
    files: dict[str, Path] = field(default_factory=dict)
    message: str = ""


class ExportNeedsRenderCapture(RuntimeError):
    pass


def export_wallpaper(
    entry: WallpaperEntry, settings: AppSettings, options: ExportOptions
) -> ExportResult:
    output_dir = export_folder_for(settings.export_root, entry.title)
    output_dir.mkdir(parents=True, exist_ok=True)

    if _is_direct_media(entry.main_file):
        return _export_direct_media(entry, output_dir)

    scene_root = _scene_root_for(entry)
    if scene_root is None:
        raise RuntimeError(f"No exportable image or scene found for {entry.title}")

    if not (scene_root / "scene.json").exists():
        if entry.has_scene_pkg:
            scene_pkg = _scene_pkg_for(entry, scene_root)
            extract_scene_pkg(scene_pkg, scene_root, settings.repkg_path)
        if not (scene_root / "scene.json").exists():
            raise RuntimeError("scene.pkg exists but extracted scene.json is missing")
    if not (scene_root / "scene.json").exists():
        raise RuntimeError(f"Scene folder does not contain scene.json: {scene_root}")

    analysis = analyze_scene(scene_root)
    if analysis.method == "render" and not options.allow_render_capture:
        raise ExportNeedsRenderCapture("; ".join(analysis.reasons))

    if analysis.method == "render":
        output_path = output_dir / "render.png"
        result = compose_auto(
            scene_root,
            output_path,
            force="render",
            width=options.width,
            height=options.height,
            wallpaper_exe=settings.wallpaper_exe,
            capture_count=options.render_capture_count,
            capture_interval=options.render_capture_interval,
        )
        method = "render"
    else:
        output_path = output_dir / "composite.png"
        result = compose_auto(
            scene_root,
            output_path,
            force="static",
            fallback_to_render=False,
        )
        method = str(result.get("method", "static"))
        if method == "render" and not options.allow_render_capture:
            raise ExportNeedsRenderCapture("render capture required")

    files = _render_files(method, output_path, result)
    _copy_preview(entry, output_dir, files)
    _write_info(entry, output_dir, method, files, result)
    return ExportResult(method=method, output_dir=output_dir, files=files)


def _export_direct_media(entry: WallpaperEntry, output_dir: Path) -> ExportResult:
    assert entry.main_file is not None
    output_path = output_dir / f"original{entry.main_file.suffix.lower()}"
    shutil.copy2(entry.main_file, output_path)
    files = {"original": output_path}
    _copy_preview(entry, output_dir, files)
    _write_info(entry, output_dir, "direct", files, {})
    return ExportResult(method="direct", output_dir=output_dir, files=files)


def _is_direct_media(path: Path | None) -> bool:
    return bool(path and path.suffix.lower() in DIRECT_MEDIA_SUFFIXES and path.exists())


def _render_files(method: str, output_path: Path, result: dict[str, Any]) -> dict[str, Path]:
    if method != "render":
        return {method: output_path}

    outputs = result.get("summary", {}).get("outputs") or [str(output_path)]
    files: dict[str, Path] = {}
    for index, item in enumerate(outputs):
        key = "render" if index == 0 else f"render_{index + 1:02d}"
        files[key] = Path(item)
    return files


def _scene_root_for(entry: WallpaperEntry) -> Path | None:
    if entry.has_scene_json or (entry.root / "scene.json").exists():
        return entry.root
    if entry.main_file and entry.main_file.name.lower() == "scene.json":
        return entry.main_file.parent
    return entry.root if entry.project_type == "scene" else None


def _scene_pkg_for(entry: WallpaperEntry, scene_root: Path) -> Path:
    if entry.main_file and entry.main_file.name.lower() == "scene.pkg":
        return entry.main_file
    return scene_root / "scene.pkg"


def extract_scene_pkg(scene_pkg: Path, destination: Path, repkg_path: Path) -> None:
    if not repkg_path.exists():
        raise FileNotFoundError(f"RePKG.exe not found: {repkg_path}")
    if not scene_pkg.exists():
        raise FileNotFoundError(f"scene.pkg not found: {scene_pkg}")

    destination.mkdir(parents=True, exist_ok=True)
    command = [
        str(repkg_path),
        "extract",
        str(scene_pkg),
        "-o",
        str(destination),
        "--overwrite",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"RePKG extraction failed: {details}")
    if not (destination / "scene.json").exists():
        details = (completed.stdout or completed.stderr or "").strip()
        raise RuntimeError(f"RePKG extraction did not create scene.json: {details}")


def _copy_preview(
    entry: WallpaperEntry, output_dir: Path, files: dict[str, Path]
) -> None:
    if not entry.preview_path or not entry.preview_path.exists():
        return
    preview_path = output_dir / f"preview{entry.preview_path.suffix.lower()}"
    shutil.copy2(entry.preview_path, preview_path)
    files["preview"] = preview_path


def _write_info(
    entry: WallpaperEntry,
    output_dir: Path,
    method: str,
    files: dict[str, Path],
    detail: dict[str, Any],
) -> None:
    info_path = output_dir / "info.json"
    payload = {
        "title": entry.title,
        "workshop_id": entry.workshop_id,
        "source_path": str(entry.root),
        "method": method,
        "files": {key: str(value) for key, value in files.items()},
        "detail": detail,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    info_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    files["info"] = info_path
