#!/usr/bin/env python3
"""Validate a script JSON file from content_json/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.content_json import load_script_file  # noqa: E402
from lib.script_schema import normalize_script, validate_script  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_content_json.py <file.json>", file=sys.stderr)
        return 1

    arg = sys.argv[1]
    path = Path(arg)
    if path.is_file():
        script = json.loads(path.read_text(encoding="utf-8"))
        label = path.name
    else:
        script = load_script_file(arg)
        label = arg if arg.endswith(".json") else f"{arg}.json"

    ok, errors = validate_script(script)
    if not ok:
        print(f"INVALID {label}:")
        for err in errors:
            print(f"  - {err}")
        return 1

    normalized = normalize_script(script, humanize=False)
    scenes = normalized.get("total_scenes", "?")
    duration = normalized.get("total_duration_seconds", "?")
    print(f"OK {label} — {scenes} scenes, ~{duration}s total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
