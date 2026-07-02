"""Asset upload helpers — resize and save scene images."""

import shutil
from io import BytesIO
from pathlib import Path

from PIL import Image


def save_uploaded_image(
    file_bytes: bytes,
    output_path: Path,
    *,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Decode, resize to 16:9, save as PNG."""
    output_path = Path(output_path)
    if output_path.suffix.lower() != ".png":
        output_path = output_path.with_suffix(".png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(BytesIO(file_bytes)).convert("RGB")
    img.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), (26, 26, 26))
    x = (width - img.width) // 2
    y = (height - img.height) // 2
    canvas.paste(img, (x, y))
    canvas.save(output_path, "PNG")
    return str(output_path)


def copy_as_broll(main_path: Path, broll_path: Path) -> str:
    """Copy image to another path (used for b-roll duplicate or hero propagation)."""
    broll_path = Path(broll_path)
    broll_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(main_path, broll_path)
    return str(broll_path)


def propagate_hero_to_scenes(hero_path: Path, scenes: list[dict], out_dir: Path) -> None:
    """Copy one hero image to every scene main/broll slot."""
    for scene in scenes:
        scene_id = scene.get("scene_id", "scene")
        copy_as_broll(hero_path, out_dir / f"{scene_id}_main.png")
        copy_as_broll(hero_path, out_dir / f"{scene_id}_broll.png")
