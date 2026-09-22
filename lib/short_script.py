"""Short-form script generation for YouTube Shorts / Reels."""

from __future__ import annotations

import json
from datetime import datetime

from lib.script import (
    DEFAULT_WRITING_RULES,
    _call_llm_json,
    find_cliches,
    hook_has_specificity_anchor,
    word_count,
)

VALID_SHORT_DURATIONS = (30, 60, 90, 120)


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] short_script: {msg}")


def short_word_budget(duration_seconds: int) -> dict:
    """~135 wpm deliberate spoken delivery for more human pacing."""
    duration_seconds = int(duration_seconds)
    total = max(45, int(duration_seconds * 135 / 60))
    if duration_seconds <= 30:
        body_beats = 1
    elif duration_seconds <= 60:
        body_beats = 2
    elif duration_seconds <= 90:
        body_beats = 3
    else:
        body_beats = 4
    hook = max(16, int(total * 0.18))
    cta = max(10, int(total * 0.10))
    body = max(18, total - hook - cta)
    per_beat = max(18, body // body_beats)
    return {
        "total": total,
        "hook": hook,
        "cta": cta,
        "body_beats": body_beats,
        "per_beat": per_beat,
    }


def flatten_short_scenes(script: dict) -> list[dict]:
    """Normalize short script into ordered scene dicts for TTS/assembly."""
    scenes: list[dict] = []
    hook = script.get("hook") or {}
    if isinstance(hook, dict) and (hook.get("narration") or hook.get("text")):
        scenes.append({
            "scene_id": hook.get("scene_id", "hook"),
            "narration": hook.get("narration") or hook.get("text", ""),
            "text": hook.get("narration") or hook.get("text", ""),
            "visual_prompt": hook.get("visual_prompt", ""),
            "emotion": hook.get("emotion", "curiosity"),
            "narration_tone": hook.get("narration_tone", ""),
            "duration_seconds": hook.get("duration_seconds", 5),
            "kind": "hook",
        })
    for i, beat in enumerate(script.get("beats") or []):
        narr = beat.get("narration") or beat.get("text") or ""
        scenes.append({
            "scene_id": beat.get("scene_id", f"beat_{i + 1}"),
            "narration": narr,
            "text": narr,
            "visual_prompt": beat.get("visual_prompt", ""),
            "emotion": beat.get("emotion", "tension"),
            "narration_tone": beat.get("narration_tone", ""),
            "duration_seconds": beat.get("duration_seconds", 8),
            "kind": "beat",
        })
    cta = script.get("cta")
    if isinstance(cta, str) and cta.strip():
        scenes.append({
            "scene_id": "cta",
            "narration": cta,
            "text": cta,
            "visual_prompt": script.get("cta_visual_prompt", ""),
            "emotion": "resolve",
            "narration_tone": "warm closure",
            "duration_seconds": 4,
            "kind": "cta",
        })
    elif isinstance(cta, dict) and (cta.get("text") or cta.get("narration")):
        text = cta.get("narration") or cta.get("text", "")
        scenes.append({
            "scene_id": cta.get("scene_id", "cta"),
            "narration": text,
            "text": text,
            "visual_prompt": cta.get("visual_prompt", ""),
            "emotion": cta.get("emotion", "resolve"),
            "narration_tone": cta.get("narration_tone", "warm closure"),
            "duration_seconds": cta.get("duration_seconds", 4),
            "kind": "cta",
        })
    return scenes


def validate_short_script(script: dict, duration_seconds: int) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(script, dict):
        return False, ["Script must be an object"]
    if not str(script.get("title", "")).strip():
        errors.append("Missing title")
    hook = script.get("hook")
    if not isinstance(hook, dict) or not str(hook.get("narration") or hook.get("text") or "").strip():
        errors.append("Missing hook narration")
    else:
        hook_text = hook.get("narration") or hook.get("text") or ""
        if not hook_has_specificity_anchor(hook_text):
            errors.append("Hook must open with YEAR, $, or proper name")
        cliches = find_cliches(hook_text)
        if cliches:
            errors.append(f"Hook has clichés: {', '.join(cliches[:2])}")
    beats = script.get("beats") or []
    if not beats:
        errors.append("At least one body beat required")
    budgets = short_word_budget(duration_seconds)
    if len(beats) < budgets["body_beats"] - 1:
        errors.append(f"Expected ~{budgets['body_beats']} body beats for {duration_seconds}s")
    cta = script.get("cta")
    cta_text = cta if isinstance(cta, str) else (cta or {}).get("text") or (cta or {}).get("narration")
    if not str(cta_text or "").strip():
        errors.append("Missing CTA")
    return len(errors) == 0, errors


def _short_system_prompt(channel_config: dict, hook_style: str | None = None) -> str:
    script_cfg = channel_config.get("script", {})
    parts = [script_cfg.get("system_prompt", "").strip()]
    rules = script_cfg.get("writing_rules") or DEFAULT_WRITING_RULES[:6]
    parts.append("Writing rules:\n" + "\n".join(f"- {r}" for r in rules))
    parts.append(
        "You are writing a VERTICAL SHORT (9:16) meant to be SPOKEN aloud.\n"
        "Write for the ear, not the page. Short sentences. Contractions speech. "
        "No essay structure. No Act 1/2/3. Insert [pause] and [breath] where a human narrator would."
    )
    if hook_style:
        parts.append(f"Hook style preference: {hook_style}")
    cta = script_cfg.get("cta_text")
    if cta:
        parts.append(f"Default CTA line to adapt: {cta}")
    return "\n\n".join(p for p in parts if p)


def generate_short_script(
    prompt: str,
    channel_config: dict,
    duration_seconds: int = 60,
    hook_style: str | None = None,
    research_context: str | None = None,
) -> dict:
    if duration_seconds not in VALID_SHORT_DURATIONS:
        raise ValueError(f"duration_seconds must be one of {VALID_SHORT_DURATIONS}")

    budgets = short_word_budget(duration_seconds)
    system = _short_system_prompt(channel_config, hook_style)
    _log(f"Generating {duration_seconds}s short (~{budgets['total']} words)")

    research_block = ""
    if research_context:
        research_block = f"""

GROUNDING RESEARCH PACK (authoritative — do not invent conflicting prices):
{research_context}
"""

    visual_note = (
        "For visual_prompt fields: describe the stock chart / year markers when research is present "
        "(e.g. 'vertical dark chart highlighting 2022 crash year')."
        if research_context
        else "visual_prompt: vertical 9:16 frame description — no text"
    )

    user = f"""Write a {duration_seconds}-second YouTube Short / Reel narration about:
"{prompt}"
{research_block}
WORD BUDGET (~135 wpm spoken): total ~{budgets['total']}, hook ~{budgets['hook']},
each body beat ~{budgets['per_beat']}, CTA ~{budgets['cta']}.
Body beats required: {budgets['body_beats']}.
{visual_note}

SPOKEN DELIVERY RULES:
- Write like a human narrator, not a blog post.
- Average sentence ≤ 14 words. Use fragments. Contractions speech.
- Put [pause] before big years/% reveals. Put [breath] between ideas.
- Hook must create curiosity in ≤ 2 sentences.
- Body beats must escalate: cause → twist → payoff.
- CTA: one line, no begging.

Return ONLY JSON:
{{
  "title": "punchy short title",
  "description": "1-2 sentence description + CTA",
  "tags": ["5-8 tags"],
  "hashtags": ["#Shorts", "#topic"],
  "on_screen_text": "optional 3-6 word hook line for burn-in",
  "hook": {{
    "scene_id": "hook",
    "narration": "cold open — year/% /name in first sentence. Include [pause].",
    "visual_prompt": "vertical 9:16 frame description — no text",
    "duration_seconds": 5,
    "emotion": "curiosity",
    "narration_tone": "urgent whisper",
    "use_chart": true
  }},
  "beats": [
    {{
      "scene_id": "beat_1",
      "narration": "body narration with [pause] / [breath]",
      "visual_prompt": "vertical frame — no text",
      "duration_seconds": 8,
      "emotion": "tension",
      "narration_tone": "measured clarity",
      "use_chart": true
    }}
  ],
  "cta": {{
    "scene_id": "cta",
    "narration": "[slow] one-line CTA",
    "visual_prompt": "closing vertical frame — no text",
    "duration_seconds": 4,
    "emotion": "resolve",
    "narration_tone": "warm closure",
    "use_chart": true
  }}
}}

Exact beat count: {budgets['body_beats']}. Stay within word budgets (±20%).
If research pack is present: open on a real % move or year; each beat explains a chart swing with news/events."""

    script = _call_llm_json(
        system, user, max_tokens=3072, label="short script", temperature=0.62
    )

    if channel_config.get("script", {}).get("script_polish", True):
        try:
            polish_extra = ""
            if research_context:
                polish_extra = (
                    "\nPreserve exact years and percentages from the research pack. "
                    "Do not invent prices.\n"
                )
            polish = _call_llm_json(
                system,
                f"""Polish this short for SPOKEN retention and human rhythm.
Keep duration word budgets. Shorten long sentences. Add [pause]/[breath] where a narrator breathes.
Remove clichés and stiff corporate phrasing. Strengthen hook curiosity. Keep scene_ids.{polish_extra}
Return ONLY the full JSON.\n\n{json.dumps(script)}""",
                max_tokens=3072,
                label="short polish",
                temperature=0.35,
            )
            if isinstance(polish, dict) and polish.get("hook"):
                script = polish
        except Exception as e:
            _log(f"Short polish skipped: {e}")

    script["duration_seconds"] = duration_seconds
    script["word_budget"] = budgets
    script["format"] = "short"
    script["prompt"] = prompt
    if research_context:
        script["has_research"] = True

    if channel_config.get("script", {}).get("auto_humanize", True):
        from lib.tts_speak import humanize_spoken_short

        rules = channel_config.get("script", {}).get("humanization_rules", [])
        hook = script.get("hook") or {}
        if hook.get("narration"):
            hook["narration"] = humanize_spoken_short(hook["narration"], rules)
        elif hook.get("text"):
            hook["text"] = humanize_spoken_short(hook["text"], rules)
        script["hook"] = hook
        for beat in script.get("beats") or []:
            if beat.get("narration"):
                beat["narration"] = humanize_spoken_short(beat["narration"], rules)
        cta = script.get("cta")
        if isinstance(cta, dict) and cta.get("narration"):
            cta["narration"] = humanize_spoken_short(cta["narration"], rules)
        elif isinstance(cta, dict) and cta.get("text"):
            cta["text"] = humanize_spoken_short(cta["text"], rules)
        elif isinstance(cta, str):
            script["cta"] = humanize_spoken_short(cta, rules)

    # Soft total word log
    total_words = sum(word_count(s.get("narration", "")) for s in flatten_short_scenes(script))
    _log(f"Short script ready ({total_words} spoken words)")
    return script
