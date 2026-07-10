# Preview Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the master-detail wallpaper browser with a responsive
thumbnail gallery that exposes a direct export button on every valid wallpaper
card.

**Architecture:** Keep all Qt presentation code in
`wallpaper_exporter/ui.py`. A `WallpaperCard` renders one `WallpaperEntry` and
emits an export request; `MainWindow` owns searching, responsive placement,
cached preview scaling, and the existing export/capture workflow.

**Tech Stack:** Python 3, PySide6, pytest.

## Global Constraints

- Target Windows and retain the existing PySide6 desktop runtime.
- Change only the browsing UI; do not modify discovery, RePKG, export-root, or
  composition behavior.
- Keep the current render-capture confirmation before a dynamic scene is
  captured.
- A normal 1180px-wide application window must show six cards per row.
- A moderately narrower viewport must show five cards per row before falling
  back to fewer columns.
- Use fixed card dimensions, a 16:9 preview surface, two title lines at most,
  and a visible direct export button.
- Keep a valid item exportable when its preview is missing or unreadable.
- Keep an indexed-error item visible but disable its export button.

## File Structure

- Modify `wallpaper_exporter/ui.py`: add responsive-grid geometry, the
  `WallpaperCard` widget, cached preview loading, and direct card export.
- Modify `tests/test_ui.py`: replace list-selection assertions with gallery,
  card-export, and error-state coverage.
- Modify `README.md`: describe gallery browsing and per-card export.

---

### Task 1: Define Responsive Grid Geometry

**Files:**
- Modify: `tests/test_ui.py`
- Modify: `wallpaper_exporter/ui.py`

**Interfaces:**
- Produces `GRID_CARD_WIDTH: int` with value `180`.
- Produces `GRID_GAP: int` with value `10`.
- Produces `MAX_GRID_COLUMNS: int` with value `6`.
- Produces `grid_column_count(available_width: int) -> int`.
- Later tasks use `grid_column_count()` to decide the `QGridLayout` column for
  every card.

- [ ] **Step 1: Write the failing geometry test**

Add this import and test to `tests/test_ui.py`:

```python
from wallpaper_exporter.ui import MainWindow, _status_for_entry, grid_column_count


def test_grid_column_count_keeps_six_cards_at_normal_width_and_five_when_narrower():
    assert grid_column_count(1130) == 6
    assert grid_column_count(1129) == 5
    assert grid_column_count(1000) == 5
    assert grid_column_count(179) == 1
```

Keep the existing `MainWindow` and `_status_for_entry` imports only once.

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```powershell
D:\code_Date\codex_projects\explore\.venv\Scripts\python.exe -m pytest tests\test_ui.py::test_grid_column_count_keeps_six_cards_at_normal_width_and_five_when_narrower -v
```

Expected: FAIL during collection because `grid_column_count` is not defined.

- [ ] **Step 3: Implement the grid constants and helper**

Add the following directly below the imports in `wallpaper_exporter/ui.py`:

```python
GRID_CARD_WIDTH = 180
GRID_CARD_HEIGHT = 218
GRID_GAP = 10
MAX_GRID_COLUMNS = 6
PREVIEW_SIZE = QSize(164, 92)


def grid_column_count(available_width: int) -> int:
    slots = max(1, (max(0, available_width) + GRID_GAP) // (GRID_CARD_WIDTH + GRID_GAP))
    return min(MAX_GRID_COLUMNS, slots)
```

Add `QSize` to the existing `PySide6.QtCore` import.

- [ ] **Step 4: Run the focused test to verify it passes**

Run:

```powershell
D:\code_Date\codex_projects\explore\.venv\Scripts\python.exe -m pytest tests\test_ui.py::test_grid_column_count_keeps_six_cards_at_normal_width_and_five_when_narrower -v
```

Expected: PASS, 1 test.

- [ ] **Step 5: Commit the responsive geometry**

Run:

