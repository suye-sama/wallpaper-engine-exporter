# Automatic Path Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically resolve local Wallpaper Engine and Steam paths on
startup while retaining any valid user-selected paths.

**Architecture:** Add a small, Qt-free discovery module that parses Steam
library locations and locates Wallpaper Engine assets. The settings module
applies persistence and precedence rules, while the renderer delegates its
executable fallback to the same discovery module.

**Tech Stack:** Python 3, standard-library `winreg`, `pathlib`, regular
expressions, PySide6, pytest.

## Global Constraints

- Target Windows; registry access must fail harmlessly on unavailable keys.
- Never scan arbitrary drives.
- Existing saved paths win only when the exact file or directory exists.
- RePKG defaults to the bundled runtime resource.
- Export root defaults to `%USERPROFILE%\Pictures\Wallpaper Engine Exports`.
- No Qt dependency is allowed in the discovery module.
- A malformed or absent `libraryfolders.vdf` is a discovery miss, not an error.

## File Structure

- Create `wallpaper_exporter/discovery.py`: Steam roots, VDF parsing, and
  Wallpaper Engine path detection.
- Create `tests/test_discovery.py`: hermetic tests for discovery behavior.
- Modify `wallpaper_exporter/settings.py`: resolve persisted settings against
  bundled defaults and discovery results.
- Modify `tests/test_settings.py`: verify precedence and persistence.
- Modify `wallpaper_exporter/wallpaper_engine/render_we_scene.py`: use shared
  discovery after explicit and environment overrides.
- Modify `tests/test_render_we_scene.py`: verify the renderer fallback.
- Modify `wallpaper_exporter/ui.py`: make a missing Workshop location visible
  in the status bar instead of appearing as a successful empty scan.
- Modify `tests/test_ui.py`: verify the visible missing-Workshop status.
- Modify `README.md`: document automatic detection and manual override.

---

### Task 1: Parse Steam Libraries

**Files:**
- Create: `tests/test_discovery.py`
- Create: `wallpaper_exporter/discovery.py`

**Interfaces:**
- Produces `parse_libraryfolders(text: str) -> list[Path]`.
- Produces `unique_paths(paths: Iterable[Path]) -> list[Path]`.
- Later tasks consume the parsed library roots.

- [ ] **Step 1: Write the failing parser tests**

```python
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
```

- [ ] **Step 2: Run the parser tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discovery.py -v
```

Expected: FAIL during collection because `wallpaper_exporter.discovery` does
not exist.

- [ ] **Step 3: Implement the parser and ordered deduplication**

```python
from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path


_STRUCTURED_PATH = re.compile(
    r'"[0-9]+"\s*\{[^{}]*?"path"\s*"((?:\\\\.|[^"])*)"',
    re.DOTALL | re.IGNORECASE,
)
_LEGACY_PATH = re.compile(
    r'^\s*"[0-9]+"\s*"((?:\\\\.|[^"])*)"\s*$',
    re.MULTILINE,
)


def _unescape_vdf_path(value: str) -> Path:
    return Path(value.replace(r"\\", "\\").replace(r'\"', '"'))


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


def parse_libraryfolders(text: str) -> list[Path]:
    structured = [_unescape_vdf_path(match.group(1)) for match in _STRUCTURED_PATH.finditer(text)]
    legacy = [_unescape_vdf_path(match.group(1)) for match in _LEGACY_PATH.finditer(text)]
    return unique_paths([*structured, *legacy])
```

- [ ] **Step 4: Run the parser tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discovery.py -v
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit the parser**

```powershell
git add wallpaper_exporter/discovery.py tests/test_discovery.py
git commit -m "feat: parse Steam library folders"
```

### Task 2: Discover Steam and Wallpaper Engine Paths

**Files:**
- Modify: `wallpaper_exporter/discovery.py`
- Modify: `tests/test_discovery.py`

**Interfaces:**
- Consumes `parse_libraryfolders()` and `unique_paths()`.
- Produces `DetectedWallpaperPaths(workshop_dir, wallpaper_exe)`.
- Produces `steam_root_candidates()` and `discover_wallpaper_paths()`.

- [ ] **Step 1: Write the failing discovery tests**

```python
from wallpaper_exporter.discovery import (
    DetectedWallpaperPaths,
    discover_wallpaper_paths,
    steam_library_roots,
    steam_root_candidates,
)


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


