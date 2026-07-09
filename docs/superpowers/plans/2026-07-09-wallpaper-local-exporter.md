# Wallpaper Local Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PySide6 development desktop app that scans the local Wallpaper Engine Workshop library and exports direct, statically composed, or user-approved rendered images.

**Architecture:** Create a small `wallpaper_exporter` package for testable settings, indexing, path, and export decisions. Keep PySide6 code in a focused UI module that calls the service layer from worker threads and reuses the existing composer/render scripts.

**Tech Stack:** Python 3.10, PySide6, Pillow, pytest, RePKG.exe, Wallpaper Engine.

## Global Constraints

- Use a workspace-local virtual environment at `D:\code_Date\codex_projects\explore\.venv`.
- Use PySide6 for the development window program.
- RePKG is preferred at `D:\code_Date\codex_projects\explore\tools\RePKG\RePKG.exe`.
- Default Workshop directory is `D:\GAME\steam\steamapps\workshop\content\431960`.
- Default Wallpaper Engine executable is `D:\GAME\steam\steamapps\common\wallpaper_engine\wallpaper64.exe`.
- Export to `<configured export root>\导出原图\<safe wallpaper title>\`.
- Do not use Wallpaper Engine render capture without asking the user first.
- Reuse `compose_we_static.py`, `compose_we_auto.py`, and `render_we_scene.py`; do not duplicate their core algorithms.

---

### Task 1: Dependency And App Skeleton

**Files:**
- Create: `requirements.txt`
- Create: `wallpaper_exporter/__init__.py`
- Create: `wallpaper_exporter/__main__.py`
- Create: `wallpaper_exporter/app.py`
- Create: `tests/test_app_smoke.py`

**Interfaces:**
- Produces: `wallpaper_exporter.app.main() -> int`
- Produces: CLI `python -m wallpaper_exporter`

- [ ] **Step 1: Write the failing smoke test**

```python
from wallpaper_exporter.app import main


def test_app_main_exists_without_launching_qt():
    assert callable(main)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_app_smoke.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'wallpaper_exporter'`.

- [ ] **Step 3: Add minimal app skeleton**

```python
# wallpaper_exporter/app.py
from __future__ import annotations


def main() -> int:
    return 0
```

```python
# wallpaper_exporter/__main__.py
from __future__ import annotations

from .app import main

raise SystemExit(main())
```

```python
# wallpaper_exporter/__init__.py
"""Wallpaper Engine local exporter desktop app."""
```

```text
# requirements.txt
PySide6>=6.7
Pillow>=12.1
pytest>=8.4
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_app_smoke.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt wallpaper_exporter tests/test_app_smoke.py
git commit -m "feat: add wallpaper exporter app skeleton"
```

### Task 2: Settings And Path Helpers

**Files:**
- Create: `wallpaper_exporter/settings.py`
- Create: `wallpaper_exporter/paths.py`
- Create: `tests/test_settings.py`
- Create: `tests/test_paths.py`

**Interfaces:**
- Produces: `AppSettings` dataclass with `workshop_dir`, `export_root`, `repkg_path`, `wallpaper_exe`.
- Produces: `load_settings(path: Path | None = None) -> AppSettings`
- Produces: `save_settings(settings: AppSettings, path: Path | None = None) -> None`
- Produces: `sanitize_windows_name(value: str, fallback: str = "untitled") -> str`
- Produces: `export_folder_for(root: Path, title: str) -> Path`

- [ ] **Step 1: Write failing settings tests**

```python
from pathlib import Path

from wallpaper_exporter.settings import AppSettings, load_settings, save_settings


def test_load_settings_uses_expected_defaults(tmp_path):
    settings = load_settings(tmp_path / "missing.json")

    assert settings.workshop_dir == Path(r"D:\GAME\steam\steamapps\workshop\content\431960")
    assert settings.repkg_path == Path(r"D:\code_Date\codex_projects\explore\tools\RePKG\RePKG.exe")
    assert settings.wallpaper_exe == Path(r"D:\GAME\steam\steamapps\common\wallpaper_engine\wallpaper64.exe")


