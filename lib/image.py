"""Image generation via FLUX (HF Inference Providers / Fal) and Pexels fallback."""

import hashlib
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests

from lib.config import HF_API_KEY, PEXELS_API_KEY, has_fal_key
from lib.image_style import normalize_image_layout, resolve_image_config

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
PLACEHOLDER_BG = "#1a1a1a"
HERO_IMAGE_NAME = "video_hero.png"
FLUX_MODEL = "black-forest-labs/FLUX.1-schnell"
FAL_FLUX_MODEL = "fal-ai/flux/schnell"
HF_FLUX_PROVIDERS = ("fal-ai", "replicate", "together", "nscale")

_STYLE_NOISE = (
    "ultra realistic",
    "cinematic",
    "1080p",
    "horizontal",
    "premium",
    "documentary",
    "aesthetic",
    "dramatic lighting",
    "rule of thirds",
    "no text",
    "no logos",
    "no readable",
    "no legible",
    "8k",
    "editorial",
    "premium quality",
    "minimal composition",
    "shallow depth of field",
    "warm amber",
    "navy",
    "black and warm",
)


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] image: {msg}")


def _build_prompt(prompt: str, channel_config: dict) -> str:
    prefix = channel_config.get("image", {}).get("prompt_prefix", "")
    style = channel_config.get("style_lock", {})
    forbidden = style.get("forbidden", "")
    always = style.get("always_include", "")
    lighting = style.get("lighting", "")
    mood = style.get("mood", "")
    composition = style.get("composition", "")
    parts = [prefix.strip(), prompt.strip()]
    for extra in (lighting, mood, composition, always):
        if extra:
            parts.append(str(extra).strip())
    body = ". ".join(p for p in parts if p)
    if forbidden:
        return f"{body}. Never include: {forbidden}."
    return body


def _clause_is_style_noise(clause: str) -> bool:
    low = clause.lower().strip()
    if not low:
        return True
    if any(noise in low for noise in _STYLE_NOISE) and len(clause) < 48:
        return True
    if "no " in low and any(x in low for x in ("text", "logo", "readable", "legible", "signage", "writing")):
        return True
    return False


def _pexels_search_query(visual_prompt: str, script: dict | None = None) -> str:
    """Short stock-photo query from scene visual + video topic (not FLUX style prefix)."""
    visual = str(visual_prompt or "").strip()
    if not visual or visual.lower() in ("cinematic scene", "cinematic scene — no text"):
        visual = str((script or {}).get("hero_visual_prompt", "") or (script or {}).get("title", "")).strip()

    clauses = [c.strip() for c in visual.replace(" — ", ", ").split(",") if c.strip()]
    meaningful = [c for c in clauses if not _clause_is_style_noise(c)]
    if not meaningful and clauses:
        meaningful = [clauses[0]]
    query = ", ".join(meaningful[:3]) if meaningful else visual[:80]

    title = str((script or {}).get("title", "")).strip()
    if title:
        short_title = title.split("—")[0].split(" - ")[0].strip()[:50]
        if short_title and short_title.lower() not in query.lower():
            query = f"{short_title}, {query}"

    return query[:100]


def _pexels_query(prompt: str, channel_config: dict, script: dict | None = None) -> str:
    """Backward-compatible alias — always prefer scene/topic terms over style boilerplate."""
    return _pexels_search_query(prompt, script)


def _call_flux_via_inference_client(prompt: str) -> bytes:
    if not HF_API_KEY or HF_API_KEY == "your_hf_token_here":
        raise ValueError("HF_API_KEY not configured in config.env")

    from huggingface_hub import InferenceClient

    last_err: Exception | None = None
    for provider in HF_FLUX_PROVIDERS:
        try:
            client = InferenceClient(provider=provider, token=HF_API_KEY)
            image = client.text_to_image(prompt, model=FLUX_MODEL)
            buf = BytesIO()
            image.save(buf, format="PNG")
            _log(f"FLUX via HF Inference Provider ({provider})")
            return buf.getvalue()
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "402" in msg or "payment" in msg or "credit" in msg:
                _log(f"HF provider {provider}: credits exhausted or billing required")
            else:
                _log(f"HF provider {provider} failed: {e}")
    raise RuntimeError(last_err or "HF Inference Providers unavailable for FLUX")