def test_discover_wallpaper_paths_returns_first_existing_library_match(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    (second / "steamapps" / "workshop" / "content" / "431960").mkdir(parents=True)
    executable = second / "steamapps" / "common" / "wallpaper_engine" / "wallpaper64.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")

    detected = discover_wallpaper_paths([first, second])

    assert detected == DetectedWallpaperPaths(
        workshop_dir=second / "steamapps" / "workshop" / "content" / "431960",
        wallpaper_exe=executable,
    )
```

- [ ] **Step 2: Run the discovery tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discovery.py -v
```

Expected: FAIL because the discovery functions and dataclass are not defined.

- [ ] **Step 3: Implement registry and library discovery**

Append this implementation to `wallpaper_exporter/discovery.py`:

```python
from dataclasses import dataclass
from typing import Sequence


KNOWN_STEAM_ROOTS = (
    Path(r"C:\Program Files (x86)\Steam"),
    Path(r"C:\Program Files\Steam"),
    Path(r"D:\GAME\steam"),
)


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
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
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
    resolved_registry = list(registry_roots) if registry_roots is not None else registry_steam_roots()
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
            candidate = library / "steamapps" / "common" / "wallpaper_engine" / "wallpaper64.exe"
            if candidate.is_file():
                wallpaper_exe = candidate
        if workshop_dir is not None and wallpaper_exe is not None:
            break
    return DetectedWallpaperPaths(workshop_dir, wallpaper_exe)
```

- [ ] **Step 4: Run the discovery tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_discovery.py -v
```

Expected: PASS, 6 tests.

- [ ] **Step 5: Commit the discovery feature**

```powershell
git add wallpaper_exporter/discovery.py tests/test_discovery.py
git commit -m "feat: discover Wallpaper Engine paths"
```

### Task 3: Resolve and Persist Application Settings

**Files:**
- Modify: `wallpaper_exporter/settings.py`
- Modify: `tests/test_settings.py`

**Interfaces:**
- Consumes `DetectedWallpaperPaths` from `discovery.py`.
- Produces `resolve_settings(settings: AppSettings) -> AppSettings`.
- `load_settings()` returns resolved settings and saves only a changed resolved
  configuration.

- [ ] **Step 1: Write failing precedence tests**

```python
from wallpaper_exporter.discovery import DetectedWallpaperPaths
from wallpaper_exporter.settings import (
    DEFAULT_EXPORT_ROOT,
    DEFAULT_REPKG_PATH,
    DEFAULT_WALLPAPER_EXE,
    DEFAULT_WORKSHOP_DIR,
    AppSettings,
    load_settings,
    resolve_settings,
    save_settings,
)


def test_load_settings_uses_defaults_when_no_paths_are_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "wallpaper_exporter.settings.discover_wallpaper_paths",
        lambda: DetectedWallpaperPaths(None, None),
    )

    settings = load_settings(tmp_path / "missing.json")

    assert settings.workshop_dir == DEFAULT_WORKSHOP_DIR
    assert settings.repkg_path == DEFAULT_REPKG_PATH
    assert settings.wallpaper_exe == DEFAULT_WALLPAPER_EXE


def test_resolve_settings_preserves_existing_saved_paths(tmp_path, monkeypatch):
    workshop = tmp_path / "chosen-workshop"
    workshop.mkdir()
    engine = tmp_path / "chosen-wallpaper64.exe"
    engine.write_bytes(b"exe")
    repkg = tmp_path / "chosen-RePKG.exe"
    repkg.write_bytes(b"exe")
    exports = tmp_path / "chosen-exports"
    exports.mkdir()
    monkeypatch.setattr(
        "wallpaper_exporter.settings.discover_wallpaper_paths",
        lambda: DetectedWallpaperPaths(tmp_path / "detected-workshop", tmp_path / "detected.exe"),
    )

    resolved = resolve_settings(AppSettings(workshop, exports, repkg, engine))

    assert resolved == AppSettings(workshop, exports, repkg, engine)


