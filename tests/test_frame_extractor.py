import pytest

from wallpaper_exporter.frame_extractor import (
    compute_timestamps,
    frame_filename,
    scaled_size,
)
from wallpaper_exporter.paths import frames_folder_for


def test_compute_timestamps_spreads_frames_from_start():
    assert compute_timestamps(1000, 60000, 1.5, 4) == [1000, 2500, 4000, 5500]


def test_compute_timestamps_drops_frames_beyond_duration():
    assert compute_timestamps(59000, 60000, 1.0, 5) == [59000]


def test_compute_timestamps_returns_empty_when_start_is_at_the_end():
    assert compute_timestamps(60000, 60000, 1.0, 5) == []


def test_compute_timestamps_keeps_all_frames_without_duration():
    assert compute_timestamps(0, None, 2.0, 3) == [0, 2000, 4000]
    assert compute_timestamps(0, 0, 2.0, 3) == [0, 2000, 4000]


def test_compute_timestamps_rounds_interval_to_milliseconds():
    assert compute_timestamps(0, None, 0.333, 3) == [0, 333, 666]


@pytest.mark.parametrize(
    "start_ms, duration_ms, interval_s, count",
    [
        (0, None, 1.0, 0),
        (0, None, 1.0, -3),
        (0, None, 0.0, 5),
        (0, None, -1.0, 5),
        (-1, None, 1.0, 5),
    ],
)
def test_compute_timestamps_rejects_invalid_parameters(
    start_ms, duration_ms, interval_s, count
):
    with pytest.raises(ValueError):
        compute_timestamps(start_ms, duration_ms, interval_s, count)


def test_frame_filename_is_zero_padded():
    assert frame_filename(1) == "frame_001.png"
    assert frame_filename(12) == "frame_012.png"
    assert frame_filename(123) == "frame_123.png"
    assert frame_filename(1234) == "frame_1234.png"


def test_frame_filename_rejects_non_positive_index():
    with pytest.raises(ValueError):
        frame_filename(0)


def test_scaled_size_keeps_original_when_no_target_width():
    assert scaled_size((3840, 2160), None) == (3840, 2160)
    assert scaled_size((3840, 2160), 0) == (3840, 2160)


def test_scaled_size_scales_width_and_keeps_aspect_ratio():
    assert scaled_size((3840, 2160), 1920) == (1920, 1080)
    assert scaled_size((1920, 1080), 960) == (960, 540)
    assert scaled_size((1080, 1920), 540) == (540, 960)


def test_scaled_size_rejects_invalid_frame_size():
    with pytest.raises(ValueError):
        scaled_size((0, 100), 1920)
    with pytest.raises(ValueError):
        scaled_size((100, 0), 1920)


def test_frames_folder_for_sanitizes_title(tmp_path):
    folder = frames_folder_for(tmp_path, 'My/Video: "Cool"')

    assert folder == tmp_path / "视频帧" / "My_Video_ _Cool_"
    assert folder.name != "My/Video: \"Cool\""
