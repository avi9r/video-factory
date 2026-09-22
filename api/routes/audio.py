"""Audio and recording routes."""

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from lib.audio import VOICES, generate_scene_voiceover
from lib.config import OUTPUT_BASE
from lib.recorder import (
    get_recording_status,
    list_input_devices,
    normalize_audio,
    record_section,
    stop_recording,
)
from pipeline.channel_loader import load_channel, load_short_channel
from pipeline.status_tracker import get_job_status

router = APIRouter()


class RecordRequest(BaseModel):
    job_id: str
    scene_id: str
    device_id: int | None = None


class StopRequest(BaseModel):
    job_id: str
    scene_id: str


class PreviewRequest(BaseModel):
    text: str
    voice: str = "default"
    speed: float = 0.85
    niche_id: str


class ChangeVoiceRequest(BaseModel):
    job_id: str
    niche_id: str | None = None
    voice: str
    speed: float | None = None


@router.get("/voices")
async def get_voices():
    return {"voices": list(VOICES.keys())}


@router.get("/devices")
async def get_devices():
    return {"devices": list_input_devices()}


@router.post("/record/start")
async def start_recording(req: RecordRequest):
    out_dir = OUTPUT_BASE / "recordings" / req.job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{req.scene_id}.wav"
    record_section(str(out_path), device_id=req.device_id)
    return {"recording": True, "scene_id": req.scene_id, "path": str(out_path)}


@router.post("/record/stop")
async def stop_recording_route(req: StopRequest):
    stop_recording()
    out_dir = OUTPUT_BASE / "recordings" / req.job_id
    raw_path = out_dir / f"{req.scene_id}.wav"
    norm_path = out_dir / f"{req.scene_id}_norm.wav"
    if raw_path.exists():
        normalize_audio(str(raw_path), str(norm_path))
        from lib.audio import get_audio_duration
        duration = get_audio_duration(str(norm_path))
        return {"path": str(norm_path), "duration": duration}
    raise HTTPException(status_code=404, detail="Recording not found")


@router.get("/record/status")
async def recording_status():
    return get_recording_status()


@router.post("/preview")
async def preview_voice(req: PreviewRequest):
    try:
        try:
            channel = load_short_channel(req.niche_id)
        except FileNotFoundError:
            channel = load_channel(req.niche_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Channel not found: {req.niche_id}")
    preview_dir = OUTPUT_BASE / "previews"
    preview_dir.mkdir(exist_ok=True)
    out_path = preview_dir / f"preview_{uuid.uuid4().hex[:8]}.wav"
    generate_scene_voiceover(req.text, channel, str(out_path), voice=req.voice, speed=req.speed)
    return FileResponse(str(out_path), media_type="audio/wav", filename="preview.wav")


@router.post("/change-voice")
async def change_voice(req: ChangeVoiceRequest, background_tasks: BackgroundTasks):
    """After a video is generated, re-run TTS + assembly with a different Kokoro voice."""
    if req.voice not in VOICES:
        raise HTTPException(status_code=400, detail=f"Unknown voice: {req.voice}")
    try:
        status = get_job_status(req.job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {req.job_id}")

    niche_id = req.niche_id or status.get("niche_id")
    if not niche_id:
        raise HTTPException(status_code=400, detail="niche_id required")

    is_short = status.get("job_kind") == "short" or "visuals" in (status.get("steps") or {})
    has_script = (status.get("steps") or {}).get("script", {}).get("status") in {
        "complete",
        "approved",
    }
    if not has_script:
        raise HTTPException(status_code=400, detail="Generate the video before changing voice")

    background_tasks.add_task(
        _run_change_voice,
        req.job_id,
        niche_id,
        req.voice,
        req.speed,
        is_short,
    )
    return {
        "job_id": req.job_id,
        "status": "changing_voice",
        "voice": req.voice,
        "speed": req.speed,
        "job_kind": "short" if is_short else "long",
        "message": "Re-generating voiceover and reassembling video",
    }


def _run_change_voice(
    job_id: str,
    niche_id: str,
    voice: str,
    speed: float | None,
    is_short: bool,
) -> None:
    from pipeline.status_tracker import update_job

    try:
        if is_short:
            from pipeline.short_generator import change_short_voice

            change_short_voice(job_id, niche_id, voice=voice, speed=speed)
        else:
            from pipeline.generator import change_long_voice

            change_long_voice(job_id, niche_id, voice=voice, speed=speed)
    except Exception as e:
        try:
            update_job(job_id, "audio", "error", {"error": str(e)}, niche_id=niche_id)
        except FileNotFoundError:
            pass
