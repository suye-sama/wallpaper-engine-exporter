from PIL import Image

from wallpaper_exporter.wallpaper_engine.compose_we_static import (
    apply_opacity_mask,
    material_png_for_model,
)


def test_apply_opacity_mask_multiplies_alpha_by_mask_luminance():
    image = Image.new("RGBA", (1, 1), (10, 20, 30, 200))
    mask = Image.new("L", (1, 1), 128)

    result = apply_opacity_mask(image, mask)

    assert result.getpixel((0, 0)) == (10, 20, 30, 100)


def test_material_lookup_finds_jpg_material_image(tmp_path):
    models = tmp_path / "models"
    materials = tmp_path / "materials"
    models.mkdir()
    materials.mkdir()
    (models / "bg.json").write_text(
        '{"autosize": true, "material": "materials/bg.json"}',
        encoding="utf-8",
    )
    Image.new("RGB", (1, 1), (1, 2, 3)).save(materials / "bg.jpg")

    image_path, model = material_png_for_model(tmp_path, "models/bg.json")

    assert image_path == materials / "bg.jpg"
    assert model == {"autosize": True, "material": "materials/bg.json"}