def _call_flux_via_fal(prompt: str, seed: int | None = None) -> bytes:
    if not has_fal_key():
        raise ValueError("FAL_API_KEY not configured in config.env")

    import fal_client

    args: dict = {
        "prompt": prompt,
        "num_inference_steps": 4,
        "image_size": "landscape_16_9",
        "enable_safety_checker": True,
    }
    if seed is not None:
        args["seed"] = seed
    result = fal_client.run(FAL_FLUX_MODEL, arguments=args)
    images = result.get("images") if isinstance(result, dict) else None
    url = None
    if images:
        url = images[0].get("url")
    elif isinstance(result, dict):
        url = result.get("image", {}).get("url") or result.get("url")
    if not url:
        raise RuntimeError(f"Fal FLUX returned no image URL: {result!r}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    _log("FLUX via Fal.ai direct")
    return resp.content


def _call_flux_api(prompt: str, seed: int | None = None) -> bytes:
    """Try HF Inference Providers, then Fal direct."""
    errors: list[str] = []
    try:
        return _call_flux_via_inference_client(prompt)
    except Exception as e:
        errors.append(f"HF: {e}")
    try:
        return _call_flux_via_fal(prompt, seed=seed)
    except Exception as e:
        errors.append(f"Fal: {e}")
    raise RuntimeError("; ".join(errors))


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


def fetch_pexels_image(
    query: str,
    output_path: str,
    label: str = "image",
    *,
    result_index: int = 0,
) -> bool:
    """Download a landscape photo from Pexels. Returns True on success."""
    if not PEXELS_API_KEY:
        return False
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        per_page = 15
        page = (result_index // per_page) + 1
        pick = result_index % per_page
        response = requests.get(
            PEXELS_SEARCH_URL,
            headers={"Authorization": PEXELS_API_KEY},
            params={
                "query": query[:100],
                "per_page": per_page,
                "page": page,
                "orientation": "landscape",
            },
            timeout=30,
        )
        response.raise_for_status()
        photos = response.json().get("photos", [])
        if not photos:
            return False
        photo = photos[min(pick, len(photos) - 1)]
        src = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
        if not src:
            return False
        img_data = requests.get(src, timeout=60)
        img_data.raise_for_status()
        _write_image_bytes(img_data.content, out)
        _log(f"Pexels {label} (result {result_index}, id {photo.get('id')}) -> {out.name}")
        return True
    except Exception as e:
        _log(f"Pexels fetch failed ({e})")
        return False


def _flux_seed(scene_index: int, scene_id: str) -> int:
    digest = hashlib.md5(scene_id.encode()).hexdigest()
    return (scene_index * 9973 + int(digest[:8], 16)) % 2_147_483_647


def generate_scene_image(
    prompt: str,
    channel_config: dict,
    output_path: str,
    seed: int | None = None,
    *,
    script: dict | None = None,
    scene_index: int = 0,
    scene_id: str = "",
) -> tuple[str, str]:
    """Return (path, source) where source is flux, pexels, or placeholder."""
    full_prompt = _build_prompt(prompt, channel_config)
    pexels_query = _pexels_search_query(prompt, script)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if seed is None and scene_id:
        seed = _flux_seed(scene_index, scene_id)

    _log(f"FLUX image -> {output_path}")
    try:
        data = _call_flux_api(full_prompt, seed=seed)
        path = _write_image_bytes(data, out)
        _log(f"Main {path.name} -> flux")
        return str(path), "flux"
    except Exception as e:
        _log(f"FLUX failed ({e}), trying Pexels fallback: {pexels_query[:70]!r}")
        if fetch_pexels_image(
            pexels_query,
            str(out),
            label="main",
            result_index=scene_index,
        ):
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
    *,
    script: dict | None = None,
    scene_index: int = 0,
) -> tuple[str, str]:
    """Return (path, source) where source is pexels, flux, or placeholder."""
    pexels_query = _pexels_search_query(prompt, script)
    if fetch_pexels_image(
        pexels_query,
        output_path,
        label="broll",
        result_index=scene_index + 7,
    ):
        return output_path, "pexels"
    return generate_scene_image(
        prompt,
        channel_config,
        output_path,
        script=script,
        scene_index=scene_index,
    )


def _hero_visual_prompt(scenes: list[dict], script: dict | None = None) -> str:
    """Build one key visual that represents the whole video."""
    if script and str(script.get("hero_visual_prompt", "")).strip():
        return str(script["hero_visual_prompt"]).strip()
    if not scenes:
        return "thematic key visual symbolic and evocative, no text in image"
    hook = scenes[0]
    hook_visual = hook.get("visual_prompt", hook.get("text", "")).strip()
    mid = scenes[len(scenes) // 2] if len(scenes) > 2 else {}
    mid_visual = mid.get("visual_prompt", "").strip()
    title = (script or {}).get("title", "").strip()
    topic_bits = [title] if title else []
    parts = [p for p in (hook_visual, mid_visual) if p and p.lower() not in ("cinematic scene", "cinematic scene — no text")]
    if not parts:
        return "thematic key visual symbolic and evocative, no text in image"
    topic_prefix = f"Video about {topic_bits[0]}: " if topic_bits else "Single hero image for the entire video — "
    if len(parts) == 1:
        return f"{topic_prefix}{parts[0]}"
    return (
        f"{topic_prefix}{parts[0]}. Also echo: {parts[1]}"
    )


def generate_scene_images_batch(
    scenes: list[dict],
    channel_config: dict,
    output_dir: str,
    image_layout: str = "per_scene",
    visual_style: str | None = None,
    script: dict | None = None,
) -> tuple[list[str], dict]:
    from lib.assets import propagate_hero_to_scenes

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
        prompt = _hero_visual_prompt(scenes, script)
        _log(f"Generating one hero image for entire video ({len(scenes)} scenes)")
        _, hero_source = generate_scene_image(
            prompt,
            resolved_channel,
            str(hero_path),
            script=script,
            scene_index=0,
            scene_id="hero",
        )
        propagate_hero_to_scenes(hero_path, scenes, out_dir, include_broll=False)
        if hero_source == "flux":
            flux_count = 1
        elif hero_source == "pexels":
            pexels_count = 1
        elif hero_source == "placeholder":
            placeholder_count = 1
        for scene in scenes:
            scene_id = scene.get("scene_id", "scene")
            fallbacks[scene_id] = {"main": hero_source}
            all_paths.append(str(out_dir / f"{scene_id}_main.png"))
        all_paths.insert(0, str(hero_path))
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
        scene_index = i - 1
        _log(f"Generating image {i}/{total}: {scene_id} ({layout})")
        main_path = out_dir / f"{scene_id}_main.png"
        visual = scene.get("visual_prompt", scene.get("text", "cinematic scene"))
        broll = scene.get("broll_prompt", visual)
        _, main_source = generate_scene_image(
            visual,
            resolved_channel,
            str(main_path),
            script=script,
            scene_index=scene_index,
            scene_id=scene_id,
        )
        if per_scene_only:
            broll_source = main_source
            fallbacks[scene_id] = {"main": main_source}
            all_paths.append(str(main_path))
        else:
            broll_path = out_dir / f"{scene_id}_broll.png"
            _, broll_source = generate_broll_image(
                broll,
                resolved_channel,
                str(broll_path),
                script=script,
                scene_index=scene_index,
            )
            fallbacks[scene_id] = {"main": main_source, "broll": broll_source}
            all_paths.extend([str(main_path), str(broll_path)])
        if main_source == "flux":
            flux_count += 1
        elif main_source == "pexels":
            pexels_count += 1
        elif main_source == "placeholder":
            placeholder_count += 1
        if not per_scene_only:
            if broll_source == "flux":
                flux_count += 1
            elif broll_source == "pexels":
                pexels_count += 1
            elif broll_source == "placeholder":
                placeholder_count += 1
    return all_paths, {
        "flux_count": flux_count,
        "pexels_count": pexels_count,
        "placeholder_count": placeholder_count,
        "fallbacks": fallbacks,
        "image_layout": layout,
        "visual_style": resolved_channel.get("image", {}).get("visual_style"),
    }