def test_save_and_load_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    original = AppSettings(
        workshop_dir=tmp_path / "workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )

    save_settings(original, path)
    loaded = load_settings(path)

    assert loaded == original
```

- [ ] **Step 2: Write failing path tests**

```python
from pathlib import Path

from wallpaper_exporter.paths import export_folder_for, sanitize_windows_name


def test_sanitize_windows_name_replaces_invalid_characters():
    assert sanitize_windows_name('a:b*c?d"e<f>g|') == "a_b_c_d_e_f_g_"


def test_sanitize_windows_name_handles_empty_values():
    assert sanitize_windows_name("   ") == "untitled"


def test_export_folder_uses_chinese_group_folder(tmp_path):
    folder = export_folder_for(tmp_path, "星之砂浜")

    assert folder == tmp_path / "导出原图" / "星之砂浜"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_settings.py tests/test_paths.py -q`
Expected: FAIL because modules do not exist.

- [ ] **Step 4: Implement settings and path helpers**

`AppSettings` stores absolute or user-selected paths as `Path`. `load_settings` returns defaults when the file is missing, and `save_settings` writes UTF-8 JSON with string paths.

`sanitize_windows_name` replaces `<>:"/\|?*` and control characters with `_`, trims trailing dots/spaces, and uses the fallback for empty results.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_settings.py tests/test_paths.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add wallpaper_exporter/settings.py wallpaper_exporter/paths.py tests/test_settings.py tests/test_paths.py
git commit -m "feat: add exporter settings and path helpers"
```

### Task 3: Workshop Indexer

**Files:**
- Create: `wallpaper_exporter/indexer.py`
- Create: `tests/test_indexer.py`

**Interfaces:**
- Produces: `WallpaperEntry` dataclass.
- Produces: `scan_workshop(workshop_dir: Path) -> list[WallpaperEntry]`
- Produces: `read_project(path: Path) -> dict[str, Any]`

- [ ] **Step 1: Write failing indexer tests**

```python
import json

from wallpaper_exporter.indexer import scan_workshop


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_scan_workshop_reads_project_metadata(tmp_path):
    item = tmp_path / "123"
    item.mkdir()
    write_json(item / "project.json", {"title": "海边", "type": "scene", "file": "scene.pkg", "preview": "preview.jpg"})
    (item / "preview.jpg").write_bytes(b"jpg")
    (item / "scene.pkg").write_bytes(b"pkg")

    entries = scan_workshop(tmp_path)

    assert len(entries) == 1
    assert entries[0].workshop_id == "123"
    assert entries[0].title == "海边"
    assert entries[0].project_type == "scene"
    assert entries[0].main_file == item / "scene.pkg"
    assert entries[0].preview_path == item / "preview.jpg"
    assert entries[0].has_scene_pkg is True


def test_scan_workshop_keeps_malformed_project_as_error_entry(tmp_path):
    item = tmp_path / "bad"
    item.mkdir()
    (item / "project.json").write_text("{", encoding="utf-8")

    entries = scan_workshop(tmp_path)

    assert len(entries) == 1
    assert entries[0].workshop_id == "bad"
    assert entries[0].title == "bad"
    assert entries[0].error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_indexer.py -q`
Expected: FAIL because `wallpaper_exporter.indexer` does not exist.

- [ ] **Step 3: Implement indexer**

The indexer sorts child directories by name, reads `project.json` as UTF-8, resolves `file` relative to the item folder, resolves preview in this order: `project.preview`, `preview.jpg`, `preview.png`, `preview.gif`. Malformed entries produce a `WallpaperEntry` with `error`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_indexer.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wallpaper_exporter/indexer.py tests/test_indexer.py
git commit -m "feat: index local wallpaper workshop entries"
```

### Task 4: Export Service

**Files:**
- Create: `wallpaper_exporter/exporter.py`
- Create: `tests/test_exporter.py`

**Interfaces:**
- Produces: `ExportOptions` dataclass with `allow_render_capture: bool = False`.
- Produces: `ExportResult` dataclass with `method`, `output_dir`, `files`, and `message`.
- Produces: `ExportNeedsRenderCapture` exception.
- Produces: `export_wallpaper(entry: WallpaperEntry, settings: AppSettings, options: ExportOptions) -> ExportResult`

- [ ] **Step 1: Write failing direct-image export test**

```python
from pathlib import Path

from wallpaper_exporter.exporter import ExportOptions, export_wallpaper
from wallpaper_exporter.indexer import WallpaperEntry
from wallpaper_exporter.settings import AppSettings


def make_settings(tmp_path):
    return AppSettings(
        workshop_dir=tmp_path / "workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )


def test_export_wallpaper_copies_direct_image_and_writes_info(tmp_path):
    source = tmp_path / "image.png"
    source.write_bytes(b"png")
    entry = WallpaperEntry(
        workshop_id="1",
        title="A:B",
        root=tmp_path,
        project_type="image",
        main_file=source,
    )

    result = export_wallpaper(entry, make_settings(tmp_path), ExportOptions())

    assert result.method == "direct"
    assert (tmp_path / "exports" / "导出原图" / "A_B" / "original.png").read_bytes() == b"png"
    assert (tmp_path / "exports" / "导出原图" / "A_B" / "info.json").exists()
```

- [ ] **Step 2: Write failing render-confirmation test**

```python
import pytest

from wallpaper_exporter.exporter import ExportNeedsRenderCapture, ExportOptions, export_wallpaper
from wallpaper_exporter.indexer import WallpaperEntry

from .test_exporter import make_settings


def test_export_wallpaper_requires_confirmation_for_render_scene(tmp_path, monkeypatch):
    scene_dir = tmp_path / "scene"
    scene_dir.mkdir()
    entry = WallpaperEntry(
        workshop_id="2",
        title="Render",
        root=scene_dir,
        project_type="scene",
        main_file=scene_dir / "scene.pkg",
        has_scene_json=True,
    )

    def fake_compose_auto(*args, **kwargs):
        return {"method": "render", "analysis": {"reasons": ["puppet"]}}

    monkeypatch.setattr("wallpaper_exporter.exporter.compose_auto", fake_compose_auto)

    with pytest.raises(ExportNeedsRenderCapture):
        export_wallpaper(entry, make_settings(tmp_path), ExportOptions(allow_render_capture=False))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_exporter.py -q`
Expected: FAIL because `wallpaper_exporter.exporter` does not exist.

- [ ] **Step 4: Implement direct copy, static compose, render guard, and info writing**

Direct image extensions are `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`. For scenes, call `compose_auto` with output path `composite.png` and `force="auto"`. If analysis or result method is `render` and render capture is not allowed, raise `ExportNeedsRenderCapture`. If allowed, call `compose_auto` again with `force="render"` and output path `render.png`.

Do not wire RePKG subprocess extraction in this task beyond reporting a clear error when a scene has `scene.pkg` but no extracted `scene.json`; add the subprocess in the next task if the direct service shape is green.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_exporter.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add wallpaper_exporter/exporter.py tests/test_exporter.py
git commit -m "feat: export direct and composed wallpapers"
```

### Task 5: RePKG Extraction

**Files:**
- Modify: `wallpaper_exporter/exporter.py`
- Modify: `tests/test_exporter.py`

**Interfaces:**
- Produces: `extract_scene_pkg(scene_pkg: Path, destination: Path, repkg_path: Path) -> None`

- [ ] **Step 1: Write failing RePKG extraction decision test**

```python
def test_export_wallpaper_extracts_scene_pkg_before_composing(tmp_path, monkeypatch):
    item = tmp_path / "item"
    item.mkdir()
    scene_pkg = item / "scene.pkg"
    scene_pkg.write_bytes(b"pkg")
    entry = WallpaperEntry(
        workshop_id="3",
        title="Packed",
        root=item,
        project_type="scene",
        main_file=scene_pkg,
        has_scene_pkg=True,
    )
    settings = make_settings(tmp_path)
    settings.repkg_path.write_bytes(b"exe")
    calls = []

    def fake_extract(pkg, destination, repkg):
        calls.append((pkg, destination, repkg))
        (destination / "scene.json").write_text('{"general":{"orthogonalprojection":{"width":1,"height":1}},"objects":[]}', encoding="utf-8")

    def fake_compose_auto(input_path, output_path, **kwargs):
        output_path.write_bytes(b"png")
        return {"method": "static", "analysis": {"reasons": ["regular"]}}

    monkeypatch.setattr("wallpaper_exporter.exporter.extract_scene_pkg", fake_extract)
    monkeypatch.setattr("wallpaper_exporter.exporter.compose_auto", fake_compose_auto)

    result = export_wallpaper(entry, settings, ExportOptions())

    assert result.method == "static"
    assert calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_exporter.py::test_export_wallpaper_extracts_scene_pkg_before_composing -q`
Expected: FAIL because extraction is not implemented.

- [ ] **Step 3: Implement RePKG subprocess extraction**

`extract_scene_pkg` validates `repkg_path.exists()`, creates the destination, then runs `RePKG.exe extract <scene.pkg> -o <destination>` with `subprocess.run(..., capture_output=True, text=True, check=False)`. If the command returns non-zero or no `scene.json` appears, raise `RuntimeError` with stderr/stdout text.

- [ ] **Step 4: Run exporter tests**

Run: `.venv\Scripts\python -m pytest tests/test_exporter.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wallpaper_exporter/exporter.py tests/test_exporter.py
git commit -m "feat: unpack scene packages during export"
```

### Task 6: PySide6 Main Window

**Files:**
- Create: `wallpaper_exporter/ui.py`
- Modify: `wallpaper_exporter/app.py`

**Interfaces:**
- Produces: `MainWindow(QMainWindow)`
- Produces: `run_app() -> int`

- [ ] **Step 1: Implement UI design plan**

Use a restrained desktop-tool design:

- Palette: canvas `#f6f7f9`, panel `#ffffff`, ink `#1f2937`, muted `#6b7280`, accent `#2f6fed`, warning `#b45309`.
- Layout: splitter with left list/search and right preview/details/actions.
- Signature element: a compact status strip showing `direct`, `needs extraction`, `static`, or `asks before capture`.
- Typography: system UI fonts, larger title only in selected-wallpaper details.

- [ ] **Step 2: Implement main window**

The window loads settings, scans with `scan_workshop`, displays entries in a `QListWidget`, loads preview images into `QPixmap`, and calls `export_wallpaper`. If `ExportNeedsRenderCapture` is raised, show `QMessageBox.question`; only retry with `allow_render_capture=True` when the user chooses yes.

- [ ] **Step 3: Smoke run manually**

Run: `.venv\Scripts\python -m wallpaper_exporter`
Expected: PySide6 window opens and scans the default Workshop directory.

- [ ] **Step 4: Commit**

```bash
git add wallpaper_exporter/ui.py wallpaper_exporter/app.py
git commit -m "feat: add PySide6 wallpaper exporter window"
```

### Task 7: Final Verification

**Files:**
- Inspect: `wallpaper_exporter/*.py`
- Inspect: `tests/*.py`
- Inspect: `requirements.txt`

**Interfaces:**
- Validates: test suite and manual app launch.

- [ ] **Step 1: Run full automated tests**

Run: `.venv\Scripts\python -m pytest`
Expected: all tests pass.

- [ ] **Step 2: Launch the app**

Run: `.venv\Scripts\python -m wallpaper_exporter`
Expected: app opens without import/runtime errors.

- [ ] **Step 3: Commit any fixes**

```bash
git add wallpaper_exporter tests requirements.txt
git commit -m "fix: polish wallpaper exporter verification"
```

- [ ] **Step 4: Report**

Report branch name, key commits, test results, and how to launch the app.
