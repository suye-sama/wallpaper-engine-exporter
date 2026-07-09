import json
from pathlib import Path

from PIL import Image

from wallpaper_exporter.wallpaper_engine.compose_we_auto import analyze_scene, compose_auto


def write_scene(root: Path, objects: list[dict]) -> None:
    payload = {
        "general": {"orthogonalprojection": {"width": 100, "height": 50}},
        "objects": objects,
    }
    (root / "scene.json").write_text(json.dumps(payload), encoding="utf-8")


def add_material(root: Path, name: str, *, puppet: bool = False) -> None:
    models = root / "models"
    materials = root / "materials"
    models.mkdir(exist_ok=True)
    materials.mkdir(exist_ok=True)
    model_payload = {"material": f"materials/{name}.json"}
    if puppet:
        model_payload["puppet"] = f"models/{name}_puppet.mdl"
    (models / f"{name}.json").write_text(json.dumps(model_payload), encoding="utf-8")
    Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(materials / f"{name}.png")


def test_analyze_scene_prefers_static_for_regular_image_layers(tmp_path):
    add_material(tmp_path, "bg")
    write_scene(
        tmp_path,
        [
            {
                "name": "bg",
                "image": "models/bg.json",
                "visible": True,
            }
        ],
    )

    analysis = analyze_scene(tmp_path)

    assert analysis.method == "static"
    assert analysis.puppet_models == []
    assert analysis.static_image_layers == 1


def test_analyze_scene_uses_render_for_puppet_models(tmp_path):
    add_material(tmp_path, "character", puppet=True)
    write_scene(
        tmp_path,
        [
            {
                "name": "character",
                "image": "models/character.json",
                "visible": True,
            }
        ],
    )

    analysis = analyze_scene(tmp_path)

    assert analysis.method == "render"
    assert analysis.puppet_models == ["models/character.json"]
    assert "puppet" in analysis.reasons[0]


def test_analyze_scene_uses_render_when_visible_image_has_no_static_material(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    (models / "missing.json").write_text("{}", encoding="utf-8")
    write_scene(
        tmp_path,
        [
            {
                "name": "missing",
                "image": "models/missing.json",
                "visible": True,
            }
        ],
    )

    analysis = analyze_scene(tmp_path)

    assert analysis.method == "render"
    assert analysis.missing_static_layers == ["missing"]


def test_compose_auto_calls_static_composer_for_static_scene(tmp_path, monkeypatch):
    add_material(tmp_path, "bg")
    write_scene(
        tmp_path,
        [
            {
                "name": "bg",
                "image": "models/bg.json",
                "visible": True,
            }
        ],
    )
    calls = []

    def fake_compose_scene(input_dir, output_path, *, draw_hidden=False):
        calls.append((input_dir, output_path, draw_hidden))
        return {"output": str(output_path), "drawn": [{"name": "bg"}], "skipped": []}

    monkeypatch.setattr(
        "wallpaper_exporter.wallpaper_engine.compose_we_auto.compose_scene",
        fake_compose_scene,
    )
    monkeypatch.setattr(
        "wallpaper_exporter.wallpaper_engine.compose_we_auto.render_scene",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("render called")),
    )

    result = compose_auto(tmp_path, tmp_path / "auto.png")

    assert result["method"] == "static"
    assert calls == [(tmp_path, tmp_path / "auto.png", False)]


def test_compose_auto_calls_renderer_for_puppet_scene(tmp_path, monkeypatch):
    add_material(tmp_path, "character", puppet=True)
    render_input = tmp_path / "project.json"
    render_input.write_text('{"file":"scene.json"}', encoding="utf-8")
    write_scene(
        tmp_path,
        [
            {
                "name": "character",
                "image": "models/character.json",
                "visible": True,
            }
        ],
    )
    calls = []

    def fake_render_scene(input_path, output_path, **kwargs):
        calls.append((input_path, output_path, kwargs))
        return {"output": str(output_path), "captured_size": (100, 50)}

    monkeypatch.setattr(
        "wallpaper_exporter.wallpaper_engine.compose_we_auto.render_scene",
        fake_render_scene,
    )

    result = compose_auto(
        tmp_path,
        tmp_path / "auto.png",
        render_input=render_input,
        width=100,
        height=50,
    )

    assert result["method"] == "render"
    assert calls[0][0] == render_input
    assert calls[0][1] == tmp_path / "auto.png"
    assert calls[0][2]["width"] == 100
    assert calls[0][2]["height"] == 50
