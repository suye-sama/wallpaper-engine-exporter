import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QMediaPlayer

from wallpaper_exporter import video_page as video_page_module
from wallpaper_exporter.indexer import WallpaperEntry
from wallpaper_exporter.settings import AppSettings
from wallpaper_exporter.video_page import VideoFramePage, format_time, video_entries


class StubExtractor(QObject):
    progress = Signal(int, int)
    finished = Signal(list)
    failed = Signal(str)

    instances: list["StubExtractor"] = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self.started: list[tuple] = []
        StubExtractor.instances.append(self)

    def start(self, video_path, timestamps, output_dir, target_width=None):
        self.started.append((video_path, timestamps, output_dir, target_width))
        return True


def _settings(tmp_path) -> AppSettings:
    return AppSettings(
        workshop_dir=tmp_path / "workshop",
        export_root=tmp_path / "exports",
        repkg_path=tmp_path / "RePKG.exe",
        wallpaper_exe=tmp_path / "wallpaper64.exe",
    )


def _video_entry(tmp_path, workshop_id="100", title="Beach loop") -> WallpaperEntry:
    video = tmp_path / workshop_id / "video.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"")
    return WallpaperEntry(
        workshop_id=workshop_id,
        title=title,
        root=video.parent,
        project_type="video",
        main_file=video,
    )


def _page():
    StubExtractor.instances = []
    return VideoFramePage()


def test_format_time_renders_minutes_and_hours():
    assert format_time(0) == "0:00"
    assert format_time(65_000) == "1:05"
    assert format_time(3_600_000) == "1:00:00"
    assert format_time(3_661_000) == "1:01:01"


def test_video_entries_keeps_only_playable_videos(tmp_path):
    video_entry = _video_entry(tmp_path)
    image = tmp_path / "200" / "image.jpg"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"")
    image_entry = WallpaperEntry(
        workshop_id="200",
        title="Image",
        root=image.parent,
        main_file=image,
    )
    scene_entry = WallpaperEntry(
        workshop_id="300",
        title="Scene",
        root=tmp_path / "300",
        project_type="scene",
    )
    broken_entry = WallpaperEntry(
        workshop_id="400",
        title="Broken",
        root=tmp_path / "400",
        error="project.json not found",
    )
    missing_video_entry = WallpaperEntry(
        workshop_id="500",
        title="Missing",
        root=tmp_path / "500",
        main_file=tmp_path / "500" / "gone.mp4",
    )

    result = video_entries(
        [video_entry, image_entry, scene_entry, broken_entry, missing_video_entry]
    )

    assert result == [video_entry]


def test_set_entries_lists_videos_and_selects_first(tmp_path):
    page = _page()
    video_entry = _video_entry(tmp_path)

    page.set_entries([video_entry])

    assert page.count_label.text() == "1 个视频"
    assert page.video_list.count() == 1
    assert page.current_entry is video_entry
    assert Path(page.player.source().toLocalFile()) == video_entry.main_file
    assert page.play_button.isEnabled()


def test_set_entries_without_videos_clears_selection(tmp_path):
    page = _page()
    video_entry = _video_entry(tmp_path)
    page.set_entries([video_entry])

    page.set_entries([])

    assert page.count_label.text() == "0 个视频"
    assert page.current_entry is None
    assert not page.play_button.isEnabled()
    assert page.player.source().isEmpty()


def test_search_filters_video_list(tmp_path):
    page = _page()
    first = _video_entry(tmp_path, "100", "First beach")
    second = _video_entry(tmp_path, "200", "Mountain")

    page.set_entries([first, second])
    page.search_edit.setText("beach")

    assert page.filtered_entries == [first]
    assert page.video_list.count() == 1
    assert page.count_label.text() == "1 个视频"


def test_extract_uses_current_position_and_parameters(tmp_path, monkeypatch):
    page = _page()
    settings = _settings(tmp_path)
    video_entry = _video_entry(tmp_path, "100", "My cool video")
    monkeypatch.setattr(video_page_module, "VideoFrameExtractor", StubExtractor)

    page.set_settings(settings)
    page.set_entries([video_entry])
    page.video_list.setCurrentRow(0)
    page.player.durationChanged.emit(60_000)

    assert page.extract_button.isEnabled()

    page.position_slider.setValue(5_000)
    page.interval_spin.setValue(2.0)
    page.count_spin.setValue(3)
    page.size_combo.setCurrentIndex(1)
    page.width_spin.setValue(1280)
    page.extract_button.click()

    assert not page.extract_button.isEnabled()
    extractor = StubExtractor.instances[-1]
    video_path, timestamps, output_dir, target_width = extractor.started[0]
    assert video_path == video_entry.main_file
    assert timestamps == [5_000, 7_000, 9_000]
    assert output_dir == settings.export_root / "视频帧" / "My cool video"
    assert target_width == 1280

    extractor.finished.emit([output_dir / "frame_001.png"])

    assert page.extract_button.isEnabled()
    assert page.open_button.isEnabled()
    assert "已保存 1 帧" in page.result_label.text()
    assert page._last_output_dir == output_dir


