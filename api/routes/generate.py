"""Video generation routes."""

import copy
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from lib.script_schema import FORMAT_SECTIONS, SCRIPT_TEMPLATE, normalize_script, parse_script_json, validate_script
from lib.config import OUTPUT_BASE
from lib.content_json import list_script_files, load_script_file
from lib.script import generate_video_script, refine_script_section
from lib.thumbnail import generate_thumbnail
from lib.image_style import VALID_IMAGE_LAYOUTS, VALID_VISUAL_STYLES, normalize_image_layout
from pipeline.channel_loader import load_channel
from pipeline.generator import (
    complete_human_recording,
    continue_after_approval,
    continue_after_image_upload,
    get_assets_status,
    get_resume_info,
    get_stage_preview,
    ingest_manual_script,
    prepare_video_job,
    regenerate_stage,
    remove_job,
    save_script,
    save_uploaded_scene_image,
    run_resume_job,
    run_resume_job_async,
    run_script_generation,
    save_json,
)
from pipeline.status_tracker import find_job_dir, get_job_status, list_jobs

router = APIRouter()


class GenerateVideoRequest(BaseModel):
    topic: str
    niche_id: str
    duration_minutes: int = 10
    audio_mode: str = "ai"
    voice: str | None = None
    speed: float = 0.85
    script_mode: str = "ai"
    image_mode: str = "ai"
    image_layout: str = "one_image"
    visual_style: str | None = None
    sfx_mode: str = "local"
    script: dict | None = None


class ScriptRequest(BaseModel):
    topic: str
    niche_id: str
    duration_minutes: int = 10


class ThumbnailRequest(BaseModel):
    title: str
    niche_id: str
    job_id: str | None = None


class ApproveScriptRequest(BaseModel):
    job_id: str
    niche_id: str
    edited_script: dict
    audio_mode: str = "ai"
    voice: str | None = None
    speed: float = 0.85
    image_mode: str | None = None
    image_layout: str | None = None
    visual_style: str | None = None


class ValidateScriptRequest(BaseModel):
    script: dict
    niche_id: str | None = None
    humanize: bool = False


class ManualScriptRequest(BaseModel):
    job_id: str
    niche_id: str
    script: dict


class RegenerateSceneRequest(BaseModel):
    job_id: str
    niche_id: str
    scene_id: str
    instruction: str


class RegenerateFullRequest(BaseModel):
    job_id: str
    niche_id: str
    topic: str
    instruction: str | None = None
    duration_minutes: int = 10


class CompleteRecordingRequest(BaseModel):
    job_id: str
    niche_id: str
    audio_paths: dict


class ResumeJobRequest(BaseModel):
    job_id: str
    niche_id: str | None = None


class RegenerateStageRequest(BaseModel):
    job_id: str
    stage: str
    niche_id: str | None = None


class SaveScriptRequest(BaseModel):
    edited_script: dict


class DeleteJobRequest(BaseModel):
    job_id: str


class ParticleRequest(BaseModel):
    video_path: str
    output_path: str
    particle_type: str = "dust"


@router.get("/script-template")
async def script_template():
    return {
        "template": SCRIPT_TEMPLATE,
        "sections": FORMAT_SECTIONS,
        "scene_id_convention": "hook, act1_scene1, act2_scene1, ..., outro",
    }


@router.get("/content-json")
async def list_content_json_scripts():
    return {"scripts": list_script_files()}


