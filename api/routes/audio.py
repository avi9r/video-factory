"""Audio and recording routes."""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
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
from pipeline.channel_loader import load_channel

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
    channel = load_channel(req.niche_id)
    preview_dir = OUTPUT_BASE / "previews"
    preview_dir.mkdir(exist_ok=True)
    out_path = preview_dir / f"preview_{uuid.uuid4().hex[:8]}.wav"
    generate_scene_voiceover(req.text, channel, str(out_path), voice=req.voice, speed=req.speed)
    return FileResponse(str(out_path), media_type="audio/wav", filename="preview.wav")
