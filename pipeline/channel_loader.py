"""Load and validate channel YAML configurations."""

from pathlib import Path

import yaml

from lib.config import CHANNELS_BASE

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


def load_channel(niche_id: str) -> dict:
    path = CHANNELS_BASE / f"{niche_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Channel not found: {niche_id} (expected {path})")
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    validate_channel_config(config)
    return config


def list_channels() -> list[dict]:
    channels = []
    if not CHANNELS_BASE.exists():
        return channels
    for path in sorted(CHANNELS_BASE.glob("*.yaml")):
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


def validate_channel_config(config: dict) -> bool:
    if not config:
        raise ValueError("Channel config is empty")
    missing = [f for f in REQUIRED_FIELDS if f not in config]
    if missing:
        raise ValueError(f"Channel config missing required fields: {', '.join(missing)}")
    return True
