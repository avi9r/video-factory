"""Image generation via Hugging Face FLUX and optional Pexels B-roll."""

import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests

from lib.config import HF_API_KEY, PEXELS_API_KEY
from lib.image_style import normalize_image_layout, resolve_image_config

HF_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
LEGACY_HF_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
PLACEHOLDER_BG = "#1a1a1a"
HERO_IMAGE_NAME = "video_hero.png"


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] image: {msg}")


def _build_prompt(prompt: str, channel_config: dict) -> str:
    prefix = channel_config.get("image", {}).get("prompt_prefix", "")
    style = channel_config.get("style_lock", {})
    forbidden = style.get("forbidden", "")
    always = style.get("always_include", "")
    return f"{prefix.strip()} {prompt}. {always}. Never include: {forbidden}."


def _call_hf_image_api(prompt: str, timeout: int = 120) -> bytes:
    if not HF_API_KEY or HF_API_KEY == "your_hf_token_here":
        raise ValueError("HF_API_KEY not configured in config.env")
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    body = {"inputs": prompt, "parameters": {"guidance_scale": 0.0, "num_inference_steps": 4}}

    for url in (HF_URL, LEGACY_HF_URL):
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
        if response.status_code == 503:
            _log("Model loading, waiting 20s...")
            time.sleep(20)
            response = requests.post(url, headers=headers, json=body, timeout=timeout)
        if response.status_code in (410, 404):
            _log(
                f"HF endpoint deprecated or unavailable ({response.status_code}): "
                "use router.huggingface.co with Inference Providers token"
            )
            continue
        response.raise_for_status()
        return response.content

    raise RuntimeError(
        "HF image API unavailable. Set HF_API_KEY with Inference Providers permission "
        "and use https://router.huggingface.co/hf-inference/models/..."
    )


def _write_image_bytes(data: bytes, output_path: Path) -> Path:
    """Decode image bytes and save as PNG for consistent pipeline paths."""
    from PIL import Image

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(BytesIO(data)).convert("RGB")
    if output_path.suffix.lower() != ".png":
        output_path = output_path.with_suffix(".png")
    img.save(output_path, "PNG")
    return output_path


def _placeholder_image(channel_config: dict, output_path: Path) -> str:
    from PIL import Image

    w = channel_config.get("image", {}).get("width", 1920)
    h = channel_config.get("image", {}).get("height", 1080)
    img = Image.new("RGB", (w, h), PLACEHOLDER_BG)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return str(output_path)


def fetch_pexels_image(query: str, output_path: str, label: str = "image") -> bool:
    """Download a landscape photo from Pexels. Returns True on success."""
    if not PEXELS_API_KEY:
        return False
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        response = requests.get(
            PEXELS_SEARCH_URL,
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query[:100], "per_page": 1, "orientation": "landscape"},
            timeout=30,
        )
        response.raise_for_status()
        photos = response.json().get("photos", [])
        if not photos:
            return False
        src = photos[0].get("src", {}).get("large2x") or photos[0].get("src", {}).get("large")
        if not src:
            return False
        img_data = requests.get(src, timeout=60)
        img_data.raise_for_status()
        _write_image_bytes(img_data.content, out)
        _log(f"Pexels {label} -> {out.name}")
        return True
    except Exception as e:
        _log(f"Pexels fetch failed ({e})")
        return False


def generate_scene_image(
    prompt: str,
    channel_config: dict,
    output_path: str,
    seed: int | None = None,
) -> tuple[str, str]:
    """Return (path, source) where source is flux, pexels, or placeholder."""
    full_prompt = _build_prompt(prompt, channel_config)
    _log(f"FLUX image -> {output_path}")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = _call_hf_image_api(full_prompt)
        path = _write_image_bytes(data, out)
        _log(f"Main {path.name} -> flux")
        return str(path), "flux"
    except Exception as e:
        _log(f"HF API failed ({e}), trying Pexels fallback")
        if fetch_pexels_image(prompt, str(out), label="main"):
            _log(f"Main {out.name} -> pexels (flux failed)")
            return str(out), "pexels"
        _log("Pexels fallback failed, creating placeholder image")
        _placeholder_image(channel_config, out)
        _log(f"Main {out.name} -> placeholder (flux + pexels failed)")
        return str(out), "placeholder"


