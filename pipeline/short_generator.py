"""Shorts / Reels job orchestration."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from lib.audio import generate_all_voiceovers, get_audio_duration
from lib.config import MUSIC_BASE, OUTPUT_BASE, SHORT_DURATIONS
from lib.image import generate_scene_image
from lib.short_script import (
    flatten_short_scenes,
    generate_short_script,
    validate_short_script,
)
from lib.short_video import (
    assemble_short_video,
    mux_scene,
    prepare_vertical_image,
    render_short_visual_clips,
)
from pipeline.channel_loader import load_short_channel
from pipeline.generator import generate_job_id, save_json, save_text
from pipeline.status_tracker import (
    create_short_job,
    find_job_dir,
    short_job_dir,
    update_job,
)


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] short_gen: {msg}")


def _short_music_path(niche_id: str, channel: dict) -> str | None:
    bed = channel.get("music", {}).get("bed", "bed")
    for base in (MUSIC_BASE / "shorts" / niche_id, MUSIC_BASE / niche_id):
        for ext in (".mp3", ".wav"):
            path = base / f"{bed}{ext}"
            if path.exists():
                return str(path)
    return None


def _resolve_voice_speed(
    channel: dict,
    voice: str | None,
    speed: float | None,
) -> tuple[str | None, float]:
    voice_cfg = channel.get("voice") or {}
    resolved_voice = voice or voice_cfg.get("default")
    if speed is None:
        resolved_speed = float(voice_cfg.get("speed", 0.78))
    else:
        resolved_speed = float(speed)
    return resolved_voice, resolved_speed


def prepare_short_job(
    *,
    prompt: str,
    niche_id: str,
    duration_seconds: int,
    voice: str | None,
    speed: float | None,
    reuse_image: bool,
    auto_approve: bool,
    hook_style: str | None,
    quiet_music: bool,
    image_bytes: bytes | None,
    image_filename: str | None,
) -> str:
    if duration_seconds not in SHORT_DURATIONS:
        raise ValueError(f"duration_seconds must be one of {SHORT_DURATIONS}")
    channel = load_short_channel(niche_id)
    research_cfg = channel.get("research") or {}
    image_optional = bool(research_cfg.get("image_optional") or research_cfg.get("auto_chart"))

    if not image_bytes and not image_optional:
        raise ValueError("image is required for this short channel")

    voice, speed = _resolve_voice_speed(channel, voice, speed)

    job_id = generate_job_id()
    create_short_job(job_id, niche_id, prompt, audio_mode="ai")
    job_dir = short_job_dir(niche_id, job_id)
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    source_path = None
    vertical = images_dir / "source_vertical.png"

    if image_bytes:
        ext = Path(image_filename or "upload.jpg").suffix.lower() or ".jpg"
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"
        source_path = job_dir / f"source_image{ext}"
        source_path.write_bytes(image_bytes)
        prepare_vertical_image(str(source_path), str(vertical))
    elif research_cfg.get("auto_chart"):
        # Placeholder until research step writes the real chart
        from PIL import Image

        Image.new("RGB", (1080, 1920), (7, 11, 20)).save(vertical)
    else:
        raise ValueError("image is required")

    update_job(
        job_id,
        "script",
        "running",
        {
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "voice": voice,
            "speed": speed,
            "reuse_image": reuse_image if image_bytes else True,
            "auto_approve": auto_approve,
            "hook_style": hook_style,
            "quiet_music": quiet_music,
            "source_image": str(source_path) if source_path else None,
            "vertical_image": str(vertical),
            "job_kind": "short",
            "research_type": research_cfg.get("type"),
            "auto_chart": bool(research_cfg.get("auto_chart")),
        },
        niche_id=niche_id,
    )
    return job_id


def _maybe_build_stock_research(
    job_id: str,
    niche_id: str,
    prompt: str,
    channel: dict,
    job_dir: Path,
) -> dict | None:
    research_cfg = channel.get("research") or {}
    if research_cfg.get("type") != "stock_chart":
        return None

    from lib.stock_data import (
        build_stock_research,
        render_year_chart,
        research_context_for_llm,
        save_research_pack,
    )

    years = int(research_cfg.get("years") or 10)
    _log(f"[{job_id}] fetching stock research for: {prompt}")
    research = build_stock_research(prompt, years=years)
    colors = channel.get("color_scheme") or {}
    paths = save_research_pack(research, job_dir)
    chart_path = paths["chart"]
    render_year_chart(
        research,
        chart_path,
        colors={
            "background": colors.get("background", "#070B14"),
            "primary": colors.get("primary", "#38BDF8"),
            "accent": colors.get("accent", "#FBBF24"),
            "text": colors.get("text", "#F8FAFC"),
        },
    )
    vertical = job_dir / "images" / "source_vertical.png"
    prepare_vertical_image(chart_path, str(vertical))
    save_text(job_dir / "research_context.txt", research_context_for_llm(research))
    # Merge into existing script step data (do not wipe prompt / voice / etc.)
    status = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    meta = dict((status.get("steps", {}).get("script", {}) or {}).get("data") or {})
    meta["research"] = {
        "ticker": research.get("ticker"),
        "company": research.get("company"),
        "chart": chart_path,
        "total_return_pct": research.get("total_return_pct"),
    }
    meta["vertical_image"] = str(vertical)
    update_job(job_id, "script", "running", meta, niche_id=niche_id)
    return research


def run_short_pipeline(job_id: str, niche_id: str) -> None:
    """Full short pipeline: script → visuals → audio → assembly."""
    job_dir = short_job_dir(niche_id, job_id)
    status_path = job_dir / "status.json"
    with open(status_path, encoding="utf-8") as f:
        status = json.load(f)
    meta = (status.get("steps", {}).get("script", {}) or {}).get("data", {})

    prompt = meta.get("prompt") or status.get("topic", "")
    duration_seconds = int(meta.get("duration_seconds", 60))
    reuse_image = bool(meta.get("reuse_image", True))
    auto_approve = bool(meta.get("auto_approve", True))
    hook_style = meta.get("hook_style")
    quiet_music = bool(meta.get("quiet_music", False))
    vertical_image = meta.get("vertical_image") or str(job_dir / "images" / "source_vertical.png")

    channel = load_short_channel(niche_id)
    voice, speed = _resolve_voice_speed(channel, meta.get("voice"), meta.get("speed"))
    resolution = channel.get("resolution") or channel.get("video", {}).get("resolution", "1080x1920")
    fps = int(channel.get("video", {}).get("fps", 30))

    try:
        research = _maybe_build_stock_research(job_id, niche_id, prompt, channel, job_dir)
        research_context = None
        if research:
            from lib.stock_data import research_context_for_llm

            research_context = research_context_for_llm(research)
            vertical_image = str(job_dir / "images" / "source_vertical.png")
            # Auto-chart channels always reuse the generated chart as primary visual
            if (channel.get("research") or {}).get("chart_as_primary_visual", True):
                reuse_image = True

        # —— Script ——
        _log(f"[{job_id}] generating short script")
        script = generate_short_script(
            prompt,
            channel,
            duration_seconds=duration_seconds,
            hook_style=hook_style,
            research_context=research_context,
        )
        if research:
            script["company"] = research.get("company")
            script["ticker"] = research.get("ticker")
            script["stock_research"] = {
                "ticker": research.get("ticker"),
                "total_return_pct": research.get("total_return_pct"),
                "best_year": research.get("best_year"),
                "worst_year": research.get("worst_year"),
            }
        ok, errors = validate_short_script(script, duration_seconds)
        if not ok:
            _log(f"[{job_id}] script validation warnings: {errors}")
        save_json(job_dir / "script.json", script)
        save_text(job_dir / "description.txt", script.get("description", ""))
        tags = script.get("tags") or []
        hashtags = script.get("hashtags") or channel.get("hashtags") or ["#Shorts"]
        save_text(job_dir / "tags.txt", "\n".join(tags))
        save_text(job_dir / "hashtags.txt", " ".join(hashtags))
        if script.get("title"):
            save_text(job_dir / "titles.txt", script["title"])

        if not auto_approve:
            update_job(
                job_id,
                "script",
                "pending_review",
                {
                    **meta,
                    "review_url": f"/ui/review.html?job_id={job_id}&kind=short",
                    "script_path": str(job_dir / "script.json"),
                },
                niche_id=niche_id,
            )
            _log(f"[{job_id}] awaiting short script review")
            return

        save_json(job_dir / "script_approved.json", script)
        update_job(job_id, "script", "complete", {"auto_approved": True}, niche_id=niche_id)
        continue_short_after_script(
            job_id,
            niche_id,
            script=script,
            vertical_image=vertical_image,
            reuse_image=reuse_image,
            voice=voice,
            speed=speed,
            quiet_music=quiet_music,
            duration_seconds=duration_seconds,
            resolution=resolution,
            fps=fps,
            channel=channel,
        )
    except Exception as e:
        _log(f"[{job_id}] ERROR: {e}")
        update_job(job_id, "script", "error", {"error": str(e)}, niche_id=niche_id)
        raise


def continue_short_after_script(
    job_id: str,
    niche_id: str,
    *,
    script: dict | None = None,
    vertical_image: str | None = None,
    reuse_image: bool = True,
    voice: str | None = None,
    speed: float | None = None,
    quiet_music: bool = False,
    duration_seconds: int = 60,
    resolution: str = "1080x1920",
    fps: int = 30,
    channel: dict | None = None,
) -> dict:
    job_dir = short_job_dir(niche_id, job_id)
    channel = channel or load_short_channel(niche_id)
    voice, speed = _resolve_voice_speed(channel, voice, speed)
    if script is None:
        approved = job_dir / "script_approved.json"
        script_path = approved if approved.exists() else job_dir / "script.json"
        script = json.loads(script_path.read_text(encoding="utf-8"))
    if vertical_image is None:
        vertical_image = str(job_dir / "images" / "source_vertical.png")

    scenes = flatten_short_scenes(script)
    if not scenes:
        raise ValueError("Short script has no scenes")

    # —— Visuals ——
    update_job(job_id, "visuals", "running", {}, niche_id=niche_id)
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[str] = []

    try:
        if reuse_image:
            for i, scene in enumerate(scenes):
                dest = images_dir / f"{scene['scene_id']}.png"
                if i == 0:
                    shutil.copy2(vertical_image, dest)
                else:
                    # Slight crop variants via re-prep with same source for Ken Burns variety
                    shutil.copy2(vertical_image, dest)
                image_paths.append(str(dest))
        else:
            for i, scene in enumerate(scenes):
                dest = images_dir / f"{scene['scene_id']}.png"
                prompt = scene.get("visual_prompt") or script.get("title") or "vertical cinematic frame"
                if i == 0:
                    shutil.copy2(vertical_image, dest)
                    image_paths.append(str(dest))
                else:
                    path, source = generate_scene_image(
                        prompt,
                        channel,
                        str(dest),
                        script=script,
                        scene_index=i,
                        scene_id=scene["scene_id"],
                    )
                    # Force vertical
                    vdest = images_dir / f"{scene['scene_id']}_v.png"
                    prepare_vertical_image(path, str(vdest), resolution=resolution)
                    image_paths.append(str(vdest))
                    _log(f"Scene image {scene['scene_id']} via {source}")
        update_job(
            job_id,
            "visuals",
            "complete",
            {"images": image_paths, "reuse_image": reuse_image},
            niche_id=niche_id,
        )
    except Exception as e:
        update_job(job_id, "visuals", "error", {"error": str(e)}, niche_id=niche_id)
        raise

    # —— Audio ——
    update_job(job_id, "audio", "running", {}, niche_id=niche_id)
    audio_dir = job_dir / "audio"
    try:
        audio_paths = generate_all_voiceovers(
            scenes, channel, str(audio_dir), voice=voice, speed=speed
        )
        durations = [get_audio_duration(p) for p in audio_paths]
        update_job(
            job_id,
            "audio",
            "complete",
            {"audio": audio_paths, "durations": durations},
            niche_id=niche_id,
        )
    except Exception as e:
        update_job(job_id, "audio", "error", {"error": str(e)}, niche_id=niche_id)
        raise

    # —— Assembly ——
    update_job(job_id, "assembly", "running", {}, niche_id=niche_id)
    try:
        visuals_dir = job_dir / "scenes"
        visual_clips = render_short_visual_clips(
            image_paths,
            durations,
            str(visuals_dir),
            resolution=resolution,
            fps=fps,
        )
        scene_videos: list[str] = []
        for i, (vclip, apath) in enumerate(zip(visual_clips, audio_paths)):
            muxed = visuals_dir / f"scene_{i:02d}_muxed.mp4"
            mux_scene(vclip, apath, str(muxed), fps=fps)
            scene_videos.append(str(muxed))

        music = _short_music_path(niche_id, channel)
        result = assemble_short_video(
            scene_videos=scene_videos,
            audio_dir=audio_dir,
            scene_ids=[s["scene_id"] for s in scenes],
            channel_config=channel,
            music_path=music,
            output_dir=job_dir,
            target_seconds=duration_seconds,
            quiet_music=quiet_music,
        )
        update_job(job_id, "assembly", "complete", result, niche_id=niche_id)
        update_job(
            job_id,
            "complete",
            "complete",
            {
                "final_video": f"/output/shorts/{niche_id}/{job_id}/final_short.mp4",
                "captions": f"/output/shorts/{niche_id}/{job_id}/captions.srt",
                "title": script.get("title"),
            },
            niche_id=niche_id,
        )
        _log(f"[{job_id}] short complete -> {result['final_video']}")
        return result
    except Exception as e:
        update_job(job_id, "assembly", "error", {"error": str(e)}, niche_id=niche_id)
        raise


def approve_short_script(job_id: str, niche_id: str, edited_script: dict | None = None) -> dict:
    job_dir = find_job_dir(job_id) or short_job_dir(niche_id, job_id)
    status = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    meta = (status.get("steps", {}).get("script", {}) or {}).get("data", {})
    script = edited_script
    if script is None:
        script = json.loads((job_dir / "script.json").read_text(encoding="utf-8"))
    save_json(job_dir / "script_approved.json", script)
    save_json(job_dir / "script.json", script)
    update_job(job_id, "script", "complete", {"approved": True}, niche_id=niche_id)
    return continue_short_after_script(
        job_id,
        niche_id,
        script=script,
        vertical_image=meta.get("vertical_image"),
        reuse_image=bool(meta.get("reuse_image", True)),
        voice=meta.get("voice"),
        speed=meta.get("speed"),
        quiet_music=bool(meta.get("quiet_music", False)),
        duration_seconds=int(meta.get("duration_seconds", 60)),
    )


def _load_short_script(job_dir: Path) -> dict:
    approved = job_dir / "script_approved.json"
    path = approved if approved.exists() else job_dir / "script.json"
    if not path.exists():
        raise ValueError("No short script found — generate the short first")
    return json.loads(path.read_text(encoding="utf-8"))


def _existing_short_images(job_dir: Path, scenes: list[dict], vertical_fallback: str | None) -> list[str]:
    images_dir = job_dir / "images"
    paths: list[str] = []
    for scene in scenes:
        sid = scene["scene_id"]
        candidates = [
            images_dir / f"{sid}.png",
            images_dir / f"{sid}_v.png",
            images_dir / "source_vertical.png",
        ]
        found = next((str(p) for p in candidates if p.exists()), None)
        if not found and vertical_fallback and Path(vertical_fallback).exists():
            found = vertical_fallback
        if not found:
            raise ValueError(f"Missing image for scene {sid} — cannot change voice without visuals")
        paths.append(found)
    return paths


def change_short_voice(
    job_id: str,
    niche_id: str,
    *,
    voice: str | None = None,
    speed: float | None = None,
) -> dict:
    """Re-TTS + reassemble a completed short with a new voice (keeps script + images)."""
    job_dir = find_job_dir(job_id) or short_job_dir(niche_id, job_id)
    if not (job_dir / "status.json").exists():
        raise ValueError(f"Short job not found: {job_id}")

    status = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    meta = dict((status.get("steps", {}).get("script", {}) or {}).get("data") or {})
    channel = load_short_channel(niche_id)
    voice, speed = _resolve_voice_speed(channel, voice, speed)

    meta["voice"] = voice
    meta["speed"] = speed
    update_job(job_id, "script", "complete", meta, niche_id=niche_id)

    script = _load_short_script(job_dir)
    scenes = flatten_short_scenes(script)
    if not scenes:
        raise ValueError("Short script has no scenes")

    vertical = meta.get("vertical_image") or str(job_dir / "images" / "source_vertical.png")
    image_paths = _existing_short_images(job_dir, scenes, vertical)
    resolution = channel.get("resolution") or channel.get("video", {}).get("resolution", "1080x1920")
    fps = int(channel.get("video", {}).get("fps", 30))
    duration_seconds = int(meta.get("duration_seconds") or script.get("duration_seconds") or 60)
    quiet_music = bool(meta.get("quiet_music", False))

    # —— Audio ——
    update_job(job_id, "audio", "running", {"voice": voice, "speed": speed}, niche_id=niche_id)
    audio_dir = job_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    try:
        audio_paths = generate_all_voiceovers(
            scenes, channel, str(audio_dir), voice=voice, speed=speed
        )
        durations = [get_audio_duration(p) for p in audio_paths]
        update_job(
            job_id,
            "audio",
            "complete",
            {"audio": audio_paths, "durations": durations, "voice": voice, "speed": speed},
            niche_id=niche_id,
        )
    except Exception as e:
        update_job(job_id, "audio", "error", {"error": str(e)}, niche_id=niche_id)
        raise

    # —— Assembly (re-time visuals to new VO lengths) ——
    update_job(job_id, "assembly", "running", {"voice_change": True}, niche_id=niche_id)
    try:
        visuals_dir = job_dir / "scenes"
        visuals_dir.mkdir(parents=True, exist_ok=True)
        visual_clips = render_short_visual_clips(
            image_paths,
            durations,
            str(visuals_dir),
            resolution=resolution,
            fps=fps,
        )
        scene_videos: list[str] = []
        for i, (vclip, apath) in enumerate(zip(visual_clips, audio_paths)):
            muxed = visuals_dir / f"scene_{i:02d}_muxed.mp4"
            mux_scene(vclip, apath, str(muxed), fps=fps)
            scene_videos.append(str(muxed))

        music = _short_music_path(niche_id, channel)
        result = assemble_short_video(
            scene_videos=scene_videos,
            audio_dir=audio_dir,
            scene_ids=[s["scene_id"] for s in scenes],
            channel_config=channel,
            music_path=music,
            output_dir=job_dir,
            target_seconds=duration_seconds,
            quiet_music=quiet_music,
        )
        update_job(job_id, "assembly", "complete", result, niche_id=niche_id)
        update_job(
            job_id,
            "complete",
            "complete",
            {
                "final_video": f"/output/shorts/{niche_id}/{job_id}/final_short.mp4",
                "captions": f"/output/shorts/{niche_id}/{job_id}/captions.srt",
                "title": script.get("title"),
                "voice": voice,
                "speed": speed,
            },
            niche_id=niche_id,
        )
        _log(f"[{job_id}] voice changed -> {voice} @ {speed}")
        return {
            "job_id": job_id,
            "voice": voice,
            "speed": speed,
            "final_video": f"/output/shorts/{niche_id}/{job_id}/final_short.mp4",
            **result,
        }
    except Exception as e:
        update_job(job_id, "assembly", "error", {"error": str(e)}, niche_id=niche_id)
        raise
