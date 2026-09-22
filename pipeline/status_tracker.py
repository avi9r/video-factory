"""Persistent job status tracking."""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from lib.config import OUTPUT_BASE

ALL_STEPS = ("script", "images", "thumbnail", "audio", "assembly", "complete")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_topic(topic: str) -> str:
    """Canonical key for matching topics (one job per topic per channel)."""
    return re.sub(r"\s+", " ", topic.strip().lower())


def _job_dir(niche_id: str, job_id: str) -> Path:
    return OUTPUT_BASE / niche_id / job_id


def find_job_dir(job_id: str) -> Path | None:
    if not OUTPUT_BASE.exists():
        return None
    for niche_dir in OUTPUT_BASE.iterdir():
        if not niche_dir.is_dir():
            continue
        candidate = niche_dir / job_id
        if (candidate / "status.json").exists():
            return candidate
        # Shorts nest: output/shorts/{niche}/{job_id}
        if niche_dir.name == "shorts":
            for short_niche in niche_dir.iterdir():
                if not short_niche.is_dir():
                    continue
                candidate = short_niche / job_id
                if (candidate / "status.json").exists():
                    return candidate
    return None


def short_job_dir(niche_id: str, job_id: str) -> Path:
    return OUTPUT_BASE / "shorts" / niche_id / job_id


def create_short_job(job_id: str, niche_id: str, topic: str, audio_mode: str = "ai") -> dict:
    job_dir = short_job_dir(niche_id, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "job_id": job_id,
        "niche_id": niche_id,
        "topic": topic,
        "topic_key": normalize_topic(topic),
        "audio_mode": audio_mode,
        "job_kind": "short",
        "created_at": _now(),
        "updated_at": _now(),
        "overall_status": "created",
        "steps": {
            "script": {"status": "pending"},
            "visuals": {"status": "pending"},
            "audio": {"status": "pending"},
            "assembly": {"status": "pending"},
            "complete": {"status": "pending"},
        },
    }
    path = job_dir / "status.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)
    return job


def _status_path(niche_id: str, job_id: str) -> Path:
    return _job_dir(niche_id, job_id) / "status.json"


def create_job(job_id: str, niche_id: str, topic: str, audio_mode: str) -> dict:
    job_dir = _job_dir(niche_id, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "job_id": job_id,
        "niche_id": niche_id,
        "topic": topic,
        "topic_key": normalize_topic(topic),
        "audio_mode": audio_mode,
        "created_at": _now(),
        "updated_at": _now(),
        "overall_status": "created",
        "steps": {
            "script": {"status": "pending"},
            "images": {"status": "pending"},
            "thumbnail": {"status": "pending"},
            "audio": {"status": "pending"},
            "assembly": {"status": "pending"},
            "complete": {"status": "pending"},
        },
    }
    path = _status_path(niche_id, job_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)
    return job


def find_job_by_topic(niche_id: str, topic: str) -> dict | None:
    """Return the most recently updated job for this channel + topic."""
    key = normalize_topic(topic)
    matches = [
        j for j in list_jobs(niche_id)
        if normalize_topic(j.get("topic", "")) == key
        or j.get("topic_key") == key
    ]
    if not matches:
        return None
    matches.sort(key=lambda j: j.get("updated_at", ""), reverse=True)
    return matches[0]


def reset_job_from_step(job_id: str, from_step: str, niche_id: str | None = None) -> None:
    """Mark from_step and all downstream steps as pending."""
    if from_step not in ALL_STEPS:
        raise ValueError(f"Unknown step: {from_step}")

    job_dir = find_job_dir(job_id)
    if job_dir is None and niche_id:
        job_dir = _job_dir(niche_id, job_id)
    if job_dir is None or not (job_dir / "status.json").exists():
        raise FileNotFoundError(f"Job not found: {job_id}")

    path = job_dir / "status.json"
    with open(path, encoding="utf-8") as f:
        job = json.load(f)

    start = ALL_STEPS.index(from_step)
    for step in ALL_STEPS[start:]:
        job["steps"][step] = {"status": "pending"}
    job["updated_at"] = _now()
    job["overall_status"] = "generating"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)