@router.get("/content-json/{filename}")
async def get_content_json_script(filename: str):
    try:
        script = load_script_file(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    ok, errors = validate_script(script)
    return {
        "filename": filename if filename.endswith(".json") else f"{filename}.json",
        "valid": ok,
        "errors": errors,
        "script": script,
    }


@router.post("/script/validate")
async def validate_script_route(req: ValidateScriptRequest):
    ok, errors = validate_script(req.script)
    if not ok:
        return {"valid": False, "errors": errors}
    channel = None
    if req.humanize and req.niche_id:
        try:
            channel = load_channel(req.niche_id)
        except FileNotFoundError:
            pass
    normalized = normalize_script(
        req.script,
        humanize=req.humanize,
        channel_config=channel,
    )
    return {"valid": True, "script": normalized}


@router.post("/video")
async def start_video_generation(req: GenerateVideoRequest, background_tasks: BackgroundTasks):
    try:
        load_channel(req.niche_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Channel not found: {req.niche_id}")

    if req.script_mode not in ("ai", "manual"):
        raise HTTPException(status_code=400, detail="script_mode must be ai or manual")
    if req.image_mode not in ("ai", "upload"):
        raise HTTPException(status_code=400, detail="image_mode must be ai or upload")
    if normalize_image_layout(req.image_layout) not in VALID_IMAGE_LAYOUTS:
        raise HTTPException(
            status_code=400,
            detail="image_layout must be one_image, per_scene, multiple, or single (legacy)",
        )
    if req.visual_style and req.visual_style not in VALID_VISUAL_STYLES:
        raise HTTPException(status_code=400, detail="visual_style must be realistic or cartoon")
    if req.sfx_mode not in ("local", "off"):
        raise HTTPException(status_code=400, detail="sfx_mode must be local or off")

    job_id, reused = prepare_video_job(
        topic=req.topic,
        niche_id=req.niche_id,
        duration_minutes=req.duration_minutes,
        audio_mode=req.audio_mode,
        voice=req.voice,
        speed=req.speed,
        script_mode=req.script_mode,
        image_mode=req.image_mode,
        image_layout=req.image_layout,
        visual_style=req.visual_style,
        sfx_mode=req.sfx_mode,
    )

    if req.script_mode == "manual":
        if not req.script:
            return {
                "job_id": job_id,
                "status": "awaiting_manual_script",
                "reused": reused,
                "manual_script_url": f"/ui/manual-script.html?job_id={job_id}&niche_id={req.niche_id}",
            }
        try:
            ingest_manual_script(
                job_id,
                req.niche_id,
                req.script,
                req.topic,
                req.duration_minutes,
                req.audio_mode,
                req.voice,
                req.speed,
                req.image_mode,
                req.image_layout,
                req.visual_style,
                req.sfx_mode,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {
            "job_id": job_id,
            "status": "pending_script_review",
            "reused": reused,
            "review_url": f"/ui/review.html?job_id={job_id}",
        }

    background_tasks.add_task(
        run_script_generation,
        job_id,
        req.topic,
        req.niche_id,
        req.duration_minutes,
        req.audio_mode,
        req.voice,
        req.speed,
    )
    return {
        "job_id": job_id,
        "status": "script_generating",
        "reused": reused,
        "message": "Updated existing job for this topic" if reused else "Created new job",
    }


@router.post("/manual-script")
async def save_manual_script(req: ManualScriptRequest):
    try:
        status = get_job_status(req.job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {req.job_id}")

    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    try:
        ingest_manual_script(
            req.job_id,
            req.niche_id,
            req.script,
            status.get("topic", ""),
            script_data.get("duration_minutes", 10),
            script_data.get("audio_mode", status.get("audio_mode", "ai")),
            script_data.get("voice"),
            script_data.get("speed", 0.85),
            script_data.get("image_mode", "ai"),
            script_data.get("image_layout", "one_image"),
            script_data.get("visual_style"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "job_id": req.job_id,
        "status": "pending_script_review",
        "review_url": f"/ui/review.html?job_id={req.job_id}",
    }


@router.get("/script-review/{job_id}")
async def get_script_for_review(job_id: str):
    job_dir = find_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    script_path = job_dir / "script.json"
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    status = get_job_status(job_id)
    return {"job_id": job_id, "niche_id": status.get("niche_id"), "script": script, "status": status}


@router.post("/script-review/approve")
async def approve_script(req: ApproveScriptRequest, background_tasks: BackgroundTasks):
    job_dir = OUTPUT_BASE / req.niche_id / req.job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job not found: {req.job_id}")

    save_json(job_dir / "script_approved.json", req.edited_script)
    status = get_job_status(req.job_id)
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    image_mode = req.image_mode or script_data.get("image_mode", "ai")
    image_layout = req.image_layout or script_data.get("image_layout", "one_image")
    visual_style = req.visual_style or script_data.get("visual_style")
    update_job_meta = {
        "image_mode": image_mode,
        "image_layout": normalize_image_layout(image_layout),
        "visual_style": visual_style,
    }
    from pipeline.status_tracker import update_job
    update_job(
        req.job_id, "script", "approved",
        {**script_data, **update_job_meta},
        niche_id=req.niche_id,
    )
    background_tasks.add_task(
        continue_after_approval,
        req.job_id,
        req.niche_id,
        req.edited_script,
        req.audio_mode,
        req.voice,
        req.speed,
        "images",
        image_mode,
        image_layout,
        visual_style,
    )
    return {"job_id": req.job_id, "status": "generating"}


@router.post("/script-review/regenerate-scene")
async def regenerate_scene(req: RegenerateSceneRequest):
    job_dir = OUTPUT_BASE / req.niche_id / req.job_id
    script_path = job_dir / "script.json"
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    channel = load_channel(req.niche_id)

    def _bookend(section: str) -> dict:
        if section not in script or not isinstance(script.get(section), dict):
            script[section] = copy.deepcopy(SCRIPT_TEMPLATE[section])
        return script[section]

    narration = None
    text_field = "text"
    target = None

    if req.scene_id == "hook":
        target = _bookend("hook")
        narration = target.get("text", "")
    elif req.scene_id == "outro":
        target = _bookend("outro")
        narration = target.get("text", "")
    else:
        text_field = "narration"
        for act in script.get("acts", []):
            for scene in act.get("scenes", []):
                if scene.get("scene_id") == req.scene_id:
                    target = scene
                    narration = scene.get("narration", "")
                    break
            if target is not None:
                break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Scene not found: {req.scene_id}")

    new_narration = refine_script_section(narration, req.instruction, channel)
    target[text_field] = new_narration

    save_json(script_path, script)
    return {"scene_id": req.scene_id, "new_narration": new_narration}


@router.post("/script-review/regenerate-full")
async def regenerate_full_script(req: RegenerateFullRequest):
    channel = load_channel(req.niche_id)
    status = get_job_status(req.job_id)
    sfx_mode = status.get("steps", {}).get("script", {}).get("data", {}).get("sfx_mode", "local")
    image_layout = status.get("steps", {}).get("script", {}).get("data", {}).get("image_layout", "one_image")
    script = generate_video_script(
        req.topic, channel, req.duration_minutes,
        extra_instruction=req.instruction,
        sfx_mode=sfx_mode,
        image_layout=image_layout,
    )
    job_dir = OUTPUT_BASE / req.niche_id / req.job_id
    save_json(job_dir / "script.json", script)
    return script


@router.post("/script-only")
async def script_only(req: ScriptRequest):
    channel = load_channel(req.niche_id)
    script = generate_video_script(req.topic, channel, req.duration_minutes)
    return script


@router.post("/thumbnail")
async def generate_thumbnail_route(req: ThumbnailRequest):
    channel = load_channel(req.niche_id)
    if req.job_id:
        out = OUTPUT_BASE / req.niche_id / req.job_id / "thumbnail.png"
    else:
        out = OUTPUT_BASE / req.niche_id / "standalone_thumbnail.png"
    path = generate_thumbnail(req.title, channel, str(out))
    return {"thumbnail_path": path}


@router.get("/stage/{job_id}/{stage}")
async def stage_preview(job_id: str, stage: str):
    try:
        return get_stage_preview(job_id, stage)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/script/{job_id}")
async def save_script_route(job_id: str, req: SaveScriptRequest):
    try:
        return save_script(job_id, req.edited_script)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/resume/{job_id}")
async def resume_info(job_id: str):
    try:
        return get_resume_info(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/resume")
async def resume_job_route(req: ResumeJobRequest, background_tasks: BackgroundTasks):
    try:
        info = get_resume_info(req.job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    resume_step = info["resume_step"]
    if resume_step == "done":
        return {**info, "status": "complete"}
    if resume_step == "review":
        return {
            **info,
            "status": "pending_review",
            "review_url": f"/ui/review.html?job_id={req.job_id}",
        }
    if resume_step == "human_recording":
        return {
            **info,
            "status": "waiting_for_human_voiceover",
            "recorder_url": f"/ui/recorder.html?job_id={req.job_id}&mode=human",
        }
    if resume_step == "hybrid_recording":
        return {
            **info,
            "status": "waiting_for_hybrid_review",
            "recorder_url": f"/ui/recorder.html?job_id={req.job_id}&mode=hybrid",
        }
    if not info["can_resume"]:
        raise HTTPException(status_code=400, detail=info["message"])

    if resume_step == "script":
        background_tasks.add_task(run_resume_job, req.job_id, req.niche_id)
    else:
        background_tasks.add_task(run_resume_job_async, req.job_id, req.niche_id)

    return {**info, "status": "resuming"}


@router.post("/regenerate")
async def regenerate_stage_route(req: RegenerateStageRequest, background_tasks: BackgroundTasks):
    try:
        get_job_status(req.job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {req.job_id}")

    valid_stages = {"script", "images", "thumbnail", "audio", "assembly"}
    if req.stage not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage. Must be one of: {', '.join(sorted(valid_stages))}",
        )

    background_tasks.add_task(_run_regenerate_background, req.job_id, req.stage, req.niche_id)

    return {
        "job_id": req.job_id,
        "status": "regenerating",
        "stage": req.stage,
        "message": f"Regenerating from {req.stage}",
    }


async def _run_regenerate_background(job_id: str, stage: str, niche_id: str | None) -> None:
    from pipeline.status_tracker import update_job

    try:
        await regenerate_stage(job_id, stage, niche_id)
    except Exception as e:
        try:
            status = get_job_status(job_id)
            update_job(job_id, stage, "error", {"error": str(e)}, niche_id=status.get("niche_id"))
        except FileNotFoundError:
            pass


@router.delete("/job/{job_id}")
async def delete_job_route(job_id: str):
    try:
        remove_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"job_id": job_id, "status": "deleted"}


@router.get("/jobs")
async def list_all_jobs(niche_id: str | None = None, dedupe: bool = True):
    return {"jobs": list_jobs(niche_id, dedupe_topics=dedupe)}


@router.post("/complete-human-recording")
async def complete_recording(req: CompleteRecordingRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        complete_human_recording, req.job_id, req.niche_id, req.audio_paths
    )
    return {"job_id": req.job_id, "status": "assembling"}


@router.get("/assets/{job_id}")
async def assets_status(job_id: str):
    try:
        return get_assets_status(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/assets/{job_id}/upload")
async def upload_asset(
    job_id: str,
    scene_id: str = Form(...),
    asset_type: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        data = await file.read()
        return save_uploaded_scene_image(job_id, scene_id, asset_type, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/assets/{job_id}/continue")
async def continue_after_upload(job_id: str, background_tasks: BackgroundTasks):
    try:
        status = get_job_status(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    niche_id = status.get("niche_id", "")
    script_data = status.get("steps", {}).get("script", {}).get("data", {})
    background_tasks.add_task(
        continue_after_image_upload,
        job_id,
        niche_id,
        status.get("audio_mode", "ai"),
        script_data.get("voice"),
        script_data.get("speed", 0.85),
    )
    return {"job_id": job_id, "status": "generating"}


@router.post("/add-particle")
async def add_particle(req: ParticleRequest):
    from lib.motion import add_particle_overlay

    path = add_particle_overlay(req.video_path, req.output_path, req.particle_type)
    return {"success": True, "path": path}
