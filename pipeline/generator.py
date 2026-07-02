"""Main video generation pipeline orchestrator."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from lib.audio import generate_all_voiceovers, get_audio_duration
from lib.config import OUTPUT_BASE
from lib.cost_tracker import get_cost_estimate, record_image_cost, record_script_cost
from lib.image import HERO_IMAGE_NAME, generate_scene_images_batch, _hero_visual_prompt
from lib.image_style import layout_uses_broll, normalize_image_layout, resolve_image_config
from lib.music import get_music_for_act
from lib.recorder import normalize_audio, reduce_noise
from lib.stitch import (
    add_act_transition,
    add_intro_outro,
    concatenate_scenes,
    create_scene_video,
    final_render,
    mix_background_music,
)
from lib.color_grade import apply_lut
from lib.thumbnail import generate_thumbnail
from lib.script import generate_video_script
from pipeline.channel_loader import load_channel
from pipeline.status_tracker import (
    create_job,
    delete_job,
    find_job_by_topic,
    find_job_dir,
    get_job_status,
    reset_job_from_step,
    update_job,
    update_job_meta,
)


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] generator: {msg}")


def generate_job_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _image_paths_dict(scenes: list[dict], images_dir: Path) -> dict:
    paths = {}
    for scene in scenes:
        sid = scene.get("scene_id", "scene")
        paths[sid] = {
            "main": str(images_dir / f"{sid}_main.png"),
            "broll": str(images_dir / f"{sid}_broll.png"),
        }
    return paths


def _audio_paths_dict(scenes: list[dict], audio_path_list: list[str]) -> dict:
    scene_ids = [s.get("scene_id", f"scene_{i}") for i, s in enumerate(scenes)]
    return dict(zip(scene_ids, audio_path_list))


def _mix_block_music(
    block_path: str,
    out_path: str,
    niche_id: str,
    act_key: str,
    channel_config: dict,
) -> str:
    music_path = get_music_for_act(niche_id, act_key, channel_config)
    volume = channel_config.get("music", {}).get("volume", 0.12)
    if music_path:
        mix_background_music(block_path, music_path, out_path, music_volume=volume)
        return out_path
    return block_path


def flatten_scenes(script: dict) -> list[dict]:
    scenes = []
    hook = dict(script.get("hook", {}))
    if "scene_id" not in hook:
        hook["scene_id"] = "hook"
    if "narration" not in hook and "text" in hook:
        hook["narration"] = hook["text"]
    scenes.append(hook)
    for act in script.get("acts", []):
        for scene in act.get("scenes", []):
            s = dict(scene)
            if "narration" not in s and "text" in s:
                s["narration"] = s["text"]
            scenes.append(s)
    outro = dict(script.get("outro", {}))
    if "scene_id" not in outro:
        outro["scene_id"] = "outro"
    if "narration" not in outro and "text" in outro:
        outro["narration"] = outro["text"]
    scenes.append(outro)
    return scenes


REGENERATE_STAGES = ("script", "images", "thumbnail", "audio", "assembly")


def _clear_artifacts(job_dir: Path, from_step: str) -> None:
    """Remove generated files from from_step onward."""
    import shutil

    root_files = {
        "script": [
            "script.json", "script_approved.json", "description.txt", "tags.txt", "titles.txt",
            "thumbnail.png", "thumbnail_bg.png", "concat.mp4", "with_intro_outro.mp4",
            "graded.mp4", "final_video.mp4", "cost_estimate.json",
        ],
        "images": [
            "thumbnail.png", "thumbnail_bg.png", "concat.mp4", "with_intro_outro.mp4",
            "graded.mp4", "final_video.mp4",
        ],
        "thumbnail": [
            "thumbnail.png", "thumbnail_bg.png", "concat.mp4", "with_intro_outro.mp4",
            "graded.mp4", "final_video.mp4",
        ],
        "audio": [
            "concat.mp4", "with_intro_outro.mp4", "graded.mp4", "final_video.mp4",
        ],
        "assembly": [
            "concat.mp4", "with_intro_outro.mp4", "graded.mp4", "final_video.mp4",
        ],
    }
    root_dirs = {
        "script": ["images", "audio", "scenes", "motion", "blocks", "audio_human"],
        "images": ["images", "scenes", "motion", "blocks"],
        "thumbnail": ["scenes", "motion", "blocks"],
        "audio": ["audio", "scenes", "motion", "blocks", "audio_human"],
        "assembly": ["scenes", "motion", "blocks"],
    }

    for name in root_files.get(from_step, []):
        path = job_dir / name
        if path.exists():
            path.unlink()

    for name in root_dirs.get(from_step, []):
        path = job_dir / name
        if path.is_dir():
            shutil.rmtree(path)


def prepare_video_job(
    topic: str,
    niche_id: str,
    duration_minutes: int,
    audio_mode: str,
    voice: str | None = None,
    speed: float = 0.85,
    job_id: str | None = None,
    script_mode: str = "ai",
    image_mode: str = "ai",
    image_layout: str = "one_image",
    visual_style: str | None = None,
) -> tuple[str, bool]:
    load_channel(niche_id)
    existing = find_job_by_topic(niche_id, topic)
    reused = existing is not None

    if reused:
        job_id = existing["job_id"]
        job_dir = OUTPUT_BASE / niche_id / job_id
        reset_job_from_step(job_id, "script", niche_id=niche_id)
        _clear_artifacts(job_dir, "script")
        update_job_meta(job_id, niche_id, topic=topic, audio_mode=audio_mode)
    else:
        job_id = job_id or generate_job_id()
        job_dir = OUTPUT_BASE / niche_id / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        create_job(job_id, niche_id, topic, audio_mode)

    update_job(
        job_id,
        "script",
        "running",
        {
            "audio_mode": audio_mode,
            "voice": voice,
            "speed": speed,
            "duration_minutes": duration_minutes,
            "script_mode": script_mode,
            "image_mode": image_mode,
            "image_layout": normalize_image_layout(image_layout),
            "visual_style": visual_style,
        },
        niche_id=niche_id,
    )
    return job_id, reused


def ingest_manual_script(
    job_id: str,
    niche_id: str,
    script: dict,
    topic: str,
    duration_minutes: int = 10,
    audio_mode: str = "ai",
    voice: str | None = None,
    speed: float = 0.85,
    image_mode: str = "ai",
    image_layout: str = "one_image",
    visual_style: str | None = None,
) -> None:
    """Save a user-provided script and mark ready for review (no LLM call)."""
    from lib.script_schema import normalize_script, validate_script

    job_dir = OUTPUT_BASE / niche_id / job_id
    ok, errors = validate_script(script)
    if not ok:
        raise ValueError("; ".join(errors))

    normalized = normalize_script(script, humanize=False)
    save_json(job_dir / "script.json", normalized)
    save_text(job_dir / "description.txt", normalized.get("description", ""))
    save_text(job_dir / "tags.txt", "\n".join(normalized.get("tags", [])))
    if normalized.get("title_variations"):
        save_text(job_dir / "titles.txt", "\n".join(normalized["title_variations"]))

    update_job(
        job_id,
        "script",
        "pending_review",
        {
            "review_url": f"/ui/review.html?job_id={job_id}",
            "script_path": str(job_dir / "script.json"),
            "audio_mode": audio_mode,
            "voice": voice,
            "speed": speed,
            "duration_minutes": duration_minutes,
            "script_mode": "manual",
            "image_mode": image_mode,
            "image_layout": normalize_image_layout(image_layout),
            "visual_style": visual_style,
        },
        niche_id=niche_id,
    )
    _log(f"Manual script ingested for job {job_id}: {topic}")


def run_script_generation(
    job_id: str,
    topic: str,
    niche_id: str,
    duration_minutes: int = 10,
    audio_mode: str = "ai",
    voice: str | None = None,
    speed: float = 0.85,
) -> None:
    channel = load_channel(niche_id)
    job_dir = OUTPUT_BASE / niche_id / job_id
    _log(f"Starting job {job_id} for {niche_id}: {topic}")
    try:
        script = generate_video_script(topic, channel, duration_minutes)
        save_json(job_dir / "script.json", script)
        save_text(job_dir / "description.txt", script.get("description", ""))
        save_text(job_dir / "tags.txt", "\n".join(script.get("tags", [])))
        save_text(job_dir / "titles.txt", "\n".join(script.get("title_variations", [])))

        cost_data = record_script_cost(job_dir, topic, script)
        status_data = get_job_status(job_id).get("steps", {}).get("script", {}).get("data", {})
        update_job(
            job_id,
            "script",
            "pending_review",
            {
                "review_url": f"/ui/review.html?job_id={job_id}",
                "script_path": str(job_dir / "script.json"),
                "audio_mode": audio_mode,
                "voice": voice,
                "speed": speed,
                "duration_minutes": duration_minutes,
                "cost_estimate": cost_data,
                "script_mode": "ai",
                "image_mode": status_data.get("image_mode", "ai"),
                "image_layout": status_data.get("image_layout", "one_image"),
                "visual_style": status_data.get("visual_style"),
            },
            niche_id=niche_id,
        )
    except Exception as e:
        _log(f"Script generation failed: {e}")
        update_job(job_id, "script", "error", {"error": str(e)}, niche_id=niche_id)


async def generate_video(
    topic: str,
    niche_id: str,
    duration_minutes: int = 10,
    audio_mode: str = "ai",
    voice: str | None = None,
    speed: float = 0.85,
    job_id: str | None = None,
) -> dict:
    job_id, _reused = prepare_video_job(
        topic, niche_id, duration_minutes, audio_mode, voice, speed, job_id
    )
    run_script_generation(
        job_id, topic, niche_id, duration_minutes, audio_mode, voice, speed
    )
    job_dir = OUTPUT_BASE / niche_id / job_id
    script_path = job_dir / "script.json"
    script = {}
    if script_path.exists():
        with open(script_path, encoding="utf-8") as f:
            script = json.load(f)
    return {
        "job_id": job_id,
        "status": "pending_script_review",
        "review_url": f"/ui/review.html?job_id={job_id}",
        "script": script,
    }


PIPELINE_STEPS = ("images", "thumbnail", "audio", "assembly")


def _step_index(step: str) -> int:
    return PIPELINE_STEPS.index(step)


def _should_run_step(step: str, from_step: str) -> bool:
    return _step_index(step) >= _step_index(from_step)


def _load_script(job_dir: Path) -> dict:
    script_path = job_dir / "script_approved.json"
    if not script_path.exists():
        script_path = job_dir / "script.json"
    with open(script_path, encoding="utf-8") as f:
        return json.load(f)


def _images_exist(job_dir: Path, script: dict) -> bool:
    for scene in flatten_scenes(script):
        sid = scene.get("scene_id", "scene")
        if not (job_dir / "images" / f"{sid}_main.png").exists():
            return False
    return True


def _audio_exists(job_dir: Path, script: dict) -> bool:
    for scene in flatten_scenes(script):
        sid = scene.get("scene_id", "scene")
        if not (job_dir / "audio" / f"{sid}_voice.wav").exists():
            return False
    return True


def _load_image_paths(status: dict, job_dir: Path, script: dict) -> dict:
    image_paths = status.get("steps", {}).get("images", {}).get("data", {}).get("paths")
    if image_paths:
        return image_paths
    return _image_paths_dict(flatten_scenes(script), job_dir / "images")


def _load_audio_paths(job_dir: Path, script: dict) -> dict[str, str]:
    audio_paths: dict[str, str] = {}
    for scene in flatten_scenes(script):
        sid = scene.get("scene_id", "scene")
        wav = job_dir / "audio" / f"{sid}_voice.wav"
        if wav.exists():
            audio_paths[sid] = str(wav)
    return audio_paths


def get_resume_info(job_id: str) -> dict:
    """Return which pipeline step to resume from and which steps are already done."""
    job_dir = find_job_dir(job_id)
    if job_dir is None:
        raise ValueError(f"Job not found: {job_id}")

    status = get_job_status(job_id)
    niche_id = status.get("niche_id")
    steps = status.get("steps", {})
    base = {
        "job_id": job_id,
        "niche_id": niche_id,
        "topic": status.get("topic"),
        "overall_status": status.get("overall_status"),
        "audio_mode": status.get("audio_mode", "ai"),
        "error": _latest_error(steps),
    }

    if status.get("overall_status") == "complete":
        return {
            **base,
            "resume_step": "done",
            "completed_steps": ["script", *PIPELINE_STEPS],
            "message": "Job is already complete",
            "can_resume": False,
        }

    script_status = steps.get("script", {}).get("status")
    if script_status == "error":
        return {
            **base,
            "resume_step": "script",
            "completed_steps": [],
            "message": "Re-run script generation",
            "can_resume": True,
        }
    if script_status == "pending_review":
        return {
            **base,
            "resume_step": "review",
            "completed_steps": [],
            "message": "Script awaiting review — open review page to continue",
            "can_resume": False,
        }
    if script_status != "approved":
        if (job_dir / "script.json").exists():
            return {
                **base,
                "resume_step": "review",
                "completed_steps": [],
                "message": "Script ready for review",
                "can_resume": False,
            }
        return {
            **base,
            "resume_step": "script",
            "completed_steps": [],
            "message": "Re-run script generation",
            "can_resume": True,
        }

    completed = ["script"]
    script = _load_script(job_dir)

    if steps.get("images", {}).get("status") != "complete" or not _images_exist(job_dir, script):
        return {
            **base,
            "resume_step": "images",
            "completed_steps": completed,
            "message": "Resume from image generation (script kept)",
            "can_resume": True,
        }
    completed.append("images")

    if steps.get("thumbnail", {}).get("status") != "complete" or not (job_dir / "thumbnail.png").exists():
        return {
            **base,
            "resume_step": "thumbnail",
            "completed_steps": completed,
            "message": "Resume from thumbnail generation",
            "can_resume": True,
        }
    completed.append("thumbnail")

    audio_status = steps.get("audio", {}).get("status")
    if audio_status == "pending_human":
        return {
            **base,
            "resume_step": "human_recording",
            "completed_steps": completed,
            "message": "Continue with human voiceover recording",
            "can_resume": False,
        }
    if audio_status == "pending_hybrid":
        return {
            **base,
            "resume_step": "hybrid_recording",
            "completed_steps": completed,
            "message": "Continue with hybrid voiceover review",
            "can_resume": False,
        }
    if audio_status != "complete" or not _audio_exists(job_dir, script):
        return {
            **base,
            "resume_step": "audio",
            "completed_steps": completed,
            "message": "Resume from voiceover generation",
            "can_resume": True,
        }
    completed.append("audio")

    return {
        **base,
        "resume_step": "assembly",
        "completed_steps": completed,
        "message": "Resume video assembly only (no API tokens used)",
        "can_resume": True,
    }


def _latest_error(steps: dict) -> str | None:
    for step in ("assembly", "audio", "thumbnail", "images", "script"):
        err = steps.get(step, {}).get("data", {}).get("error")
        if err:
            return err
    return None


def run_resume_job(job_id: str, niche_id: str | None = None) -> None:
    """Sync wrapper for script-only resume (used when resume_step is script)."""
    status = get_job_status(job_id)
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    niche_id = niche_id or status.get("niche_id")
    run_script_generation(
        job_id,
        status["topic"],
        niche_id,
        script_data.get("duration_minutes", 10),
        status.get("audio_mode", "ai"),
        script_data.get("voice"),
        script_data.get("speed", 0.85),
    )


async def run_resume_job_async(job_id: str, niche_id: str | None = None) -> dict:
    """Async entry point for background task resume."""
    info = get_resume_info(job_id)
    resume_step = info["resume_step"]
    niche_id = niche_id or info["niche_id"]

    if resume_step == "done":
        return {"job_id": job_id, "status": "complete", "message": info["message"]}
    if resume_step == "review":
        return {
            "job_id": job_id,
            "status": "pending_review",
            "review_url": f"/ui/review.html?job_id={job_id}",
        }
    if resume_step == "human_recording":
        return {
            "job_id": job_id,
            "status": "waiting_for_human_voiceover",
            "recorder_url": f"/ui/recorder.html?job_id={job_id}&mode=human",
        }
    if resume_step == "hybrid_recording":
        return {
            "job_id": job_id,
            "status": "waiting_for_hybrid_review",
            "recorder_url": f"/ui/recorder.html?job_id={job_id}&mode=hybrid",
        }

    if resume_step == "script":
        status = get_job_status(job_id)
        script_data = status.get("steps", {}).get("script", {}).get("data", {})
        run_script_generation(
            job_id,
            status["topic"],
            niche_id,
            script_data.get("duration_minutes", 10),
            status.get("audio_mode", "ai"),
            script_data.get("voice"),
            script_data.get("speed", 0.85),
        )
        return {"job_id": job_id, "status": "script_generating"}

    job_dir = OUTPUT_BASE / niche_id / job_id
    script = _load_script(job_dir)
    status = get_job_status(job_id)
    audio_mode = status.get("audio_mode", "ai")
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    voice = script_data.get("voice")
    speed = script_data.get("speed", 0.85)

    if resume_step == "assembly":
        return _run_assembly_only(job_id, niche_id, script, job_dir)

    try:
        return await continue_after_approval(
            job_id, niche_id, script, audio_mode, voice, speed, from_step=resume_step
        )
    except Exception as e:
        _log(f"Resume failed: {e}")
        raise


def _image_layout_from_status(status: dict) -> str:
    images_data = status.get("steps", {}).get("images", {}).get("data", {})
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    raw = images_data.get("image_layout") or script_data.get("image_layout", "one_image")
    return normalize_image_layout(raw)


def _visual_style_from_status(status: dict) -> str | None:
    images_data = status.get("steps", {}).get("images", {}).get("data", {})
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    return images_data.get("visual_style") or script_data.get("visual_style")


def _run_assembly_only(job_id: str, niche_id: str, script: dict, job_dir: Path) -> dict:
    status = get_job_status(job_id)
    image_paths = _load_image_paths(status, job_dir, script)
    audio_paths = _load_audio_paths(job_dir, script)
    if not audio_paths:
        raise ValueError(f"No audio files found for job {job_id}")

    channel = load_channel(niche_id)
    image_layout = _image_layout_from_status(status)
    try:
        update_job(job_id, "assembly", "running", niche_id=niche_id)
        final_path = assemble_video(
            script, image_paths, audio_paths, channel, job_dir, niche_id,
            image_layout=image_layout,
        )
        update_job(
            job_id,
            "assembly",
            "complete",
            {"output_path": str(final_path), "cost_estimate": get_cost_estimate(job_dir)},
            niche_id=niche_id,
        )
        update_job(
            job_id,
            "complete",
            "complete",
            {"output_path": str(final_path), "cost_estimate": get_cost_estimate(job_dir)},
            niche_id=niche_id,
        )
        return {
            "job_id": job_id,
            "status": "complete",
            "output_path": str(final_path),
            "thumbnail_path": status.get("steps", {}).get("thumbnail", {}).get("data", {}).get("thumbnail_path"),
        }
    except Exception as e:
        _log(f"Assembly resume failed: {e}")
        update_job(job_id, "assembly", "error", {"error": str(e)}, niche_id=niche_id)
        raise


async def continue_after_approval(
    job_id: str,
    niche_id: str,
    approved_script: dict,
    audio_mode: str = "ai",
    voice: str | None = None,
    speed: float | None = None,
    from_step: str = "images",
    image_mode: str | None = None,
    image_layout: str | None = None,
    visual_style: str | None = None,
) -> dict:
    channel = load_channel(niche_id)
    job_dir = OUTPUT_BASE / niche_id / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    save_json(job_dir / "script_approved.json", approved_script)
    update_job(job_id, "script", "approved", niche_id=niche_id)

    desc_path = job_dir / "description.txt"
    if not desc_path.exists():
        save_text(desc_path, approved_script.get("description", ""))
    disclaimer = channel.get("script", {}).get("disclaimer", "")
    if disclaimer.strip():
        existing = desc_path.read_text(encoding="utf-8") if desc_path.exists() else ""
        if disclaimer.strip() not in existing:
            with open(desc_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n{disclaimer.strip()}")

    if speed is None:
        status = get_job_status(job_id)
        speed = status.get("steps", {}).get("script", {}).get("data", {}).get("speed", 0.85)
    if voice is None:
        status = get_job_status(job_id)
        voice = status.get("steps", {}).get("script", {}).get("data", {}).get("voice")

    all_scenes = flatten_scenes(approved_script)
    status = get_job_status(job_id)
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    if image_mode is None:
        image_mode = script_data.get("image_mode", "ai")
    if image_layout is None:
        image_layout = _image_layout_from_status(status)
    else:
        image_layout = normalize_image_layout(image_layout)
    if visual_style is None:
        visual_style = _visual_style_from_status(status)
    resolved_channel = resolve_image_config(channel, visual_style)
    image_paths = _load_image_paths(status, job_dir, approved_script)
    thumbnail_path = status.get("steps", {}).get("thumbnail", {}).get("data", {}).get("thumbnail_path")

    try:
        if _should_run_step("images", from_step):
            current_step = "images"
            if image_mode == "upload":
                update_job(
                    job_id,
                    "images",
                    "pending_upload",
                    {
                        "scenes": [{"scene_id": s.get("scene_id")} for s in all_scenes],
                        "image_layout": image_layout,
                        "visual_style": visual_style,
                        "assets_url": f"/ui/assets.html?job_id={job_id}",
                    },
                    niche_id=niche_id,
                )
                return {
                    "job_id": job_id,
                    "status": "pending_image_upload",
                    "assets_url": f"/ui/assets.html?job_id={job_id}",
                }
            update_job(job_id, "images", "running", niche_id=niche_id)
            _, image_sources = generate_scene_images_batch(
                all_scenes,
                channel,
                str(job_dir / "images"),
                image_layout=image_layout,
                visual_style=visual_style,
            )
            image_paths = _image_paths_dict(all_scenes, job_dir / "images")
            cost_data = record_image_cost(
                job_dir,
                image_sources.get("flux_count", 0),
                image_sources.get("pexels_count", 0),
            )
            update_job(
                job_id,
                "images",
                "complete",
                {
                    "paths": image_paths,
                    "cost_estimate": cost_data,
                    "fallbacks": image_sources.get("fallbacks", {}),
                    "placeholder_count": image_sources.get("placeholder_count", 0),
                    "image_layout": image_layout,
                    "image_mode": image_mode,
                    "visual_style": image_sources.get("visual_style") or visual_style,
                },
                niche_id=niche_id,
            )

        if _should_run_step("thumbnail", from_step):
            current_step = "thumbnail"
            update_job(job_id, "thumbnail", "running", niche_id=niche_id)
            thumbnail_path = generate_thumbnail(
                approved_script.get("title", "Video"),
                resolved_channel,
                str(job_dir / "thumbnail.png"),
            )
            update_job(
                job_id, "thumbnail", "complete", {"thumbnail_path": thumbnail_path}, niche_id=niche_id
            )

        audio_paths = _load_audio_paths(job_dir, approved_script)

        if _should_run_step("audio", from_step):
            current_step = "audio"
            update_job(job_id, "audio", "running", niche_id=niche_id)

            if audio_mode == "human":
                update_job(
                    job_id,
                    "audio",
                    "pending_human",
                    {
                        "scenes": all_scenes,
                        "image_paths": image_paths,
                        "job_dir": str(job_dir),
                        "waiting_for": "human_voiceover",
                    },
                    niche_id=niche_id,
                )
                return {
                    "job_id": job_id,
                    "status": "waiting_for_human_voiceover",
                    "script": approved_script,
                    "recorder_url": f"/ui/recorder.html?job_id={job_id}&mode=human",
                }

            audio_path_list = generate_all_voiceovers(
                all_scenes, channel, str(job_dir / "audio"), voice=voice, speed=speed
            )
            audio_paths = _audio_paths_dict(all_scenes, audio_path_list)

            if audio_mode == "hybrid":
                update_job(
                    job_id,
                    "audio",
                    "pending_hybrid",
                    {
                        "ai_audio_paths": audio_paths,
                        "image_paths": image_paths,
                        "scenes": all_scenes,
                        "waiting_for": "human_review",
                    },
                    niche_id=niche_id,
                )
                return {
                    "job_id": job_id,
                    "status": "waiting_for_hybrid_review",
                    "script": approved_script,
                    "recorder_url": f"/ui/recorder.html?job_id={job_id}&mode=hybrid",
                }

            update_job(job_id, "audio", "complete", niche_id=niche_id)

        if _should_run_step("assembly", from_step):
            current_step = "assembly"
            update_job(job_id, "assembly", "running", niche_id=niche_id)
            if not audio_paths:
                audio_paths = _load_audio_paths(job_dir, approved_script)
            final_path = assemble_video(
                approved_script, image_paths, audio_paths, channel, job_dir, niche_id,
                image_layout=image_layout,
            )
            update_job(
                job_id,
                "assembly",
                "complete",
                {
                    "output_path": str(final_path),
                    "cost_estimate": get_cost_estimate(job_dir),
                },
                niche_id=niche_id,
            )
            update_job(
                job_id,
                "complete",
                "complete",
                {
                    "output_path": str(final_path),
                    "cost_estimate": get_cost_estimate(job_dir),
                },
                niche_id=niche_id,
            )

            return {
                "job_id": job_id,
                "status": "complete",
                "output_path": str(final_path),
                "thumbnail_path": thumbnail_path,
            }

        return {"job_id": job_id, "status": "complete"}
    except Exception as e:
        _log(f"Pipeline failed at {current_step}: {e}")
        update_job(job_id, current_step, "error", {"error": str(e)}, niche_id=niche_id)
        raise


def assemble_video(
    script: dict,
    image_paths: dict,
    audio_paths: dict,
    channel_config: dict,
    job_dir: Path,
    niche_id: str,
    image_layout: str = "one_image",
) -> str:
    _log("Assembling final video")
    all_scenes = flatten_scenes(script)
    scenes_dir = job_dir / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    blocks_dir = job_dir / "blocks"
    blocks_dir.mkdir(exist_ok=True)

    transition_type = channel_config.get("video", {}).get("transition_type", "crossfade")
    fps = channel_config.get("video", {}).get("fps", 30)
    broll_freq = channel_config.get("video", {}).get("broll_frequency", 3)
    max_segment = channel_config.get("video", {}).get("max_visual_segment_seconds", 7.0)

    use_broll = layout_uses_broll(image_layout)
    scene_video_map: dict[str, str] = {}
    for i, scene in enumerate(all_scenes):
        scene_id = scene.get("scene_id", f"scene_{i}")
        imgs = image_paths.get(scene_id, {})
        main = imgs.get("main", "")
        broll = imgs.get("broll", main)
        audio = audio_paths.get(scene_id, "")
        if not main or not audio:
            _log(f"Skipping scene {scene_id} - missing assets")
            continue
        out = scenes_dir / f"{scene_id}.mp4"
        create_scene_video(
            main, broll, audio, str(out),
            broll_at_second=broll_freq,
            transition=transition_type,
            use_broll=use_broll,
            fps=fps,
            max_segment_seconds=max_segment,
        )
        scene_video_map[scene_id] = str(out)

    act_blocks: list[str] = []

    hook_id = script.get("hook", {}).get("scene_id", "hook")
    if hook_id in scene_video_map:
        hook_block = str(blocks_dir / "hook_block.mp4")
        concatenate_scenes([scene_video_map[hook_id]], hook_block, transition=transition_type, fps=fps)
        hook_mixed = str(blocks_dir / "hook_mixed.mp4")
        hook_final = _mix_block_music(
            hook_block, hook_mixed, niche_id, "hook", channel_config
        )
        act_blocks.append(hook_final)

    for act in script.get("acts", []):
        act_scene_videos = [
            scene_video_map[s["scene_id"]]
            for s in act.get("scenes", [])
            if s.get("scene_id") in scene_video_map
        ]
        if not act_scene_videos:
            continue

        act_num = act.get("act_number", 1)
        act_block = str(blocks_dir / f"act{act_num}_block.mp4")
        concatenate_scenes(act_scene_videos, act_block, transition=transition_type, fps=fps)

        act_mixed = str(blocks_dir / f"act{act_num}_mixed.mp4")
        act_final = _mix_block_music(
            act_block, act_mixed, niche_id, f"act{act_num}", channel_config
        )

        transition_path = str(blocks_dir / f"act{act_num}_transition.mp4")
        add_act_transition(
            act_final,
            act.get("act_title", f"Act {act_num}"),
            channel_config,
            transition_path,
            fps=fps,
        )
        act_blocks.append(transition_path)

    outro_id = script.get("outro", {}).get("scene_id", "outro")
    if outro_id in scene_video_map:
        outro_block = str(blocks_dir / "outro_block.mp4")
        concatenate_scenes([scene_video_map[outro_id]], outro_block, transition=transition_type, fps=fps)
        outro_mixed = str(blocks_dir / "outro_mixed.mp4")
        outro_final = _mix_block_music(
            outro_block, outro_mixed, niche_id, "outro", channel_config
        )
        act_blocks.append(outro_final)

    if not act_blocks:
        raise ValueError("No scene blocks to assemble")

    concat_path = job_dir / "concat.mp4"
    concatenate_scenes(act_blocks, str(concat_path), transition="cut", fps=fps)

    with_intro = job_dir / "with_intro_outro.mp4"
    add_intro_outro(str(concat_path), channel_config, str(with_intro), fps=fps)

    lut_name = channel_config.get("style_lock", {}).get("color_grade", "")
    graded_path = job_dir / "graded.mp4"
    apply_lut(str(with_intro), lut_name, str(graded_path))

    final_path = job_dir / "final_video.mp4"
    res = channel_config.get("video", {}).get("resolution", "1920x1080")
    final_render(str(graded_path), str(final_path), resolution=res, fps=fps)
    _log(f"Final video: {final_path}")
    return str(final_path)


def resume_assembly(job_id: str, niche_id: str | None = None) -> str:
    """Re-run video assembly for an existing job using saved script, images, and audio."""
    job_dir = find_job_dir(job_id)
    if not job_dir:
        raise ValueError(f"Job not found: {job_id}")

    status = get_job_status(job_id)
    niche_id = niche_id or status.get("niche_id")
    if not niche_id:
        raise ValueError(f"niche_id required for job {job_id}")

    script = _load_script(job_dir)
    result = _run_assembly_only(job_id, niche_id, script, job_dir)
    return result["output_path"]


async def regenerate_stage(
    job_id: str,
    stage: str,
    niche_id: str | None = None,
) -> dict:
    """Force re-run a specific pipeline stage and everything after it."""
    if stage not in REGENERATE_STAGES:
        raise ValueError(f"Invalid stage: {stage}. Must be one of {REGENERATE_STAGES}")

    job_dir = find_job_dir(job_id)
    if job_dir is None:
        raise ValueError(f"Job not found: {job_id}")

    status = get_job_status(job_id)
    niche_id = niche_id or status.get("niche_id")
    if not niche_id:
        raise ValueError(f"niche_id required for job {job_id}")

    reset_job_from_step(job_id, stage, niche_id=niche_id)
    _clear_artifacts(job_dir, stage)

    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    audio_mode = status.get("audio_mode", "ai")
    voice = script_data.get("voice")
    speed = script_data.get("speed", 0.85)
    topic = status.get("topic", "")
    duration = script_data.get("duration_minutes", 10)

    if stage == "script":
        run_script_generation(
            job_id, topic, niche_id, duration, audio_mode, voice, speed
        )
        return {"job_id": job_id, "status": "script_generating", "stage": stage}

    script_path = job_dir / "script_approved.json"
    if not script_path.exists():
        script_path = job_dir / "script.json"
    if not script_path.exists():
        raise ValueError("No script found — regenerate script first")

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    if not (job_dir / "script_approved.json").exists():
        save_json(job_dir / "script_approved.json", script)
    update_job(job_id, "script", "approved", niche_id=niche_id)

    return await continue_after_approval(
        job_id, niche_id, script, audio_mode, voice, speed, from_step=stage
    )


def remove_job(job_id: str) -> None:
    """Delete a job and all its artifacts."""
    delete_job(job_id)


def _job_output_url(niche_id: str, job_id: str, rel_path: str) -> str:
    return f"/output/{niche_id}/{job_id}/{rel_path}"


def save_script(job_id: str, edited_script: dict) -> dict:
    """Persist user-edited script to disk."""
    job_dir = find_job_dir(job_id)
    if job_dir is None:
        raise ValueError(f"Job not found: {job_id}")

    save_json(job_dir / "script.json", edited_script)
    if (job_dir / "script_approved.json").exists():
        save_json(job_dir / "script_approved.json", edited_script)
    save_text(job_dir / "description.txt", edited_script.get("description", ""))
    save_text(job_dir / "tags.txt", "\n".join(edited_script.get("tags", [])))
    if edited_script.get("title_variations"):
        save_text(job_dir / "titles.txt", "\n".join(edited_script["title_variations"]))

    status = get_job_status(job_id)
    niche_id = status.get("niche_id", "")
    _log(f"Saved edited script for job {job_id}")
    return {"job_id": job_id, "niche_id": niche_id, "saved": True}


def get_assets_status(job_id: str) -> dict:
    """Return per-scene upload slots with prompts for manual image mode."""
    job_dir = find_job_dir(job_id)
    if job_dir is None:
        raise ValueError(f"Job not found: {job_id}")

    status = get_job_status(job_id)
    niche_id = status.get("niche_id", "")
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    images_data = status.get("steps", {}).get("images", {}).get("data", {})
    image_layout = normalize_image_layout(
        images_data.get("image_layout") or script_data.get("image_layout", "one_image")
    )
    visual_style = images_data.get("visual_style") or script_data.get("visual_style")

    script = _load_script(job_dir)
    scenes = flatten_scenes(script)
    images_dir = job_dir / "images"
    upload_slots: list[dict] = []
    scenes_grouped: list[dict] = []
    all_ready = True

    if image_layout == "one_image":
        hero_path = images_dir / HERO_IMAGE_NAME
        has_hero = hero_path.exists()
        prompt = _hero_visual_prompt(scenes)
        slot = {
            "scene_id": "hero",
            "scene_label": "Entire video",
            "slot_label": "Hero image (all scenes)",
            "asset_type": "main",
            "prompt": prompt,
            "required": True,
            "uploaded": has_hero,
            "url": _job_output_url(niche_id, job_id, f"images/{HERO_IMAGE_NAME}") if has_hero else None,
            "narration_preview": "",
        }
        if not has_hero:
            all_ready = False
        upload_slots.append(slot)
        scenes_grouped.append({
            "scene_id": "hero",
            "label": "Entire video",
            "narration_preview": "One image is used for every scene with Ken Burns motion.",
            "main": has_hero,
            "broll": has_hero,
            "main_url": slot["url"],
            "broll_url": None,
            "visual_prompt": prompt,
            "broll_prompt": prompt,
            "slots": [slot],
        })
        return {
            "job_id": job_id,
            "niche_id": niche_id,
            "image_layout": image_layout,
            "visual_style": visual_style,
            "scenes": scenes_grouped,
            "upload_slots": upload_slots,
            "uploaded_count": 1 if has_hero else 0,
            "required_count": 1,
            "ready": all_ready,
        }

    def _label_for(sid: str) -> str:
        if sid == "hook":
            return "Hook"
        if sid == "outro":
            return "Outro"
        return sid.replace("_", " ").title()

    def _narration_preview(scene: dict) -> str:
        text = scene.get("narration", scene.get("text", ""))
        text = " ".join(text.split())
        return text[:160] + ("…" if len(text) > 160 else "")

    for scene in scenes:
        sid = scene.get("scene_id", "scene")
        main_path = images_dir / f"{sid}_main.png"
        broll_path = images_dir / f"{sid}_broll.png"
        has_main = main_path.exists()
        has_broll = broll_path.exists()
        visual = scene.get("visual_prompt", "Cinematic scene — no text in image")
        broll = scene.get("broll_prompt", visual)
        narration = _narration_preview(scene)
        scene_label = _label_for(sid)

        slot_defs = [
            {
                "asset_type": "main",
                "slot_label": "Main image",
                "prompt": visual,
                "required": True,
                "uploaded": has_main,
                "url": _job_output_url(niche_id, job_id, f"images/{sid}_main.png") if has_main else None,
            },
        ]
        if image_layout == "multiple":
            slot_defs.append({
                "asset_type": "broll",
                "slot_label": "B-roll image",
                "prompt": broll,
                "required": True,
                "uploaded": has_broll,
                "url": _job_output_url(niche_id, job_id, f"images/{sid}_broll.png") if has_broll else None,
            })

        scene_slots = []
        for slot in slot_defs:
            if slot["required"] and not slot["uploaded"]:
                all_ready = False
            entry = {
                "scene_id": sid,
                "scene_label": scene_label,
                "narration_preview": narration,
                **slot,
            }
            upload_slots.append(entry)
            scene_slots.append(entry)

        scenes_grouped.append({
            "scene_id": sid,
            "label": scene_label,
            "narration_preview": narration,
            "main": has_main,
            "broll": has_broll,
            "main_url": _job_output_url(niche_id, job_id, f"images/{sid}_main.png") if has_main else None,
            "broll_url": _job_output_url(niche_id, job_id, f"images/{sid}_broll.png") if has_broll else None,
            "visual_prompt": visual,
            "broll_prompt": broll,
            "slots": scene_slots,
        })

    uploaded_count = sum(1 for s in upload_slots if s["uploaded"])
    required_count = sum(1 for s in upload_slots if s["required"])

    return {
        "job_id": job_id,
        "niche_id": niche_id,
        "image_layout": image_layout,
        "visual_style": visual_style,
        "scenes": scenes_grouped,
        "upload_slots": upload_slots,
        "uploaded_count": uploaded_count,
        "required_count": required_count,
        "ready": all_ready,
    }


def save_uploaded_scene_image(
    job_id: str,
    scene_id: str,
    asset_type: str,
    file_bytes: bytes,
) -> dict:
    """Save an uploaded scene image (main or broll)."""
    from lib.assets import copy_as_broll, propagate_hero_to_scenes, save_uploaded_image

    job_dir = find_job_dir(job_id)
    if job_dir is None:
        raise ValueError(f"Job not found: {job_id}")

    status = get_job_status(job_id)
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    images_data = status.get("steps", {}).get("images", {}).get("data", {})
    image_layout = normalize_image_layout(
        images_data.get("image_layout") or script_data.get("image_layout", "one_image")
    )

    if asset_type not in ("main", "broll"):
        raise ValueError("asset_type must be main or broll")

    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    if image_layout == "one_image":
        hero_path = images_dir / HERO_IMAGE_NAME
        save_uploaded_image(file_bytes, hero_path)
        script = _load_script(job_dir)
        propagate_hero_to_scenes(hero_path, flatten_scenes(script), images_dir)
        return get_assets_status(job_id)

    main_path = images_dir / f"{scene_id}_main.png"
    broll_path = images_dir / f"{scene_id}_broll.png"

    if asset_type == "main":
        save_uploaded_image(file_bytes, main_path)
        if image_layout == "per_scene":
            copy_as_broll(main_path, broll_path)
    else:
        save_uploaded_image(file_bytes, broll_path)

    return get_assets_status(job_id)


async def continue_after_image_upload(
    job_id: str,
    niche_id: str,
    audio_mode: str | None = None,
    voice: str | None = None,
    speed: float | None = None,
) -> dict:
    """Continue pipeline after manual image uploads are complete."""
    assets = get_assets_status(job_id)
    if not assets["ready"]:
        raise ValueError("Not all required images uploaded")

    status = get_job_status(job_id)
    niche_id = niche_id or status.get("niche_id", "")
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    script = _load_script(find_job_dir(job_id) or OUTPUT_BASE / niche_id / job_id)
    image_layout = assets.get("image_layout", "one_image")
    visual_style = assets.get("visual_style") or script_data.get("visual_style")
    job_dir = OUTPUT_BASE / niche_id / job_id
    all_scenes = flatten_scenes(script)
    image_paths = _image_paths_dict(all_scenes, job_dir / "images")

    update_job(
        job_id,
        "images",
        "complete",
        {
            "paths": image_paths,
            "image_layout": image_layout,
            "image_mode": "upload",
            "visual_style": visual_style,
        },
        niche_id=niche_id,
    )

    if audio_mode is None:
        audio_mode = status.get("audio_mode", script_data.get("audio_mode", "ai"))
    if voice is None:
        voice = script_data.get("voice")
    if speed is None:
        speed = script_data.get("speed", 0.85)

    return await continue_after_approval(
        job_id,
        niche_id,
        script,
        audio_mode,
        voice,
        speed,
        from_step="thumbnail",
        image_mode="upload",
        image_layout=image_layout,
        visual_style=visual_style,
    )


def get_stage_preview(job_id: str, stage: str) -> dict:
    """Return preview assets and content for a pipeline stage."""
    if stage not in REGENERATE_STAGES:
        raise ValueError(f"Invalid stage: {stage}")

    job_dir = find_job_dir(job_id)
    if job_dir is None:
        raise ValueError(f"Job not found: {job_id}")

    status = get_job_status(job_id)
    niche_id = status.get("niche_id", "")
    step_info = status.get("steps", {}).get(stage, {})
    step_status = step_info.get("status", "pending")
    error = step_info.get("data", {}).get("error")

    preview: dict = {
        "job_id": job_id,
        "niche_id": niche_id,
        "stage": stage,
        "status": step_status,
        "error": error,
        "assets": [],
        "scenes": [],
        "has_content": False,
    }

    if stage == "script":
        script_path = job_dir / "script_approved.json"
        if not script_path.exists():
            script_path = job_dir / "script.json"
        if not script_path.exists():
            return preview
        with open(script_path, encoding="utf-8") as f:
            script = json.load(f)
        scenes = []
        hook = script.get("hook", {})
        if hook:
            scenes.append({
                "scene_id": hook.get("scene_id", "hook"),
                "label": "Hook",
                "text": hook.get("text", hook.get("narration", "")),
                "visual_prompt": hook.get("visual_prompt", ""),
            })
        for act in script.get("acts", []):
            for scene in act.get("scenes", []):
                scenes.append({
                    "scene_id": scene.get("scene_id", ""),
                    "label": scene.get("scene_id", "").replace("_", " "),
                    "text": scene.get("narration", scene.get("text", "")),
                    "visual_prompt": scene.get("visual_prompt", ""),
                })
        outro = script.get("outro", {})
        if outro:
            scenes.append({
                "scene_id": outro.get("scene_id", "outro"),
                "label": "Outro",
                "text": outro.get("text", outro.get("narration", "")),
                "visual_prompt": outro.get("visual_prompt", ""),
            })
        preview["title"] = script.get("title", "")
        preview["description"] = script.get("description", "")
        preview["tags"] = script.get("tags", [])
        preview["scenes"] = scenes
        preview["script"] = script
        preview["has_content"] = bool(scenes)
        return preview

    if stage == "images":
        preview["fallbacks"] = step_info.get("data", {}).get("fallbacks", {})
        preview["placeholder_count"] = step_info.get("data", {}).get("placeholder_count", 0)
        images_dir = job_dir / "images"
        if images_dir.is_dir():
            for path in sorted(images_dir.glob("*.png")):
                preview["assets"].append({
                    "type": "image",
                    "label": path.stem.replace("_", " "),
                    "url": _job_output_url(niche_id, job_id, f"images/{path.name}"),
                })

    elif stage == "thumbnail":
        for name in ("thumbnail.png", "thumbnail_bg.png"):
            if (job_dir / name).exists():
                preview["assets"].append({
                    "type": "image",
                    "label": name.replace(".png", "").replace("_", " "),
                    "url": _job_output_url(niche_id, job_id, name),
                })

    elif stage == "audio":
        audio_dir = job_dir / "audio"
        if audio_dir.is_dir():
            for path in sorted(audio_dir.glob("*.wav")):
                preview["assets"].append({
                    "type": "audio",
                    "label": path.stem.replace("_", " "),
                    "url": _job_output_url(niche_id, job_id, f"audio/{path.name}"),
                })

    elif stage == "assembly":
        for name in ("final_video.mp4", "with_intro_outro.mp4", "concat.mp4"):
            if (job_dir / name).exists():
                preview["assets"].append({
                    "type": "video",
                    "label": name.replace(".mp4", "").replace("_", " "),
                    "url": _job_output_url(niche_id, job_id, name),
                    "primary": name == "final_video.mp4",
                })
        scenes_dir = job_dir / "scenes"
        if scenes_dir.is_dir():
            for path in sorted(scenes_dir.glob("*.mp4")):
                preview["assets"].append({
                    "type": "video",
                    "label": f"scene: {path.stem}",
                    "url": _job_output_url(niche_id, job_id, f"scenes/{path.name}"),
                })

    preview["has_content"] = bool(preview["assets"])
    return preview


async def complete_human_recording(
    job_id: str,
    niche_id: str,
    audio_paths: dict,
) -> dict:
    job_dir = find_job_dir(job_id) or (OUTPUT_BASE / niche_id / job_id)
    status = get_job_status(job_id)
    audio_step = status.get("steps", {}).get("audio", {}).get("data", {})

    script_path = job_dir / "script_approved.json"
    if not script_path.exists():
        script_path = job_dir / "script.json"
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    image_paths = audio_step.get("image_paths", {})
    processed: dict[str, str] = {}
    audio_dir = job_dir / "audio_human"
    audio_dir.mkdir(exist_ok=True)

    for scene_id, path in audio_paths.items():
        norm = audio_dir / f"{scene_id}_norm.wav"
        clean = audio_dir / f"{scene_id}_clean.wav"
        normalize_audio(path, str(norm))
        reduce_noise(str(norm), str(clean))
        processed[scene_id] = str(clean)

    channel = load_channel(niche_id)
    status = get_job_status(job_id)
    image_layout = _image_layout_from_status(status)
    update_job(job_id, "assembly", "running", niche_id=niche_id)
    final_path = assemble_video(
        script, image_paths, processed, channel, job_dir, niche_id,
        image_layout=image_layout,
    )
    update_job(job_id, "assembly", "complete", {"output_path": str(final_path)}, niche_id=niche_id)
    update_job(job_id, "complete", "complete", {"output_path": str(final_path)}, niche_id=niche_id)

    return {
        "job_id": job_id,
        "status": "complete",
        "output_path": str(final_path),
    }
