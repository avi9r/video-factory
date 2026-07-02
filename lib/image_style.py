"""Visual style presets and image layout normalization."""

from __future__ import annotations

import copy
from typing import Any

VALID_VISUAL_STYLES = ("realistic", "cartoon")
VALID_IMAGE_LAYOUTS = ("one_image", "per_scene", "multiple")
IMAGE_LAYOUT_ALIASES = {"single": "per_scene"}


def normalize_image_layout(layout: str | None) -> str:
    """Map legacy values and return a canonical layout name."""
    if not layout:
        return "per_scene"
    return IMAGE_LAYOUT_ALIASES.get(layout, layout)


def layout_uses_broll(layout: str | None) -> bool:
    return normalize_image_layout(layout) == "multiple"


def layout_label(layout: str | None) -> str:
    normalized = normalize_image_layout(layout)
    return {
        "one_image": "One image (entire video)",
        "per_scene": "One image per scene",
        "multiple": "Per scene + B-roll",
    }.get(normalized, normalized)


def resolve_image_config(channel_config: dict, visual_style: str | None = None) -> dict:
    """Return channel config with image style preset merged into prompt_prefix and style_lock."""
    config = copy.deepcopy(channel_config)
    image = config.setdefault("image", {})
    style = visual_style or image.get("visual_style", "realistic")
    if style not in VALID_VISUAL_STYLES:
        style = "realistic"

    presets: dict[str, Any] = image.get("style_presets", {})
    preset = presets.get(style, {})
    if preset.get("prompt_prefix"):
        image["prompt_prefix"] = preset["prompt_prefix"]
    if preset.get("thumbnail_background_style"):
        config.setdefault("thumbnail", {})["background_style"] = preset["thumbnail_background_style"]

    overrides = preset.get("style_lock_overrides", {})
    if overrides:
        config.setdefault("style_lock", {}).update(overrides)

    image["visual_style"] = style
    return config
