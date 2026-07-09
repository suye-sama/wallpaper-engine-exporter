from importlib import import_module
from pathlib import Path


def test_wallpaper_engine_helpers_live_in_package():
    package = "wallpaper_exporter.wallpaper_engine"

    assert import_module(f"{package}.compose_we_auto")
    assert import_module(f"{package}.compose_we_static")
    assert import_module(f"{package}.render_we_scene")


def test_wallpaper_engine_helpers_are_not_root_scripts():
    root = Path(__file__).resolve().parents[1]

    assert not (root / "compose_we_auto.py").exists()
    assert not (root / "compose_we_static.py").exists()
    assert not (root / "render_we_scene.py").exists()