```powershell
git add wallpaper_exporter/ui.py tests/test_ui.py
git commit -m "feat: calculate responsive preview grid columns"
```

### Task 2: Render Wallpaper Cards and Route Direct Export

**Files:**
- Modify: `tests/test_ui.py`
- Modify: `wallpaper_exporter/ui.py`

**Interfaces:**
- Consumes `grid_column_count()`, `WallpaperEntry`, `ExportNeedsRenderCapture`,
  `ExportOptions`, and `ExportResult`.
- Produces `WallpaperCard(entry: WallpaperEntry, status: str, preview: QPixmap | None, preview_message: str)`.
- `WallpaperCard.export_requested` is a `Signal(object)` that emits its
  `WallpaperEntry`.
- Produces `MainWindow.cards: list[WallpaperCard]`.
- Produces `MainWindow.export_entry(entry: WallpaperEntry) -> None`.
- `MainWindow._apply_filter()` rebuilds `cards` from `filtered_entries`.

- [ ] **Step 1: Write the failing gallery and direct-export tests**

Add these imports to `tests/test_ui.py`:

```python
from PySide6.QtWidgets import QMessageBox

from wallpaper_exporter.exporter import ExportNeedsRenderCapture, ExportOptions, ExportResult
```

Add the following tests:

```python
def _settings(tmp_path) -> AppSettings:
    return AppSettings(
        workshop_dir=tmp_path / "workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )


def test_filter_rebuilds_a_wallpaper_card_for_each_matching_entry(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=_settings(tmp_path), auto_scan=False)
    first = WallpaperEntry("100", "First beach", tmp_path / "100")
    second = WallpaperEntry("200", "Second beach", tmp_path / "200")
    third = WallpaperEntry("300", "Mountain", tmp_path / "300")

    window.entries = [first, second, third]
    window._apply_filter()

    assert [card.entry for card in window.cards] == [first, second, third]
    assert window.count_label.text() == "3 项"

    window.search_edit.setText("beach")

    assert [card.entry for card in window.cards] == [first, second]
    assert window.count_label.text() == "2 项"
    window.close()
    app.processEvents()


def test_card_export_uses_its_own_entry_and_enables_open_output(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=_settings(tmp_path), auto_scan=False)
    entry = WallpaperEntry("100", "Export me", tmp_path / "100")
    output_dir = tmp_path / "exports" / "Export me"
    calls: list[tuple[WallpaperEntry, ExportOptions]] = []

    def fake_run_export(passed_entry, options):
        calls.append((passed_entry, options))
        return ExportResult(method="direct", output_dir=output_dir)

    monkeypatch.setattr(window, "_run_export", fake_run_export)
    monkeypatch.setattr(ui_module.QMessageBox, "information", lambda *args: None)
    window.entries = [entry]
    window._apply_filter()

    window.cards[0].export_button.click()

    assert calls == [(entry, ExportOptions(allow_render_capture=False))]
    assert window.last_output_dir == output_dir
    assert window.open_button.isEnabled()
    window.close()
    app.processEvents()


def test_invalid_entry_card_disables_export_but_a_missing_preview_does_not(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=_settings(tmp_path), auto_scan=False)
    invalid = WallpaperEntry("100", "Broken", tmp_path / "100", error="project.json not found")
    valid_without_preview = WallpaperEntry("200", "No preview", tmp_path / "200")

    window.entries = [invalid, valid_without_preview]
    window._apply_filter()

    assert not window.cards[0].export_button.isEnabled()
    assert window.cards[0].preview_label.text() == "没有预览"
    assert window.cards[1].export_button.isEnabled()
    assert window.cards[1].preview_label.text() == "没有预览"
    window.close()
    app.processEvents()


def test_card_export_retries_with_capture_after_user_confirms(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings=_settings(tmp_path), auto_scan=False)
    entry = WallpaperEntry("100", "Dynamic", tmp_path / "100")
    output_dir = tmp_path / "exports" / "Dynamic"
    calls: list[ExportOptions] = []

    def fake_run_export(_entry, options):
        calls.append(options)
        if not options.allow_render_capture:
            raise ExportNeedsRenderCapture("dynamic scene")
        return ExportResult(method="render", output_dir=output_dir)

    monkeypatch.setattr(window, "_run_export", fake_run_export)
    monkeypatch.setattr(
        ui_module.QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(ui_module.QMessageBox, "information", lambda *args: None)
    window.entries = [entry]
    window._apply_filter()

    window.cards[0].export_button.click()

    assert calls == [
        ExportOptions(allow_render_capture=False),
        ExportOptions(allow_render_capture=True),
    ]
    assert window.last_output_dir == output_dir
    window.close()
    app.processEvents()
```

