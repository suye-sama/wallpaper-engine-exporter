from pathlib import Path

from wallpaper_exporter import settings


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_root_uses_pyinstaller_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(settings.sys, "frozen", True, raising=False)
    monkeypatch.setattr(settings.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert settings.runtime_root() == tmp_path


def test_windows_build_script_bundles_repkg_and_entrypoint():
    script = ROOT / "scripts" / "build_windows.ps1"

    text = script.read_text(encoding="utf-8")

    assert "PyInstaller" in text
    assert "tools\\RePKG\\RePKG.exe" in text
    assert "pyinstaller_entry.py" in text
    assert "--add-data" in text


def test_build_requirements_include_pyinstaller():
    text = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")

    assert "PyInstaller" in text
