"""Load and validate channel YAML configurations."""

from copy import deepcopy
from pathlib import Path

import yaml

from lib.config import CHANNELS_BASE, SHORTS_CHANNELS_BASE

REQUIRED_FIELDS = [
    "name",
    "niche_id",
    "color_scheme",
    "voice",
    "music",
    "style_lock",
    "script",
    "thumbnail",
    "video",
    "image",
]

SHORT_REQUIRED_FIELDS = [
    "name",
    "niche_id",
    "format",
    "color_scheme",
    "voice",
    "music",
    "style_lock",
    "script",
    "video",
    "image",
]

CHANNEL_DEFAULTS: dict = {
    "captions": {
        "enabled": True,
        "font_name": "Arial",
        "font_size": 44,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline": 3,
        "margin_v": 72,
        "max_chars_per_line": 42,
        "shadow": 1,
    },
    "sfx": {
        "enabled": True,
        "max_cues_per_scene": 2,
        "default_volume": 0.06,
        "ambient_volume_scale": 0.55,
        "one_shot_volume_scale": 0.80,
        "max_bus_volume": 0.10,
        "ducking": {
            "enabled": True,
            "ratio": 6,
            "attack_ms": 60,
            "release_ms": 450,
        },
    },
    "script": {
        "auto_humanize": True,
        "script_polish": True,
    },
}

SHORT_CHANNEL_DEFAULTS: dict = {
    "format": "short",
    "aspect_ratio": "9:16",
    "resolution": "1080x1920",
    "captions": {
        "enabled": True,
        "font_name": "Arial",
        "font_size": 64,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline": 4,
        "margin_v": 220,
        "max_chars_per_line": 28,
        "shadow": 2,
        "position": "lower_third",
        "play_res_x": 1080,
        "play_res_y": 1920,
    },
    "sfx": {"enabled": False},
    "script": {
        "auto_humanize": True,
        "script_polish": True,
        "cta_text": "Follow for more",
        "hook_patterns": ["date_dollar", "paradox", "single_fact"],
    },
    "image": {"reuse_default": True},
    "video": {
        "fps": 30,
        "format": "mp4",
        "resolution": "1080x1920",
    },
    "hashtags": ["#Shorts"],
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def apply_channel_defaults(config: dict) -> dict:
    """Merge optional sections so new channels only need core YAML fields."""
    return _deep_merge(CHANNEL_DEFAULTS, config)


def apply_short_channel_defaults(config: dict) -> dict:
    return _deep_merge(SHORT_CHANNEL_DEFAULTS, config)


def load_channel(niche_id: str) -> dict:
    path = CHANNELS_BASE / f"{niche_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Channel not found: {niche_id} (expected {path})")
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    validate_channel_config(config)
    return apply_channel_defaults(config)


def load_short_channel(niche_id: str) -> dict:
    path = SHORTS_CHANNELS_BASE / f"{niche_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Short channel not found: {niche_id} (expected {path})")
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    validate_short_channel_config(config)
    if config.get("niche_id") != niche_id:
        raise ValueError(f"niche_id mismatch: file stem={niche_id}, yaml={config.get('niche_id')}")
    return apply_short_channel_defaults(config)


def list_channels() -> list[dict]:
    channels = []
    if not CHANNELS_BASE.exists():
        return channels
    for path in sorted(CHANNELS_BASE.glob("*.yaml")):
        if path.stem.startswith("_"):
            continue
        niche_id = path.stem
        try:
            config = load_channel(niche_id)
            channels.append(
                {
                    "niche_id": niche_id,
                    "name": config.get("name", niche_id),
                    "color_scheme": config.get("color_scheme", {}),
                }
            )
        except (ValueError, yaml.YAMLError):
            continue
    return channels


def list_short_channels() -> list[dict]:
    channels = []
    if not SHORTS_CHANNELS_BASE.exists():
        return channels
    for path in sorted(SHORTS_CHANNELS_BASE.glob("*.yaml")):
        if path.stem.startswith("_"):
            continue
        niche_id = path.stem
        try:
            config = load_short_channel(niche_id)
            research = config.get("research") or {}
            channels.append(
                {
                    "niche_id": niche_id,
                    "name": config.get("name", niche_id),
                    "color_scheme": config.get("color_scheme", {}),
                    "format": "short",
                    "durations": [30, 60, 90, 120],
                    "reuse_default": bool(config.get("image", {}).get("reuse_default", True)),
                    "voice": config.get("voice", {}),
                    "channel_handle": config.get("channel_handle", ""),
                    "tagline": config.get("channel_tagline", ""),
                    "research_type": research.get("type"),
                    "image_optional": bool(
                        research.get("image_optional") or research.get("auto_chart")
                    ),
                    "prompt_placeholder": (
                        "e.g. NVIDIA or Apple"
                        if research.get("type") == "stock_chart"
                        else "e.g. Kodak buried the first digital camera"
                    ),
                }
            )
        except (ValueError, yaml.YAMLError, FileNotFoundError):
            continue
    return channels


def validate_channel_config(config: dict) -> bool:
    if not config:
        raise ValueError("Channel config is empty")
    missing = [f for f in REQUIRED_FIELDS if f not in config]
    if missing:
        raise ValueError(f"Channel config missing required fields: {', '.join(missing)}")
    return True


def validate_short_channel_config(config: dict) -> bool:
    if not config:
        raise ValueError("Short channel config is empty")
    missing = [f for f in SHORT_REQUIRED_FIELDS if f not in config]
    if missing:
        raise ValueError(f"Short channel missing required fields: {', '.join(missing)}")
    if str(config.get("format", "")).lower() != "short":
        raise ValueError("Short channel must set format: short")
    return True