def generate_broll_image(
    prompt: str,
    channel_config: dict,
    output_path: str,
) -> tuple[str, str]:
    """Return (path, source) where source is pexels, flux, or placeholder."""
    if fetch_pexels_image(prompt, output_path, label="broll"):
        return output_path, "pexels"
    return generate_scene_image(prompt, channel_config, output_path)


def _hero_visual_prompt(scenes: list[dict]) -> str:
    """Build one key visual that represents the whole video."""
    if not scenes:
        return "cinematic thematic key visual, symbolic and evocative, no text in image"
    hook = scenes[0]
    hook_visual = hook.get("visual_prompt", hook.get("text", "")).strip()
    mid = scenes[len(scenes) // 2] if len(scenes) > 2 else {}
    mid_visual = mid.get("visual_prompt", "").strip()
    parts = [p for p in (hook_visual, mid_visual) if p]
    if not parts:
        return "cinematic thematic key visual, symbolic and evocative, no text in image"
    if len(parts) == 1:
        return f"Single hero image for the entire video — {parts[0]}"
    return (
        "Single hero image for the entire video combining the core themes: "
        f"{parts[0]}. Also echo: {parts[1]}"
    )


def generate_scene_images_batch(
    scenes: list[dict],
    channel_config: dict,
    output_dir: str,
    image_layout: str = "per_scene",
    visual_style: str | None = None,
) -> tuple[list[str], dict]:
    from lib.assets import copy_as_broll, propagate_hero_to_scenes

    resolved_channel = resolve_image_config(channel_config, visual_style)
    layout = normalize_image_layout(image_layout)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_paths: list[str] = []
    flux_count = 0
    pexels_count = 0
    placeholder_count = 0
    fallbacks: dict[str, dict[str, str]] = {}

    if layout == "one_image":
        hero_path = out_dir / HERO_IMAGE_NAME
        prompt = _hero_visual_prompt(scenes)
        _log(f"Generating one hero image for entire video ({len(scenes)} scenes)")
        _, hero_source = generate_scene_image(prompt, resolved_channel, str(hero_path))
        propagate_hero_to_scenes(hero_path, scenes, out_dir)
        if hero_source == "flux":
            flux_count = 1
        elif hero_source == "pexels":
            pexels_count = 1
        elif hero_source == "placeholder":
            placeholder_count = 1
        for scene in scenes:
            scene_id = scene.get("scene_id", "scene")
            fallbacks[scene_id] = {"main": hero_source, "broll": hero_source}
            all_paths.extend([
                str(out_dir / f"{scene_id}_main.png"),
                str(out_dir / f"{scene_id}_broll.png"),
            ])
        return all_paths, {
            "flux_count": flux_count,
            "pexels_count": pexels_count,
            "placeholder_count": placeholder_count,
            "fallbacks": fallbacks,
            "image_layout": layout,
            "visual_style": resolved_channel.get("image", {}).get("visual_style"),
            "hero_image": str(hero_path),
        }

    per_scene_only = layout == "per_scene"
    total = len(scenes)
    for i, scene in enumerate(scenes, 1):
        scene_id = scene.get("scene_id", f"scene_{i}")
        _log(f"Generating image {i}/{total}: {scene_id} ({layout})")
        main_path = out_dir / f"{scene_id}_main.png"
        broll_path = out_dir / f"{scene_id}_broll.png"
        visual = scene.get("visual_prompt", scene.get("text", "cinematic scene"))
        broll = scene.get("broll_prompt", visual)
        _, main_source = generate_scene_image(visual, resolved_channel, str(main_path))
        if per_scene_only:
            copy_as_broll(main_path, broll_path)
            broll_source = main_source
        else:
            _, broll_source = generate_broll_image(broll, resolved_channel, str(broll_path))
        fallbacks[scene_id] = {"main": main_source, "broll": broll_source}
        for source in (main_source,) if per_scene_only else (main_source, broll_source):
            if source == "flux":
                flux_count += 1
            elif source == "pexels":
                pexels_count += 1
            elif source == "placeholder":
                placeholder_count += 1
        all_paths.extend([str(main_path), str(broll_path)])
    return all_paths, {
        "flux_count": flux_count,
        "pexels_count": pexels_count,
        "placeholder_count": placeholder_count,
        "fallbacks": fallbacks,
        "image_layout": layout,
        "visual_style": resolved_channel.get("image", {}).get("visual_style"),
    }
