import json

import pytest

from wallpaper_exporter.exporter import (
    ExportNeedsRenderCapture,
    ExportOptions,
    extract_scene_pkg,
    export_wallpaper,
)
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

    output_dir = tmp_path / "exports" / "导出原图" / "A_B"
    info = json.loads((output_dir / "info.json").read_text(encoding="utf-8"))
    assert result.method == "direct"
    assert (output_dir / "original.png").read_bytes() == b"png"
    assert info["workshop_id"] == "1"
    assert info["method"] == "direct"


def test_export_wallpaper_requires_confirmation_for_render_scene(tmp_path, monkeypatch):
    scene_dir = tmp_path / "scene"
    scene_dir.mkdir()
    (scene_dir / "scene.json").write_text(
        '{"general":{"orthogonalprojection":{"width":1,"height":1}},"objects":[]}',
        encoding="utf-8",
    )
    entry = WallpaperEntry(
        workshop_id="2",
        title="Render",
        root=scene_dir,
        project_type="scene",
        main_file=scene_dir / "scene.pkg",
        has_scene_json=True,
    )

    def fake_compose_auto(*args, **kwargs):
        return {
            "method": "render",
            "output": str(kwargs.get("output_path") or args[1]),
            "analysis": {"reasons": ["puppet"]},
        }

    monkeypatch.setattr("wallpaper_exporter.exporter.compose_auto", fake_compose_auto)

    with pytest.raises(ExportNeedsRenderCapture):
        export_wallpaper(
            entry,
            make_settings(tmp_path),
            ExportOptions(allow_render_capture=False),
        )


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
        (destination / "scene.json").write_text(
            '{"general":{"orthogonalprojection":{"width":1,"height":1}},"objects":[]}',
            encoding="utf-8",
        )

    def fake_compose_auto(input_path, output_path, **kwargs):
        output_path.write_bytes(b"png")
        return {"method": "static", "analysis": {"reasons": ["regular"]}}

    monkeypatch.setattr(
        "wallpaper_exporter.exporter.extract_scene_pkg",
        fake_extract,
        raising=False,
    )
    monkeypatch.setattr("wallpaper_exporter.exporter.compose_auto", fake_compose_auto)

    result = export_wallpaper(entry, settings, ExportOptions())

    assert result.method == "static"
    assert calls == [(scene_pkg, item, settings.repkg_path)]


def test_extract_scene_pkg_uses_overwrite_flag(tmp_path, monkeypatch):
    repkg = tmp_path / "RePKG.exe"
    repkg.write_bytes(b"exe")
    scene_pkg = tmp_path / "scene.pkg"
    scene_pkg.write_bytes(b"pkg")
    destination = tmp_path / "out"
    commands = []

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, **kwargs):
        commands.append(command)
        (destination / "scene.json").write_text("{}", encoding="utf-8")
        return Completed()

    monkeypatch.setattr("wallpaper_exporter.exporter.subprocess.run", fake_run)

    extract_scene_pkg(scene_pkg, destination, repkg)

    assert commands == [
        [str(repkg), "extract", str(scene_pkg), "-o", str(destination), "--overwrite"]
    ]
