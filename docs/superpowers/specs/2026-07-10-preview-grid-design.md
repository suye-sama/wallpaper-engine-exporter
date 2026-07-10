# Preview Grid Design

## Goal

Replace the current master-detail wallpaper browser with an image-first gallery
that lets users scan local Wallpaper Engine items and export any item directly
from its thumbnail card.

At the normal application width, the gallery must show five or six thumbnail
cards per row. It must remain usable at smaller widths by reducing the column
count instead of shrinking cards until their previews or labels are unclear.

## Scope

This feature changes only the browsing interface in `wallpaper_exporter.ui`.
It does not change:

- Workshop and Wallpaper Engine path discovery;
- bundled `RePKG.exe` resolution;
- the fixed export root;
- static composition, extraction, or render-capture behavior;
- the confirmation required before render capture.

The existing right-side large-preview and selected-entry detail panel are
removed. Export is an action on every wallpaper card, so an item no longer has
to be selected before it can be exported.

## User Interface

The top bar remains:

- search by title or Workshop ID;
- rescan the automatically discovered Workshop location;
- open the most recently exported directory after a successful export.

Below it, the main area is a scrollable responsive grid. A wallpaper card
contains:

1. a 16:9 preview area;
2. a title limited to two lines;
3. the existing status classification;
4. a compact `Export` button.

Cards whose source metadata cannot be read show their error state and have a
disabled export button. Missing or unreadable preview images show the existing
no-preview state while remaining exportable when the entry itself is valid.

The grid uses a target card width and a fixed gap to calculate the column
count from the viewport width. It caps at six columns, uses five columns when
the available width is moderately narrower, and continuously falls back to
fewer columns for smaller windows. Each row uses a stable card height so
different titles or status text cannot shift the grid.

## Component Boundaries

Introduce a focused thumbnail card widget with one responsibility: render a
`WallpaperEntry` and emit an export request for that entry.

`MainWindow` remains responsible for:

- scanning and filtering `WallpaperEntry` values;
- rebuilding and laying out card widgets;
- caching scaled preview pixmaps;
- initiating exports;
- handling render-capture confirmation, errors, success messages, and the
  last-output directory.

The card widget does not call exporter functions directly. This preserves one
export path and keeps the rendering component testable without filesystem or
process work.

The existing `WallpaperEntry`, `ExportOptions`, and `export_wallpaper` APIs
are reused unchanged. The selected-entry API and list-specific behavior are
removed or replaced only where no longer needed by the grid.

## Data Flow

```text
scan Workshop -> entries -> search filter -> responsive card grid
                                             |
                                             v
                                    card export request
                                             |
                                             v
                         existing export / capture confirmation workflow
                                             |
                                             v
                              enable "Open output" after success
```

Preview loading remains local and synchronous for this first version. Scaled
pixmaps are cached by preview path and target dimensions so ordinary filtering
and grid relayout do not repeatedly decode the same source image.

## Error Handling

Existing scan and export errors keep their current message boxes and status
bar behavior.

An invalid image file must not make the grid fail to render. Its card displays
the no-preview label. A valid wallpaper item continues to offer export even
when its preview cannot be loaded.

An entry with an indexing error cannot be exported. Its card conveys the
unavailable state without making the rest of the grid unusable.

## Tests

Add tests before production changes for:

- filtering entries rebuilds the expected card count;
- grid width calculation yields six columns at the normal application width
  and five columns at the narrower target width;
- a card export request routes the correct `WallpaperEntry` to the main-window
  export path;
- invalid entries render as unavailable and cannot request export;
- existing direct-image, extraction, composition, and render-capture flows
  remain covered by their current tests.

Perform a PySide6 offscreen smoke test and a rendered visual inspection at a
desktop-sized viewport. Confirm that a normal-width window visibly presents
five or six cards per row, card labels remain contained, and every card exposes
its export action.