Update `test_main_window_can_be_created_without_scanning()` so its assertion
checks the retained top-bar control:

```python
assert window.open_button.text() == "打开输出"
assert not window.open_button.isEnabled()
```

Remove the old assertion for `window.export_button`, because that selected-item
button no longer exists.

- [ ] **Step 2: Run the gallery tests to verify they fail**

Run:

```powershell
D:\code_Date\codex_projects\explore\.venv\Scripts\python.exe -m pytest tests\test_ui.py -v
```

Expected: FAIL because `MainWindow` has no `cards` collection and no
card-level export controls.

- [ ] **Step 3: Replace the list/detail interface with a card gallery**

In `wallpaper_exporter/ui.py`, update imports:

```python
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
```

Remove the `QListWidget`, `QListWidgetItem`, `QSizePolicy`, and `QSplitter`
imports.

Add this widget before `MainWindow`:

```python
class WallpaperCard(QFrame):
    export_requested = Signal(object)

    def __init__(
        self,
        entry: WallpaperEntry,
        status: str,
        preview: QPixmap | None,
        preview_message: str,
    ) -> None:
        super().__init__()
        self.entry = entry
        self.setObjectName("wallpaperCard")
        self.setFixedSize(GRID_CARD_WIDTH, GRID_CARD_HEIGHT)
        self.setToolTip(f"{entry.title}\nID: {entry.workshop_id}\n{entry.root}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.preview_label = QLabel(preview_message)
        self.preview_label.setObjectName("cardPreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(PREVIEW_SIZE)
        if preview is not None:
            self.preview_label.setText("")
            self.preview_label.setPixmap(preview)
        layout.addWidget(self.preview_label)

        self.title_label = QLabel(entry.title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setFixedHeight(36)
        self.title_label.setToolTip(entry.title)
        layout.addWidget(self.title_label)

        self.status_label = QLabel(status)
        self.status_label.setObjectName("cardStatus")
        self.status_label.setFixedHeight(20)
        layout.addWidget(self.status_label)

        self.export_button = QPushButton("导出")
        self.export_button.setObjectName("cardExport")
        self.export_button.setEnabled(not bool(entry.error))
        self.export_button.clicked.connect(
            lambda: self.export_requested.emit(self.entry)
        )
        layout.addWidget(self.export_button)
```

In `MainWindow.__init__`, initialize the new state after
`self.last_output_dir`:

```python
self.cards: list[WallpaperCard] = []
self._grid_columns = 0
self._preview_cache: dict[tuple[Path, int, int], QPixmap | None] = {}
```

Replace the splitter construction in `_build_ui()` with this gallery:

```python
self.count_label = QLabel("0 项")
self.count_label.setObjectName("muted")
toolbar.addWidget(self.count_label)

self.open_button = QPushButton("打开输出")
self.open_button.clicked.connect(self.open_last_output)
self.open_button.setEnabled(False)
toolbar.addWidget(self.open_button)
outer.addLayout(toolbar)

self.gallery_scroll = QScrollArea()
self.gallery_scroll.setObjectName("galleryScroll")
self.gallery_scroll.setWidgetResizable(True)
self.gallery = QWidget()
self.gallery_layout = QGridLayout(self.gallery)
self.gallery_layout.setContentsMargins(0, 0, 0, 0)
self.gallery_layout.setHorizontalSpacing(GRID_GAP)
self.gallery_layout.setVerticalSpacing(GRID_GAP)
self.gallery_layout.setAlignment(
    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
)
self.gallery_scroll.setWidget(self.gallery)
outer.addWidget(self.gallery_scroll, 1)

self.setStatusBar(QStatusBar())
```