def test_load_settings_repairs_missing_paths_and_persists_result(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    detected_workshop = tmp_path / "detected-workshop"
    detected_workshop.mkdir()
    detected_engine = tmp_path / "wallpaper64.exe"
    detected_engine.write_bytes(b"exe")
    bundled_repkg = tmp_path / "bundled-RePKG.exe"
    bundled_repkg.write_bytes(b"exe")
    monkeypatch.setattr(
        "wallpaper_exporter.settings.discover_wallpaper_paths",
        lambda: DetectedWallpaperPaths(detected_workshop, detected_engine),
    )
    monkeypatch.setattr("wallpaper_exporter.settings.DEFAULT_REPKG_PATH", bundled_repkg)
    save_settings(
        AppSettings(tmp_path / "missing-workshop", tmp_path / "missing-exports",
                    tmp_path / "missing-repkg.exe", tmp_path / "missing-engine.exe"),
        settings_path,
    )

    loaded = load_settings(settings_path)

    assert loaded.workshop_dir == detected_workshop
    assert loaded.wallpaper_exe == detected_engine
    assert loaded.repkg_path == bundled_repkg
    assert loaded.export_root == DEFAULT_EXPORT_ROOT
    assert load_settings(settings_path) == loaded
```

- [ ] **Step 2: Run the settings tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_settings.py -v
```

Expected: FAIL because `resolve_settings` does not exist and settings do not
yet use discovery.

- [ ] **Step 3: Implement per-path resolution**

Replace the default-loading section of `wallpaper_exporter/settings.py` with:

```python
from dataclasses import asdict, dataclass, replace

from .discovery import discover_wallpaper_paths


def _existing_or(current: Path, fallback: Path | None) -> Path:
    if current.exists():
        return current
    return fallback if fallback is not None else current


def resolve_settings(settings: AppSettings) -> AppSettings:
    detected = discover_wallpaper_paths()
    return replace(
        settings,
        workshop_dir=_existing_or(settings.workshop_dir, detected.workshop_dir),
        export_root=_existing_or(settings.export_root, DEFAULT_EXPORT_ROOT),
        repkg_path=_existing_or(settings.repkg_path, DEFAULT_REPKG_PATH),
        wallpaper_exe=_existing_or(settings.wallpaper_exe, detected.wallpaper_exe),
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
```

Keep the existing `AppSettings` field order and the `save_settings()` JSON
format unchanged.

- [ ] **Step 4: Run the settings tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_settings.py -v
```

Expected: PASS, including the existing round-trip test.

- [ ] **Step 5: Commit settings resolution**

```powershell
git add wallpaper_exporter/settings.py tests/test_settings.py
git commit -m "feat: resolve missing app paths automatically"
```

### Task 4: Reuse Discovery in Capture and Explain Missing Workshop

**Files:**
- Modify: `wallpaper_exporter/wallpaper_engine/render_we_scene.py`
- Modify: `tests/test_render_we_scene.py`
- Modify: `wallpaper_exporter/ui.py`
- Modify: `tests/test_ui.py`
- Modify: `README.md`

**Interfaces:**
- Consumes `discover_wallpaper_paths()`.
- `resolve_wallpaper_exe()` checks explicit path, environment variable, shared
  Steam discovery, then `PATH`.
- `MainWindow.scan_now()` presents a non-empty status message when the
  Workshop directory does not exist.

- [ ] **Step 1: Write failing renderer and UI tests**

```python
from wallpaper_exporter.discovery import DetectedWallpaperPaths
from wallpaper_exporter.wallpaper_engine.render_we_scene import resolve_wallpaper_exe


def test_resolve_wallpaper_exe_uses_shared_discovery(monkeypatch, tmp_path):
    discovered = tmp_path / "wallpaper64.exe"
    discovered.write_bytes(b"exe")
    monkeypatch.delenv("WALLPAPER_ENGINE_EXE", raising=False)
    monkeypatch.setattr(
        "wallpaper_exporter.wallpaper_engine.render_we_scene.discover_wallpaper_paths",
        lambda: DetectedWallpaperPaths(None, discovered),
    )
    monkeypatch.setattr(
        "wallpaper_exporter.wallpaper_engine.render_we_scene.shutil.which",
        lambda name: None,
    )

    assert resolve_wallpaper_exe() == discovered
```

```python
def test_missing_workshop_shows_settings_hint(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = AppSettings(
        workshop_dir=tmp_path / "missing-workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )
    window = MainWindow(settings=settings, auto_scan=False)

    window.scan_now()

    assert "Workshop" in window.statusBar().currentMessage()
    assert "设置" in window.statusBar().currentMessage()
    window.close()
    app.processEvents()
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_render_we_scene.py tests\test_ui.py -v
```

Expected: FAIL because the renderer does not import the discovery module and
the UI silently reports a completed scan for a missing directory.

- [ ] **Step 3: Use shared discovery and add the UI status**

In `render_we_scene.py`, import `discover_wallpaper_paths` and replace the
hard-coded candidate list inside `resolve_wallpaper_exe()` with:

```python
    detected = discover_wallpaper_paths()
    if detected.wallpaper_exe is not None:
        candidates.append(detected.wallpaper_exe)
```

Keep the existing explicit-path, environment-variable, and `shutil.which()`
checks in their current priority order.

At the start of `MainWindow.scan_now()` in `ui.py`, add:

```python
        if not self.settings.workshop_dir.is_dir():
            self.entries = []
            self._apply_filter()
            self.statusBar().showMessage(
                "找不到 Wallpaper Engine Workshop，请在设置中选择目录。"
            )
            return
```

Replace README lines 48-72 with a short automatic-discovery section stating:

```markdown
打开程序后会自动从 Steam 注册表和 Steam 库目录查找 Workshop 与
`wallpaper64.exe`。`RePKG.exe` 已内置，导出目录默认是
`图片\Wallpaper Engine Exports`。

已有且存在的手动设置会被保留；仅当旧路径已不存在时，程序才会自动修复。
自动识别失败时，点右上方的 `设置` 手动选择路径。
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_render_we_scene.py tests\test_ui.py -v
```

Expected: PASS, including existing capture tests.

- [ ] **Step 5: Commit integration and documentation**

```powershell
git add wallpaper_exporter/wallpaper_engine/render_we_scene.py tests/test_render_we_scene.py wallpaper_exporter/ui.py tests/test_ui.py README.md
git commit -m "feat: auto-detect local Wallpaper Engine paths"
```

### Task 5: Full Regression and Package Smoke Test

**Files:**
- Verify: all repository tests
- Verify: `scripts/build_windows.ps1`

**Interfaces:**
- Verifies all preceding public functions and packaged runtime behavior.

- [ ] **Step 1: Run the complete suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS with no failures.

- [ ] **Step 2: Build the portable one-file executable**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -OneFile
```

Expected: `dist\WallpaperExporter.exe` exists and contains the bundled
`RePKG.exe` runtime resource.

- [ ] **Step 3: Smoke-test the executable startup**

Run:

```powershell
$process = Start-Process -FilePath .\dist\WallpaperExporter.exe -PassThru
Start-Sleep -Seconds 5
if ($process.HasExited) { throw "WallpaperExporter.exe exited with $($process.ExitCode)" }
Stop-Process -Id $process.Id
```

Expected: the process remains running for five seconds, proving it did not
fail during automatic path discovery.

- [ ] **Step 4: Commit any verification-only changes**

Run:

```powershell
git status --short
```

Expected: no output. Do not create an empty commit.