def test_extract_defaults_to_original_size_and_five_frames(tmp_path, monkeypatch):
    page = _page()
    settings = _settings(tmp_path)
    video_entry = _video_entry(tmp_path)
    monkeypatch.setattr(video_page_module, "VideoFrameExtractor", StubExtractor)

    page.set_settings(settings)
    page.set_entries([video_entry])
    page.player.durationChanged.emit(120_000)
    page.position_slider.setValue(10_000)
    page.extract_button.click()

    extractor = StubExtractor.instances[-1]
    _, timestamps, _, target_width = extractor.started[0]
    assert timestamps == [10_000, 11_000, 12_000, 13_000, 14_000]
    assert target_width is None


def test_extract_reports_failure_and_recovers(tmp_path, monkeypatch):
    page = _page()
    settings = _settings(tmp_path)
    video_entry = _video_entry(tmp_path)
    monkeypatch.setattr(video_page_module, "VideoFrameExtractor", StubExtractor)

    page.set_settings(settings)
    page.set_entries([video_entry])
    page.player.durationChanged.emit(30_000)
    page.extract_button.click()

    extractor = StubExtractor.instances[-1]
    extractor.failed.emit("boom")

    assert page.extract_button.isEnabled()
    assert page.result_label.text() == "boom"
    assert not page.open_button.isEnabled()

    page.extract_button.click()
    assert StubExtractor.instances[-1].started


def test_extract_disabled_without_duration_or_selection(tmp_path):
    page = _page()
    video_entry = _video_entry(tmp_path)

    page.set_settings(_settings(tmp_path))
    page.set_entries([video_entry])

    assert not page.extract_button.isEnabled()

    page.player.durationChanged.emit(30_000)
    assert page.extract_button.isEnabled()


def test_width_spin_only_visible_in_custom_size_mode(tmp_path):
    page = _page()

    assert page.width_spin.isHidden()

    page.size_combo.setCurrentIndex(1)
    assert not page.width_spin.isHidden()
    assert page.width_spin.isEnabled()

    page.size_combo.setCurrentIndex(0)
    assert page.width_spin.isHidden()


def test_output_hint_shows_original_and_scaled_sizes(tmp_path):
    page = _page()
    assert page.output_size_label.text() == ""

    page._video_resolution = (2560, 1440)
    page._update_output_hint()
    assert "2560×1440（原始）" in page.output_size_label.text()

    page.size_combo.setCurrentIndex(1)
    page.width_spin.setValue(1280)
    assert "2560×1440 → 1280×720" in page.output_size_label.text()


def test_loaded_media_reads_resolution_and_updates_hint(monkeypatch, tmp_path):
    page = _page()
    video_entry = _video_entry(tmp_path)
    page.set_entries([video_entry])

    def fake_read_resolution() -> None:
        page._video_resolution = (2560, 1440)
        page._update_output_hint()

    monkeypatch.setattr(page, "_read_video_resolution", fake_read_resolution)

    page.player.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)

    assert "2560×1440（原始）" in page.output_size_label.text()


def test_selecting_video_shows_poster_page_with_preview_image(tmp_path):
    page = _page()
    video_entry = _video_entry(tmp_path)
    preview = video_entry.root / "preview.png"
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(0xFF0000)
    image.save(str(preview))
    video_entry.preview_path = preview

    page.set_entries([video_entry])

    assert page.player_stack.currentWidget() is page.poster_label
    assert page.poster_label._poster is not None


def test_poster_without_preview_shows_placeholder_text(tmp_path):
    page = _page()
    video_entry = _video_entry(tmp_path)

    page.set_entries([video_entry])

    assert page.player_stack.currentWidget() is page.poster_label
    assert page.poster_label.text() == "没有预览"


def test_playing_switches_from_poster_to_video_widget(tmp_path):
    page = _page()
    video_entry = _video_entry(tmp_path)
    page.set_entries([video_entry])

    page.player.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)
    assert page.player_stack.currentWidget() is page.video_widget

    page.player.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PausedState)
    assert page.player_stack.currentWidget() is page.video_widget