Keep the search and rescan controls already created at the start of the
toolbar. Remove the old `QSplitter`, list widget, detail labels, and
selected-entry action layout.

Replace `_apply_filter()` with:

```python
def _apply_filter(self) -> None:
    text = self.search_edit.text().strip().lower()
    self.filtered_entries = [
        entry
        for entry in self.entries
        if not text
        or text in entry.title.lower()
        or text in entry.workshop_id.lower()
    ]
    self.count_label.setText(f"{len(self.filtered_entries)} 项")
    self._rebuild_grid()
```

Add these `MainWindow` helpers:

```python
def _clear_grid(self) -> None:
    while self.gallery_layout.count():
        item = self.gallery_layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
    self.cards = []


def _preview_for_entry(self, entry: WallpaperEntry) -> tuple[QPixmap | None, str]:
    path = entry.preview_path
    if path is None or not path.is_file():
        return None, "没有预览"

    key = (path, PREVIEW_SIZE.width(), PREVIEW_SIZE.height())
    if key not in self._preview_cache:
        source = QPixmap(str(path))
        self._preview_cache[key] = (
            None
            if source.isNull()
            else source.scaled(
                PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    preview = self._preview_cache[key]
    return (
        (preview, "")
        if preview is not None
        else (None, "预览不可读")
    )


def _rebuild_grid(self) -> None:
    columns = grid_column_count(self.gallery_scroll.viewport().width())
    self._grid_columns = columns
    self._clear_grid()
    for index, entry in enumerate(self.filtered_entries):
        preview, preview_message = self._preview_for_entry(entry)
        card = WallpaperCard(
            entry,
            _status_for_entry(entry),
            preview,
            preview_message,
        )
        card.export_requested.connect(self.export_entry)
        self.cards.append(card)
        self.gallery_layout.addWidget(card, index // columns, index % columns)
```

Replace the selected-entry-only `resizeEvent()` with:

```python
def showEvent(self, event) -> None:  # noqa: N802
    super().showEvent(event)
    self._rebuild_grid()


def resizeEvent(self, event) -> None:  # noqa: N802
    super().resizeEvent(event)
    columns = grid_column_count(self.gallery_scroll.viewport().width())
    if columns != self._grid_columns:
        self._rebuild_grid()
```

Delete `_selection_changed()`, `_show_entry()`, `_clear_selection()`,
`_load_preview()`, `selected_entry()`, and `export_selected()`.

Rename `export_selected()` to `export_entry()` and change only its first lines
to accept the clicked card entry:

```python
def export_entry(self, entry: WallpaperEntry) -> None:
    try:
        result = self._run_export(entry, ExportOptions(allow_render_capture=False))
```

Keep its existing `ExportNeedsRenderCapture`, failure, success, and
`open_button` handling unchanged after those first lines.

Replace the list/detail stylesheet rules with:

```css
QScrollArea#galleryScroll {
    border: none;
    background: transparent;
}
QWidget#qt_scrollarea_viewport {
    background: transparent;
}
QFrame#wallpaperCard {
    background: #ffffff;
    border: 1px solid #dfe3ea;
    border-radius: 6px;
}
QFrame#wallpaperCard:hover {
    border-color: #2f6fed;
}
QLabel#cardPreview {
    background: #111827;
    color: #e5e7eb;
    border-radius: 4px;
}
QLabel#cardTitle {
    color: #1f2937;
    font-weight: 600;
}
QLabel#cardStatus {
    color: #64748b;
}
QPushButton#cardExport {
    background: #2f6fed;
    border-color: #2f6fed;
    color: #ffffff;
}
QPushButton#cardExport:hover {
    background: #245bd0;
    border-color: #245bd0;
}
```

