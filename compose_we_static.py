#!/usr/bin/env python
"""Static composer for RePKG-extracted Wallpaper Engine scene folders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

STATIC_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def object_value(value: Any, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get("value", default)
    if value is None:
        return default
    return value


def parse_vec(value: Any, count: int, default: str = "0 0 0") -> list[float]:
    raw = object_value(value, default)
    if isinstance(raw, (int, float)):
        return [float(raw)] * count

    parts = str(raw).split()
    numbers = [float(part) for part in parts[:count]]
    while len(numbers) < count:
        numbers.append(0.0)
    return numbers


def is_visible(value: Any) -> bool:
    return bool(object_value(value, True))


def apply_opacity_mask(
    image: Image.Image, mask: Image.Image, alpha: float = 1.0
) -> Image.Image:
    """Apply Wallpaper Engine opacity-mask semantics to an RGBA image."""
    result = image.convert("RGBA")
    mask_luma = mask.convert("L")
    if mask_luma.size != result.size:
        mask_luma = mask_luma.resize(result.size, Image.Resampling.LANCZOS)

    red, green, blue, image_alpha = result.split()
    masked_alpha = ImageChops.multiply(image_alpha, mask_luma)
    if alpha != 1.0:
        masked_alpha = masked_alpha.point(lambda pixel: int(pixel * alpha))
    return Image.merge("RGBA", (red, green, blue, masked_alpha))


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def texture_to_png(root: Path, texture_ref: str) -> Path | None:
    texture_path = Path(texture_ref)
    if texture_path.suffix.lower() == ".png":
        candidate = root / "materials" / texture_path
    else:
        candidate = root / "materials" / f"{texture_ref}.png"
    return candidate if candidate.exists() else None


def static_image_for_material(material_path: Path) -> Path | None:
    for suffix in STATIC_IMAGE_SUFFIXES:
        candidate = material_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def material_png_for_model(root: Path, model_ref: str) -> tuple[Path | None, dict[str, Any] | None]:
    if not model_ref or not str(model_ref).startswith("models/"):
        return None, None

    model_path = root / model_ref
    if not model_path.exists():
        return None, None

    model = read_json(model_path)
    material_ref = model.get("material")
    if not material_ref:
        return None, model

    return static_image_for_material(root / material_ref), model


def alpha_float(value: Any) -> float:
    try:
        return float(object_value(value, 1.0))
    except (TypeError, ValueError):
        return 1.0


def apply_object_opacity_effects(root: Path, image: Image.Image, obj: dict[str, Any]) -> Image.Image:
    result = image
    for effect in obj.get("effects") or []:
        if effect.get("file") != "effects/opacity/effect.json":
            continue
        if not is_visible(effect.get("visible", True)):
            continue

        effect_alpha = 1.0
        for pass_def in effect.get("passes") or []:
            shader_values = pass_def.get("constantshadervalues") or {}
            effect_alpha = alpha_float(shader_values.get("alpha", effect_alpha))

            textures = pass_def.get("textures") or []
            if len(textures) < 2 or not textures[1]:
                result = apply_opacity_mask(
                    result, Image.new("L", result.size, 255), effect_alpha
                )
                continue

            mask_path = texture_to_png(root, textures[1])
            if mask_path is None:
                continue
            mask = Image.open(mask_path)
            result = apply_opacity_mask(result, mask, effect_alpha)
    return result


def resize_layer(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    result = image.convert("RGBA")
    if result.size == target_size:
        return result
    return result.resize(target_size, Image.Resampling.LANCZOS)


def apply_layer_alpha(image: Image.Image, alpha: float) -> Image.Image:
    if alpha == 1.0:
        return image
    red, green, blue, image_alpha = image.split()
    image_alpha = image_alpha.point(lambda pixel: int(pixel * alpha))
    return Image.merge("RGBA", (red, green, blue, image_alpha))


def layer_position(
    obj: dict[str, Any], canvas_height: int, target_size: tuple[int, int]
) -> tuple[int, int]:
    origin_x, origin_y, _ = parse_vec(obj.get("origin"), 3)
    center_y = canvas_height - origin_y
    width, height = target_size

    if obj.get("alignment", "center") == "left":
        return round(origin_x), round(center_y - height / 2)
    return round(origin_x - width / 2), round(center_y - height / 2)


def ignored_effect_names(obj: dict[str, Any]) -> list[str]:
    ignored = []
    for effect in obj.get("effects") or []:
        effect_file = effect.get("file")
        if effect_file and effect_file != "effects/opacity/effect.json":
            ignored.append(effect_file)
    return ignored


def compose_scene(
    input_dir: Path, output_path: Path, *, draw_hidden: bool = False
) -> dict[str, Any]:
    root = input_dir.resolve()
    scene_path = root / "scene.json"
    scene = read_json(scene_path)
    projection = scene.get("general", {}).get("orthogonalprojection", {})
    width = int(projection["width"])
    height = int(projection["height"])

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    drawn: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for index, obj in enumerate(scene.get("objects", [])):
        name = obj.get("name", f"object-{index}")
        if not draw_hidden and not is_visible(obj.get("visible", True)):
            skipped.append({"index": index, "name": name, "reason": "hidden"})
            continue

        png_path, _model = material_png_for_model(root, obj.get("image", ""))
        if png_path is None:
            skipped.append(
                {"index": index, "name": name, "reason": "no static material png"}
            )
            continue

        size_x, size_y = parse_vec(obj.get("size"), 2)
        scale_x, scale_y, _ = parse_vec(obj.get("scale", "1 1 1"), 3, "1 1 1")
        target_size = (
            max(1, round(size_x * scale_x)),
            max(1, round(size_y * scale_y)),
        )

        layer = resize_layer(Image.open(png_path), target_size)
        layer = apply_object_opacity_effects(root, layer, obj)
        layer = apply_layer_alpha(layer, alpha_float(obj.get("alpha", 1.0)))
        x, y = layer_position(obj, height, target_size)
        canvas.alpha_composite(layer, (x, y))

        drawn.append(
            {
                "index": index,
                "name": name,
                "png": str(png_path.relative_to(root)),
                "size": target_size,
                "position": (x, y),
                "ignored_effects": ignored_effect_names(obj),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return {
        "input": str(root),
        "output": str(output_path),
        "canvas_size": (width, height),
        "drawn": drawn,
        "skipped": skipped,
    }


def default_output_path(input_dir: Path) -> Path:
    return input_dir / "composite_static.png"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Statically compose image layers from a RePKG Wallpaper Engine scene."
    )
    parser.add_argument("input_dir", type=Path, help="Folder containing scene.json")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output PNG path. Defaults to INPUT_DIR/composite_static.png",
    )
    parser.add_argument(
        "--draw-hidden",
        action="store_true",
        help="Also draw objects whose visible value is false.",
    )
    return parser


def print_summary(summary: dict[str, Any]) -> None:
    print(f"Saved: {summary['output']}")
    print(f"Canvas: {summary['canvas_size'][0]}x{summary['canvas_size'][1]}")
    print(f"Drawn layers: {len(summary['drawn'])}")
    for item in summary["drawn"]:
        ignored = ""
        if item["ignored_effects"]:
            ignored = f" ignored_effects={','.join(item['ignored_effects'])}"
        print(
            f"  #{item['index']} {item['name']} {item['png']} "
            f"size={item['size']} pos={item['position']}{ignored}"
        )
    print(f"Skipped layers: {len(summary['skipped'])}")
    for item in summary["skipped"]:
        print(f"  #{item['index']} {item['name']} ({item['reason']})")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)
    input_dir = args.input_dir
    output = args.output or default_output_path(input_dir)

    try:
        summary = compose_scene(input_dir, output, draw_hidden=args.draw_hidden)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
