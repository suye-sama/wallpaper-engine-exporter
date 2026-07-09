# Wallpaper Engine Static Composer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable Python CLI that statically composes RePKG-extracted Wallpaper Engine scene folders into a PNG preview.

**Architecture:** One focused script contains parsing, compositing, and CLI code. One focused pytest file locks the opacity-mask alpha behavior that caused the ripple layer bug.

**Tech Stack:** Python 3, Pillow, pytest.

## Global Constraints

- Place script in `D:\code_Date\codex_projects\explore\compose_we_static.py`.
- Do not modify the source RePKG folder except when the user chooses an output path inside it.
- Support static image layers only; print skipped dynamic/non-image layers.
- Apply `effects/opacity/effect.json` masks by multiplying layer alpha by the mask red/luminance channel.

---

### Task 1: Opacity Mask Unit Test

**Files:**
- Create: `D:\code_Date\codex_projects\explore\tests\test_compose_we_static.py`

**Interfaces:**
- Consumes: `apply_opacity_mask(image: Image.Image, mask: Image.Image, alpha: float = 1.0) -> Image.Image`
- Produces: a regression test proving a 50% mask halves alpha.

- [ ] Write test importing `apply_opacity_mask`.
- [ ] Run `python -m pytest tests/test_compose_we_static.py -q` and verify it fails because `compose_we_static` does not exist.

### Task 2: CLI Script

**Files:**
- Create: `D:\code_Date\codex_projects\explore\compose_we_static.py`

**Interfaces:**
- Produces: `compose_scene(input_dir: Path, output_path: Path, *, draw_hidden: bool = False) -> dict`
- Produces: CLI `python compose_we_static.py INPUT_DIR -o OUTPUT.png`

- [ ] Implement scene parsing, static layer lookup, WE coordinate conversion, alpha handling, opacity mask handling, and CLI summary printing.
- [ ] Run the unit test and verify it passes.

### Task 3: Real Fixture Verification

**Files:**
- Output only: user-selected PNG under `D:\base_tools\RePKG\待合成\output（星浴）`.

**Interfaces:**
- Consumes: CLI from Task 2.
- Produces: a 3840x2160 composed PNG and printed layer summary.

- [ ] Run script against `D:\base_tools\RePKG\待合成\output（星浴）`.
- [ ] Verify output image exists and has size `3840x2160`.
