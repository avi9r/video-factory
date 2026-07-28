"""Load and list video scripts saved under content_json/."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from lib.config import CONTENT_JSON_BASE


def slugify_topic(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", topic.strip().lower())
    return slug.strip("_")[:80] or "script"


def content_json_dir() -> Path:
    path = CONTENT_JSON_BASE
    path.mkdir(parents=True, exist_ok=True)
    return path


def script_path_for_topic(topic: str) -> Path:
    return content_json_dir() / f"{slugify_topic(topic)}.json"


def list_script_files() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(content_json_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            title = str(data.get("title") or path.stem.replace("_", " "))
        except (json.JSONDecodeError, OSError):
            title = path.stem.replace("_", " ")
        stat = path.stat()
        rows.append(
            {
                "filename": path.name,
                "title": title,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )
    return rows


def load_script_file(filename: str) -> dict:
    if not filename.endswith(".json"):
        filename = f"{filename}.json"
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise ValueError("Invalid filename")
    path = content_json_dir() / filename
    if not path.is_file():
        raise FileNotFoundError(f"Script not found: {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_script_file(script: dict, *, topic: str | None = None, filename: str | None = None) -> Path:
    if filename:
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        if "/" in filename or "\\" in filename:
            raise ValueError("Invalid filename")
        path = content_json_dir() / filename
    else:
        name = script.get("title") or topic or "script"
        path = script_path_for_topic(str(name))
    path.write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
