"""Job status routes."""

from fastapi import APIRouter, HTTPException, Query

from pipeline.status_tracker import get_job_status, list_jobs

router = APIRouter()


@router.get("/list")
async def all_jobs(
    niche_id: str | None = Query(None),
    dedupe: bool = Query(True),
):
    return {"jobs": list_jobs(niche_id, dedupe_topics=dedupe)}


@router.get("/{job_id}")
async def job_status(job_id: str):
    try:
        return get_job_status(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")


@router.get("/list/{niche_id}")
async def jobs_for_niche(niche_id: str, dedupe: bool = Query(True)):
    return {"jobs": list_jobs(niche_id, dedupe_topics=dedupe)}
