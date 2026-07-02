"""Script template, validation, and normalization for manual entry."""

from __future__ import annotations

import copy
import json
import re

SCRIPT_TEMPLATE: dict = {
    "title": "Your Video Title",
    "title_variations": ["Alt Title 1", "Alt Title 2", "Alt Title 3"],
    "description": "SEO-optimized YouTube description (~150 words).",
    "tags": ["tag1", "tag2", "tag3"],
    "hook": {
        "scene_id": "hook",
        "text": "Hook narration (0:00–0:45). Use [pause] [slow] [emphasis] markers.",
        "visual_prompt": "Cinematic scene description — no text in image",
        "broll_prompt": "B-roll scene description — no text in image",
        "duration_seconds": 45,
    },
    "acts": [
        {
            "act_number": 1,
            "act_title": "The Problem",
            "scenes": [
                {
                    "scene_id": "act1_scene1",
                    "narration": "Act 1 scene narration...",
                    "visual_prompt": "Scene visual — no text",
                    "broll_prompt": "B-roll visual — no text",
                    "duration_seconds": 30,
                    "emotion": "tension",
                },
            ],
        },
        {
            "act_number": 2,
            "act_title": "The Truth",
            "scenes": [
                {
                    "scene_id": "act2_scene1",
                    "narration": "...",
                    "visual_prompt": "...",
                    "broll_prompt": "...",
                    "duration_seconds": 30,
                    "emotion": "revelation",
                },
            ],
        },
        {
            "act_number": 3,
            "act_title": "The Takeaway",
            "scenes": [
                {
                    "scene_id": "act3_scene1",
                    "narration": "...",
                    "visual_prompt": "...",
                    "broll_prompt": "...",
                    "duration_seconds": 30,
                    "emotion": "resolution",
                },
            ],
        },
    ],
    "outro": {
        "scene_id": "outro",
        "text": "Outro narration with subscribe CTA.",
        "visual_prompt": "Outro scene — no text",
        "duration_seconds": 30,
    },
}

FORMAT_SECTIONS = [
    {"id": "outline", "title": "Outline", "fields": "title, title_variations, description, tags"},
    {"id": "hook", "title": "Hook", "fields": "text, visual_prompt, broll_prompt, duration_seconds"},
    {"id": "act1", "title": "Act 1", "fields": "act_title + scenes (scene_id, narration, visual_prompt, broll_prompt)"},
    {"id": "act2", "title": "Act 2", "fields": "same as Act 1"},
    {"id": "act3", "title": "Act 3", "fields": "same as Act 1"},
    {"id": "outro", "title": "Outro", "fields": "text, visual_prompt, duration_seconds"},
]


def validate_script(script: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(script, dict):
        return False, ["Script must be a JSON object"]

    if not str(script.get("title", "")).strip():
        errors.append("Missing title")
    if not str(script.get("description", "")).strip():
        errors.append("Missing description")
    tags = script.get("tags", [])
    if not tags or not isinstance(tags, list):
        errors.append("tags must be a non-empty list")

    hook = script.get("hook")
    if not hook or not isinstance(hook, dict):
        errors.append("Missing hook object")
    elif not str(hook.get("text", "")).strip():
        errors.append("Hook text is required")

    acts = script.get("acts", [])
    if not acts or not isinstance(acts, list):
        errors.append("acts must be a non-empty list")
    else:
        for i, act in enumerate(acts):
            scenes = act.get("scenes", [])
            if not scenes:
                errors.append(f"Act {i + 1} has no scenes")
            for scene in scenes:
                sid = scene.get("scene_id", "")
                if not sid:
                    errors.append(f"Act {i + 1} has a scene without scene_id")
                narration = scene.get("narration", scene.get("text", ""))
                if not str(narration).strip():
                    errors.append(f"Scene {sid or '?'} missing narration")

    outro = script.get("outro")
    if not outro or not isinstance(outro, dict):
        errors.append("Missing outro object")
    elif not str(outro.get("text", "")).strip():
        errors.append("Outro text is required")

    scene_ids: list[str] = []
    if hook and hook.get("scene_id"):
        scene_ids.append(hook["scene_id"])
    for act in acts:
        for scene in act.get("scenes", []):
            if scene.get("scene_id"):
                scene_ids.append(scene["scene_id"])
    if outro and outro.get("scene_id"):
        scene_ids.append(outro["scene_id"])

    if len(scene_ids) != len(set(scene_ids)):
        errors.append("Duplicate scene_id values found")

    return len(errors) == 0, errors


def normalize_script(script: dict, *, humanize: bool = False) -> dict:
    from lib.script import _ensure_scene_ids, apply_humanization

    out = copy.deepcopy(script)

    if "hook" in out:
        out["hook"].setdefault("scene_id", "hook")
        out["hook"].setdefault("duration_seconds", 45)
        out["hook"].setdefault("visual_prompt", "cinematic scene")
        out["hook"].setdefault("broll_prompt", out["hook"]["visual_prompt"])
    if "outro" in out:
        out["outro"].setdefault("scene_id", "outro")
        out["outro"].setdefault("duration_seconds", 30)
        out["outro"].setdefault("visual_prompt", "cinematic outro scene")

    for act in out.get("acts", []):
        act.setdefault("act_number", 1)
        for i, scene in enumerate(act.get("scenes", [])):
            scene.setdefault("scene_id", f"act{act['act_number']}_scene{i + 1}")
            scene.setdefault("duration_seconds", 30)
            scene.setdefault("visual_prompt", "cinematic scene")
            scene.setdefault("broll_prompt", scene["visual_prompt"])
            scene.setdefault("emotion", "neutral")
            if "narration" not in scene and "text" in scene:
                scene["narration"] = scene["text"]

    out.setdefault("title_variations", [out.get("title", "")])
    out = _ensure_scene_ids(out)

    if humanize:
        rules: list = []
        if "hook" in out and "text" in out["hook"]:
            out["hook"]["text"] = apply_humanization(out["hook"]["text"], rules)
        for act in out.get("acts", []):
            for scene in act.get("scenes", []):
                if "narration" in scene:
                    scene["narration"] = apply_humanization(scene["narration"], rules)
        if "outro" in out and "text" in out["outro"]:
            out["outro"]["text"] = apply_humanization(out["outro"]["text"], rules)

    scenes_count = 1 + sum(len(a.get("scenes", [])) for a in out.get("acts", [])) + 1
    out["total_scenes"] = scenes_count
    if "total_duration_seconds" not in out:
        total = out.get("hook", {}).get("duration_seconds", 45)
        for act in out.get("acts", []):
            for scene in act.get("scenes", []):
                total += scene.get("duration_seconds", 30)
        total += out.get("outro", {}).get("duration_seconds", 30)
        out["total_duration_seconds"] = total

    return out


def parse_script_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)
