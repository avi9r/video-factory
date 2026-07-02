"""Script generation and narration processing."""

import json
import re
from datetime import datetime

from lib.llm import chat_completion

DEFAULT_WRITING_RULES = [
    "Write like a sharp documentary narrator — curious, specific, never salesy.",
    "Open with a concrete fact, person, date, or dollar amount — not a generic question.",
    "Every act must advance ONE clear story thread with cause and effect.",
    "Name real companies, studies, economists, founders, or historical moments when relevant.",
    "Use short punchy sentences mixed with longer explanatory ones.",
    "Never use: 'In today's world', 'Let's dive in', 'Buckle up', 'game-changer', "
    "'At the end of the day', 'Here's the thing', 'mind-blowing', 'you won't believe'.",
    "Avoid hollow superlatives (shocking, incredible, amazing) unless tied to a specific fact.",
    "Visual prompts describe ONE clear frame — symbolic or literal — with no on-screen text.",
]


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] script: {msg}")


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _call_llm(system_prompt: str, user_prompt: str, *, max_tokens: int = 4096) -> str:
    return chat_completion(system_prompt, user_prompt, max_tokens=max_tokens)


def _build_system_prompt(channel_config: dict, extra_instruction: str | None = None) -> str:
    script_cfg = channel_config.get("script", {})
    parts = [script_cfg.get("system_prompt", "").strip()]
    rules = script_cfg.get("writing_rules", DEFAULT_WRITING_RULES)
    if rules:
        parts.append("\n\nWriting rules (follow strictly):\n" + "\n".join(f"- {r}" for r in rules))
    if extra_instruction:
        parts.append(f"\n\nAdditional instruction: {extra_instruction}")
    return "\n".join(p for p in parts if p)


def _outline_prompt(topic: str, duration_minutes: int) -> str:
    return f"""Plan a {duration_minutes}-minute YouTube video about: "{topic}"

Design a STORY, not a listicle. Pick one narrative spine (e.g. one company arc, one bias traced through real examples, one decision that changed an industry).

Return ONLY JSON:
{{
  "title": "specific compelling title (not clickbait)",
  "title_variations": ["alt1", "alt2", "alt3"],
  "description": "SEO YouTube description ~150 words",
  "tags": ["15 relevant tags"],
  "story_spine": "one sentence: the through-line of the whole video",
  "acts": [
    {{
      "act_number": 1,
      "act_title": "Act title",
      "scene_summaries": [
        {{"scene_id": "act1_scene1", "beat": "specific beat with names/dates/facts"}},
        {{"scene_id": "act1_scene2", "beat": "..."}},
        {{"scene_id": "act1_scene3", "beat": "..."}}
      ]
    }},
    {{"act_number": 2, "act_title": "...", "scene_summaries": [3-4 items with act2_sceneN ids]}},
    {{"act_number": 3, "act_title": "...", "scene_summaries": [3-4 items with act3_sceneN ids]}}
  ]
}}"""


def _hook_prompt(topic: str, outline: dict) -> str:
    spine = outline.get("story_spine", "")
    return f"""Write the hook for this video about "{topic}".

Title: {outline.get("title", topic)}
Story spine: {spine}

The hook must grab attention in the first 10 seconds with a SPECIFIC fact, moment, or paradox — not a vague question.
45 seconds max spoken. Include [pause] only where a human would naturally pause.

Return ONLY JSON:
{{
  "scene_id": "hook",
  "text": "hook narration",
  "visual_prompt": "one cinematic frame for this opening beat, no text in image",
  "broll_prompt": "optional cutaway, no text",
  "duration_seconds": 45
}}"""


def _act_prompt(topic: str, act: dict, outline: dict) -> str:
    summaries = json.dumps(act.get("scene_summaries", []), indent=2)
    act_num = act["act_number"]
    act_title = act.get("act_title", "")
    spine = outline.get("story_spine", "")
    return f"""Write Act {act_num} scenes for: "{topic}"
Act title: {act_title}
Story spine: {spine}

Expand these beats into spoken narration. Each scene = one idea. Use concrete examples.
Scene beats:
{summaries}

Return ONLY JSON:
{{
  "act_number": {act_num},
  "act_title": "{act_title}",
  "scenes": [
    {{
      "scene_id": "act{act_num}_scene1",
      "narration": "spoken words — natural, varied rhythm",
      "visual_prompt": "one clear scene, no text in image",
      "broll_prompt": "b-roll cutaway, no text",
      "duration_seconds": 30,
      "emotion": "tension"
    }}
  ]
}}"""


def _outro_prompt(topic: str, outline: dict) -> str:
    spine = outline.get("story_spine", "")
    return f"""Write the outro for this video about "{topic}".

Title: {outline.get("title", topic)}
Story spine: {spine}

Land the story — one insight the viewer takes away. No generic subscribe begging in the narration body.
30 seconds max.

Return ONLY JSON:
{{
  "scene_id": "outro",
  "text": "outro narration",
  "visual_prompt": "closing visual, no text in image",
  "duration_seconds": 30
}}"""