Retain the existing global background, search field, regular button,
disabled-button, and status-bar styles.

- [ ] **Step 4: Run the gallery tests to verify they pass**

Run:

```powershell
D:\code_Date\codex_projects\explore\.venv\Scripts\python.exe -m pytest tests\test_ui.py -v
```

Expected: PASS, including the existing auto-discovery rescan and direct-video
status tests.

- [ ] **Step 5: Commit the gallery UI**

Run:

```powershell
git add wallpaper_exporter/ui.py tests/test_ui.py
git commit -m "feat: browse wallpapers in a preview grid"
```

### Task 3: Document the Gallery and Verify the Desktop View

**Files:**
- Modify: `README.md`
- Verify: `tests/test_ui.py`
- Verify: repository test suite

**Interfaces:**
- Documents the top-bar search/rescan controls, direct card export, and
  unchanged capture confirmation.
- Verifies `MainWindow` remains creatable in offscreen Qt and renders six
  card widgets in a normal-width desktop window.

- [ ] **Step 1: Update the export instructions**

Replace the four numbered items under `## 导出图片` in `README.md` with:

```markdown
1. 在主界面的缩略图网格中搜索或浏览壁纸。
2. 每张卡片都会显示预览、标题、导出方式和 `导出` 按钮。
3. 点击目标壁纸卡片上的 `导出`，不需要先在列表中选中它。
4. 如果该壁纸需要 Wallpaper Engine 抓图，程序会先询问是否允许。
```

Replace the existing left-list/right-preview wording in that section with:

```markdown
窗口在常见桌面宽度下一行显示 5 至 6 张预览卡片；窗口变窄时会自动减少列数。
预览图缺失不会阻止可导出的壁纸执行导出，无法读取 `project.json` 的条目则会显示为不可导出。
```

- [ ] **Step 2: Run the full automated suite**

Run:

```powershell
D:\code_Date\codex_projects\explore\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS with no failures.

- [ ] **Step 3: Produce a six-card desktop screenshot**

Run this PowerShell command from the repository root:

```powershell
@'
import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from wallpaper_exporter.indexer import WallpaperEntry
from wallpaper_exporter.settings import AppSettings
from wallpaper_exporter.ui import MainWindow

app = QApplication.instance() or QApplication([])
root = Path(tempfile.mkdtemp(prefix="wallpaper-exporter-grid-"))
preview = root / "preview.png"
image = QImage(320, 180, QImage.Format.Format_RGB32)
image.fill(0x336699)
assert image.save(str(preview))

settings = AppSettings(
    workshop_dir=root / "workshop",
    export_root=root / "exports",
    repkg_path=root / "RePKG.exe",
    wallpaper_exe=root / "wallpaper64.exe",
)
window = MainWindow(settings=settings, auto_scan=False)
window.entries = [
    WallpaperEntry(str(index), f"Wallpaper {index}", root / str(index), preview_path=preview)
    for index in range(6)
]
window.resize(1180, 760)
window._apply_filter()
window.show()
app.processEvents()

output = Path(tempfile.gettempdir()) / "WallpaperExporter-preview-grid.png"
assert window.grab().save(str(output))
print(output)
window.close()
'@ | D:\code_Date\codex_projects\explore\.venv\Scripts\python.exe -
```

Expected: the command prints the absolute PNG path. Inspect that file and
confirm six complete cards are visible on the first row, each card has a
preview, a contained title, a status label, and an `导出` button.

- [ ] **Step 4: Check the final diff and commit documentation**

Run:

```powershell
git diff --check
git status --short
```

Expected: only `README.md` is modified after the two feature commits.

Then run:

```powershell
git add README.md
git commit -m "docs: describe preview grid exports"
```
