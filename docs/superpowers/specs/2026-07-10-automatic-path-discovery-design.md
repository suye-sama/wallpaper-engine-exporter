# Automatic Path Discovery Design

## Goal

Remove the need for a first-time user to configure local paths before browsing
and exporting Wallpaper Engine Workshop items.

The application must automatically identify:

- the Wallpaper Engine Workshop directory;
- the installed `wallpaper64.exe`;
- the bundled `RePKG.exe`;
- a usable export root.

## Scope

This feature applies when loading application settings at startup. It does not
search every drive for executables and it does not change the export workflow.

The existing Settings dialog remains available for users who want to override
any detected path.

## Path Precedence

Each setting is resolved independently in this order:

1. A saved path that exists on disk.
2. An automatically discovered path.
3. The current default path, even if it does not yet exist.

When automatic discovery replaces a missing saved path, the resolved settings
are saved so the next launch does not need to rediscover them.

The app must never replace an existing user-selected path.

## Discovery Sources

### RePKG

`RePKG.exe` is bundled with the application. Its path is always the executable
provided from the application runtime directory. A saved RePKG setting is used
only when it exists, allowing development and advanced users to override it.

### Export Root

The fallback export root is:

```text
%USERPROFILE%\Pictures\Wallpaper Engine Exports
```

The directory is created on the first successful export. A saved existing
export directory remains unchanged.

### Steam Libraries

The resolver builds a deduplicated list of Steam library roots from:

1. `HKCU\Software\Valve\Steam\SteamPath`.
2. `HKLM\SOFTWARE\WOW6432Node\Valve\Steam\InstallPath`.
3. `HKLM\SOFTWARE\Valve\Steam\InstallPath`.
4. Well-known Steam folders:
   - `C:\Program Files (x86)\Steam`
   - `C:\Program Files\Steam`
   - `D:\GAME\steam`

For every existing Steam root, it reads:

```text
<steam root>\steamapps\libraryfolders.vdf
```

The VDF parser only needs the `path` values in current structured files and
the numeric library values in legacy files. It must tolerate comments,
whitespace, malformed entries, and a missing VDF file. The Steam root itself
is always included as a library candidate.

## Wallpaper Engine Paths

For each discovered Steam library root, resolve:

```text
<library>\steamapps\common\wallpaper_engine\wallpaper64.exe
<library>\steamapps\workshop\content\431960
```

The first matching path in deterministic library order is selected. The order
is: registry Steam root, its VDF library order, then well-known roots and
their VDF library order. Duplicate paths are ignored.

`wallpaper32.exe` is not chosen for app settings, but the existing renderer
may retain its command-line fallback behavior.

## User Experience

On a fresh launch, the main window scans the discovered Workshop directory
without any settings interaction.

If no Workshop directory is found, the main window stays usable and shows a
clear scan error explaining that a Workshop directory could not be found and
can be set from Settings.

If `wallpaper64.exe` cannot be found, normal image, video, extraction, and
static-composition exports still work. Only render capture reports the missing
executable and directs the user to Settings.

The Settings dialog displays the resolved paths. It does not need an extra
"Auto detect" button in this first version.

## Architecture

Add a focused discovery module that returns a `DetectedPaths` value and has no
Qt dependency. `settings.py` owns precedence and persistence:

```text
load saved settings -> resolve missing paths -> save only when values changed
```

The render module delegates executable resolution to the shared discovery
module after checking an explicit command-line argument and the
`WALLPAPER_ENGINE_EXE` environment variable. This removes its separate,
hard-coded path list.

## Error Handling

Registry permission errors, absent registry keys, unreadable VDF files, and
invalid VDF content are discovery misses, not application errors.

No automatic discovery result is accepted unless the exact expected directory
or executable exists.

## Tests

Unit tests cover:

- valid saved paths win over discovered paths;
- missing saved paths are replaced by detected paths and saved;
- a missing workshop path does not prevent other settings from resolving;
- registry values and known folders contribute Steam roots;
- current and legacy `libraryfolders.vdf` formats produce library paths;
- duplicate libraries are removed while preserving order;
- Wallpaper Engine and Workshop paths are discovered from a library;
- the renderer uses the shared Wallpaper Engine discovery fallback.

The existing settings round-trip and packaged executable tests remain green.
