#!/usr/bin/env python
"""Auto-select static composition or Wallpaper Engine capture for scene folders."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .compose_we_static import (
    compose_scene,
    is_visible,
    material_png_for_model,
    read_json,
)
from .render_we_scene import render_scene


@dataclass
class SceneAnalysis:
    method: str
    reasons: list[str] = field(default_factory=list)
    canvas_size: tuple[int, int] | None = None
    static_image_layers: int = 0
    missing_static_layers: list[str] = field(default_factory=list)
    puppet_models: list[str] = field(default_factory=list)
    utility_layers: list[str] = field(default_factory=list)
    dynamic_layers: list[str] = field(default_factory=list)
    hidden_layers: list[str] = field(default_factory=list)


def default_output_path(input_path: Path) -> Path:
    path = Path(input_path)
    output_dir = path if path.is_dir() else path.parent
    return output_dir / "composite_auto.png"


def _canvas_size(scene: dict[str, Any]) -> tuple[int, int] | None:
    projection = scene.get("general", {}).get("orthogonalprojection")
    if not projection:
        return None
    return int(projection["width"]), int(projection["height"])


def _object_name(obj: dict[str, Any], index: int) -> str:
    return str(obj.get("name") or f"object-{index}")


def analyze_scene(input_dir: Path, *, draw_hidden: bool = False) -> SceneAnalysis:
    root = Path(input_dir)
    scene = read_json(root / "scene.json")
    analysis = SceneAnalysis(method="static", canvas_size=_canvas_size(scene))

    for index, obj in enumerate(scene.get("objects", [])):
        name = _object_name(obj, index)
        if not draw_hidden and not is_visible(obj.get("visible", True)):
            analysis.hidden_layers.append(name)
            continue

        if obj.get("particle") or obj.get("sound") or obj.get("text") is not None:
            analysis.dynamic_layers.append(name)

        image_ref = obj.get("image")
        if not image_ref:
            continue

        if str(image_ref).startswith("models/util/"):
            analysis.utility_layers.append(name)
            continue

        png_path, model = material_png_for_model(root, str(image_ref))
        if model and model.get("puppet"):
            analysis.puppet_models.append(str(image_ref))

        if png_path is not None:
            analysis.static_image_layers += 1
        else:
            analysis.missing_static_layers.append(name)

    if analysis.puppet_models:
        analysis.method = "render"
        analysis.reasons.append(
            f"puppet model(s) detected: {', '.join(analysis.puppet_models)}"
        )
    if analysis.missing_static_layers:
        analysis.method = "render"
        analysis.reasons.append(
            "visible image layer(s) have no static PNG/JPG: "
            + ", ".join(analysis.missing_static_layers)
        )
    if not analysis.reasons:
        analysis.reasons.append("regular static image layers only")

    return analysis


def _analysis_to_dict(analysis: SceneAnalysis) -> dict[str, Any]:
    return {
        "method": analysis.method,
        "reasons": analysis.reasons,
        "canvas_size": analysis.canvas_size,
        "static_image_layers": analysis.static_image_layers,
        "missing_static_layers": analysis.missing_static_layers,
        "puppet_models": analysis.puppet_models,
        "utility_layers": analysis.utility_layers,
        "dynamic_layers": analysis.dynamic_layers,
        "hidden_layers": analysis.hidden_layers,
    }


def compose_auto(
    input_path: Path,
    output_path: Path | None = None,
    *,
    render_input: Path | None = None,
    force: str = "auto",
    width: int | None = None,
    height: int | None = None,
    wallpaper_exe: Path | None = None,
    wait_seconds: float = 3.0,
    window_timeout: float = 10.0,
    window_name: str | None = None,
    keep_open: bool = False,
    draw_hidden: bool = False,
    fallback_to_render: bool = True,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output = Path(output_path) if output_path else default_output_path(input_path)

    if input_path.is_file():
        analysis = SceneAnalysis(
            method="render",
            reasons=["file input cannot be statically composed"],
        )
    else:
        analysis = analyze_scene(input_path, draw_hidden=draw_hidden)

    method = force if force != "auto" else analysis.method

    if method == "static":
        try:
            static_summary = compose_scene(input_path, output, draw_hidden=draw_hidden)
            return {
                "method": "static",
                "output": str(output),
                "analysis": _analysis_to_dict(analysis),
                "summary": static_summary,
            }
        except Exception as exc:
            if force == "static" or not fallback_to_render:
                raise
            analysis.method = "render"
            analysis.reasons.append(f"static compose failed: {exc}")
            method = "render"

    if method != "render":
        raise ValueError(f"Unknown compose method: {method}")

    render_source = Path(render_input) if render_input else input_path
    render_width, render_height = _render_size(width, height, analysis)
    render_summary = render_scene(
        render_source,
        output,
        wallpaper_exe=wallpaper_exe,
        width=render_width,
        height=render_height,
        wait_seconds=wait_seconds,
        window_timeout=window_timeout,
        window_name=window_name,
        keep_open=keep_open,
    )
    return {
        "method": "render",
        "output": str(output),
        "analysis": _analysis_to_dict(analysis),
        "summary": render_summary,
    }


def _render_size(
    width: int | None, height: int | None, analysis: SceneAnalysis
) -> tuple[int, int]:
    if width and height:
        return width, height
    if analysis.canvas_size:
        canvas_width, canvas_height = analysis.canvas_size
        return width or canvas_width, height or canvas_height
    return width or 3840, height or 2160


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Auto-compose a Wallpaper Engine scene: static when possible, render capture when needed."
    )
    parser.add_argument("input", type=Path, help="Scene folder, project.json, or scene.pkg.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output PNG path. Defaults to INPUT/composite_auto.png.",
    )
    parser.add_argument(
        "--render-input",
        type=Path,
        help="Original workshop project.json/scene.pkg to use when render capture is needed.",
    )
    parser.add_argument(
        "--force",
        choices=("auto", "static", "render"),
        default="auto",
        help="Override automatic method selection.",
    )
    parser.add_argument("--width", type=int, help="Render width for capture fallback.")
    parser.add_argument("--height", type=int, help="Render height for capture fallback.")
    parser.add_argument("--wallpaper-exe", type=Path, help="Path to wallpaper64.exe.")
    parser.add_argument("--wait", type=float, default=3.0, help="Seconds to wait before capture.")
    parser.add_argument(
        "--window-timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for the Wallpaper Engine pop-out window.",
    )
    parser.add_argument("--window-name", help="Temporary Wallpaper Engine window name.")
    parser.add_argument("--keep-open", action="store_true", help="Keep render window open.")
    parser.add_argument(
        "--draw-hidden",
        action="store_true",
        help="Include scene objects whose visible value is false.",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Do not fall back to render capture if static composition fails.",
    )
    return parser


def print_summary(result: dict[str, Any]) -> None:
    analysis = result["analysis"]
    print(f"Saved: {result['output']}")
    print(f"Method: {result['method']}")
    print(f"Reason: {'; '.join(analysis['reasons'])}")
    print(f"Static image layers: {analysis['static_image_layers']}")
    if analysis["puppet_models"]:
        print(f"Puppet models: {', '.join(analysis['puppet_models'])}")
    if analysis["missing_static_layers"]:
        print(f"Missing static layers: {', '.join(analysis['missing_static_layers'])}")
    if analysis["dynamic_layers"]:
        print(f"Dynamic/non-image layers ignored by static: {len(analysis['dynamic_layers'])}")
    if analysis["hidden_layers"]:
        print(f"Hidden layers skipped: {len(analysis['hidden_layers'])}")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = compose_auto(
            args.input,
            args.output,
            render_input=args.render_input,
            force=args.force,
            width=args.width,
            height=args.height,
            wallpaper_exe=args.wallpaper_exe,
            wait_seconds=args.wait,
            window_timeout=args.window_timeout,
            window_name=args.window_name,
            keep_open=args.keep_open,
            draw_hidden=args.draw_hidden,
            fallback_to_render=not args.no_fallback,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
