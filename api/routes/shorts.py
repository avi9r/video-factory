"""Shorts / Reels generation routes."""

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from lib.config import SHORT_DURATIONS
from pipeline.channel_loader import list_short_channels, load_short_channel
from pipeline.short_generator import (
    approve_short_script,
    prepare_short_job,
    run_short_pipeline,
)
from pipeline.status_tracker import get_job_status

router = APIRouter()


@router.get("/channels")
async def short_channels():
    return {"channels": list_short_channels()}


@router.get("/channels/{niche_id}")
async def short_channel(niche_id: str):
    try:
        return load_short_channel(niche_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Short channel not found: {niche_id}")


@router.post("")
async def generate_short(
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    niche_id: str = Form(...),
    duration_seconds: int = Form(60),
    voice: str | None = Form(None),
    speed: float | None = Form(None),
    reuse_image: str = Form("true"),
    auto_approve: str = Form("true"),
    hook_style: str | None = Form(None),
    quiet_music: str = Form("false"),
    image: UploadFile | None = File(None),
):
    if duration_seconds not in SHORT_DURATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"duration_seconds must be one of {list(SHORT_DURATIONS)}",
        )
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    def _truthy(val: str) -> bool:
        return str(val).strip().lower() in {"1", "true", "yes", "on"}

    try:
        channel = load_short_channel(niche_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Short channel not found: {niche_id}")

    research_cfg = channel.get("research") or {}
    image_optional = bool(research_cfg.get("image_optional") or research_cfg.get("auto_chart"))

    data = None
    filename = None
    if image is not None and image.filename:
        data = await image.read()
        filename = image.filename
        if not data:
            raise HTTPException(status_code=400, detail="image file is empty")
    elif not image_optional:
        raise HTTPException(status_code=400, detail="image is required")

    try:
        job_id = prepare_short_job(
            prompt=prompt.strip(),
            niche_id=niche_id,
            duration_seconds=duration_seconds,
            voice=voice,
            speed=speed,
            reuse_image=_truthy(reuse_image),
            auto_approve=_truthy(auto_approve),
            hook_style=hook_style,
            quiet_music=_truthy(quiet_music),
            image_bytes=data,
            image_filename=filename,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(run_short_pipeline, job_id, niche_id)
    return {
        "job_id": job_id,
        "niche_id": niche_id,
        "job_kind": "short",
        "duration_seconds": duration_seconds,
        "research_type": research_cfg.get("type"),
        "status_url": f"/status/{job_id}",
    }


@router.post("/approve")
async def approve_short(background_tasks: BackgroundTasks, payload: dict):
    job_id = payload.get("job_id")
    niche_id = payload.get("niche_id")
    if not job_id or not niche_id:
        raise HTTPException(status_code=400, detail="job_id and niche_id required")
    edited = payload.get("edited_script")

    def _run():
        try:
            approve_short_script(job_id, niche_id, edited)
        except Exception as e:
            from pipeline.status_tracker import update_job

            update_job(job_id, "assembly", "error", {"error": str(e)}, niche_id=niche_id)

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "continuing"}


@router.get("/{job_id}")
async def short_status(job_id: str):
    try:
        return get_job_status(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
