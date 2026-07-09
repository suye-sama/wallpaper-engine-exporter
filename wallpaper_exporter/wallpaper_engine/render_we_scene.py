#!/usr/bin/env python
"""Render a Wallpaper Engine scene in-engine and capture the final frame."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from ctypes import wintypes

from PIL import Image

GENERATED_PROJECT_NAME = "_codex_render_project.json"
PW_RENDERFULLCONTENT = 0x00000002
_WIN32_DLLS: tuple[Any, Any] | None = None
STAGE_IGNORE_PREFIXES = ("we_render", "composite")
STAGE_IGNORE_NAMES = {"steam_preview.jpg", "materials_top_png_composite.png"}
DEFAULT_RENDER_WAIT_SECONDS = 20.0


def ensure_wallpaper_file(input_path: Path) -> Path:
    """Return a Wallpaper Engine-openable file for a file or extracted scene folder."""
    path = Path(input_path)
    if path.is_file():
        return path
    if not path.exists():
        raise FileNotFoundError(f"Input does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Input is neither a file nor a directory: {path}")

    project_path = path / "project.json"
    if project_path.exists():
        return project_path

    scene_path = path / "scene.json"
    if not scene_path.exists():
        raise FileNotFoundError(f"Directory does not contain project.json or scene.json: {path}")

    generated_path = path / GENERATED_PROJECT_NAME
    payload = {
        "file": "scene.json",
        "title": path.name,
        "type": "scene",
    }
    generated_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent="\t") + "\n",
        encoding="utf-8",
    )
    return generated_path


def default_output_path(input_path: Path, width: int, height: int) -> Path:
    path = Path(input_path)
    output_dir = path if path.is_dir() else path.parent
    return output_dir / f"we_render_capture_{width}x{height}.png"


def build_open_wallpaper_command(
    wallpaper_exe: Path,
    wallpaper_file: Path,
    window_name: str,
    width: int,
    height: int,
    *,
    x: int = 0,
    y: int = 0,
    activate: bool = True,
    borderless: bool = True,
) -> list[str]:
    command = [
        str(wallpaper_exe),
        "-control",
        "openWallpaper",
        "-file",
        str(wallpaper_file),
        "-playInWindow",
        window_name,
        "-width",
        str(width),
        "-height",
        str(height),
        "-x",
        str(x),
        "-y",
        str(y),
    ]
    if activate:
        command.append("-activate")
    if borderless:
        command.append("-borderless")
    return command


def build_close_wallpaper_command(wallpaper_exe: Path, window_name: str) -> list[str]:
    return [
        str(wallpaper_exe),
        "-control",
        "closeWallpaper",
        "-location",
        window_name,
    ]


def path_is_ascii(path: Path) -> bool:
    try:
        str(path).encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def _stage_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        lower_name = name.lower()
        if lower_name in STAGE_IGNORE_NAMES:
            ignored.add(name)
            continue
        if lower_name.endswith(".png") and lower_name.startswith(STAGE_IGNORE_PREFIXES):
            ignored.add(name)
    return ignored


def stage_wallpaper_file_for_engine(
    wallpaper_file: Path,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if path_is_ascii(wallpaper_file):
        return wallpaper_file, None

    cleanup = tempfile.TemporaryDirectory(prefix="codex_we_render_")
    source_root = wallpaper_file.parent
    staged_root = Path(cleanup.name) / "scene"
    shutil.copytree(source_root, staged_root, ignore=_stage_ignore)
    return staged_root / wallpaper_file.name, cleanup


def launch_wallpaper_window(command: list[str]) -> subprocess.Popen[Any]:
    return subprocess.Popen(command)


def close_wallpaper_window(
    command: list[str],
    process: subprocess.Popen[Any] | None,
    *,
    timeout: float = 5.0,
) -> None:
    try:
        subprocess.run(command, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        pass

    if process is None or process.poll() is not None:
        return

    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()


def resolve_wallpaper_exe(explicit_path: Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit_path is not None:
        candidates.append(Path(explicit_path))

    env_path = os.environ.get("WALLPAPER_ENGINE_EXE")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path(r"D:\GAME\steam\steamapps\common\wallpaper_engine\wallpaper64.exe"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\wallpaper64.exe"),
            Path(r"C:\Program Files\Steam\steamapps\common\wallpaper_engine\wallpaper64.exe"),
        ]
    )

    for name in ("wallpaper64.exe", "wallpaper32.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not find wallpaper64.exe. Pass --wallpaper-exe or set WALLPAPER_ENGINE_EXE."
    )


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Wallpaper Engine window capture is only supported on Windows.")


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", ctypes.c_uint32 * 3),
    ]


def _win32() -> tuple[Any, Any]:
    global _WIN32_DLLS
    if _WIN32_DLLS is not None:
        return _WIN32_DLLS

    _require_windows()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    user32.SetProcessDPIAware.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.GetWindowDC.restype = wintypes.HDC
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_uint]
    user32.PrintWindow.restype = wintypes.BOOL
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int

    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC,
        wintypes.HBITMAP,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.POINTER(_BITMAPINFO),
        ctypes.c_uint,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL

    _WIN32_DLLS = (user32, gdi32)
    return _WIN32_DLLS


def _raise_last_error(operation: str) -> None:
    code = ctypes.get_last_error()
    raise OSError(code, f"{operation} failed")


def set_process_dpi_aware() -> None:
    user32, _gdi32 = _win32()
    try:
        user32.SetProcessDPIAware()
    except AttributeError:
        pass


def find_window_by_title(title: str) -> int | None:
    user32, _gdi32 = _win32()
    found: list[int] = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    @enum_proc
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if buffer.value == title:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def wait_for_window(title: str, timeout: float) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hwnd = find_window_by_title(title)
        if hwnd:
            return hwnd
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for Wallpaper Engine window: {title}")


def _client_size(hwnd: int) -> tuple[int, int]:
    user32, _gdi32 = _win32()
    rect = _RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        _raise_last_error("GetClientRect")
    return rect.right - rect.left, rect.bottom - rect.top


def prepare_window(
    hwnd: int,
    width: int,
    height: int,
    *,
    x: int = 0,
    y: int = 0,
    topmost: bool = True,
) -> tuple[int, int]:
    user32, _gdi32 = _win32()
    hwnd_insert_after = wintypes.HWND(-1 if topmost else 0)
    swp_showwindow = 0x0040
    if not user32.SetWindowPos(
        hwnd,
        hwnd_insert_after,
        x,
        y,
        width,
        height,
        swp_showwindow,
    ):
        _raise_last_error("SetWindowPos")
    user32.SetForegroundWindow(hwnd)
    user32.SetCursorPos(x + width + 32, y + height + 32)
    return _client_size(hwnd)


def image_is_nearly_black(image: Image.Image, *, threshold: int = 8) -> bool:
    extrema = image.convert("L").getextrema()
    return extrema[1] <= threshold


def capture_window_with_printwindow(
    hwnd: int, output_path: Path, *, allow_black_capture: bool = False
) -> tuple[int, int]:
    user32, gdi32 = _win32()
    width, height = _client_size(hwnd)
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid window size: {width}x{height}")

    window_dc = user32.GetWindowDC(hwnd)
    if not window_dc:
        _raise_last_error("GetWindowDC")

    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    old_object = None

    try:
        if not memory_dc or not bitmap:
            _raise_last_error("CreateCompatibleBitmap")
        old_object = gdi32.SelectObject(memory_dc, bitmap)

        if not user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT):
            _raise_last_error("PrintWindow")

        bitmap_info = _BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = 0

        buffer = ctypes.create_string_buffer(width * height * 4)
        lines = gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            buffer,
            ctypes.byref(bitmap_info),
            0,
        )
        if lines != height:
            _raise_last_error("GetDIBits")

        image = Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
        if not allow_black_capture and image_is_nearly_black(image):
            raise RuntimeError(
                "Captured image is nearly black. The wallpaper may not have loaded yet, "
                "or this extracted folder cannot be opened directly by Wallpaper Engine. "
                "Try a larger --wait value or pass the original workshop project.json/scene.pkg."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGBA").save(output_path)
        return width, height
    finally:
        if old_object:
            gdi32.SelectObject(memory_dc, old_object)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if memory_dc:
            gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def render_scene(
    input_path: Path,
    output_path: Path | None = None,
    *,
    wallpaper_exe: Path | None = None,
    width: int = 3840,
    height: int = 2160,
    x: int = 0,
    y: int = 0,
    window_name: str | None = None,
    wait_seconds: float = DEFAULT_RENDER_WAIT_SECONDS,
    window_timeout: float = 10.0,
    activate: bool = True,
    borderless: bool = True,
    topmost: bool = True,
    keep_open: bool = False,
    allow_black_capture: bool = False,
) -> dict[str, Any]:
    set_process_dpi_aware()
    wallpaper_file = ensure_wallpaper_file(input_path)
    engine_wallpaper_file, stage_cleanup = stage_wallpaper_file_for_engine(wallpaper_file)
    resolved_exe = resolve_wallpaper_exe(wallpaper_exe)
    resolved_output = output_path or default_output_path(input_path, width, height)
    name = window_name or f"CodexWERender-{os.getpid()}"

    open_command = build_open_wallpaper_command(
        resolved_exe,
        engine_wallpaper_file,
        name,
        width,
        height,
        x=x,
        y=y,
        activate=activate,
        borderless=borderless,
    )
    close_command = build_close_wallpaper_command(resolved_exe, name)

    process = launch_wallpaper_window(open_command)
    captured_size: tuple[int, int] | None = None
    try:
        hwnd = wait_for_window(name, window_timeout)
        captured_size = prepare_window(hwnd, width, height, x=x, y=y, topmost=topmost)
        time.sleep(wait_seconds)
        captured_size = capture_window_with_printwindow(
            hwnd, resolved_output, allow_black_capture=allow_black_capture
        )
    finally:
        if not keep_open:
            close_wallpaper_window(close_command, process)
        if stage_cleanup is not None:
            stage_cleanup.cleanup()

    return {
        "input": str(input_path),
        "wallpaper_file": str(wallpaper_file),
        "engine_wallpaper_file": str(engine_wallpaper_file),
        "output": str(resolved_output),
        "requested_size": (width, height),
        "captured_size": captured_size,
        "window_name": name,
        "wallpaper_exe": str(resolved_exe),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a Wallpaper Engine scene with the real engine and capture a PNG."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="project.json, scene.pkg, or an extracted scene folder containing scene.json.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output PNG path. Defaults to INPUT_DIR/we_render_capture_WIDTHxHEIGHT.png.",
    )
    parser.add_argument("--wallpaper-exe", type=Path, help="Path to wallpaper64.exe.")
    parser.add_argument("--width", type=int, default=3840, help="Render width.")
    parser.add_argument("--height", type=int, default=2160, help="Render height.")
    parser.add_argument("--x", type=int, default=0, help="Window X position.")
    parser.add_argument("--y", type=int, default=0, help="Window Y position.")
    parser.add_argument("--window-name", help="Temporary Wallpaper Engine window name.")
    parser.add_argument(
        "--wait",
        type=float,
        default=DEFAULT_RENDER_WAIT_SECONDS,
        help="Seconds to wait after opening before capture.",
    )
    parser.add_argument(
        "--window-timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for the render window.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Do not close the Wallpaper Engine pop-out after capture.",
    )
    parser.add_argument("--no-activate", action="store_true", help="Do not activate the window.")
    parser.add_argument(
        "--no-borderless", action="store_true", help="Do not request a borderless window."
    )
    parser.add_argument("--no-topmost", action="store_true", help="Do not force topmost capture.")
    parser.add_argument(
        "--allow-black-capture",
        action="store_true",
        help="Save the frame even if it appears to be nearly black.",
    )
    return parser


def print_summary(summary: dict[str, Any]) -> None:
    print(f"Saved: {summary['output']}")
    print(f"Wallpaper file: {summary['wallpaper_file']}")
    if summary["engine_wallpaper_file"] != summary["wallpaper_file"]:
        print(f"Engine file: {summary['engine_wallpaper_file']}")
    print(f"Window: {summary['window_name']}")
    if summary["captured_size"]:
        width, height = summary["captured_size"]
        print(f"Captured: {width}x{height}")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summary = render_scene(
            args.input,
            args.output,
            wallpaper_exe=args.wallpaper_exe,
            width=args.width,
            height=args.height,
            x=args.x,
            y=args.y,
            window_name=args.window_name,
            wait_seconds=args.wait,
            window_timeout=args.window_timeout,
            activate=not args.no_activate,
            borderless=not args.no_borderless,
            topmost=not args.no_topmost,
            keep_open=args.keep_open,
            allow_black_capture=args.allow_black_capture,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
