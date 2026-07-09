import json
from pathlib import Path

from PIL import Image

from wallpaper_exporter.wallpaper_engine.render_we_scene import (
    build_close_wallpaper_command,
    build_open_wallpaper_command,
    build_parser,
    default_output_path,
    ensure_wallpaper_file,
    image_is_nearly_black,
    launch_wallpaper_window,
    stage_wallpaper_file_for_engine,
)


def test_build_open_wallpaper_command_uses_window_and_size_flags():
    command = build_open_wallpaper_command(
        Path(r"D:\we\wallpaper64.exe"),
        Path(r"D:\workshop\project.json"),
        "CodexTest",
        3840,
        2160,
        x=0,
        y=0,
        activate=True,
        borderless=True,
    )

    assert command == [
        r"D:\we\wallpaper64.exe",
        "-control",
        "openWallpaper",
        "-file",
        r"D:\workshop\project.json",
        "-playInWindow",
        "CodexTest",
        "-width",
        "3840",
        "-height",
        "2160",
        "-x",
        "0",
        "-y",
        "0",
        "-activate",
        "-borderless",
    ]


def test_build_close_wallpaper_command_targets_named_window():
    command = build_close_wallpaper_command(
        Path(r"D:\we\wallpaper64.exe"), "CodexTest"
    )

    assert command == [
        r"D:\we\wallpaper64.exe",
        "-control",
        "closeWallpaper",
        "-location",
        "CodexTest",
    ]


def test_ensure_wallpaper_file_prefers_existing_project_json(tmp_path):
    project = tmp_path / "project.json"
    project.write_text('{"file":"scene.json","type":"scene"}', encoding="utf-8")
    (tmp_path / "scene.json").write_text("{}", encoding="utf-8")

    resolved = ensure_wallpaper_file(tmp_path)

    assert resolved == project
    assert not (tmp_path / "_codex_render_project.json").exists()


def test_ensure_wallpaper_file_creates_minimal_project_for_scene_folder(tmp_path):
    scene = tmp_path / "scene.json"
    scene.write_text("{}", encoding="utf-8")

    resolved = ensure_wallpaper_file(tmp_path)

    assert resolved == tmp_path / "_codex_render_project.json"
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    assert payload == {
        "file": "scene.json",
        "title": tmp_path.name,
        "type": "scene",
    }


def test_default_output_path_uses_input_parent_and_resolution():
    output = default_output_path(Path(r"D:\workshop\project.json"), 1280, 720)

    assert output == Path(r"D:\workshop\we_render_capture_1280x720.png")


def test_launch_wallpaper_window_uses_non_blocking_popen(monkeypatch):
    calls = []

    class DummyProcess:
        pass

    def fake_popen(command):
        calls.append(command)
        return DummyProcess()

    monkeypatch.setattr(
        "wallpaper_exporter.wallpaper_engine.render_we_scene.subprocess.Popen",
        fake_popen,
    )

    process = launch_wallpaper_window(["wallpaper64.exe", "-control", "openWallpaper"])

    assert isinstance(process, DummyProcess)
    assert calls == [["wallpaper64.exe", "-control", "openWallpaper"]]


def test_parser_defaults_wait_long_enough_for_scene_first_frame():
    args = build_parser().parse_args(["scene-folder"])

    assert args.wait == 20.0


def test_stage_wallpaper_file_for_engine_returns_ascii_paths_unchanged(tmp_path):
    project = tmp_path / "project.json"
    project.write_text("{}", encoding="utf-8")

    staged, cleanup = stage_wallpaper_file_for_engine(project)

    assert staged == project
    assert cleanup is None


def test_stage_wallpaper_file_for_engine_copies_non_ascii_scene(tmp_path):
    scene_dir = tmp_path / "待合成"
    materials = scene_dir / "materials"
    materials.mkdir(parents=True)
    project = scene_dir / "_codex_render_project.json"
    project.write_text('{"file":"scene.json","type":"scene"}', encoding="utf-8")
    (scene_dir / "scene.json").write_text("{}", encoding="utf-8")
    (materials / "天空2.png").write_bytes(b"fake")
    (scene_dir / "we_render_capture_3840x2160.png").write_bytes(b"large-output")

    staged, cleanup = stage_wallpaper_file_for_engine(project)
    try:
        assert staged.name == project.name
        assert staged != project
        assert staged.exists()
        assert (staged.parent / "scene.json").exists()
        assert (staged.parent / "materials" / "天空2.png").exists()
        assert not (staged.parent / "we_render_capture_3840x2160.png").exists()
    finally:
        assert cleanup is not None
        cleanup.cleanup()


def test_image_is_nearly_black_detects_empty_capture():
    assert image_is_nearly_black(Image.new("RGB", (2, 2), (0, 0, 0)))
    assert not image_is_nearly_black(Image.new("RGB", (2, 2), (0, 40, 0)))