def apply_humanization(text: str, rules: list) -> str:
    """Apply light humanization markers to narration text."""
    if not text or not text.strip():
        return text

    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = []
    sentence_count = 0

    for i, sentence in enumerate(sentences):
        if not sentence.strip():
            continue

        sentence_count += 1

        if sentence_count % 5 == 0:
            result.append("[breath]")

        if sentence.strip().endswith("?"):
            sentence = f"{sentence} [pause]"

        if i == 0 and len(sentence.split()) > 12:
            sentence = f"{sentence} [pause]"

        result.append(sentence)

    return " ".join(result)


def clean_narration_for_tts(text: str) -> str:
    text = re.sub(r"\[pause\]", "...", text, flags=re.IGNORECASE)
    text = re.sub(r"\[breath\]", ",", text, flags=re.IGNORECASE)
    text = re.sub(r"\[(slow|fast|emphasis)\]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _ensure_scene_ids(script: dict) -> dict:
    if "hook" in script and "scene_id" not in script["hook"]:
        script["hook"]["scene_id"] = "hook"
    if "outro" in script and "scene_id" not in script["outro"]:
        script["outro"]["scene_id"] = "outro"
    for act in script.get("acts", []):
        for i, scene in enumerate(act.get("scenes", [])):
            if "scene_id" not in scene:
                scene["scene_id"] = f"act{act.get('act_number', 0)}_scene{i + 1}"
    return script


def _humanize_script(script: dict, rules: list) -> dict:
    if "hook" in script and "text" in script["hook"]:
        script["hook"]["text"] = apply_humanization(script["hook"]["text"], rules)
    for act in script.get("acts", []):
        for scene in act.get("scenes", []):
            if "narration" in scene:
                scene["narration"] = apply_humanization(scene["narration"], rules)
    if "outro" in script and "text" in script["outro"]:
        script["outro"]["text"] = apply_humanization(script["outro"]["text"], rules)
    return script


def generate_video_script(
    topic: str,
    channel_config: dict,
    duration_minutes: int = 10,
    extra_instruction: str | None = None,
) -> dict:
    """
    Generate script in multiple small LLM calls to stay within free-tier TPM limits.
    Typical flow: outline → hook → 3 acts → outro (6 calls).
    """
    _log(f"Generating script (chunked) for topic: {topic}")
    system_prompt = _build_system_prompt(channel_config, extra_instruction)

    outline_prompt = _outline_prompt(topic, duration_minutes)
    raw = _call_llm(system_prompt, outline_prompt, max_tokens=2048)
    outline = _parse_json_response(raw)
    _log("Outline complete")

    hook_raw = _call_llm(system_prompt, _hook_prompt(topic, outline), max_tokens=1024)
    hook = _parse_json_response(hook_raw)
    _log("Hook complete")

    acts = []
    for act_plan in outline.get("acts", []):
        act_raw = _call_llm(
            system_prompt, _act_prompt(topic, act_plan, outline), max_tokens=3072
        )
        acts.append(_parse_json_response(act_raw))
        _log(f"Act {act_plan.get('act_number')} complete")

    outro_raw = _call_llm(system_prompt, _outro_prompt(topic, outline), max_tokens=1024)
    outro = _parse_json_response(outro_raw)
    _log("Outro complete")

    total_scenes = 1 + sum(len(a.get("scenes", [])) for a in acts) + 1
    script = {
        "title": outline.get("title", topic),
        "title_variations": outline.get("title_variations", []),
        "description": outline.get("description", ""),
        "tags": outline.get("tags", []),
        "story_spine": outline.get("story_spine", ""),
        "hook": hook,
        "acts": acts,
        "outro": outro,
        "total_scenes": total_scenes,
        "total_duration_seconds": duration_minutes * 60,
    }

    if channel_config.get("script", {}).get("auto_humanize", False):
        rules = channel_config.get("script", {}).get("humanization_rules", [])
        script = _humanize_script(script, rules)

    script = _ensure_scene_ids(script)
    _log("Script generation complete")
    return script


def refine_script_section(
    section_text: str,
    instruction: str,
    channel_config: dict | None = None,
) -> str:
    _log(f"Refining section: {instruction[:50]}...")
    system = (
        _build_system_prompt(channel_config)
        if channel_config
        else "You are an expert YouTube scriptwriter."
    )
    user = f"""Refine this narration section according to the instruction.

Instruction: {instruction}

Original text:
{section_text}

Return ONLY the refined narration text. Keep it natural and specific — avoid AI clichés."""
    return _call_llm(system, user, max_tokens=1024).strip()
