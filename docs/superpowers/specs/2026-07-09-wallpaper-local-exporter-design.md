# Wallpaper Local Exporter Design

## Goal

Build a Python development desktop app for browsing the user's local Wallpaper Engine Workshop library and exporting original or reconstructed wallpaper images.

The MVP is local-only. It does not subscribe to Workshop items, download new wallpapers from the internet, or manage Steam.

## User Workflow

1. The app opens and scans the configured Wallpaper Engine Workshop directory.
2. The user browses wallpaper entries with title, preview image, type, and extraction status.
3. The user selects a wallpaper and clicks export.
4. The app chooses the least invasive export path:
   - copy a direct image file when the wallpaper is already an image;
   - unpack `scene.pkg` with RePKG when extracted files are missing;
   - statically compose RePKG-extracted scene layers when possible;
   - ask the user before using Wallpaper Engine render capture when static export cannot produce a valid image.
5. The exported files are written under:

```text
<configured export root>\导出原图\<safe wallpaper title>\
```

## Desktop Technology

Use PySide6 for the development window program.

The project uses a workspace-local virtual environment at:

```text
D:\code_Date\codex_projects\explore\.venv
```

Expected dependencies:

- `PySide6` for the desktop UI.
- `Pillow` for image loading, thumbnails, and static composition.
- `pytest` for tests.

## Tool Locations

The preferred bundled RePKG path is:

```text
D:\code_Date\codex_projects\explore\tools\RePKG\RePKG.exe
```

The app should also support these fallbacks:

- `D:\code_Date\codex_projects\explore\RePKG.exe`
- user-selected RePKG path from settings

The default Wallpaper Engine executable path is:

```text
D:\GAME\steam\steamapps\common\wallpaper_engine\wallpaper64.exe
```

The app should allow this path to be changed from settings.

## Default Paths

Default Workshop directory:

```text
D:\GAME\steam\steamapps\workshop\content\431960
```

Default export root should be configurable. The app stores the last selected export root and uses it on the next launch.

## UI Structure

The first screen is the working tool, not a landing page.

Main window:

- Left: searchable local wallpaper list.
- Center/right: large selected wallpaper preview.
- Details panel: title, Workshop ID, type, source path, detected export method, and status notes.
- Actions: rescan, choose export root, export selected, open output folder.

Dialogs:

- Settings dialog for Workshop path, export root, RePKG path, and Wallpaper Engine path.
- Confirmation dialog before engine render capture.
- Progress dialog for scan, unpack, compose, and export work.

## Wallpaper Indexing

For each child directory under the Workshop directory, read `project.json` when present.

Track these fields:

- Workshop ID from the directory name.
- Title from `project.json`.
- Type from `project.json`.
- Main file from `project.json.file`.
- Preview image from `preview.jpg`, `preview.gif`, `preview.png`, or the path referenced by `project.json.preview` when present.
- Whether `scene.pkg`, `scene.json`, `materials`, and direct image files exist.

Entries that cannot be parsed should still appear with their folder name and an error status instead of aborting the scan.

## Export Decision Flow

The export service should expose one high-level operation:

```text
export_wallpaper(entry, export_root, options) -> ExportResult
```

Decision order:

1. If the project file points to a normal image file, copy it as `original.<ext>`.
2. If the wallpaper is a scene and only `scene.pkg` exists, run RePKG into a working extraction directory.
3. Analyze the extracted scene with the existing static/auto logic.
4. If static composition is suitable, create `composite.png`.
5. If render capture is required, show a confirmation dialog before opening Wallpaper Engine.
6. If the user accepts capture, create `render.png`.
7. Always copy the preview image when available and write `info.json`.

The existing scripts should be reused instead of reimplementing their behavior:

- `compose_we_static.py`
- `compose_we_auto.py`
- `render_we_scene.py`

## Output Files

Each export folder may contain:

- `original.<ext>` for direct image wallpapers.
- `composite.png` for static layer composition.
- `render.png` for Wallpaper Engine capture.
- `preview.<ext>` when a preview exists.
- `info.json` with title, Workshop ID, source path, export method, output files, and timestamp.

File and folder names must be sanitized for Windows.

## Error Handling

The app should never silently save a known-bad black render capture.

Expected user-facing errors:

- RePKG path missing.
- Wallpaper Engine executable missing.
- `project.json` cannot be parsed.
- `scene.pkg` unpack failed.
- static composition failed.
- render capture failed or produced a near-black image.
- output path cannot be written.

When static export cannot handle a wallpaper, the app asks whether to render-capture. If the user declines, the export is canceled without error.

## Threading

Long operations run off the UI thread:

- scanning the Workshop directory;
- unpacking with RePKG;
- static composition;
- Wallpaper Engine render capture.

The UI receives progress and final result events. The window stays responsive during export.

## Testing

Unit tests should cover:

- project indexing and fallback behavior for malformed entries;
- Windows-safe title sanitization;
- export decision selection for direct image, packaged scene, static scene, and render-required scene;
- settings load/save defaults;
- the existing static composer and render helper tests.

Manual verification should cover:

- opening the PySide6 app;
- scanning the local Workshop directory;
- exporting a direct image wallpaper;
- exporting a static composed scene;
- confirming and canceling render capture;
- confirming render capture for a known render-required wallpaper such as `星之砂浜`.
