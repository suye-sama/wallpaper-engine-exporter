import json

from wallpaper_exporter.indexer import scan_workshop


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_scan_workshop_reads_project_metadata(tmp_path):
    item = tmp_path / "123"
    item.mkdir()
    write_json(
        item / "project.json",
        {
            "title": "海边",
            "type": "scene",
            "file": "scene.pkg",
            "preview": "preview.jpg",
        },
    )
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
