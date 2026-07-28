"""Optional video clip generation via Fal.ai."""

from datetime import datetime
from pathlib import Path

import requests

from lib.config import has_fal_key


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] video: {msg}")


def _build_prompt(prompt: str, channel_config: dict) -> str:
    from lib.image import _build_prompt as build_image_prompt
    return build_image_prompt(prompt, channel_config)


def generate_scene_clip(
    prompt: str,
    channel_config: dict,
    output_path: str,
    duration_seconds: int = 5,
    seed: int | None = None,
) -> str | None:
    if not has_fal_key():
        _log("FAL_API_KEY not set, skipping video clip generation")
        return None

    import fal_client

    full_prompt = _build_prompt(prompt, channel_config)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Generating clip -> {output_path}")

    try:
        result = fal_client.run(
            "fal-ai/seedance-v1-lite",
            arguments={
                "prompt": full_prompt,
                "duration": duration_seconds,
                "resolution": "1080p",
                "aspect_ratio": "16:9",
            },
        )
        video_url = result.get("video", {}).get("url") if isinstance(result, dict) else None
        if not video_url and isinstance(result, dict):
            video_url = result.get("url")
        if video_url:
            resp = requests.get(video_url, timeout=120)
            resp.raise_for_status()
            out.write_bytes(resp.content)
            return str(out)
    except Exception as e:
        _log(f"Fal clip generation failed: {e}")
    return None


def generate_clips_batch(
    scenes: list[dict],
    channel_config: dict,
    output_dir: str,
) -> dict[str, str]:
    if not has_fal_key():
        return {}
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for i, scene in enumerate(scenes, 1):
        scene_id = scene.get("scene_id", f"scene_{i}")
        prompt = scene.get("visual_prompt", "cinematic scene")
        out_path = out_dir / f"{scene_id}_clip.mp4"
        result = generate_scene_clip(prompt, channel_config, str(out_path))
        if result:
            paths[scene_id] = result
    return paths
