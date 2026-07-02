"""Channel configuration routes."""

from fastapi import APIRouter, HTTPException

from pipeline.channel_loader import load_channel, list_channels, validate_channel_config

router = APIRouter()


@router.get("/list")
async def get_channels():
    return {"channels": list_channels()}


@router.get("/{niche_id}")
async def get_channel(niche_id: str):
    try:
        return load_channel(niche_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Channel not found: {niche_id}")


@router.post("/validate/{niche_id}")
async def validate_channel(niche_id: str):
    try:
        config = load_channel(niche_id)
        validate_channel_config(config)
        return {"valid": True, "niche_id": niche_id}
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