def update_job_meta(
    job_id: str,
    niche_id: str,
    *,
    topic: str | None = None,
    audio_mode: str | None = None,
) -> None:
    job_dir = find_job_dir(job_id) or _job_dir(niche_id, job_id)
    path = job_dir / "status.json"
    with open(path, encoding="utf-8") as f:
        job = json.load(f)
    if topic is not None:
        job["topic"] = topic
        job["topic_key"] = normalize_topic(topic)
    if audio_mode is not None:
        job["audio_mode"] = audio_mode
    job["updated_at"] = _now()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)


def delete_job(job_id: str) -> None:
    job_dir = find_job_dir(job_id)
    if job_dir is None:
        raise FileNotFoundError(f"Job not found: {job_id}")
    shutil.rmtree(job_dir)


def update_job(
    job_id: str,
    step: str,
    status: str,
    data: dict | None = None,
    niche_id: str | None = None,
) -> None:
    job_dir = find_job_dir(job_id)
    if job_dir is None and niche_id:
        # Prefer short path if it exists (shorts live under output/shorts/)
        short_dir = short_job_dir(niche_id, job_id)
        if (short_dir / "status.json").exists():
            job_dir = short_dir
        else:
            job_dir = _job_dir(niche_id, job_id)
    if job_dir is None or not (job_dir / "status.json").exists():
        raise FileNotFoundError(f"Job not found: {job_id}")

    path = job_dir / "status.json"
    with open(path, encoding="utf-8") as f:
        job = json.load(f)

    if step not in job["steps"]:
        job["steps"][step] = {}
    job["steps"][step]["status"] = status
    job["steps"][step]["updated_at"] = _now()
    if data:
        job["steps"][step]["data"] = data
    job["updated_at"] = _now()
    if status == "error":
        job["overall_status"] = "error"
    elif status == "running":
        job["overall_status"] = "generating"
    elif step == "complete" and status == "complete":
        job["overall_status"] = "complete"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2)


def get_job_status(job_id: str) -> dict:
    job_dir = find_job_dir(job_id)
    if job_dir is None:
        raise FileNotFoundError(f"Job not found: {job_id}")
    with open(job_dir / "status.json", encoding="utf-8") as f:
        return json.load(f)


def list_jobs(niche_id: str | None = None, dedupe_topics: bool = False) -> list[dict]:
    jobs = []
    if not OUTPUT_BASE.exists():
        return jobs

    def _collect_from_niche_dir(niche_dir: Path) -> None:
        if not niche_dir.is_dir():
            return
        for job_dir in niche_dir.iterdir():
            status_file = job_dir / "status.json"
            if status_file.exists():
                with open(status_file, encoding="utf-8") as f:
                    job = json.load(f)
                if "topic_key" not in job and job.get("topic"):
                    job["topic_key"] = normalize_topic(job["topic"])
                jobs.append(job)

    if niche_id:
        _collect_from_niche_dir(OUTPUT_BASE / niche_id)
        _collect_from_niche_dir(OUTPUT_BASE / "shorts" / niche_id)
    else:
        for niche_dir in OUTPUT_BASE.iterdir():
            if not niche_dir.is_dir():
                continue
            if niche_dir.name == "shorts":
                for short_niche in niche_dir.iterdir():
                    _collect_from_niche_dir(short_niche)
            else:
                _collect_from_niche_dir(niche_dir)

    jobs.sort(key=lambda j: j.get("updated_at", ""), reverse=True)

    if not dedupe_topics:
        return jobs

    seen: set[str] = set()
    deduped: list[dict] = []
    for job in jobs:
        key = f"{job.get('niche_id')}:{job.get('topic_key') or normalize_topic(job.get('topic', ''))}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped
