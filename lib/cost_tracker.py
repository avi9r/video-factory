"""Estimated API cost tracking per job."""

import json
from pathlib import Path

GROQ_OUTPUT_PER_CHAR_USD = 0.79 / 1_000_000
GROQ_INPUT_PER_CHAR_USD = 0.59 / 1_000_000
FLUX_PER_IMAGE_USD = 0.003


def _load(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"total_usd": 0.0, "breakdown": {}, "currency": "USD"}


def _save(path: Path, data: dict) -> dict:
    data["total_usd"] = round(
        sum(v for k, v in data["breakdown"].items() if k.endswith("_usd")),
        4,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def record_script_cost(job_dir: Path, topic: str, script: dict) -> dict:
    """Estimate Groq cost from script size."""
    text = json.dumps(script) + topic
    input_chars = len(topic) + 2000
    output_chars = len(text)
    cost = input_chars * GROQ_INPUT_PER_CHAR_USD + output_chars * GROQ_OUTPUT_PER_CHAR_USD
    path = job_dir / "cost_estimate.json"
    data = _load(path)
    data["breakdown"]["groq_script_usd"] = round(cost, 4)
    return _save(path, data)


def record_image_cost(job_dir: Path, flux_count: int, pexels_count: int = 0) -> dict:
    """Estimate image generation cost."""
    path = job_dir / "cost_estimate.json"
    data = _load(path)
    data["breakdown"]["flux_images_usd"] = round(flux_count * FLUX_PER_IMAGE_USD, 4)
    data["breakdown"]["pexels_images_usd"] = 0.0
    data["image_count_flux"] = flux_count
    data["image_count_pexels"] = pexels_count
    return _save(path, data)


def get_cost_estimate(job_dir: Path) -> dict:
    return _load(job_dir / "cost_estimate.json")
